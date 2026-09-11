#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitDeploy for Splunk - Main Server
Serveur HTTP pour pousser les applications Splunk vers Git
et déployer vers le Search Head Cluster via le SH Deployer

Avec système de licence par fichier .lic
"""

import sys
import os
import json
import logging
import tempfile
import shutil
import subprocess
import ssl
import re
import hmac
import secrets
import urllib.request
import urllib.error
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Importer le validateur de licence
# En production, ce fichier sera dans le même dossier
try:
    from license_validator import (
        validate_license, 
        save_license_file, 
        check_limits, 
        increment_usage,
        get_splunk_hostname,
        get_usage_stats,
        parse_license_content
    )
except ImportError:
    # Fallback pour le développement
    print("Warning: license_validator not found, running without license checks")
    def validate_license(): return {"valid": True, "type": "dev", "days_remaining": 999}
    def save_license_file(c): return {"success": True}
    def check_limits(): return {"allowed": True}
    def increment_usage(): return {}
    def get_splunk_hostname(): return "dev-host"
    def get_usage_stats(): return {}
    def parse_license_content(c): return {}

# ============================================
# CONFIGURATION
# ============================================

# Chemins Splunk
SPLUNK_HOME = os.environ.get('SPLUNK_HOME', '/opt/splunk')
APP_HOME = os.path.join(SPLUNK_HOME, 'etc', 'apps', 'gitdeploy_app')
CONFIG_FILE = os.path.join(APP_HOME, 'local', 'config.json')

# Configuration par défaut
DEFAULT_CONFIG = {
    "api": {
        "url": "",
        "port": 9999,
        "useProxy": True,
        # Token requis (header X-Auth-Token ou Authorization: Bearer) pour tous les
        # endpoints POST. Généré automatiquement au premier démarrage si vide (voir plus bas).
        "token": "",
        # Origines autorisées pour CORS. Si vide, le comportement historique (permissif) est
        # conservé avec un avertissement - à restreindre en production.
        "allowedOrigins": []
    },
    "deployer": {
        "enabled": False,
        "host": "",
        "port": 9998,
        "token": "",
        "useSSL": True
    },
    "license": {
        "checkInterval": 24
    },
    "advanced": {
        "logLevel": "INFO",
        "timeout": 30,
        "gitTimeout": 120,
        # Si False, les certificats TLS (Git et appels vers le SH Deployer) ne sont pas
        # vérifiés. À activer uniquement si vous utilisez des certificats auto-signés internes.
        "tlsVerify": True
    }
}

def load_config():
    """Charger la configuration depuis le fichier"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Fusionner avec la config par défaut pour les clés manquantes
                return {**DEFAULT_CONFIG, **config}
    except Exception as e:
        logger.error(f"Erreur chargement config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Sauvegarder la configuration dans le fichier"""
    try:
        local_dir = os.path.join(APP_HOME, 'local')
        os.makedirs(local_dir, exist_ok=True)
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        os.chmod(CONFIG_FILE, 0o600)
        logger.info(f"Configuration sauvegardée: {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde config: {e}")
        return False

# Charger la configuration au démarrage
APP_CONFIG = load_config()

# Configuration du SH Deployer (depuis la config ou valeurs par défaut)
SH_DEPLOYER_CONFIG = {
    "enabled": APP_CONFIG.get("deployer", {}).get("enabled", False),
    "host": APP_CONFIG.get("deployer", {}).get("host", ""),
    "port": APP_CONFIG.get("deployer", {}).get("port", 9998),
    "use_ssl": APP_CONFIG.get("deployer", {}).get("useSSL", True),
    "token": APP_CONFIG.get("deployer", {}).get("token", ""),
    "timeout": APP_CONFIG.get("advanced", {}).get("timeout", 30)
}

# Configuration du logging
log_dir = '/opt/splunk/var/log/splunk'
os.makedirs(log_dir, exist_ok=True)

log_level = getattr(logging, APP_CONFIG.get("advanced", {}).get("logLevel", "INFO"), logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'gitdeploy.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('gitdeploy')

# S'assurer qu'un token API est configuré. Sans authentification, n'importe qui pouvant
# atteindre ce port pourrait déclencher un push Git ou un déploiement SH Cluster : on refuse
# de démarrer "ouvert" et on génère un token la première fois plutôt que de laisser l'API
# sans protection.
if not APP_CONFIG.get('api', {}).get('token'):
    _generated_token = secrets.token_hex(32)
    APP_CONFIG.setdefault('api', {})['token'] = _generated_token
    save_config(APP_CONFIG)
    logger.warning("=" * 70)
    logger.warning("No API token was configured - a new one has been generated.")
    logger.warning(f"API token: {_generated_token}")
    logger.warning("Enter this token in the GitDeploy configuration page so the dashboard")
    logger.warning("can authenticate against this server. It is stored in local/config.json.")
    logger.warning("=" * 70)


def get_tls_verify():
    """Indique si les certificats TLS doivent être vérifiés (Git et appels au SH Deployer)."""
    return bool(APP_CONFIG.get('advanced', {}).get('tlsVerify', True))


APP_ID_RE = re.compile(r'^[A-Za-z0-9_\-]+$')
BRANCH_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]*$')


def validate_branch_name(branch):
    """Valider un nom de branche Git pour éviter l'injection d'arguments (ex: '--force')."""
    branch = (branch or '').strip()
    if not branch or '..' in branch or not BRANCH_NAME_RE.match(branch):
        raise ValueError(f"Invalid git branch name: {branch!r}")
    return branch


class GitPusherRequestHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes HTTP"""
    
    def send_cors_headers(self):
        """Envoyer les headers CORS complets"""
        origin = self.headers.get('Origin', '')
        allowed_origins = APP_CONFIG.get('api', {}).get('allowedOrigins') or []

        if allowed_origins:
            # Liste blanche configurée : ne refléter l'origine que si elle y figure
            if origin in allowed_origins:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Access-Control-Allow-Credentials', 'true')
        else:
            # Aucune liste configurée : comportement permissif historique.
            # À restreindre via api.allowedOrigins dans la configuration en production.
            self.send_header('Access-Control-Allow-Origin', origin or '*')
            self.send_header('Access-Control-Allow-Credentials', 'true')

        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Origin, X-Splunk-Form-Key, X-Auth-Token')
        self.send_header('Access-Control-Max-Age', '86400')  # Cache preflight 24h

    def check_api_token(self):
        """Vérifier le token d'authentification API (requis pour tous les endpoints POST)."""
        expected = APP_CONFIG.get('api', {}).get('token', '')
        if not expected:
            # Ne devrait plus se produire (token auto-généré au démarrage) : on refuse par défaut.
            return False

        token = self.headers.get('X-Auth-Token', '')
        if not token:
            auth_header = self.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[len('Bearer '):]

        return bool(token) and hmac.compare_digest(token, expected)
    
    def do_OPTIONS(self):
        """Traiter les requêtes OPTIONS (CORS preflight)"""
        logger.info(f"OPTIONS request from {self.headers.get('Origin', 'unknown')}")
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
        # Important: ne rien écrire dans le body pour OPTIONS
        return
    
    def do_GET(self):
        """Traiter les requêtes GET"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            # ============================================
            # ENDPOINTS LICENCE
            # ============================================
            
            if path == '/license' or path == '/license/status':
                # Récupérer le statut de la licence
                validation = validate_license()
                usage = get_usage_stats()
                hostname = get_splunk_hostname()
                
                response = {
                    "status": "valid" if validation.get("valid") else "invalid",
                    "hostname": hostname,
                    "license": validation if validation.get("valid") else None,
                    "error": validation.get("error") if not validation.get("valid") else None,
                    "error_code": validation.get("error_code") if not validation.get("valid") else None,
                    "usage": usage
                }
                self.wfile.write(json.dumps(response).encode())
            
            elif path == '/license/hostname':
                # Juste le hostname
                response = {"hostname": get_splunk_hostname()}
                self.wfile.write(json.dumps(response).encode())
            
            elif path == '/license/file':
                # Charger la licence depuis le fichier sur le serveur
                license_file = os.path.join(APP_HOME, 'local', 'license.lic')
                
                if os.path.exists(license_file):
                    try:
                        with open(license_file, 'r') as f:
                            license_content = f.read()
                        response = {
                            "success": True,
                            "content": license_content
                        }
                    except Exception as e:
                        response = {
                            "success": False,
                            "error": f"Erreur lecture fichier: {str(e)}"
                        }
                else:
                    response = {
                        "success": False,
                        "error": "Aucun fichier de licence sur le serveur"
                    }
                
                self.wfile.write(json.dumps(response).encode())
            
            # ============================================
            # ENDPOINT CONFIGURATION
            # ============================================
            
            elif path == '/config':
                # Retourner la configuration actuelle
                config = load_config()
                # Masquer les tokens pour la sécurité
                if 'deployer' in config and 'token' in config['deployer']:
                    config['deployer']['token'] = '***' if config['deployer']['token'] else ''
                if 'api' in config and 'token' in config['api']:
                    config['api']['token'] = '***' if config['api']['token'] else ''
                self.wfile.write(json.dumps(config).encode())
            
            elif path == '/health':
                # Health check
                response = {
                    "status": "ok",
                    "service": "gitdeploy",
                    "timestamp": datetime.now().isoformat(),
                    "sh_deployer": {
                        "enabled": SH_DEPLOYER_CONFIG.get("enabled", True),
                        "host": SH_DEPLOYER_CONFIG.get("host"),
                        "port": SH_DEPLOYER_CONFIG.get("port")
                    }
                }
                self.wfile.write(json.dumps(response).encode())
            
            # ============================================
            # ENDPOINTS SH DEPLOYER
            # ============================================
            
            elif path == '/deployer/health':
                # Vérifier la santé du SH Deployer
                result = call_deployer_agent("/health")
                if result.get("success"):
                    response = {
                        "status": "ok",
                        "deployer": result.get("data"),
                        "config": {
                            "host": SH_DEPLOYER_CONFIG.get("host"),
                            "port": SH_DEPLOYER_CONFIG.get("port")
                        }
                    }
                else:
                    response = {
                        "status": "error",
                        "error": result.get("error"),
                        "config": {
                            "host": SH_DEPLOYER_CONFIG.get("host"),
                            "port": SH_DEPLOYER_CONFIG.get("port")
                        }
                    }
                self.wfile.write(json.dumps(response).encode())
            
            elif path == '/deployer/status':
                # Statut du SH Deployer
                result = get_deployer_status()
                self.wfile.write(json.dumps(result).encode())
            
            elif path == '/deployer/config':
                # Configuration actuelle du SH Deployer
                response = {
                    "enabled": SH_DEPLOYER_CONFIG.get("enabled", True),
                    "host": SH_DEPLOYER_CONFIG.get("host"),
                    "port": SH_DEPLOYER_CONFIG.get("port"),
                    "use_ssl": SH_DEPLOYER_CONFIG.get("use_ssl", True)
                }
                self.wfile.write(json.dumps(response).encode())
            
            else:
                response = {"error": "Unknown endpoint", "path": path}
                self.wfile.write(json.dumps(response).encode())
        
        except Exception as e:
            logger.error(f"GET error: {e}")
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_POST(self):
        """Traiter les requêtes POST"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Toutes les requêtes POST modifient un état (config, licence, push Git, déploiement) :
        # elles nécessitent toutes le token API.
        if not self.check_api_token():
            logger.warning(f"Unauthorized POST to {path} from {self.client_address[0]}")
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "Missing or invalid API token"
            }).encode())
            return

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_cors_headers()
        self.end_headers()

        try:
            logger.info(f"POST request to {path}")
            
            # ============================================
            # ENDPOINT CONFIGURATION
            # ============================================
            
            if path == '/config':
                # Sauvegarder la configuration
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                
                try:
                    new_config = json.loads(body)
                    
                    # Charger la config existante pour préserver le token si masqué
                    existing_config = load_config()
                    
                    # Si un token est masqué (***), garder l'ancien
                    if new_config.get('deployer', {}).get('token') == '***':
                        new_config['deployer']['token'] = existing_config.get('deployer', {}).get('token', '')
                    if new_config.get('api', {}).get('token') == '***':
                        new_config.setdefault('api', {})['token'] = existing_config.get('api', {}).get('token', '')

                    # Sauvegarder
                    if save_config(new_config):
                        # Recharger la config globale
                        global APP_CONFIG, SH_DEPLOYER_CONFIG
                        APP_CONFIG = load_config()
                        SH_DEPLOYER_CONFIG = {
                            "enabled": APP_CONFIG.get("deployer", {}).get("enabled", False),
                            "host": APP_CONFIG.get("deployer", {}).get("host", ""),
                            "port": APP_CONFIG.get("deployer", {}).get("port", 9998),
                            "use_ssl": APP_CONFIG.get("deployer", {}).get("useSSL", True),
                            "token": APP_CONFIG.get("deployer", {}).get("token", ""),
                            "timeout": APP_CONFIG.get("advanced", {}).get("timeout", 30)
                        }
                        
                        response = {"success": True, "message": "Configuration sauvegardée"}
                    else:
                        response = {"success": False, "error": "Erreur lors de la sauvegarde"}
                        
                except json.JSONDecodeError as e:
                    response = {"success": False, "error": f"JSON invalide: {str(e)}"}
                except Exception as e:
                    logger.error(f"Erreur sauvegarde config: {e}")
                    response = {"success": False, "error": str(e)}
                
                self.wfile.write(json.dumps(response).encode())
                return
            
            # ============================================
            # ENDPOINTS LICENCE
            # ============================================
            
            elif path == '/license/upload' or path == '/license/save':
                # Sauvegarder la licence sur le serveur (fichier). La signature RSA est
                # revérifiée ici côté serveur (voir license_validator.save_license_file) avant
                # d'écrire quoi que ce soit sur disque : on ne fait plus confiance à la seule
                # validation côté client pour accepter le contenu.
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')

                try:
                    data = json.loads(body)
                    license_content = data.get('license_content', '')
                except:
                    license_content = body

                if not license_content:
                    response = {"success": False, "error": "Contenu de licence vide"}
                else:
                    save_result = save_license_file(license_content)
                    if save_result.get('success'):
                        logger.info("Licence sauvegardée sur le serveur (signature vérifiée)")
                        response = {
                            "success": True,
                            "message": "Licence sauvegardée sur le serveur"
                        }
                    else:
                        logger.error(f"Erreur sauvegarde licence: {save_result.get('error')}")
                        response = {
                            "success": False,
                            "error": save_result.get('error', 'Erreur de sauvegarde')
                        }

                self.wfile.write(json.dumps(response).encode())
                return
            
            elif path == '/license/delete':
                # Supprimer la licence
                license_path = os.path.join(APP_HOME, 'local', 'license.lic')
                if os.path.exists(license_path):
                    os.remove(license_path)
                    logger.info(f"Licence supprimée: {license_path}")
                    response = {"success": True, "message": "Licence supprimée"}
                else:
                    response = {"success": False, "error": "Aucune licence à supprimer"}
                
                self.wfile.write(json.dumps(response).encode())
                return
            
            # ============================================
            # ENDPOINT PUSH GIT
            # ============================================
            
            elif path == '/push' or path.startswith('/services/'):
                # Vérification de licence côté serveur (la validation RSA côté client reste une
                # aide UX, mais l'application de la limite doit être décidée par le serveur).
                license_check = check_limits()
                if not license_check.get("allowed", True):
                    response = {
                        "status": "error",
                        "error_code": "LICENSE_ERROR",
                        "message": license_check.get("error", "Licence invalide ou limite atteinte")
                    }
                    self.wfile.write(json.dumps(response).encode())
                    return

                # Les paramètres (y compris les secrets git_token/deployer_token) sont attendus
                # dans le corps JSON de la requête plutôt que dans la query string, pour éviter
                # qu'ils ne se retrouvent dans les logs de proxy/access log.
                params = self.parse_request_params(query_params)
                self.handle_git_push(params)
                return

            else:
                # Traiter comme un push Git (compatibilité)
                params = self.parse_request_params(query_params)
                self.handle_git_push(params)
        
        except Exception as e:
            logger.error(f"POST error: {str(e)}", exc_info=True)
            response = {
                "status": "error",
                "message": f"Error: {str(e)}"
            }
            self.wfile.write(json.dumps(response).encode())
    
    def parse_request_params(self, query_params):
        """
        Fusionner les paramètres de la query string (compatibilité) avec le corps JSON de la
        requête (prioritaire). Les secrets (tokens) doivent être envoyés dans le corps JSON,
        jamais dans l'URL, pour éviter qu'ils ne finissent dans des logs d'accès de proxy.
        """
        merged = {}
        for key, values in query_params.items():
            merged[key] = values[0] if len(values) == 1 else values

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            try:
                raw_body = self.rfile.read(content_length).decode('utf-8')
                body = json.loads(raw_body) if raw_body else {}
                if isinstance(body, dict):
                    merged.update(body)
            except Exception as e:
                logger.warning(f"Could not parse JSON body: {e}")

        return merged

    def handle_git_push(self, params):
        """Gérer le push Git et optionnellement le déploiement vers SH Cluster"""
        try:
            # Extraire les paramètres
            git_url = params.get('git_url', '')
            git_branch = params.get('git_branch', 'main')
            git_token = params.get('git_token', '')
            commit_message = params.get('commit_message', '')
            apps_json = params.get('apps', params.get('dashboards', '[]'))
            shcluster_apps_json = params.get('shcluster_apps', '[]')  # Apps pour le SH Cluster
            user = params.get('user', 'unknown')

            # Nettoyer l'URL Git (supprimer guillemets, espaces, slash final)
            git_url = git_url.strip().strip("'\"").rstrip('/')
            git_token = git_token.strip().strip("'\"")

            # Valider le nom de branche pour empêcher l'injection d'arguments Git (ex: "--force")
            try:
                git_branch = validate_branch_name(git_branch)
            except ValueError as e:
                logger.warning(f"Rejected push: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
                return

            logger.info(f"Cleaned git_url: {git_url}")

            # Paramètres pour le déploiement SH Cluster
            deploy_to_shcluster = str(params.get('deploy_to_shcluster', 'false')).lower() == 'true'
            deployer_host = params.get('deployer_host', SH_DEPLOYER_CONFIG.get('host', ''))
            deployer_token = params.get('deployer_token', SH_DEPLOYER_CONFIG.get('token', ''))
            sh_auth_user = params.get('sh_auth_user', '')
            sh_auth_pass = params.get('sh_auth_pass', '')

            # Paramètres de licence (envoyés par le client)
            license_type = params.get('license_type', '')
            license_id = params.get('license_id', '')

            logger.info(f"Parameters: git_url={git_url}, branch={git_branch}, user={user}, deploy_to_shcluster={deploy_to_shcluster}")

            # Parser les apps pour Git
            try:
                apps = json.loads(apps_json) if isinstance(apps_json, str) else apps_json
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"JSON parse error for apps: {e}")
                apps = []

            # Parser les apps pour SH Cluster
            try:
                shcluster_apps = json.loads(shcluster_apps_json) if isinstance(shcluster_apps_json, str) else shcluster_apps_json
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"JSON parse error for shcluster_apps: {e}")
                shcluster_apps = apps  # Fallback: utiliser toutes les apps

            # Parser les dashboards sélectionnés par app
            dashboards_by_app_json = params.get('dashboards_by_app', '{}')
            try:
                dashboards_by_app = json.loads(dashboards_by_app_json) if isinstance(dashboards_by_app_json, str) else dashboards_by_app_json
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"JSON parse error for dashboards_by_app: {e}")
                dashboards_by_app = {}
            
            logger.info(f"Apps for Git: {len(apps)}, Apps for SH Cluster: {len(shcluster_apps)}")
            if dashboards_by_app:
                logger.info(f"Selective dashboards: {dashboards_by_app}")
            
            # NOTE: La vérification des limites est maintenant faite côté client
            # Le serveur fait confiance aux informations envoyées par le client
            
            # Valider les paramètres
            if not git_url or not git_token or not commit_message or not apps:
                response = {
                    "status": "error",
                    "message": "Missing required parameters"
                }
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Créer un répertoire temporaire dans /opt (plus d'espace que /tmp)
            git_temp_base = '/opt/splunk_git_temp'
            os.makedirs(git_temp_base, exist_ok=True)
            temp_dir = tempfile.mkdtemp(prefix='splunk_git_', dir=git_temp_base)
            logger.info(f"Created temp directory: {temp_dir}")
            
            try:
                # Préparer l'URL Git avec le token
                git_url_with_token = self.prepare_git_url(git_url, git_token)
                
                logger.info("Cloning repository...")
                self.clone_repository(temp_dir, git_url_with_token, git_branch)
                
                # Récupérer les applications
                logger.info("Fetching applications from Splunk...")
                app_directories = self.fetch_apps_directories(apps)
                
                # Créer le dossier apps
                apps_dir = os.path.join(temp_dir, 'apps')
                os.makedirs(apps_dir, exist_ok=True)
                
                # Copier les applications
                logger.info("Copying applications to repository...")
                apps_copied = 0
                for app_data in app_directories:
                    app_name = app_data['name']
                    app_path = app_data['path']
                    dest_path = os.path.join(apps_dir, app_name)
                    
                    if os.path.exists(app_path):
                        # Vérifier si on a une sélection fine de dashboards pour cette app
                        selected_dashboards = dashboards_by_app.get(app_name, [])
                        
                        if selected_dashboards:
                            # Mode sélectif: mettre à jour uniquement les dashboards sélectionnés
                            # NE PAS supprimer le dossier existant pour conserver les autres fichiers
                            logger.info(f"Selective update for {app_name}: {len(selected_dashboards)} dashboard(s)")
                            self.update_app_selective(app_path, dest_path, selected_dashboards)
                        else:
                            # Mode complet: remplacer toute l'application
                            if os.path.exists(dest_path):
                                logger.info(f"Removing old version of {app_name}")
                                shutil.rmtree(dest_path)
                            shutil.copytree(app_path, dest_path)
                        
                        apps_copied += 1
                        
                        # Compter les fichiers copiés
                        file_count = sum(len(files) for _, _, files in os.walk(dest_path))
                        logger.info(f"Copied app: {app_name} ({file_count} files)")
                    else:
                        logger.warning(f"App path not found: {app_path}")
                
                logger.info(f"Total apps copied: {apps_copied}")
                
                # Configurer git
                subprocess.run(['git', 'config', 'user.email', 'splunk@splunk.local'], 
                             cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(['git', 'config', 'user.name', 'Splunk GitDeploy for Splunk'], 
                             cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Reconfigurer le remote origin avec l'URL contenant le token
                # Cela garantit que le push utilisera l'authentification
                logger.info("Configuring remote origin with authentication...")
                subprocess.run(['git', 'remote', 'set-url', 'origin', git_url_with_token], 
                             cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Ajouter TOUS les fichiers (y compris les suppressions)
                subprocess.run(['git', 'add', '--all'], cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Afficher le statut Git pour debug
                status_check = subprocess.run(['git', 'status', '--short'], 
                                             cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if status_check.stdout.strip():
                    logger.info(f"Git changes detected:\n{status_check.stdout[:500]}")
                else:
                    logger.info("No Git changes detected")
                
                # Message de commit avec infos de licence (envoyées par le client)
                full_message = f"{commit_message}\n\n"
                full_message += f"Pushed by: {user}\n"
                full_message += f"License: {license_id or 'N/A'} ({license_type or 'N/A'})\n"
                full_message += f"Timestamp: {datetime.now().isoformat()}"
                
                # Vérifier s'il y a des changements à committer
                status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                              cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if status_result.stdout.strip():
                    # Il y a des changements, faire le commit
                    result = subprocess.run(['git', 'commit', '-m', full_message], 
                                          cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode != 0:
                        logger.warning(f"Commit warning: {result.stderr}")
                    else:
                        logger.info("Commit created successfully")
                else:
                    logger.info("No changes detected, skipping commit")
                
                logger.info("Pushing to Git...")

                # Vérification SSL désactivable uniquement via advanced.tlsVerify=false en config
                # (certificats auto-signés/internes) - active par défaut.
                git_env = os.environ.copy()
                if not get_tls_verify():
                    git_env['GIT_SSL_NO_VERIFY'] = 'true'

                # Debug: afficher le remote actuel
                remote_check = subprocess.run(['git', 'remote', '-v'],
                                             cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                logger.info(f"Current remotes:\n{remote_check.stdout}")

                # Méthode 1: Essayer avec git push origin
                # "--" empêche git_branch d'être interprété comme une option même s'il commence
                # par des caractères inattendus (défense en profondeur, en plus de validate_branch_name)
                result = subprocess.run(['git', 'push', 'origin', '--', git_branch],
                                      cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, env=git_env)

                if result.returncode != 0:
                    # Vérifier si c'est juste "Everything up-to-date"
                    if "Everything up-to-date" in result.stderr or "Everything up-to-date" in result.stdout:
                        logger.info("Repository is already up-to-date")
                    else:
                        logger.warning(f"Push with 'origin' failed: {result.stderr}")
                        logger.info("Trying direct URL push...")

                        # Méthode 2: Pousser directement vers l'URL avec token
                        result = subprocess.run(['git', 'push', git_url_with_token, '--', git_branch],
                                              cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, env=git_env)
                        
                        if result.returncode != 0:
                            if "Everything up-to-date" in result.stderr or "Everything up-to-date" in result.stdout:
                                logger.info("Repository is already up-to-date")
                            else:
                                logger.error(f"Direct push also failed: {result.stderr}")
                                raise Exception(f"Push failed: {result.stderr}")
                
                # Incrémenter le compteur d'utilisation côté serveur (fait foi pour check_limits(),
                # contrairement au compteur JavaScript dans le localStorage du navigateur qui peut
                # être modifié par l'utilisateur).
                increment_usage()

                logger.info("Git push successful!")
                
                # ============================================
                # DÉPLOIEMENT VERS SH CLUSTER (optionnel)
                # ============================================
                
                deployer_result = None
                shcluster_apps_deployed = 0
                
                if deploy_to_shcluster:
                    # Vérifier que la branche est autorisée pour le déploiement SH Cluster
                    allowed_branches = ['main', 'master']
                    if git_branch.lower() not in allowed_branches:
                        logger.warning(f"SH Cluster deployment blocked: branch '{git_branch}' not allowed (only main/master)")
                        deployer_result = {
                            "success": False,
                            "error": f"SH Cluster deployment only allowed on main/master branch. Current branch: {git_branch}"
                        }
                    else:
                        logger.info("Triggering deployment to SH Cluster...")
                        
                        # Extraire les IDs des apps à déployer sur le SH Cluster
                        shcluster_app_ids = [app.get('id') or app.get('name') for app in shcluster_apps]
                        logger.info(f"Apps to deploy to SH Cluster: {shcluster_app_ids}")
                        
                        shcluster_apps_deployed = len(shcluster_app_ids)
                        
                        # Configurer le deployer
                        deployer_config = SH_DEPLOYER_CONFIG.copy()
                        if deployer_host:
                            deployer_config["host"] = deployer_host
                        if deployer_token:
                            deployer_config["token"] = deployer_token
                        
                        # Appeler le SH Deployer pour pull + deploy
                        # Note: on ne passe plus git_branch car le deployer utilise toujours main/master
                        deployer_result = trigger_deployer_pull_and_deploy(
                            git_url=git_url,
                            git_token=git_token,
                            auth_user=sh_auth_user if sh_auth_user else None,
                            auth_pass=sh_auth_pass if sh_auth_pass else None,
                            config=deployer_config,
                            apps_to_deploy=shcluster_app_ids  # Liste des apps à déployer
                        )
                        
                        if deployer_result.get("success"):
                            logger.info(f"SH Cluster deployment triggered successfully for {shcluster_apps_deployed} apps")
                        else:
                            logger.error(f"SH Cluster deployment failed: {deployer_result.get('error')}")
                
                # Préparer la réponse
                response = {
                    "status": "success",
                    "message": f"Successfully pushed {len(app_directories)} application(s) to Git",
                    "apps_pushed": len(app_directories),
                    "license_type": license_type or "N/A"
                }
                
                # Ajouter les infos de déploiement si activé
                if deploy_to_shcluster:
                    response["shcluster_deployment"] = {
                        "triggered": True,
                        "apps_count": shcluster_apps_deployed,
                        "success": deployer_result.get("success", False) if deployer_result else False,
                        "message": deployer_result.get("data", {}).get("message") if deployer_result and deployer_result.get("success") else deployer_result.get("error") if deployer_result else "Not triggered"
                    }
                    
                    if deployer_result and deployer_result.get("success"):
                        response["message"] += f" and triggered SH Cluster deployment ({shcluster_apps_deployed} apps)"
                    else:
                        response["message"] += " (SH Cluster deployment failed)"
                
                self.wfile.write(json.dumps(response).encode())
            
            finally:
                logger.info(f"Cleaning up {temp_dir}")
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        except Exception as e:
            logger.error(f"Git push error: {str(e)}", exc_info=True)
            response = {
                "status": "error",
                "message": f"Error: {str(e)}"
            }
            self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        logger.debug(format % args)
    
    @staticmethod
    def prepare_git_url(git_url, token):
        """Préparer l'URL Git avec le token"""
        # Nettoyer l'URL et le token
        git_url = str(git_url).strip().strip("'\"").rstrip('/')
        token = str(token).strip().strip("'\"")

        logger.info(f"prepare_git_url CLEANED - git_url: '{git_url}' (token len={len(token)})")

        # N'accepter que http:// et https:// : tout autre schéma (ext::, file://, ssh:// avec
        # options, etc.) peut être détourné par git pour exécuter des commandes arbitraires
        # (git-remote-ext) ou lire des fichiers locaux. On refuse plutôt que de "passer tel quel".
        if '://' not in git_url:
            raise ValueError(f"Unsupported git URL (missing scheme): {git_url!r}")

        scheme = git_url.split('://', 1)[0].lower()
        if scheme not in ('http', 'https'):
            raise ValueError(f"Unsupported git URL scheme {scheme!r}: only http/https are allowed")

        # Si l'URL contient déjà des identifiants (@), les remplacer
        if '@' in git_url:
            rest = git_url.split('://', 1)[1]
            host_and_path = rest.split('@', 1)[1] if '@' in rest else rest
            host_and_path = host_and_path.strip().rstrip('/')
            # Format pour Gitea: token comme username avec mot de passe vide
            result = f"{scheme}://{token}:@{host_and_path}"
            logger.info(f"prepare_git_url RESULT (had @): protocol://<token>:@host")
            return result

        host_and_path = git_url.split('://', 1)[1].strip().rstrip('/')
        # Format pour Gitea: token comme username avec mot de passe vide
        # Certains serveurs Git attendent: token:x-oauth-basic@ ou token:@
        result = f"{scheme}://{token}:@{host_and_path}"
        logger.info(f"prepare_git_url RESULT: protocol://<token>:@host")
        return result

    @staticmethod
    def clone_repository(dest_dir, git_url, branch):
        """Cloner le repository"""
        try:
            # Log l'URL utilisée (masquer le token)
            safe_url = git_url
            if '@' in git_url:
                parts = git_url.split('@')
                protocol_and_token = parts[0]
                protocol = protocol_and_token.split('://')[0]
                safe_url = f"{protocol}://****@{parts[1]}"
            logger.info(f"Cloning repository: {safe_url} branch: {branch}")

            # Vérification SSL désactivable uniquement via advanced.tlsVerify=false en config
            env = os.environ.copy()
            if not get_tls_verify():
                env['GIT_SSL_NO_VERIFY'] = 'true'

            cmd = ['git', 'clone', '--depth', '1', '--branch', branch, git_url, dest_dir]
            logger.info(f"Git command: git clone --depth 1 --branch {branch} {safe_url} {dest_dir}")
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, env=env)
            
            if result.returncode != 0:
                logger.error(f"Git clone stderr: {result.stderr}")
                raise Exception(f"Clone failed: {result.stderr}")
            
            logger.info("Repository cloned successfully")
        except subprocess.TimeoutExpired:
            raise Exception("Git clone operation timed out")
        except FileNotFoundError:
            raise Exception("Git is not installed on this system")
    
    @staticmethod
    def fetch_apps_directories(apps):
        """Récupérer les dossiers des applications"""
        logger.info(f"Fetching directories for {len(apps)} applications")

        apps_base_path = os.path.join(SPLUNK_HOME, 'etc', 'apps')

        # Allow-list: seuls des noms d'app réellement présents sous etc/apps sont acceptés.
        # Empêche un app_id malveillant (ex: "../../../../etc") de faire sortir la copie de ce
        # dossier (traversée de répertoire / exfiltration de fichiers arbitraires).
        try:
            existing_apps = set(os.listdir(apps_base_path))
        except OSError as e:
            logger.error(f"Cannot list apps directory {apps_base_path}: {e}")
            existing_apps = set()

        app_directories = []

        for app in apps:
            app_id = app.get('id') or app.get('app_id')

            if not app_id or not APP_ID_RE.match(app_id) or app_id not in existing_apps:
                logger.warning(f"Rejected invalid or unknown app id: {app_id!r}")
                continue

            app_path = os.path.join(apps_base_path, app_id)

            if os.path.isdir(app_path):
                app_directories.append({
                    'name': app_id,
                    'path': app_path,
                    'size': sum(os.path.getsize(os.path.join(dirpath, filename))
                               for dirpath, dirnames, filenames in os.walk(app_path)
                               for filename in filenames)
                })
                logger.info(f"Found app: {app_id}")
            else:
                logger.warning(f"App directory not found: {app_path}")

        return app_directories

    @staticmethod
    def update_app_selective(src_path, dest_path, selected_dashboards):
        """
        Mettre à jour une application en mode sélectif - seulement les dashboards spécifiés.
        Ne supprime PAS les fichiers existants dans le dépôt, met seulement à jour les fichiers concernés.
        
        Args:
            src_path: Chemin source de l'application (Splunk)
            dest_path: Chemin destination (dépôt Git)
            selected_dashboards: Liste des noms de dashboards à mettre à jour (sans .xml)
        """
        logger.info(f"Selective update: {src_path} -> {dest_path}")
        logger.info(f"Selected dashboards: {selected_dashboards}")
        
        # Créer le dossier destination s'il n'existe pas
        os.makedirs(dest_path, exist_ok=True)
        
        # Fichiers/dossiers essentiels à toujours synchroniser
        # Ces fichiers sont mis à jour mais les autres fichiers du dépôt sont conservés
        essential_items = [
            'default/app.conf',
            'local/app.conf', 
            'metadata/default.meta',
            'metadata/local.meta',
            'default/data/ui/nav/default.xml',
            'local/data/ui/nav/default.xml',
        ]
        
        # Mettre à jour les fichiers essentiels (sans supprimer les autres)
        for item in essential_items:
            src_item = os.path.join(src_path, item)
            dest_item = os.path.join(dest_path, item)
            
            if os.path.exists(src_item):
                dest_dir = os.path.dirname(dest_item)
                if dest_dir and not os.path.exists(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)
                
                if os.path.isfile(src_item):
                    shutil.copy2(src_item, dest_item)
                    logger.debug(f"Updated file: {item}")
        
        # Mettre à jour SEULEMENT les dashboards sélectionnés
        views_locations = [
            'default/data/ui/views',
            'local/data/ui/views'
        ]
        
        for views_dir in views_locations:
            src_views = os.path.join(src_path, views_dir)
            dest_views = os.path.join(dest_path, views_dir)
            
            if os.path.exists(src_views):
                os.makedirs(dest_views, exist_ok=True)
                
                for dashboard_name in selected_dashboards:
                    # Essayer avec et sans extension .xml
                    dashboard_file = dashboard_name if dashboard_name.endswith('.xml') else f"{dashboard_name}.xml"
                    src_dashboard = os.path.join(src_views, dashboard_file)
                    dest_dashboard = os.path.join(dest_views, dashboard_file)
                    
                    if os.path.exists(src_dashboard):
                        shutil.copy2(src_dashboard, dest_dashboard)
                        logger.info(f"Updated dashboard: {views_dir}/{dashboard_file}")
                    else:
                        # Essayer sans extension
                        src_dashboard_alt = os.path.join(src_views, dashboard_name)
                        if os.path.exists(src_dashboard_alt):
                            dest_dashboard_alt = os.path.join(dest_views, dashboard_name)
                            shutil.copy2(src_dashboard_alt, dest_dashboard_alt)
                            logger.info(f"Updated dashboard: {views_dir}/{dashboard_name}")
        
        logger.info(f"Selective update completed for {os.path.basename(src_path)}")


# ============================================
# FONCTIONS SH DEPLOYER
# ============================================

def call_deployer_agent(endpoint, method="GET", data=None, config=None):
    """
    Appeler l'agent SH Deployer
    
    Args:
        endpoint: Endpoint à appeler (ex: /health, /pull, /deploy)
        method: GET ou POST
        data: Données à envoyer (dict)
        config: Configuration (override SH_DEPLOYER_CONFIG)
    
    Returns:
        dict avec success, data ou error
    """
    if config is None:
        config = SH_DEPLOYER_CONFIG
    
    if not config.get("enabled", True):
        return {"success": False, "error": "SH Deployer is disabled"}
    
    host = config.get("host", "10.10.40.14")
    port = config.get("port", 9998)
    use_ssl = config.get("use_ssl", True)
    token = config.get("token", "")
    timeout = config.get("timeout", 30)
    
    protocol = "https" if use_ssl else "http"
    
    # Si c'est un nom de domaine (commence par une lettre et contient un point)
    # Ne pas ajouter le port (le proxy gère)
    is_domain = bool(re.match(r'^[a-zA-Z]', host)) and '.' in host and not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', host)
    
    if is_domain:
        url = f"{protocol}://{host}{endpoint}"
    else:
        url = f"{protocol}://{host}:{port}{endpoint}"
    
    logger.info(f"Calling SH Deployer: {method} {url}")
    
    try:
        # Vérification TLS désactivable uniquement via advanced.tlsVerify=false en config
        # (certificats auto-signés/internes) - active par défaut.
        ssl_context = ssl.create_default_context()
        if not get_tls_verify():
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        # Préparer les données
        if data:
            json_data = json.dumps(data).encode('utf-8')
        else:
            json_data = None
        
        # Créer la requête
        req = urllib.request.Request(url, data=json_data, method=method)
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-Auth-Token', token)
        
        # Exécuter la requête
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            logger.info(f"SH Deployer response: {response_data}")
            return {"success": True, "data": response_data}
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        logger.error(f"SH Deployer HTTP error {e.code}: {error_body}")
        return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
    
    except urllib.error.URLError as e:
        logger.error(f"SH Deployer connection error: {e.reason}")
        return {"success": False, "error": f"Connection error: {e.reason}"}
    
    except Exception as e:
        logger.error(f"SH Deployer error: {str(e)}")
        return {"success": False, "error": str(e)}


def check_deployer_health(config=None):
    """Vérifier si l'agent SH Deployer est accessible"""
    result = call_deployer_agent("/health", config=config)
    return result.get("success", False)


def trigger_deployer_pull(git_url, git_token, config=None):
    """
    Déclencher un pull sur le SH Deployer
    
    Args:
        git_url: URL du repository Git
        git_token: Token Git pour l'authentification
        config: Configuration du deployer
    """
    data = {
        "repo_url": git_url,
        "git_token": git_token,
        "apps_subdir": "apps"
    }
    
    return call_deployer_agent("/pull", method="POST", data=data, config=config)


def trigger_deployer_deploy(target_uri=None, auth_user=None, auth_pass=None, config=None):
    """
    Déclencher le déploiement du bundle sur le SH Cluster
    
    Args:
        target_uri: URI du captain du SH Cluster (optionnel)
        auth_user: Utilisateur Splunk
        auth_pass: Mot de passe Splunk
        config: Configuration du deployer
    """
    data = {}
    if target_uri:
        data["target_uri"] = target_uri
    if auth_user:
        data["auth_user"] = auth_user
    if auth_pass:
        data["auth_pass"] = auth_pass
    
    return call_deployer_agent("/deploy", method="POST", data=data, config=config)


def trigger_deployer_pull_and_deploy(git_url, git_token, target_uri=None, auth_user=None, auth_pass=None, config=None, apps_to_deploy=None):
    """
    Déclencher pull + deploy en une seule opération
    
    Note: Le deployer utilise toujours la branche par défaut (main/master).
    Le déploiement SH Cluster n'est autorisé que depuis ces branches.
    
    Args:
        git_url: URL du repo Git
        git_token: Token d'accès Git
        target_uri: URI cible pour le déploiement
        auth_user: Utilisateur Splunk pour l'authentification
        auth_pass: Mot de passe Splunk
        config: Configuration du deployer
        apps_to_deploy: Liste des IDs d'apps à déployer (si None, toutes les apps)
    """
    data = {
        "repo_url": git_url,
        "git_token": git_token,
        "apps_subdir": "apps"
    }
    # Note: pas de git_branch - le deployer utilise toujours la branche par défaut
    if target_uri:
        data["target_uri"] = target_uri
    if auth_user:
        data["auth_user"] = auth_user
    if auth_pass:
        data["auth_pass"] = auth_pass
    if apps_to_deploy:
        data["apps_to_deploy"] = apps_to_deploy  # Liste des apps à déployer
    
    return call_deployer_agent("/pull-and-deploy", method="POST", data=data, config=config)


def get_deployer_status(config=None):
    """Récupérer le statut du SH Deployer"""
    return call_deployer_agent("/status", config=config)


def start_server(port=9999, use_ssl=True):
    """Démarrer le serveur HTTP/HTTPS"""
    import ssl
    
    server = HTTPServer(('0.0.0.0', port), GitPusherRequestHandler)
    
    ssl_enabled = False
    
    if use_ssl:
        # Chemins possibles pour les certificats (ordre de priorité)
        cert_paths = [
            # Certificats dédiés pour GitDeploy for Splunk (recommandé)
            ('/opt/splunk/etc/apps/gitdeploy_app/local/certs/server.crt', 
             '/opt/splunk/etc/apps/gitdeploy_app/local/certs/server.key'),
            # Certificats splunkweb
            ('/opt/splunk/etc/auth/splunkweb/cert.pem', 
             '/opt/splunk/etc/auth/splunkweb/privkey.pem'),
            # Autre emplacement splunkweb
            ('/opt/splunk/etc/auth/splunkweb/splunkweb.pem', 
             '/opt/splunk/etc/auth/splunkweb/splunkweb.key'),
        ]
        
        for cert_file, key_file in cert_paths:
            logger.info(f"Trying SSL cert: {cert_file}")
            if os.path.exists(cert_file) and os.path.exists(key_file):
                try:
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    
                    # Charger le certificat et la clé
                    ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
                    
                    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
                    ssl_enabled = True
                    logger.info(f"SSL enabled using: {cert_file}")
                    break
                except Exception as e:
                    logger.warning(f"Could not load SSL cert {cert_file}: {e}")
                    continue
            else:
                logger.debug(f"Cert not found: {cert_file} or {key_file}")
        
        if not ssl_enabled:
            logger.error("=" * 60)
            logger.error("SSL CERTIFICATES NOT FOUND OR INVALID!")
            logger.error("HTTPS requests from browser will fail!")
            logger.error("")
            logger.error("To fix, run these commands:")
            logger.error("  mkdir -p /opt/splunk/etc/apps/gitdeploy_app/local/certs")
            logger.error("  openssl req -x509 -newkey rsa:4096 \\")
            logger.error("    -keyout /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.key \\")
            logger.error("    -out /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.crt \\")
            logger.error("    -days 365 -nodes -subj \"/CN=gitdeploy\"")
            logger.error("=" * 60)
    
    protocol = "HTTPS" if ssl_enabled else "HTTP"
    logger.info(f"GitDeploy for Splunk server listening on 0.0.0.0:{port} ({protocol})")
    
    # Afficher le statut de la licence au démarrage
    license_status = validate_license()
    if license_status.get("valid"):
        logger.info(f"License: {license_status.get('type_name')} - {license_status.get('days_remaining')} days remaining")
    else:
        logger.warning(f"License: {license_status.get('error', 'Invalid')}")
    
    server.serve_forever()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='GitDeploy for Splunk Server')
    parser.add_argument('--no-ssl', action='store_true', help='Disable SSL/HTTPS')
    parser.add_argument('--port', type=int, default=9999, help='Port number (default: 9999)')
    args = parser.parse_args()
    
    port = args.port
    use_ssl = not args.no_ssl
    
    logger.info(f"Starting GitDeploy for Splunk on port {port} (SSL: {use_ssl})")
    start_server(port, use_ssl)
