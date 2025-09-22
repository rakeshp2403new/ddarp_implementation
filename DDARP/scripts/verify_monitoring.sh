#!/bin/bash

# =============================================================================
# DDARP Monitoring Verification Script
# =============================================================================
# This script verifies that all monitoring services are accessible
# and returns their health status.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== DDARP Monitoring Service Verification ===${NC}\n"

# Function to test HTTP endpoint
test_http_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"

    echo -n "Testing $name at $url... "

    if command -v curl >/dev/null 2>&1; then
        status_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")
        if [[ "$status_code" == "$expected_status" ]]; then
            echo -e "${GREEN}✓ HEALTHY${NC} (HTTP $status_code)"
            return 0
        else
            echo -e "${RED}✗ UNHEALTHY${NC} (HTTP $status_code)"
            return 1
        fi
    else
        echo -e "${YELLOW}? UNKNOWN${NC} (curl not available)"
        return 2
    fi
}

# Function to test TCP port
test_tcp_port() {
    local name="$1"
    local host="$2"
    local port="$3"

    echo -n "Testing $name at $host:$port... "

    if command -v nc >/dev/null 2>&1; then
        if nc -z "$host" "$port" 2>/dev/null; then
            echo -e "${GREEN}✓ REACHABLE${NC}"
            return 0
        else
            echo -e "${RED}✗ UNREACHABLE${NC}"
            return 1
        fi
    elif command -v telnet >/dev/null 2>&1; then
        if timeout 3 telnet "$host" "$port" </dev/null >/dev/null 2>&1; then
            echo -e "${GREEN}✓ REACHABLE${NC}"
            return 0
        else
            echo -e "${RED}✗ UNREACHABLE${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}? UNKNOWN${NC} (nc/telnet not available)"
        return 2
    fi
}

# Function to test WebSocket
test_websocket() {
    local name="$1"
    local url="$2"

    echo -n "Testing $name WebSocket at $url... "

    if command -v wscat >/dev/null 2>&1; then
        if timeout 3 wscat -c "$url" -x '{"type":"ping"}' >/dev/null 2>&1; then
            echo -e "${GREEN}✓ CONNECTED${NC}"
            return 0
        else
            echo -e "${RED}✗ FAILED${NC}"
            return 1
        fi
    else
        # Fallback to testing the port
        local port="${url##*:}"
        if nc -z localhost "$port" 2>/dev/null; then
            echo -e "${YELLOW}✓ PORT OPEN${NC} (wscat not available for full test)"
            return 0
        else
            echo -e "${RED}✗ PORT CLOSED${NC}"
            return 1
        fi
    fi
}

# Test counters
total_tests=0
passed_tests=0
failed_tests=0
unknown_tests=0

# Core Monitoring Services
echo -e "${BLUE}Core Monitoring Services:${NC}"

# Grafana
total_tests=$((total_tests + 1))
if test_http_endpoint "Grafana" "http://localhost:3000/api/health"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

# Prometheus
total_tests=$((total_tests + 1))
if test_http_endpoint "Prometheus" "http://localhost:9096/-/ready"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

# Kibana
total_tests=$((total_tests + 1))
if test_http_endpoint "Kibana" "http://localhost:5601/api/status"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

# Elasticsearch
total_tests=$((total_tests + 1))
if test_http_endpoint "Elasticsearch" "http://localhost:9200/_cluster/health"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

# Alertmanager
total_tests=$((total_tests + 1))
if test_http_endpoint "Alertmanager" "http://localhost:9095/-/ready"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

echo ""

# DDARP Nodes
echo -e "${BLUE}DDARP Node Services:${NC}"

# Node APIs
for i in 1 2 3; do
    port=$((8080 + i))
    total_tests=$((total_tests + 1))
    if test_http_endpoint "Node$i API" "http://localhost:$port/health"; then
        passed_tests=$((passed_tests + 1))
    elif [[ $? == 1 ]]; then
        failed_tests=$((failed_tests + 1))
    else
        unknown_tests=$((unknown_tests + 1))
    fi
done

# Node Prometheus endpoints
node_prometheus_ports=(9091 9092 9094)
for i in 0 1 2; do
    node_num=$((i + 1))
    port=${node_prometheus_ports[i]}
    total_tests=$((total_tests + 1))
    if test_http_endpoint "Node$node_num Metrics" "http://localhost:$port/metrics"; then
        passed_tests=$((passed_tests + 1))
    elif [[ $? == 1 ]]; then
        failed_tests=$((failed_tests + 1))
    else
        unknown_tests=$((unknown_tests + 1))
    fi
done

echo ""

# WebSocket Services
echo -e "${BLUE}Real-time Services:${NC}"

# Real-time pipeline
total_tests=$((total_tests + 1))
if test_websocket "Real-time Pipeline" "ws://localhost:8765"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

# Node WebSockets
for i in 1 2 3; do
    port=$((8765 + i))
    total_tests=$((total_tests + 1))
    if test_websocket "Node$i WebSocket" "ws://localhost:$port"; then
        passed_tests=$((passed_tests + 1))
    elif [[ $? == 1 ]]; then
        failed_tests=$((failed_tests + 1))
    else
        unknown_tests=$((unknown_tests + 1))
    fi
done

echo ""

# Additional Infrastructure
echo -e "${BLUE}Infrastructure Services:${NC}"

# Logstash
total_tests=$((total_tests + 1))
if test_tcp_port "Logstash TCP" "localhost" "5000"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

# Node Exporter
total_tests=$((total_tests + 1))
if test_http_endpoint "Node Exporter" "http://localhost:9100/metrics"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

# cAdvisor
total_tests=$((total_tests + 1))
if test_http_endpoint "cAdvisor" "http://localhost:8084/healthz"; then
    passed_tests=$((passed_tests + 1))
elif [[ $? == 1 ]]; then
    failed_tests=$((failed_tests + 1))
else
    unknown_tests=$((unknown_tests + 1))
fi

echo ""

# Summary
echo -e "${BLUE}=== VERIFICATION SUMMARY ===${NC}"
echo "Total tests: $total_tests"
echo -e "Passed: ${GREEN}$passed_tests${NC}"
echo -e "Failed: ${RED}$failed_tests${NC}"
echo -e "Unknown: ${YELLOW}$unknown_tests${NC}"

# Overall status
if [[ $failed_tests -eq 0 ]]; then
    echo -e "\n${GREEN}✓ All services are healthy!${NC}"
    exit 0
elif [[ $passed_tests -gt $failed_tests ]]; then
    echo -e "\n${YELLOW}⚠ Some services have issues${NC}"
    exit 1
else
    echo -e "\n${RED}✗ Major issues detected${NC}"
    exit 2
fi