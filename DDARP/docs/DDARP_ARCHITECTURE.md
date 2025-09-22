# DDARP - Distributed Dynamic Adaptive Routing Protocol

## End-to-End Architecture Documentation

### Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Application Flow](#application-flow)
4. [Deployment Architecture](#deployment-architecture)
5. [Folder Structure](#folder-structure)
6. [Technology Stack](#technology-stack)
7. [Setup Guide](#setup-guide)
8. [API Documentation](#api-documentation)
9. [Monitoring & Observability](#monitoring--observability)
10. [Troubleshooting](#troubleshooting)

---

## Project Overview

**DDARP (Distributed Dynamic Adaptive Routing Protocol)** is an advanced network routing system that combines BGP (Border Gateway Protocol) with One-Way Latency (OWL) measurements to create intelligent, adaptive routing decisions. The system uses real-time network metrics to optimize traffic paths and provides comprehensive monitoring capabilities.

### Key Features
- **Dynamic BGP Routing**: Full mesh BGP topology with real-time route optimization
- **OWL Metrics**: One-Way Latency measurement engine for intelligent path selection
- **WireGuard Integration**: Secure VPN tunneling capabilities
- **Real-time Monitoring**: Prometheus metrics with Grafana dashboards
- **Container Orchestration**: Docker-based deployment with Docker Compose
- **RESTful APIs**: Comprehensive API interface for system control and monitoring

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DDARP DISTRIBUTED SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐               │
│  │    NODE 1   │◄────────┤    NODE 2   │────────►│    NODE 3   │               │
│  │  AS 65001   │         │  AS 65002   │         │  AS 65003   │               │
│  │172.20.0.10  │         │172.20.0.11  │         │172.20.0.12  │               │
│  └─────────────┘         └─────────────┘         └─────────────┘               │
│         │                        │                        │                    │
│         │              BGP Full Mesh Topology             │                    │
│         │                        │                        │                    │
│  ┌──────▼──────┐         ┌───────▼───────┐         ┌──────▼──────┐              │
│  │             │         │               │         │             │              │
│  │ ┌─────────┐ │         │ ┌─────────┐   │         │ ┌─────────┐ │              │
│  │ │OWL Eng. │ │         │ │OWL Eng. │   │         │ │OWL Eng. │ │              │
│  │ │Port 8080│ │         │ │Port 8080│   │         │ │Port 8080│ │              │
│  │ └─────────┘ │         │ └─────────┘   │         │ └─────────┘ │              │
│  │             │         │               │         │             │              │
│  │ ┌─────────┐ │         │ ┌─────────┐   │         │ ┌─────────┐ │              │
│  │ │BIRD BGP │ │         │ │BIRD BGP │   │         │ │BIRD BGP │ │              │
│  │ │Port 179 │ │         │ │Port 179 │   │         │ │Port 179 │ │              │
│  │ └─────────┘ │         │ └─────────┘   │         │ └─────────┘ │              │
│  │             │         │               │         │             │              │
│  │ ┌─────────┐ │         │ ┌─────────┐   │         │ ┌─────────┐ │              │
│  │ │WireGuard│ │         │ │WireGuard│   │         │ │WireGuard│ │              │
│  │ │Port51820│ │         │ │Port51820│   │         │ │Port51820│ │              │
│  │ └─────────┘ │         │ └─────────┘   │         │ └─────────┘ │              │
│  │             │         │               │         │             │              │
│  │ ┌─────────┐ │         │ ┌─────────┐   │         │ ┌─────────┐ │              │
│  │ │REST API │ │         │ │REST API │   │         │ │REST API │ │              │
│  │ │Port 8081│ │         │ │Port 8082│   │         │ │Port 8083│ │              │
│  │ └─────────┘ │         │ └─────────┘   │         │ └─────────┘ │              │
│  └─────────────┘         └───────────────┘         └─────────────┘              │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                            MONITORING STACK                                     │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐               │
│  │ PROMETHEUS  │         │   GRAFANA   │         │  REAL-TIME  │               │
│  │   :9090     │◄────────┤    :3000    │         │ WEBSOCKETS  │               │
│  │             │         │             │         │    :8765    │               │
│  │ Metrics     │         │ Dashboards  │         │ Data Stream │               │
│  │ Collection  │         │ & Alerts    │         │ Pipeline    │               │
│  └─────────────┘         └─────────────┘         └─────────────┘               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DDARP NODE INTERNAL ARCHITECTURE         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 APPLICATION LAYER                       │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │ │
│  │  │   REST API  │    │ WebSocket   │    │ Prometheus  │  │ │
│  │  │   Server    │    │   Server    │    │  Exporter   │  │ │
│  │  │  (aiohttp)  │    │(websockets) │    │ (metrics)   │  │ │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  CONTROL PLANE                          │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │ │
│  │  │  Topology   │    │   Routing   │    │    Peer     │  │ │
│  │  │  Manager    │    │   Engine    │    │  Manager    │  │ │
│  │  │             │    │             │    │             │  │ │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   DATA PLANE                            │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │ │
│  │  │    BIRD     │    │  WireGuard  │    │     OWL     │  │ │
│  │  │ BGP Daemon  │    │   Tunnel    │    │   Engine    │  │ │
│  │  │             │    │ Orchestrator│    │             │  │ │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 NETWORK LAYER                           │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │ │
│  │  │   Docker    │    │  Container  │    │   Host OS   │  │ │
│  │  │  Networking │    │  Interfaces │    │  Networking │  │ │
│  │  │             │    │             │    │             │  │ │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Application Flow

### 1. System Initialization Flow

```
START
  │
  ├─► [1] Environment Preparation
  │     ├─ Clean existing containers
  │     ├─ Validate Docker setup
  │     └─ Prepare configuration files
  │
  ├─► [2] Container Orchestration
  │     ├─ Deploy DDARP nodes (1, 2, 3)
  │     ├─ Deploy monitoring stack
  │     └─ Initialize network bridges
  │
  ├─► [3] Service Initialization
  │     ├─ Start BGP daemons (BIRD)
  │     ├─ Initialize OWL engines
  │     ├─ Start REST API servers
  │     └─ Launch WebSocket servers
  │
  ├─► [4] Network Topology Discovery
  │     ├─ Register peer relationships
  │     ├─ Establish BGP sessions
  │     ├─ Configure WireGuard tunnels
  │     └─ Wait for convergence
  │
  ├─► [5] Monitoring Activation
  │     ├─ Start Prometheus scraping
  │     ├─ Initialize Grafana dashboards
  │     └─ Enable real-time metrics
  │
  └─► [6] System Validation
        ├─ Health check all endpoints
        ├─ Verify BGP sessions
        ├─ Test OWL measurements
        └─ Confirm monitoring
```

### 2. Runtime Operation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTINUOUS OPERATION CYCLE               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │    OWL      │    │  TOPOLOGY   │    │   ROUTING   │      │
│  │ MEASUREMENT │───►│   UPDATE    │───►│ OPTIMIZATION │      │
│  │             │    │             │    │             │      │
│  │ • Latency   │    │ • Weight    │    │ • Path      │      │
│  │ • Jitter    │    │   Updates   │    │   Selection │      │
│  │ • Loss      │    │ • Graph     │    │ • BGP       │      │
│  │   Rate      │    │   Rebuild   │    │   Updates   │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│        │                   │                   │            │
│        │            ┌─────────────┐           │            │
│        │            │ MONITORING  │           │            │
│        └───────────►│  & METRICS  │◄──────────┘            │
│                     │             │                        │
│                     │ • Prometheus│                        │
│                     │ • Grafana   │                        │
│                     │ • WebSocket │                        │
│                     │ • REST APIs │                        │
│                     └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 3. BGP Convergence Process

```
Initial State: All nodes isolated
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: BGP Session Establishment                         │
│  Node1 ◄──── TCP:179 ────► Node2 ◄──── TCP:179 ────► Node3 │
│    │                         │                         │   │
│    └─────────── TCP:179 ─────┘                         │   │
│    └─────────────────── TCP:179 ───────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: Route Advertisement                               │
│  • Each node advertises its local networks                  │
│  • BGP UPDATE messages exchanged                           │
│  • Routing Information Base (RIB) populated                │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: OWL Integration                                   │
│  • OWL measurements start                                   │
│  • Real-time latency data collected                        │
│  • BGP weights updated based on OWL metrics                │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
Final State: Optimized routing with real-time metrics
```

---

## Deployment Architecture

### Container Network Topology

```
Host System (Docker Host)
├─ Docker Network: ddarp_network (172.20.0.0/16)
│  ├─ ddarp-node1    (172.20.0.10) → Ports: 8081, 9091, 8766, 1791
│  ├─ ddarp-node2    (172.20.0.11) → Ports: 8082, 9092, 8767, 1792
│  ├─ ddarp-node3    (172.20.0.12) → Ports: 8083, 9093, 8768, 1793
│  ├─ prometheus     (172.20.0.20) → Port:  9090
│  └─ grafana        (172.20.0.21) → Port:  3000
└─ Host Network Interfaces
   ├─ eth0 (External connectivity)
   ├─ docker0 (Docker bridge)
   └─ br-* (Custom bridge for DDARP)
```

### Port Mapping

| Service | Container Port | Host Port | Protocol | Purpose |
|---------|---------------|-----------|----------|---------|
| node1 API | 8080 | 8081 | HTTP | REST API & Health |
| node1 Prometheus | 9090 | 9091 | HTTP | Metrics Export |
| node1 WebSocket | 8765 | 8766 | WS | Real-time Data |
| node1 BGP | 179 | 1791 | TCP | BGP Protocol |
| node2 API | 8080 | 8082 | HTTP | REST API & Health |
| node2 Prometheus | 9090 | 9092 | HTTP | Metrics Export |
| node2 WebSocket | 8765 | 8767 | WS | Real-time Data |
| node2 BGP | 179 | 1792 | TCP | BGP Protocol |
| node3 API | 8080 | 8083 | HTTP | REST API & Health |
| node3 Prometheus | 9090 | 9093 | HTTP | Metrics Export |
| node3 WebSocket | 8765 | 8768 | WS | Real-time Data |
| node3 BGP | 179 | 1793 | TCP | BGP Protocol |
| Prometheus | 9090 | 9090 | HTTP | Metrics Collection |
| Grafana | 3000 | 3000 | HTTP | Dashboard UI |

---

## Folder Structure

```
DDARP/
├── ddarp.sh                    # Main control script
├── DDARP_ARCHITECTURE.md       # This documentation
├── README.md                   # Quick start guide
│
├── src/                        # Python source code
│   ├── main.py                 # Application entry point
│   ├── core/                   # Core system components
│   │   ├── __init__.py
│   │   ├── composite_node.py   # Main node orchestrator
│   │   ├── control_plane.py    # Control plane logic
│   │   ├── data_plane.py       # Data plane management
│   │   ├── owl_engine.py       # OWL measurement engine
│   │   └── routing_engine.py   # Routing optimization
│   │
│   ├── monitoring/             # Monitoring & observability
│   │   ├── __init__.py
│   │   ├── prometheus_exporter.py    # Metrics exporter
│   │   ├── structured_logger.py      # Logging system
│   │   └── realtime_pipeline.py      # WebSocket data pipeline
│   │
│   ├── network/                # Networking components
│   │   ├── __init__.py
│   │   ├── bgp_manager.py      # BGP protocol handling
│   │   ├── bird_manager.py     # BIRD daemon integration
│   │   └── tunnel_orchestrator.py    # WireGuard management
│   │
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       ├── config.py           # Configuration management
│       └── helpers.py          # Helper functions
│
├── deploy/                     # Deployment configurations
│   ├── docker-compose.simple.yml      # Basic 3-node setup
│   ├── docker-compose.monitoring.yml  # Full monitoring stack
│   └── docker-compose.enhanced.yml    # Advanced features
│
├── docker/                     # Docker build files
│   ├── Dockerfile              # Main DDARP container
│   ├── Dockerfile.realtime     # Real-time pipeline
│   └── start.sh               # Container startup script
│
├── configs/                    # Configuration files
│   ├── node1/                  # Node 1 configuration
│   │   ├── ddarp.yml
│   │   └── logging.yml
│   ├── node2/                  # Node 2 configuration
│   ├── node3/                  # Node 3 configuration
│   ├── bird/                   # BIRD BGP configurations
│   │   ├── node1.conf
│   │   ├── node2.conf
│   │   └── node3.conf
│   ├── wireguard/              # WireGuard keys & configs
│   │   ├── node1/
│   │   ├── node2/
│   │   └── node3/
│   ├── prometheus/             # Prometheus configuration
│   │   ├── prometheus.yml
│   │   └── rules/
│   └── grafana/                # Grafana dashboards
│       ├── provisioning/
│       └── dashboards/
│
├── scripts/                    # Utility scripts
│   ├── setup.sh               # System setup
│   ├── enhanced_test_system.sh # Comprehensive testing
│   ├── system_diagnostics.sh   # System diagnostics
│   └── verify_monitoring.sh    # Monitoring verification
│
├── logs/                       # Log files
│   ├── node1/
│   ├── node2/
│   └── node3/
│
└── docs/                       # Additional documentation
    ├── api_reference.md        # API documentation
    ├── troubleshooting.md      # Common issues & solutions
    └── development.md          # Development guidelines
```

---

## Technology Stack

### Core Technologies

| Technology | Version | Purpose | Why We Use It |
|------------|---------|---------|---------------|
| **Python** | 3.9+ | Application Runtime | Excellent asyncio support, rich networking libraries |
| **Docker** | 20.10+ | Containerization | Consistent deployment, isolation, scalability |
| **Docker Compose** | 1.29+ | Orchestration | Multi-container management, networking |
| **BIRD** | 2.0+ | BGP Daemon | Production-grade BGP implementation |
| **WireGuard** | 1.0+ | VPN Tunneling | Modern, secure, high-performance VPN |

### Python Libraries

| Library | Purpose | Why We Use It |
|---------|---------|---------------|
| **aiohttp** | Async HTTP Server/Client | High-performance async web framework |
| **asyncio** | Asynchronous Programming | Non-blocking I/O for network operations |
| **websockets** | WebSocket Server | Real-time data streaming |
| **prometheus_client** | Metrics Export | Industry-standard metrics format |
| **pyyaml** | Configuration Parsing | Human-readable configuration files |
| **uvloop** | Event Loop | Faster asyncio event loop implementation |

### Monitoring Stack

| Technology | Purpose | Why We Use It |
|------------|---------|---------------|
| **Prometheus** | Metrics Collection | Time-series database, powerful querying |
| **Grafana** | Visualization | Rich dashboards, alerting capabilities |
| **cAdvisor** | Container Metrics | Docker container resource monitoring |
| **Node Exporter** | System Metrics | Host system monitoring |

### Network Protocols

| Protocol | Purpose | Implementation |
|----------|---------|----------------|
| **BGP-4** | Routing Protocol | BIRD daemon with custom route optimization |
| **OWL** | Latency Measurement | Custom UDP-based measurement protocol |
| **WireGuard** | VPN Tunneling | Kernel-level secure tunneling |
| **WebSocket** | Real-time Communication | Async WebSocket server for live data |

---

## Setup Guide

### Prerequisites

```bash
# System Requirements
- Ubuntu 20.04+ / CentOS 8+ / Fedora 32+
- Docker 20.10+
- Docker Compose 1.29+
- Python 3.9+ (for development)
- 4GB RAM minimum
- 10GB disk space
```

### Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd DDARP

# 2. Make the control script executable
chmod +x ddarp.sh

# 3. One-command setup and start
./ddarp.sh auto-install

# 4. Verify the system
./ddarp.sh test
```

### Manual Setup

```bash
# 1. Install Docker (if not present)
./ddarp.sh install-docker

# 2. Setup the system
./ddarp.sh setup

# 3. Start the DDARP system
./ddarp.sh start

# 4. Monitor the deployment
./ddarp.sh status

# 5. View logs
./ddarp.sh logs node1
```

### Development Setup

```bash
# 1. Create Python virtual environment
python3 -m venv ddarp-env
source ddarp-env/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install development dependencies
pip install -r requirements-dev.txt

# 4. Run tests
pytest tests/

# 5. Start development server
python src/main.py
```

### Configuration

```yaml
# configs/node1/ddarp.yml
node:
  id: "node1"
  type: "regular"
  asn: 65001
  router_id: "10.255.1.1"

networking:
  api_port: 8080
  bgp_port: 179
  owl_port: 8080
  websocket_port: 8765

peers:
  - id: "node2"
    ip: "172.20.0.11"
    asn: 65002
  - id: "node3"
    ip: "172.20.0.12"
    asn: 65003

monitoring:
  prometheus_enabled: true
  logging_level: "INFO"
  metrics_interval: 5
```

---

## API Documentation

### Health Check
```http
GET /health
Response: {
  "status": "healthy",
  "node_id": "node1",
  "node_type": "regular",
  "owl_engine_running": true,
  "control_plane_running": true,
  "peer_count": 2,
  "uptime": "15m30s"
}
```

### Node Information
```http
GET /node_info
Response: {
  "node_id": "node1",
  "node_type": "regular",
  "asn": 65001,
  "router_id": "10.255.1.1",
  "version": "1.0.0",
  "started_at": "2025-09-22T19:16:46Z"
}
```

### OWL Metrics
```http
GET /metrics/owl
Response: {
  "metrics_matrix": {
    "node2": {
      "latency_ms": 0.75,
      "jitter_ms": 0.05,
      "packet_loss": 0.0,
      "timestamp": "2025-09-22T19:31:35Z"
    },
    "node3": {
      "latency_ms": 0.65,
      "jitter_ms": 0.03,
      "packet_loss": 0.0,
      "timestamp": "2025-09-22T19:31:35Z"
    }
  }
}
```

### Topology Information
```http
GET /topology
Response: {
  "topology": {
    "node_count": 3,
    "edge_count": 6,
    "nodes": ["node1", "node2", "node3"],
    "edges": [
      {"source": "node1", "target": "node2", "weight": 0.75},
      {"source": "node1", "target": "node3", "weight": 0.65},
      {"source": "node2", "target": "node3", "weight": 0.80}
    ]
  }
}
```

### BGP Peers
```http
GET /bgp/peers
Response: {
  "bgp_peers": [
    {
      "peer_id": "node2",
      "peer_ip": "172.20.0.11",
      "peer_asn": 65002,
      "state": "established",
      "uptime": "14m25s"
    },
    {
      "peer_id": "node3",
      "peer_ip": "172.20.0.12",
      "peer_asn": 65003,
      "state": "established",
      "uptime": "14m20s"
    }
  ]
}
```

### Peer Management
```http
POST /peers
Content-Type: application/json
{
  "peer_id": "node4",
  "peer_ip": "172.20.0.13",
  "peer_type": "regular"
}
```

### Tunnel Management
```http
POST /tunnels/node2
Content-Type: application/json
{
  "endpoint": "172.20.0.11:51820",
  "public_key": "optional_wireguard_public_key"
}
```

---

## Monitoring & Observability

### Prometheus Metrics

**Node Health Metrics:**
- `ddarp_node_up{node_id}` - Node operational status
- `ddarp_peer_count{node_id}` - Number of connected peers
- `ddarp_bgp_sessions{node_id,state}` - BGP session states

**OWL Metrics:**
- `ddarp_owl_latency_ms{source,destination}` - One-way latency
- `ddarp_owl_jitter_ms{source,destination}` - Latency jitter
- `ddarp_owl_packet_loss{source,destination}` - Packet loss rate

**System Metrics:**
- `ddarp_api_requests_total{method,endpoint}` - API usage
- `ddarp_topology_updates_total{node_id}` - Topology changes
- `ddarp_tunnel_count{node_id,state}` - WireGuard tunnel status

### Grafana Dashboards

**DDARP Overview Dashboard:**
- System health summary
- Network topology visualization
- Performance metrics overview

**Network Performance Dashboard:**
- OWL latency trends
- BGP convergence metrics
- Traffic flow analysis

**System Resources Dashboard:**
- Container resource usage
- Network interface statistics
- Storage and memory utilization

### Log Analysis

**Application Logs:**
```bash
# View real-time logs
./ddarp.sh logs node1

# Filter specific log levels
./ddarp.sh logs node1 | grep ERROR

# Monitor BGP events
./ddarp.sh logs node1 | grep "BGP"
```

**System Diagnostics:**
```bash
# Run comprehensive diagnostics
./scripts/system_diagnostics.sh

# Check network connectivity
./scripts/verify_monitoring.sh
```

---

## Troubleshooting

### Common Issues

**1. Docker Permission Denied**
```bash
# Error: Permission denied (Docker socket)
# Solution: Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**2. BGP Sessions Not Establishing**
```bash
# Check BGP configuration
./ddarp.sh logs node1 | grep "bird"

# Verify network connectivity
docker exec ddarp-node1 ping 172.20.0.11
```

**3. OWL Measurements Failing**
```bash
# Check UDP connectivity
docker exec ddarp-node1 netstat -un | grep 8080

# Verify firewall rules
sudo ufw status
```

**4. High Memory Usage**
```bash
# Monitor container resources
docker stats ddarp-node1

# Adjust memory limits in docker-compose.yml
```

### Debugging Commands

```bash
# System status overview
./ddarp.sh status

# Run comprehensive tests
./ddarp.sh test

# View specific service logs
./ddarp.sh logs prometheus

# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Network troubleshooting
docker network inspect deploy_ddarp_network

# BGP session debugging
docker exec ddarp-node1 birdc show protocols
```

### Performance Tuning

**Memory Optimization:**
```yaml
# docker-compose.yml
services:
  ddarp-node1:
    mem_limit: 512m
    memswap_limit: 512m
```

**Network Optimization:**
```yaml
# Increase buffer sizes
sysctls:
  - net.core.rmem_max=16777216
  - net.core.wmem_max=16777216
```

**BGP Optimization:**
```bash
# BIRD configuration tuning
# /configs/bird/node1.conf
protocol bgp node2 {
    neighbor 172.20.0.11 as 65002;
    hold time 180;
    keepalive time 60;
    connect retry time 30;
}
```

---

## Command Reference

### DDARP Control Script

```bash
# Core Operations
./ddarp.sh start          # Start the DDARP system
./ddarp.sh stop           # Stop the system
./ddarp.sh restart        # Restart the system
./ddarp.sh status         # Show system status
./ddarp.sh test           # Run system tests

# Setup & Installation
./ddarp.sh setup          # Setup system (first time)
./ddarp.sh auto-install   # One-click setup and start
./ddarp.sh install-docker # Install Docker if missing

# Monitoring & Debugging
./ddarp.sh logs           # Show all service logs
./ddarp.sh logs node1     # Show specific node logs
./ddarp.sh logs prometheus # Show Prometheus logs

# Maintenance
./ddarp.sh clean          # Clean up completely
./ddarp.sh help           # Show help information
```

### System Access URLs

```bash
# Node APIs
curl http://localhost:8081/health  # Node 1 health
curl http://localhost:8082/health  # Node 2 health
curl http://localhost:8083/health  # Node 3 health

# Monitoring
http://localhost:9090              # Prometheus
http://localhost:3000              # Grafana (admin/ddarp2023)

# Real-time Data
ws://localhost:8766                # Node 1 WebSocket
ws://localhost:8767                # Node 2 WebSocket
ws://localhost:8768                # Node 3 WebSocket
```

---

## Security Considerations

### Network Security
- All inter-node communication encrypted with WireGuard
- BGP sessions authenticated with MD5 (configurable)
- API endpoints with optional authentication
- Container network isolation

### Access Control
- Grafana admin credentials: `admin/ddarp2023`
- API rate limiting enabled
- Container privilege escalation disabled where possible
- Read-only filesystem mounts for security

### Monitoring Security
- Prometheus metrics scraping over internal network only
- WebSocket connections authenticated
- Log rotation and retention policies
- Sensitive data filtering in logs

---

This comprehensive documentation provides a complete overview of the DDARP system architecture, deployment, and operation. For additional information, refer to the specific documentation files in the `docs/` directory.