# DDARP Quick Start Guide

## 🚀 One-Click Startup

The DDARP system now has fully automated startup that handles all dependencies, fixes, and configuration!

### Prerequisites

- **Docker** must be installed and running
- **Linux/Unix environment** (WSL, macOS, or native Linux)
- **Internet connection** (for downloading Docker Compose if needed)

### Start DDARP System

```bash
# From the DDARP project root directory:
./scripts/ddarp_one_click_start.sh
```

**That's it!** The script will automatically:

✅ Check and install Docker Compose if needed
✅ Apply all necessary code fixes
✅ Build Docker images
✅ Start all services
✅ Configure peer relationships
✅ Verify system functionality
✅ Display access URLs and status

### Stop DDARP System

```bash
./scripts/ddarp_stop.sh
```

## 🌐 Access Points

Once started, access these URLs:

| Service | URL | Description |
|---------|-----|-------------|
| **Node1 API** | http://localhost:8001 | Regular node REST API |
| **Node2 API** | http://localhost:8002 | Regular node REST API |
| **Border1 API** | http://localhost:8003 | Border node REST API |
| **Prometheus** | http://localhost:9090 | Metrics monitoring dashboard |

## 📊 API Endpoints

Each node exposes these endpoints:

| Endpoint | Description | Example |
|----------|-------------|---------|
| `/health` | Node health status | `curl http://localhost:8001/health` |
| `/metrics/owl` | OWL measurement data | `curl http://localhost:8001/metrics/owl` |
| `/topology` | Network topology view | `curl http://localhost:8001/topology` |
| `/routing_table` | Current routing table | `curl http://localhost:8001/routing_table` |
| `/path/{destination}` | Path to destination | `curl http://localhost:8001/path/node2` |
| `/metrics` | Prometheus metrics | `curl http://localhost:8001/metrics` |
| `/node_info` | Node configuration | `curl http://localhost:8001/node_info` |

## 🧪 Quick Tests

### Test Node Health
```bash
curl http://localhost:8001/health | jq '.'
```

### Test OWL Metrics
```bash
curl http://localhost:8001/metrics/owl | jq '.'
```

### Test Path Discovery
```bash
curl http://localhost:8001/path/node2 | jq '.'
```

### Test Prometheus Metrics
```bash
curl http://localhost:8001/metrics | head -20
```

### Query Prometheus
```bash
curl "http://localhost:9090/api/v1/query?query=ddarp_owl_latency_ms" | jq '.'
```

## 📈 Available Metrics

The system exposes these Prometheus metrics:

- **`ddarp_owl_latency_ms`** - Network latency between nodes
- **`ddarp_owl_jitter_ms`** - Network jitter measurements
- **`ddarp_owl_packet_loss_percent`** - Packet loss percentage
- **`ddarp_node_health`** - Node health status (1=healthy, 0=unhealthy)
- **`ddarp_topology_nodes_total`** - Total nodes in topology
- **`ddarp_topology_edges_total`** - Total edges in topology
- **`ddarp_routing_table_size`** - Number of routes per node

## ⚡ Performance Expectations

- **Startup Time**: ~60-90 seconds for full convergence
- **OWL Measurements**: Sub-millisecond precision (~0.5ms typical)
- **Route Convergence**: 30-60 seconds for full routing tables
- **Metric Updates**: Every 5-10 seconds

## 🔧 Troubleshooting

### If startup fails:

1. **Check Docker**: `docker --version && docker info`
2. **Check permissions**: `sudo chmod +x scripts/ddarp_one_click_start.sh`
3. **Manual restart**:
   ```bash
   ./scripts/ddarp_stop.sh
   ./scripts/ddarp_one_click_start.sh
   ```

### If routing tables are empty:

- **Wait**: Routing tables populate dynamically (30-60 seconds)
- **Check logs**: `docker-compose logs node1 | grep "Updated route"`
- **Verify OWL**: Ensure OWL metrics are flowing

### If Prometheus shows no data:

- **Check targets**: Visit http://localhost:9090/targets
- **Wait for scraping**: Prometheus scrapes every 10 seconds
- **Test endpoints**: `curl http://localhost:8001/metrics`

## 🏗️ Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Node1    │────│    Node2    │────│   Border1   │
│  (Regular)  │    │  (Regular)  │    │  (Border)   │
│ :8001/:8081 │    │ :8002/:8082 │    │ :8003/:8083 │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                          │
                ┌─────────────┐
                │ Prometheus  │
                │    :9090    │
                └─────────────┘
```

## 💡 Tips

- **Routing is dynamic** - Tables update automatically based on network conditions
- **Metrics are real-time** - OWL measurements update every second
- **System is resilient** - Automatically recovers from network changes
- **Access via localhost** - Don't use Docker internal IPs (172.20.0.x)

## 📞 Support

If you encounter issues:

1. Check the logs: `docker-compose logs [service_name]`
2. Verify container status: `docker-compose ps`
3. Test individual endpoints manually
4. Restart if needed: `./scripts/ddarp_stop.sh && ./scripts/ddarp_one_click_start.sh`

---

**Happy networking with DDARP! 🚀**