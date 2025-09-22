#!/bin/bash

# DDARP WireGuard Setup Automation Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if WireGuard is installed
check_wireguard() {
    if ! command -v wg &> /dev/null; then
        print_error "WireGuard tools not found. Please install WireGuard:"
        echo "  Ubuntu/Debian: sudo apt install wireguard-tools"
        echo "  CentOS/RHEL:   sudo yum install wireguard-tools"
        echo "  macOS:         brew install wireguard-tools"
        exit 1
    fi
    print_success "WireGuard tools found"
}

# Function to generate WireGuard keys
generate_keys() {
    print_status "Generating WireGuard keys..."
    cd "$PROJECT_DIR/wireguard/scripts"
    ./generate_keys.sh
    print_success "WireGuard keys generated"
}

# Function to update configuration files with real keys
update_configs() {
    print_status "Updating WireGuard configuration files with generated keys..."

    local node1_private=$(cat "$PROJECT_DIR/wireguard/keys/node1_private.key")
    local node1_public=$(cat "$PROJECT_DIR/wireguard/keys/node1_public.key")
    local node2_private=$(cat "$PROJECT_DIR/wireguard/keys/node2_private.key")
    local node2_public=$(cat "$PROJECT_DIR/wireguard/keys/node2_public.key")
    local border1_private=$(cat "$PROJECT_DIR/wireguard/keys/border1_private.key")
    local border1_public=$(cat "$PROJECT_DIR/wireguard/keys/border1_public.key")

    # Update node1 config
    sed -i "s/NODE1_PRIVATE_KEY_PLACEHOLDER/$node1_private/g" "$PROJECT_DIR/wireguard/configs/node1.conf"
    sed -i "s/NODE2_PUBLIC_KEY_PLACEHOLDER/$node2_public/g" "$PROJECT_DIR/wireguard/configs/node1.conf"
    sed -i "s/BORDER1_PUBLIC_KEY_PLACEHOLDER/$border1_public/g" "$PROJECT_DIR/wireguard/configs/node1.conf"

    # Update node2 config
    sed -i "s/NODE2_PRIVATE_KEY_PLACEHOLDER/$node2_private/g" "$PROJECT_DIR/wireguard/configs/node2.conf"
    sed -i "s/NODE1_PUBLIC_KEY_PLACEHOLDER/$node1_public/g" "$PROJECT_DIR/wireguard/configs/node2.conf"
    sed -i "s/BORDER1_PUBLIC_KEY_PLACEHOLDER/$border1_public/g" "$PROJECT_DIR/wireguard/configs/node2.conf"

    # Update border1 config
    sed -i "s/BORDER1_PRIVATE_KEY_PLACEHOLDER/$border1_private/g" "$PROJECT_DIR/wireguard/configs/border1.conf"
    sed -i "s/NODE1_PUBLIC_KEY_PLACEHOLDER/$node1_public/g" "$PROJECT_DIR/wireguard/configs/border1.conf"
    sed -i "s/NODE2_PUBLIC_KEY_PLACEHOLDER/$node2_public/g" "$PROJECT_DIR/wireguard/configs/border1.conf"

    print_success "Configuration files updated with WireGuard keys"
}

# Function to start WireGuard-enabled DDARP system
start_system() {
    print_status "Starting DDARP system with WireGuard..."
    cd "$PROJECT_DIR"

    # Stop any existing system
    docker-compose -f docker-compose.wireguard.yml down 2>/dev/null || true

    # Build and start containers
    docker-compose -f docker-compose.wireguard.yml up -d --build

    print_success "DDARP system with WireGuard started"
}

# Function to setup peers
setup_peers() {
    print_status "Waiting for system to initialize..."
    sleep 30

    print_status "Setting up peer relationships with WireGuard IPs..."
    "$SCRIPT_DIR/setup_peers_wireguard.sh"

    print_success "Peer setup complete"
}

# Function to test the system
test_system() {
    print_status "Testing WireGuard DDARP system..."

    # Test container status
    print_status "Checking container status..."
    docker-compose -f "$PROJECT_DIR/docker-compose.wireguard.yml" ps

    # Test API endpoints
    print_status "Testing API endpoints..."
    for port in 8001 8002 8003; do
        if curl -s "http://localhost:$port/health" > /dev/null; then
            print_success "Port $port: API responsive"
        else
            print_warning "Port $port: API not responsive"
        fi
    done

    # Test WireGuard interfaces in containers
    print_status "Checking WireGuard interfaces..."
    docker exec ddarp_node1_wg wg show 2>/dev/null && print_success "Node1: WireGuard active" || print_warning "Node1: WireGuard issues"
    docker exec ddarp_node2_wg wg show 2>/dev/null && print_success "Node2: WireGuard active" || print_warning "Node2: WireGuard issues"
    docker exec ddarp_border1_wg wg show 2>/dev/null && print_success "Border1: WireGuard active" || print_warning "Border1: WireGuard issues"

    # Test WireGuard connectivity
    print_status "Testing WireGuard connectivity..."
    docker exec ddarp_node1_wg ping -c 2 10.0.0.2 > /dev/null 2>&1 && print_success "Node1 → Node2: Connected" || print_warning "Node1 → Node2: Connection issues"
    docker exec ddarp_node1_wg ping -c 2 10.0.0.3 > /dev/null 2>&1 && print_success "Node1 → Border1: Connected" || print_warning "Node1 → Border1: Connection issues"
    docker exec ddarp_node2_wg ping -c 2 10.0.0.3 > /dev/null 2>&1 && print_success "Node2 → Border1: Connected" || print_warning "Node2 → Border1: Connection issues"
}

# Function to show system status
show_status() {
    print_status "DDARP WireGuard System Status:"
    echo ""

    # Container status
    echo "Container Status:"
    docker-compose -f "$PROJECT_DIR/docker-compose.wireguard.yml" ps

    echo ""
    echo "WireGuard Interface Status:"
    echo "Node1:"
    docker exec ddarp_node1_wg wg show 2>/dev/null || echo "  Not available"
    echo ""
    echo "Node2:"
    docker exec ddarp_node2_wg wg show 2>/dev/null || echo "  Not available"
    echo ""
    echo "Border1:"
    docker exec ddarp_border1_wg wg show 2>/dev/null || echo "  Not available"

    echo ""
    echo "API Endpoints:"
    echo "  Node1:   http://localhost:8001"
    echo "  Node2:   http://localhost:8002"
    echo "  Border1: http://localhost:8003"
    echo "  Prometheus: http://localhost:9090"
}

# Function to stop the system
stop_system() {
    print_status "Stopping DDARP WireGuard system..."
    cd "$PROJECT_DIR"
    docker-compose -f docker-compose.wireguard.yml down
    print_success "System stopped"
}

# Function to show help
show_help() {
    echo "DDARP WireGuard Setup Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup     - Complete setup: generate keys, update configs, start system"
    echo "  keys      - Generate WireGuard keys only"
    echo "  configs   - Update configuration files with keys"
    echo "  start     - Start the WireGuard-enabled system"
    echo "  stop      - Stop the system"
    echo "  restart   - Restart the system"
    echo "  peers     - Setup peer relationships"
    echo "  test      - Test system functionality"
    echo "  status    - Show system status"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup     # Complete setup from scratch"
    echo "  $0 test      # Test current system"
    echo "  $0 status    # Show current status"
}

# Main script logic
case "${1:-help}" in
    setup)
        check_wireguard
        generate_keys
        update_configs
        start_system
        setup_peers
        test_system
        print_success "DDARP WireGuard setup complete!"
        ;;
    keys)
        check_wireguard
        generate_keys
        ;;
    configs)
        update_configs
        ;;
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    restart)
        stop_system
        sleep 2
        start_system
        ;;
    peers)
        setup_peers
        ;;
    test)
        test_system
        ;;
    status)
        show_status
        ;;
    help|*)
        show_help
        ;;
esac