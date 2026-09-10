#!/bin/bash
# ============================================
# GitDeploy for Splunk - Script d'installation
# SH Deployer Agent
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
APP_NAME="deployer_agent"
APP_PATH="${SPLUNK_HOME}/etc/apps/${APP_NAME}"
GIT_REPOS_DIR="${SPLUNK_HOME}/var/git_repos"
SERVICE_PORT=9998

# Banner
echo -e "${PURPLE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║     🎯 SH Deployer Agent - Installation Script            ║"
echo "║                                                            ║"
echo "║     Version: 2.1                                          ║"
echo "║     Serveur: Search Head Deployer                         ║"
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
        GIT_REPOS_DIR="${SPLUNK_HOME}/var/git_repos"
    fi
    log_success "Splunk trouvé: $SPLUNK_HOME"
    
    # Vérifier que c'est bien un Deployer
    if [[ ! -d "${SPLUNK_HOME}/etc/shcluster" ]]; then
        log_warning "Ce serveur ne semble pas être un Search Head Deployer"
        log_warning "Le dossier ${SPLUNK_HOME}/etc/shcluster n'existe pas"
        read -p "Continuer quand même ? (o/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Oo]$ ]]; then
            exit 1
        fi
        mkdir -p "${SPLUNK_HOME}/etc/shcluster/apps"
    fi
    log_success "SH Cluster config trouvée"
    
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
        # Essayer le Python de Splunk
        if [[ -x "${SPLUNK_HOME}/bin/python3" ]]; then
            PYTHON_CMD="${SPLUNK_HOME}/bin/python3"
        else
            log_error "Python n'est pas installé"
            exit 1
        fi
    fi
    log_success "Python installé: $($PYTHON_CMD --version 2>&1)"
}

# Créer la structure de l'application
create_app_structure() {
    echo ""
    echo -e "${PURPLE}=== Création de la structure de l'application ===${NC}"
    echo ""
    
    # Créer les dossiers
    mkdir -p "${APP_PATH}/bin"
    mkdir -p "${APP_PATH}/local/certs"
    mkdir -p "${APP_PATH}/local"
    mkdir -p "${GIT_REPOS_DIR}"
    mkdir -p "${SPLUNK_HOME}/etc/shcluster/apps"
    
    log_success "Structure créée: ${APP_PATH}"
    log_success "Dossier Git repos: ${GIT_REPOS_DIR}"
}

# Copier les fichiers
copy_files() {
    echo ""
    echo -e "${PURPLE}=== Copie des fichiers ===${NC}"
    echo ""
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Déterminer le dossier source des fichiers
    # Si on est dans gitdeploy_distribution/, chercher dans deployer_agent/
    if [[ -d "${SCRIPT_DIR}/deployer_agent" ]]; then
        SOURCE_DIR="${SCRIPT_DIR}/deployer_agent"
    else
        # Sinon, on suppose que les fichiers sont à côté du script
        SOURCE_DIR="${SCRIPT_DIR}"
    fi
    
    log_info "Dossier source: ${SOURCE_DIR}"
    
    # Copier deployer_agent.py
    if [[ -f "${SOURCE_DIR}/bin/deployer_agent.py" ]]; then
        cp "${SOURCE_DIR}/bin/deployer_agent.py" "${APP_PATH}/bin/"
        log_success "Copié: deployer_agent.py"
    elif [[ -f "${SOURCE_DIR}/deployer_agent.py" ]]; then
        cp "${SOURCE_DIR}/deployer_agent.py" "${APP_PATH}/bin/"
        log_success "Copié: deployer_agent.py"
    else
        log_error "deployer_agent.py non trouvé"
        exit 1
    fi
    
    # Copier configure_deployer_credentials.py
    if [[ -f "${SOURCE_DIR}/bin/configure_deployer_credentials.py" ]]; then
        cp "${SOURCE_DIR}/bin/configure_deployer_credentials.py" "${APP_PATH}/bin/"
        log_success "Copié: configure_deployer_credentials.py"
    elif [[ -f "${SOURCE_DIR}/configure_deployer_credentials.py" ]]; then
        cp "${SOURCE_DIR}/configure_deployer_credentials.py" "${APP_PATH}/bin/"
        log_success "Copié: configure_deployer_credentials.py"
    fi
    
    # Copier start_deployer_agent.sh si présent
    if [[ -f "${SOURCE_DIR}/bin/start_deployer_agent.sh" ]]; then
        cp "${SOURCE_DIR}/bin/start_deployer_agent.sh" "${APP_PATH}/bin/"
        chmod +x "${APP_PATH}/bin/start_deployer_agent.sh"
        log_success "Copié: start_deployer_agent.sh"
        START_SCRIPT_COPIED=true
    else
        START_SCRIPT_COPIED=false
    fi
}

# Générer le token d'authentification
generate_auth_token() {
    echo ""
    echo -e "${PURPLE}=== Configuration du token d'authentification ===${NC}"
    echo ""

    # deployer_agent.py génère et persiste lui-même un token aléatoire dans
    # local/auth_token.txt au premier démarrage s'il n'en trouve pas. On peut donc en générer
    # un ici à l'avance (utile pour l'afficher pendant l'installation), mais il ne doit plus
    # être injecté dans le code source: deployer_agent.py le relira depuis ce même fichier.
    mkdir -p "${APP_PATH}/local"

    if [[ -f "${APP_PATH}/local/auth_token.txt" ]]; then
        NEW_TOKEN=$(cat "${APP_PATH}/local/auth_token.txt")
        log_info "Token d'authentification existant réutilisé (local/auth_token.txt)"
    else
        NEW_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
        echo "${NEW_TOKEN}" > "${APP_PATH}/local/auth_token.txt"
        chmod 600 "${APP_PATH}/local/auth_token.txt"
        log_success "Nouveau token généré et sauvegardé dans ${APP_PATH}/local/auth_token.txt"
    fi

    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  IMPORTANT: Notez ce token, il sera nécessaire pour la configuration   ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Token: ${GREEN}${NEW_TOKEN}${NC}"
    echo ""
}

# Créer le script de démarrage
create_start_script() {
    echo ""
    echo -e "${PURPLE}=== Création du script de démarrage ===${NC}"
    echo ""

    # Si start_deployer_agent.sh a déjà été copié depuis la distribution (cas normal), ne pas
    # l'écraser par une version générée ici avec une implémentation différente : une seule
    # version du script de démarrage, à jour.
    if [[ "${START_SCRIPT_COPIED:-false}" == "true" ]]; then
        log_success "start_deployer_agent.sh déjà en place (copié depuis la distribution), pas de régénération"
        return 0
    fi

    cat > "${APP_PATH}/bin/start_deployer_agent.sh" << EOF
#!/bin/bash
# SH Deployer Agent - Script de démarrage/arrêt

SPLUNK_HOME="${SPLUNK_HOME}"
APP_PATH="${APP_PATH}"
PID_FILE="${APP_PATH}/local/deployer_agent.pid"
LOG_FILE="${SPLUNK_HOME}/var/log/splunk/deployer_agent.log"
PYTHON_CMD="${PYTHON_CMD:-python3}"

export SPLUNK_HOME

start() {
    if [[ -f "\$PID_FILE" ]]; then
        PID=\$(cat "\$PID_FILE")
        if ps -p \$PID > /dev/null 2>&1; then
            echo "Deployer Agent déjà en cours d'exécution (PID: \$PID)"
            return 1
        fi
    fi
    
    echo "Démarrage du Deployer Agent..."
    cd "\$APP_PATH/bin"
    nohup \$PYTHON_CMD deployer_agent.py >> "\$LOG_FILE" 2>&1 &
    echo \$! > "\$PID_FILE"
    echo "Deployer Agent démarré (PID: \$!)"
}

stop() {
    if [[ -f "\$PID_FILE" ]]; then
        PID=\$(cat "\$PID_FILE")
        if ps -p \$PID > /dev/null 2>&1; then
            echo "Arrêt du Deployer Agent (PID: \$PID)..."
            kill \$PID
            rm -f "\$PID_FILE"
            echo "Deployer Agent arrêté"
        else
            echo "Processus non trouvé, nettoyage du PID file"
            rm -f "\$PID_FILE"
        fi
    else
        echo "Deployer Agent n'est pas en cours d'exécution"
    fi
}

status() {
    if [[ -f "\$PID_FILE" ]]; then
        PID=\$(cat "\$PID_FILE")
        if ps -p \$PID > /dev/null 2>&1; then
            echo "Deployer Agent en cours d'exécution (PID: \$PID)"
            return 0
        fi
    fi
    echo "Deployer Agent n'est pas en cours d'exécution"
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

    chmod +x "${APP_PATH}/bin/start_deployer_agent.sh"
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
        -subj "/CN=deployer-agent/O=Splunk/C=FR" 2>/dev/null
    
    chmod 600 "${CERT_DIR}/server.key"
    log_success "Certificats SSL générés"
}

# Configurer les credentials Splunk
configure_splunk_credentials() {
    echo ""
    echo -e "${PURPLE}=== Configuration des credentials Splunk ===${NC}"
    echo ""
    
    echo "Ces credentials seront utilisés pour exécuter:"
    echo "  splunk apply shcluster-bundle -target <uri> -auth <user>:<pass>"
    echo ""
    
    read -p "Configurer les credentials maintenant ? (O/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "Configuration reportée. Utilisez plus tard:"
        echo "  ${PYTHON_CMD} ${APP_PATH}/bin/configure_deployer_credentials.py"
        return
    fi
    
    read -p "Nom d'utilisateur Splunk [admin]: " SPLUNK_USER
    SPLUNK_USER="${SPLUNK_USER:-admin}"
    
    read -s -p "Mot de passe Splunk: " SPLUNK_PASS
    echo ""
    
    if [[ -z "$SPLUNK_PASS" ]]; then
        log_error "Mot de passe requis"
        return
    fi
    
    read -p "URI du Captain (ex: https://10.10.40.20:8089) [laisser vide pour défaut]: " TARGET_URI
    
    # Créer le fichier de credentials
    PASS_B64=$(echo -n "$SPLUNK_PASS" | base64)
    
    cat > "${APP_PATH}/local/credentials.json" << EOF
{
    "splunk_user": "${SPLUNK_USER}",
    "splunk_password_b64": "${PASS_B64}",
    "target_uri": ${TARGET_URI:+\"$TARGET_URI\"}${TARGET_URI:-null},
    "updated_at": "$(date -Iseconds)"
}
EOF

    chmod 600 "${APP_PATH}/local/credentials.json"
    log_success "Credentials configurés pour l'utilisateur: ${SPLUNK_USER}"
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
    chown -R "${SPLUNK_USER}:${SPLUNK_USER}" "${GIT_REPOS_DIR}" 2>/dev/null || true
    chown -R "${SPLUNK_USER}:${SPLUNK_USER}" "${SPLUNK_HOME}/etc/shcluster" 2>/dev/null || true
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
    
    read -p "Démarrer le Deployer Agent maintenant ? (O/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        "${APP_PATH}/bin/start_deployer_agent.sh" start
        
        # Vérifier le health check
        sleep 2
        if curl -sk "https://localhost:${SERVICE_PORT}/health" > /dev/null 2>&1; then
            log_success "Health check OK"
        elif curl -sk "http://localhost:${SERVICE_PORT}/health" > /dev/null 2>&1; then
            log_success "Health check OK (HTTP)"
        else
            log_warning "Health check échoué - vérifiez les logs"
        fi
    fi
}

# Afficher le résumé
show_summary() {
    TOKEN=$(cat "${APP_PATH}/local/auth_token.txt" 2>/dev/null || echo "N/A")
    
    echo ""
    echo -e "${PURPLE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║              Installation terminée !                        ║${NC}"
    echo -e "${PURPLE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}SH Deployer Agent a été installé avec succès.${NC}"
    echo ""
    echo "Configuration:"
    echo "  • Application: ${APP_PATH}"
    echo "  • Port: ${SERVICE_PORT} (HTTPS)"
    echo "  • Git Repos: ${GIT_REPOS_DIR}"
    echo "  • SHCluster Apps: ${SPLUNK_HOME}/etc/shcluster/apps"
    echo "  • Logs: ${SPLUNK_HOME}/var/log/splunk/deployer_agent.log"
    echo ""
    echo -e "${YELLOW}Token d'authentification:${NC}"
    echo -e "  ${GREEN}${TOKEN}${NC}"
    echo ""
    echo "Commandes utiles:"
    echo "  • Démarrer:     ${APP_PATH}/bin/start_deployer_agent.sh start"
    echo "  • Arrêter:      ${APP_PATH}/bin/start_deployer_agent.sh stop"
    echo "  • Status:       ${APP_PATH}/bin/start_deployer_agent.sh status"
    echo "  • Credentials:  ${PYTHON_CMD} ${APP_PATH}/bin/configure_deployer_credentials.py"
    echo "  • Logs:         tail -f ${SPLUNK_HOME}/var/log/splunk/deployer_agent.log"
    echo ""
    echo "Test de connexion:"
    echo "  curl -sk https://localhost:${SERVICE_PORT}/health"
    echo ""
    echo -e "${YELLOW}Prochaines étapes:${NC}"
    echo "  1. Notez le token ci-dessus"
    echo "  2. Sur le serveur GitDeploy for Splunk, configurez ce token dans Configuration"
    echo "  3. Testez un déploiement"
    echo ""
}

# Main
main() {
    check_prerequisites
    create_app_structure
    copy_files
    generate_auth_token
    create_start_script
    generate_ssl_certs
    configure_splunk_credentials
    set_permissions
    configure_firewall
    start_service
    show_summary
}

# Exécuter
main "$@"
