# 🚀 Git Pusher - Procédure de Déploiement Complète

## Vue d'ensemble

Ce document décrit toutes les étapes pour déployer Git Pusher chez un client, depuis la préparation du package jusqu'à la validation finale.

```
┌─────────────────────────────────────────────────────────────────┐
│                    WORKFLOW GLOBAL                               │
│                                                                   │
│  VENDEUR                          CLIENT                         │
│  ────────                         ──────                         │
│  1. Préparer le package      ───▶                                │
│  2. Générer la licence       ───▶ 3. Installer l'application    │
│                                   4. Configurer                  │
│                                   5. Activer la licence          │
│                                   6. Tester                      │
└─────────────────────────────────────────────────────────────────┘
```

---

# PARTIE 1 : PRÉPARATION (Vendeur - Une seule fois)

## 1.1 Structure initiale requise

```
pusher_app_prem/
├── bin/
│   ├── git_pusher.py
│   ├── start_git_pusher.sh
│   ├── license_generator_rsa.py    ← NE PAS LIVRER
│   ├── obfuscate_js.py             ← NE PAS LIVRER
│   └── keys/                        ← NE PAS LIVRER
│       ├── private_key.pem
│       └── public_key.pem
├── appserver/static/
│   ├── git_pusher.js
│   ├── git_pusher_config.js
│   └── license_validation.js       ← Version source (à obfusquer)
├── default/
│   ├── app.conf
│   └── data/ui/views/
│       ├── git_pusher_dashboard.xml
│       └── git_pusher_config.xml
├── static/
│   ├── appIcon.png
│   └── appIcon_2x.png
└── README.md
```

## 1.2 Générer les clés RSA (une seule fois)

```bash
cd /chemin/vers/pusher_app_prem/bin/

# Installer les dépendances Python
pip3 install cryptography

# Générer les clés RSA 4096 bits
python3 license_generator_rsa.py genkeys
```

**Résultat attendu :**
```
Génération d'une paire de clés RSA (4096 bits)...
✅ Clé privée sauvegardée: keys/private_key.pem
✅ Clé publique sauvegardée: keys/public_key.pem

⚠️  IMPORTANT: Gardez la clé privée SECRÈTE!
```

## 1.3 Intégrer la clé publique dans le JavaScript

```bash
# Afficher la clé publique formatée
python3 license_generator_rsa.py export-key
```

**Copier la sortie et remplacer dans `appserver/static/license_validation.js` :**

```javascript
// Ligne ~76 - Remplacer toute la section PUBLIC_KEY_PEM
const PUBLIC_KEY_PEM = `-----BEGIN PUBLIC KEY-----
VOTRE_CLE_PUBLIQUE_ICI
-----END PUBLIC KEY-----`;
```

## 1.4 Obfusquer le JavaScript

```bash
cd /chemin/vers/pusher_app_prem/

# Obfusquer
python3 bin/obfuscate_js.py appserver/static/license_validation.js \
                            appserver/static/license_validation.obfuscated.js

# Vérifier la syntaxe
node --check appserver/static/license_validation.obfuscated.js

# Remplacer l'original
mv appserver/static/license_validation.obfuscated.js \
   appserver/static/license_validation.js

echo "✅ JavaScript obfusqué"
```

## 1.5 Créer le package de distribution

```bash
cd /chemin/vers/

# Créer un dossier temporaire pour le package
mkdir -p package_tmp/pusher_app_prem

# Copier les fichiers à distribuer (SANS les fichiers secrets)
cp -r pusher_app_prem/appserver package_tmp/pusher_app_prem/
cp -r pusher_app_prem/bin package_tmp/pusher_app_prem/
cp -r pusher_app_prem/default package_tmp/pusher_app_prem/
cp -r pusher_app_prem/static package_tmp/pusher_app_prem/
cp pusher_app_prem/README.md package_tmp/pusher_app_prem/

# Supprimer les fichiers secrets du package
rm -f package_tmp/pusher_app_prem/bin/license_generator_rsa.py
rm -f package_tmp/pusher_app_prem/bin/obfuscate_js.py
rm -rf package_tmp/pusher_app_prem/bin/keys/
rm -rf package_tmp/pusher_app_prem/bin/licenses/

# Créer l'archive
cd package_tmp
tar -czvf ../pusher_app_prem_v2.1.tgz pusher_app_prem/

# Nettoyer
cd ..
rm -rf package_tmp

echo "✅ Package créé: pusher_app_prem_v2.1.tgz"
```

---

# PARTIE 2 : GÉNÉRATION DE LICENCE (Vendeur - Pour chaque client)

## 2.1 Informations requises du client

Avant de générer la licence, obtenir du client :

| Information | Exemple | Comment l'obtenir |
|-------------|---------|-------------------|
| Nom de l'entreprise | Acme Corporation | Demander au client |
| Email contact | admin@acme.com | Demander au client |
| Hostname Splunk | splunk.acme.com | `hostname -f` sur le serveur Splunk |
| Type de licence | professional | Selon le contrat |

## 2.2 Générer la licence

```bash
cd /chemin/vers/pusher_app_prem/bin/

# Générer la licence
python3 license_generator_rsa.py quick "Acme Corporation" "admin@acme.com" "splunk.acme.com" professional
```

**Résultat :**
```
✅ Licence générée: licenses/license_splunk.acme.com_ABC123XYZ.lic
```

## 2.3 Vérifier la licence

```bash
python3 license_generator_rsa.py verify licenses/license_splunk.acme.com_ABC123XYZ.lic
```

## 2.4 Envoyer au client

Envoyer au client :
1. `pusher_app_prem_v2.1.tgz` (le package de l'application)
2. `license_splunk.acme.com_ABC123XYZ.lic` (la licence personnalisée)

---

# PARTIE 3 : INSTALLATION (Client - Serveur Splunk Source)

## 3.1 Prérequis

- Splunk Enterprise 8.x ou supérieur
- Python 3.7+
- Git installé (`yum install git` ou `apt install git`)
- Accès root ou utilisateur splunk

## 3.2 Extraire l'application

```bash
# Se connecter en tant que root ou splunk
sudo su - splunk

# Aller dans le dossier apps
cd /opt/splunk/etc/apps/

# Extraire l'archive
tar -xzvf /chemin/vers/pusher_app_prem_v2.1.tgz

# Vérifier
ls -la pusher_app_prem/
```

## 3.3 Configurer les permissions

```bash
# Définir le propriétaire
chown -R splunk:splunk /opt/splunk/etc/apps/pusher_app_prem

# Rendre les scripts exécutables
chmod +x /opt/splunk/etc/apps/pusher_app_prem/bin/*.sh
chmod +x /opt/splunk/etc/apps/pusher_app_prem/bin/*.py
```

## 3.4 Générer les certificats SSL

**Option A : Certificat auto-signé (simple)**

```bash
mkdir -p /opt/splunk/etc/apps/pusher_app_prem/local/certs

openssl req -x509 -newkey rsa:4096 \
  -keyout /opt/splunk/etc/apps/pusher_app_prem/local/certs/server.key \
  -out /opt/splunk/etc/apps/pusher_app_prem/local/certs/server.crt \
  -days 365 -nodes -subj "/CN=gitdeploy"

chmod 600 /opt/splunk/etc/apps/pusher_app_prem/local/certs/server.key
chown -R splunk:splunk /opt/splunk/etc/apps/pusher_app_prem/local/certs/
```

**Option B : Certificats Let's Encrypt (avec proxy)**

```bash
# Copier depuis Nginx Proxy Manager ou autre
mkdir -p /opt/splunk/etc/apps/pusher_app_prem/local/certs/
cp /chemin/vers/fullchain.pem /opt/splunk/etc/apps/pusher_app_prem/local/certs/server.crt
cp /chemin/vers/privkey.pem /opt/splunk/etc/apps/pusher_app_prem/local/certs/server.key
chmod 600 /opt/splunk/etc/apps/pusher_app_prem/local/certs/server.key
chown -R splunk:splunk /opt/splunk/etc/apps/pusher_app_prem/local/certs/
```

## 3.5 Démarrer le serveur Git Pusher

```bash
cd /opt/splunk/etc/apps/pusher_app_prem/bin/

# Démarrer
./start_git_pusher.sh start

# Vérifier le statut
./start_git_pusher.sh status

# Voir les logs
tail -f /opt/splunk/var/log/splunk/git_pusher.log
```

## 3.6 Ouvrir le firewall

```bash
# FirewallD (CentOS/RHEL)
sudo firewall-cmd --add-port=9999/tcp --permanent
sudo firewall-cmd --reload

# UFW (Ubuntu/Debian)
sudo ufw allow 9999/tcp
```

## 3.7 Redémarrer Splunk

```bash
/opt/splunk/bin/splunk restart
```

## 3.8 Vérifier l'installation

```bash
# Tester l'API
curl -k https://localhost:9999/health

# Réponse attendue:
# {"status": "ok", "version": "2.1.0", ...}
```

---

# PARTIE 4 : INSTALLATION SH DEPLOYER (Client - Optionnel)

*Uniquement si le client utilise un Search Head Cluster*

## 4.1 Sur le serveur SH Deployer

```bash
# Créer l'application
mkdir -p /opt/splunk/etc/apps/deployer_agent/bin
mkdir -p /opt/splunk/etc/apps/deployer_agent/local/certs

# Copier les fichiers (fournis séparément)
cp deployer_agent.py /opt/splunk/etc/apps/deployer_agent/bin/
cp start_deployer.sh /opt/splunk/etc/apps/deployer_agent/bin/

# Permissions
chmod +x /opt/splunk/etc/apps/deployer_agent/bin/*.sh
chmod +x /opt/splunk/etc/apps/deployer_agent/bin/*.py
chown -R splunk:splunk /opt/splunk/etc/apps/deployer_agent
```

## 4.2 Configurer le token

```bash
nano /opt/splunk/etc/apps/deployer_agent/bin/deployer_agent.py
```

Modifier :
```python
AUTH_TOKEN = "votre_token_secret_unique"
```

## 4.3 Configurer le Captain

Dans le même fichier, modifier :
```python
DEFAULT_TARGET = "https://IP_DU_CAPTAIN:8089"
```

## 4.4 Générer les certificats

```bash
cd /opt/splunk/etc/apps/deployer_agent/bin/
./start_deployer.sh gencerts
```

## 4.5 Démarrer l'agent

```bash
./start_deployer.sh start

# Ouvrir le firewall
sudo firewall-cmd --add-port=9998/tcp --permanent
sudo firewall-cmd --reload
```

## 4.6 Vérifier

```bash
curl -k https://localhost:9998/health
```

---

# PARTIE 5 : CONFIGURATION (Client)

## 5.1 Accéder à la page de configuration

Ouvrir dans le navigateur :
```
https://VOTRE_SPLUNK/en-US/app/pusher_app_prem/git_pusher_config
```

## 5.2 Configurer l'API

| Champ | Valeur | Exemple |
|-------|--------|---------|
| URL de l'API | URL du serveur Git Pusher | `https://splunk-api.acme.com` |
| Port | Port si accès direct | `9999` |
| Utiliser un proxy | Cocher si reverse proxy | ✅ |

**Règle simple :**
- Si accès via **IP** → Ne pas cocher proxy, port = 9999
- Si accès via **domaine** (proxy) → Cocher proxy, pas de port

## 5.3 Configurer le SH Deployer (si applicable)

| Champ | Valeur |
|-------|--------|
| Activer SH Deployer | ✅ |
| Adresse | `splunk-deployer.acme.com` ou `10.10.40.14` |
| Port | `9998` |
| Token | Le même que dans deployer_agent.py |
| Utiliser SSL | ✅ |

## 5.4 Sauvegarder

Cliquer sur **"Save Configuration"**

## 5.5 Tester les connexions

- Cliquer sur **"Test Connection"** pour l'API
- Cliquer sur **"Test Connection"** pour le SH Deployer

---

# PARTIE 6 : ACTIVATION DE LA LICENCE (Client)

## 6.1 Accéder au dashboard principal

```
https://VOTRE_SPLUNK/en-US/app/pusher_app_prem/git_pusher_dashboard
```

## 6.2 Ouvrir le gestionnaire de licence

Cliquer sur le badge de licence en haut à droite (affiche "No License" ou "Trial")

## 6.3 Uploader la licence

1. Cliquer sur **"Upload License"**
2. Sélectionner le fichier `.lic` fourni
3. Attendre la validation

## 6.4 Vérifier l'activation

Le badge doit afficher :
- Type de licence (Professional, Enterprise, etc.)
- Date d'expiration
- Couleur verte = OK

---

# PARTIE 7 : TEST FINAL (Client)

## 7.1 Test de push Git

1. Sélectionner une application dans la liste
2. Configurer :
   - **Repository URL** : `https://github.com/user/repo.git`
   - **Branch** : `main`
   - **Token** : Token d'accès Git
   - **Commit Message** : "Test deployment"
3. Cliquer sur **"Deploy to Git"**
4. Vérifier le message de succès

## 7.2 Test de déploiement SH Cluster (si applicable)

1. Cocher **"Enable automatic deployment"**
2. (Optionnel) Sélectionner les apps à déployer
3. Entrer les credentials Splunk si nécessaire
4. Cliquer sur **"Deploy to Git"**
5. Vérifier les logs du deployer_agent

## 7.3 Vérifications finales

```bash
# Logs Git Pusher
tail -50 /opt/splunk/var/log/splunk/git_pusher.log

# Logs Deployer Agent (si applicable)
tail -50 /opt/splunk/var/log/splunk/deployer_agent.log

# Vérifier le repo Git
git clone https://github.com/user/repo.git /tmp/test-repo
ls -la /tmp/test-repo/apps/
```

---

# PARTIE 8 : CHECKLIST DE DÉPLOIEMENT

## Vendeur

- [ ] Clés RSA générées
- [ ] Clé publique intégrée dans license_validation.js
- [ ] JavaScript obfusqué
- [ ] Package créé (sans fichiers secrets)
- [ ] Licence client générée
- [ ] Licence vérifiée
- [ ] Package et licence envoyés au client

## Client - Serveur Source

- [ ] Application extraite dans /opt/splunk/etc/apps/
- [ ] Permissions configurées (splunk:splunk)
- [ ] Certificats SSL installés
- [ ] Serveur Git Pusher démarré
- [ ] Firewall ouvert (9999)
- [ ] Splunk redémarré
- [ ] API accessible (curl /health)

## Client - SH Deployer (optionnel)

- [ ] deployer_agent installé
- [ ] Token configuré
- [ ] Captain configuré
- [ ] Certificats installés
- [ ] Agent démarré
- [ ] Firewall ouvert (9998)
- [ ] API accessible (curl /health)

## Client - Configuration

- [ ] Page de configuration accessible
- [ ] URL API configurée
- [ ] SH Deployer configuré (si applicable)
- [ ] Tests de connexion OK
- [ ] Configuration sauvegardée

## Client - Licence

- [ ] Dashboard accessible
- [ ] Licence uploadée
- [ ] Licence validée (badge vert)
- [ ] Type et expiration corrects

## Client - Tests

- [ ] Push Git fonctionnel
- [ ] Déploiement SH Cluster fonctionnel (si applicable)
- [ ] Logs sans erreurs

---

# ANNEXES

## A. Commandes utiles

```bash
# Statut Git Pusher
/opt/splunk/etc/apps/pusher_app_prem/bin/start_git_pusher.sh status

# Redémarrer Git Pusher
/opt/splunk/etc/apps/pusher_app_prem/bin/start_git_pusher.sh restart

# Logs en temps réel
tail -f /opt/splunk/var/log/splunk/git_pusher.log

# Vider le cache Splunk (après modification JS/CSS)
rm -rf /opt/splunk/var/run/splunk/appserver/*
/opt/splunk/bin/splunk restart

# Tester l'API
curl -k https://localhost:9999/health
curl -k https://localhost:9999/license
```

## B. Ports utilisés

| Port | Service | Protocole |
|------|---------|-----------|
| 9999 | Git Pusher API | HTTPS |
| 9998 | Deployer Agent | HTTPS |
| 8000 | Splunk Web | HTTPS |
| 8089 | Splunk API | HTTPS |

## C. Fichiers de configuration

| Fichier | Description |
|---------|-------------|
| `/opt/splunk/etc/apps/pusher_app_prem/local/config.json` | Configuration de l'app |
| `/opt/splunk/etc/apps/pusher_app_prem/local/license.lic` | Licence (copie serveur) |
| `/opt/splunk/etc/apps/pusher_app_prem/local/certs/` | Certificats SSL |

## D. Dépannage rapide

| Problème | Solution |
|----------|----------|
| "License system not loaded" | Vider cache + Ctrl+Shift+R |
| Erreur CORS | Vérifier URL API dans config |
| 401 Unauthorized (Deployer) | Vérifier token |
| Certificat invalide | Accepter le certificat dans le navigateur |
| Port non accessible | Vérifier firewall |
