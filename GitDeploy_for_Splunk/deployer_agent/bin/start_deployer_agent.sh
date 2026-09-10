#!/bin/bash
# ============================================
# SH Deployer Agent - Start Script
# À installer sur le Search Head Deployer
# ============================================

# Configuration
SPLUNK_HOME=${SPLUNK_HOME:-/opt/splunk}
APP_NAME="deployer_agent"
APP_HOME="${SPLUNK_HOME}/etc/apps/${APP_NAME}"
BIN_DIR="${APP_HOME}/bin"
LOG_DIR="${SPLUNK_HOME}/var/log/splunk"
PID_FILE="${BIN_DIR}/deployer_agent.pid"
CERTS_DIR="${APP_HOME}/local/certs"

# Port de l'agent
AGENT_PORT=9998

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Vérifier si l'agent tourne
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Générer les certificats SSL
generate_certs() {
    log_info "Generating SSL certificates..."
    
    mkdir -p "$CERTS_DIR"
    
    openssl req -x509 -newkey rsa:4096 \
        -keyout "${CERTS_DIR}/server.key" \
        -out "${CERTS_DIR}/server.crt" \
        -days 365 -nodes \
        -subj "/CN=deployer-agent"
    
    chmod 600 "${CERTS_DIR}/server.key"
    chown -R splunk:splunk "$CERTS_DIR" 2>/dev/null || true
    
    log_info "Certificates generated in $CERTS_DIR"
}

# Démarrer l'agent
start_agent() {
    log_info "Starting SH Deployer Agent..."
    
    if check_running; then
        log_warn "Agent is already running (PID: $(cat $PID_FILE))"
        return 1
    fi
    
    # Vérifier les certificats
    if [ ! -f "${CERTS_DIR}/server.crt" ]; then
        log_warn "SSL certificates not found, generating..."
        generate_certs
    fi
    
    # Créer les dossiers nécessaires
    mkdir -p "$LOG_DIR"
    mkdir -p "$BIN_DIR"
    
    # Démarrer l'agent
    cd "$BIN_DIR"
    python3 deployer_agent.py --port $AGENT_PORT > "${LOG_DIR}/deployer_agent_startup.log" 2>&1 &
    
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if check_running; then
        log_info "Agent started successfully (PID: $(cat $PID_FILE))"
        log_info "Listening on port $AGENT_PORT"
        return 0
    else
        log_error "Failed to start agent"
        log_error "Check logs: ${LOG_DIR}/deployer_agent.log"
        return 1
    fi
}

# Arrêter l'agent
stop_agent() {
    log_info "Stopping SH Deployer Agent..."
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            sleep 2
            
            if ps -p $PID > /dev/null 2>&1; then
                log_warn "Force killing..."
                kill -9 $PID
            fi
            
            rm -f "$PID_FILE"
            log_info "Agent stopped"
            return 0
        else
            log_warn "Process not running, cleaning up PID file"
            rm -f "$PID_FILE"
            return 0
        fi
    else
        log_warn "PID file not found"
        return 1
    fi
}

# Redémarrer l'agent
restart_agent() {
    log_info "Restarting SH Deployer Agent..."
    stop_agent
    sleep 1
    start_agent
}

# Afficher le statut
show_status() {
    echo "============================================"
    echo "SH Deployer Agent Status"
    echo "============================================"
    
    if check_running; then
        PID=$(cat "$PID_FILE")
        echo -e "Status: ${GREEN}RUNNING${NC}"
        echo "PID: $PID"
        echo "Port: $AGENT_PORT"
    else
        echo -e "Status: ${RED}STOPPED${NC}"
    fi
    
    echo ""
    echo "Paths:"
    echo "  App Home: $APP_HOME"
    echo "  SHCluster Apps: ${SPLUNK_HOME}/etc/shcluster/apps"
    echo "  Logs: ${LOG_DIR}/deployer_agent.log"
    echo ""
    
    # Vérifier les certificats
    echo "SSL Certificates:"
    if [ -f "${CERTS_DIR}/server.crt" ]; then
        echo -e "  Status: ${GREEN}Present${NC}"
        EXPIRY=$(openssl x509 -enddate -noout -in "${CERTS_DIR}/server.crt" 2>/dev/null | cut -d= -f2)
        echo "  Expires: $EXPIRY"
    else
        echo -e "  Status: ${YELLOW}Not found${NC}"
    fi
    
    echo ""
    echo "============================================"
}

# Afficher les logs
show_logs() {
    LOG_FILE="${LOG_DIR}/deployer_agent.log"
    
    if [ -f "$LOG_FILE" ]; then
        if [ "$1" == "-f" ]; then
            tail -f "$LOG_FILE"
        else
            tail -n 50 "$LOG_FILE"
        fi
    else
        log_warn "Log file not found"
    fi
}

# Tester la connexion
test_connection() {
    log_info "Testing agent connection..."
    
    if command -v curl &> /dev/null; then
        RESPONSE=$(curl -sk "https://127.0.0.1:${AGENT_PORT}/health" 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Connection OK${NC}"
            echo "Response: $RESPONSE"
        else
            # Essayer en HTTP
            RESPONSE=$(curl -s "http://127.0.0.1:${AGENT_PORT}/health" 2>/dev/null)
            if [ $? -eq 0 ]; then
                echo -e "${YELLOW}Connection OK (HTTP only)${NC}"
                echo "Response: $RESPONSE"
            else
                echo -e "${RED}Connection FAILED${NC}"
            fi
        fi
    else
        log_warn "curl not installed"
    fi
}

# Aide
show_help() {
    echo "SH Deployer Agent - Management Script"
    echo ""
    echo "Usage: $0 {command}"
    echo ""
    echo "Commands:"
    echo "  start       Start the agent"
    echo "  stop        Stop the agent"
    echo "  restart     Restart the agent"
    echo "  status      Show status"
    echo "  logs [-f]   Show logs (-f to follow)"
    echo "  test        Test connection"
    echo "  gencerts    Generate SSL certificates"
    echo "  help        Show this help"
    echo ""
    echo "Configuration:"
    echo "  Port: $AGENT_PORT"
    echo "  App Home: $APP_HOME"
}

# Main
case "$1" in
    start)
        start_agent
        ;;
    stop)
        stop_agent
        ;;
    restart)
        restart_agent
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    test)
        test_connection
        ;;
    gencerts)
        generate_certs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -z "$1" ]; then
            show_help
        else
            echo "Unknown command: $1"
            show_help
            exit 1
        fi
        ;;
esac
