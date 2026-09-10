// ============================================
// GIT PUSHER - LICENSE VALIDATION (RSA)
// Version 2.1 - 100% Client-Side Validation
// ============================================

// Configuration par défaut
const DEFAULT_APP_CONFIG = {
    api: {
        url: '',
        port: 9999,
        useProxy: true
    }
};

// Charger la configuration
function loadAppConfigForLicense() {
    try {
        const stored = localStorage.getItem('gitdeploy_config');
        if (stored) {
            return JSON.parse(stored);
        }
    } catch (e) {
        console.warn('Erreur chargement config localStorage:', e);
    }
    return DEFAULT_APP_CONFIG;
}

// Déterminer l'URL du serveur API
function getLicenseServerUrl() {
    const config = loadAppConfigForLicense();
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;
    
    // Si une URL est configurée, l'utiliser
    if (config.api && config.api.url) {
        let url = config.api.url;
        // Ajouter le port si pas de proxy
        if (!config.api.useProxy && config.api.port) {
            url = url.replace(/\/$/, '') + ':' + config.api.port;
        }
        return url;
    }
    
    // Fallback : auto-détection basée sur le hostname
    // Si c'est une IP ou localhost, ajouter le port 9999
    if (/^(\d{1,3}\.){3}\d{1,3}$/.test(hostname) || hostname === 'localhost') {
        return protocol + '//' + hostname + ':9999';
    }
    
    // Si c'est un domaine, essayer d'ajouter -api au sous-domaine
    // Exemple: splunk.example.com → splunk-api.example.com
    const parts = hostname.split('.');
    if (parts.length >= 2) {
        parts[0] = parts[0] + '-api';
        return protocol + '//' + parts.join('.');
    }
    
    // Dernier fallback : même hostname avec port 9999
    return protocol + '//' + hostname + ':9999';
}

// Configuration
const LICENSE_CONFIG = {
    storageKey: 'gitdeploy_license',
    usageKey: 'gitdeploy_usage',
    version: '2.1.0',
    serverUrl: getLicenseServerUrl()
};

// ============================================
// CLÉ PUBLIQUE RSA
// ============================================
// Cette clé est générée par le vendeur avec license_generator_rsa.py
// Commande: python3 license_generator_rsa.py export-key

const PUBLIC_KEY_PEM = `-----BEGIN PUBLIC KEY-----
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
-----END PUBLIC KEY-----`;

// ============================================
// UTILITAIRES CRYPTO
// ============================================

/**
 * Convertir une chaîne PEM en ArrayBuffer
 */
function pemToArrayBuffer(pem) {
    const b64 = pem
        .replace(/-----BEGIN PUBLIC KEY-----/, '')
        .replace(/-----END PUBLIC KEY-----/, '')
        .replace(/\s/g, '');
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

/**
 * Importer la clé publique RSA
 */
async function importPublicKey() {
    try {
        const keyData = pemToArrayBuffer(PUBLIC_KEY_PEM);
        const key = await crypto.subtle.importKey(
            'spki',
            keyData,
            {
                name: 'RSASSA-PKCS1-v1_5',
                hash: 'SHA-256'
            },
            false,
            ['verify']
        );
        return key;
    } catch (error) {
        console.error('Erreur import clé publique:', error);
        return null;
    }
}

/**
 * Vérifier la signature RSA PKCS#1 v1.5
 */
async function verifySignature(data, signatureB64, publicKey) {
    try {
        const signature = Uint8Array.from(atob(signatureB64), c => c.charCodeAt(0));
        const dataBuffer = new TextEncoder().encode(data);
        
        const isValid = await crypto.subtle.verify(
            'RSASSA-PKCS1-v1_5',
            publicKey,
            signature,
            dataBuffer
        );
        
        return isValid;
    } catch (error) {
        console.error('Erreur vérification signature:', error);
        return false;
    }
}

// ============================================
// FONCTIONS UTILITAIRES
// ============================================

/**
 * Décoder Base64
 */
function base64Decode(str) {
    try {
        return decodeURIComponent(atob(str).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
    } catch (e) {
        return atob(str);
    }
}

/**
 * Obtenir le hostname actuel (depuis l'URL)
 */
function getCurrentHostname() {
    return window.location.hostname.toLowerCase();
}

/**
 * Obtenir le vrai hostname Splunk via l'API REST
 */
async function getSplunkHostname() {
    try {
        // Méthode 1: Via server/info
        const response = await fetch('/en-US/splunkd/__raw/services/server/info?output_mode=json', {
            credentials: 'include'
        });
        if (response.ok) {
            const data = await response.json();
            const serverName = data.entry?.[0]?.content?.serverName;
            if (serverName) {
                console.log('Hostname Splunk (server/info):', serverName);
                return serverName.toLowerCase();
            }
        }
    } catch (e) {
        console.log('Méthode server/info échouée:', e);
    }
    
    try {
        // Méthode 2: Via server/settings
        const response2 = await fetch('/en-US/splunkd/__raw/services/server/settings?output_mode=json', {
            credentials: 'include'
        });
        if (response2.ok) {
            const data2 = await response2.json();
            const serverName = data2.entry?.[0]?.content?.serverName;
            if (serverName) {
                console.log('Hostname Splunk (server/settings):', serverName);
                return serverName.toLowerCase();
            }
        }
    } catch (e) {
        console.log('Méthode server/settings échouée:', e);
    }
    
    // Fallback: hostname de l'URL (pas idéal)
    console.warn('Impossible de récupérer le hostname Splunk, utilisation URL:', getCurrentHostname());
    return getCurrentHostname();
}

/**
 * Calculer les jours restants
 */
function daysRemaining(expiryDate) {
    const expiry = new Date(expiryDate);
    const now = new Date();
    const diff = expiry - now;
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

// ============================================
// PARSING DE LICENCE
// ============================================

/**
 * Parser le contenu d'un fichier .lic
 */
function parseLicenseFile(content) {
    try {
        const lines = content.trim().split('\n');
        let payloadB64 = null;
        
        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed && !trimmed.startsWith('#')) {
                payloadB64 = trimmed;
                break;
            }
        }
        
        if (!payloadB64) {
            return { error: 'Payload non trouvé dans le fichier' };
        }
        
        // Décoder le payload
        const payloadJson = base64Decode(payloadB64);
        const payload = JSON.parse(payloadJson);
        
        if (!payload.license || !payload.signature) {
            return { error: 'Format de licence invalide' };
        }
        
        // Décoder les données de licence
        const licenseJson = base64Decode(payload.license);
        const licenseData = JSON.parse(licenseJson);
        
        return {
            success: true,
            licenseJson: licenseJson,
            licenseData: licenseData,
            signatureB64: payload.signature,
            rawPayload: payloadB64
        };
    } catch (error) {
        console.error('Erreur parsing licence:', error);
        return { error: 'Erreur de lecture du fichier de licence' };
    }
}

// ============================================
// VALIDATION DE LICENCE
// ============================================

/**
 * Valider une licence complète (signature RSA + hostname + expiration)
 */
async function validateLicense(licenseContent = null) {
    try {
        // Si pas de contenu fourni, charger depuis le localStorage
        let parsed;
        if (licenseContent) {
            parsed = parseLicenseFile(licenseContent);
        } else {
            const stored = localStorage.getItem(LICENSE_CONFIG.storageKey);
            if (!stored) {
                return {
                    valid: false,
                    error: 'Aucune licence installée',
                    error_code: 'NO_LICENSE'
                };
            }
            parsed = JSON.parse(stored);
        }
        
        if (parsed.error) {
            return {
                valid: false,
                error: parsed.error,
                error_code: 'PARSE_ERROR'
            };
        }
        
        const { licenseJson, licenseData, signatureB64 } = parsed;
        
        // DEBUG: Afficher les données
        console.log('=== DEBUG VALIDATION LICENCE ===');
        console.log('License JSON:', licenseJson);
        console.log('License JSON length:', licenseJson.length);
        console.log('Signature B64:', signatureB64.substring(0, 50) + '...');
        console.log('Signature B64 length:', signatureB64.length);
        
        // 1. Vérifier la signature RSA
        console.log('Vérification de la signature RSA...');
        const publicKey = await importPublicKey();
        
        if (!publicKey) {
            console.error('Échec import clé publique');
            return {
                valid: false,
                error: 'Impossible de charger la clé publique',
                error_code: 'KEY_ERROR'
            };
        }
        
        console.log('Clé publique importée avec succès');
        
        const signatureValid = await verifySignature(licenseJson, signatureB64, publicKey);
        
        console.log('Résultat vérification signature:', signatureValid);
        
        if (!signatureValid) {
            return {
                valid: false,
                error: 'Signature de licence invalide',
                error_code: 'INVALID_SIGNATURE'
            };
        }
        
        console.log('✓ Signature RSA valide');
        
        // 2. Vérifier le hostname
        const expectedHostname = (licenseData.hostname || '').toLowerCase();
        const currentHostname = await getSplunkHostname();
        
        console.log(`Hostname attendu: "${expectedHostname}", actuel: "${currentHostname}"`);
        
        // Permettre une correspondance partielle ou exacte
        if (expectedHostname && expectedHostname !== currentHostname) {
            // Vérifier si c'est une correspondance partielle (le hostname peut être un FQDN)
            if (!currentHostname.includes(expectedHostname) && !expectedHostname.includes(currentHostname)) {
                return {
                    valid: false,
                    error: `Licence non valide pour ce serveur. Attendu: ${expectedHostname}, Actuel: ${currentHostname}`,
                    error_code: 'HOSTNAME_MISMATCH',
                    expected_hostname: expectedHostname,
                    current_hostname: currentHostname
                };
            }
            console.log('✓ Hostname valide (correspondance partielle)');
        } else {
            console.log('✓ Hostname valide (exact)');
        }
        
        // 3. Vérifier la date d'expiration
        const expiryDate = licenseData.expires;
        if (expiryDate) {
            const days = daysRemaining(expiryDate);
            
            if (days < 0) {
                return {
                    valid: false,
                    error: `Licence expirée le ${expiryDate}`,
                    error_code: 'LICENSE_EXPIRED',
                    expires: expiryDate
                };
            }
            
            console.log(`✓ Licence valide (${days} jours restants)`);
        }
        
        // Licence valide !
        return {
            valid: true,
            license_id: licenseData.license_id,
            type: licenseData.type,
            type_name: licenseData.type_name,
            customer: licenseData.customer,
            hostname: expectedHostname,
            issued: licenseData.issued,
            expires: expiryDate,
            days_remaining: daysRemaining(expiryDate),
            limits: licenseData.limits || {},
            features: licenseData.features || []
        };
        
    } catch (error) {
        console.error('Erreur validation licence:', error);
        return {
            valid: false,
            error: error.message,
            error_code: 'VALIDATION_ERROR'
        };
    }
}

/**
 * Vérifier si une fonctionnalité est disponible
 */
async function hasFeature(featureName) {
    const validation = await validateLicense();
    if (!validation.valid) return false;
    return validation.features.includes(featureName);
}

// ============================================
// GESTION DU STOCKAGE
// ============================================

/**
 * Sauvegarder une licence validée (localStorage + serveur)
 */
async function saveLicense(licenseContent) {
    try {
        // Parser le fichier
        const parsed = parseLicenseFile(licenseContent);
        
        if (parsed.error) {
            return {
                success: false,
                error: parsed.error
            };
        }
        
        // Valider la licence avant de sauvegarder
        const validation = await validateLicense(licenseContent);
        
        if (!validation.valid) {
            return {
                success: false,
                error: validation.error,
                error_code: validation.error_code
            };
        }
        
        // 1. Sauvegarder dans localStorage
        localStorage.setItem(LICENSE_CONFIG.storageKey, JSON.stringify(parsed));
        console.log('✓ Licence sauvegardée dans localStorage');
        
        // 2. Sauvegarder sur le serveur (pour persistance après vidage cache)
        try {
            const response = await fetch(`${LICENSE_CONFIG.serverUrl}/license/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    license_content: licenseContent
                })
            });
            
            const serverResult = await response.json();
            
            if (serverResult.success) {
                console.log('✓ Licence sauvegardée sur le serveur');
            } else {
                console.warn('⚠ Échec sauvegarde serveur:', serverResult.error);
                // On continue quand même car localStorage fonctionne
            }
        } catch (serverError) {
            console.warn('⚠ Impossible de sauvegarder sur le serveur:', serverError);
            // On continue quand même car localStorage fonctionne
        }
        
        return {
            success: true,
            license: validation
        };
        
    } catch (error) {
        console.error('Erreur sauvegarde licence:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

/**
 * Charger la licence depuis le serveur (si localStorage vide)
 */
async function loadLicenseFromServer() {
    try {
        const response = await fetch(`${LICENSE_CONFIG.serverUrl}/license/file`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success && result.content) {
            console.log('Licence trouvée sur le serveur, validation en cours...');
            
            // Parser et valider la licence
            const parsed = parseLicenseFile(result.content);
            
            if (parsed.error) {
                console.warn('Erreur parsing licence serveur:', parsed.error);
                return false;
            }
            
            // Valider la signature
            const validation = await validateLicense(result.content);
            
            if (validation.valid) {
                // Sauvegarder dans localStorage pour les prochaines fois
                localStorage.setItem(LICENSE_CONFIG.storageKey, JSON.stringify(parsed));
                console.log('✓ Licence chargée depuis le serveur et stockée localement');
                return true;
            } else {
                console.warn('Licence serveur invalide:', validation.error);
                return false;
            }
        } else {
            console.log('Aucune licence sur le serveur');
            return false;
        }
    } catch (error) {
        console.log('Impossible de charger la licence depuis le serveur:', error.message);
        return false;
    }
}

/**
 * Supprimer la licence (localStorage + serveur)
 */
async function removeLicense() {
    // Supprimer du localStorage
    localStorage.removeItem(LICENSE_CONFIG.storageKey);
    localStorage.removeItem(LICENSE_CONFIG.usageKey);
    
    // Supprimer du serveur
    try {
        await fetch(`${LICENSE_CONFIG.serverUrl}/license/delete`, {
            method: 'POST'
        });
        console.log('Licence supprimée du serveur');
    } catch (e) {
        console.warn('Impossible de supprimer la licence du serveur:', e);
    }
    
    console.log('Licence supprimée');
}

/**
 * Récupérer les infos de licence (sans revalider la signature)
 */
function getLicenseInfo() {
    try {
        const stored = localStorage.getItem(LICENSE_CONFIG.storageKey);
        if (!stored) return null;
        
        const parsed = JSON.parse(stored);
        return parsed.licenseData;
    } catch {
        return null;
    }
}

// ============================================
// GESTION DES LIMITES D'UTILISATION
// ============================================

/**
 * Obtenir les stats d'utilisation
 */
function getUsageStats() {
    try {
        const stored = localStorage.getItem(LICENSE_CONFIG.usageKey);
        if (stored) {
            return JSON.parse(stored);
        }
    } catch {}
    
    return {
        total_pushes: 0,
        pushes_today: 0,
        last_push_date: null
    };
}

/**
 * Incrémenter le compteur d'utilisation
 */
function incrementUsage() {
    const stats = getUsageStats();
    const today = new Date().toISOString().split('T')[0];
    
    // Reset si nouveau jour
    if (stats.last_push_date !== today) {
        stats.pushes_today = 0;
        stats.last_push_date = today;
    }
    
    stats.total_pushes = (stats.total_pushes || 0) + 1;
    stats.pushes_today = (stats.pushes_today || 0) + 1;
    
    localStorage.setItem(LICENSE_CONFIG.usageKey, JSON.stringify(stats));
    return stats;
}

/**
 * Vérifier les limites avant un push
 */
async function checkLimits() {
    const validation = await validateLicense();
    
    if (!validation.valid) {
        return {
            allowed: false,
            error: validation.error,
            error_code: validation.error_code
        };
    }
    
    const limits = validation.limits || {};
    const maxPushes = limits.max_pushes_per_day || -1;
    
    if (maxPushes > 0) {
        const stats = getUsageStats();
        const today = new Date().toISOString().split('T')[0];
        
        // Reset si nouveau jour
        let pushesToday = stats.pushes_today || 0;
        if (stats.last_push_date !== today) {
            pushesToday = 0;
        }
        
        if (pushesToday >= maxPushes) {
            return {
                allowed: false,
                error: `Limite quotidienne atteinte (${maxPushes} pushes/jour)`,
                error_code: 'DAILY_LIMIT_REACHED'
            };
        }
    }
    
    return {
        allowed: true,
        license_type: validation.type_name,
        remaining_today: maxPushes > 0 ? maxPushes - getUsageStats().pushes_today : -1
    };
}

// ============================================
// INTERFACE UTILISATEUR
// ============================================

/**
 * Afficher le badge de licence
 */
async function updateLicenseBadge() {
    const container = document.getElementById('license-badge-container');
    if (!container) return;
    
    const validation = await validateLicense();
    
    let badgeHtml = '';
    
    if (validation.valid) {
        const daysLeft = validation.days_remaining;
        let badgeClass = 'license-badge-valid';
        let icon = '✓';
        
        if (daysLeft <= 7) {
            badgeClass = 'license-badge-expiring';
            icon = '⚠️';
        } else if (daysLeft <= 30) {
            badgeClass = 'license-badge-warning';
            icon = '⏳';
        }
        
        badgeHtml = `
            <div class="license-badge ${badgeClass}" onclick="showLicenseDetails()">
                <span class="license-icon">${icon}</span>
                <span class="license-type">${validation.type_name}</span>
                <span class="license-days">${daysLeft}j</span>
            </div>
        `;
    } else {
        badgeHtml = `
            <div class="license-badge license-badge-invalid" onclick="showLicenseModal()">
                <span class="license-icon">🔐</span>
                <span class="license-type">Activer</span>
            </div>
        `;
    }
    
    container.innerHTML = badgeHtml;
}

/**
 * Afficher le modal de licence
 */
function showLicenseModal(message = null, errorCode = null) {
    // Supprimer l'ancien modal s'il existe
    const existingModal = document.getElementById('license-modal');
    if (existingModal) existingModal.remove();
    
    const modal = document.createElement('div');
    modal.id = 'license-modal';
    modal.className = 'license-modal-overlay';
    
    let errorMessage = '';
    if (message) {
        errorMessage = `<div class="license-error-message">${message}</div>`;
    }
    
    modal.innerHTML = `
        <div class="license-modal">
            <div class="license-modal-header">
                <h2>🔐 Activation de Licence</h2>
                <button class="license-modal-close" onclick="closeLicenseModal()">×</button>
            </div>
            
            <div class="license-modal-body">
                ${errorMessage}
                
                <div class="license-upload-zone" id="license-upload-zone">
                    <div class="license-upload-icon">📄</div>
                    <div class="license-upload-text">
                        Glissez-déposez votre fichier <strong>.lic</strong> ici
                        <br><small>ou cliquez pour sélectionner</small>
                    </div>
                    <input type="file" id="license-file-input" accept=".lic" style="display: none;">
                </div>
                
                <div class="license-hostname-info">
                    <strong>Hostname du serveur:</strong>
                    <code id="current-hostname-display">Chargement...</code>
                    <br><small>Communiquez ce hostname pour obtenir votre licence</small>
                </div>
                
                <div id="license-validation-result"></div>
            </div>
            
            <div class="license-modal-footer">
                <button class="btn btn-secondary" onclick="closeLicenseModal()">Fermer</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Afficher le hostname
    getSplunkHostname().then(hostname => {
        const hostnameDisplay = document.getElementById('current-hostname-display');
        if (hostnameDisplay) {
            hostnameDisplay.textContent = hostname;
        }
    });
    
    // Configurer le drag & drop
    setupLicenseUpload();
}

/**
 * Configurer l'upload de licence
 */
function setupLicenseUpload() {
    const dropZone = document.getElementById('license-upload-zone');
    const fileInput = document.getElementById('license-file-input');
    
    if (!dropZone || !fileInput) return;
    
    // Clic pour sélectionner
    dropZone.addEventListener('click', () => fileInput.click());
    
    // Drag & drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleLicenseFile(files[0]);
        }
    });
    
    // Sélection de fichier
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleLicenseFile(e.target.files[0]);
        }
    });
}

/**
 * Traiter le fichier de licence uploadé
 */
async function handleLicenseFile(file) {
    const resultDiv = document.getElementById('license-validation-result');
    if (!resultDiv) return;
    
    // Vérifier l'extension
    if (!file.name.endsWith('.lic')) {
        resultDiv.innerHTML = `
            <div class="license-result error">
                ❌ Le fichier doit avoir l'extension .lic
            </div>
        `;
        return;
    }
    
    resultDiv.innerHTML = `
        <div class="license-result loading">
            ⏳ Validation en cours...
        </div>
    `;
    
    try {
        // Lire le fichier
        const content = await file.text();
        
        // Sauvegarder et valider
        const result = await saveLicense(content);
        
        if (result.success) {
            const license = result.license;
            resultDiv.innerHTML = `
                <div class="license-result success">
                    <div class="license-success-icon">✅</div>
                    <div class="license-success-text">
                        <strong>Licence activée avec succès !</strong><br>
                        Type: ${license.type_name}<br>
                        Expire: ${license.expires} (${license.days_remaining} jours)<br>
                        Client: ${license.customer?.name || 'N/A'}
                    </div>
                </div>
            `;
            
            // Mettre à jour le badge
            updateLicenseBadge();
            
            // Fermer le modal après 3 secondes
            setTimeout(() => {
                closeLicenseModal();
            }, 3000);
            
        } else {
            resultDiv.innerHTML = `
                <div class="license-result error">
                    ❌ ${result.error}
                </div>
            `;
        }
        
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="license-result error">
                ❌ Erreur: ${error.message}
            </div>
        `;
    }
}

/**
 * Fermer le modal de licence
 */
function closeLicenseModal() {
    const modal = document.getElementById('license-modal');
    if (modal) modal.remove();
}

/**
 * Afficher les détails de la licence
 */
async function showLicenseDetails() {
    const validation = await validateLicense();
    
    if (!validation.valid) {
        showLicenseModal(validation.error, validation.error_code);
        return;
    }
    
    // Supprimer l'ancien modal s'il existe
    const existingModal = document.getElementById('license-details-modal');
    if (existingModal) existingModal.remove();
    
    const modal = document.createElement('div');
    modal.id = 'license-details-modal';
    modal.className = 'license-modal-overlay';
    
    const features = validation.features.map(f => `<span class="feature-tag">${f}</span>`).join(' ');
    const limits = validation.limits;
    const maxApps = limits.max_apps === -1 ? '∞' : limits.max_apps;
    const maxPushes = limits.max_pushes_per_day === -1 ? '∞' : limits.max_pushes_per_day;
    
    const usage = getUsageStats();
    
    modal.innerHTML = `
        <div class="license-modal">
            <div class="license-modal-header">
                <h2>📋 Détails de la Licence</h2>
                <button class="license-modal-close" onclick="this.closest('.license-modal-overlay').remove()">×</button>
            </div>
            
            <div class="license-modal-body">
                <table class="license-details-table">
                    <tr><td><strong>ID</strong></td><td>${validation.license_id}</td></tr>
                    <tr><td><strong>Type</strong></td><td>${validation.type_name}</td></tr>
                    <tr><td><strong>Client</strong></td><td>${validation.customer?.name || 'N/A'}</td></tr>
                    <tr><td><strong>Email</strong></td><td>${validation.customer?.email || 'N/A'}</td></tr>
                    <tr><td><strong>Hostname</strong></td><td>${validation.hostname}</td></tr>
                    <tr><td><strong>Émise le</strong></td><td>${validation.issued}</td></tr>
                    <tr><td><strong>Expire le</strong></td><td>${validation.expires}</td></tr>
                    <tr><td><strong>Jours restants</strong></td><td>${validation.days_remaining}</td></tr>
                    <tr><td><strong>Apps max</strong></td><td>${maxApps}</td></tr>
                    <tr><td><strong>Pushes/jour</strong></td><td>${maxPushes}</td></tr>
                </table>
                
                <div style="margin-top: 15px;">
                    <strong>Fonctionnalités:</strong><br>
                    <div style="margin-top: 8px;">${features}</div>
                </div>
                
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
                    <strong>Utilisation:</strong><br>
                    <small>Total pushes: ${usage.total_pushes} | Aujourd'hui: ${usage.pushes_today}</small>
                </div>
            </div>
            
            <div class="license-modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.license-modal-overlay').remove()">Fermer</button>
                <button class="btn btn-danger" onclick="confirmRemoveLicense()">Supprimer la licence</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

/**
 * Confirmer la suppression de licence
 */
function confirmRemoveLicense() {
    if (confirm('Êtes-vous sûr de vouloir supprimer cette licence ?')) {
        removeLicense();
        
        // Fermer le modal des détails
        const detailsModal = document.getElementById('license-details-modal');
        if (detailsModal) detailsModal.remove();
        
        // Mettre à jour le badge
        updateLicenseBadge();
        
        alert('Licence supprimée.');
    }
}

/**
 * Vérifier la licence avant un push (appelé par gitdeploy.js)
 */
async function checkLicenseBeforePush() {
    const result = await checkLimits();
    
    if (!result.allowed) {
        showLicenseModal(result.error, result.error_code);
        return false;
    }
    
    return true;
}

// ============================================
// STYLES CSS
// ============================================

const licenseStyles = `
<style>
/* Badge de licence */
.license-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.license-badge:hover {
    transform: scale(1.05);
}

.license-badge-valid {
    background: linear-gradient(135deg, #4CAF50, #45a049);
    color: white;
}

.license-badge-warning {
    background: linear-gradient(135deg, #FF9800, #F57C00);
    color: white;
}

.license-badge-expiring {
    background: linear-gradient(135deg, #f44336, #d32f2f);
    color: white;
    animation: pulse 2s infinite;
}

.license-badge-invalid {
    background: linear-gradient(135deg, #9e9e9e, #757575);
    color: white;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

/* Modal */
.license-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.license-modal {
    background: white;
    border-radius: 16px;
    max-width: 500px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.license-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 25px;
    border-bottom: 1px solid #e0e0e0;
}

.license-modal-header h2 {
    margin: 0;
    font-size: 20px;
    color: #333;
}

.license-modal-close {
    background: none;
    border: none;
    font-size: 28px;
    cursor: pointer;
    color: #999;
    line-height: 1;
}

.license-modal-close:hover {
    color: #333;
}

.license-modal-body {
    padding: 25px;
}

.license-modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 15px 25px;
    border-top: 1px solid #e0e0e0;
}

/* Zone d'upload */
.license-upload-zone {
    border: 2px dashed #ccc;
    border-radius: 12px;
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s ease;
    margin-bottom: 20px;
}

.license-upload-zone:hover,
.license-upload-zone.dragover {
    border-color: #667eea;
    background: #f8f9ff;
}

.license-upload-icon {
    font-size: 48px;
    margin-bottom: 10px;
}

.license-upload-text {
    color: #666;
}

/* Hostname info */
.license-hostname-info {
    background: #f5f5f5;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
}

.license-hostname-info code {
    background: #e0e0e0;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: monospace;
}

/* Résultat de validation */
.license-result {
    padding: 15px;
    border-radius: 8px;
    margin-top: 15px;
}

.license-result.loading {
    background: #e3f2fd;
    color: #1565c0;
}

.license-result.success {
    background: #e8f5e9;
    color: #2e7d32;
    display: flex;
    align-items: center;
    gap: 15px;
}

.license-result.error {
    background: #ffebee;
    color: #c62828;
}

.license-success-icon {
    font-size: 32px;
}

/* Message d'erreur */
.license-error-message {
    background: #ffebee;
    color: #c62828;
    padding: 12px 15px;
    border-radius: 8px;
    margin-bottom: 20px;
    border-left: 4px solid #c62828;
}

/* Table de détails */
.license-details-table {
    width: 100%;
    border-collapse: collapse;
}

.license-details-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #eee;
}

.license-details-table td:first-child {
    width: 40%;
    color: #666;
}

/* Tags de fonctionnalités */
.feature-tag {
    display: inline-block;
    background: #e3f2fd;
    color: #1565c0;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    margin: 2px;
}

/* Bouton danger */
.btn-danger {
    background: #f44336 !important;
    color: white !important;
}

.btn-danger:hover {
    background: #d32f2f !important;
}
</style>
`;

// ============================================
// INITIALISATION
// ============================================

/**
 * Initialiser le système de licence
 */
async function initializeLicense() {
    console.log('GitDeploy for Splunk License System v' + LICENSE_CONFIG.version + ' (RSA)');
    
    // Injecter les styles
    if (!document.getElementById('license-styles')) {
        const styleEl = document.createElement('div');
        styleEl.id = 'license-styles';
        styleEl.innerHTML = licenseStyles;
        document.head.appendChild(styleEl);
    }
    
    // Vérifier si une licence existe dans localStorage
    const stored = localStorage.getItem(LICENSE_CONFIG.storageKey);
    
    if (!stored) {
        console.log('Aucune licence en cache, tentative de chargement depuis le serveur...');
        
        // Essayer de charger depuis le serveur
        const loadedFromServer = await loadLicenseFromServer();
        
        if (loadedFromServer) {
            console.log('✓ Licence restaurée depuis le serveur');
        } else {
            console.log('Aucune licence disponible');
        }
    } else {
        console.log('Licence trouvée dans le cache local');
    }
    
    // Mettre à jour le badge
    updateLicenseBadge();
}

// Exposer les fonctions globalement
window.initializeLicense = initializeLicense;
window.validateLicense = validateLicense;
window.saveLicense = saveLicense;
window.removeLicense = removeLicense;
window.loadLicenseFromServer = loadLicenseFromServer;
window.checkLicenseBeforePush = checkLicenseBeforePush;
window.showLicenseModal = showLicenseModal;
window.closeLicenseModal = closeLicenseModal;
window.showLicenseDetails = showLicenseDetails;
window.confirmRemoveLicense = confirmRemoveLicense;
window.updateLicenseBadge = updateLicenseBadge;
window.hasFeature = hasFeature;
window.incrementUsage = incrementUsage;
window.getUsageStats = getUsageStats;
window.getLicenseInfo = getLicenseInfo;

// Auto-initialiser après le chargement
if (document.readyState === 'complete') {
    setTimeout(initializeLicense, 100);
} else {
    window.addEventListener('load', function() {
        setTimeout(initializeLicense, 100);
    });
}
