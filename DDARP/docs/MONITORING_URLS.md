# DDARP Monitoring URLs - Fixed Configuration

## 🔧 Port Conflict Resolution

The original configuration had port conflicts. Here are the **corrected URLs** that should work:

## ✅ Main Monitoring Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Grafana** | http://localhost:3000 | admin/ddarp2023 |
| **OWL Matrix Dashboard** | http://localhost:3000/d/owl-matrix-table/owl-matrix-table | admin/ddarp2023 |
| **Prometheus** | http://localhost:9096 | - |
| **Kibana** | http://localhost:5601 | - |
| **Alertmanager** | http://localhost:9095 | - |
| **Real-time Pipeline** | ws://localhost:8765 | - |

## 📊 DDARP Node Services

| Service | URL | Description |
|---------|-----|-------------|
| **Node1 API** | http://localhost:8081 | Main API endpoint |
| **Node2 API** | http://localhost:8082 | Main API endpoint |
| **Node3 API** | http://localhost:8083 | Main API endpoint |
| **Node1 Metrics** | http://localhost:9091/metrics | Prometheus metrics |
| **Node2 Metrics** | http://localhost:9092/metrics | Prometheus metrics |
| **Node3 Metrics** | http://localhost:9094/metrics | Prometheus metrics |
| **Node1 WebSocket** | ws://localhost:8766 | Real-time data |
| **Node2 WebSocket** | ws://localhost:8767 | Real-time data |
| **Node3 WebSocket** | ws://localhost:8768 | Real-time data |

## 🔍 Infrastructure Services

| Service | URL | Description |
|---------|-----|-------------|
| **Elasticsearch** | http://localhost:9200 | Search & analytics |
| **Logstash TCP** | tcp://localhost:5000 | Log ingestion |
| **Node Exporter** | http://localhost:9100/metrics | System metrics |
| **cAdvisor** | http://localhost:8084 | Container metrics |

## 🚀 Quick Start Commands

```bash
# Start the monitoring stack
./ddarp.sh start

# Check status
./ddarp.sh status

# Verify all URLs work
./ddarp.sh verify

# View detailed monitoring status
./ddarp.sh monitoring
```

## 🔍 Verification Script

Run the verification script to test all URLs:

```bash
./verify_monitoring.sh
```

This will check:
- ✅ HTTP endpoints health
- ✅ WebSocket connectivity
- ✅ TCP port availability
- ✅ Service responsiveness

## 🐛 Troubleshooting

### If URLs don't work:

1. **Check if containers are running:**
   ```bash
   docker ps | grep ddarp
   ```

2. **Check port conflicts:**
   ```bash
   ss -tuln | grep -E ':(3000|5601|8765|9096|9095)'
   ```

3. **Check container logs:**
   ```bash
   ./ddarp.sh logs grafana
   ./ddarp.sh logs prometheus
   ./ddarp.sh logs kibana
   ```

4. **Restart services:**
   ```bash
   ./ddarp.sh restart
   ```

### Common Issues:

- **Port already in use**: Check if other services are using the same ports
- **Container startup timeout**: Increase wait times in docker-compose
- **Memory issues**: ELK stack requires significant RAM (4GB+ recommended)
- **Permission issues**: Ensure Docker has necessary privileges

## 📝 Key Changes Made

1. **Fixed port conflicts:**
   - Prometheus: 9090 → 9096 (external access)
   - Alertmanager: 9093 → 9095 (external access)
   - cAdvisor: 8080 → 8084 (external access)
   - Node3 metrics: 9093 → 9094 (external access)

2. **Added missing services:**
   - Kibana service was missing from Docker Compose
   - Proper Alertmanager configuration

3. **Updated all configuration files:**
   - Updated ddarp.sh with correct URLs
   - Updated MONITORING.md documentation
   - Fixed Prometheus scrape configuration
   - Added verification script

4. **Maintained internal networking:**
   - Container-to-container communication uses internal ports
   - External access uses mapped ports
   - Service discovery works correctly

## 🎯 What Should Work Now

✅ All monitoring URLs should be accessible
✅ Grafana dashboards should load
✅ Prometheus should scrape metrics
✅ Kibana should connect to Elasticsearch
✅ Real-time WebSocket streaming should work
✅ Alertmanager should receive alerts

If you still have issues, run `./ddarp.sh verify` to get detailed diagnostics.