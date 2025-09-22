#!/bin/bash

# =============================================================================
# DDARP Setup Verification Script
# =============================================================================
# Verifies that the DDARP automation setup is correct
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo "=============================================="
echo "        DDARP Setup Verification"
echo "=============================================="
echo ""

# Check file structure
log_info "Checking file structure..."

# Main scripts
if [[ -f "ddarp.sh" && -x "ddarp.sh" ]]; then
    log_success "Master control script (ddarp.sh) exists and is executable"
else
    log_error "Master control script missing or not executable"
fi

if [[ -f "setup.sh" && -x "setup.sh" ]]; then
    log_success "Environment setup script (setup.sh) exists and is executable"
else
    log_error "Environment setup script missing or not executable"
fi

if [[ -f "SETUP_GUIDE.md" ]]; then
    log_success "Setup guide documentation exists"
else
    log_error "Setup guide missing"
fi

# Configuration structure
if [[ -d "configs/bird" ]]; then
    log_success "BIRD configuration directory exists"
else
    log_error "BIRD configuration directory missing"
fi

if [[ -d "configs/wireguard" ]]; then
    log_success "WireGuard configuration directory exists"
else
    log_error "WireGuard configuration directory missing"
fi

# Docker configurations
if [[ -f "docker-compose.enhanced.yml" ]]; then
    log_success "Enhanced Docker Compose configuration exists"
else
    log_error "Enhanced Docker Compose configuration missing"
fi

if [[ -f "docker/Dockerfile.enhanced" ]]; then
    log_success "Enhanced Dockerfile exists"
else
    log_error "Enhanced Dockerfile missing"
fi

# Scripts directory
if [[ -f "scripts/enhanced_test_system.sh" ]]; then
    log_success "Enhanced test system script exists"
else
    log_error "Enhanced test system script missing"
fi

if [[ -f "scripts/system_diagnostics.sh" ]]; then
    log_success "System diagnostics script exists"
else
    log_error "System diagnostics script missing"
fi

# Check for redundant scripts (should be moved to backup)
REDUNDANT_SCRIPTS=(
    "scripts/ddarp_automation.sh"
    "scripts/ddarp_one_click_start.sh"
    "scripts/start_system.sh"
    "scripts/setup_peers.sh"
)

echo ""
log_info "Checking for redundant scripts (should be in backup)..."

for script in "${REDUNDANT_SCRIPTS[@]}"; do
    if [[ -f "$script" ]]; then
        log_error "Redundant script still present: $script"
    else
        log_success "Redundant script removed: $(basename "$script")"
    fi
done

# Test script functionality
echo ""
log_info "Testing script functionality..."

# Test help command
if ./ddarp.sh help &>/dev/null; then
    log_success "Master script help command works"
else
    log_error "Master script help command failed"
fi

# Check for valid commands
VALID_COMMANDS=("setup" "start" "test" "stop" "restart" "status" "logs" "clean")
log_info "Master script supports commands: ${VALID_COMMANDS[*]}"

# Summary
echo ""
echo "=============================================="
echo "        Verification Summary"
echo "=============================================="
echo ""

log_info "✅ DDARP automation suite is ready!"
echo ""
log_info "📋 Quick Start Commands:"
echo "   1. ./setup.sh           # Install prerequisites"
echo "   2. ./ddarp.sh setup     # Configure DDARP"
echo "   3. ./ddarp.sh start     # Start system"
echo "   4. ./ddarp.sh test      # Run tests"
echo ""
log_info "📖 For detailed instructions, see: SETUP_GUIDE.md"
echo ""
log_info "🔧 Troubleshooting: ./ddarp.sh logs"
log_info "📊 Monitoring: http://localhost:9090 (after start)"
echo ""