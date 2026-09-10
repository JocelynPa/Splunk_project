#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour configurer les credentials Splunk sur le SH Deployer Agent
À exécuter sur le serveur deployer pour configurer les credentials de manière sécurisée

Usage:
    python3 configure_deployer_credentials.py
    python3 configure_deployer_credentials.py --user admin --target https://captain:8089
"""

import os
import sys
import json
import base64
import getpass
import argparse

SPLUNK_HOME = os.environ.get('SPLUNK_HOME', '/opt/splunk')
CREDENTIALS_FILE = f"{SPLUNK_HOME}/etc/apps/deployer_agent/local/credentials.json"


def configure_credentials():
    """Configurer les credentials de manière interactive"""
    print("=" * 60)
    print("SH Deployer Agent - Configuration des credentials Splunk")
    print("=" * 60)
    print()
    print("Ces credentials seront utilisés pour exécuter la commande:")
    print("  splunk apply shcluster-bundle -target <uri> -auth <user>:<pass>")
    print()
    print("Les credentials sont stockés localement de manière sécurisée")
    print(f"Fichier: {CREDENTIALS_FILE}")
    print()
    
    # Vérifier si des credentials existent déjà
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                existing = json.load(f)
            print(f"⚠️  Credentials existants pour l'utilisateur: {existing.get('splunk_user', 'unknown')}")
            confirm = input("Voulez-vous les remplacer? (o/N): ").strip().lower()
            if confirm != 'o' and confirm != 'oui' and confirm != 'y' and confirm != 'yes':
                print("Annulé.")
                return
        except:
            pass
    
    # Collecter les informations
    print()
    splunk_user = input("Nom d'utilisateur Splunk [admin]: ").strip() or "admin"
    splunk_password = getpass.getpass("Mot de passe Splunk: ")
    
    if not splunk_password:
        print("❌ Le mot de passe est requis")
        return
    
    print()
    print("URI du Captain du Search Head Cluster")
    print("Exemple: https://10.10.40.20:8089")
    target_uri = input("Target URI [laisser vide pour utiliser le défaut]: ").strip()
    
    # Sauvegarder
    try:
        os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
        
        creds = {
            'splunk_user': splunk_user,
            'splunk_password_b64': base64.b64encode(splunk_password.encode('utf-8')).decode('utf-8'),
            'target_uri': target_uri if target_uri else None,
            'updated_at': __import__('datetime').datetime.now().isoformat()
        }
        
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(creds, f, indent=2)
        
        # Sécuriser le fichier
        os.chmod(CREDENTIALS_FILE, 0o600)
        
        print()
        print("=" * 60)
        print("✅ Credentials configurés avec succès!")
        print("=" * 60)
        print(f"   Utilisateur: {splunk_user}")
        print(f"   Target URI:  {target_uri or '(par défaut)'}")
        print(f"   Fichier:     {CREDENTIALS_FILE}")
        print()
        print("Redémarrez le deployer agent pour prendre en compte les changements:")
        print("  ./start_deployer.sh restart")
        print()
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")


def show_credentials():
    """Afficher les credentials configurés (sans le mot de passe)"""
    if not os.path.exists(CREDENTIALS_FILE):
        print("❌ Aucun credential configuré")
        print(f"   Fichier attendu: {CREDENTIALS_FILE}")
        return
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
        
        print("=" * 60)
        print("Credentials configurés")
        print("=" * 60)
        print(f"   Utilisateur: {creds.get('splunk_user', 'N/A')}")
        print(f"   Target URI:  {creds.get('target_uri') or '(par défaut)'}")
        print(f"   Mis à jour:  {creds.get('updated_at', 'N/A')}")
        print(f"   Fichier:     {CREDENTIALS_FILE}")
        print()
        
    except Exception as e:
        print(f"❌ Erreur lors de la lecture: {e}")


def delete_credentials():
    """Supprimer les credentials"""
    if not os.path.exists(CREDENTIALS_FILE):
        print("❌ Aucun credential à supprimer")
        return
    
    confirm = input("Êtes-vous sûr de vouloir supprimer les credentials? (o/N): ").strip().lower()
    if confirm != 'o' and confirm != 'oui' and confirm != 'y' and confirm != 'yes':
        print("Annulé.")
        return
    
    try:
        os.remove(CREDENTIALS_FILE)
        print("✅ Credentials supprimés")
    except Exception as e:
        print(f"❌ Erreur: {e}")


def main():
    parser = argparse.ArgumentParser(description='Configurer les credentials Splunk pour le SH Deployer')
    parser.add_argument('action', nargs='?', default='configure',
                       choices=['configure', 'show', 'delete'],
                       help='Action à effectuer (default: configure)')
    parser.add_argument('--user', help='Nom d\'utilisateur Splunk')
    parser.add_argument('--target', help='URI du Captain (ex: https://captain:8089)')
    
    args = parser.parse_args()
    
    if args.action == 'show':
        show_credentials()
    elif args.action == 'delete':
        delete_credentials()
    else:
        # Mode non-interactif si --user est fourni
        if args.user:
            print("Mode non-interactif détecté")
            splunk_password = getpass.getpass("Mot de passe Splunk: ")
            
            if not splunk_password:
                print("❌ Le mot de passe est requis")
                return
            
            try:
                os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
                
                creds = {
                    'splunk_user': args.user,
                    'splunk_password_b64': base64.b64encode(splunk_password.encode('utf-8')).decode('utf-8'),
                    'target_uri': args.target,
                    'updated_at': __import__('datetime').datetime.now().isoformat()
                }
                
                with open(CREDENTIALS_FILE, 'w') as f:
                    json.dump(creds, f, indent=2)
                
                os.chmod(CREDENTIALS_FILE, 0o600)
                
                print(f"✅ Credentials configurés pour: {args.user}")
            except Exception as e:
                print(f"❌ Erreur: {e}")
        else:
            configure_credentials()


if __name__ == '__main__':
    main()
