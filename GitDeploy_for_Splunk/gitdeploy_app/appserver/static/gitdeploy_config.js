// ============================================
// GIT PUSHER - CONFIGURATION PAGE
// Version 2.1 - Compatible Splunk
// ============================================

require([
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/simplexml/ready!'
], function($, mvc) {
    
    console.log('GitDeploy for Splunk Config v2.1 initializing...');
    
    // Configuration par défaut
    var DEFAULT_CONFIG = {
        api: {
            url: '',
            port: 9999,
            useProxy: true,
            token: ''
        },
        deployer: {
            enabled: false,
            host: '',
            port: 9998,
            token: '',
            useSSL: true
        },
        license: {
            checkInterval: 24
        },
        advanced: {
            logLevel: 'INFO',
            timeout: 30,
            gitTimeout: 120
        }
    };
    
    // URL de l'API pour la config
    function getConfigApiUrl() {
        var hostname = window.location.hostname;
        var protocol = window.location.protocol;
        
        // Essayer de charger depuis localStorage
        try {
            var stored = localStorage.getItem('gitdeploy_config');
            if (stored) {
                var config = JSON.parse(stored);
                if (config.api && config.api.url) {
                    var url = config.api.url;
                    if (!config.api.useProxy && config.api.port) {
                        url = url.replace(/\/$/, '') + ':' + config.api.port;
                    }
                    return url;
                }
            }
        } catch(e) {}
        
        // Auto-détection
        if (/^(\d{1,3}\.){3}\d{1,3}$/.test(hostname) || hostname === 'localhost') {
            return protocol + '//' + hostname + ':9999';
        }
        return protocol + '//' + hostname + ':9999';
    }
    
    // ============================================
    // CHARGEMENT DE LA CONFIGURATION
    // ============================================
    
    function loadConfig() {
        console.log('Loading configuration...');
        var apiUrl = getConfigApiUrl();

        $.ajax({
            url: apiUrl + '/config',
            method: 'GET',
            dataType: 'json',
            success: function(config) {
                console.log('Config loaded:', config);
                applyConfigToForm(config);
                showMessage('Configuration chargée', 'success');
            },
            error: function(xhr, status, error) {
                console.log('No server config, using defaults:', error);
                applyConfigToForm(DEFAULT_CONFIG);
            }
        });

        loadLicenseStatus();
    }

    function applyConfigToForm(config) {
        // API
        $('#api-url').val(config.api ? config.api.url || '' : '');
        $('#api-port').val(config.api ? config.api.port || 9999 : 9999);
        $('#use-proxy').prop('checked', config.api ? config.api.useProxy !== false : true);

        // Le serveur masque le token API réel ('***') : on ne l'affiche que s'il vient du
        // localStorage local (jamais transmis en clair par le serveur).
        var apiToken = config.api ? config.api.token || '' : '';
        if (apiToken && apiToken !== '***') {
            $('#api-token').val(apiToken);
        } else {
            try {
                var stored = JSON.parse(localStorage.getItem('gitdeploy_config') || '{}');
                $('#api-token').val((stored.api && stored.api.token) || '');
            } catch (e) {
                $('#api-token').val('');
            }
        }

        // Deployer
        $('#deployer-enabled').prop('checked', config.deployer ? config.deployer.enabled || false : false);
        $('#deployer-host').val(config.deployer ? config.deployer.host || '' : '');
        $('#deployer-port').val(config.deployer ? config.deployer.port || 9998 : 9998);
        $('#deployer-token').val(config.deployer ? config.deployer.token || '' : '');
        $('#deployer-use-ssl').prop('checked', config.deployer ? config.deployer.useSSL !== false : true);
        
        // Licence
        $('#license-check-interval').val(config.license ? config.license.checkInterval || 24 : 24);
        
        // Avancé
        $('#log-level').val(config.advanced ? config.advanced.logLevel || 'INFO' : 'INFO');
        $('#timeout').val(config.advanced ? config.advanced.timeout || 30 : 30);
        $('#git-timeout').val(config.advanced ? config.advanced.gitTimeout || 120 : 120);
    }
    
    function getConfigFromForm() {
        return {
            api: {
                url: $('#api-url').val().trim(),
                port: parseInt($('#api-port').val()) || 9999,
                useProxy: $('#use-proxy').is(':checked'),
                token: $('#api-token').val()
            },
            deployer: {
                enabled: $('#deployer-enabled').is(':checked'),
                host: $('#deployer-host').val().trim(),
                port: parseInt($('#deployer-port').val()) || 9998,
                token: $('#deployer-token').val(),
                useSSL: $('#deployer-use-ssl').is(':checked')
            },
            license: {
                checkInterval: parseInt($('#license-check-interval').val()) || 24
            },
            advanced: {
                logLevel: $('#log-level').val(),
                timeout: parseInt($('#timeout').val()) || 30,
                gitTimeout: parseInt($('#git-timeout').val()) || 120
            }
        };
    }
    
    // ============================================
    // SAUVEGARDE DE LA CONFIGURATION
    // ============================================
    
    function saveConfig() {
        console.log('Saving configuration...');
        var config = getConfigFromForm();
        var apiUrl = getConfigApiUrl();

        $.ajax({
            url: apiUrl + '/config',
            method: 'POST',
            contentType: 'application/json',
            headers: {
                // Le serveur exige ce token pour tout POST. Il doit correspondre au token déjà
                // configuré côté serveur (affiché dans ses logs au premier démarrage) : pour la
                // toute première sauvegarde, saisissez ce token ici avant de cliquer Sauvegarder.
                'X-Auth-Token': config.api.token
            },
            data: JSON.stringify(config),
            dataType: 'json',
            success: function(result) {
                console.log('Save result:', result);
                if (result.success) {
                    showMessage('✅ Configuration sauvegardée avec succès !', 'success');
                    // Sauvegarder aussi dans localStorage
                    localStorage.setItem('gitdeploy_config', JSON.stringify(config));
                } else {
                    showMessage('❌ Erreur: ' + (result.error || 'Échec de la sauvegarde'), 'error');
                }
            },
            error: function(xhr, status, error) {
                console.error('Save error:', error);
                if (xhr.status === 401) {
                    showMessage('❌ Token API invalide ou manquant. Vérifiez la valeur du champ "Token API" (voir les logs du serveur pour le token généré au démarrage).', 'error');
                } else {
                    showMessage('❌ Erreur de connexion au serveur: ' + error, 'error');
                }
            }
        });
    }
    
    function resetConfig() {
        if (confirm('Voulez-vous vraiment réinitialiser la configuration ?')) {
            applyConfigToForm(DEFAULT_CONFIG);
            showMessage('Configuration réinitialisée (non sauvegardée)', 'success');
        }
    }
    
    // ============================================
    // TESTS DE CONNEXION
    // ============================================
    
    function testApiConnection() {
        console.log('Testing API connection...');
        var $status = $('#api-status');
        $status.removeClass('connected disconnected').text('● Test en cours...');
        
        var apiUrl = $('#api-url').val().trim();
        
        if (!apiUrl) {
            apiUrl = getConfigApiUrl();
        } else if (!$('#use-proxy').is(':checked')) {
            var port = $('#api-port').val() || 9999;
            if (apiUrl.indexOf(':' + port) === -1) {
                apiUrl = apiUrl.replace(/\/$/, '') + ':' + port;
            }
        }
        
        console.log('Testing URL:', apiUrl);
        
        $.ajax({
            url: apiUrl + '/health',
            method: 'GET',
            dataType: 'json',
            timeout: 10000,
            success: function(data) {
                console.log('API health:', data);
                $status.addClass('connected').text('● Connecté');
            },
            error: function(xhr, status, error) {
                console.error('API test failed:', error);
                $status.addClass('disconnected').text('● Échec connexion');
            }
        });
    }
    
    function testDeployerConnection() {
        console.log('Testing Deployer connection...');
        var $status = $('#deployer-status');
        $status.removeClass('connected disconnected').text('● Test en cours...');
        
        var host = $('#deployer-host').val().trim();
        var port = $('#deployer-port').val() || 9998;
        var useSSL = $('#deployer-use-ssl').is(':checked');
        var token = $('#deployer-token').val();
        
        if (!host) {
            $status.addClass('disconnected').text('● Adresse manquante');
            return;
        }
        
        var protocol = useSSL ? 'https' : 'http';
        var url;
        
        // Si c'est un nom de domaine (contient des lettres et des points, pas une IP)
        // Ne pas ajouter le port (le proxy gère)
        if (/^[a-zA-Z]/.test(host) && host.indexOf('.') > -1 && !/^(\d{1,3}\.){3}\d{1,3}$/.test(host)) {
            // C'est un domaine, pas de port
            url = protocol + '://' + host + '/health';
        } else {
            // C'est une IP ou localhost, ajouter le port
            url = protocol + '://' + host + ':' + port + '/health';
        }
        
        console.log('Testing Deployer URL:', url);
        
        $.ajax({
            url: url,
            method: 'GET',
            dataType: 'json',
            timeout: 10000,
            headers: {
                'X-Auth-Token': token
            },
            success: function(data) {
                console.log('Deployer health:', data);
                $status.addClass('connected').text('● Connecté');
            },
            error: function(xhr, status, error) {
                console.error('Deployer test failed:', error);
                $status.addClass('disconnected').text('● Échec connexion');
            }
        });
    }
    
    // ============================================
    // STATUT DE LA LICENCE
    // ============================================
    
    function loadLicenseStatus() {
        var $status = $('#license-status');
        
        try {
            var stored = localStorage.getItem('gitdeploy_license');
            
            if (stored) {
                var parsed = JSON.parse(stored);
                var licenseData = parsed.licenseData;
                
                if (licenseData) {
                    var expires = new Date(licenseData.expires);
                    var now = new Date();
                    var daysRemaining = Math.ceil((expires - now) / (1000 * 60 * 60 * 24));
                    
                    if (daysRemaining > 0) {
                        $status.html(
                            '<span class="config-status connected">● Active</span>' +
                            '<br><small>Type: ' + licenseData.type_name + ' | Expire: ' + licenseData.expires + ' (' + daysRemaining + 'j)</small>'
                        );
                    } else {
                        $status.html(
                            '<span class="config-status disconnected">● Expirée</span>' +
                            '<br><small>Expirée le ' + licenseData.expires + '</small>'
                        );
                    }
                    return;
                }
            }
            
            $status.html('<span class="config-status disconnected">● Non installée</span>');
            
        } catch (error) {
            console.error('Erreur lecture licence:', error);
            $status.html('<span class="config-status disconnected">● Erreur</span>');
        }
    }
    
    // ============================================
    // UTILITAIRES
    // ============================================
    
    function showMessage(message, type) {
        var $msg = $('#config-message');
        $msg.text(message).removeClass('success error').addClass(type).show();
        
        setTimeout(function() {
            $msg.fadeOut();
        }, 5000);
    }
    
    // ============================================
    // ATTACHER LES ÉVÉNEMENTS
    // ============================================
    
    function attachEvents() {
        console.log('Attaching events...');
        
        // Bouton Test API
        $('#test-api-btn').on('click', function(e) {
            e.preventDefault();
            console.log('Test API clicked');
            testApiConnection();
        });
        
        // Bouton Test Deployer
        $('#test-deployer-btn').on('click', function(e) {
            e.preventDefault();
            console.log('Test Deployer clicked');
            testDeployerConnection();
        });
        
        // Bouton Sauvegarder
        $('#save-btn').on('click', function(e) {
            e.preventDefault();
            console.log('Save clicked');
            saveConfig();
        });
        
        // Bouton Réinitialiser
        $('#reset-btn').on('click', function(e) {
            e.preventDefault();
            console.log('Reset clicked');
            resetConfig();
        });
        
        console.log('Events attached to buttons');
    }
    
    // ============================================
    // INITIALISATION
    // ============================================
    
    // Attendre que le DOM soit complètement prêt
    function init() {
        if ($('#api-url').length > 0) {
            console.log('DOM ready, initializing...');
            attachEvents();
            loadConfig();
        } else {
            console.log('DOM not ready, retrying...');
            setTimeout(init, 300);
        }
    }
    
    setTimeout(init, 500);
    
    // Exposer globalement pour le debug
    window.gitPusherConfig = {
        saveConfig: saveConfig,
        resetConfig: resetConfig,
        testApiConnection: testApiConnection,
        testDeployerConnection: testDeployerConnection,
        loadConfig: loadConfig
    };
    
    console.log('GitDeploy for Splunk Config module loaded');
});
