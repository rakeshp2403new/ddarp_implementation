#!/bin/bash

# DDARP System Diagnostics and Troubleshooting Script
# Comprehensive verification and problem detection

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

DOCKER_COMPOSE="/tmp/docker-compose"

# Diagnostic functions
check_prerequisites() {
    echo -e "${BLUE}=== Prerequisites Check ===${NC}"

    # Docker
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✅ Docker: Installed${NC}"
        if docker info >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Docker: Running${NC}"
        else
            echo -e "${RED}❌ Docker: Not running${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ Docker: Not installed${NC}"
        return 1
    fi

    # Docker Compose
    if [ -f "$DOCKER_COMPOSE" ]; then
        echo -e "${GREEN}✅ Docker Compose: Available at $DOCKER_COMPOSE${NC}"
    else
        echo -e "${YELLOW}⚠️ Docker Compose: Not found at $DOCKER_COMPOSE${NC}"
    fi

    # Python
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version)
        echo -e "${GREEN}✅ Python: $python_version${NC}"
    else
        echo -e "${RED}❌ Python3: Not installed${NC}"
        return 1
    fi

    # Network tools
    if command -v curl &> /dev/null; then
        echo -e "${GREEN}✅ Curl: Available${NC}"
    else
        echo -e "${RED}❌ Curl: Not available${NC}"
        return 1
    fi

    echo
}

check_containers() {
    echo -e "${BLUE}=== Container Status ===${NC}"

    if ! $DOCKER_COMPOSE ps &>/dev/null; then
        echo -e "${RED}❌ No containers found or docker-compose not accessible${NC}"
        return 1
    fi

    local containers_status=$($DOCKER_COMPOSE ps --format table)
    echo "$containers_status"
    echo

    # Individual container checks
    local expected_containers=("ddarp_node1" "ddarp_node2" "ddarp_border1" "ddarp_prometheus")
    for container in "${expected_containers[@]}"; do
        if $DOCKER_COMPOSE ps | grep -q "$container.*Up"; then
            echo -e "${GREEN}✅ $container: Running${NC}"
        else
            echo -e "${RED}❌ $container: Not running${NC}"
        fi
    done
    echo
}

check_ports() {
    echo -e "${BLUE}=== Port Accessibility ===${NC}"

    local ports=(8001 8002 8003 9090)
    local port_names=("node1-api" "node2-api" "border1-api" "prometheus")

    for i in "${!ports[@]}"; do
        local port=${ports[$i]}
        local name=${port_names[$i]}

        if curl -s --connect-timeout 5 "http://localhost:$port" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Port $port ($name): Accessible${NC}"
        else
            echo -e "${RED}❌ Port $port ($name): Not accessible${NC}"
        fi
    done
    echo
}

check_api_health() {
    echo -e "${BLUE}=== API Health Status ===${NC}"

    for port in 8001 8002 8003; do
        local node_name="node$((port-8000))"
        if [ "$port" = "8003" ]; then
            node_name="border1"
        fi

        echo -n "Testing $node_name (port $port): "

        local response=$(curl -s --connect-timeout 10 "http://localhost:$port/health" 2>/dev/null)
        local exit_code=$?

        if [ $exit_code -eq 0 ]; then
            if echo "$response" | grep -q '"status": "healthy"'; then
                echo -e "${GREEN}Healthy${NC}"

                # Extract additional info
                local peer_count=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('peer_count', 'N/A'))
except:
    print('N/A')
                " 2>/dev/null)

                echo "  └─ Peer count: $peer_count"
            else
                echo -e "${YELLOW}Unhealthy: $response${NC}"
            fi
        else
            echo -e "${RED}Connection failed${NC}"
        fi
    done
    echo
}

check_owl_metrics() {
    echo -e "${BLUE}=== OWL Metrics Analysis ===${NC}"

    for port in 8001 8002 8003; do
        local node_name="node$((port-8000))"
        if [ "$port" = "8003" ]; then
            node_name="border1"
        fi

        echo "Analyzing $node_name OWL metrics:"

        local response=$(curl -s --connect-timeout 10 "http://localhost:$port/metrics/owl" 2>/dev/null)

        if [ $? -eq 0 ] && [ -n "$response" ]; then
            local analysis=$(echo "$response" | python3 -c "
import json, sys, time
try:
    data = json.load(sys.stdin)
    matrix = data.get('metrics_matrix', {})
    current_time = time.time()

    total_peers = 0
    avg_latency = 0
    total_latency = 0
    min_latency = float('inf')
    max_latency = 0
    zero_loss_count = 0
    fresh_count = 0

    for src_node, destinations in matrix.items():
        for dest_node, metrics in destinations.items():
            total_peers += 1
            latency = metrics.get('latency_ms', 0)
            loss = metrics.get('packet_loss_percent', 0)
            last_updated = metrics.get('last_updated', 0)

            total_latency += latency
            min_latency = min(min_latency, latency)
            max_latency = max(max_latency, latency)

            if loss == 0:
                zero_loss_count += 1

            if current_time - last_updated < 30:
                fresh_count += 1

    if total_peers > 0:
        avg_latency = total_latency / total_peers
        print(f'{total_peers},{avg_latency:.2f},{min_latency:.2f},{max_latency:.2f},{zero_loss_count},{fresh_count}')
    else:
        print('0,0,0,0,0,0')

except Exception as e:
    print('error,error,error,error,error,error')
            " 2>/dev/null)

            IFS=',' read -r total avg_lat min_lat max_lat zero_loss fresh <<< "$analysis"

            if [ "$total" != "0" ] && [ "$total" != "error" ]; then
                echo -e "  ├─ Peer measurements: ${GREEN}$total${NC}"
                echo -e "  ├─ Latency: avg=${GREEN}${avg_lat}ms${NC}, min=${min_lat}ms, max=${max_lat}ms"
                echo -e "  ├─ Zero packet loss: ${GREEN}$zero_loss/$total${NC}"
                echo -e "  └─ Fresh measurements: ${GREEN}$fresh/$total${NC}"
            else
                echo -e "  └─ ${RED}No valid measurements${NC}"
            fi
        else
            echo -e "  └─ ${RED}Failed to retrieve metrics${NC}"
        fi
        echo
    done
}

check_topology() {
    echo -e "${BLUE}=== Topology Analysis ===${NC}"

    for port in 8001 8002 8003; do
        local node_name="node$((port-8000))"
        if [ "$port" = "8003" ]; then
            node_name="border1"
        fi

        echo "Analyzing $node_name topology:"

        local response=$(curl -s --connect-timeout 10 "http://localhost:$port/topology" 2>/dev/null)

        if [ $? -eq 0 ] && [ -n "$response" ]; then
            local analysis=$(echo "$response" | python3 -c "
import json, sys, time
try:
    data = json.load(sys.stdin)
    topology = data.get('topology', {})
    nodes = topology.get('nodes', [])
    edges = topology.get('edges', [])
    current_time = time.time()

    node_count = len(nodes)
    edge_count = len(edges)

    # Analyze node freshness
    fresh_nodes = 0
    stale_nodes = 0
    for node in nodes:
        last_seen = node.get('last_seen', 0)
        if current_time - last_seen < 300:  # 5 minutes
            fresh_nodes += 1
        else:
            stale_nodes += 1

    print(f'{node_count},{edge_count},{fresh_nodes},{stale_nodes}')

except Exception as e:
    print('error,error,error,error')
            " 2>/dev/null)

            IFS=',' read -r nodes edges fresh stale <<< "$analysis"

            if [ "$nodes" != "error" ]; then
                echo -e "  ├─ Nodes discovered: ${GREEN}$nodes${NC}"
                echo -e "  ├─ Edges created: ${YELLOW}$edges${NC}"
                echo -e "  ├─ Fresh nodes: ${GREEN}$fresh${NC}"
                echo -e "  └─ Stale nodes: ${RED}$stale${NC}"

                if [ "$edges" = "0" ] && [ "$nodes" -gt "1" ]; then
                    echo -e "  ${YELLOW}⚠️ No edges despite multiple nodes (known routing bug)${NC}"
                fi
            else
                echo -e "  └─ ${RED}Failed to analyze topology${NC}"
            fi
        else
            echo -e "  └─ ${RED}Failed to retrieve topology${NC}"
        fi
        echo
    done
}

check_routing() {
    echo -e "${BLUE}=== Routing Table Analysis ===${NC}"

    for port in 8001 8002 8003; do
        local node_name="node$((port-8000))"
        if [ "$port" = "8003" ]; then
            node_name="border1"
        fi

        echo "Checking $node_name routing table:"

        local response=$(curl -s --connect-timeout 10 "http://localhost:$port/routing_table" 2>/dev/null)

        if [ $? -eq 0 ] && [ -n "$response" ]; then
            local route_count=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    routing_table = data.get('routing_table', {})
    print(len(routing_table))
except:
    print('error')
            " 2>/dev/null)

            if [ "$route_count" != "error" ]; then
                if [ "$route_count" = "0" ]; then
                    echo -e "  └─ ${YELLOW}Empty routing table (expected due to edge creation bug)${NC}"
                else
                    echo -e "  └─ ${GREEN}$route_count routes available${NC}"
                fi
            else
                echo -e "  └─ ${RED}Failed to analyze routing table${NC}"
            fi
        else
            echo -e "  └─ ${RED}Failed to retrieve routing table${NC}"
        fi
    done
    echo
}

check_prometheus() {
    echo -e "${BLUE}=== Prometheus Status ===${NC}"

    if curl -s --connect-timeout 10 "http://localhost:9090" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Prometheus web interface: Accessible${NC}"

        # Check if Prometheus is scraping anything
        local targets_response=$(curl -s --connect-timeout 10 "http://localhost:9090/api/v1/targets" 2>/dev/null)
        if [ $? -eq 0 ]; then
            local active_targets=$(echo "$targets_response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    targets = data.get('data', {}).get('activeTargets', [])
    up_count = sum(1 for t in targets if t.get('health') == 'up')
    total_count = len(targets)
    print(f'{up_count},{total_count}')
except:
    print('error,error')
            " 2>/dev/null)

            IFS=',' read -r up_targets total_targets <<< "$active_targets"

            if [ "$up_targets" != "error" ]; then
                echo -e "  └─ Active targets: ${GREEN}$up_targets/$total_targets${NC}"
            else
                echo -e "  └─ ${YELLOW}Could not check target status${NC}"
            fi
        fi
    else
        echo -e "${RED}❌ Prometheus: Not accessible${NC}"
    fi
    echo
}

check_docker_logs() {
    echo -e "${BLUE}=== Recent Error Logs ===${NC}"

    local containers=("node1" "node2" "border1" "prometheus")

    for container in "${containers[@]}"; do
        echo "Checking $container for recent errors:"

        local error_count=$($DOCKER_COMPOSE logs --tail=50 "$container" 2>/dev/null | grep -i "error\|exception\|failed" | wc -l)

        if [ "$error_count" -gt 0 ]; then
            echo -e "  └─ ${RED}Found $error_count error messages${NC}"
            echo "  Recent errors:"
            $DOCKER_COMPOSE logs --tail=50 "$container" 2>/dev/null | grep -i "error\|exception\|failed" | tail -3 | sed 's/^/    /'
        else
            echo -e "  └─ ${GREEN}No recent errors found${NC}"
        fi
        echo
    done
}

generate_diagnostic_report() {
    echo -e "${PURPLE}=== DIAGNOSTIC SUMMARY ===${NC}"

    # System status
    echo "System Status:"
    local containers_up=$($DOCKER_COMPOSE ps | grep -c "Up" || echo "0")
    local containers_expected=4

    if [ "$containers_up" -eq "$containers_expected" ]; then
        echo "✅ All containers running ($containers_up/$containers_expected)"
    else
        echo "❌ Some containers not running ($containers_up/$containers_expected)"
    fi

    # API health
    local healthy_apis=0
    for port in 8001 8002 8003; do
        if curl -s "http://localhost:$port/health" | grep -q "healthy" 2>/dev/null; then
            ((healthy_apis++))
        fi
    done

    if [ "$healthy_apis" -eq 3 ]; then
        echo "✅ All APIs healthy (3/3)"
    else
        echo "❌ Some APIs unhealthy ($healthy_apis/3)"
    fi

    # OWL functionality
    local owl_working=0
    for port in 8001 8002 8003; do
        if curl -s "http://localhost:$port/metrics/owl" | grep -q "latency_ms" 2>/dev/null; then
            ((owl_working++))
        fi
    done

    if [ "$owl_working" -eq 3 ]; then
        echo "✅ OWL measurements working (3/3)"
    else
        echo "❌ OWL measurements issues ($owl_working/3)"
    fi

    # Known issues
    echo
    echo "Known Issues Status:"
    echo "🔴 Routing/Path Finding: Disabled (edge creation bug)"
    echo "🟡 Prometheus Metrics: Limited (JSON only, no Prometheus format)"

    echo
    echo "Recommendations:"
    if [ "$containers_up" -eq "$containers_expected" ] && [ "$healthy_apis" -eq 3 ] && [ "$owl_working" -eq 3 ]; then
        echo "✅ System is ready for OWL latency monitoring"
        echo "✅ All core functionality working except path routing"
        echo "💡 Use OWL metrics endpoints for latency analysis"
    else
        echo "⚠️ System has issues that need addressing"
        echo "💡 Check container logs and restart if necessary"
    fi
}

# Troubleshooting suggestions
show_troubleshooting() {
    echo -e "${PURPLE}=== TROUBLESHOOTING GUIDE ===${NC}"

    echo "Common Issues and Solutions:"
    echo
    echo "1. Containers not starting:"
    echo "   → Run: $DOCKER_COMPOSE down && $DOCKER_COMPOSE up -d"
    echo "   → Check: docker system df (disk space)"
    echo
    echo "2. APIs not responding:"
    echo "   → Wait 30 seconds after container start"
    echo "   → Check: $DOCKER_COMPOSE logs <service_name>"
    echo
    echo "3. No OWL measurements:"
    echo "   → Verify peer configuration: curl http://localhost:8001/node_info"
    echo "   → Re-run: ./scripts/setup_peers.sh"
    echo
    echo "4. Prometheus not working:"
    echo "   → Check config: cat configs/prometheus.yml"
    echo "   → Restart: $DOCKER_COMPOSE restart prometheus"
    echo
    echo "5. Path queries failing (expected):"
    echo "   → Known issue: edge creation bug in control plane"
    echo "   → Workaround: Use OWL metrics directly for connectivity info"
    echo
}

# Main function
main() {
    local mode=${1:-full}

    echo -e "${CYAN}DDARP System Diagnostics${NC}"
    echo "========================"
    echo

    case $mode in
        "quick"|"q")
            check_prerequisites
            check_containers
            check_api_health
            ;;
        "full"|"f"|*)
            check_prerequisites
            check_containers
            check_ports
            check_api_health
            check_owl_metrics
            check_topology
            check_routing
            check_prometheus
            check_docker_logs
            generate_diagnostic_report
            echo
            show_troubleshooting
            ;;
    esac
}

main "$@"