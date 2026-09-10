// ============================================
// GITDEPLOY FOR SPLUNK - MAIN JAVASCRIPT
// Version 2.1 avec déploiement vers SH Cluster
// ============================================

// Configuration par défaut
const DEFAULT_CONFIG = {
    api: {
        url: '',
        port: 9999,
        useProxy: true,
        // Token d'authentification pour le serveur GitDeploy (voir page Configuration).
        // Requis par le serveur pour tous les appels POST (push, config, licence).
        token: ''
    },
    deployer: {
        enabled: false,
        host: '',
        port: 9998,
        token: '',
        useSSL: true
    }
};

// Charger la configuration
function loadAppConfig() {
    try {
        const stored = localStorage.getItem('gitdeploy_config');
        if (stored) {
            return JSON.parse(stored);
        }
    } catch (e) {
        console.warn('Erreur chargement config localStorage:', e);
    }
    return DEFAULT_CONFIG;
}

// Déterminer l'URL du serveur API
function getServerUrl() {
    const config = loadAppConfig();
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
const GITDEPLOY_CONFIG = {
    serverUrl: getServerUrl(),
    credentialsKey: 'gitdeploy_credentials',
    deployerConfigKey: 'gitdeploy_deployer_config',
    // Token d'authentification pour le serveur GitDeploy, configuré sur la page Configuration.
    apiToken: (loadAppConfig().api && loadAppConfig().api.token) || '',
    version: '2.1.0'
};

// Headers standards pour les appels POST authentifiés vers le serveur GitDeploy
function apiAuthHeaders(extra) {
    return Object.assign({ 'X-Auth-Token': GITDEPLOY_CONFIG.apiToken }, extra || {});
}

// Configuration SH Deployer (peut être modifiée via l'interface)
let SH_DEPLOYER_CONFIG = {
    enabled: false,
    host: '',
    port: 9998,
    token: '',
    useSSL: true,
    // Credentials Splunk pour apply shcluster-bundle (optionnel)
    splunkAuthUser: '',
    splunkAuthPass: ''
};

// Construire l'URL du deployer
function getDeployerUrl() {
    if (!SH_DEPLOYER_CONFIG.host) {
        return null;
    }
    
    const protocol = SH_DEPLOYER_CONFIG.useSSL ? 'https' : 'http';
    const host = SH_DEPLOYER_CONFIG.host;
    const port = SH_DEPLOYER_CONFIG.port || 9998;
    
    // Si c'est un domaine (pas une IP), ne pas ajouter le port si on utilise un proxy
    const isIP = /^(\d{1,3}\.){3}\d{1,3}$/.test(host);
    
    if (isIP || host === 'localhost') {
        return `${protocol}://${host}:${port}`;
    }
    
    // Pour les domaines, vérifier si le port est standard
    if (port === 443 || port === 9998) {
        return `${protocol}://${host}`;
    }
    
    return `${protocol}://${host}:${port}`;
}

// Branches autorisées pour le déploiement SH Cluster
const ALLOWED_SHCLUSTER_BRANCHES = ['main', 'master'];

// Vérifier si la branche actuelle permet le déploiement SH Cluster
function isShClusterBranchAllowed() {
    const branchInput = document.getElementById('git-branch');
    const branch = branchInput?.value?.trim().toLowerCase() || 'main';
    return ALLOWED_SHCLUSTER_BRANCHES.includes(branch);
}

// Mettre à jour l'interface SH Cluster selon la branche sélectionnée
function updateShClusterAvailability() {
    const deployCheckbox = document.getElementById('deploy-to-shcluster');
    const branchWarning = document.getElementById('shcluster-branch-warning');
    const deployerSection = document.getElementById('deployer-section');
    
    const branchAllowed = isShClusterBranchAllowed();
    const branchInput = document.getElementById('git-branch');
    const currentBranch = branchInput?.value?.trim() || 'main';
    
    if (!branchAllowed) {
        // Branche non autorisée pour SH Cluster
        if (deployCheckbox) {
            deployCheckbox.checked = false;
            deployCheckbox.disabled = true;
        }
        
        // Afficher l'avertissement
        if (branchWarning) {
            branchWarning.style.display = 'block';
            branchWarning.innerHTML = `<span style="color: #ff9800;">⚠️ SH Cluster deployment is only available on <strong>main</strong> or <strong>master</strong> branch. Current branch: <strong>${currentBranch}</strong></span>`;
        }
        
        // Masquer les options de déploiement
        const appsSection = document.getElementById('deployer-apps-section');
        if (appsSection) appsSection.classList.remove('visible');
        
        // Griser la section
        if (deployerSection) deployerSection.style.opacity = '0.6';
        
    } else {
        // Branche autorisée
        if (deployCheckbox && deployerAvailable) {
            deployCheckbox.disabled = false;
        }
        
        // Masquer l'avertissement
        if (branchWarning) {
            branchWarning.style.display = 'none';
        }
        
        // Restaurer l'opacité si deployer disponible
        if (deployerSection && deployerAvailable) {
            deployerSection.style.opacity = '1';
        }
    }
}

// Vérifier si les credentials sont configurés sur le deployer
async function checkDeployerCredentials() {
    const statusDiv = document.getElementById('stored-credentials-status');
    const notConfiguredDiv = document.getElementById('deployer-not-configured');
    const deployCheckbox = document.getElementById('deploy-to-shcluster');
    
    // Vérifier si le deployer est configuré (via la variable globale mise à jour par checkDeployerHealth)
    const deployerUrl = getDeployerUrl();
    
    // Si pas d'URL configurée ET deployer non disponible → afficher message
    if (!deployerUrl && !deployerAvailable) {
        if (notConfiguredDiv) notConfiguredDiv.style.display = 'block';
        if (deployCheckbox) deployCheckbox.disabled = true;
        if (statusDiv) statusDiv.innerHTML = '<span style="color: #ff9800;">⚠️ Configure SH Deployer in settings</span>';
        return;
    }
    
    // Si deployer disponible (health check OK), masquer le message "not configured"
    if (deployerAvailable) {
        if (notConfiguredDiv) notConfiguredDiv.style.display = 'none';
        if (deployCheckbox) deployCheckbox.disabled = false;
    }
    
    if (!statusDiv) return;
    if (!deployerUrl) return;
    
    try {
        const response = await fetch(`${deployerUrl}/credentials`, {
            headers: {
                'X-Auth-Token': SH_DEPLOYER_CONFIG.token
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.configured) {
                statusDiv.innerHTML = `<span style="color: #4caf50;">✅ Credentials configured for user: <strong>${data.user}</strong></span>`;
            } else {
                statusDiv.innerHTML = '<span style="color: #ff9800;">⚠️ No Splunk credentials configured on deployer server. <a href="gitdeploy_config" style="color: #0056b3;">Configure now →</a></span>';
            }
        } else {
            statusDiv.innerHTML = '<span style="color: #f44336;">❌ Could not check server credentials</span>';
        }
    } catch (e) {
        console.warn('Could not check deployer credentials:', e);
        statusDiv.innerHTML = '<span style="color: #888;">Could not connect to deployer server</span>';
    }
}

// État global
let selectedApps = [];
let selectedShClusterApps = [];  // Apps sélectionnées pour le SH Cluster
let isProcessing = false;
let deployerAvailable = false;

// ============================================
// INITIALISATION
// ============================================

require([
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/searchmanager',
    'splunkjs/mvc/simplexml/ready!'
], function($, mvc, SearchManager) {
    
    console.log("GitDeploy for Splunk v2.1 initializing...");
    
    // Initialiser le système de licence
    if (typeof initializeLicense === 'function') {
        initializeLicense();
    } else {
        console.warn("License system not loaded");
    }
    
    // Charger les credentials sauvegardés
    loadSavedCredentials();
    
    // Charger la config du deployer
    loadDeployerConfig();
    
    // Vérifier la disponibilité du SH Deployer
    checkDeployerHealth();
    
    // Vérifier les credentials après un court délai (pour laisser le health check se faire)
    setTimeout(function() {
        checkDeployerCredentials();
    }, 1000);
    
    // ============================================
    // GESTION ROBUSTE DE LA LISTE DES APPLICATIONS
    // ============================================
    
    function loadApplications() {
        console.log("Loading applications...");
        
        // Méthode 1: Essayer de récupérer la recherche existante du dashboard
        var searchManager = mvc.Components.get('dsearch');
        
        if (searchManager) {
            console.log("Found dashboard search 'dsearch'");
            
            // Vérifier si la recherche a déjà des résultats
            var existingResults = searchManager.data('results');
            if (existingResults && existingResults.hasData && existingResults.hasData()) {
                console.log("Search already has data, rendering...");
                var rows = existingResults.data().rows;
                var fields = existingResults.data().fields;
                if (rows && rows.length > 0) {
                    renderAppsList(rows, fields);
                    return;
                }
            }
            
            // Écouter les événements de la recherche
            searchManager.on('search:done', function(properties) {
                console.log("Dashboard search completed");
                var results = searchManager.data('results');
                if (results) {
                    results.on('data', function() {
                        if (results.hasData()) {
                            var rows = results.data().rows;
                            var fields = results.data().fields;
                            renderAppsList(rows, fields);
                        }
                    });
                    // Forcer la lecture si les données sont déjà là
                    if (results.hasData()) {
                        var rows = results.data().rows;
                        var fields = results.data().fields;
                        renderAppsList(rows, fields);
                    }
                }
            });
            
            // Si la recherche est déjà terminée, forcer la récupération
            if (searchManager.attributes && searchManager.attributes.data) {
                var job = searchManager.job;
                if (job && job.state() === 'done') {
                    console.log("Search already done, fetching results...");
                    var results = searchManager.data('results');
                    if (results) {
                        results.on('data', function() {
                            if (results.hasData()) {
                                renderAppsList(results.data().rows, results.data().fields);
                            }
                        });
                    }
                }
            }
        } else {
            console.log("Dashboard search not found, creating our own...");
        }
        
        // Méthode 2: Fallback - Créer notre propre recherche après un délai
        setTimeout(function() {
            var container = document.getElementById('dashboard-list');
            if (container && container.innerHTML.indexOf('Loading') !== -1) {
                console.log("Still loading, trying REST API fallback...");
                loadAppsViaREST();
            }
        }, 3000);
    }
    
    // Fallback: Charger via l'API REST directement
    function loadAppsViaREST() {
        console.log("Loading apps via REST API...");
        
        // Liste des applications à exclure (même liste que dans la recherche du dashboard)
        const excludedApps = [
            "splunk_internal_metrics",
            "splunk_monitoring_console",
            "splunk_secure_gateway",
            "splunk_archiver",
            "splunk_httpinput",
            "splunk_instrumentation",
            "learned",
            "legacy",
            "sample_app",
            "search",
            "launcher",
            "gettingstarted",
            "introspection_generator_addon",
            "journald_input",
            "splunk_gdi",
            "splunk_essentials_9",
            "SplunkForwarder",
            "SplunkLightForwarder",
            "appsbrowser",
            "config_explorer",
            "custom_login",
            "gitdeploy_app",
            "Config_ressources",
            "SA-IndexCreation",
            "splunk_metrics_workspace",
            "lookup_editor",
            "splunk-dashboard-studio",
            "splunk_rapid_diag",
            "python_upgrade_readiness_app"
        ];
        
        fetch('/en-US/splunkd/__raw/services/apps/local?output_mode=json&count=0', {
            credentials: 'include'
        })
        .then(function(response) {
            if (!response.ok) throw new Error('REST API error: ' + response.status);
            return response.json();
        })
        .then(function(data) {
            if (data && data.entry) {
                var apps = data.entry
                    .filter(function(app) {
                        // Exclure les apps désactivées
                        if (app.content.disabled) return false;
                        // Exclure les apps non visibles
                        if (app.content.visible === false || app.content.visible === "0") return false;
                        // Exclure les apps de la liste
                        if (excludedApps.indexOf(app.name) !== -1) return false;
                        return true;
                    })
                    .map(function(app) {
                        return {
                            name: app.name,
                            label: app.content.label || app.name,
                            description: app.content.description || ''
                        };
                    })
                    .sort(function(a, b) {
                        return (a.label || '').localeCompare(b.label || '');
                    });
                
                console.log("Loaded " + apps.length + " apps via REST");
                renderAppsListFromObjects(apps);
            }
        })
        .catch(function(error) {
            console.error("REST API fallback failed:", error);
            var container = document.getElementById('dashboard-list');
            if (container) {
                container.innerHTML = '<p style="color: #d32f2f; text-align: center; padding: 20px;">Error loading applications. Please refresh the page.</p>';
            }
        });
    }
    
    // Render depuis des objets (pour le fallback REST)
    function renderAppsListFromObjects(apps) {
        var container = document.getElementById('dashboard-list');
        if (!container) return;
        
        var rows = apps.map(function(app) {
            return [app.name, app.label, app.description];
        });
        var fields = ['name', 'label', 'description'];
        
        renderAppsList(rows, fields);
    }
    
    // Lancer le chargement
    loadApplications();
    
    // Exposer les fonctions globalement
    window.pushDashboards = pushDashboards;
    window.resetForm = resetForm;
    window.toggleSelectAll = toggleSelectAll;
    window.toggleShClusterAllApps = toggleShClusterAllApps;
    window.updateSelectedShClusterApps = updateSelectedShClusterApps;
    window.loadApplications = loadApplications;
    window.loadAppsViaREST = loadAppsViaREST;
    window.selectAppForDashboards = selectAppForDashboards;
    window.loadDashboardsForApp = loadDashboardsForApp;
    window.selectAllDashboards = selectAllDashboards;
    window.updateSelectedDashboards = updateSelectedDashboards;
    window.getSelectedItemsForPush = getSelectedItemsForPush;
    
    // Attacher les événements pour la section SH Cluster
    setTimeout(function() {
        // Checkbox "Deploy to SH Cluster"
        const deployCheckbox = document.getElementById('deploy-to-shcluster');
        if (deployCheckbox) {
            deployCheckbox.addEventListener('change', function() {
                toggleDeployerOptions();
            });
        }
        
        // Checkbox "All apps"
        const allAppsCheckbox = document.getElementById('shcluster-all-apps');
        if (allAppsCheckbox) {
            allAppsCheckbox.addEventListener('change', function() {
                toggleShClusterAllApps();
            });
        }
        
        // Champ de branche Git - mettre à jour la disponibilité SH Cluster
        const branchInput = document.getElementById('git-branch');
        if (branchInput) {
            branchInput.addEventListener('input', function() {
                updateShClusterAvailability();
            });
            branchInput.addEventListener('change', function() {
                updateShClusterAvailability();
            });
            // Vérifier l'état initial
            updateShClusterAvailability();
        }
    }, 500);
});

// Afficher/masquer les options du deployer
function toggleDeployerOptions() {
    const checkbox = document.getElementById('deploy-to-shcluster');
    const appsSection = document.getElementById('deployer-apps-section');
    
    if (checkbox && checkbox.checked) {
        if (appsSection) appsSection.classList.add('visible');
        // Vérifier les credentials quand on active le déploiement
        checkDeployerCredentials();
    } else {
        if (appsSection) appsSection.classList.remove('visible');
    }
}

// ============================================
// RENDU DE LA LISTE DES APPLICATIONS
// ============================================

function renderAppsList(rows, fields) {
    const container = document.getElementById('dashboard-list');
    if (!container) return;
    
    // Trouver les index des colonnes
    const nameIdx = fields.indexOf('name');
    const labelIdx = fields.indexOf('label');
    const descIdx = fields.indexOf('description');
    
    // Stocker les apps pour référence
    window.availableApps = rows.map(row => ({
        name: row[nameIdx] || '',
        label: row[labelIdx] || row[nameIdx] || '',
        description: row[descIdx] || ''
    })).filter(app => !app.name.startsWith('splunk_') && app.name !== 'learned' && app.name !== 'launcher');
    
    // Générer le HTML
    let html = `
        <div class="app-header">
            <div>
                <input type="checkbox" id="select-all" onchange="toggleSelectAll(this.checked)" />
                <label for="select-all" style="cursor: pointer; margin-left: 8px;">Select All</label>
            </div>
            <span class="app-count">${window.availableApps.length} apps</span>
        </div>
    `;
    
    window.availableApps.forEach((app, index) => {
        html += `
            <div class="app-item" id="app-item-${index}" onclick="selectAppForDashboards('${app.name}', ${index}, event)">
                <input type="checkbox" 
                       id="app-${index}" 
                       data-app-id="${app.name}" 
                       data-app-label="${app.label}"
                       onchange="updateSelectedApps(); event.stopPropagation();" 
                       onclick="event.stopPropagation();" />
                <div class="app-info">
                    <div class="app-name">${app.label}</div>
                    <div class="app-technical">${app.name}</div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    
    console.log(`Rendered ${window.availableApps.length} applications`);
}

// ============================================
// GESTION DU PANNEAU DES DASHBOARDS
// ============================================

// App actuellement affichée dans le panneau dashboards
let currentSelectedAppForDashboards = null;

// Structure pour stocker les dashboards sélectionnés par app
// Format: { "app_name": ["dashboard1.xml", "dashboard2.xml"], ... }
let selectedDashboardsByApp = {};

function selectAppForDashboards(appName, index, event) {
    // Ne pas sélectionner si on clique sur la checkbox
    if (event && event.target.type === 'checkbox') return;
    
    // Mettre à jour le style de sélection
    document.querySelectorAll('.app-item').forEach(item => {
        item.classList.remove('selected');
    });
    const appItem = document.getElementById(`app-item-${index}`);
    if (appItem) {
        appItem.classList.add('selected');
    }
    
    currentSelectedAppForDashboards = appName;
    loadDashboardsForApp(appName);
}

async function loadDashboardsForApp(appName) {
    const container = document.getElementById('dashboards-container');
    if (!container) return;
    
    // Afficher le loading
    container.innerHTML = `
        <div class="loading-dashboards">
            <div class="mini-spinner"></div>
            <span>Loading dashboards...</span>
        </div>
    `;
    
    try {
        // Appeler l'API REST pour récupérer les views/dashboards de l'app
        const response = await fetch(`/en-US/splunkd/__raw/services/data/ui/views?output_mode=json&count=0&search=eai:acl.app=${appName}`, {
            credentials: 'include'
        });
        
        if (!response.ok) throw new Error('Failed to load dashboards');
        
        const data = await response.json();
        
        if (data && data.entry && data.entry.length > 0) {
            renderDashboardsList(appName, data.entry);
        } else {
            container.innerHTML = `
                <div class="selected-app-header">
                    <span class="app-name">${appName}</span>
                    <span class="dashboard-count">0 dashboards</span>
                </div>
                <div class="empty-state" style="height: 200px;">
                    <div class="icon">📭</div>
                    <p>No dashboards found</p>
                    <p style="font-size: 12px; color: #888;">This app doesn't contain any views or dashboards</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading dashboards:', error);
        container.innerHTML = `
            <div class="empty-state" style="height: 200px;">
                <div class="icon">⚠️</div>
                <p style="color: #d32f2f;">Error loading dashboards</p>
                <p style="font-size: 12px;">${error.message}</p>
            </div>
        `;
    }
    
    updateSelectionSummary();
}

function renderDashboardsList(appName, dashboards) {
    const container = document.getElementById('dashboards-container');
    if (!container) return;
    
    // Filtrer pour ne garder que les dashboards de cette app
    const appDashboards = dashboards.filter(d => {
        const acl = d.acl || {};
        return acl.app === appName;
    });
    
    // Récupérer les dashboards déjà sélectionnés pour cette app
    const selectedForThisApp = selectedDashboardsByApp[appName] || [];
    
    let html = `
        <div class="selected-app-header">
            <span class="app-name">${appName}</span>
            <span class="dashboard-count">${appDashboards.length} dashboard(s)</span>
        </div>
        <div class="dashboard-actions">
            <button onclick="selectAllDashboards('${appName}', true)">☑️ Select All</button>
            <button onclick="selectAllDashboards('${appName}', false)">☐ Deselect All</button>
        </div>
        <div id="dashboards-list">
    `;
    
    appDashboards.forEach((dashboard, idx) => {
        const name = dashboard.name;
        const label = dashboard.content && dashboard.content.label ? dashboard.content.label : name;
        const isDashboard = dashboard.content && dashboard.content['eai:type'] === 'views';
        const isChecked = selectedForThisApp.includes(name);
        
        html += `
            <div class="dashboard-item">
                <input type="checkbox" 
                       id="dash-${idx}" 
                       data-dashboard-id="${name}"
                       data-app-id="${appName}"
                       ${isChecked ? 'checked' : ''}
                       onchange="updateSelectedDashboards('${appName}')" />
                <div class="dashboard-info">
                    <div class="dashboard-name">${label}</div>
                    <div class="dashboard-file">${name}.xml</div>
                </div>
                <span class="dashboard-type">view</span>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function selectAllDashboards(appName, selectAll) {
    const checkboxes = document.querySelectorAll(`#dashboards-list input[type="checkbox"][data-app-id="${appName}"]`);
    checkboxes.forEach(cb => {
        cb.checked = selectAll;
    });
    updateSelectedDashboards(appName);
}

function updateSelectedDashboards(appName) {
    const checkboxes = document.querySelectorAll(`#dashboards-list input[type="checkbox"][data-app-id="${appName}"]`);
    const selected = [];
    
    checkboxes.forEach(cb => {
        if (cb.checked) {
            selected.push(cb.getAttribute('data-dashboard-id'));
        }
    });
    
    // Mettre à jour la structure
    if (selected.length > 0) {
        selectedDashboardsByApp[appName] = selected;
    } else {
        delete selectedDashboardsByApp[appName];
    }
    
    // Si des dashboards sont sélectionnés, s'assurer que l'app est cochée
    const appCheckbox = document.querySelector(`input[type="checkbox"][data-app-id="${appName}"]`);
    if (appCheckbox && selected.length > 0 && !appCheckbox.checked) {
        appCheckbox.checked = true;
        updateSelectedApps();
    }
    
    updateSelectionSummary();
    console.log('Selected dashboards by app:', selectedDashboardsByApp);
}

function updateSelectionSummary() {
    const summaryContainer = document.getElementById('selection-summary');
    const summaryList = document.getElementById('selection-summary-list');
    
    if (!summaryContainer || !summaryList) return;
    
    const apps = Object.keys(selectedDashboardsByApp);
    
    if (apps.length === 0) {
        summaryContainer.style.display = 'none';
        return;
    }
    
    summaryContainer.style.display = 'block';
    
    let html = '';
    apps.forEach(appName => {
        const dashboards = selectedDashboardsByApp[appName];
        html += `<div class="summary-item"><strong>${appName}</strong>: ${dashboards.length} dashboard(s)</div>`;
    });
    
    summaryList.innerHTML = html;
}

// Fonction pour obtenir la sélection finale (pour le push)
function getSelectedItemsForPush() {
    const result = [];
    
    // Parcourir les apps sélectionnées
    selectedApps.forEach(app => {
        const appName = app.id;
        const selectedDashboards = selectedDashboardsByApp[appName];
        
        if (selectedDashboards && selectedDashboards.length > 0) {
            // Mode sélection fine : seulement les dashboards spécifiés
            result.push({
                app: appName,
                label: app.label,
                mode: 'selective',
                dashboards: selectedDashboards
            });
        } else {
            // Mode app complète : toute l'app
            result.push({
                app: appName,
                label: app.label,
                mode: 'full',
                dashboards: []
            });
        }
    });
    
    return result;
}

// ============================================
// GESTION DE LA SÉLECTION
// ============================================

function updateSelectedApps() {
    const checkboxes = document.querySelectorAll('#dashboard-list input[type="checkbox"][data-app-id]');
    selectedApps = [];
    
    checkboxes.forEach(cb => {
        if (cb.checked) {
            selectedApps.push({
                id: cb.getAttribute('data-app-id'),
                label: cb.getAttribute('data-app-label')
            });
        }
    });
    
    // Mettre à jour le "Select All"
    const selectAll = document.getElementById('select-all');
    if (selectAll) {
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        const someChecked = Array.from(checkboxes).some(cb => cb.checked);
        selectAll.checked = allChecked;
        selectAll.indeterminate = someChecked && !allChecked;
    }
    
    // Mettre à jour la liste des apps pour le SH Cluster
    updateShClusterAppsList();
    
    console.log(`Selected ${selectedApps.length} apps`);
}

function updateShClusterAppsList() {
    const container = document.getElementById('shcluster-apps-container');
    if (!container) return;
    
    if (selectedApps.length === 0) {
        container.innerHTML = '<p style="color: #888; font-style: italic;">Select apps from the left panel first</p>';
        selectedShClusterApps = [];
        return;
    }
    
    // Sauvegarder l'état actuel des checkboxes
    const currentState = {};
    const existingCheckboxes = container.querySelectorAll('input[type="checkbox"][data-app-id]');
    existingCheckboxes.forEach(cb => {
        currentState[cb.getAttribute('data-app-id')] = cb.checked;
    });
    
    // Vérifier si la liste a changé (nouvelles apps ajoutées ou apps retirées)
    const currentAppIds = Array.from(existingCheckboxes).map(cb => cb.getAttribute('data-app-id'));
    const newAppIds = selectedApps.map(app => app.id);
    const listChanged = currentAppIds.length !== newAppIds.length || 
                        !currentAppIds.every(id => newAppIds.includes(id));
    
    // Ne recréer le HTML que si la liste a changé
    if (listChanged || existingCheckboxes.length === 0) {
        let html = '';
        selectedApps.forEach((app, index) => {
            // Préserver l'état si l'app existait, sinon cocher par défaut
            const isChecked = currentState.hasOwnProperty(app.id) ? currentState[app.id] : true;
            html += `
                <div class="shcluster-app-item">
                    <input type="checkbox" 
                           id="shcluster-app-${index}" 
                           data-app-id="${app.id}" 
                           data-app-label="${app.label}"
                           ${isChecked ? 'checked="checked"' : ''}
                           onchange="updateSelectedShClusterApps()" />
                    <label for="shcluster-app-${index}">
                        <span class="app-badge">${app.id}</span>
                        ${app.label !== app.id ? app.label : ''}
                    </label>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    // Mettre à jour la liste des apps SH Cluster sélectionnées (sans recréer le HTML)
    updateSelectedShClusterApps();
}

function updateSelectedShClusterApps() {
    const allAppsCheckbox = document.getElementById('shcluster-all-apps');
    
    if (allAppsCheckbox && allAppsCheckbox.checked) {
        // Toutes les apps sélectionnées pour Git
        selectedShClusterApps = [...selectedApps];
    } else {
        // Seulement les apps cochées dans la liste SH Cluster
        const checkboxes = document.querySelectorAll('#shcluster-apps-container input[type="checkbox"][data-app-id]');
        selectedShClusterApps = [];
        
        checkboxes.forEach(cb => {
            if (cb.checked) {
                selectedShClusterApps.push({
                    id: cb.getAttribute('data-app-id'),
                    label: cb.getAttribute('data-app-label')
                });
            }
        });
    }
    
    console.log(`Selected ${selectedShClusterApps.length} apps for SH Cluster`);
}

function toggleShClusterAllApps() {
    const allAppsCheckbox = document.getElementById('shcluster-all-apps');
    const appsList = document.getElementById('shcluster-apps-list');
    
    if (allAppsCheckbox && appsList) {
        if (allAppsCheckbox.checked) {
            // Masquer la liste et utiliser toutes les apps
            appsList.style.display = 'none';
            selectedShClusterApps = [...selectedApps];
            console.log('SH Cluster: Using all selected apps');
        } else {
            // Afficher la liste pour permettre la sélection manuelle
            appsList.style.display = 'block';
            // Ne PAS appeler updateSelectedShClusterApps() ici
            // L'utilisateur va faire sa sélection manuellement
            // La liste garde son état actuel (tous cochés par défaut)
            console.log('SH Cluster: Manual selection enabled');
        }
    }
}

function toggleSelectAll(checked) {
    const checkboxes = document.querySelectorAll('#dashboard-list input[type="checkbox"][data-app-id]');
    checkboxes.forEach(cb => {
        cb.checked = checked;
    });
    updateSelectedApps();
}

// ============================================
// PUSH VERS GIT
// ============================================

async function pushDashboards() {
    console.log("Starting push process...");
    
    // Vérifier si déjà en cours
    if (isProcessing) {
        console.log("Push already in progress");
        return;
    }
    
    // Vérifier la licence AVANT tout
    if (typeof checkLicenseBeforePush === 'function') {
        const licenseOk = await checkLicenseBeforePush();
        if (!licenseOk) {
            console.log("License check failed");
            return;
        }
    }
    
    // Récupérer les valeurs du formulaire
    let gitUrl = document.getElementById('git-url')?.value?.trim() || '';
    const gitBranch = document.getElementById('git-branch')?.value?.trim() || 'main';
    const gitToken = document.getElementById('git-token')?.value?.trim() || '';
    const commitMessage = document.getElementById('commit-message')?.value?.trim() || '';
    const saveCredentials = document.getElementById('save-credentials')?.checked;
    
    // Nettoyer l'URL Git (supprimer guillemets et slash final)
    gitUrl = gitUrl.replace(/^['"]|['"]$/g, '').replace(/\/+$/, '');
    
    // Ne PAS rappeler updateSelectedApps() ici car cela réinitialiserait la liste SH Cluster
    // La liste selectedApps est déjà à jour grâce aux événements onchange
    
    // Validation
    if (!gitUrl) {
        showMessage('error', 'Please enter a Git repository URL');
        return;
    }
    
    if (!gitToken) {
        showMessage('error', 'Please enter a Git token or password');
        return;
    }
    
    if (!commitMessage) {
        showMessage('error', 'Please enter a commit message');
        return;
    }
    
    if (selectedApps.length === 0) {
        showMessage('error', 'Please select at least one application to deploy');
        return;
    }
    
    // Sauvegarder les credentials si demandé
    if (saveCredentials) {
        saveCredentialsToStorage(gitUrl, gitBranch, gitToken);
    }
    
    // Vérifier si le déploiement vers SH Cluster est activé
    let deployToSHCluster = document.getElementById('deploy-to-shcluster')?.checked || false;
    
    // Sécurité : vérifier que la branche est autorisée pour SH Cluster
    if (deployToSHCluster && !isShClusterBranchAllowed()) {
        console.warn('SH Cluster deployment blocked: branch not allowed');
        deployToSHCluster = false;
        showMessage('error', `SH Cluster deployment is only available on main/master branch. Current branch: ${gitBranch}`);
        return;
    }
    
    // La liste selectedShClusterApps est déjà à jour via les événements onchange
    // Ne pas rappeler updateSelectedShClusterApps() pour éviter de réinitialiser la sélection
    
    // Validation des apps SH Cluster si déploiement activé
    if (deployToSHCluster && selectedShClusterApps.length === 0) {
        showMessage('error', 'Please select at least one application to deploy to SH Cluster');
        return;
    }
    
    // Démarrer le push
    isProcessing = true;
    showLoading(true, deployToSHCluster);
    hideMessages();
    
    try {
        // Récupérer l'utilisateur courant
        const currentUser = await getCurrentUser();
        
        // Récupérer les infos de licence depuis le localStorage
        const licenseInfo = getLicenseInfo ? getLicenseInfo() : null;
        const licenseType = licenseInfo?.type_name || '';
        const licenseId = licenseInfo?.license_id || '';
        
        // Récupérer la sélection détaillée (apps + dashboards)
        const selectionDetails = getSelectedItemsForPush();

        // Construire les paramètres. Envoyés dans le corps JSON de la requête (jamais dans
        // l'URL) car ils contiennent des secrets (git_token, deployer_token) qui ne doivent
        // pas se retrouver dans les logs d'accès d'un proxy ou dans l'historique du navigateur.
        const payload = {
            git_url: gitUrl,
            git_branch: gitBranch,
            git_token: gitToken,
            commit_message: commitMessage,
            apps: selectedApps,
            selection_details: selectionDetails,  // Détails avec dashboards
            dashboards_by_app: selectedDashboardsByApp,  // Dashboards par app
            shcluster_apps: selectedShClusterApps,  // Apps pour le SH Cluster
            user: currentUser,
            deploy_to_shcluster: deployToSHCluster.toString(),
            deployer_host: SH_DEPLOYER_CONFIG.host,
            deployer_token: SH_DEPLOYER_CONFIG.token,
            license_type: licenseType,
            license_id: licenseId
        };

        console.log(`Pushing ${selectedApps.length} apps to Git${deployToSHCluster ? `, ${selectedShClusterApps.length} apps to SH Cluster` : ''}`);

        // Appeler le serveur
        const response = await fetch(`${GITDEPLOY_CONFIG.serverUrl}/push`, {
            method: 'POST',
            headers: apiAuthHeaders({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        console.log("Push result:", result);
        
        if (result.status === 'success') {
            // Incrémenter le compteur d'utilisation côté client
            console.log("=== INCREMENT USAGE ===");
            console.log("typeof incrementUsage:", typeof incrementUsage);
            console.log("typeof window.incrementUsage:", typeof window.incrementUsage);
            
            try {
                if (typeof window.incrementUsage === 'function') {
                    const stats = window.incrementUsage();
                    console.log("✓ Usage incremented successfully:", stats);
                } else if (typeof incrementUsage === 'function') {
                    const stats = incrementUsage();
                    console.log("✓ Usage incremented (local):", stats);
                } else {
                    console.warn("✗ incrementUsage function not available");
                }
            } catch (e) {
                console.error("✗ Error incrementing usage:", e);
            }
            
            let message = `✅ Successfully deployed ${result.apps_pushed || selectedApps.length} application(s) to Git!`;
            
            // Ajouter le statut du déploiement SH Cluster
            if (deployToSHCluster && result.shcluster_deployment) {
                if (result.shcluster_deployment.success) {
                    message += '\n🚀 SH Cluster deployment triggered successfully!';
                } else {
                    message += `\n⚠️ SH Cluster deployment failed: ${result.shcluster_deployment.message}`;
                }
            }
            
            showMessage('success', message);
            
            // Reset la sélection après succès
            setTimeout(() => {
                toggleSelectAll(false);
            }, 2000);
        } else if (result.error_code === 'UNAUTHORIZED') {
            showMessage('error', '🔒 Authentication failed: missing or invalid API token. Set the correct API token on the Configuration page.');
        } else if (result.error_code === 'LICENSE_ERROR') {
            showMessage('error', `🔐 ${result.message}`);
            
            // Afficher le modal de licence
            if (typeof showLicenseModal === 'function') {
                showLicenseModal(result.message, result.error_code);
            }
        } else if (result.error_code === 'APP_LIMIT') {
            showMessage('error', `📦 ${result.message}`);
        } else {
            showMessage('error', result.message || 'Unknown error occurred');
        }
        
    } catch (error) {
        console.error("Push error:", error);
        showMessage('error', `Connection error: ${error.message}. Is the GitDeploy for Splunk server running?`);
    } finally {
        isProcessing = false;
        showLoading(false);
    }
}

// ============================================
// UTILITAIRES UI
// ============================================

function showLoading(show, deployToSHCluster = false) {
    const loading = document.getElementById('loading');
    const pushBtn = document.getElementById('push-btn');
    const loadingText = document.querySelector('.loading-text');
    
    if (loading) {
        loading.classList.toggle('active', show);
    }
    
    if (loadingText && show) {
        if (deployToSHCluster) {
            loadingText.textContent = 'Deploying to Git and SH Cluster... Please wait';
        } else {
            loadingText.textContent = 'Deploying applications to Git... Please wait';
        }
    }
    
    if (pushBtn) {
        pushBtn.disabled = show;
        if (show) {
            pushBtn.textContent = deployToSHCluster ? '⏳ Deploying to Git + SH...' : '⏳ Deploying...';
        } else {
            pushBtn.textContent = '✈️ Deploy to Git';
        }
    }
}

function showMessage(type, text) {
    hideMessages();
    
    const successMsg = document.getElementById('success-msg');
    const errorMsg = document.getElementById('error-msg');
    const successText = document.getElementById('success-text');
    const errorText = document.getElementById('error-text');
    
    if (type === 'success' && successMsg && successText) {
        successText.textContent = text;
        successMsg.classList.add('active');
        
        // Auto-hide après 5 secondes
        setTimeout(() => {
            successMsg.classList.remove('active');
        }, 5000);
    } else if (type === 'error' && errorMsg && errorText) {
        errorText.textContent = text;
        errorMsg.classList.add('active');
    }
}

function hideMessages() {
    const successMsg = document.getElementById('success-msg');
    const errorMsg = document.getElementById('error-msg');
    
    if (successMsg) successMsg.classList.remove('active');
    if (errorMsg) errorMsg.classList.remove('active');
}

function resetForm(clearCredentials = false) {
    // Reset les champs
    const commitMessage = document.getElementById('commit-message');
    if (commitMessage) commitMessage.value = '';
    
    if (clearCredentials) {
        const gitUrl = document.getElementById('git-url');
        const gitToken = document.getElementById('git-token');
        const saveCredentials = document.getElementById('save-credentials');
        
        if (gitUrl) gitUrl.value = '';
        if (gitToken) gitToken.value = '';
        if (saveCredentials) saveCredentials.checked = false;
        
        // Supprimer les credentials sauvegardés
        localStorage.removeItem(GITDEPLOY_CONFIG.credentialsKey);
    }
    
    // Reset la sélection
    toggleSelectAll(false);
    
    // Cacher les messages
    hideMessages();
    
    console.log("Form reset" + (clearCredentials ? " (with credentials)" : ""));
}

// ============================================
// GESTION DES CREDENTIALS
// ============================================

function saveCredentialsToStorage(gitUrl, gitBranch, gitToken) {
    try {
        const credentials = {
            gitUrl: gitUrl,
            gitBranch: gitBranch,
            // Note: En production, envisager une solution plus sécurisée
            gitToken: btoa(gitToken), // Encodage basique (pas sécurisé, juste pour l'obfuscation)
            savedAt: new Date().toISOString()
        };
        
        localStorage.setItem(GITDEPLOY_CONFIG.credentialsKey, JSON.stringify(credentials));
        console.log("Credentials saved");
    } catch (error) {
        console.error("Error saving credentials:", error);
    }
}

function loadSavedCredentials() {
    try {
        const saved = localStorage.getItem(GITDEPLOY_CONFIG.credentialsKey);
        if (!saved) return;
        
        const credentials = JSON.parse(saved);
        
        const gitUrl = document.getElementById('git-url');
        const gitBranch = document.getElementById('git-branch');
        const gitToken = document.getElementById('git-token');
        const saveCredentials = document.getElementById('save-credentials');
        
        if (gitUrl && credentials.gitUrl) {
            gitUrl.value = credentials.gitUrl;
        }
        
        if (gitBranch && credentials.gitBranch) {
            gitBranch.value = credentials.gitBranch;
        }
        
        if (gitToken && credentials.gitToken) {
            gitToken.value = atob(credentials.gitToken);
        }
        
        if (saveCredentials) {
            saveCredentials.checked = true;
        }
        
        console.log("Credentials loaded from storage");
    } catch (error) {
        console.error("Error loading credentials:", error);
    }
}

// ============================================
// RÉCUPÉRATION DE L'UTILISATEUR SPLUNK
// ============================================

async function getCurrentUser() {
    try {
        const response = await fetch('/en-US/splunkd/__raw/services/authentication/current-context?output_mode=json');
        const data = await response.json();
        return data.entry?.[0]?.content?.username || 'unknown';
    } catch (error) {
        console.error("Error getting current user:", error);
        return 'unknown';
    }
}

// ============================================
// VÉRIFICATION DU SERVEUR
// ============================================

async function checkServerHealth() {
    try {
        const response = await fetch(`${GITDEPLOY_CONFIG.serverUrl}/health`, {
            method: 'GET',
            timeout: 5000
        });
        const data = await response.json();
        return data.status === 'ok';
    } catch (error) {
        console.error("Server health check failed:", error);
        return false;
    }
}

// ============================================
// SH DEPLOYER FUNCTIONS
// ============================================

async function checkDeployerHealth() {
    try {
        const response = await fetch(`${GITDEPLOY_CONFIG.serverUrl}/deployer/health`, {
            method: 'GET',
            timeout: 5000
        });
        const data = await response.json();
        
        deployerAvailable = data.status === 'ok';
        
        // Mettre à jour l'UI
        updateDeployerUI();
        
        console.log("SH Deployer status:", deployerAvailable ? "Available" : "Unavailable");
        return deployerAvailable;
    } catch (error) {
        console.error("Deployer health check failed:", error);
        deployerAvailable = false;
        updateDeployerUI();
        return false;
    }
}

function updateDeployerUI() {
    const deployerCheckbox = document.getElementById('deploy-to-shcluster');
    const deployerStatus = document.getElementById('deployer-status');
    const deployerSection = document.getElementById('deployer-section');
    
    if (deployerCheckbox) {
        deployerCheckbox.disabled = !deployerAvailable;
    }
    
    if (deployerStatus) {
        if (deployerAvailable) {
            deployerStatus.innerHTML = '<span style="color: #4CAF50;">● Connected</span>';
        } else {
            deployerStatus.innerHTML = '<span style="color: #f44336;">● Disconnected</span>';
        }
    }
    
    if (deployerSection && !deployerAvailable) {
        deployerSection.style.opacity = '0.6';
    }
}

function loadDeployerConfig() {
    try {
        const saved = localStorage.getItem(GITDEPLOY_CONFIG.deployerConfigKey);
        if (saved) {
            const config = JSON.parse(saved);
            SH_DEPLOYER_CONFIG = { ...SH_DEPLOYER_CONFIG, ...config };
            console.log("Deployer config loaded");
        }
    } catch (error) {
        console.error("Error loading deployer config:", error);
    }
}

function saveDeployerConfig() {
    try {
        localStorage.setItem(GITDEPLOY_CONFIG.deployerConfigKey, JSON.stringify(SH_DEPLOYER_CONFIG));
        console.log("Deployer config saved");
    } catch (error) {
        console.error("Error saving deployer config:", error);
    }
}

// Vérifier la santé du serveur au démarrage
setTimeout(async () => {
    const healthy = await checkServerHealth();
    if (!healthy) {
        console.warn("GitDeploy for Splunk server may not be running");
    } else {
        console.log("GitDeploy for Splunk server is healthy");
    }
}, 1000);

// ============================================
// EXPORT FONCTIONS GLOBALES
// ============================================

// Exposer les fonctions principales
window.pushDashboards = pushDashboards;
window.resetForm = resetForm;
window.toggleSelectAll = toggleSelectAll;
window.updateSelectedApps = updateSelectedApps;

// Fonction toggle pour le HTML (appelle la vraie fonction)
window.toggleDeployerAuth = toggleDeployerOptions;

// ============================================
// ATTACHEMENT DES ÉVÉNEMENTS AUX BOUTONS
// ============================================

(function attachButtonEvents() {
    function tryAttach() {
        console.log("Trying to attach button events...");
        
        // Bouton Deploy to Git
        var pushBtn = document.getElementById('push-btn');
        if (pushBtn) {
            // Supprimer les anciens listeners
            pushBtn.replaceWith(pushBtn.cloneNode(true));
            pushBtn = document.getElementById('push-btn');
            
            pushBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log("Deploy button clicked!");
                pushDashboards();
            });
            console.log("✓ Deploy button event attached");
        } else {
            console.log("✗ Deploy button not found yet");
        }
        
        // Bouton Reset - chercher par classe ou contenu
        var buttons = document.querySelectorAll('button.btn, button.btn-secondary');
        buttons.forEach(function(btn) {
            if (btn.textContent.includes('Reset') || btn.textContent.includes('🔄')) {
                // Supprimer les anciens listeners
                var newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
                
                newBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log("Reset button clicked!");
                    resetForm(true);
                });
                console.log("✓ Reset button event attached");
            }
        });
        
        // Checkbox deploy to shcluster
        var deployCheckbox = document.getElementById('deploy-to-shcluster');
        if (deployCheckbox) {
            deployCheckbox.addEventListener('change', function() {
                toggleDeployerOptions();
            });
            console.log("✓ Deploy checkbox event attached");
        }
        
        // Si le bouton principal n'est pas encore là, réessayer
        if (!pushBtn) {
            console.log("Retrying in 500ms...");
            setTimeout(tryAttach, 500);
        } else {
            console.log("=== All button events attached successfully ===");
        }
    }
    
    // Démarrer après un délai pour laisser le DOM se charger
    if (document.readyState === 'complete') {
        console.log("Document ready, attaching events in 1s...");
        setTimeout(tryAttach, 1000);
    } else {
        window.addEventListener('load', function() {
            console.log("Window loaded, attaching events in 1s...");
            setTimeout(tryAttach, 1000);
        });
    }
})();

// ============================================
// EXPORT POUR DEBUG
// ============================================

window.GitPusher = {
    config: GITDEPLOY_CONFIG,
    deployerConfig: SH_DEPLOYER_CONFIG,
    getSelectedApps: () => selectedApps,
    checkServer: checkServerHealth,
    checkDeployer: checkDeployerHealth,
    version: GITDEPLOY_CONFIG.version
};
