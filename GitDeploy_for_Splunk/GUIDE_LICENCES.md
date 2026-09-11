# 🔐 Guide de Gestion des Licences - GitDeploy for Splunk

## Vue d'ensemble

Le système de licence utilise **RSA-4096** pour signer les licences. Le processus est :

```
┌─────────────────────────────────────────────────────────────────┐
│                    VENDEUR (Toi)                                 │
│                                                                   │
│  1. Générer les clés RSA (une seule fois)                       │
│     └── Crée: private_key.pem (SECRET) + public_key.pem         │
│                                                                   │
│  2. Intégrer la clé publique dans license_validation.js         │
│     └── Copier le contenu de public_key.pem dans le JS          │
│                                                                   │
│  3. Obfusquer le JS                                              │
│     └── python3 obfuscate_js.py license_validation.js            │
│                                                                   │
│  4. Générer une licence pour chaque client                       │
│     └── Crée un fichier .lic signé avec la clé privée           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT                                        │
│                                                                   │
│  • Reçoit l'application avec le JS obfusqué (clé publique)      │
│  • Reçoit son fichier .lic personnalisé                         │
│  • Upload la licence via l'interface                            │
│  • La validation se fait côté client avec la clé publique       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Étape 1 : Générer les clés RSA (une seule fois)

```bash
# Aller dans le dossier de l'application
cd /chemin/vers/gitdeploy_app/bin/

# Générer les clés
python3 license_generator_rsa.py genkeys
```

**Résultat :**
```
Génération d'une paire de clés RSA (4096 bits)...
✅ Clé privée sauvegardée: keys/private_key.pem
✅ Clé publique sauvegardée: keys/public_key.pem

⚠️  IMPORTANT: Gardez la clé privée SECRÈTE!
```

**Structure créée :**
```
bin/
├── license_generator_rsa.py
├── keys/
│   ├── private_key.pem   ← SECRET - Ne jamais distribuer !
│   └── public_key.pem    ← À intégrer dans le JS client
└── licenses/             ← Les licences générées
```

---

## Étape 2 : Exporter la clé publique

```bash
python3 license_generator_rsa.py export-key
```

**Résultat :**
```
==================================================
CLÉ PUBLIQUE À INTÉGRER DANS LE CODE CLIENT
==================================================

Copiez cette clé dans license_validator.py:

PUBLIC_KEY = '''
-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAnj2hOg61Q9k9iz4U5F7I
RdaJrpLTG+orz0/Kpbz2HSxbAVXkvL5GvYVfxROjy0UgxOZFycZAaGN2am+5CDHA
... (contenu de la clé)
-----END PUBLIC KEY-----
'''
```

---

## Étape 3 : Intégrer la clé dans license_validation.js

Ouvrir le fichier `appserver/static/license_validation.js` et remplacer la section :

```javascript
// ============================================
// CLÉ PUBLIQUE RSA
// ============================================
// Cette clé est générée par le vendeur avec license_generator_rsa.py
// Commande: python3 license_generator_rsa.py export-key

const PUBLIC_KEY_PEM = `-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAnj2hOg61Q9k9iz4U5F7I
RdaJrpLTG+orz0/Kpbz2HSxbAVXkvL5GvYVfxROjy0UgxOZFycZAaGN2am+5CDHA
... COLLER ICI LE CONTENU DE VOTRE CLÉ PUBLIQUE ...
-----END PUBLIC KEY-----`;
```

---

## Étape 3bis : Intégrer la clé dans license_validator.py (vérification serveur)

Depuis la v2.1, `gitdeploy.py` vérifie aussi la licence côté serveur (hors ligne, sans appel
réseau) via `gitdeploy_app/bin/license_validator.py`. **Cette clé doit être strictement
identique** à celle collée dans `license_validation.js` à l'étape 3 - sinon la validation
côté serveur et celle côté navigateur ne seront plus d'accord.

Ouvrir `gitdeploy_app/bin/license_validator.py` et remplacer le bloc `PUBLIC_KEY_PEM` (en
tête de fichier) par la même clé :

```python
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
... COLLER ICI LE MÊME CONTENU QUE license_validation.js ...
-----END PUBLIC KEY-----"""
```

Contrairement à `license_validation.js`, ce fichier Python n'est **pas** obfusqué (ce n'est
pas nécessaire côté serveur) et n'a pas besoin de repasser par `obfuscate_js.py`.

---

## Étape 4 : Obfusquer le JavaScript

```bash
cd /chemin/vers/gitdeploy_app/

# Obfusquer le fichier
python3 bin/obfuscate_js.py appserver/static/license_validation.js \
                            appserver/static/license_validation.obfuscated.js

# Remplacer l'original par la version obfusquée
mv appserver/static/license_validation.obfuscated.js \
   appserver/static/license_validation.js
```

---

## Étape 5 : Générer une licence pour un client

### Mode interactif
```bash
python3 license_generator_rsa.py
```

### Mode rapide (ligne de commande)
```bash
python3 license_generator_rsa.py quick "Nom Client" "email@client.com" "hostname-splunk" [type]
```

**Exemples :**
```bash
# Licence Professional pour Acme Corp
python3 license_generator_rsa.py quick "Acme Corp" "admin@acme.com" "splunk-prod.acme.com" professional

# Licence Trial pour test
python3 license_generator_rsa.py quick "Test Client" "test@test.com" "localhost" trial

# Licence Enterprise
python3 license_generator_rsa.py quick "Big Corp" "it@bigcorp.fr" "splunk.bigcorp.fr" enterprise
```

**Types de licence disponibles :**

| Type | Durée | Max Apps | Max Push/jour | Features |
|------|-------|----------|---------------|----------|
| `trial` | 14 jours | 3 | 5 | basic_push |
| `starter` | 365 jours | 10 | 50 | + scheduled_push |
| `professional` | 365 jours | ∞ | ∞ | + multi_repo, priority_support |
| `enterprise` | 365 jours | ∞ | ∞ | + shcluster_deploy, custom_branding |

---

## Étape 6 : Vérifier une licence

```bash
python3 license_generator_rsa.py verify licenses/license_splunk-prod_ABC123.lic
```

**Résultat si valide :**
```
✅ Licence valide
{
  "license_id": "ABC123XYZ789",
  "type": "professional",
  "type_name": "Professional",
  "customer": {
    "name": "Acme Corp",
    "email": "admin@acme.com"
  },
  "hostname": "splunk-prod.acme.com",
  "expires": "2027-03-06",
  ...
}
```

---

## Structure du fichier .lic

Le fichier `.lic` est un JSON signé :

```json
{
  "license": {
    "license_id": "ABC123XYZ789",
    "version": "2.0",
    "type": "professional",
    "type_name": "Professional",
    "customer": {
      "name": "Acme Corp",
      "email": "admin@acme.com"
    },
    "hostname": "splunk-prod.acme.com",
    "issued": "2026-03-06",
    "expires": "2027-03-06",
    "limits": {
      "max_apps": -1,
      "max_pushes_per_day": -1
    },
    "features": ["basic_push", "scheduled_push", "multi_repo", "priority_support"]
  },
  "signature": "BASE64_ENCODED_RSA_SIGNATURE..."
}
```

---

## Résumé des commandes

| Commande | Description |
|----------|-------------|
| `python3 license_generator_rsa.py` | Mode interactif |
| `python3 license_generator_rsa.py genkeys` | Générer les clés RSA |
| `python3 license_generator_rsa.py export-key` | Afficher la clé publique |
| `python3 license_generator_rsa.py quick <nom> <email> <host> [type]` | Générer rapidement |
| `python3 license_generator_rsa.py verify <fichier.lic>` | Vérifier une licence |
| `python3 license_generator_rsa.py help` | Afficher l'aide |

---

## Fichiers à NE JAMAIS distribuer au client

| Fichier | Raison |
|---------|--------|
| `license_generator_rsa.py` | Permet de générer des licences |
| `keys/private_key.pem` | Clé privée secrète |
| `obfuscate_js.py` | Outil d'obfuscation |
| `license_validation.js` (non obfusqué) | Code source lisible |

---

## Fichiers à livrer au client

| Fichier | Description |
|---------|-------------|
| `license_validation.js` | Version **obfusquée** |
| `license_HOSTNAME_ID.lic` | Fichier de licence personnalisé |
| Reste de l'application | Dashboards, Python, etc. |

---

## Dépannage

### "Clé privée non trouvée"
```bash
python3 license_generator_rsa.py genkeys
```

### "Licence invalide - hostname mismatch"
Le hostname dans la licence doit correspondre exactement au hostname Splunk du client. Vérifier avec :
```bash
hostname -f  # Sur le serveur Splunk du client
```

### "Licence expirée"
Générer une nouvelle licence avec une nouvelle date d'expiration.

### Régénérer les clés (ATTENTION !)
Si vous régénérez les clés, **toutes les licences existantes deviennent invalides**. Il faudra :
1. Régénérer les clés
2. Mettre à jour la clé publique dans `license_validation.js`
3. Mettre à jour la **même** clé publique dans `license_validator.py` (voir Étape 3bis) -
   sinon la validation côté serveur refusera des licences que le navigateur accepte, ou
   inversement
4. Ré-obfusquer le JS
5. Redistribuer l'application à tous les clients
6. Régénérer toutes les licences clients
