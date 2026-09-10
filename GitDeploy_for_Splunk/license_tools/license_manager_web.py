#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitDeploy for Splunk - License Manager (Web Interface)
Interface graphique pour la génération et gestion des licences

À GARDER SECRET - Ne jamais distribuer ce fichier aux clients !
La clé privée doit rester confidentielle.

Usage:
    python license_manager_web.py

Puis ouvrir http://localhost:8089 dans le navigateur

SÉCURITÉ: cet outil ne fait aucune authentification et permet de générer des licences
illimitées. Il écoute par défaut uniquement sur 127.0.0.1 (localhost) - ne JAMAIS le lancer
avec --host 0.0.0.0 (ou tout autre host non-local) sur une machine exposée au réseau.
"""

import os
import sys
import json
import base64
import hashlib
import random
import string
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading
import webbrowser

# Vérifier si cryptography est installé
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("❌ Module 'cryptography' non installé.")
    print("   Installez-le avec: pip install cryptography")
    sys.exit(1)

# ============================================
# CONFIGURATION
# ============================================

DEFAULT_PORT = 8089
DEFAULT_HOST = '127.0.0.1'  # Loopback uniquement par défaut : cet outil n'a aucune authentification
KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys')
PRIVATE_KEY_FILE = os.path.join(KEYS_DIR, 'private_key.pem')
PUBLIC_KEY_FILE = os.path.join(KEYS_DIR, 'public_key.pem')
LICENSES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'licenses')
LICENSES_DB_FILE = os.path.join(LICENSES_DIR, 'licenses_db.json')

# Types de licences
LICENSE_TYPES = {
    "trial": {
        "name": "Trial",
        "duration_days": 14,
        "max_apps": 3,
        "max_pushes_per_day": 5,
        "features": ["basic_push"],
        "color": "#ff9800",
        "icon": "⏱️"
    },
    "starter": {
        "name": "Starter",
        "duration_days": 365,
        "max_apps": 10,
        "max_pushes_per_day": 50,
        "features": ["basic_push", "scheduled_push"],
        "color": "#2196f3",
        "icon": "🚀"
    },
    "professional": {
        "name": "Professional",
        "duration_days": 365,
        "max_apps": -1,
        "max_pushes_per_day": -1,
        "features": ["basic_push", "scheduled_push", "multi_repo", "priority_support"],
        "color": "#9c27b0",
        "icon": "💼"
    },
    "enterprise": {
        "name": "Enterprise",
        "duration_days": 365,
        "max_apps": -1,
        "max_pushes_per_day": -1,
        "features": ["basic_push", "scheduled_push", "multi_repo", "priority_support", 
                    "shcluster_deploy", "custom_branding", "api_access"],
        "color": "#4caf50",
        "icon": "🏢"
    }
}

# ============================================
# GESTION DES CLÉS RSA
# ============================================

def generate_rsa_keys(key_size=4096):
    """Générer une paire de clés RSA"""
    os.makedirs(KEYS_DIR, exist_ok=True)
    
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    with open(PRIVATE_KEY_FILE, 'wb') as f:
        f.write(private_pem)
    os.chmod(PRIVATE_KEY_FILE, 0o600)
    
    with open(PUBLIC_KEY_FILE, 'wb') as f:
        f.write(public_pem)
    
    return private_key, public_key


def load_private_key():
    """Charger la clé privée"""
    if not os.path.exists(PRIVATE_KEY_FILE):
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
        raise FileNotFoundError("Clé publique non trouvée.")
    
    with open(PUBLIC_KEY_FILE, 'rb') as f:
        public_key = serialization.load_pem_public_key(
            f.read(),
            backend=default_backend()
        )
    return public_key


def get_public_key_string():
    """Récupérer la clé publique en format string"""
    if not os.path.exists(PUBLIC_KEY_FILE):
        return None
    with open(PUBLIC_KEY_FILE, 'rb') as f:
        return f.read().decode('utf-8')


# ============================================
# GÉNÉRATION DE LICENCE
# ============================================

def generate_license_id():
    """Générer un ID de licence unique"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(12))


def create_license(customer_name, customer_email, hostname, license_type="professional", 
                   duration_days=None, notes=""):
    """Créer une licence signée avec RSA"""
    
    if license_type not in LICENSE_TYPES:
        raise ValueError(f"Type de licence invalide: {license_type}")
    
    license_config = LICENSE_TYPES[license_type]
    
    # Calculer la date d'expiration
    days = duration_days if duration_days else license_config["duration_days"]
    issue_date = datetime.now()
    expiry_date = issue_date + timedelta(days=days)
    
    # Générer l'ID de licence
    license_id = generate_license_id()
    
    # Créer les données de licence (même structure que le CLI)
    license_data = {
        "license_id": license_id,
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
        "features": license_config["features"]
    }
    
    # Convertir en JSON (trié pour consistance, sans espaces)
    license_json = json.dumps(license_data, sort_keys=True, separators=(',', ':'))
    
    # Charger la clé privée et signer avec PKCS#1 v1.5 (comme le CLI)
    private_key = load_private_key()
    signature = private_key.sign(
        license_json.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    # Encoder en base64
    license_b64 = base64.b64encode(license_json.encode('utf-8')).decode('utf-8')
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    # Créer le payload final (même format que le CLI)
    payload = {
        "license": license_b64,
        "signature": signature_b64
    }
    payload_b64 = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
    
    # Créer le fichier .lic avec en-tête commenté
    lic_file_content = f'''# =============================================
# GitDeploy for Splunk License File
# =============================================
# Customer: {customer_name}
# Email: {customer_email}
# Type: {license_config["name"]}
# Hostname: {hostname}
# Issued: {issue_date.strftime("%Y-%m-%d")}
# Expires: {expiry_date.strftime("%Y-%m-%d")}
# License ID: {license_id}
# =============================================
# DO NOT MODIFY THIS FILE
# Signature: RSA-PKCS1v15 with SHA-256
# =============================================

{payload_b64}

# =============================================
# END OF LICENSE
# =============================================
'''
    
    # Sauvegarder le fichier
    os.makedirs(LICENSES_DIR, exist_ok=True)
    safe_hostname = hostname.replace('.', '_').replace(':', '_')
    filename = f"license_{safe_hostname}_{license_id}.lic"
    filepath = os.path.join(LICENSES_DIR, filename)
    
    with open(filepath, 'w') as f:
        f.write(lic_file_content)
    
    # Sauvegarder dans la base de données (garder les infos lisibles)
    db_license_data = {
        "license_id": license_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "hostname": hostname.lower(),
        "license_type": license_type,
        "license_name": license_config["name"],
        "issued_date": issue_date.strftime("%Y-%m-%d"),
        "expiration_date": expiry_date.strftime("%Y-%m-%d"),
        "max_apps": license_config["max_apps"],
        "max_pushes_per_day": license_config["max_pushes_per_day"],
        "features": license_config["features"]
    }
    save_license_to_db(db_license_data, filename, notes)
    
    return {
        "license_data": db_license_data,
        "filename": filename,
        "filepath": filepath,
        "content": lic_file_content
    }


def save_license_to_db(license_data, filename, notes=""):
    """Sauvegarder les infos de licence dans la base de données JSON"""
    db = load_licenses_db()
    
    entry = {
        **license_data,
        "filename": filename,
        "notes": notes,
        "created_at": datetime.now().isoformat(),
        "status": "active"
    }
    
    db["licenses"].append(entry)
    
    with open(LICENSES_DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)


def load_licenses_db():
    """Charger la base de données des licences"""
    if os.path.exists(LICENSES_DB_FILE):
        with open(LICENSES_DB_FILE, 'r') as f:
            return json.load(f)
    return {"licenses": []}


def revoke_license(license_id):
    """Révoquer une licence"""
    db = load_licenses_db()
    
    for lic in db["licenses"]:
        if lic["license_id"] == license_id:
            lic["status"] = "revoked"
            lic["revoked_at"] = datetime.now().isoformat()
            break
    
    with open(LICENSES_DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)


# ============================================
# INTERFACE WEB
# ============================================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitDeploy License Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        header p {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .tab-btn {
            padding: 12px 24px;
            border: none;
            background: rgba(255,255,255,0.2);
            color: white;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s;
        }
        
        .tab-btn:hover, .tab-btn.active {
            background: white;
            color: #667eea;
        }
        
        .card {
            background: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        
        .card h2 {
            color: #333;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }
        
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        .license-types {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .license-type {
            padding: 20px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
        }
        
        .license-type:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .license-type.selected {
            border-color: #667eea;
            background: #f3f0ff;
        }
        
        .license-type .icon {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .license-type .name {
            font-weight: 600;
            margin-bottom: 5px;
        }
        
        .license-type .details {
            font-size: 0.85em;
            color: #888;
        }
        
        .btn {
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: #f5f5f5;
            color: #333;
        }
        
        .btn-danger {
            background: #f44336;
            color: white;
        }
        
        .licenses-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .licenses-table th, .licenses-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .licenses-table th {
            background: #f5f5f5;
            font-weight: 600;
            color: #555;
        }
        
        .licenses-table tr:hover {
            background: #fafafa;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }
        
        .status-active {
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        .status-expired {
            background: #fff3e0;
            color: #e65100;
        }
        
        .status-revoked {
            background: #ffebee;
            color: #c62828;
        }
        
        .result-card {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .result-card h3 {
            color: #4caf50;
            margin-bottom: 15px;
        }
        
        .result-info {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .result-info div {
            padding: 10px;
            background: white;
            border-radius: 8px;
        }
        
        .result-info label {
            font-size: 0.85em;
            color: #888;
            display: block;
        }
        
        .result-info span {
            font-weight: 600;
            color: #333;
        }
        
        .license-content {
            background: #263238;
            color: #aed581;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.9em;
            max-height: 200px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
        
        .copy-btn {
            margin-top: 10px;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }
        
        .copy-btn:hover {
            background: #5a6fd6;
        }
        
        .hidden {
            display: none;
        }
        
        .alert {
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .alert-warning {
            background: #fff3e0;
            color: #e65100;
            border: 1px solid #ffcc02;
        }
        
        .alert-success {
            background: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #a5d6a7;
        }
        
        .keys-status {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 15px;
            background: #e8f5e9;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .keys-status.warning {
            background: #fff3e0;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .stat-card .number {
            font-size: 2.5em;
            font-weight: 700;
            color: #667eea;
        }
        
        .stat-card .label {
            color: #888;
            margin-top: 5px;
        }
        
        @media (max-width: 768px) {
            .form-row, .license-types, .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .result-info {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔐 GitDeploy License Manager</h1>
            <p>Générez et gérez les licences pour GitDeploy for Splunk</p>
        </header>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('generate')">➕ Générer</button>
            <button class="tab-btn" onclick="showTab('licenses')">📋 Licences</button>
            <button class="tab-btn" onclick="showTab('settings')">⚙️ Paramètres</button>
        </div>
        
        <!-- Tab: Générer -->
        <div id="tab-generate" class="tab-content">
            <div class="card">
                <h2>📝 Nouvelle Licence</h2>
                
                <div id="keys-status"></div>
                
                <form id="license-form" onsubmit="generateLicense(event)">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Nom du client *</label>
                            <input type="text" name="customer_name" required placeholder="Entreprise XYZ">
                        </div>
                        <div class="form-group">
                            <label>Email *</label>
                            <input type="email" name="customer_email" required placeholder="contact@entreprise.com">
                        </div>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label>Hostname Splunk *</label>
                            <input type="text" name="hostname" required placeholder="splunk-server.exemple.com">
                        </div>
                        <div class="form-group">
                            <label>Durée (jours)</label>
                            <input type="number" name="duration_days" placeholder="Laisser vide pour la durée par défaut">
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Type de licence *</label>
                        <div class="license-types" id="license-types">
                            <!-- Généré dynamiquement -->
                        </div>
                        <input type="hidden" name="license_type" id="license_type" value="professional">
                    </div>
                    
                    <div class="form-group">
                        <label>Notes internes</label>
                        <textarea name="notes" rows="2" placeholder="Notes sur ce client (usage interne)"></textarea>
                    </div>
                    
                    <button type="submit" class="btn btn-primary">🔑 Générer la licence</button>
                </form>
                
                <div id="result" class="result-card hidden">
                    <h3>✅ Licence générée avec succès</h3>
                    <div class="result-info" id="result-info"></div>
                    <h4>Contenu du fichier .lic</h4>
                    <div class="license-content" id="license-content"></div>
                    <button class="copy-btn" onclick="copyLicense()">📋 Copier</button>
                    <button class="copy-btn" onclick="downloadLicense()">💾 Télécharger</button>
                </div>
            </div>
        </div>
        
        <!-- Tab: Licences -->
        <div id="tab-licenses" class="tab-content hidden">
            <div class="stats-grid" id="stats-grid">
                <!-- Généré dynamiquement -->
            </div>
            
            <div class="card">
                <h2>📋 Licences émises</h2>
                <div id="licenses-list">
                    <table class="licenses-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Client</th>
                                <th>Hostname</th>
                                <th>Type</th>
                                <th>Expiration</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="licenses-tbody">
                            <!-- Généré dynamiquement -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- Tab: Paramètres -->
        <div id="tab-settings" class="tab-content hidden">
            <div class="card">
                <h2>🔑 Clés RSA</h2>
                <div id="keys-info"></div>
                
                <div class="form-group">
                    <label>Clé publique (à intégrer dans le client)</label>
                    <textarea id="public-key" rows="10" readonly style="font-family: monospace; font-size: 0.85em;"></textarea>
                    <button class="copy-btn" onclick="copyPublicKey()">📋 Copier la clé publique</button>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                    <h3 style="color: #f44336; margin-bottom: 15px;">⚠️ Zone dangereuse</h3>
                    <p style="margin-bottom: 15px; color: #666;">Régénérer les clés invalidera TOUTES les licences existantes.</p>
                    <button class="btn btn-danger" onclick="regenerateKeys()">🔄 Régénérer les clés RSA</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentLicense = null;
        
        const LICENSE_TYPES = ''' + json.dumps(LICENSE_TYPES) + ''';
        
        // Initialisation
        document.addEventListener('DOMContentLoaded', function() {
            renderLicenseTypes();
            loadKeysStatus();
            loadLicenses();
        });
        
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.remove('hidden');
            event.target.classList.add('active');
            
            if (tabName === 'licenses') {
                loadLicenses();
            } else if (tabName === 'settings') {
                loadSettings();
            }
        }
        
        function renderLicenseTypes() {
            const container = document.getElementById('license-types');
            let html = '';
            
            for (const [key, config] of Object.entries(LICENSE_TYPES)) {
                const apps = config.max_apps === -1 ? 'Illimité' : config.max_apps;
                const pushes = config.max_pushes_per_day === -1 ? 'Illimité' : config.max_pushes_per_day;
                
                html += `
                    <div class="license-type ${key === 'professional' ? 'selected' : ''}" 
                         onclick="selectLicenseType('${key}')" data-type="${key}">
                        <div class="icon">${config.icon}</div>
                        <div class="name">${config.name}</div>
                        <div class="details">${apps} apps • ${config.duration_days}j</div>
                    </div>
                `;
            }
            
            container.innerHTML = html;
        }
        
        function selectLicenseType(type) {
            document.querySelectorAll('.license-type').forEach(el => el.classList.remove('selected'));
            document.querySelector(`.license-type[data-type="${type}"]`).classList.add('selected');
            document.getElementById('license_type').value = type;
        }
        
        async function loadKeysStatus() {
            try {
                const response = await fetch('/api/keys/status');
                const data = await response.json();
                
                const statusDiv = document.getElementById('keys-status');
                if (data.exists) {
                    statusDiv.innerHTML = `
                        <div class="keys-status">
                            ✅ Clés RSA configurées • Créées le ${data.created || 'N/A'}
                        </div>
                    `;
                } else {
                    statusDiv.innerHTML = `
                        <div class="keys-status warning">
                            ⚠️ Aucune clé RSA trouvée. Les clés seront générées automatiquement.
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error loading keys status:', error);
            }
        }
        
        async function generateLicense(event) {
            event.preventDefault();
            
            const form = event.target;
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            if (data.duration_days) {
                data.duration_days = parseInt(data.duration_days);
            } else {
                delete data.duration_days;
            }
            
            try {
                const response = await fetch('/api/license/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentLicense = result;
                    showResult(result);
                } else {
                    alert('Erreur: ' + result.error);
                }
            } catch (error) {
                alert('Erreur: ' + error.message);
            }
        }
        
        function showResult(result) {
            const resultDiv = document.getElementById('result');
            const infoDiv = document.getElementById('result-info');
            const contentDiv = document.getElementById('license-content');
            
            const lic = result.license_data;
            
            infoDiv.innerHTML = `
                <div><label>ID Licence</label><span>${lic.license_id}</span></div>
                <div><label>Client</label><span>${lic.customer_name}</span></div>
                <div><label>Hostname</label><span>${lic.hostname}</span></div>
                <div><label>Type</label><span>${lic.license_name}</span></div>
                <div><label>Expiration</label><span>${lic.expiration_date}</span></div>
                <div><label>Fichier</label><span>${result.filename}</span></div>
            `;
            
            contentDiv.textContent = result.content;
            resultDiv.classList.remove('hidden');
        }
        
        function copyLicense() {
            const content = document.getElementById('license-content').textContent;
            navigator.clipboard.writeText(content).then(() => {
                alert('Licence copiée dans le presse-papiers !');
            });
        }
        
        function downloadLicense() {
            if (!currentLicense) return;
            
            const blob = new Blob([currentLicense.content], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = currentLicense.filename;
            a.click();
            URL.revokeObjectURL(url);
        }
        
        async function loadLicenses() {
            try {
                const response = await fetch('/api/licenses');
                const data = await response.json();
                
                // Stats
                const stats = {
                    total: data.licenses.length,
                    active: data.licenses.filter(l => l.status === 'active' && new Date(l.expiration_date) > new Date()).length,
                    expired: data.licenses.filter(l => new Date(l.expiration_date) <= new Date()).length,
                    revoked: data.licenses.filter(l => l.status === 'revoked').length
                };
                
                document.getElementById('stats-grid').innerHTML = `
                    <div class="stat-card"><div class="number">${stats.total}</div><div class="label">Total</div></div>
                    <div class="stat-card"><div class="number" style="color: #4caf50;">${stats.active}</div><div class="label">Actives</div></div>
                    <div class="stat-card"><div class="number" style="color: #ff9800;">${stats.expired}</div><div class="label">Expirées</div></div>
                    <div class="stat-card"><div class="number" style="color: #f44336;">${stats.revoked}</div><div class="label">Révoquées</div></div>
                `;
                
                // Table
                const tbody = document.getElementById('licenses-tbody');
                if (data.licenses.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #888;">Aucune licence générée</td></tr>';
                    return;
                }
                
                tbody.innerHTML = data.licenses.map(lic => {
                    const isExpired = new Date(lic.expiration_date) <= new Date();
                    let status = lic.status;
                    if (status === 'active' && isExpired) status = 'expired';
                    
                    const statusClass = status === 'active' ? 'status-active' : 
                                       status === 'expired' ? 'status-expired' : 'status-revoked';
                    const statusLabel = status === 'active' ? 'Active' : 
                                       status === 'expired' ? 'Expirée' : 'Révoquée';
                    
                    return `
                        <tr>
                            <td><code>${lic.license_id}</code></td>
                            <td>${lic.customer_name}</td>
                            <td><code>${lic.hostname}</code></td>
                            <td>${lic.license_name}</td>
                            <td>${lic.expiration_date}</td>
                            <td><span class="status-badge ${statusClass}">${statusLabel}</span></td>
                            <td>
                                <button onclick="downloadLicenseFile('${lic.filename}')" class="btn btn-secondary" style="padding: 6px 12px; font-size: 0.85em;">💾</button>
                                ${status === 'active' ? `<button onclick="revokeLicense('${lic.license_id}')" class="btn btn-danger" style="padding: 6px 12px; font-size: 0.85em;">🚫</button>` : ''}
                            </td>
                        </tr>
                    `;
                }).join('');
                
            } catch (error) {
                console.error('Error loading licenses:', error);
            }
        }
        
        async function revokeLicense(licenseId) {
            if (!confirm('Êtes-vous sûr de vouloir révoquer cette licence ?')) return;
            
            try {
                const response = await fetch('/api/license/revoke', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ license_id: licenseId })
                });
                
                const result = await response.json();
                if (result.success) {
                    loadLicenses();
                } else {
                    alert('Erreur: ' + result.error);
                }
            } catch (error) {
                alert('Erreur: ' + error.message);
            }
        }
        
        async function downloadLicenseFile(filename) {
            window.open('/api/license/download?filename=' + encodeURIComponent(filename));
        }
        
        async function loadSettings() {
            try {
                const response = await fetch('/api/keys/public');
                const data = await response.json();
                
                document.getElementById('public-key').value = data.public_key || 'Aucune clé générée';
                
                document.getElementById('keys-info').innerHTML = data.public_key ? 
                    '<div class="alert alert-success">✅ Les clés RSA sont configurées et prêtes à être utilisées.</div>' :
                    '<div class="alert alert-warning">⚠️ Aucune clé RSA trouvée. Cliquez sur "Régénérer" pour créer une nouvelle paire.</div>';
                    
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        }
        
        function copyPublicKey() {
            const textarea = document.getElementById('public-key');
            textarea.select();
            document.execCommand('copy');
            alert('Clé publique copiée !');
        }
        
        async function regenerateKeys() {
            if (!confirm('⚠️ ATTENTION: Cela invalidera TOUTES les licences existantes !\\n\\nÊtes-vous absolument sûr ?')) return;
            if (!confirm('Dernière confirmation: Régénérer les clés ?')) return;
            
            try {
                const response = await fetch('/api/keys/regenerate', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    alert('Clés régénérées avec succès !');
                    loadSettings();
                } else {
                    alert('Erreur: ' + result.error);
                }
            } catch (error) {
                alert('Erreur: ' + error.message);
            }
        }
    </script>
</body>
</html>
'''


class LicenseManagerHandler(BaseHTTPRequestHandler):
    """Handler HTTP pour l'interface web"""
    
    def log_message(self, format, *args):
        """Personnaliser les logs"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")
    
    def send_json(self, data, status=200):
        """Envoyer une réponse JSON"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_html(self, html):
        """Envoyer une réponse HTML"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def do_GET(self):
        """Gérer les requêtes GET"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/index.html':
            self.send_html(HTML_TEMPLATE)
        
        elif path == '/api/keys/status':
            exists = os.path.exists(PRIVATE_KEY_FILE)
            created = None
            if exists:
                created = datetime.fromtimestamp(os.path.getctime(PRIVATE_KEY_FILE)).strftime('%Y-%m-%d %H:%M')
            self.send_json({'exists': exists, 'created': created})
        
        elif path == '/api/keys/public':
            public_key = get_public_key_string()
            self.send_json({'public_key': public_key})
        
        elif path == '/api/licenses':
            db = load_licenses_db()
            self.send_json(db)
        
        elif path.startswith('/api/license/download'):
            params = parse_qs(parsed.query)
            filename = params.get('filename', [''])[0]

            # N'accepter qu'un nom de fichier simple (pas de séparateurs) et vérifier que le
            # chemin résolu reste bien dans LICENSES_DIR, pour empêcher toute traversée de
            # répertoire (ex: filename="../../../../etc/passwd").
            safe_name = os.path.basename(filename)
            filepath = os.path.normpath(os.path.join(LICENSES_DIR, safe_name))
            licenses_dir_real = os.path.realpath(LICENSES_DIR)

            if (not safe_name or safe_name != filename
                    or not os.path.realpath(filepath).startswith(licenses_dir_real + os.sep)):
                self.send_json({'error': 'Invalid filename'}, 400)
                return

            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{safe_name}"')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_json({'error': 'File not found'}, 404)
        
        else:
            self.send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        """Gérer les requêtes POST"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        
        path = urlparse(self.path).path
        
        if path == '/api/license/generate':
            try:
                result = create_license(
                    customer_name=data.get('customer_name'),
                    customer_email=data.get('customer_email'),
                    hostname=data.get('hostname'),
                    license_type=data.get('license_type', 'professional'),
                    duration_days=data.get('duration_days'),
                    notes=data.get('notes', '')
                )
                self.send_json({
                    'success': True,
                    'license_data': result['license_data'],
                    'filename': result['filename'],
                    'content': result['content']
                })
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)}, 400)
        
        elif path == '/api/license/revoke':
            try:
                revoke_license(data.get('license_id'))
                self.send_json({'success': True})
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)}, 400)
        
        elif path == '/api/keys/regenerate':
            try:
                generate_rsa_keys()
                self.send_json({'success': True})
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)}, 400)
        
        else:
            self.send_json({'error': 'Not found'}, 404)
    
    def do_OPTIONS(self):
        """Gérer les requêtes OPTIONS (CORS)"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def find_available_port(host, start_port=8089, max_attempts=10):
    """Trouver un port disponible"""
    import socket

    for port in range(start_port, start_port + max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((host, port))
            sock.close()
            return port
        except OSError:
            continue

    return None


def main():
    """Point d'entrée principal"""
    import argparse

    parser = argparse.ArgumentParser(description='GitDeploy License Manager')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help=f'Port à utiliser (défaut: {DEFAULT_PORT})')
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help=f'Adresse d\'écoute (défaut: {DEFAULT_HOST} - loopback uniquement). '
                             'Cet outil ne fait AUCUNE authentification: ne jamais utiliser '
                             '0.0.0.0 ou une IP publique sans le protéger autrement (VPN, tunnel SSH...).')
    parser.add_argument('--no-browser', action='store_true',
                        help='Ne pas ouvrir le navigateur automatiquement')
    args = parser.parse_args()

    if args.host not in ('127.0.0.1', 'localhost', '::1'):
        print("⚠️  " + "=" * 68)
        print("⚠️  ATTENTION: écoute sur une adresse non locale (" + args.host + ").")
        print("⚠️  Cet outil ne fait AUCUNE authentification et permet de générer des")
        print("⚠️  licences illimitées à quiconque peut l'atteindre sur le réseau.")
        print("⚠️  " + "=" * 68)

    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     🔐 GitDeploy License Manager - Interface Web          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Créer les dossiers nécessaires
    os.makedirs(KEYS_DIR, exist_ok=True)
    os.makedirs(LICENSES_DIR, exist_ok=True)
    
    # Vérifier/générer les clés
    if not os.path.exists(PRIVATE_KEY_FILE):
        print("🔑 Génération des clés RSA...")
        generate_rsa_keys()
        print()
    
    # Trouver un port disponible
    port = args.port
    host = args.host
    try:
        server = HTTPServer((host, port), LicenseManagerHandler)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"⚠️  Port {port} déjà utilisé, recherche d'un port disponible...")
            port = find_available_port(host, port + 1)
            if port is None:
                print("❌ Impossible de trouver un port disponible")
                sys.exit(1)
            server = HTTPServer((host, port), LicenseManagerHandler)
        else:
            raise

    display_host = 'localhost' if host in ('127.0.0.1', '::1') else host
    url = f"http://{display_host}:{port}"
    print(f"🌐 Serveur démarré sur {url}")
    print()
    print("📋 Endpoints disponibles:")
    print(f"   • Interface web: {url}")
    print(f"   • API Generate:  POST {url}/api/license/generate")
    print(f"   • API Licenses:  GET  {url}/api/licenses")
    print()
    print("Appuyez sur Ctrl+C pour arrêter le serveur")
    print()
    
    # Ouvrir le navigateur automatiquement
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Serveur arrêté")
        server.shutdown()


if __name__ == '__main__':
    main()
