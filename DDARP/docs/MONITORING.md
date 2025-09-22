# DDARP Comprehensive Monitoring Setup

This document describes the comprehensive monitoring system for DDARP, including Grafana dashboards, Prometheus metrics, ELK stack integration, and real-time data streaming.

## Overview

The DDARP monitoring system provides:

- **Real-time metrics collection** via Prometheus
- **Interactive dashboards** with Grafana
- **Log aggregation and analysis** with ELK stack
- **Real-time data streaming** via WebSocket
- **Alerting and notifications** with Alertmanager
- **Performance visualization** and network topology mapping

## Architecture

```
DDARP Nodes (node1, node2, node3)
    ↓ (metrics)
Prometheus ← Node Exporter, cAdvisor
    ↓ (queries)
Grafana Dashboards
    ↓ (alerts)
Alertmanager

DDARP Nodes (logs)
    ↓ (JSON logs)
Logstash
    ↓ (processed)
Elasticsearch
    ↓ (visualize)
Kibana Dashboards

DDARP Nodes (real-time)
    ↓ (WebSocket)
Real-time Pipeline
    ↓ (stream)
WebSocket Clients
```

## Quick Start

### 1. Setup and Start

```bash
# Complete setup with monitoring
./ddarp.sh setup
./ddarp.sh start

# Check status
./ddarp.sh status
./ddarp.sh monitoring
```

### 2. Access Monitoring Interfaces

- **Grafana**: http://localhost:3000 (admin/ddarp2023)
- **Prometheus**: http://localhost:9096
- **Kibana**: http://localhost:5601
- **Alertmanager**: http://localhost:9095
- **Real-time Data**: ws://localhost:8765

## Grafana Dashboards

### Network Performance Dashboard
- **URL**: http://localhost:3000/d/ddarp-network-performance
- **Features**:
  - Real-time latency heatmap between node pairs
  - Packet loss trends and thresholds
  - Jitter distribution analysis
  - Network performance matrix

### Topology Dashboard
- **URL**: http://localhost:3000/d/ddarp-topology
- **Features**:
  - Dynamic network graph with node status
  - BGP session states
  - Tunnel connectivity map
  - Node count and health summary

### Algorithm Performance Dashboard
- **URL**: http://localhost:3000/d/ddarp-algorithm
- **Features**:
  - Path computation time analysis
  - Algorithm efficiency metrics
  - Route update rates
  - Performance heatmaps

### BGP Operations Dashboard
- **URL**: http://localhost:3000/d/ddarp-bgp
- **Features**:
  - BGP session status monitoring
  - Route convergence time tracking
  - Neighbor relationship health
  - Route exchange statistics

### Tunnel Management Dashboard
- **URL**: http://localhost:3000/d/ddarp-tunnels
- **Features**:
  - Active tunnel status map
  - Throughput per tunnel analysis
  - Tunnel setup duration metrics
  - WireGuard performance tracking

### System Health Dashboard
- **URL**: http://localhost:3000/d/ddarp-health
- **Features**:
  - CPU, memory, and disk usage
  - Container health monitoring
  - Error rate analysis
  - Resource utilization trends

## Prometheus Metrics

### Core DDARP Metrics

```prometheus
# Latency metrics
ddarp_latency_current_milliseconds{node_id, peer_id}
ddarp_latency_milliseconds_bucket{node_id, peer_id, le}
ddarp_jitter_current_milliseconds{node_id, peer_id}

# Packet loss metrics
ddarp_packet_loss_ratio{node_id, peer_id}

# Path computation metrics
ddarp_path_computation_duration_milliseconds{node_id, destination}
ddarp_path_computation_duration_milliseconds_bucket{node_id, destination, le}

# BGP metrics
ddarp_bgp_session_status{node_id, neighbor}
ddarp_bgp_convergence_duration_milliseconds{node_id, neighbor}
ddarp_bgp_routes_received{node_id, neighbor}
ddarp_bgp_routes_sent{node_id, neighbor}

# Tunnel metrics
ddarp_tunnel_status{node_id, peer_id, interface}
ddarp_tunnel_setup_duration_milliseconds{node_id, peer_id}
ddarp_tunnel_bytes_in{node_id, peer_id, interface}
ddarp_tunnel_bytes_out{node_id, peer_id, interface}

# System metrics
ddarp_node_status{node_id}
ddarp_cpu_usage_percent{node_id}
ddarp_memory_usage_percent{node_id}
ddarp_disk_usage_percent{node_id}
ddarp_container_health_status{node_id, container}

# Algorithm metrics
ddarp_algorithm_efficiency_ratio{node_id}
ddarp_route_updates_total{node_id}
ddarp_errors_total{node_id, error_type}
```

### Metric Endpoints

- **node1**: http://localhost:9091/metrics
- **node2**: http://localhost:9092/metrics
- **node3**: http://localhost:9094/metrics

## ELK Stack Integration

### Structured Logging

DDARP uses structured JSON logging with the following categories:

```json
{
  "timestamp": "2023-12-01T10:30:00Z",
  "log_level": "INFO",
  "log_category": "OWL_MEASUREMENT",
  "node_id": "node1",
  "correlation_id": "uuid-1234",
  "message": "OWL measurement completed",
  "details": {
    "peer_id": "node2",
    "latency_ms": 15.5,
    "jitter_ms": 2.1,
    "packet_loss_ratio": 0.001
  }
}
```

### Log Categories

- **OWL_MEASUREMENT**: Network latency measurements
- **PATH_COMPUTATION**: Routing algorithm operations
- **BGP_EVENT**: BGP session state changes
- **TUNNEL_LIFECYCLE**: WireGuard tunnel operations
- **SYSTEM_HEALTH**: System status and errors

### Elasticsearch Indices

- `ddarp-logs-*`: General DDARP logs
- `ddarp-owl_measurement-*`: OWL-specific measurements
- `ddarp-path_computation-*`: Path computation events
- `ddarp-bgp_event-*`: BGP operational events
- `ddarp-tunnel_lifecycle-*`: Tunnel management events
- `ddarp-system_health-*`: System health and errors

### Kibana Dashboards

Access Kibana at http://localhost:5601 for:

- **DDARP Overview**: Comprehensive system overview
- **Network Analysis**: Latency and performance analysis
- **Error Investigation**: Error tracking and debugging
- **Operational Insights**: BGP and tunnel operations

## Real-time Data Pipeline

### WebSocket Streaming

The real-time pipeline provides live data streaming via WebSocket:

```javascript
// Connect to real-time data stream
const ws = new WebSocket('ws://localhost:8765');

// Subscribe to specific data channels
ws.send(JSON.stringify({
  type: 'subscribe',
  subscriptions: ['owl_measurements', 'bgp_events', 'system_health']
}));

// Receive real-time updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Real-time update:', data);
};
```

### Available Channels

- `owl_measurements`: Live latency/jitter/packet loss data
- `path_computations`: Real-time path computation events
- `bgp_events`: BGP session state changes
- `tunnel_events`: WireGuard tunnel status updates
- `system_health`: System health metrics
- `topology_changes`: Network topology modifications

### Node-specific WebSocket Endpoints

- **node1**: ws://localhost:8766
- **node2**: ws://localhost:8767
- **node3**: ws://localhost:8768

## Alerting

### Prometheus Alerts

Configured alerts include:

- **High Latency**: > 50ms (warning), > 100ms (critical)
- **High Packet Loss**: > 1% (warning), > 5% (critical)
- **Node Down**: Service unavailable > 30s
- **BGP Session Down**: Session state down > 1m
- **Tunnel Down**: WireGuard tunnel down > 1m
- **High CPU/Memory**: > 80% (warning), > 95% (critical)
- **Container Unhealthy**: Health check failure > 2m

### Alertmanager Configuration

Access Alertmanager at http://localhost:9095

Default notification channels:
- Email alerts for critical issues
- Webhook integration with real-time pipeline
- Slack notifications (configure webhook URL)

## Performance Tuning

### Prometheus Configuration

```yaml
# Scrape intervals
global:
  scrape_interval: 15s      # Default scrape interval
  evaluation_interval: 15s  # Alert evaluation interval

# DDARP-specific scraping
scrape_configs:
  - job_name: 'ddarp-nodes'
    scrape_interval: 5s     # High-frequency for network metrics
```

### Elasticsearch Optimization

```yaml
# Index settings for performance
index:
  refresh_interval: "5s"
  number_of_shards: 1
  number_of_replicas: 0
  codec: "best_compression"
```

### Real-time Pipeline Tuning

```python
# Buffer sizes for different data types
BUFFER_SIZES = {
    'owl_measurements': 1000,
    'path_computations': 500,
    'bgp_events': 200,
    'system_health': 100
}
```

## Troubleshooting

### Common Issues

1. **Grafana dashboards not loading**
   ```bash
   # Check Grafana logs
   ./ddarp.sh logs grafana

   # Restart Grafana
   docker restart ddarp-grafana
   ```

2. **Prometheus targets down**
   ```bash
   # Check target status
   curl http://localhost:9090/api/v1/targets

   # Check node metrics endpoints
   curl http://localhost:9091/metrics
   ```

3. **Elasticsearch cluster red**
   ```bash
   # Check cluster health
   curl http://localhost:9200/_cluster/health

   # Check logs
   ./ddarp.sh logs elasticsearch
   ```

4. **Real-time pipeline connection issues**
   ```bash
   # Test WebSocket connectivity
   wscat -c ws://localhost:8765

   # Check pipeline logs
   ./ddarp.sh logs ddarp-realtime-pipeline
   ```

### Log Analysis

```bash
# View specific service logs
./ddarp.sh logs node1           # Node1 logs
./ddarp.sh logs prometheus      # Prometheus logs
./ddarp.sh logs grafana         # Grafana logs
./ddarp.sh logs elasticsearch   # Elasticsearch logs

# Follow all logs
./ddarp.sh logs
```

### Health Checks

```bash
# Comprehensive status check
./ddarp.sh status

# Detailed monitoring status
./ddarp.sh monitoring

# Run system tests
./ddarp.sh test
```

## Advanced Configuration

### Custom Dashboards

1. Create dashboard JSON in `configs/grafana/dashboards/`
2. Restart Grafana to load new dashboards
3. Or import via Grafana UI

### Custom Alerts

1. Add rules to `configs/prometheus/rules/`
2. Update Alertmanager config for notification routing
3. Restart Prometheus and Alertmanager

### Custom Log Processing

1. Modify `configs/logstash/logstash.conf`
2. Add custom field mappings
3. Update Elasticsearch templates as needed

## Security Considerations

- Default Grafana credentials: admin/ddarp2023 (change in production)
- Elasticsearch has no authentication enabled (add security for production)
- WebSocket endpoints are unencrypted (use WSS in production)
- All services run in privileged Docker containers

## Backup and Recovery

### Prometheus Data
```bash
# Backup Prometheus data
docker cp ddarp-prometheus:/prometheus ./prometheus-backup

# Restore Prometheus data
docker cp ./prometheus-backup ddarp-prometheus:/prometheus
```

### Grafana Configuration
```bash
# Export dashboards
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:3000/api/dashboards/db/dashboard-name

# Backup Grafana data
docker cp ddarp-grafana:/var/lib/grafana ./grafana-backup
```

### Elasticsearch Data
```bash
# Create snapshot repository
curl -X PUT "localhost:9200/_snapshot/backup_repo" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/backups"
  }
}'

# Create snapshot
curl -X PUT "localhost:9200/_snapshot/backup_repo/snapshot_1"
```

For production deployments, implement automated backup strategies and secure access controls.