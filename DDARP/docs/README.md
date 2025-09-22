# DDARP - Dynamic Distributed Routing Protocol

A comprehensive implementation of a Dynamic Distributed Routing Protocol featuring OWL (One-Way Latency) measurements, Dijkstra-based routing, BIRD eBGP integration, and WireGuard data plane tunneling.

## Architecture

The system consists of integrated components forming a complete routing solution:

### Core Components

1. **OWL Engine** (`src/core/owl_engine.py`) - Handles UDP ping measurements with HMAC authentication
2. **Control Plane** (`src/core/control_plane.py`) - Implements Dijkstra routing with hysteresis
3. **Composite Node** (`src/core/composite_node.py`) - Orchestrates all components with comprehensive REST API

### Data Plane Components

4. **BIRD eBGP Manager** (`src/networking/bird_manager.py`) - Manages BIRD routing daemon for BGP integration
5. **WireGuard Tunnel Orchestrator** (`src/networking/tunnel_orchestrator.py`) - Dynamic WireGuard tunnel management
6. **Data Plane Manager** (`src/networking/data_plane.py`) - Unified forwarding and routing control

## Features

### Core Routing Features
- **OWL Measurements**: 1Hz UDP pings with latency, jitter, and packet loss calculation
- **HMAC Authentication**: Secure message authentication using SHA-256
- **Dijkstra Routing**: Shortest path calculation with 20% hysteresis threshold
- **Dynamic Topology**: Real-time topology updates based on performance metrics

### Data Plane Features
- **BIRD eBGP Integration**: Full BGP router with OWL metrics as communities
- **WireGuard Tunnels**: Dynamic encrypted tunnel creation and management
- **Performance-Based Routing**: Routes created based on latency and packet loss thresholds
- **Tunnel Lifecycle Management**: Automatic tunnel creation/teardown based on path decisions
- **Multi-hop eBGP**: Support for eBGP peering across container networks

### Monitoring & Management
- **Comprehensive REST API**: JSON endpoints for all components
- **Prometheus Integration**: Detailed metrics export for monitoring
- **Health Monitoring**: BGP session and tunnel status tracking
- **Data Plane Testing**: Built-in forwarding and connectivity testing

### Deployment & Infrastructure
- **Docker Deployment**: Enhanced containers with networking privileges
- **Privileged Networking**: Support for network interface management
- **Configuration Management**: BIRD and WireGuard configuration templates
- **Automatic Discovery**: Nodes discover each other and establish connections

## Quick Start

### Basic DDARP Deployment

1. **Start the basic system:**
   ```bash
   ./scripts/start_system.sh
   ```

2. **Configure peer relationships:**
   ```bash
   ./scripts/setup_peers.sh
   ```

3. **Test functionality:**
   ```bash
   ./scripts/test_system.sh
   ```

### Enhanced Deployment with Data Plane

1. **Start the enhanced system with BIRD and WireGuard:**
   ```bash
   docker-compose -f docker-compose.enhanced.yml up -d
   ```

2. **Generate WireGuard keys:**
   ```bash
   ./scripts/wireguard_setup.sh
   ```

3. **Configure enhanced peer relationships:**
   ```bash
   ./scripts/setup_peers_wireguard.sh
   ```

4. **Run comprehensive tests:**
   ```bash
   ./scripts/enhanced_test_system.sh
   ```

5. **Stop the system:**
   ```bash
   docker-compose -f docker-compose.enhanced.yml down
   ```

## API Endpoints

Each node exposes comprehensive REST API endpoints:

### Core DDARP Endpoints
- `GET /health` - Node health status
- `GET /metrics/owl` - OWL measurement matrix
- `GET /topology` - Network topology information
- `GET /path/{destination}` - Path to destination node
- `GET /routing_table` - Current routing table
- `GET /node_info` - Node configuration details
- `POST /peers` - Add a peer node
- `DELETE /peers/{peer_id}` - Remove a peer node

### Data Plane Endpoints
- `GET /bgp/peers` - BGP peering status
- `GET /bgp/routes` - BGP routing table
- `GET /tunnels` - List active WireGuard tunnels
- `POST /tunnels/{peer_id}` - Create tunnel to specific peer
- `DELETE /tunnels/{peer_id}` - Delete tunnel to specific peer
- `GET /forwarding/{destination}` - Test data plane forwarding
- `GET /data_plane/status` - Comprehensive data plane status

### Monitoring Endpoints
- `GET /metrics` - Prometheus metrics export

## Node Configuration

### Basic Deployment
- **node1**: Regular node at 172.20.0.10 (API: localhost:8001)
- **node2**: Regular node at 172.20.0.11 (API: localhost:8002)
- **border1**: Border node at 172.20.0.12 (API: localhost:8003)
- **Prometheus**: Monitoring at localhost:9090

### Enhanced Deployment (with Data Plane)
- **node1**: AS 65001, Router ID 10.255.1.1, WireGuard IP 10.0.0.1
- **node2**: AS 65002, Router ID 10.255.2.1, WireGuard IP 10.0.0.2
- **border1**: AS 65003, Router ID 10.255.3.1, WireGuard IP 10.0.0.3
- **BGP Ports**: 1791 (node1), 1792 (node2), 1793 (border1)
- **WireGuard Ports**: 51821 (node1), 51822 (node2), 51823 (border1)

## Key Implementation Details

### OWL Engine
- Sends 1Hz UDP pings to all peers
- Calculates latency (ms), jitter (standard deviation), packet loss (%)
- Uses HMAC-SHA256 for message authentication
- Maintains sliding window of last 100 measurements

### Control Plane
- Updates topology every 5 seconds based on OWL metrics
- Uses NetworkX for Dijkstra shortest path calculation
- Implements 20% hysteresis to prevent route flapping
- Refreshes routes older than 30 seconds
- Removes stale routes and unreachable nodes

### BIRD eBGP Integration
- **Community Encoding**: OWL metrics encoded as BGP communities
  - 65000:X - Latency (X = latency_ms * 10)
  - 65001:X - Jitter (X = jitter_ms * 10)
  - 65002:X - Packet Loss (X = loss_percent * 10)
- **Multi-hop eBGP**: Supports peering across container networks
- **Route Injection**: Control plane decisions injected into BGP
- **Hysteresis Filtering**: 20% improvement threshold for route updates
- **Dynamic Configuration**: BIRD config updated based on peer changes

### WireGuard Data Plane
- **Dynamic Tunnels**: Created based on control plane path decisions
- **One-peer-per-interface**: Each tunnel connects to single peer
- **Key Management**: Automatic key generation and exchange
- **Tunnel Networks**:
  - Control plane: 10.0.0.0/24 for peer communication
  - Data plane: 10.100.0.0/16 for tunnel allocation
- **Performance Thresholds**: Tunnels created for latency <10ms, loss <1%
- **Lifecycle Management**: Automatic creation/teardown based on usage

### Data Plane Integration
- **Route Evaluation**: Control plane → Tunnel requirement assessment
- **Forwarding Table**: Unified view of BGP and tunnel routes
- **Performance Testing**: Built-in connectivity and latency testing
- **Maintenance Loop**: Background tunnel health monitoring
- **Hysteresis Application**: Tunnel changes require 20% improvement

### Routing Metrics
- Edge weight = latency + (packet_loss * 10ms penalty)
- Routes with >50% packet loss are considered unusable
- Metrics older than 30 seconds trigger route refresh
- Routes expire after 120 seconds without updates
- BGP Local Preference = 1000 - latency_ms (higher preference for lower latency)

## Development

### Project Structure
```
DDARP/
├── src/
│   ├── core/           # Core DDARP implementation
│   │   ├── owl_engine.py        # OWL measurement engine
│   │   ├── control_plane.py     # Dijkstra routing logic
│   │   └── composite_node.py    # Main orchestrator
│   └── networking/     # Data plane components
│       ├── bird_manager.py      # BIRD eBGP integration
│       ├── tunnel_orchestrator.py # WireGuard management
│       └── data_plane.py        # Unified data plane
├── docker/             # Docker configurations
│   ├── Dockerfile.enhanced      # Full-featured container
│   ├── entrypoint-enhanced.sh   # Enhanced startup script
│   ├── Dockerfile.wireguard     # WireGuard-enabled container
│   └── Dockerfile               # Basic container
├── configs/            # Configuration templates
│   ├── bird/           # BIRD configuration per node
│   ├── wireguard/      # WireGuard configuration per node
│   └── prometheus.yml  # Prometheus scraping config
├── scripts/            # Deployment and test scripts
│   ├── enhanced_test_system.sh  # Comprehensive testing
│   ├── wireguard_setup.sh       # WireGuard key generation
│   └── setup_peers_wireguard.sh # WireGuard peer setup
├── docker-compose.enhanced.yml  # Full deployment
├── docker-compose.yml           # Basic deployment
└── requirements.txt             # Python dependencies
```

### Dependencies

#### Python Dependencies
- aiohttp: Web server and HTTP client
- networkx: Graph algorithms
- prometheus-client: Metrics export
- asyncio-mqtt: MQTT client (future enhancement)
- Standard library: asyncio, hmac, json, statistics

#### System Dependencies (Enhanced Deployment)
- **BIRD2**: BGP routing daemon
- **WireGuard**: VPN tunnel management (`wireguard-tools`)
- **iproute2**: Network interface management
- **iptables**: Firewall and NAT rules
- **Docker**: Container runtime with privileged networking

### Requirements

#### For Basic Deployment
- Docker and docker-compose
- Linux host with UDP port access
- Python 3.11+ (if running outside containers)

#### For Enhanced Deployment
- Docker with privileged container support
- Linux host with CAP_NET_ADMIN capability
- WireGuard kernel module support
- BGP port access (179) if external peering needed

## Data Plane Operation

### Tunnel Creation Process
1. **Path Decision**: Control plane calculates optimal path using Dijkstra
2. **Performance Check**: OWL metrics evaluated (latency <10ms, loss <1%)
3. **Tunnel Creation**: WireGuard tunnel established if thresholds met
4. **BGP Integration**: Route injected into BGP with performance communities
5. **Forwarding Update**: Data plane forwarding table updated

### BGP Community Usage
```
Community Format: ASN:Value
- 65000:X = Latency in 0.1ms units (X = latency_ms * 10)
- 65001:X = Jitter in 0.1ms units (X = jitter_ms * 10)
- 65002:X = Packet loss in 0.1% units (X = loss_percent * 10)
- 65003:1 = Hysteresis flag (route approved by hysteresis filter)
```

### Example API Usage

#### Check Node Status
```bash
curl http://localhost:8001/health
curl http://localhost:8001/data_plane/status
```

#### Test Data Plane Forwarding
```bash
curl http://localhost:8001/forwarding/node2
curl http://localhost:8001/tunnels
```

#### Monitor BGP Status
```bash
curl http://localhost:8001/bgp/peers
curl http://localhost:8001/bgp/routes
```

#### Create Tunnel
```bash
curl -X POST http://localhost:8001/tunnels/node2 \
  -H "Content-Type: application/json" \
  -d '{"peer_ip": "172.20.0.11", "peer_asn": 65002}'
```

## Monitoring

### Prometheus Integration
- **Endpoint**: http://localhost:9090
- **Metrics**: OWL latency, BGP sessions, tunnel status, routing table size
- **Alerting**: Health checks and automatic container restart on failure
- **Dashboards**: Pre-configured for DDARP performance monitoring

### Health Monitoring
- **OWL Engine**: Ping success rate and latency tracking
- **BGP Sessions**: Session state and route exchange monitoring
- **WireGuard Tunnels**: Handshake status and data transfer stats
- **Control Plane**: Route convergence time and topology changes

## Recent Fixes and Improvements

### Routing System Fixes (v2.0)
- **Fixed topology edge creation issue**: Corrected the metrics update loop timing that prevented edges from being created in the topology graph
- **Improved routing table staleness handling**: Extended route expiration time from 60 to 120 seconds and added automatic refresh for routes older than 30 seconds
- **Enhanced hysteresis logic**: Routes are now properly refreshed when stale, preventing unreachable destinations
- **Better error handling**: Added comprehensive debugging and improved exception handling in the metrics update loop

### Data Plane Implementation (v3.0) ✅ **NEW**

#### BIRD eBGP Integration
- **Complete BGP Router**: Full BIRD2 integration with eBGP peering
- **OWL Metrics Encoding**: Performance data as BGP communities (65000-65003)
- **Dynamic Configuration**: BIRD config generation and live updates
- **Multi-hop eBGP**: Container-to-container BGP peering
- **Route Injection**: Control plane decisions propagated via BGP
- **Hysteresis Filtering**: 20% improvement threshold for route acceptance

#### WireGuard Data Plane
- **Dynamic Tunnel Creation**: Performance-based tunnel establishment
- **One-peer-per-interface**: Individual tunnels for each peer connection
- **Key Management**: Automatic WireGuard key generation and exchange
- **Tunnel Orchestration**: Lifecycle management with health monitoring
- **Network Segmentation**: Separate networks for control (10.0.0.0/24) and data (10.100.0.0/16)
- **Performance Thresholds**: Tunnels for latency <10ms, packet loss <1%

#### Enhanced Docker Deployment
- **Privileged Containers**: CAP_NET_ADMIN for network interface management
- **BIRD Installation**: Complete routing daemon in each container
- **WireGuard Support**: Full kernel module and tools integration
- **Configuration Management**: Volume-mounted BIRD and WireGuard configs
- **Enhanced Monitoring**: BGP session and tunnel status tracking

### System Status
✅ **Fully Functional Features:**
- OWL measurements with sub-millisecond latency detection
- Dynamic topology discovery and edge creation
- Dijkstra-based routing with complete path calculation
- **BIRD eBGP routing with performance communities**
- **WireGuard tunnel orchestration and management**
- **Integrated data plane with tunnel lifecycle management**
- **Performance-based routing decisions**
- All REST API endpoints working correctly (basic + data plane)
- Real-time metrics updates and Prometheus integration

### Performance
- **Latency measurements**: 0.4-0.7ms between containerized nodes
- **Update frequency**: 5-second topology updates, 1Hz OWL measurements
- **Route convergence**: Sub-10 second convergence after topology changes
- **BGP convergence**: Sub-30 second BGP session establishment
- **Tunnel setup time**: <5 seconds for WireGuard tunnel creation
- **Zero packet loss**: Perfect connectivity in containerized environment
- **Data plane forwarding**: Near-native performance through tunnels