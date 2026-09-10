#!/bin/bash
# ============================================
# GitDeploy for Splunk - Start Script
# ============================================

# Configuration
SPLUNK_HOME=${SPLUNK_HOME:-/opt/splunk}
APP_NAME="gitdeploy_app"
APP_HOME="${SPLUNK_HOME}/etc/apps/${APP_NAME}"
BIN_DIR="${APP_HOME}/bin"
LOG_DIR="${SPLUNK_HOME}/var/log/splunk"
PID_FILE="${BIN_DIR}/gitdeploy.pid"

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction de logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Vérifier si le serveur est déjà en cours d'exécution
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0  # Running
        fi
    fi
    return 1  # Not running
}

# Démarrer le serveur
start_server() {
    log_info "Starting GitDeploy for Splunk server..."

    # Vérifier si déjà en cours
    if check_running; then
        log_warn "GitDeploy for Splunk is already running (PID: $(cat $PID_FILE))"
        return 1
    fi

    # Créer le répertoire de logs
    mkdir -p "$LOG_DIR"

    # Démarrer le serveur Python. La configuration (port, token API, SH Deployer, etc.) vit
    # dans local/config.json et est gérée via la page "Configuration" de l'app - aucun
    # identifiant Splunk n'est requis pour démarrer ce serveur.
    cd "$BIN_DIR"
    python3 gitdeploy.py > "${LOG_DIR}/gitdeploy_startup.log" 2>&1 &

    # Sauvegarder le PID
    echo $! > "$PID_FILE"

    # Attendre un peu et vérifier
    sleep 2

    if check_running; then
        log_info "GitDeploy for Splunk started successfully (PID: $(cat $PID_FILE))"
        log_info "Server listening on port 9999"

        HOSTNAME=$(hostname)
        log_info "Hostname: $HOSTNAME"

        if [ -f "${APP_HOME}/local/license.lic" ]; then
            log_info "License file found"
        else
            log_warn "No license file found - activation required"
        fi

        if grep -q "No API token was configured" "${LOG_DIR}/gitdeploy.log" 2>/dev/null; then
            log_warn "A new API token was generated - check ${LOG_DIR}/gitdeploy.log and enter"
            log_warn "it on the Configuration page before using the dashboard."
        fi

        return 0
    else
        log_error "Failed to start GitDeploy for Splunk"
        log_error "Check logs at ${LOG_DIR}/gitdeploy.log"
        return 1
    fi
}

# Arrêter le serveur
stop_server() {
    log_info "Stopping GitDeploy for Splunk server..."

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")

        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            sleep 2

            # Force kill si nécessaire
            if ps -p $PID > /dev/null 2>&1; then
                log_warn "Force killing process..."
                kill -9 $PID
            fi

            rm -f "$PID_FILE"
            log_info "GitDeploy for Splunk stopped"
            return 0
        else
            log_warn "Process not running, cleaning up PID file"
            rm -f "$PID_FILE"
            return 0
        fi
    else
        log_warn "PID file not found, GitDeploy for Splunk may not be running"
        return 1
    fi
}

# Redémarrer le serveur
restart_server() {
    log_info "Restarting GitDeploy for Splunk server..."
    stop_server
    sleep 1
    start_server
}

# Afficher le statut
show_status() {
    echo "============================================"
    echo "GitDeploy for Splunk Status"
    echo "============================================"

    if check_running; then
        PID=$(cat "$PID_FILE")
        echo -e "Server Status: ${GREEN}RUNNING${NC}"
        echo "PID: $PID"
        echo "Port: 9999"
    else
        echo -e "Server Status: ${RED}STOPPED${NC}"
    fi

    echo ""
    echo "Paths:"
    echo "  App Home: $APP_HOME"
    echo "  Bin Dir: $BIN_DIR"
    echo "  Log Dir: $LOG_DIR"
    echo "  Config: ${APP_HOME}/local/config.json"
    echo ""

    # Statut de la licence
    echo "License:"
    if [ -f "${APP_HOME}/local/license.lic" ]; then
        echo -e "  File: ${GREEN}Present${NC}"
        # Essayer de lire quelques infos
        if command -v python3 &> /dev/null; then
            python3 -c "
import sys
sys.path.insert(0, '$BIN_DIR')
try:
    from license_validator import validate_license
    result = validate_license()
    if result.get('valid'):
        print(f\"  Type: {result.get('type_name', 'N/A')}\")
        print(f\"  Expires: {result.get('expires', 'N/A')}\")
        print(f\"  Days remaining: {result.get('days_remaining', 'N/A')}\")
    else:
        print(f\"  Status: Invalid - {result.get('error', 'Unknown error')}\")
except Exception as e:
    print(f'  Unable to read license: {e}')
" 2>/dev/null || echo "  Unable to read license details"
        fi
    else
        echo -e "  File: ${YELLOW}Not found${NC}"
    fi

    echo ""
    echo "Hostname: $(hostname)"
    echo "============================================"
}

# Afficher les logs
show_logs() {
    LOG_FILE="${LOG_DIR}/gitdeploy.log"

    if [ -f "$LOG_FILE" ]; then
        if [ "$1" == "-f" ]; then
            tail -f "$LOG_FILE"
        else
            tail -n 50 "$LOG_FILE"
        fi
    else
        log_warn "Log file not found at $LOG_FILE"
    fi
}

# Menu d'aide
show_help() {
    echo "GitDeploy for Splunk - Server Management Script"
    echo ""
    echo "Usage: $0 {command} [options]"
    echo ""
    echo "Commands:"
    echo "  start              Start the GitDeploy for Splunk server"
    echo "  stop               Stop the GitDeploy for Splunk server"
    echo "  restart            Restart the GitDeploy for Splunk server"
    echo "  status             Show the current status"
    echo "  logs [-f]          Show recent logs (-f for follow)"
    echo "  help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start               # Start server"
    echo "  $0 logs -f             # Follow logs"
}

# Main
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -z "$1" ]; then
            show_help
        else
            echo "Unknown command: $1"
            echo ""
            show_help
            exit 1
        fi
        ;;
esac
