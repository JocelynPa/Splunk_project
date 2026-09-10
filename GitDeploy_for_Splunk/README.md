# 🚀 GitDeploy for Splunk

**Version 2.1** | Application Splunk pour déployer vos applications vers Git et le Search Head Cluster

---

## 📋 Table des matières

- [Présentation](#-présentation)
- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#-architecture)
- [Installation - Serveur Source](#-installation---serveur-source)
- [Installation - SH Deployer Agent](#-installation---sh-deployer-agent)
- [Configuration](#-configuration)
- [Configuration avec Proxy (Nginx)](#-configuration-avec-proxy-nginx)
- [Système de Licence](#-système-de-licence)
- [Utilisation](#-utilisation)
- [Sécurité](#-sécurité)
- [Dépannage](#-dépannage)
- [API Reference](#-api-reference)
- [Changelog](#-changelog)
- [Support](#-support)

---

## 🎯 Présentation

**GitDeploy for Splunk** est une application Splunk Enterprise qui permet de :
1. **Versionner** vos applications Splunk dans un repository Git
2. **Déployer automatiquement** vers un Search Head Cluster via le SH Deployer
3. **Sélectionner** quelles applications déployer sur le SH Cluster (indépendamment du push Git)

Le workflow complet en un clic :
```
Splunk Source → Push Git → Pull SH Deployer → Apply Bundle → Search Head Cluster
```

### Nouveau dans v2.1 : Sélection des apps pour le SH Cluster

```
┌─────────────────────────────────────────────────────────────┐
│  APPLICATIONS SÉLECTIONNÉES                                  │
│  ☑ App1   ☑ App2   ☑ App3   ☑ App4                         │
└─────────────────────────────────────────────────────────────┘
                           │
                    Push to Git (4 apps)
                           │
┌─────────────────────────────────────────────────────────────┐
│  DEPLOY TO SH CLUSTER                                        │
│  ☐ Deploy all selected apps                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ☑ App1   ☑ App2   ☐ App3   ☐ App4                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                    Deploy (2 apps only)
```

Idéal pour :
- 📦 Sauvegarder vos configurations Splunk dans Git
- 🔄 Versionner vos dashboards et applications
- 👥 Collaborer en équipe sur les développements Splunk
- 🚀 Mettre en place un workflow CI/CD pour Splunk
- 🎯 Déployer sélectivement vers votre Search Head Cluster

---

## ✨ Fonctionnalités

| Fonctionnalité | Description |
|----------------|-------------|
| **Push vers Git** | Déployez une ou plusieurs applications Splunk vers votre repository Git |
| **Déploiement SH Cluster** | Déploiement automatique vers le Search Head Cluster après le push Git |
| **Sélection apps SH Cluster** | Choisir un sous-ensemble d'apps pour le déploiement SH Cluster |
| **Page de configuration** | Interface dédiée pour configurer l'API, le SH Deployer, et la licence |
| **Support Proxy** | Configuration pour utiliser un reverse proxy (Nginx, Apache) |
| **Interface moderne** | Dashboard intuitif avec sélection visuelle des applications |
| **Multi-repository** | Support de GitHub, GitLab, Gitea, Bitbucket et tout serveur Git |
| **Support HTTPS** | Communication sécurisée avec certificats SSL/Let's Encrypt |
| **Système de licence RSA** | Validation cryptographique côté client (RSA-4096) |
| **Persistance licence** | Licence sauvegardée sur serveur (survit au vidage cache navigateur) |
| **Credentials sécurisés** | Chiffrement des mots de passe Splunk |
| **Logs détaillés** | Traçabilité complète des opérations |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NGINX PROXY MANAGER                           │
│  splunk.example.com ─────────────▶ Splunk Web (:8000)           │
│  splunk-api.example.com ─────────▶ GitDeploy for Splunk (:9999)           │
│  splunk-deployer.example.com ────▶ Deployer Agent (:9998)       │
└─────────────────────────────────────────────────────────────────┘
                                          │
┌─────────────────────────────────────────┼───────────────────────┐
│                    SERVEUR SOURCE       │                        │
│  ┌─────────────┐     ┌─────────────────▼───────────────────┐    │
│  │   Splunk    │────▶│  GitDeploy for Splunk Server (:9999)          │    │
│  │  Dashboard  │     │  • Push apps vers Git               │    │
│  │   (HTTPS)   │     │  • Gestion des licences             │    │
│  └─────────────┘     │  • Appelle le SH Deployer Agent     │    │
│                      └──────────────────┬──────────────────┘    │
└─────────────────────────────────────────┼───────────────────────┘
                                          │ HTTPS
                                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SH DEPLOYER                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Deployer Agent (:9998)                                  │    │
│  │  • Filtre les apps à déployer                           │    │
│  │  • Git pull dans /opt/splunk/etc/shcluster/apps/        │    │
│  │  • Exécute: splunk apply shcluster-bundle               │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SEARCH HEAD CLUSTER                            │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐               │
│  │    SH1    │    │    SH2    │    │    SH3    │               │
│  └───────────┘    └───────────┘    └───────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### Structure des fichiers

```
SERVEUR SOURCE - gitdeploy_app/
├── bin/
│   ├── gitdeploy.py              # Serveur HTTP/HTTPS principal (port 9999)
│   ├── license_generator_rsa.py   # Génération des licences (vendeur)
│   └── start_gitdeploy.sh        # Script de démarrage
├── appserver/static/
│   ├── gitdeploy.js              # Logique JavaScript principale
│   ├── gitdeploy_config.js       # JavaScript page de configuration
│   └── license_validation.js      # Validation RSA côté client
├── default/data/ui/views/
│   ├── gitdeploy_dashboard.xml   # Dashboard principal
│   └── gitdeploy_config.xml      # Page de configuration
├── local/
│   ├── config.json                # Configuration de l'application
│   ├── license.lic                # Fichier de licence (après activation)
│   └── certs/                     # Certificats SSL
│       ├── server.crt
│       └── server.key
└── README.md

SH DEPLOYER - deployer_agent/
├── bin/
│   ├── deployer_agent.py          # Agent de déploiement (port 9998)
│   └── start_deployer_agent.sh          # Script de démarrage
└── local/
    └── certs/                     # Certificats SSL
        ├── server.crt
        └── server.key
```

---

## 📥 Installation - Serveur Source

### Prérequis

- Splunk Enterprise 8.x ou supérieur
- Python 3.7+
- Git installé sur le serveur (`yum install git` ou `apt install git`)
- Accès réseau vers votre repository Git
- (Optionnel) Nginx Proxy Manager pour les certificats Let's Encrypt

### Étapes d'installation

#### 1. Extraire l'application

```bash
# Copier l'application dans Splunk
cp -r gitdeploy_app /opt/splunk/etc/apps/

# Définir les permissions
chown -R splunk:splunk /opt/splunk/etc/apps/gitdeploy_app
chmod +x /opt/splunk/etc/apps/gitdeploy_app/bin/*.sh
chmod +x /opt/splunk/etc/apps/gitdeploy_app/bin/*.py
```

#### 2. Configurer les certificats SSL

**Option A : Certificats Let's Encrypt (recommandé avec proxy)**

```bash
# Copier les certificats depuis Nginx Proxy Manager
mkdir -p /opt/splunk/etc/apps/gitdeploy_app/local/certs/
cp /path/to/fullchain.pem /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.crt
cp /path/to/privkey.pem /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.key
chmod 600 /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.key
chown -R splunk:splunk /opt/splunk/etc/apps/gitdeploy_app/local/certs/
```

**Option B : Certificat auto-signé**

```bash
mkdir -p /opt/splunk/etc/apps/gitdeploy_app/local/certs
openssl req -x509 -newkey rsa:4096 \
  -keyout /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.key \
  -out /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.crt \
  -days 365 -nodes -subj "/CN=gitdeploy"
chmod 600 /opt/splunk/etc/apps/gitdeploy_app/local/certs/server.key
chown -R splunk:splunk /opt/splunk/etc/apps/gitdeploy_app/local/certs/
```

#### 3. Démarrer le serveur GitDeploy for Splunk

```bash
cd /opt/splunk/etc/apps/gitdeploy_app/bin/
./start_gitdeploy.sh start
```

#### 4. Ouvrir le firewall (si nécessaire)

```bash
# FirewallD
sudo firewall-cmd --add-port=9999/tcp --permanent
sudo firewall-cmd --reload

# UFW
sudo ufw allow 9999/tcp
```

#### 5. Redémarrer Splunk

```bash
/opt/splunk/bin/splunk restart
```

#### 6. Vérifier l'installation

```bash
curl -k https://localhost:9999/health
# Réponse attendue: {"status": "ok", ...}
```

---

## 📥 Installation - SH Deployer Agent

### Sur le serveur SH Deployer

#### 1. Créer l'application

```bash
# Créer les dossiers
mkdir -p /opt/splunk/etc/apps/deployer_agent/bin
mkdir -p /opt/splunk/etc/apps/deployer_agent/local/certs

# Copier les fichiers
cp deployer_agent.py /opt/splunk/etc/apps/deployer_agent/bin/
cp start_deployer_agent.sh /opt/splunk/etc/apps/deployer_agent/bin/

# Rendre exécutable
chmod +x /opt/splunk/etc/apps/deployer_agent/bin/*.sh
chmod +x /opt/splunk/etc/apps/deployer_agent/bin/*.py
```

#### 2. Configurer le token d'authentification

```bash
nano /opt/splunk/etc/apps/deployer_agent/bin/deployer_agent.py
```

Modifier la ligne `AUTH_TOKEN` :
```python
AUTH_TOKEN = "votre_token_secret_personnalise"
```

#### 3. Configurer le Search Head Captain

Dans le même fichier, trouver `DEFAULT_TARGET` :
```python
DEFAULT_TARGET = "https://IP_DU_CAPTAIN:8089"
```

#### 4. Générer les certificats SSL

```bash
cd /opt/splunk/etc/apps/deployer_agent/bin/
./start_deployer_agent.sh gencerts
```

#### 5. Définir les permissions

```bash
chown -R splunk:splunk /opt/splunk/etc/apps/deployer_agent
```

#### 6. Démarrer l'agent

```bash
./start_deployer_agent.sh start
```

#### 7. Ouvrir le firewall

```bash
sudo firewall-cmd --add-port=9998/tcp --permanent
sudo firewall-cmd --reload
```

#### 8. Vérifier l'installation

```bash
curl -k https://localhost:9998/health
# Réponse attendue: {"status": "ok", ...}
```

---

## ⚙️ Configuration

### Page de configuration

Accédez à la page de configuration :
```
https://votre-splunk/en-US/app/gitdeploy_app/gitdeploy_config
```

### Paramètres disponibles

#### Configuration API

| Paramètre | Description | Exemple |
|-----------|-------------|---------|
| **URL de l'API** | URL du serveur GitDeploy for Splunk | `https://splunk-api.example.com` |
| **Port** | Port si accès direct (sans proxy) | `9999` |
| **Utiliser un proxy** | Coché si utilisation d'un reverse proxy | ✅ |

#### Configuration SH Deployer

| Paramètre | Description | Exemple |
|-----------|-------------|---------|
| **Activer SH Deployer** | Activer le déploiement vers SH Cluster | ✅ |
| **Adresse** | Hostname ou IP du SH Deployer | `splunk-deployer.example.com` |
| **Port** | Port (ignoré si domaine avec proxy) | `9998` |
| **Token** | Token d'authentification | `your_secret_token` |
| **Utiliser SSL** | Communication HTTPS | ✅ |

#### Paramètres avancés

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| **Niveau de log** | INFO, DEBUG, WARNING, ERROR | `INFO` |
| **Timeout requêtes** | Timeout en secondes | `30` |
| **Timeout Git** | Timeout opérations Git | `120` |

### Fichier de configuration

La configuration est sauvegardée dans :
```
/opt/splunk/etc/apps/gitdeploy_app/local/config.json
```

Exemple :
```json
{
  "api": {
    "url": "https://splunk-api.example.com",
    "port": 9999,
    "useProxy": true
  },
  "deployer": {
    "enabled": true,
    "host": "splunk-deployer.example.com",
    "port": 9998,
    "token": "your_secret_token",
    "useSSL": true
  },
  "license": {
    "checkInterval": 24
  },
  "advanced": {
    "logLevel": "INFO",
    "timeout": 30,
    "gitTimeout": 120
  }
}
```

---

## 🌐 Configuration avec Proxy (Nginx)

### Architecture recommandée

```
┌─────────────────────────────────────────────────────────────────┐
│                    NGINX PROXY MANAGER                           │
│                                                                   │
│  splunk.example.com ──────────────▶ 10.10.40.17:8000 (Splunk)   │
│  splunk-api.example.com ──────────▶ 10.10.40.17:9999 (API)      │
│  splunk-deployer.example.com ─────▶ 10.10.40.14:9998 (Deployer) │
│                                                                   │
│  Certificats: Let's Encrypt (wildcard *.example.com)            │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Nginx Proxy Manager

#### Proxy Host 1 - Splunk Web

| Champ | Valeur |
|-------|--------|
| Domain Names | `splunk.example.com` |
| Scheme | `https` |
| Forward Hostname/IP | `10.10.40.17` |
| Forward Port | `8000` |
| SSL Certificate | Let's Encrypt |
| Force SSL | ✅ |

#### Proxy Host 2 - GitDeploy for Splunk API

| Champ | Valeur |
|-------|--------|
| Domain Names | `splunk-api.example.com` |
| Scheme | `https` |
| Forward Hostname/IP | `10.10.40.17` |
| Forward Port | `9999` |
| SSL Certificate | Let's Encrypt |
| Force SSL | ✅ |

#### Proxy Host 3 - SH Deployer Agent

| Champ | Valeur |
|-------|--------|
| Domain Names | `splunk-deployer.example.com` |
| Scheme | `https` |
| Forward Hostname/IP | `10.10.40.14` |
| Forward Port | `9998` |
| SSL Certificate | Let's Encrypt |
| Force SSL | ✅ |

### Configuration dans GitDeploy for Splunk

Dans la page de configuration :

1. **URL de l'API** : `https://splunk-api.example.com`
2. **Utiliser un proxy** : ✅ Coché
3. **Adresse SH Deployer** : `splunk-deployer.example.com`
4. **Utiliser SSL** : ✅ Coché

**Important** : Ne pas inclure le port dans l'URL quand vous utilisez un proxy !

---

## 🔐 Système de Licence

### Architecture

Le système de licence utilise une validation **RSA-4096** côté client :

```
┌─────────────────┐     ┌─────────────────────────────────────┐
│    VENDEUR      │     │              CLIENT                  │
│                 │     │                                      │
│  Clé privée     │     │  Clé publique (dans JS)             │
│  (secrète)      │     │                                      │
│       │         │     │       │                              │
│       ▼         │     │       ▼                              │
│  Génère .lic ───┼────▶│  Valide signature RSA               │
│                 │     │       │                              │
│                 │     │       ▼                              │
│                 │     │  ✅ Licence valide                   │
│                 │     │       │                              │
│                 │     │       ├──▶ localStorage (cache)     │
│                 │     │       └──▶ Serveur (persistance)    │
└─────────────────┘     └─────────────────────────────────────┘
```

### Types de licence

| Type | Durée | Apps | Pushes/jour | Features |
|------|-------|------|-------------|----------|
| **Trial** | 14 jours | 3 | 5 | basic_push |
| **Starter** | 1 an | 10 | 50 | + scheduled_push |
| **Professional** | 1 an | ∞ | ∞ | + multi_repo, priority_support |
| **Enterprise** | 1 an | ∞ | ∞ | + shcluster_deploy, custom_branding |

### Générer une licence (Vendeur)

```bash
cd /opt/splunk/etc/apps/gitdeploy_app/bin/

# Générer les clés (une seule fois)
python3 license_generator_rsa.py genkeys

# Exporter la clé publique (à intégrer dans license_validation.js)
python3 license_generator_rsa.py export-key

# Générer une licence
python3 license_generator_rsa.py quick "Client Name" "email@client.com" "hostname.client.com" professional
```

### Installer une licence (Client)

1. Ouvrir le dashboard GitDeploy for Splunk
2. Cliquer sur le badge de licence (coin supérieur droit)
3. Cliquer sur "Upload License"
4. Sélectionner le fichier `.lic`
5. La licence est validée et sauvegardée automatiquement

### Persistance de la licence

La licence est sauvegardée à deux endroits :
- **localStorage** : Cache rapide dans le navigateur
- **Fichier serveur** : `/opt/splunk/etc/apps/gitdeploy_app/local/license.lic`

Après un vidage du cache navigateur, la licence est automatiquement rechargée depuis le serveur.

---

## 🖥️ Utilisation

### Dashboard principal

Accès : `https://votre-splunk/en-US/app/gitdeploy_app/gitdeploy_dashboard`

### Workflow standard

1. **Sélectionner les applications** dans la colonne gauche
2. **Configurer Git** : URL, branche, token, message de commit
3. **(Optionnel) Activer le déploiement SH Cluster**
4. **(Optionnel) Sélectionner les apps pour le SH Cluster**
5. **Cliquer sur "Deploy to Git"**

### Sélection des apps pour le SH Cluster

Quand "Deploy to Search Head Cluster" est activé :

1. **Par défaut** : Toutes les apps sélectionnées sont déployées
2. **Sélection personnalisée** : Décocher "Deploy all selected apps" pour choisir un sous-ensemble

Exemple :
- Apps sélectionnées pour Git : App1, App2, App3, App4
- Apps pour SH Cluster : App1, App2 seulement

Résultat :
- Git reçoit les 4 apps
- Le SH Cluster reçoit seulement App1 et App2

### Messages de commit

Le message de commit inclut automatiquement :
- Votre message personnalisé
- L'utilisateur Splunk
- L'ID de licence
- Le timestamp

---

## 🔒 Sécurité

### Headers CORS autorisés

Le serveur GitDeploy for Splunk autorise les headers suivants :
- `Content-Type`
- `Authorization`
- `X-Requested-With`
- `X-Splunk-Form-Key`
- `X-Auth-Token`

### Bonnes pratiques

1. ✅ Utiliser HTTPS pour tous les composants
2. ✅ Utiliser des certificats Let's Encrypt via un proxy
3. ✅ Changer le token par défaut du Deployer Agent
4. ✅ Utiliser des tokens Git avec permissions minimales (repo write)
5. ✅ Restreindre l'accès réseau aux ports 9998/9999
6. ✅ Configurer les proxy hosts dans Nginx Proxy Manager

### Validation des licences

- **RSA-4096** avec PKCS1v15 pour la signature
- **SHA-256** pour le hash du contenu
- Validation du hostname pour éviter la copie de licence
- Vérification de la date d'expiration

---

## 🔧 Dépannage

### Erreur CORS avec x-splunk-form-key

**Symptôme** : `l'en-tête « x-splunk-form-key » n'est pas autorisé`

**Solution** : Vérifier que le serveur autorise ce header. Dans `gitdeploy.py` :
```python
self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Origin, X-Splunk-Form-Key, X-Auth-Token')
```

### Port ajouté automatiquement à l'URL

**Symptôme** : L'URL inclut `:9999` ou `:9998` alors que vous utilisez un proxy

**Solution** : 
1. Aller dans la page de configuration
2. Cocher "Utiliser un proxy"
3. Entrer l'URL sans port : `https://splunk-api.example.com`

### Les apps SH Cluster sont toutes déployées malgré la sélection

**Symptôme** : Les apps décochées sont quand même déployées sur le SH Cluster

**Solution** : Mettre à jour le `deployer_agent.py` avec la version qui supporte le filtrage des apps.

### Licence perdue après vidage du cache

**Symptôme** : La licence disparaît après Ctrl+Shift+Delete

**Solution** : C'est normal. La licence est automatiquement rechargée depuis le serveur. Si ce n'est pas le cas, vérifier :
```bash
ls -la /opt/splunk/etc/apps/gitdeploy_app/local/license.lic
```

### Les boutons ne fonctionnent pas

**Solution** :
```bash
rm -rf /opt/splunk/var/run/splunk/appserver/*
/opt/splunk/bin/splunk restart
```
Puis **Ctrl+Shift+R** dans le navigateur.

### Erreur 401 Unauthorized (Deployer)

**Solution** : Vérifier que le token correspond :
```bash
# Sur le Deployer
grep "AUTH_TOKEN" /opt/splunk/etc/apps/deployer_agent/bin/deployer_agent.py

# Configurer le même token dans l'interface GitDeploy for Splunk
```

### Vérifier les logs

```bash
# GitDeploy for Splunk
tail -50 /opt/splunk/var/log/splunk/gitdeploy.log

# Deployer Agent
tail -50 /opt/splunk/var/log/splunk/deployer_agent.log
```

---

## 📡 API Reference

### GitDeploy for Splunk Server (Port 9999)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/config` | Configuration actuelle |
| `GET` | `/license` | Statut de la licence |
| `GET` | `/license/file` | Charger licence depuis fichier |
| `GET` | `/license/hostname` | Hostname Splunk |
| `GET` | `/deployer/health` | Santé du SH Deployer |
| `GET` | `/deployer/status` | Statut du SH Deployer |
| `POST` | `/config` | Sauvegarder configuration |
| `POST` | `/license/save` | Sauvegarder licence sur serveur |
| `POST` | `/license/delete` | Supprimer licence |
| `POST` | `/push` | Pousser les applications |

### Deployer Agent (Port 9998)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/health` | Health check (pas d'auth) |
| `GET` | `/status` | Statut du déploiement |
| `GET` | `/apps` | Liste des apps |
| `GET` | `/history` | Historique des déploiements |
| `POST` | `/pull` | Git pull |
| `POST` | `/deploy` | Apply shcluster-bundle |
| `POST` | `/pull-and-deploy` | Pull + Deploy (avec filtrage apps) |

### Paramètres /push

| Paramètre | Type | Description |
|-----------|------|-------------|
| `git_url` | string | URL du repository Git |
| `git_branch` | string | Branche (défaut: main) |
| `git_token` | string | Token d'accès Git |
| `commit_message` | string | Message de commit |
| `apps` | JSON | Liste des apps pour Git |
| `shcluster_apps` | JSON | Liste des apps pour SH Cluster |
| `deploy_to_shcluster` | boolean | Activer déploiement SH |
| `deployer_host` | string | Adresse du deployer |
| `deployer_token` | string | Token du deployer |

### Paramètres /pull-and-deploy

| Paramètre | Type | Description |
|-----------|------|-------------|
| `repo_url` | string | URL du repository Git |
| `git_token` | string | Token d'accès Git |
| `apps_subdir` | string | Sous-dossier des apps (défaut: apps) |
| `apps_to_deploy` | array | Liste des apps à déployer (filtrage) |
| `target_uri` | string | URI du captain (optionnel) |
| `auth_user` | string | Utilisateur Splunk |
| `auth_pass` | string | Mot de passe Splunk |

---

## 📝 Changelog

### Version 2.1.0 (Février 2026)

#### Nouvelles fonctionnalités
- 🎯 **Sélection des apps pour SH Cluster** : Choisir un sous-ensemble d'apps pour le déploiement
- ⚙️ **Page de configuration** : Interface dédiée pour tous les paramètres
- 🌐 **Support proxy complet** : Configuration URL sans port pour reverse proxy
- 🔐 **Licence RSA** : Validation cryptographique côté client (RSA-4096)
- 💾 **Persistance licence** : Sauvegarde serveur + localStorage

#### Améliorations
- 🔧 Headers CORS étendus (X-Splunk-Form-Key, X-Auth-Token)
- 📱 Détection automatique domaine vs IP pour les ports
- 🔄 Configuration dynamique depuis fichier JSON
- 📊 Logs améliorés avec filtrage des apps

#### Corrections
- 🐛 Fix sélection apps SH Cluster qui se réinitialisait
- 🐛 Fix URL avec port quand proxy configuré
- 🐛 Fix CORS pour les requêtes Splunk

### Version 2.0.0 (Février 2026)
- 🚀 Déploiement automatique vers Search Head Cluster
- 🔧 Agent Deployer pour le SH Deployer
- ✨ Nouveau système de licence par fichier `.lic`
- 🔐 Credentials Splunk chiffrés
- 🔒 Support HTTPS avec certificats SSL
- 🎨 Interface utilisateur modernisée

### Version 1.0.0
- 🚀 Version initiale
- Push d'applications vers Git

---

## 📞 Support

### Fichiers de log

```bash
# GitDeploy for Splunk (serveur source)
/opt/splunk/var/log/splunk/gitdeploy.log

# Deployer Agent (SH Deployer)
/opt/splunk/var/log/splunk/deployer_agent.log
```

### Signaler un bug

Incluez dans votre rapport :
1. Version de GitDeploy for Splunk
2. Version de Splunk
3. Configuration (proxy, HTTPS)
4. Architecture (standalone, SH Cluster)
5. Contenu des logs
6. Erreurs console navigateur (F12)
7. Étapes pour reproduire

### Contact

- 📧 Email : support@jp-engineering.fr
- 🌐 Site web : https://jp-engineering.fr

---

## 📄 Licence

GitDeploy for Splunk est un logiciel propriétaire. Une licence valide est requise pour son utilisation.

© 2026 JP Engineering - Tous droits réservés

---

<p align="center">
  Made with ❤️ for Splunk administrators
</p>
