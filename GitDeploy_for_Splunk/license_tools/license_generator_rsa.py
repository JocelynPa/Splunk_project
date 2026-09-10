#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitDeploy for Splunk - License Generator (RSA)
Outil de génération de licences avec signature RSA

À GARDER SECRET - Ne jamais distribuer ce fichier aux clients !
La clé privée doit rester confidentielle.
"""

import os
import sys
import json
import base64
import hashlib
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# ============================================
# CONFIGURATION
# ============================================

KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys')
PRIVATE_KEY_FILE = os.path.join(KEYS_DIR, 'private_key.pem')
PUBLIC_KEY_FILE = os.path.join(KEYS_DIR, 'public_key.pem')
LICENSES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'licenses')

# Types de licences
LICENSE_TYPES = {
    "trial": {
        "name": "Trial",
        "duration_days": 14,
        "max_apps": 3,
        "max_pushes_per_day": 5,
        "features": ["basic_push"]
    },
    "starter": {
        "name": "Starter",
        "duration_days": 365,
        "max_apps": 10,
        "max_pushes_per_day": 50,
        "features": ["basic_push", "scheduled_push"]
    },
    "professional": {
        "name": "Professional",
        "duration_days": 365,
        "max_apps": -1,  # Illimité
        "max_pushes_per_day": -1,
        "features": ["basic_push", "scheduled_push", "multi_repo", "priority_support"]
    },
    "enterprise": {
        "name": "Enterprise",
        "duration_days": 365,
        "max_apps": -1,
        "max_pushes_per_day": -1,
        "features": ["basic_push", "scheduled_push", "multi_repo", "priority_support", 
                    "shcluster_deploy", "custom_branding", "api_access"]
    }
}

# ============================================
# GÉNÉRATION DES CLÉS RSA
# ============================================

def generate_rsa_keys(key_size=4096):
    """Générer une paire de clés RSA"""
    print(f"Génération d'une paire de clés RSA ({key_size} bits)...")
    
    # Créer le dossier keys
    os.makedirs(KEYS_DIR, exist_ok=True)
    
    # Générer la clé privée
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Sérialiser la clé privée
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Sérialiser la clé publique
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Sauvegarder les clés
    with open(PRIVATE_KEY_FILE, 'wb') as f:
        f.write(private_pem)
    os.chmod(PRIVATE_KEY_FILE, 0o600)
    
    with open(PUBLIC_KEY_FILE, 'wb') as f:
        f.write(public_pem)
    
    print(f"✅ Clé privée sauvegardée: {PRIVATE_KEY_FILE}")
    print(f"✅ Clé publique sauvegardée: {PUBLIC_KEY_FILE}")
    print()
    print("⚠️  IMPORTANT: Gardez la clé privée SECRÈTE!")
    print("📤 Distribuez la clé publique avec l'application client.")
    
    return private_key, public_key


def load_private_key():
    """Charger la clé privée"""
    if not os.path.exists(PRIVATE_KEY_FILE):
        print("❌ Clé privée non trouvée. Génération en cours...")
        generate_rsa_keys()
    
    with open(PRIVATE_KEY_FILE, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    return private_key


def load_public_key():
    """Charger la clé publique"""
    if not os.path.exists(PUBLIC_KEY_FILE):
        raise FileNotFoundError("Clé publique non trouvée. Générez d'abord les clés.")
    
    with open(PUBLIC_KEY_FILE, 'rb') as f:
        public_key = serialization.load_pem_public_key(
            f.read(),
            backend=default_backend()
        )
    return public_key


def get_public_key_string():
    """Récupérer la clé publique en format string pour l'intégrer dans le code client"""
    with open(PUBLIC_KEY_FILE, 'rb') as f:
        return f.read().decode('utf-8')


# ============================================
# GÉNÉRATION DE LICENCE
# ============================================

def generate_license_id():
    """Générer un ID de licence unique"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(12))


def create_license(customer_name, customer_email, hostname, license_type="professional", 
                   duration_days=None, custom_features=None):
    """
    Créer une licence signée avec RSA
    
    Args:
        customer_name: Nom du client
        customer_email: Email du client
        hostname: Hostname Splunk du client (binding)
        license_type: Type de licence (trial, starter, professional, enterprise)
        duration_days: Durée personnalisée (optionnel)
        custom_features: Features personnalisées (optionnel)
    
    Returns:
        dict avec la licence et le contenu du fichier .lic
    """
    
    if license_type not in LICENSE_TYPES:
        raise ValueError(f"Type de licence invalide: {license_type}")
    
    license_config = LICENSE_TYPES[license_type]
    
    # Calculer la date d'expiration
    if duration_days is None:
        duration_days = license_config["duration_days"]
    
    issue_date = datetime.now()
    expiry_date = issue_date + timedelta(days=duration_days)
    
    # Créer les données de licence
    license_data = {
        "license_id": generate_license_id(),
        "version": "2.0",
        "type": license_type,
        "type_name": license_config["name"],
        "customer": {
            "name": customer_name,
            "email": customer_email
        },
        "hostname": hostname.lower(),  # Normaliser en minuscules
        "issued": issue_date.strftime("%Y-%m-%d"),
        "expires": expiry_date.strftime("%Y-%m-%d"),
        "limits": {
            "max_apps": license_config["max_apps"],
            "max_pushes_per_day": license_config["max_pushes_per_day"]
        },
        "features": custom_features if custom_features else license_config["features"]
    }
    
    # Convertir en JSON (trié pour consistance)
    license_json = json.dumps(license_data, sort_keys=True, separators=(',', ':'))
    
    # Charger la clé privée et signer avec PKCS#1 v1.5
    private_key = load_private_key()
    
    signature = private_key.sign(
        license_json.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    # Encoder en base64
    license_b64 = base64.b64encode(license_json.encode('utf-8')).decode('utf-8')
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    # Créer le payload final
    payload = {
        "license": license_b64,
        "signature": signature_b64
    }
    
    payload_b64 = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
    
    # Créer le contenu du fichier .lic
    lic_content = f"""# =============================================
# GitDeploy for Splunk License File
# =============================================
# Customer: {customer_name}
# Email: {customer_email}
# Type: {license_config['name']}
# Hostname: {hostname}
# Issued: {issue_date.strftime("%Y-%m-%d")}
# Expires: {expiry_date.strftime("%Y-%m-%d")}
# License ID: {license_data['license_id']}
# =============================================
# DO NOT MODIFY THIS FILE
# Signature: RSA-PSS with SHA-256
# =============================================

{payload_b64}

# =============================================
# END OF LICENSE
# =============================================
"""
    
    return {
        "license_data": license_data,
        "lic_content": lic_content,
        "payload": payload_b64
    }


def save_license(license_result, filename=None):
    """Sauvegarder la licence dans un fichier"""
    os.makedirs(LICENSES_DIR, exist_ok=True)
    
    if filename is None:
        license_id = license_result["license_data"]["license_id"]
        hostname = license_result["license_data"]["hostname"]
        filename = f"license_{hostname}_{license_id}.lic"
    
    filepath = os.path.join(LICENSES_DIR, filename)
    
    with open(filepath, 'w') as f:
        f.write(license_result["lic_content"])
    
    print(f"✅ Licence sauvegardée: {filepath}")
    return filepath


# ============================================
# VÉRIFICATION DE LICENCE (pour tests)
# ============================================

def verify_license(lic_content):
    """Vérifier une licence (pour tests côté vendeur)"""
    try:
        # Extraire le payload
        lines = lic_content.strip().split('\n')
        payload_b64 = None
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                payload_b64 = line
                break
        
        if not payload_b64:
            return {"valid": False, "error": "Payload non trouvé"}
        
        # Décoder le payload
        payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
        license_b64 = payload.get("license")
        signature_b64 = payload.get("signature")
        
        if not license_b64 or not signature_b64:
            return {"valid": False, "error": "Format invalide"}
        
        # Décoder la licence et la signature
        license_json = base64.b64decode(license_b64).decode('utf-8')
        signature = base64.b64decode(signature_b64)
        
        # Charger la clé publique et vérifier
        public_key = load_public_key()
        
        try:
            public_key.verify(
                signature,
                license_json.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception as e:
            return {"valid": False, "error": f"Signature invalide: {e}"}
        
        # Parser les données de licence
        license_data = json.loads(license_json)
        
        # Vérifier l'expiration
        expiry_date = datetime.strptime(license_data["expires"], "%Y-%m-%d")
        if datetime.now() > expiry_date:
            return {
                "valid": False, 
                "error": "Licence expirée",
                "license_data": license_data
            }
        
        return {
            "valid": True,
            "license_data": license_data
        }
    
    except Exception as e:
        return {"valid": False, "error": str(e)}


# ============================================
# INTERFACE CLI
# ============================================

def interactive_mode():
    """Mode interactif pour générer une licence"""
    print("=" * 50)
    print("GitDeploy for Splunk - Générateur de Licence RSA")
    print("=" * 50)
    print()
    
    # Vérifier/Générer les clés
    if not os.path.exists(PRIVATE_KEY_FILE):
        print("🔑 Première utilisation - Génération des clés RSA...")
        generate_rsa_keys()
        print()
    
    # Collecter les informations
    print("📝 Informations client:")
    customer_name = input("   Nom du client: ").strip()
    customer_email = input("   Email: ").strip()
    hostname = input("   Hostname Splunk: ").strip()
    
    print()
    print("📦 Types de licence disponibles:")
    for key, config in LICENSE_TYPES.items():
        limits = f"Apps: {'∞' if config['max_apps'] == -1 else config['max_apps']}, "
        limits += f"Pushes/jour: {'∞' if config['max_pushes_per_day'] == -1 else config['max_pushes_per_day']}"
        print(f"   - {key}: {config['name']} ({config['duration_days']} jours) - {limits}")
    
    print()
    license_type = input("   Type de licence [professional]: ").strip().lower() or "professional"
    
    if license_type not in LICENSE_TYPES:
        print(f"❌ Type invalide: {license_type}")
        return
    
    # Durée personnalisée ?
    custom_duration = input("   Durée personnalisée en jours (Enter = défaut): ").strip()
    duration_days = int(custom_duration) if custom_duration else None
    
    print()
    print("⏳ Génération de la licence...")
    
    # Générer la licence
    result = create_license(
        customer_name=customer_name,
        customer_email=customer_email,
        hostname=hostname,
        license_type=license_type,
        duration_days=duration_days
    )
    
    # Sauvegarder
    filepath = save_license(result)
    
    # Afficher le résumé
    print()
    print("=" * 50)
    print("✅ LICENCE GÉNÉRÉE AVEC SUCCÈS")
    print("=" * 50)
    print(f"   ID: {result['license_data']['license_id']}")
    print(f"   Client: {customer_name}")
    print(f"   Hostname: {hostname}")
    print(f"   Type: {result['license_data']['type_name']}")
    print(f"   Expire: {result['license_data']['expires']}")
    print(f"   Fichier: {filepath}")
    print()
    
    # Vérifier la licence
    print("🔍 Vérification de la licence...")
    with open(filepath, 'r') as f:
        verification = verify_license(f.read())
    
    if verification["valid"]:
        print("   ✅ Signature valide")
    else:
        print(f"   ❌ Erreur: {verification['error']}")


def quick_generate(customer_name, customer_email, hostname, license_type="professional"):
    """Génération rapide en ligne de commande"""
    result = create_license(
        customer_name=customer_name,
        customer_email=customer_email,
        hostname=hostname,
        license_type=license_type
    )
    
    filepath = save_license(result)
    print(f"✅ Licence générée: {filepath}")
    return filepath


def export_public_key():
    """Exporter la clé publique pour intégration dans le code client"""
    if not os.path.exists(PUBLIC_KEY_FILE):
        print("❌ Clé publique non trouvée. Générez d'abord les clés avec: python3 license_generator_rsa.py genkeys")
        return
    
    public_key_content = get_public_key_string().strip()
    
    print("=" * 60)
    print("CLÉ PUBLIQUE RSA - À INTÉGRER DANS LE CODE CLIENT")
    print("=" * 60)
    print()
    print("📋 OPTION 1: Pour license_validation.js (JavaScript)")
    print("-" * 60)
    print()
    print("Remplacez la section PUBLIC_KEY_PEM dans license_validation.js:")
    print()
    print("const PUBLIC_KEY_PEM = `" + public_key_content + "`;")
    print()
    print()
    print("📋 OPTION 2: Pour Python (si besoin)")
    print("-" * 60)
    print()
    print("PUBLIC_KEY = '''")
    print(public_key_content)
    print("'''")
    print()
    print("=" * 60)
    print("⚠️  Après avoir mis à jour la clé, n'oubliez pas d'obfusquer:")
    print("    python3 obfuscate_js.py license_validation.js license_validation.obfuscated.js")
    print("=" * 60)


def show_help():
    """Afficher l'aide"""
    print("""
GitDeploy for Splunk - Générateur de Licence RSA

Usage:
    python license_generator_rsa.py                     Mode interactif
    python license_generator_rsa.py genkeys             Générer les clés RSA
    python license_generator_rsa.py export-key          Exporter la clé publique
    python license_generator_rsa.py quick <name> <email> <hostname> [type]
    python license_generator_rsa.py verify <fichier.lic>
    python license_generator_rsa.py help                Afficher cette aide

Types de licence: trial, starter, professional, enterprise

Exemples:
    python license_generator_rsa.py quick "Acme Corp" "admin@acme.com" "splunk-prod" professional
    python license_generator_rsa.py verify licenses/license_splunk-prod_ABC123.lic
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        interactive_mode()
    elif sys.argv[1] == "genkeys":
        generate_rsa_keys()
    elif sys.argv[1] == "export-key":
        export_public_key()
    elif sys.argv[1] == "quick" and len(sys.argv) >= 5:
        license_type = sys.argv[5] if len(sys.argv) > 5 else "professional"
        quick_generate(sys.argv[2], sys.argv[3], sys.argv[4], license_type)
    elif sys.argv[1] == "verify" and len(sys.argv) >= 3:
        with open(sys.argv[2], 'r') as f:
            result = verify_license(f.read())
        if result["valid"]:
            print("✅ Licence valide")
            print(json.dumps(result["license_data"], indent=2))
        else:
            print(f"❌ Licence invalide: {result['error']}")
    elif sys.argv[1] == "help":
        show_help()
    else:
        show_help()
