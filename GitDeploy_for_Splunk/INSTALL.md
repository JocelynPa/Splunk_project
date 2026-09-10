# GitDeploy for Splunk v2.1 - Guide d'Installation

## Table des matières

1. [Prérequis](#prérequis)
2. [Installation du Serveur Source](#installation-du-serveur-source)
3. [Installation du SH Deployer Agent](#installation-du-sh-deployer-agent)
4. [Configuration des Licences](#configuration-des-licences)
5. [Mise à Jour Manuelle](#mise-à-jour-manuelle)
6. [Commandes Utiles](#commandes-utiles)
7. [Dépannage](#dépannage)

---

## Prérequis

| Composant | Version minimum | Notes |
|-----------|-----------------|-------|
| Splunk Enterprise | 8.0+ | Avec accès admin |
| Git | 2.0+ | Installé sur le serveur source |
| Python | 3.6+ | Avec pip (pour license_manager_web) |
| Accès | root ou splunk | Pour les scripts d'installation |

### Ports réseau

| Service | Port | Protocole |
|---------|------|-----------|
| GitDeploy Server | 9999 | HTTPS |
| Deployer Agent | 9998 | HTTPS |

---

## Installation du Serveur Source

### Étape 1 : Extraire le package

```bash
# Copier le ZIP sur le serveur Splunk source
scp GitDeploy_for_Splunk_v2.1.zip user@splunk-server:/tmp/

# Sur le serveur Splunk
cd /tmp
unzip GitDeploy_for_Splunk_v2.1.zip
cd gitdeploy_distribution
```

### Étape 2 : Exécuter le script d'installation

```bash
chmod +x install_gitdeploy.sh
sudo ./install_gitdeploy.sh
```

Le script va :
- ✅ Créer l'application dans `/opt/splunk/etc/apps/gitdeploy_app`
- ✅ Générer les certificats SSL auto-signés
- ✅ Configurer les permissions (utilisateur splunk)
- ✅ Ouvrir le port 9999 dans le firewall (si firewalld actif)
- ✅ Démarrer le service GitDeploy

### Étape 3 : Redémarrer Splunk et vider le cache

```bash
# Redémarrer Splunk
/opt/splunk/bin/splunk restart

# Vider le cache des assets (important!)
rm -rf /opt/splunk/var/run/splunk/appserver/static/*

# Dans le navigateur : Ctrl+Shift+R pour forcer le rechargement
```

### Étape 4 : Vérifier l'installation

```bash
# Vérifier que le service est actif
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh status

# Tester l'API
curl -k https://localhost:9999/health
# Réponse attendue : {"status":"ok","version":"2.1.0",...}
```

---

## Installation du SH Deployer Agent

> ⚠️ Cette étape est **optionnelle** et nécessaire uniquement si vous utilisez un Search Head Cluster.

### Étape 1 : Copier sur le serveur Deployer

```bash
# Copier le package sur le SH Deployer
scp GitDeploy_for_Splunk_v2.1.zip user@sh-deployer:/tmp/

# Sur le SH Deployer
cd /tmp
unzip GitDeploy_for_Splunk_v2.1.zip
cd gitdeploy_distribution
```

### Étape 2 : Exécuter le script d'installation

```bash
chmod +x install_deployer_agent.sh
sudo ./install_deployer_agent.sh
```

Le script va :
- ✅ Créer l'agent dans `/opt/splunk/etc/apps/deployer_agent`
- ✅ Générer un **TOKEN D'AUTHENTIFICATION** (⚠️ NOTEZ-LE!)
- ✅ Configurer les credentials Splunk (utilisateur/mot de passe)
- ✅ Démarrer le service sur le port 9998

### Étape 3 : Configurer le token dans GitDeploy

1. Accédez à Splunk > GitDeploy for Splunk > **Configuration**
2. Dans la section "SH Deployer", entrez :
   - Host : IP ou hostname du SH Deployer
   - Token : le token généré lors de l'installation
3. Cliquez sur "Test Connection" puis "Save"

---

## Configuration des Licences

### Option 1 : Interface Web (recommandé)

```bash
# Sur le poste admin
cd gitdeploy_distribution/license_tools

# Installer les dépendances
pip install cryptography

# Lancer l'interface web
python license_manager_web.py
# L'interface s'ouvre automatiquement sur http://localhost:5000
```

### Option 2 : Ligne de commande

```bash
cd gitdeploy_distribution/license_tools
python license_generator_rsa.py --generate \
    --customer "Entreprise XYZ" \
    --email "admin@entreprise.com" \
    --hostname "splunk.entreprise.com" \
    --type enterprise
```

### Installer la licence sur Splunk

1. Copier le fichier `.lic` sur le serveur Splunk
2. Placer dans : `/opt/splunk/etc/apps/gitdeploy_app/local/license.lic`
3. Redémarrer le service : `/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh restart`

> ⚠️ **Important** : Les deux générateurs (CLI et Web) doivent utiliser les **mêmes clés RSA** situées dans le dossier `keys/`.

---

## Mise à Jour Manuelle

Si vous devez mettre à jour des fichiers individuellement sans réinstaller :

```bash
# Arrêter le service
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh stop

# Mettre à jour les fichiers
cp gitdeploy.py /opt/splunk/etc/apps/gitdeploy_app/bin/
cp gitdeploy.js /opt/splunk/etc/apps/gitdeploy_app/appserver/static/
cp gitdeploy_dashboard.xml /opt/splunk/etc/apps/gitdeploy_app/default/data/ui/views/

# Redémarrer le service
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh start

# Vider le cache Splunk
rm -rf /opt/splunk/var/run/splunk/appserver/static/*

# Rafraîchir le navigateur : Ctrl+Shift+R
```

---

## Structure du Package

```
gitdeploy_distribution/
├── gitdeploy_app/              # Application Splunk principale
│   ├── bin/
│   │   ├── gitdeploy.py        # Serveur API Python (port 9999)
│   │   └── start_gitdeploy.sh  # Script de démarrage
│   ├── appserver/static/
│   │   ├── gitdeploy.js        # JavaScript principal
│   │   ├── gitdeploy_config.js # Page de configuration
│   │   └── license_validation.js
│   ├── default/
│   │   ├── app.conf
│   │   └── data/ui/views/
│   │       ├── gitdeploy_dashboard.xml
│   │       └── gitdeploy_config.xml
│   └── local/                  # Fichiers locaux (licences, certs)
│
├── deployer_agent/             # Agent pour SH Cluster
│   └── bin/
│       ├── deployer_agent.py
│       ├── configure_deployer_credentials.py
│       └── start_deployer_agent.sh
│
├── license_tools/              # Outils de gestion des licences
│   ├── license_generator_rsa.py    # Générateur CLI
│   ├── license_manager_web.py      # Interface web
│   └── obfuscate_js.py
│
├── install_gitdeploy.sh        # Script installation serveur source
├── install_deployer_agent.sh   # Script installation deployer
├── INSTALL.md                  # Ce fichier
├── README.md                   # Présentation du projet
└── GitDeploy_Guide_Utilisateur.docx
```

---

## Commandes Utiles

### Serveur Source (GitDeploy)

```bash
# Gestion du service
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh start
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh stop
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh restart
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh status

# Logs
tail -f /opt/splunk/var/log/splunk/gitdeploy.log

# Test API
curl -k https://localhost:9999/health
```

### SH Deployer Agent

```bash
# Gestion du service
/opt/splunk/etc/apps/deployer_agent/bin/start_deployer_agent.sh start
/opt/splunk/etc/apps/deployer_agent/bin/start_deployer_agent.sh stop
/opt/splunk/etc/apps/deployer_agent/bin/start_deployer_agent.sh restart
/opt/splunk/etc/apps/deployer_agent/bin/start_deployer_agent.sh status

# Logs
tail -f /opt/splunk/var/log/splunk/deployer_agent.log

# Reconfigurer les credentials Splunk
python /opt/splunk/etc/apps/deployer_agent/bin/configure_deployer_credentials.py
```

---

## Dépannage

### Le dashboard ne se charge pas / affiche "Loading..."

```bash
# Vider le cache
rm -rf /opt/splunk/var/run/splunk/appserver/static/*

# Forcer le rechargement dans le navigateur
Ctrl+Shift+R
```

### Erreur "Connection error" lors du push

```bash
# Vérifier que le service tourne
/opt/splunk/etc/apps/gitdeploy_app/bin/start_gitdeploy.sh status

# Vérifier les logs
tail -50 /opt/splunk/var/log/splunk/gitdeploy.log

# Tester la connectivité
curl -k https://localhost:9999/health
```

### Erreur de licence "InvalidCharacterError"

Cela signifie que le fichier de licence est mal formaté. Regénérez-la avec :
- Le **même générateur** (CLI ou Web) utilisé pour créer les clés
- Les **mêmes clés RSA** dans le dossier `keys/`

### Le déploiement SH Cluster ne fonctionne pas

1. Vérifiez que vous êtes sur la branche **main** ou **master**
2. Vérifiez que le token est correct dans Configuration
3. Testez la connexion au deployer :
```bash
curl -k -H "X-Auth-Token: VOTRE_TOKEN" https://deployer:9998/health
```

---

## Support

📧 Pour toute question, consultez le **Guide Utilisateur** (GitDeploy_Guide_Utilisateur.docx) ou contactez le support.
