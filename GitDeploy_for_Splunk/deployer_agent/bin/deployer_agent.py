#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitDeploy for Splunk - SH Deployer Agent
Agent à installer sur le Search Head Deployer pour recevoir les commandes
de pull Git et déploiement vers le Search Head Cluster.

Installation: /opt/splunk/etc/apps/deployer_agent/bin/deployer_agent.py
Port: 9998
"""

import os
import sys
import json
import logging
import subprocess
import hashlib
import hmac
import ssl
import base64
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading
import time
import shutil

# ============================================
# CONFIGURATION
# ============================================

# Port d'écoute
AGENT_PORT = 9998

# Chemins Splunk
SPLUNK_HOME = os.environ.get('SPLUNK_HOME', '/opt/splunk')
SHCLUSTER_APPS_PATH = f"{SPLUNK_HOME}/etc/shcluster/apps"
SPLUNK_BIN = f"{SPLUNK_HOME}/bin/splunk"

# Dossier pour les repos Git locaux (persistant)
GIT_REPOS_DIR = f"{SPLUNK_HOME}/var/git_repos"

# Fichier de credentials Splunk (stocké de manière sécurisée sur le serveur)
CREDENTIALS_FILE = f"{SPLUNK_HOME}/etc/apps/deployer_agent/local/credentials.json"

# Certificats SSL
CERTS_DIR = f"{SPLUNK_HOME}/etc/apps/deployer_agent/local/certs"
CERT_FILE = f"{CERTS_DIR}/server.crt"
KEY_FILE = f"{CERTS_DIR}/server.key"

# Vérification TLS pour les opérations Git (dépôts distants). Désactivée par défaut seulement
# si explicitement demandé (certificats auto-signés internes) via cette variable d'environnement.
GIT_TLS_VERIFY = os.environ.get('DEPLOYER_AGENT_GIT_TLS_VERIFY', 'true').lower() != 'false'

# Logs
LOG_DIR = f"{SPLUNK_HOME}/var/log/splunk"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'deployer_agent.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('deployer_agent')

# ============================================
# TOKEN D'AUTHENTIFICATION
# ============================================
# Un token identique codé en dur dans le code source finit par être partagé par toutes les
# installations qui ne l'ont pas explicitement changé (ex: install manuelle en suivant le
# README). On génère donc un token aléatoire au tout premier démarrage et on le persiste,
# plutôt que d'expédier une valeur par défaut réelle dans le code.
AUTH_TOKEN_FILE = f"{SPLUNK_HOME}/etc/apps/deployer_agent/local/auth_token.txt"


def load_or_create_auth_token():
    """Charger le token d'authentification, ou en générer un nouveau au premier démarrage."""
    try:
        if os.path.exists(AUTH_TOKEN_FILE):
            with open(AUTH_TOKEN_FILE, 'r') as f:
                token = f.read().strip()
            if token:
                return token
    except Exception as e:
        logger.error(f"Error reading {AUTH_TOKEN_FILE}: {e}")

    import secrets
    token = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(AUTH_TOKEN_FILE), exist_ok=True)
        with open(AUTH_TOKEN_FILE, 'w') as f:
            f.write(token)
        os.chmod(AUTH_TOKEN_FILE, 0o600)
    except Exception as e:
        logger.error(f"Error saving generated auth token to {AUTH_TOKEN_FILE}: {e}")

    logger.warning("=" * 70)
    logger.warning("No auth token was configured - a new one has been generated.")
    logger.warning(f"Auth token: {token}")
    logger.warning(f"Saved to: {AUTH_TOKEN_FILE}")
    logger.warning("Enter this token as the 'deployer_token' in the GitDeploy configuration.")
    logger.warning("=" * 70)
    return token


AUTH_TOKEN = load_or_create_auth_token()

# ============================================
# GESTION DES CREDENTIALS SÉCURISÉS
# ============================================

def load_credentials():
    """Charger les credentials depuis le fichier sécurisé"""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
        
        # Décoder le mot de passe (base64 simple - pour plus de sécurité, utiliser Splunk's credential store)
        if 'splunk_password_b64' in creds:
            creds['splunk_password'] = base64.b64decode(creds['splunk_password_b64']).decode('utf-8')
            del creds['splunk_password_b64']
        
        logger.info(f"Loaded credentials for user: {creds.get('splunk_user', 'unknown')}")
        return creds
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        return None


def save_credentials(splunk_user, splunk_password, target_uri=None):
    """Sauvegarder les credentials de manière sécurisée"""
    try:
        # Créer le dossier si nécessaire
        os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
        
        creds = {
            'splunk_user': splunk_user,
            'splunk_password_b64': base64.b64encode(splunk_password.encode('utf-8')).decode('utf-8'),
            'target_uri': target_uri,
            'updated_at': datetime.now().isoformat()
        }
        
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(creds, f, indent=2)
        
        # Sécuriser le fichier (lecture seule pour le propriétaire)
        os.chmod(CREDENTIALS_FILE, 0o600)
        
        logger.info(f"Credentials saved for user: {splunk_user}")
        return True
    except Exception as e:
        logger.error(f"Error saving credentials: {e}")
        return False


def get_splunk_credentials(body):
    """
    Récupérer les credentials Splunk.
    Priorité:
    1. Credentials fournis dans la requête
    2. Credentials stockés sur le serveur
    """
    auth_user = body.get('auth_user')
    auth_pass = body.get('auth_pass')
    target_uri = body.get('target_uri')
    
    # Si credentials fournis dans la requête, les utiliser
    if auth_user and auth_pass:
        return auth_user, auth_pass, target_uri
    
    # Sinon, charger depuis le fichier
    stored_creds = load_credentials()
    if stored_creds:
        return (
            stored_creds.get('splunk_user', 'admin'),
            stored_creds.get('splunk_password'),
            target_uri or stored_creds.get('target_uri')
        )
    
    return None, None, target_uri


# État global
deployment_status = {
    "last_pull": None,
    "last_deploy": None,
    "last_error": None,
    "is_deploying": False,
    "history": []
}

# ============================================
# FONCTIONS UTILITAIRES
# ============================================

def verify_token(token):
    """Vérifier le token d'authentification"""
    if not token:
        return False
    return hmac.compare_digest(token, AUTH_TOKEN)


def run_command(cmd, cwd=None, timeout=300, env=None):
    """Exécuter une commande shell (compatible Python 3.6+)"""
    logger.info(f"Running command: {' '.join(cmd)}")
    try:
        # Utiliser l'environnement fourni ou l'environnement système
        cmd_env = env if env else os.environ.copy()
        
        # Compatible Python 3.6 : utiliser stdout/stderr=PIPE au lieu de capture_output
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=cmd_env
        )
        
        # Décoder les sorties (bytes -> str)
        stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
        stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)
        }


def add_to_history(action, status, message, details=None):
    """Ajouter une entrée à l'historique"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "status": status,
        "message": message,
        "details": details
    }
    deployment_status["history"].insert(0, entry)
    # Garder seulement les 50 dernières entrées
    deployment_status["history"] = deployment_status["history"][:50]
    return entry


# ============================================
# OPÉRATIONS GIT
# ============================================

def git_pull_all(repo_url, token=None, apps_subdir="apps", apps_to_deploy=None):
    """
    Cloner/Pull le repo complet et synchroniser les apps
    
    - Si le repo local existe déjà: git pull (plus rapide)
    - Sinon: git clone (première fois)
    
    Note: Utilise toujours la branche par défaut du repo (main/master).
    Le déploiement SH Cluster n'est autorisé que depuis ces branches.
    
    Le repo est structuré ainsi:
    repo/
      apps/
        app1/
        app2/
    
    Args:
        repo_url: URL du repo Git
        token: Token d'accès Git
        apps_subdir: Sous-dossier contenant les apps (défaut: "apps")
        apps_to_deploy: Liste des noms d'apps à déployer (si None, toutes les apps)
    """
    if apps_to_deploy:
        logger.info(f"Pulling selected apps from {repo_url}: {apps_to_deploy}")
    else:
        logger.info(f"Pulling all apps from {repo_url}")
    
    # Créer le dossier pour les repos Git
    os.makedirs(GIT_REPOS_DIR, exist_ok=True)
    
    # Dossier local pour le repo (persistant, pas temporaire)
    repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
    local_repo_dir = os.path.join(GIT_REPOS_DIR, repo_name)
    
    logger.info(f"Local repo directory: {local_repo_dir}")
    
    # Préparer l'URL avec le token
    repo_url_clean = repo_url.strip().strip("'\"").rstrip('/')
    
    if token:
        token = token.strip().strip("'\"")
        if '@' in repo_url_clean and '://' in repo_url_clean:
            protocol = repo_url_clean.split('://')[0]
            rest = repo_url_clean.split('://', 1)[1]
            host_and_path = rest.split('@', 1)[1] if '@' in rest else rest
            repo_url_with_token = f"{protocol}://{token}:@{host_and_path}"
        elif repo_url_clean.startswith('https://') or repo_url_clean.startswith('http://'):
            protocol = repo_url_clean.split('://')[0]
            host_and_path = repo_url_clean.split('://', 1)[1]
            repo_url_with_token = f"{protocol}://{token}:@{host_and_path}"
        else:
            repo_url_with_token = repo_url_clean
    else:
        repo_url_with_token = repo_url_clean
    
    # Environnement Git - vérification SSL désactivable via DEPLOYER_AGENT_GIT_TLS_VERIFY=false
    # (certificats auto-signés internes), active par défaut.
    git_env = os.environ.copy()
    if not GIT_TLS_VERIFY:
        git_env['GIT_SSL_NO_VERIFY'] = 'true'
    
    try:
        git_dir = os.path.join(local_repo_dir, '.git')
        
        if os.path.exists(git_dir):
            # ============================================
            # Le repo existe déjà -> GIT PULL
            # ============================================
            logger.info(f"Repository exists at {local_repo_dir}, performing git pull...")
            
            # Mettre à jour l'URL remote avec le token
            run_command(['git', 'remote', 'set-url', 'origin', repo_url_with_token], 
                       cwd=local_repo_dir, env=git_env)
            
            # Fetch pour récupérer les changements distants
            fetch_result = run_command(['git', 'fetch', 'origin'], cwd=local_repo_dir, env=git_env)
            if not fetch_result["success"]:
                logger.warning(f"Git fetch warning: {fetch_result['stderr']}")
            
            # Reset pour forcer le repo local à matcher le distant (branche par défaut)
            reset_result = run_command(['git', 'reset', '--hard', 'origin/HEAD'], 
                                       cwd=local_repo_dir, env=git_env)
            
            if not reset_result["success"]:
                # Essayer avec origin/main ou origin/master
                reset_result = run_command(['git', 'reset', '--hard', 'origin/main'], 
                                          cwd=local_repo_dir, env=git_env)
                if not reset_result["success"]:
                    reset_result = run_command(['git', 'reset', '--hard', 'origin/master'], 
                                              cwd=local_repo_dir, env=git_env)
            
            # Nettoyer les fichiers non suivis
            run_command(['git', 'clean', '-fd'], cwd=local_repo_dir, env=git_env)
            
            # Remettre l'URL sans token (sécurité)
            run_command(['git', 'remote', 'set-url', 'origin', repo_url_clean], 
                       cwd=local_repo_dir, env=git_env)
            
            if not reset_result["success"]:
                # Si le pull échoue, essayer de supprimer et re-cloner
                logger.warning(f"Git pull failed: {reset_result['stderr']}, trying fresh clone...")
                shutil.rmtree(local_repo_dir, ignore_errors=True)
                
                clone_result = run_command(
                    ['git', 'clone', '--depth', '1', repo_url_with_token, local_repo_dir], 
                    env=git_env
                )
                if not clone_result["success"]:
                    return {
                        "success": False,
                        "message": f"Git clone failed: {clone_result['stderr']}",
                        "apps_updated": []
                    }
                # Remettre l'URL sans token
                run_command(['git', 'remote', 'set-url', 'origin', repo_url_clean], 
                           cwd=local_repo_dir, env=git_env)
            else:
                logger.info("Git pull successful")
        else:
            # ============================================
            # Premier clone -> GIT CLONE
            # ============================================
            logger.info(f"First time: cloning repository to {local_repo_dir}...")
            
            # Supprimer le dossier s'il existe mais n'est pas un repo git
            if os.path.exists(local_repo_dir):
                shutil.rmtree(local_repo_dir, ignore_errors=True)
            
            clone_result = run_command(
                ['git', 'clone', '--depth', '1', repo_url_with_token, local_repo_dir], 
                env=git_env
            )
            
            if not clone_result["success"]:
                return {
                    "success": False,
                    "message": f"Git clone failed: {clone_result['stderr']}",
                    "apps_updated": []
                }
            
            # Remettre l'URL sans token (sécurité)
            run_command(['git', 'remote', 'set-url', 'origin', repo_url_clean], 
                       cwd=local_repo_dir, env=git_env)
            
            logger.info("Git clone successful")
        
        # ============================================
        # Synchroniser les apps vers shcluster/apps
        # ============================================
        
        # Chemin vers le dossier apps dans le repo
        repo_apps_path = os.path.join(local_repo_dir, apps_subdir)
        
        if not os.path.exists(repo_apps_path):
            return {
                "success": False,
                "message": f"Apps directory not found in repo: {apps_subdir}",
                "apps_updated": []
            }
        
        # Créer le dossier shcluster/apps s'il n'existe pas
        os.makedirs(SHCLUSTER_APPS_PATH, exist_ok=True)
        
        apps_updated = []
        apps_skipped = []
        
        def rmtree_error_handler(func, path, exc_info):
            """Handler pour ignorer les erreurs de permission lors de la suppression"""
            import stat
            # Essayer de changer les permissions et réessayer
            try:
                os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
                func(path)
            except Exception as e:
                logger.warning(f"Could not remove {path}: {e} - ignoring")
        
        for app_name in os.listdir(repo_apps_path):
            src_app_path = os.path.join(repo_apps_path, app_name)
            
            if not os.path.isdir(src_app_path):
                continue
            
            # Filtrer les apps si apps_to_deploy est spécifié
            if apps_to_deploy and app_name not in apps_to_deploy:
                logger.info(f"Skipping app (not in selection): {app_name}")
                apps_skipped.append(app_name)
                continue
            
            dest_app_path = os.path.join(SHCLUSTER_APPS_PATH, app_name)
            
            logger.info(f"Syncing app: {app_name}")
            
            # Supprimer l'ancienne version (ignorer les erreurs de permission)
            if os.path.exists(dest_app_path):
                try:
                    shutil.rmtree(dest_app_path, onerror=rmtree_error_handler)
                except Exception as e:
                    logger.warning(f"Could not fully remove {dest_app_path}: {e} - continuing anyway")
            
            # Copier la nouvelle version (compatible Python 3.6)
            try:
                # Python 3.8+ a dirs_exist_ok, pour 3.6/3.7 on supprime d'abord
                if os.path.exists(dest_app_path):
                    shutil.rmtree(dest_app_path, ignore_errors=True)
                shutil.copytree(src_app_path, dest_app_path)
                apps_updated.append(app_name)
                logger.info(f"Updated app: {app_name}")
            except Exception as e:
                logger.error(f"Error copying app {app_name}: {e}")
                # Continuer avec les autres apps
        
        message = f"Successfully updated {len(apps_updated)} apps"
        if apps_skipped:
            message += f" (skipped {len(apps_skipped)} apps not in selection)"
        
        return {
            "success": True,
            "message": message,
            "apps_updated": apps_updated,
            "apps_skipped": apps_skipped
        }
    
    except Exception as e:
        logger.error(f"Error during pull: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": str(e),
            "apps_updated": []
        }


# ============================================
# OPÉRATIONS SPLUNK
# ============================================

def apply_shcluster_bundle(target_uri=None, auth_user=None, auth_pass=None, skip_validation=False):
    """
    Appliquer le bundle au Search Head Cluster
    
    Commande: splunk apply shcluster-bundle -target <uri> -auth <user>:<pass>
    """
    global deployment_status
    
    deployment_status["is_deploying"] = True
    
    try:
        # Le target est OBLIGATOIRE - URI du capitaine
        if not target_uri:
            # Target par défaut - À CONFIGURER selon ton environnement !
            target_uri = "https://localhost:8089"
            logger.warning(f"No target specified, using default: {target_uri}")
        
        # Construire la commande sous forme de liste d'arguments (pas de shell=True) : target_uri,
        # auth_user et auth_pass viennent de la requête HTTP et ne doivent jamais être interprétés
        # par un shell (injection de commande via ';', '|', '$(...)', etc.)
        cmd = [SPLUNK_BIN, 'apply', 'shcluster-bundle', '-target', target_uri]
        if auth_user and auth_pass:
            cmd += ['-auth', f'{auth_user}:{auth_pass}']
        cmd += ['-preserve-lookups', 'true']
        if skip_validation:
            cmd.append('--skip-validation')

        logger.info(f"Applying bundle to {target_uri} as user {auth_user or 'default'}")

        # Répondre "y" au prompt de confirmation via stdin plutôt que via un pipe shell
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600,
                input=b'y\n',
                env={**os.environ}
            )
            
            # Décoder les sorties (bytes -> str)
            stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
            stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
            
            cmd_result = {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": stderr
            }
        except subprocess.TimeoutExpired:
            cmd_result = {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out after 600 seconds"
            }
        except Exception as e:
            cmd_result = {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e)
            }
        
        if cmd_result["success"]:
            deployment_status["last_deploy"] = datetime.now().isoformat()
            add_to_history("deploy", "success", "Bundle applied successfully", cmd_result["stdout"])
            logger.info("Bundle applied successfully!")
        else:
            deployment_status["last_error"] = cmd_result["stderr"]
            add_to_history("deploy", "error", "Bundle apply failed", cmd_result["stderr"])
            logger.error(f"Bundle apply failed: {cmd_result['stderr']}")
        
        return cmd_result
    
    finally:
        deployment_status["is_deploying"] = False


# ============================================
# HANDLER HTTP
# ============================================

class DeployerAgentHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes HTTP de l'agent"""
    
    def send_cors_headers(self):
        """Envoyer les headers CORS"""
        origin = self.headers.get('Origin', '*')
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Auth-Token')
        self.send_header('Access-Control-Allow-Credentials', 'true')
    
    def check_auth(self):
        """Vérifier l'authentification"""
        token = self.headers.get('X-Auth-Token', '')
        if not token:
            # Essayer dans les query params
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            token = params.get('token', [''])[0]
        
        return verify_token(token)
    
    def send_json_response(self, data, status=200):
        """Envoyer une réponse JSON"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, message, status=400):
        """Envoyer une réponse d'erreur"""
        self.send_json_response({"success": False, "error": message}, status)
    
    def do_OPTIONS(self):
        """Gérer les requêtes OPTIONS (CORS preflight)"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Gérer les requêtes GET"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Health check (pas d'auth requise)
        if path == '/health':
            self.send_json_response({
                "status": "ok",
                "service": "deployer_agent",
                "version": "2.1.1",
                "timestamp": datetime.now().isoformat(),
                "shcluster_apps_path": SHCLUSTER_APPS_PATH,
                "git_repos_path": GIT_REPOS_DIR
            })
            return
        
        # Vérifier l'auth pour les autres endpoints
        if not self.check_auth():
            self.send_error_response("Unauthorized", 401)
            return
        
        if path == '/status':
            # Statut du déploiement
            self.send_json_response({
                "success": True,
                "status": deployment_status,
                "shcluster_apps_path": SHCLUSTER_APPS_PATH,
                "git_repos_path": GIT_REPOS_DIR,
                "apps": os.listdir(SHCLUSTER_APPS_PATH) if os.path.exists(SHCLUSTER_APPS_PATH) else []
            })
        
        elif path == '/apps':
            # Lister les apps
            if os.path.exists(SHCLUSTER_APPS_PATH):
                apps = []
                for app_name in os.listdir(SHCLUSTER_APPS_PATH):
                    app_path = os.path.join(SHCLUSTER_APPS_PATH, app_name)
                    if os.path.isdir(app_path):
                        apps.append({
                            "name": app_name,
                            "path": app_path,
                            "is_git_repo": os.path.exists(os.path.join(app_path, '.git'))
                        })
                self.send_json_response({"success": True, "apps": apps})
            else:
                self.send_error_response(f"Path not found: {SHCLUSTER_APPS_PATH}")
        
        elif path == '/history':
            # Historique des déploiements
            self.send_json_response({
                "success": True,
                "history": deployment_status["history"]
            })
        
        elif path == '/credentials':
            # Vérifier si les credentials sont configurés (sans les révéler)
            creds = load_credentials()
            if creds:
                self.send_json_response({
                    "success": True,
                    "configured": True,
                    "user": creds.get('splunk_user', 'unknown'),
                    "target_uri": creds.get('target_uri', 'not set'),
                    "updated_at": creds.get('updated_at', 'unknown')
                })
            else:
                self.send_json_response({
                    "success": True,
                    "configured": False,
                    "message": "No credentials configured. Use POST /credentials to set them."
                })
        
        else:
            self.send_error_response("Not found", 404)
    
    def do_POST(self):
        """Gérer les requêtes POST"""
        # Vérifier l'auth
        if not self.check_auth():
            self.send_error_response("Unauthorized", 401)
            return
        
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        # Lire le body si présent
        content_length = int(self.headers.get('Content-Length', 0))
        body = {}
        if content_length > 0:
            try:
                body = json.loads(self.rfile.read(content_length).decode())
            except:
                pass
        
        # Fusionner params et body
        for key, value in params.items():
            if key not in body:
                body[key] = value[0] if len(value) == 1 else value
        
        logger.info(f"POST {path} - Body: {json.dumps({k: ('****' if k in ['token', 'git_token', 'auth_pass', 'password'] else v) for k, v in body.items()})}")
        
        if path == '/pull':
            # Pull depuis Git (utilise toujours la branche par défaut)
            repo_url = body.get('repo_url') or body.get('git_url')
            git_token = body.get('git_token')
            apps_subdir = body.get('apps_subdir', 'apps')
            
            if not repo_url:
                self.send_error_response("repo_url is required")
                return
            
            logger.info(f"Pulling from {repo_url} (default branch)")
            result = git_pull_all(repo_url, git_token, apps_subdir)
            
            if result["success"]:
                deployment_status["last_pull"] = datetime.now().isoformat()
                add_to_history("pull", "success", result["message"], result["apps_updated"])
            else:
                deployment_status["last_error"] = result["message"]
                add_to_history("pull", "error", result["message"])
            
            self.send_json_response(result)
        
        elif path == '/deploy':
            # Appliquer le bundle
            if deployment_status["is_deploying"]:
                self.send_error_response("Deployment already in progress")
                return
            
            target_uri = body.get('target_uri')
            auth_user = body.get('auth_user', 'admin')
            auth_pass = body.get('auth_pass')
            skip_validation = body.get('skip_validation', False)
            
            # Lancer le déploiement dans un thread séparé pour ne pas bloquer
            def deploy_async():
                result = apply_shcluster_bundle(target_uri, auth_user, auth_pass, skip_validation)
                logger.info(f"Deploy result: {result}")
            
            thread = threading.Thread(target=deploy_async)
            thread.start()
            
            self.send_json_response({
                "success": True,
                "message": "Deployment started",
                "status": "deploying"
            })
        
        elif path == '/credentials':
            # Sauvegarder les credentials Splunk
            splunk_user = body.get('splunk_user') or body.get('auth_user')
            splunk_password = body.get('splunk_password') or body.get('auth_pass')
            target_uri = body.get('target_uri')
            
            if not splunk_user or not splunk_password:
                self.send_error_response("splunk_user and splunk_password are required")
                return
            
            success = save_credentials(splunk_user, splunk_password, target_uri)
            
            if success:
                self.send_json_response({
                    "success": True,
                    "message": f"Credentials saved for user: {splunk_user}"
                })
            else:
                self.send_error_response("Failed to save credentials")
        
        elif path == '/pull-and-deploy':
            # Pull puis deploy en une seule opération (utilise toujours la branche par défaut)
            repo_url = body.get('repo_url') or body.get('git_url')
            git_token = body.get('git_token')
            apps_subdir = body.get('apps_subdir', 'apps')
            apps_to_deploy = body.get('apps_to_deploy')  # Liste des apps à déployer
            
            # Récupérer les credentials (depuis la requête OU depuis le fichier stocké)
            auth_user, auth_pass, target_uri = get_splunk_credentials(body)
            
            if not repo_url:
                self.send_error_response("repo_url is required")
                return
            
            if not auth_user or not auth_pass:
                self.send_error_response("Splunk credentials required. Either provide auth_user/auth_pass or configure with POST /credentials")
                return
            
            if deployment_status["is_deploying"]:
                self.send_error_response("Deployment already in progress")
                return
            
            # Log des apps à déployer (sans les credentials)
            if apps_to_deploy:
                logger.info(f"Apps to deploy filter: {apps_to_deploy}")
            else:
                logger.info("No apps filter, deploying all apps")
            
            logger.info(f"Using credentials for user: {auth_user}, target: {target_uri or 'default'}")
            
            # Lancer le processus complet dans un thread
            def pull_and_deploy_async():
                # Étape 1: Pull (toujours depuis la branche par défaut)
                logger.info("Step 1: Pulling from Git (default branch)...")
                pull_result = git_pull_all(repo_url, git_token, apps_subdir, apps_to_deploy)
                
                if not pull_result["success"]:
                    deployment_status["last_error"] = pull_result["message"]
                    add_to_history("pull-and-deploy", "error", f"Pull failed: {pull_result['message']}")
                    return
                
                deployment_status["last_pull"] = datetime.now().isoformat()
                add_to_history("pull", "success", pull_result["message"], pull_result["apps_updated"])
                
                # Étape 2: Deploy
                logger.info("Step 2: Applying bundle...")
                deploy_result = apply_shcluster_bundle(target_uri, auth_user, auth_pass)
                
                if deploy_result["success"]:
                    add_to_history("pull-and-deploy", "success", 
                                 f"Pulled {len(pull_result['apps_updated'])} apps and deployed successfully")
                else:
                    add_to_history("pull-and-deploy", "error", 
                                 f"Pull succeeded but deploy failed: {deploy_result['stderr']}")
            
            thread = threading.Thread(target=pull_and_deploy_async)
            thread.start()
            
            self.send_json_response({
                "success": True,
                "message": "Pull and deploy started",
                "status": "processing",
                "apps_filter": apps_to_deploy,
                "using_stored_credentials": body.get('auth_pass') is None
            })
        
        else:
            self.send_error_response("Not found", 404)
    
    def log_message(self, format, *args):
        logger.debug(format % args)


# ============================================
# SERVEUR PRINCIPAL
# ============================================

def start_server(port=AGENT_PORT, use_ssl=True):
    """Démarrer le serveur"""
    server = HTTPServer(('0.0.0.0', port), DeployerAgentHandler)
    
    ssl_enabled = False
    
    if use_ssl:
        if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(CERT_FILE, KEY_FILE)
                server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
                ssl_enabled = True
                logger.info(f"SSL enabled using: {CERT_FILE}")
            except Exception as e:
                logger.warning(f"Could not load SSL certificates: {e}")
        else:
            logger.warning(f"SSL certificates not found at {CERTS_DIR}")
            logger.warning("To create certificates, run:")
            logger.warning(f"  mkdir -p {CERTS_DIR}")
            logger.warning(f"  openssl req -x509 -newkey rsa:4096 -keyout {KEY_FILE} -out {CERT_FILE} -days 365 -nodes -subj '/CN=deployer-agent'")
    
    protocol = "HTTPS" if ssl_enabled else "HTTP"
    logger.info(f"Deployer Agent v2.1.1 listening on 0.0.0.0:{port} ({protocol})")
    logger.info(f"SHCluster apps path: {SHCLUSTER_APPS_PATH}")
    logger.info(f"Git repos cache path: {GIT_REPOS_DIR}")
    
    server.serve_forever()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='SH Deployer Agent')
    parser.add_argument('--port', type=int, default=AGENT_PORT, help=f'Port (default: {AGENT_PORT})')
    parser.add_argument('--no-ssl', action='store_true', help='Disable SSL')
    args = parser.parse_args()
    
    logger.info("Starting SH Deployer Agent v2.1.1...")
    start_server(args.port, not args.no_ssl)
