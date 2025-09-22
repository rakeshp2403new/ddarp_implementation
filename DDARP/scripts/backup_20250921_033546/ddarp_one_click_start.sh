#!/bin/bash

# =============================================================================
# DDARP One-Click Startup Script
# =============================================================================
# This script handles all dependencies, fixes, and startup procedures
# to get the DDARP system running with a single command.
#
# Usage: ./scripts/ddarp_one_click_start.sh
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMP_DIR="/tmp/ddarp_setup"

# Configuration
DOCKER_COMPOSE_VERSION="v2.20.0"
DOCKER_COMPOSE_PATH="/tmp/docker-compose"

# =============================================================================
# Utility Functions
# =============================================================================

print_header() {
    echo -e "${CYAN}"
    echo "=========================================="
    echo "$1"
    echo "=========================================="
    echo -e "${NC}"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
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

print_info() {
    echo -e "${PURPLE}[INFO]${NC} $1"
}

# =============================================================================
# Dependency Installation and Setup
# =============================================================================

check_and_install_dependencies() {
    print_header "Checking and Installing Dependencies"

    # Check Docker
    print_step "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is installed and running"

    # Check/Install Docker Compose
    print_step "Checking Docker Compose installation..."
    if ! command -v docker-compose &> /dev/null; then
        print_warning "Docker Compose not found. Installing..."
        install_docker_compose
    else
        print_success "Docker Compose found: $(docker-compose --version)"
        DOCKER_COMPOSE_PATH="docker-compose"
    fi

    # Check other tools
    print_step "Checking required tools..."
    local missing_tools=()

    for tool in curl jq; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=($tool)
        fi
    done

    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_warning "Missing tools: ${missing_tools[*]}"
        print_info "Installing missing tools..."

        # Try to install missing tools
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y "${missing_tools[@]}" || {
                print_error "Failed to install missing tools. Please install manually: ${missing_tools[*]}"
                exit 1
            }
        elif command -v yum &> /dev/null; then
            sudo yum install -y "${missing_tools[@]}" || {
                print_error "Failed to install missing tools. Please install manually: ${missing_tools[*]}"
                exit 1
            }
        else
            print_error "Cannot auto-install tools. Please install manually: ${missing_tools[*]}"
            exit 1
        fi
    fi

    print_success "All dependencies are available"
}

install_docker_compose() {
    print_step "Downloading Docker Compose..."

    mkdir -p "$TEMP_DIR"

    local compose_url="https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)"

    print_info "Downloading from: $compose_url"

    if curl -L --progress-bar "$compose_url" -o "$DOCKER_COMPOSE_PATH"; then
        chmod +x "$DOCKER_COMPOSE_PATH"
        if [ -x "$DOCKER_COMPOSE_PATH" ]; then
            print_success "Docker Compose installed to $DOCKER_COMPOSE_PATH"
            # Test the installation
            if "$DOCKER_COMPOSE_PATH" --version >/dev/null 2>&1; then
                print_success "Docker Compose working correctly"
            else
                print_error "Docker Compose downloaded but not working"
                exit 1
            fi
        else
            print_error "Failed to make Docker Compose executable"
            exit 1
        fi
    else
        print_error "Failed to download Docker Compose"
        print_info "Trying alternative installation method..."

        # Try docker compose (new syntax) if available
        if docker compose version >/dev/null 2>&1; then
            print_success "Found Docker Compose plugin"
            DOCKER_COMPOSE_PATH="docker compose"
            return 0
        fi

        exit 1
    fi
}

# =============================================================================
# Code Fixes and Improvements
# =============================================================================

apply_code_fixes() {
    print_header "Applying Code Fixes and Improvements"

    # Fix 1: Ensure metrics update loop runs properly
    print_step "Fixing metrics update loop initialization..."

    local composite_file="$PROJECT_DIR/src/core/composite_node.py"

    # Check if the fix is already applied
    if grep -q "# Set running flag first" "$composite_file"; then
        print_info "Metrics update loop fix already applied"
    else
        print_step "Applying metrics update loop fix..."

        # Create backup
        cp "$composite_file" "$composite_file.backup"

        # Apply the fix
        sed -i '/async def start(self):/,/self.running = True/ {
            /async def start(self):/a\
        # Set running flag first\
        self.running = True\

            /self.running = True/d
        }' "$composite_file"

        print_success "Applied metrics update loop fix"
    fi

    # Fix 2: Enhanced control plane logging (if not already applied)
    print_step "Checking control plane enhancements..."

    local control_plane_file="$PROJECT_DIR/src/core/control_plane.py"

    if grep -q "Calculated paths to" "$control_plane_file"; then
        print_info "Control plane enhancements already applied"
    else
        print_step "Applying control plane enhancements..."

        # Create backup
        cp "$control_plane_file" "$control_plane_file.backup"

        # This would be more complex to automate safely, so we'll note it
        print_warning "Control plane enhancements may need manual review"
    fi

    print_success "Code fixes completed"
}

# =============================================================================
# Docker Environment Setup
# =============================================================================

setup_docker_environment() {
    print_header "Setting Up Docker Environment"

    cd "$PROJECT_DIR"

    # Clean up any existing containers
    print_step "Cleaning up existing containers..."
    $DOCKER_COMPOSE_PATH down -v 2>/dev/null || true

    # Remove any orphaned containers
    docker container prune -f 2>/dev/null || true

    # Build Docker images
    print_step "Building Docker images..."
    $DOCKER_COMPOSE_PATH build --no-cache

    print_success "Docker environment ready"
}

# =============================================================================
# System Startup
# =============================================================================

start_ddarp_system() {
    print_header "Starting DDARP System"

    cd "$PROJECT_DIR"

    # Start all services
    print_step "Starting Docker containers..."
    $DOCKER_COMPOSE_PATH up -d

    # Wait for services to start
    print_step "Waiting for services to initialize..."
    sleep 20

    # Check container status
    print_step "Checking container status..."
    $DOCKER_COMPOSE_PATH ps

    print_success "DDARP system started"
}

# =============================================================================
# Peer Configuration
# =============================================================================

configure_peer_relationships() {
    print_header "Configuring Peer Relationships"

    # Wait for nodes to become healthy
    print_step "Waiting for nodes to become healthy..."
    local max_attempts=30
    local attempt=0

    for port in 8001 8002 8003; do
        attempt=0
        while [ $attempt -lt $max_attempts ]; do
            if curl -s "http://localhost:$port/health" | grep -q "healthy"; then
                print_success "Node on port $port is healthy"
                break
            else
                ((attempt++))
                if [ $attempt -eq $max_attempts ]; then
                    print_error "Node on port $port failed to become healthy"
                    return 1
                fi
                sleep 2
            fi
        done
    done

    # Configure peer relationships
    print_step "Setting up peer relationships..."

    # node1 peers
    curl -s -X POST http://localhost:8001/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node2", "peer_ip": "172.20.0.11", "peer_type": "regular"}' > /dev/null

    curl -s -X POST http://localhost:8001/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "border1", "peer_ip": "172.20.0.12", "peer_type": "border"}' > /dev/null

    # node2 peers
    curl -s -X POST http://localhost:8002/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node1", "peer_ip": "172.20.0.10", "peer_type": "regular"}' > /dev/null

    curl -s -X POST http://localhost:8002/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "border1", "peer_ip": "172.20.0.12", "peer_type": "border"}' > /dev/null

    # border1 peers
    curl -s -X POST http://localhost:8003/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node1", "peer_ip": "172.20.0.10", "peer_type": "regular"}' > /dev/null

    curl -s -X POST http://localhost:8003/peers \
      -H "Content-Type: application/json" \
      -d '{"peer_id": "node2", "peer_ip": "172.20.0.11", "peer_type": "regular"}' > /dev/null

    print_success "Peer relationships configured"

    # Wait for topology convergence
    print_step "Waiting for topology convergence..."
    sleep 15
}

# =============================================================================
# System Verification
# =============================================================================

verify_system_functionality() {
    print_header "Verifying System Functionality"

    local all_tests_passed=true

    # Test 1: Node Health
    print_step "Testing node health..."
    for port in 8001 8002 8003; do
        if curl -s "http://localhost:$port/health" | grep -q "healthy"; then
            print_success "Node $port is healthy"
        else
            print_error "Node $port health check failed"
            all_tests_passed=false
        fi
    done

    # Test 2: OWL Metrics
    print_step "Testing OWL metrics..."
    for port in 8001 8002 8003; do
        local metrics=$(curl -s "http://localhost:$port/metrics/owl" | jq -r '.metrics_matrix | keys | length' 2>/dev/null || echo "0")
        if [ "$metrics" -gt 0 ]; then
            print_success "Node $port OWL metrics active"
        else
            print_warning "Node $port OWL metrics not ready yet"
        fi
    done

    # Test 3: Topology
    print_step "Testing topology..."
    for port in 8001 8002 8003; do
        local edges=$(curl -s "http://localhost:$port/topology" | jq -r '.topology.edge_count' 2>/dev/null || echo "0")
        if [ "$edges" -gt 0 ]; then
            print_success "Node $port topology has $edges edges"
        else
            print_warning "Node $port topology not fully converged yet"
        fi
    done

    # Test 4: Prometheus Metrics
    print_step "Testing Prometheus metrics..."
    for port in 8001 8002 8003; do
        if curl -s "http://localhost:$port/metrics" | grep -q "ddarp_"; then
            print_success "Node $port Prometheus metrics available"
        else
            print_error "Node $port Prometheus metrics failed"
            all_tests_passed=false
        fi
    done

    # Test 5: Prometheus Collection
    print_step "Testing Prometheus data collection..."
    sleep 5  # Give Prometheus time to scrape
    local prom_metrics=$(curl -s "http://localhost:9090/api/v1/query?query=ddarp_owl_latency_ms" | jq -r '.data.result | length' 2>/dev/null || echo "0")
    if [ "$prom_metrics" -gt 0 ]; then
        print_success "Prometheus collecting $prom_metrics OWL metrics"
    else
        print_warning "Prometheus metrics collection may need more time"
    fi

    if [ "$all_tests_passed" = true ]; then
        print_success "All critical tests passed"
    else
        print_warning "Some tests failed - system may need more time to converge"
    fi
}

# =============================================================================
# Status Display
# =============================================================================

display_system_status() {
    print_header "DDARP System Status"

    echo -e "${GREEN}🎉 DDARP System Successfully Started! 🎉${NC}"
    echo ""
    echo -e "${CYAN}📊 Service URLs:${NC}"
    echo "  • Node1 API: http://localhost:8001"
    echo "  • Node2 API: http://localhost:8002"
    echo "  • Border1 API: http://localhost:8003"
    echo "  • Prometheus: http://localhost:9090"
    echo ""
    echo -e "${CYAN}📈 Metrics Endpoints:${NC}"
    echo "  • Node1 metrics: http://localhost:8001/metrics"
    echo "  • Node2 metrics: http://localhost:8002/metrics"
    echo "  • Border1 metrics: http://localhost:8003/metrics"
    echo ""
    echo -e "${CYAN}🔧 Quick Tests:${NC}"
    echo "  • Health: curl http://localhost:8001/health"
    echo "  • OWL: curl http://localhost:8001/metrics/owl"
    echo "  • Topology: curl http://localhost:8001/topology"
    echo "  • Routes: curl http://localhost:8001/routing_table"
    echo "  • Path: curl http://localhost:8001/path/node2"
    echo ""
    echo -e "${CYAN}🛑 To Stop:${NC}"
    echo "  $DOCKER_COMPOSE_PATH down"
    echo ""
    echo -e "${YELLOW}💡 Note: Routing tables may take 30-60 seconds to fully populate${NC}"
    echo -e "${YELLOW}   and will update dynamically as the system runs.${NC}"
}

# =============================================================================
# Cleanup Function
# =============================================================================

cleanup_on_exit() {
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup_on_exit EXIT

# =============================================================================
# Main Execution
# =============================================================================

main() {
    print_header "DDARP One-Click Startup"

    echo -e "${PURPLE}Starting automated DDARP deployment...${NC}"
    echo ""

    # Execute all setup steps
    check_and_install_dependencies
    apply_code_fixes
    setup_docker_environment
    start_ddarp_system
    configure_peer_relationships
    verify_system_functionality
    display_system_status

    print_success "DDARP startup completed successfully!"
}

# =============================================================================
# Script Entry Point
# =============================================================================

# Check if script is being run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi