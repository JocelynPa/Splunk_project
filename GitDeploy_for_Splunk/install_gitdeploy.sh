#!/bin/bash
# ============================================
# GitDeploy for Splunk - Script d'installation
# Serveur Splunk Source
# ============================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration par défaut
SPLUNK_HOME="${SPLUNK_HOME:-/opt/splunk}"
APP_NAME="gitdeploy_app"
APP_PATH="${SPLUNK_HOME}/etc/apps/${APP_NAME}"
GIT_TEMP_DIR="/opt/splunk_git_temp"
SERVICE_PORT=9999

# Banner
echo -e "${PURPLE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║     🚀 GitDeploy for Splunk - Installation Script                   ║"
echo "║                                                            ║"
echo "║     Version: 2.1                                          ║"
echo "║     Serveur: Source (Push to Git)                         ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Fonctions utilitaires
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Vérifications préliminaires
check_prerequisites() {
    echo ""
    echo -e "${PURPLE}=== Vérification des prérequis ===${NC}"
    echo ""
    
    # Vérifier si root ou splunk
    if [[ $EUID -ne 0 ]] && [[ $(whoami) != "splunk" ]]; then
        log_warning "Ce script devrait être exécuté en tant que root ou splunk"
        read -p "Continuer quand même ? (o/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Oo]$ ]]; then
            exit 1
        fi
    fi
    
    # Vérifier Splunk
    if [[ ! -d "$SPLUNK_HOME" ]]; then
        log_error "Splunk non trouvé dans $SPLUNK_HOME"
        read -p "Entrez le chemin Splunk: " SPLUNK_HOME
        APP_PATH="${SPLUNK_HOME}/etc/apps/${APP_NAME}"
    fi
    log_success "Splunk trouvé: $SPLUNK_HOME"
    
    # Vérifier Git
    if ! command -v git &> /dev/null; then
        log_error "Git n'est pas installé"
        echo "Installez Git avec: yum install git (RHEL/CentOS) ou apt install git (Debian/Ubuntu)"
        exit 1
    fi
    log_success "Git installé: $(git --version)"
    
    # Vérifier Python
    PYTHON_CMD=""
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python n'est pas installé"
        exit 1
    fi
    log_success "Python installé: $($PYTHON_CMD --version)"
}

# Créer la structure de l'application
create_app_structure() {
    echo ""
    echo -e "${PURPLE}=== Création de la structure de l'application ===${NC}"
    echo ""
    
    # Créer les dossiers
    mkdir -p "${APP_PATH}/bin"
    mkdir -p "${APP_PATH}/default/data/ui/views"
    mkdir -p "${APP_PATH}/appserver/static"
    mkdir -p "${APP_PATH}/local/certs"
    mkdir -p "${APP_PATH}/local"
    
    log_success "Structure créée: ${APP_PATH}"
    
    # Créer le dossier temporaire Git
    mkdir -p "${GIT_TEMP_DIR}"
    log_success "Dossier Git temp créé: ${GIT_TEMP_DIR}"
}

# Copier les fichiers
copy_files() {
    echo ""
    echo -e "${PURPLE}=== Copie des fichiers ===${NC}"
    echo ""
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Déterminer le dossier source des fichiers
    # Si on est dans gitdeploy_distribution/, chercher dans gitdeploy_app/
    if [[ -d "${SCRIPT_DIR}/gitdeploy_app" ]]; then
        SOURCE_DIR="${SCRIPT_DIR}/gitdeploy_app"
    else
        # Sinon, on suppose que les fichiers sont à côté du script
        SOURCE_DIR="${SCRIPT_DIR}"
    fi
    
    log_info "Dossier source: ${SOURCE_DIR}"
    
    # Créer les dossiers supplémentaires
    mkdir -p "${APP_PATH}/default/data/ui/nav"
    mkdir -p "${APP_PATH}/default/data/ui/views"
    mkdir -p "${APP_PATH}/metadata"
    mkdir -p "${APP_PATH}/appserver/static"
    mkdir -p "${APP_PATH}/bin"
    mkdir -p "${APP_PATH}/static"
    
    # Copier les fichiers depuis la structure de distribution
    # bin/
    if [[ -f "${SOURCE_DIR}/bin/gitdeploy.py" ]]; then
        cp "${SOURCE_DIR}/bin/gitdeploy.py" "${APP_PATH}/bin/"
        log_success "Copié: gitdeploy.py → bin/"
    else
        log_warning "Fichier non trouvé: bin/gitdeploy.py"
    fi
    
    if [[ -f "${SOURCE_DIR}/bin/start_gitdeploy.sh" ]]; then
        cp "${SOURCE_DIR}/bin/start_gitdeploy.sh" "${APP_PATH}/bin/"
        chmod +x "${APP_PATH}/bin/start_gitdeploy.sh"
        log_success "Copié: start_gitdeploy.sh → bin/"
        START_SCRIPT_COPIED=true
    else
        START_SCRIPT_COPIED=false
    fi
    
    # appserver/static/
    for file in gitdeploy.js gitdeploy_config.js license_validation.js; do
        if [[ -f "${SOURCE_DIR}/appserver/static/${file}" ]]; then
            cp "${SOURCE_DIR}/appserver/static/${file}" "${APP_PATH}/appserver/static/"
            log_success "Copié: ${file} → appserver/static/"
        else
            log_warning "Fichier non trouvé: appserver/static/${file}"
        fi
    done
    
    # default/
    if [[ -f "${SOURCE_DIR}/default/app.conf" ]]; then
        cp "${SOURCE_DIR}/default/app.conf" "${APP_PATH}/default/"
        log_success "Copié: app.conf → default/"
    fi
    
    # default/data/ui/views/
    for file in gitdeploy_dashboard.xml gitdeploy_config.xml; do
        if [[ -f "${SOURCE_DIR}/default/data/ui/views/${file}" ]]; then
            cp "${SOURCE_DIR}/default/data/ui/views/${file}" "${APP_PATH}/default/data/ui/views/"
            log_success "Copié: ${file} → default/data/ui/views/"
        else
            log_warning "Fichier non trouvé: default/data/ui/views/${file}"
        fi
    done
    
    # default/data/ui/nav/
    if [[ -f "${SOURCE_DIR}/default/data/ui/nav/default.xml" ]]; then
        cp "${SOURCE_DIR}/default/data/ui/nav/default.xml" "${APP_PATH}/default/data/ui/nav/"
        log_success "Copié: default.xml → default/data/ui/nav/"
    else
        log_warning "Fichier non trouvé: default/data/ui/nav/default.xml"
    fi
    
    # metadata/
    if [[ -f "${SOURCE_DIR}/metadata/default.meta" ]]; then
        cp "${SOURCE_DIR}/metadata/default.meta" "${APP_PATH}/metadata/"
        log_success "Copié: default.meta → metadata/"
    else
        log_warning "Fichier non trouvé: metadata/default.meta"
    fi
    
    # static/ (icônes)
    if [[ -f "${SOURCE_DIR}/static/appIcon.png" ]]; then
        cp "${SOURCE_DIR}/static/appIcon.png" "${APP_PATH}/static/"
        log_success "Copié: appIcon.png → static/"
    fi
    if [[ -f "${SOURCE_DIR}/static/appIcon_2x.png" ]]; then
        cp "${SOURCE_DIR}/static/appIcon_2x.png" "${APP_PATH}/static/"
        log_success "Copié: appIcon_2x.png → static/"
    fi
}

# Créer app.conf
create_app_conf() {
    echo ""
    echo -e "${PURPLE}=== Création de app.conf ===${NC}"
    echo ""
    
    cat > "${APP_PATH}/default/app.conf" << 'EOF'
[install]
is_configured = true
build = 1

[ui]
is_visible = true
label = GitDeploy for Splunk

[launcher]
author = Splunk Admin
description = Push Splunk apps to Git and deploy to Search Head Cluster
version = 2.1.0

[package]
id = gitdeploy_app
check_for_updates = false
EOF

    log_success "app.conf créé"
}

# Créer le script de démarrage
create_start_script() {
    echo ""
    echo -e "${PURPLE}=== Création du script de démarrage ===${NC}"
    echo ""

    # Si start_gitdeploy.sh a déjà été copié depuis la distribution (cas normal), ne pas le
    # remplacer par une version générée ici : garder une seule version du script, à jour.
    if [[ "${START_SCRIPT_COPIED:-false}" == "true" ]]; then
        log_success "start_gitdeploy.sh déjà en place (copié depuis la distribution), pas de régénération"
        return 0
    fi

    cat > "${APP_PATH}/bin/start_gitdeploy.sh" << EOF
#!/bin/bash
# GitDeploy for Splunk - Script de démarrage/arrêt

SPLUNK_HOME="${SPLUNK_HOME}"
APP_PATH="${APP_PATH}"
PID_FILE="${APP_PATH}/local/gitdeploy.pid"
LOG_FILE="${SPLUNK_HOME}/var/log/splunk/gitdeploy.log"
PYTHON_CMD="${PYTHON_CMD:-python3}"

start() {
    if [[ -f "\$PID_FILE" ]]; then
        PID=\$(cat "\$PID_FILE")
        if ps -p \$PID > /dev/null 2>&1; then
            echo "GitDeploy for Splunk déjà en cours d'exécution (PID: \$PID)"
            return 1
        fi
    fi
    
    echo "Démarrage de GitDeploy for Splunk..."
    cd "\$APP_PATH/bin"
    nohup \$PYTHON_CMD gitdeploy.py >> "\$LOG_FILE" 2>&1 &
    echo \$! > "\$PID_FILE"
    echo "GitDeploy for Splunk démarré (PID: \$!)"
}

stop() {
    if [[ -f "\$PID_FILE" ]]; then
        PID=\$(cat "\$PID_FILE")
        if ps -p \$PID > /dev/null 2>&1; then
            echo "Arrêt de GitDeploy for Splunk (PID: \$PID)..."
            kill \$PID
            rm -f "\$PID_FILE"
            echo "GitDeploy for Splunk arrêté"
        else
            echo "Processus non trouvé, nettoyage du PID file"
            rm -f "\$PID_FILE"
        fi
    else
        echo "GitDeploy for Splunk n'est pas en cours d'exécution"
    fi
}

status() {
    if [[ -f "\$PID_FILE" ]]; then
        PID=\$(cat "\$PID_FILE")
        if ps -p \$PID > /dev/null 2>&1; then
            echo "GitDeploy for Splunk en cours d'exécution (PID: \$PID)"
            return 0
        fi
    fi
    echo "GitDeploy for Splunk n'est pas en cours d'exécution"
    return 1
}

case "\$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: \$0 {start|stop|restart|status}"
        exit 1
        ;;
esac
EOF

    chmod +x "${APP_PATH}/bin/start_gitdeploy.sh"
    log_success "Script de démarrage créé"
}

# Générer les certificats SSL
generate_ssl_certs() {
    echo ""
    echo -e "${PURPLE}=== Génération des certificats SSL ===${NC}"
    echo ""
    
    CERT_DIR="${APP_PATH}/local/certs"
    
    if [[ -f "${CERT_DIR}/server.crt" ]] && [[ -f "${CERT_DIR}/server.key" ]]; then
        log_warning "Certificats existants trouvés"
        read -p "Régénérer les certificats ? (o/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Oo]$ ]]; then
            log_info "Certificats conservés"
            return
        fi
    fi
    
    openssl req -x509 -newkey rsa:4096 \
        -keyout "${CERT_DIR}/server.key" \
        -out "${CERT_DIR}/server.crt" \
        -days 365 -nodes \
        -subj "/CN=gitdeploy/O=Splunk/C=FR" 2>/dev/null
    
    chmod 600 "${CERT_DIR}/server.key"
    log_success "Certificats SSL générés"
}

# Configurer les permissions
set_permissions() {
    echo ""
    echo -e "${PURPLE}=== Configuration des permissions ===${NC}"
    echo ""
    
    # Déterminer l'utilisateur Splunk
    SPLUNK_USER="splunk"
    if ! id "$SPLUNK_USER" &>/dev/null; then
        SPLUNK_USER=$(stat -c '%U' "$SPLUNK_HOME")
    fi
    
    chown -R "${SPLUNK_USER}:${SPLUNK_USER}" "${APP_PATH}" 2>/dev/null || true
    chown -R "${SPLUNK_USER}:${SPLUNK_USER}" "${GIT_TEMP_DIR}" 2>/dev/null || true
    chmod +x "${APP_PATH}/bin/"*.sh 2>/dev/null || true
    chmod +x "${APP_PATH}/bin/"*.py 2>/dev/null || true
    
    log_success "Permissions configurées pour ${SPLUNK_USER}"
}

# Configurer le firewall
configure_firewall() {
    echo ""
    echo -e "${PURPLE}=== Configuration du firewall ===${NC}"
    echo ""
    
    if command -v firewall-cmd &> /dev/null; then
        read -p "Ouvrir le port ${SERVICE_PORT} dans le firewall ? (O/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            firewall-cmd --add-port=${SERVICE_PORT}/tcp --permanent 2>/dev/null || true
            firewall-cmd --reload 2>/dev/null || true
            log_success "Port ${SERVICE_PORT} ouvert"
        fi
    else
        log_info "firewall-cmd non disponible, configuration manuelle requise"
    fi
}

# Démarrer le service
start_service() {
    echo ""
    echo -e "${PURPLE}=== Démarrage du service ===${NC}"
    echo ""
    
    read -p "Démarrer GitDeploy for Splunk maintenant ? (O/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        "${APP_PATH}/bin/start_gitdeploy.sh" start
    fi
}

# Vider le cache Splunk
clear_cache() {
    echo ""
    echo -e "${PURPLE}=== Nettoyage du cache ===${NC}"
    echo ""
    
    rm -rf "${SPLUNK_HOME}/var/run/splunk/appserver/"* 2>/dev/null || true
    log_success "Cache Splunk vidé"
}

# Afficher le résumé
show_summary() {
    echo ""
    echo -e "${PURPLE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║              Installation terminée !                        ║${NC}"
    echo -e "${PURPLE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}GitDeploy for Splunk a été installé avec succès.${NC}"
    echo ""
    echo "Configuration:"
    echo "  • Application: ${APP_PATH}"
    echo "  • Port: ${SERVICE_PORT}"
    echo "  • Logs: ${SPLUNK_HOME}/var/log/splunk/gitdeploy.log"
    echo ""
    echo "Commandes utiles:"
    echo "  • Démarrer:  ${APP_PATH}/bin/start_gitdeploy.sh start"
    echo "  • Arrêter:   ${APP_PATH}/bin/start_gitdeploy.sh stop"
    echo "  • Status:    ${APP_PATH}/bin/start_gitdeploy.sh status"
    echo "  • Logs:      tail -f ${SPLUNK_HOME}/var/log/splunk/gitdeploy.log"
    echo ""
    echo "Prochaines étapes:"
    echo "  1. Redémarrez Splunk: ${SPLUNK_HOME}/bin/splunk restart"
    echo "  2. Accédez à GitDeploy for Splunk dans l'interface Splunk"
    echo "  3. Configurez vos paramètres Git dans la page Configuration"
    echo ""
}

# Main
main() {
    check_prerequisites
    create_app_structure
    copy_files
    create_app_conf
    create_start_script
    generate_ssl_certs
    set_permissions
    configure_firewall
    clear_cache
    start_service
    show_summary
}

# Exécuter
main "$@"
