#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitDeploy for Splunk - Validateur de licence (côté serveur)

Vérifie hors-ligne la signature RSA d'un fichier .lic local (aucune communication
réseau avec un serveur de licence n'est nécessaire ni effectuée) et fait respecter les
limites de licence côté serveur, pour que ces contrôles ne dépendent plus uniquement du
JavaScript exécuté dans le navigateur (contournable via les devtools).

Le format du fichier .lic et le schéma de signature (RSASSA-PKCS1-v1.5 / SHA-256) sont
strictement identiques à ceux utilisés par license_generator_rsa.py (génération) et
license_validation.js (vérification côté client) - ne pas les faire diverger.
"""

import os
import re
import json
import base64
import socket
from datetime import datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

# ============================================
# CONFIGURATION
# ============================================

SPLUNK_HOME = os.environ.get('SPLUNK_HOME', '/opt/splunk')
APP_HOME = os.path.join(SPLUNK_HOME, 'etc', 'apps', 'gitdeploy_app')
LICENSE_FILE = os.path.join(APP_HOME, 'local', 'license.lic')
USAGE_FILE = os.path.join(APP_HOME, 'local', 'usage.json')

# ============================================
# CLÉ PUBLIQUE RSA
# ============================================
# Doit être identique à PUBLIC_KEY_PEM dans gitdeploy_app/appserver/static/license_validation.js
# (générée par license_generator_rsa.py export-key). Ne changer qu'en même temps que ce
# fichier et après régénération/redistribution des licences clients.

PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAnj2hOg61Q9k9iz4U5F7I
RdaJrpLTG+orz0/Kpbz2HSxbAVXkvL5GvYVfxROjy0UgxOZFycZAaGN2am+5CDHA
D1dTL9KCPhEaPqw4XTFnf6Ur5VG0+SftugTdTcyxRe614Z+i61/2ahk/vKG9D4kB
j4qV4se4lLk993lEaQrOXkXCbZ8royB5MPeOchPxZd7SDzoovEcyUmf2Fa2eYk6U
WmbrymCnJRsfxEVZofQQyp1ILS8KuSxaquXvMWm3cXV2Krs/3E5ax0vBPMrZRL+o
Vn7/dVnzbOlbifeosTYaad1DLd7NEgst3OFUv+dSH5hcCCc36IHMSvxcJ9l7s2kv
KbEFPeh582JNmRoMMNPRbd+/ZVDeJ/oB344+TtB6VeQ2GQyOyoggiLryZujg3WDE
shwLkFwiYGa/zEct0qs2/HBS1FOAqrLiPdQYJTx+RhrXhTni/p3H42L+2xJcbnki
fAgn8ND5k2yQw2gk4AlLqq2y01m0jsHdjaOfhKzzPLyzt1En/KAnCWJSzB+jur4z
fd70R4pLTYfawr2NTvTAhOtiOIjWj380oGmxeKCNJT1P4Dq8Yl+OxKLBy4cnUlgV
sbpKJug7Goth4g7bmCVMhC4bf7JB/iTrrS8DhMaWaZX/FeFloM3yYyo/gzmAY19z
sUdQuBpxCwIf/J7Q4dYsDkMCAwEAAQ==
-----END PUBLIC KEY-----"""

_public_key = None


def _get_public_key():
    global _public_key
    if _public_key is None:
        _public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
    return _public_key


# ============================================
# PARSING / VÉRIFICATION DE LICENCE
# ============================================

def parse_license_content(content):
    """
    Parser le contenu d'un fichier .lic (même format que parseLicenseFile() dans
    license_validation.js) : la première ligne non vide et non commentée est un payload
    JSON encodé en base64 contenant {"license": <base64 JSON>, "signature": <base64>}.
    """
    try:
        payload_b64 = None
        for line in content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                payload_b64 = line
                break

        if not payload_b64:
            return {"error": "Payload non trouvé dans le fichier"}

        payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
        license_b64 = payload.get('license')
        signature_b64 = payload.get('signature')

        if not license_b64 or not signature_b64:
            return {"error": "Format de licence invalide"}

        license_json = base64.b64decode(license_b64).decode('utf-8')
        license_data = json.loads(license_json)

        return {
            "success": True,
            "license_json": license_json,
            "license_data": license_data,
            "signature_b64": signature_b64
        }
    except Exception as e:
        return {"error": f"Erreur de lecture du fichier de licence: {e}"}


def verify_signature(license_json, signature_b64):
    """Vérifier la signature RSASSA-PKCS1-v1.5/SHA-256 d'une licence, hors ligne."""
    try:
        signature = base64.b64decode(signature_b64)
        _get_public_key().verify(
            signature,
            license_json.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except (InvalidSignature, ValueError):
        return False


def get_splunk_hostname():
    """
    Récupérer le hostname du serveur, pour vérifier le rattachement de licence.
    Contrairement à la version JavaScript (qui interroge l'API REST Splunk depuis le
    navigateur), ce code tourne côté serveur : on lit directement server.conf, avec un
    repli sur le hostname système.
    """
    for conf_dir in ('local', 'default'):
        server_conf = os.path.join(SPLUNK_HOME, 'etc', 'system', conf_dir, 'server.conf')
        try:
            with open(server_conf, 'r') as f:
                in_general = False
                for line in f:
                    line = line.strip()
                    if line.startswith('['):
                        in_general = (line == '[general]')
                        continue
                    if in_general and line.lower().startswith('servername'):
                        match = re.match(r'servername\s*=\s*(.+)', line, re.IGNORECASE)
                        if match and match.group(1).strip():
                            return match.group(1).strip().lower()
        except (OSError, IOError):
            continue

    return socket.gethostname().lower()


def _days_remaining(expiry_date_str):
    expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d")
    return (expiry - datetime.now()).days


def validate_license(license_content=None):
    """
    Valider une licence complète : signature RSA (hors ligne) + hostname + expiration.
    Si license_content n'est pas fourni, charge le fichier local/license.lic.

    Retourne un dict {"valid": bool, ...} avec la même forme que validateLicense() côté
    JavaScript, pour que gitdeploy.py puisse s'en servir de la même façon.
    """
    try:
        if license_content is None:
            if not os.path.exists(LICENSE_FILE):
                return {"valid": False, "error": "Aucune licence installée", "error_code": "NO_LICENSE"}
            with open(LICENSE_FILE, 'r') as f:
                license_content = f.read()

        parsed = parse_license_content(license_content)
        if 'error' in parsed:
            return {"valid": False, "error": parsed['error'], "error_code": "PARSE_ERROR"}

        license_json = parsed['license_json']
        license_data = parsed['license_data']
        signature_b64 = parsed['signature_b64']

        if not verify_signature(license_json, signature_b64):
            return {"valid": False, "error": "Signature de licence invalide", "error_code": "INVALID_SIGNATURE"}

        expected_hostname = (license_data.get('hostname') or '').lower()
        current_hostname = get_splunk_hostname()

        if expected_hostname and expected_hostname != current_hostname:
            # Correspondance partielle autorisée (hostname court vs FQDN), comme côté client.
            if expected_hostname not in current_hostname and current_hostname not in expected_hostname:
                return {
                    "valid": False,
                    "error": f"Licence non valide pour ce serveur. Attendu: {expected_hostname}, Actuel: {current_hostname}",
                    "error_code": "HOSTNAME_MISMATCH",
                    "expected_hostname": expected_hostname,
                    "current_hostname": current_hostname
                }

        expires = license_data.get('expires')
        days_remaining = None
        if expires:
            days_remaining = _days_remaining(expires)
            if days_remaining < 0:
                return {
                    "valid": False,
                    "error": f"Licence expirée le {expires}",
                    "error_code": "LICENSE_EXPIRED",
                    "expires": expires
                }

        return {
            "valid": True,
            "license_id": license_data.get('license_id'),
            "type": license_data.get('type'),
            "type_name": license_data.get('type_name'),
            "customer": license_data.get('customer'),
            "hostname": expected_hostname,
            "issued": license_data.get('issued'),
            "expires": expires,
            "days_remaining": days_remaining,
            "limits": license_data.get('limits', {}),
            "features": license_data.get('features', [])
        }
    except Exception as e:
        return {"valid": False, "error": str(e), "error_code": "VALIDATION_ERROR"}


def save_license_file(license_content):
    """
    Sauvegarder un fichier de licence sur le serveur, après avoir vérifié sa signature.
    Empêche de persister un fichier corrompu ou falsifié (le endpoint /license/upload
    faisait confiance au client avant cette vérification).
    """
    validation = validate_license(license_content)
    if not validation.get('valid'):
        return {"success": False, "error": validation.get('error', 'Licence invalide')}

    try:
        os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
        with open(LICENSE_FILE, 'w') as f:
            f.write(license_content)
        os.chmod(LICENSE_FILE, 0o600)
        return {"success": True, "license": validation}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================
# SUIVI D'UTILISATION (CÔTÉ SERVEUR)
# ============================================
# Contrairement au compteur JavaScript stocké dans le localStorage du navigateur
# (modifiable par l'utilisateur), ce compteur vit sur le serveur et fait foi pour
# check_limits().

def get_usage_stats():
    """Lire les statistiques d'utilisation stockées côté serveur."""
    try:
        if os.path.exists(USAGE_FILE):
            with open(USAGE_FILE, 'r') as f:
                return json.load(f)
    except (OSError, ValueError):
        pass

    return {"total_pushes": 0, "pushes_today": 0, "last_push_date": None}


def increment_usage():
    """Incrémenter le compteur d'utilisation côté serveur (appelé après un push réussi)."""
    stats = get_usage_stats()
    today = datetime.now().strftime('%Y-%m-%d')

    if stats.get('last_push_date') != today:
        stats['pushes_today'] = 0
        stats['last_push_date'] = today

    stats['total_pushes'] = stats.get('total_pushes', 0) + 1
    stats['pushes_today'] = stats.get('pushes_today', 0) + 1

    try:
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        with open(USAGE_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
        os.chmod(USAGE_FILE, 0o600)
    except OSError:
        pass

    return stats


def check_limits():
    """
    Vérifier que la licence autorise un nouveau push, en s'appuyant uniquement sur des
    données côté serveur (licence + compteur d'utilisation) - jamais sur ce que le client
    prétend dans la requête.
    """
    validation = validate_license()

    if not validation.get('valid'):
        return {
            "allowed": False,
            "error": validation.get('error'),
            "error_code": validation.get('error_code')
        }

    limits = validation.get('limits', {})
    max_pushes = limits.get('max_pushes_per_day', -1)

    if max_pushes and max_pushes > 0:
        stats = get_usage_stats()
        today = datetime.now().strftime('%Y-%m-%d')
        pushes_today = stats.get('pushes_today', 0) if stats.get('last_push_date') == today else 0

        if pushes_today >= max_pushes:
            return {
                "allowed": False,
                "error": f"Limite quotidienne atteinte ({max_pushes} pushes/jour)",
                "error_code": "DAILY_LIMIT_REACHED"
            }

        return {
            "allowed": True,
            "license_type": validation.get('type_name'),
            "remaining_today": max_pushes - pushes_today
        }

    return {
        "allowed": True,
        "license_type": validation.get('type_name'),
        "remaining_today": -1
    }
