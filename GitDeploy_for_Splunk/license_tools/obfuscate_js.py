#!/usr/bin/env python3
"""
GitDeploy for Splunk - JavaScript Obfuscator
Obfusque le fichier license_validation.js pour protéger la clé publique
"""

import re
import base64
import random
import string
import json
import sys
import os

def random_var_name(length=8):
    """Générer un nom de variable aléatoire"""
    return '_' + ''.join(random.choices(string.ascii_letters, k=length))

def encode_string_array(s):
    """Encoder une chaîne en tableau de codes de caractères avec XOR"""
    key = random.randint(1, 255)
    encoded = [ord(c) ^ key for c in s]
    return encoded, key

def create_string_decoder():
    """Créer une fonction de décodage de chaînes"""
    return '''
function _d(a,k){return a.map(function(c){return String.fromCharCode(c^k)}).join('')}
'''

def encode_string_for_js(s, var_prefix='_s'):
    """Encoder une chaîne pour JS"""
    encoded, key = encode_string_array(s)
    var_name = random_var_name()
    return var_name, f"var {var_name}=_d([{','.join(map(str, encoded))}],{key});"

def split_key_into_chunks(key_pem, num_chunks=8):
    """Diviser la clé en morceaux"""
    # Extraire le contenu base64 de la clé
    key_content = key_pem.replace('-----BEGIN PUBLIC KEY-----', '')
    key_content = key_content.replace('-----END PUBLIC KEY-----', '')
    key_content = key_content.replace('\n', '').replace(' ', '')
    
    chunk_size = len(key_content) // num_chunks
    chunks = []
    for i in range(num_chunks):
        start = i * chunk_size
        if i == num_chunks - 1:
            chunks.append(key_content[start:])
        else:
            chunks.append(key_content[start:start + chunk_size])
    
    return chunks

def generate_obfuscated_key_reconstruction(chunks):
    """Générer le code pour reconstruire la clé"""
    code_parts = []
    var_names = []
    
    for i, chunk in enumerate(chunks):
        var_name = random_var_name()
        var_names.append(var_name)
        encoded, key = encode_string_array(chunk)
        code_parts.append(f"var {var_name}=_d([{','.join(map(str, encoded))}],{key});")
    
    # Créer la reconstruction
    reconstruct_var = random_var_name()
    header_var = random_var_name()
    footer_var = random_var_name()
    
    # Encoder header et footer
    header_encoded, header_key = encode_string_array('-----BEGIN PUBLIC KEY-----\n')
    footer_encoded, footer_key = encode_string_array('\n-----END PUBLIC KEY-----')
    
    # Header et footer en premier
    header_code = f"var {header_var}=_d([{','.join(map(str, header_encoded))}],{header_key});"
    footer_code = f"var {footer_var}=_d([{','.join(map(str, footer_encoded))}],{footer_key});"
    
    # Assembler : header, chunks, footer, puis reconstruction
    all_declarations = [header_code] + code_parts + [footer_code]
    
    # La reconstruction doit être APRÈS toutes les déclarations
    reconstruct_code = f"var {reconstruct_var}={header_var}+{'+'.join(var_names)}+{footer_var};"
    
    return '\n'.join(all_declarations), reconstruct_code, reconstruct_var

def add_anti_debug():
    """Ajouter du code anti-debug"""
    return '''
(function(){
var _t1=Date.now();debugger;var _t2=Date.now();
if(_t2-_t1>100){console.clear();window.location.reload();}
})();
(function(){
var _c=0;
setInterval(function(){
var _s=Date.now();debugger;
if(Date.now()-_s>50){_c++;if(_c>2){console.clear();}}
},3000);
})();
'''

def add_dead_code():
    """Ajouter du code leurre"""
    fake_vars = []
    for _ in range(10):
        var_name = random_var_name()
        fake_value = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        fake_vars.append(f"var {var_name}='{fake_value}';")
    
    fake_functions = []
    for _ in range(5):
        func_name = random_var_name()
        fake_functions.append(f"""
function {func_name}(a,b){{
var c=a^b;var d=c.toString(16);
return d.split('').reverse().join('');
}}
""")
    
    return '\n'.join(fake_vars) + '\n' + '\n'.join(fake_functions)

def obfuscate_function_names(code):
    """Obfusquer les noms de fonctions internes"""
    # Liste des fonctions à renommer (internes uniquement)
    internal_functions = [
        'pemToArrayBuffer',
        'importPublicKey', 
        'verifySignature',
        'base64Decode',
        'getCurrentHostname',
        'parseLicenseFile',
        'extractSignatureAndContent',
    ]
    
    replacements = {}
    for func in internal_functions:
        new_name = random_var_name()
        replacements[func] = new_name
        # Remplacer les déclarations et appels
        code = re.sub(r'\b' + func + r'\b', new_name, code)
    
    return code, replacements

def minify_code(code):
    """Minifier le code (supprimer commentaires et espaces inutiles)"""
    # Supprimer les commentaires multi-lignes
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    
    # Supprimer les commentaires single-line SEULEMENT en début de ligne ou après un espace
    # Ne pas supprimer // dans les chaînes ou les URLs
    lines = code.split('\n')
    cleaned_lines = []
    for line in lines:
        # Trouver le premier // qui n'est pas dans une chaîne
        in_string = False
        string_char = None
        comment_start = -1
        
        i = 0
        while i < len(line):
            char = line[i]
            
            # Gestion des chaînes
            if char in ['"', "'", '`'] and (i == 0 or line[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
            
            # Détection de commentaire hors chaîne
            if not in_string and char == '/' and i + 1 < len(line) and line[i + 1] == '/':
                comment_start = i
                break
            
            i += 1
        
        if comment_start >= 0:
            line = line[:comment_start]
        
        cleaned_lines.append(line)
    
    code = '\n'.join(cleaned_lines)
    
    # Supprimer les lignes vides multiples
    code = re.sub(r'\n\s*\n', '\n', code)
    
    return code

def obfuscate_license_validation(input_file, output_file):
    """Obfusquer le fichier license_validation.js"""
    
    with open(input_file, 'r') as f:
        original_code = f.read()
    
    # Extraire la clé publique
    key_match = re.search(r"const PUBLIC_KEY_PEM = `(-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----)`", 
                          original_code, re.DOTALL)
    
    if not key_match:
        print("Erreur: Clé publique non trouvée")
        return False
    
    public_key = key_match.group(1)
    
    # Diviser la clé en morceaux
    chunks = split_key_into_chunks(public_key, num_chunks=12)
    
    # Générer le code de reconstruction
    chunk_code, reconstruct_code, key_var = generate_obfuscated_key_reconstruction(chunks)
    
    # Créer l'en-tête obfusqué
    obfuscated_header = f'''
// GitDeploy for Splunk License Module v2.1
// (c) 2026 - Proprietary Software
{create_string_decoder()}
{add_dead_code()}
{chunk_code}
{reconstruct_code}
var PUBLIC_KEY_PEM={key_var};
'''
    
    # Remplacer la déclaration de clé originale
    modified_code = re.sub(
        r"// ============================================\n// CLÉ PUBLIQUE RSA.*?-----END PUBLIC KEY-----`;",
        '',
        original_code,
        flags=re.DOTALL
    )
    
    # Anti-debug: seule protection un peu sérieuse contre l'inspection en devtools.
    # Peut être désactivé pour le développement en repassant cette variable à ''.
    anti_debug = add_anti_debug()

    # Minifier
    modified_code = minify_code(modified_code)

    # Assembler le code final
    final_code = obfuscated_header + anti_debug + modified_code

    # Obfusquer les noms de fonctions internes (pemToArrayBuffer, verifySignature, etc.).
    # Ne touche pas aux fonctions volontairement exposées sur window (validateLicense,
    # checkLimits, checkLicenseBeforePush...) dont gitdeploy.js dépend.
    final_code, _ = obfuscate_function_names(final_code)

    with open(output_file, 'w') as f:
        f.write(final_code)
    
    print(f"✅ Fichier obfusqué créé: {output_file}")
    print(f"   Taille originale: {len(original_code)} caractères")
    print(f"   Taille obfusquée: {len(final_code)} caractères")
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 obfuscate_js.py <input.js> [output.js]")
        print("       python3 obfuscate_js.py license_validation.js")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.js', '.obfuscated.js')
    
    if not os.path.exists(input_file):
        print(f"Erreur: Fichier non trouvé: {input_file}")
        sys.exit(1)
    
    obfuscate_license_validation(input_file, output_file)

if __name__ == '__main__':
    main()
