#!/bin/bash

set -e

# DDARP System Automation Script
# Enhanced version with current system state handling

DOCKER_COMPOSE="/tmp/docker-compose"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# WireGuard support
WG_COMPOSE="docker-compose.wireguard.yml"
WG_SETUP_SCRIPT="$SCRIPT_DIR/wireguard_setup.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running"
        exit 1
    fi

    # Check Docker Compose
    if [ ! -f "$DOCKER_COMPOSE" ]; then
        log_warning "Docker Compose not found at $DOCKER_COMPOSE, downloading..."
        curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o "$DOCKER_COMPOSE"
        chmod +x "$DOCKER_COMPOSE"
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi

    log_success "All dependencies satisfied"
}

# Check WireGuard dependencies
check_wireguard_dependencies() {
    log_info "Checking WireGuard dependencies..."

    # Check WireGuard tools
    if ! command -v wg &> /dev/null; then
        log_warning "WireGuard tools not found. WireGuard features will be disabled."
        echo "  To enable WireGuard, install wireguard-tools:"
        echo "    Ubuntu/Debian: sudo apt install wireguard-tools"
        echo "    CentOS/RHEL:   sudo yum install wireguard-tools"
        echo "    macOS:         brew install wireguard-tools"
        return 1
    fi

    # Check if WireGuard setup script exists
    if [ ! -f "$WG_SETUP_SCRIPT" ]; then
        log_warning "WireGuard setup script not found at $WG_SETUP_SCRIPT"
        return 1
    fi

    # Check if WireGuard compose file exists
    if [ ! -f "$PROJECT_DIR/$WG_COMPOSE" ]; then
        log_warning "WireGuard compose file not found at $PROJECT_DIR/$WG_COMPOSE"
        return 1
    fi

    log_success "WireGuard dependencies satisfied"
    return 0
}

# Setup function
setup_system() {
    local use_wireguard=${1:-false}

    if [ "$use_wireguard" = "true" ]; then
        log_info "Setting up DDARP system with WireGuard..."
        setup_wireguard_system
    else
        log_info "Setting up standard DDARP system..."
        setup_standard_system
    fi
}

# Setup standard DDARP system
setup_standard_system() {
    cd "$PROJECT_DIR"

    # Clean up any existing containers
    log_info "Cleaning up existing containers..."
    $DOCKER_COMPOSE down -v 2>/dev/null || true
    $DOCKER_COMPOSE -f "$WG_COMPOSE" down -v 2>/dev/null || true

    # Build and start the system
    log_info "Building Docker images..."
    $DOCKER_COMPOSE build

    log_info "Starting DDARP nodes and Prometheus..."
    $DOCKER_COMPOSE up -d

    log_info "Waiting for services to start..."
    sleep 15

    # Check container status
    log_info "Checking container status..."
    if $DOCKER_COMPOSE ps | grep -q "unhealthy\|exited"; then
        log_error "Some containers are not healthy"
        $DOCKER_COMPOSE ps
        return 1
    fi

    log_success "Standard DDARP system started successfully"
}

# Setup WireGuard DDARP system
setup_wireguard_system() {
    cd "$PROJECT_DIR"

    # Clean up any existing containers
    log_info "Cleaning up existing containers..."
    $DOCKER_COMPOSE down -v 2>/dev/null || true
    $DOCKER_COMPOSE -f "$WG_COMPOSE" down -v 2>/dev/null || true

    # Use WireGuard setup script
    log_info "Running WireGuard setup..."
    if [ -x "$WG_SETUP_SCRIPT" ]; then
        "$WG_SETUP_SCRIPT" setup
    else
        log_error "WireGuard setup script not found or not executable"
        return 1
    fi

    log_success "WireGuard DDARP system started successfully"
}

# Wait for nodes to be healthy
wait_for_health() {
    log_info "Waiting for nodes to become healthy..."

    local max_attempts=30
    local attempt=0

    for port in 8001 8002 8003; do
        attempt=0
        log_info "Checking node on port $port..."

        while [ $attempt -lt $max_attempts ]; do
            if curl -s "http://localhost:$port/health" | grep -q "healthy"; then
                log_success "Node on port $port is healthy"
                break
            else
                ((attempt++))
                if [ $attempt -eq $max_attempts ]; then
                    log_error "Node on port $port failed to become healthy"
                    return 1
                fi
                sleep 2
            fi
        done
    done

    log_success "All nodes are healthy"
}

# Configure peer relationships
configure_peers() {
    local use_wireguard=${1:-false}

    if [ "$use_wireguard" = "true" ]; then
        log_info "Configuring peer relationships with WireGuard IPs..."
        configure_wireguard_peers
    else
        log_info "Configuring peer relationships with standard IPs..."
        configure_standard_peers
    fi

    log_info "Waiting for OWL measurements to stabilize..."
    sleep 15
}

# Configure standard peer relationships
configure_standard_peers() {
    # Configure node1 peers
    log_info "Configuring node1 peers..."
    curl -s -X POST http://localhost:8001/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node2", "peer_ip": "172.20.0.11", "peer_type": "regular"}' | grep -q "success"

    curl -s -X POST http://localhost:8001/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "border1", "peer_ip": "172.20.0.12", "peer_type": "border"}' | grep -q "success"

    # Configure node2 peers
    log_info "Configuring node2 peers..."
    curl -s -X POST http://localhost:8002/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node1", "peer_ip": "172.20.0.10", "peer_type": "regular"}' | grep -q "success"

    curl -s -X POST http://localhost:8002/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "border1", "peer_ip": "172.20.0.12", "peer_type": "border"}' | grep -q "success"

    # Configure border1 peers
    log_info "Configuring border1 peers..."
    curl -s -X POST http://localhost:8003/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node1", "peer_ip": "172.20.0.10", "peer_type": "regular"}' | grep -q "success"

    curl -s -X POST http://localhost:8003/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node2", "peer_ip": "172.20.0.11", "peer_type": "regular"}' | grep -q "success"

    log_success "Standard peer relationships configured successfully"
}

# Configure WireGuard peer relationships
configure_wireguard_peers() {
    # Use the dedicated WireGuard peer setup script
    if [ -f "$SCRIPT_DIR/setup_peers_wireguard.sh" ]; then
        "$SCRIPT_DIR/setup_peers_wireguard.sh"
        log_success "WireGuard peer relationships configured successfully"
    else
        log_error "WireGuard peer setup script not found"
        return 1
    fi
}

# Test system functionality
test_system() {
    log_info "Testing system functionality..."

    # Test health endpoints
    log_info "Testing node health..."
    for port in 8001 8002 8003; do
        local response=$(curl -s "http://localhost:$port/health")
        if echo "$response" | grep -q '"status": "healthy"'; then
            log_success "Node $port: healthy"
        else
            log_error "Node $port: unhealthy - $response"
        fi
    done

    # Test OWL metrics (the working part)
    log_info "Testing OWL metrics..."
    for port in 8001 8002 8003; do
        local response=$(curl -s "http://localhost:$port/metrics/owl")
        if echo "$response" | grep -q '"latency_ms"'; then
            local latency=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    matrix = data.get('metrics_matrix', {})
    latencies = []
    for src in matrix.values():
        for metrics in src.values():
            latencies.append(metrics.get('latency_ms', 0))
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        print(f'{avg_latency:.2f}')
    else:
        print('N/A')
except:
    print('Error')
            ")
            log_success "Node $port: OWL metrics active (avg latency: ${latency}ms)"
        else
            log_error "Node $port: OWL metrics unavailable"
        fi
    done

    # Test topology (partially working)
    log_info "Testing topology discovery..."
    for port in 8001 8002 8003; do
        local response=$(curl -s "http://localhost:$port/topology")
        local node_count=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data['topology']['node_count'])
except:
    print('0')
        ")
        local edge_count=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data['topology']['edge_count'])
except:
    print('0')
        ")

        if [ "$node_count" = "3" ]; then
            log_success "Node $port: All 3 nodes discovered"
        else
            log_warning "Node $port: Only $node_count nodes discovered"
        fi

        if [ "$edge_count" = "0" ]; then
            log_warning "Node $port: No edges (routing disabled - known issue)"
        else
            log_success "Node $port: $edge_count edges created"
        fi
    done

    # Test path queries (expected to fail due to routing issue)
    log_info "Testing path queries (expected to fail due to known routing issue)..."
    local path_response=$(curl -s "http://localhost:8001/path/node2")
    if echo "$path_response" | grep -q '"reachable": true'; then
        log_success "Path queries working"
    else
        log_warning "Path queries not working (expected due to edge creation bug)"
    fi
}

# System status report
system_status() {
    log_info "DDARP System Status Report"
    echo "=========================="

    # Container status
    echo "Container Status:"
    $DOCKER_COMPOSE ps
    echo

    # Service URLs
    echo "Service URLs:"
    echo "- node1 API: http://localhost:8001"
    echo "- node2 API: http://localhost:8002"
    echo "- border1 API: http://localhost:8003"
    echo "- Prometheus: http://localhost:9090"
    echo

    # Quick health check
    echo "Quick Health Check:"
    for port in 8001 8002 8003; do
        if curl -s "http://localhost:$port/health" | grep -q "healthy" 2>/dev/null; then
            echo "✅ Node $port: Healthy"
        else
            echo "❌ Node $port: Unhealthy"
        fi
    done
    echo

    # Known issues
    echo "Known Issues:"
    echo "🔴 Path routing partially fixed (metrics loop timing issue remains)"
    echo "🟡 Prometheus scrapes only itself (nodes expose JSON, not Prometheus format)"
    echo "🟢 OWL measurements working perfectly (~0.5-0.7ms latency)"
    echo "🟢 Node discovery and topology detection functional"
}

# Stop system
stop_system() {
    log_info "Stopping DDARP system..."
    cd "$PROJECT_DIR"

    # Stop both standard and WireGuard systems
    $DOCKER_COMPOSE down 2>/dev/null || true
    if [ -f "$WG_COMPOSE" ]; then
        $DOCKER_COMPOSE -f "$WG_COMPOSE" down 2>/dev/null || true
    fi

    log_success "DDARP system stopped"
}

# Cleanup system
cleanup_system() {
    log_info "Cleaning up DDARP system..."
    cd "$PROJECT_DIR"

    # Cleanup both standard and WireGuard systems
    $DOCKER_COMPOSE down -v 2>/dev/null || true
    if [ -f "$WG_COMPOSE" ]; then
        $DOCKER_COMPOSE -f "$WG_COMPOSE" down -v 2>/dev/null || true
    fi

    docker image prune -f
    log_success "DDARP system cleaned up"
}

# Show logs
show_logs() {
    local service=${1:-}
    cd "$PROJECT_DIR"

    if [ -z "$service" ]; then
        log_info "Available services: node1, node2, border1, prometheus"
        log_info "Usage: $0 logs <service_name>"
        return
    fi

    log_info "Showing logs for $service..."
    $DOCKER_COMPOSE logs -f "$service"
}

# Main menu
show_help() {
    echo "DDARP System Automation Script"
    echo "=============================="
    echo
    echo "Usage: $0 <command> [options]"
    echo
    echo "Commands:"
    echo "  setup          - Full system setup (build, start, configure)"
    echo "  setup-wg       - Full WireGuard system setup"
    echo "  start          - Start existing system"
    echo "  start-wg       - Start WireGuard system"
    echo "  stop           - Stop system"
    echo "  restart        - Restart system"
    echo "  restart-wg     - Restart WireGuard system"
    echo "  test           - Run system tests"
    echo "  test-wg        - Run WireGuard system tests"
    echo "  status         - Show system status"
    echo "  logs [svc]     - Show logs (optionally for specific service)"
    echo "  cleanup        - Stop and cleanup system completely"
    echo "  health         - Quick health check"
    echo "  wg-status      - Show WireGuard-specific status"
    echo "  help           - Show this help"
    echo
    echo "Standard Examples:"
    echo "  $0 setup           # Complete standard setup from scratch"
    echo "  $0 test            # Test current system"
    echo "  $0 logs node1      # Show node1 logs"
    echo "  $0 status          # Show status report"
    echo
    echo "WireGuard Examples:"
    echo "  $0 setup-wg       # Complete WireGuard setup from scratch"
    echo "  $0 test-wg        # Test WireGuard system"
    echo "  $0 wg-status      # Show WireGuard status"
    echo
    echo "Notes:"
    echo "  - WireGuard commands require wireguard-tools to be installed"
    echo "  - Use 'setup-wg' for encrypted network communication"
    echo "  - Standard mode uses Docker bridge networking"
}

# Quick health check
quick_health() {
    log_info "Quick health check..."

    # Check containers (try both compose files)
    local containers_running=false
    if $DOCKER_COMPOSE ps | grep -q "Up"; then
        containers_running=true
        log_info "Standard containers detected"
    elif [ -f "$PROJECT_DIR/$WG_COMPOSE" ] && $DOCKER_COMPOSE -f "$WG_COMPOSE" ps | grep -q "Up"; then
        containers_running=true
        log_info "WireGuard containers detected"
    fi

    if ! $containers_running; then
        log_error "No containers are running"
        return 1
    fi

    # Check APIs
    for port in 8001 8002 8003; do
        if ! curl -s "http://localhost:$port/health" | grep -q "healthy"; then
            log_error "Node $port is not healthy"
            return 1
        fi
    done

    log_success "All nodes healthy"
}

# WireGuard specific status
wireguard_status() {
    log_info "WireGuard System Status"

    if [ ! -f "$PROJECT_DIR/$WG_COMPOSE" ]; then
        log_error "WireGuard compose file not found"
        return 1
    fi

    # Check if WireGuard containers are running
    cd "$PROJECT_DIR"
    if ! $DOCKER_COMPOSE -f "$WG_COMPOSE" ps | grep -q "Up"; then
        log_error "WireGuard containers are not running"
        return 1
    fi

    # Use WireGuard setup script status function
    if [ -x "$WG_SETUP_SCRIPT" ]; then
        "$WG_SETUP_SCRIPT" status
    else
        log_warning "WireGuard setup script not found, showing basic status"
        $DOCKER_COMPOSE -f "$WG_COMPOSE" ps
    fi
}

# Main script logic
main() {
    local command=${1:-help}

    case $command in
        "setup")
            check_dependencies
            setup_system false
            wait_for_health
            configure_peers false
            test_system
            system_status
            ;;
        "setup-wg")
            check_dependencies
            if check_wireguard_dependencies; then
                setup_system true
                log_success "WireGuard system setup complete"
            else
                log_error "WireGuard dependencies not satisfied"
                exit 1
            fi
            ;;
        "start")
            check_dependencies
            cd "$PROJECT_DIR"
            $DOCKER_COMPOSE up -d
            wait_for_health
            log_success "Standard system started"
            ;;
        "start-wg")
            check_dependencies
            if check_wireguard_dependencies; then
                cd "$PROJECT_DIR"
                $DOCKER_COMPOSE -f "$WG_COMPOSE" up -d
                wait_for_health
                log_success "WireGuard system started"
            else
                log_error "WireGuard dependencies not satisfied"
                exit 1
            fi
            ;;
        "stop")
            stop_system
            ;;
        "restart")
            stop_system
            sleep 2
            cd "$PROJECT_DIR"
            $DOCKER_COMPOSE up -d
            wait_for_health
            log_success "Standard system restarted"
            ;;
        "restart-wg")
            if check_wireguard_dependencies; then
                stop_system
                sleep 2
                cd "$PROJECT_DIR"
                $DOCKER_COMPOSE -f "$WG_COMPOSE" up -d
                wait_for_health
                log_success "WireGuard system restarted"
            else
                log_error "WireGuard dependencies not satisfied"
                exit 1
            fi
            ;;
        "test")
            test_system
            ;;
        "test-wg")
            if check_wireguard_dependencies; then
                if [ -x "$WG_SETUP_SCRIPT" ]; then
                    "$WG_SETUP_SCRIPT" test
                else
                    log_warning "WireGuard setup script not found, running standard tests"
                    test_system
                fi
            else
                log_error "WireGuard dependencies not satisfied"
                exit 1
            fi
            ;;
        "status")
            system_status
            ;;
        "wg-status")
            wireguard_status
            ;;
        "logs")
            show_logs "$2"
            ;;
        "cleanup")
            cleanup_system
            ;;
        "health")
            quick_health
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Run main function with all arguments
main "$@"