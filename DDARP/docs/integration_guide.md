# DDARP Protocol Integration Guide

This guide shows how to integrate the new DDARP wire format and TLV system with your existing DDARP implementation.

## Quick Start

### 1. Run Tests

First, verify the protocol implementation works correctly:

```bash
# Run all protocol tests
python3 run_protocol_tests.py

# Run examples
python3 examples/protocol_usage.py
```

### 2. Basic Integration

```python
# Import the protocol components
from src.protocol import DDARPCodec, TLVType, FLAG_REQUEST, FLAG_RESPONSE

# Create a codec instance
codec = DDARPCodec()

# Create packets
keepalive = codec.create_keepalive_packet(tunnel_id=1001, sequence=1)
owl_metrics = codec.create_owl_metrics_packet(
    tunnel_id=1001, sequence=2,
    latency_ns=1500000, jitter_ns=50000, timestamp=int(time.time())
)

# Decode incoming packets
header, tlvs = codec.decode_packet(received_data)
for tlv_type, value in tlvs:
    if tlv_type == TLVType.OWL_METRICS:
        latency_ns, jitter_ns, timestamp = value
        # Process OWL metrics
```

## Integration Points

### 1. Node Class Integration

Add protocol support to your main DDARP node:

```python
# In src/core/composite_node.py or similar
from protocol import DDARPCodec, TLVType, FLAG_REQUEST

class DDARPNode:
    def __init__(self, node_id):
        self.node_id = node_id
        self.codec = DDARPCodec()
        self.tunnel_id = self.generate_tunnel_id()
        self.sequence = 0

    def send_owl_metrics(self, peer_addr, latency_ns, jitter_ns):
        """Send OWL metrics to peer using DDARP protocol."""
        packet = self.codec.create_owl_metrics_packet(
            tunnel_id=self.tunnel_id,
            sequence=self.get_next_sequence(),
            latency_ns=latency_ns,
            jitter_ns=jitter_ns,
            timestamp=int(time.time())
        )
        self.send_packet(peer_addr, packet)

    def handle_protocol_packet(self, data, addr):
        """Handle incoming DDARP protocol packet."""
        try:
            header, tlvs = self.codec.decode_packet(data)

            for tlv_type, value in tlvs:
                if tlv_type == TLVType.OWL_METRICS:
                    self.process_owl_metrics(addr, *value)
                elif tlv_type == TLVType.ROUTING_INFO:
                    self.process_routing_update(addr, *value)
                elif tlv_type == TLVType.T3_TERNARY:
                    self.process_t3_computation(addr, value)

        except Exception as e:
            self.logger.error(f"Protocol error from {addr}: {e}")
```

### 2. OWL Engine Integration

Update your OWL engine to use the protocol:

```python
# In src/core/owl_engine.py
from protocol import DDARPCodec, TLVType

class OWLEngine:
    def __init__(self):
        self.codec = DDARPCodec()

    def send_latency_measurement(self, target_addr, tunnel_id):
        """Send latency measurement packet."""
        measurement_data = {
            "measurement_id": str(uuid.uuid4()),
            "timestamp": time.time_ns(),
            "measurement_type": "latency_probe"
        }

        packet = self.codec.encode_packet(
            tunnel_id=tunnel_id,
            sequence=self.get_sequence(),
            tlv_data=[(TLVType.T3_TERNARY, measurement_data)],
            flags=FLAG_REQUEST
        )
        self.send_packet(target_addr, packet)

    def process_measurement_response(self, data, addr):
        """Process latency measurement response."""
        header, tlvs = self.codec.decode_packet(data)

        for tlv_type, value in tlvs:
            if tlv_type == TLVType.OWL_METRICS:
                latency_ns, jitter_ns, timestamp = value
                self.update_latency_database(addr, latency_ns, jitter_ns)
```

### 3. Networking Layer Integration

Add protocol support to your networking components:

```python
# In src/networking/data_plane.py
import asyncio
from protocol import DDARPCodec

class DataPlane:
    def __init__(self):
        self.codec = DDARPCodec()

    async def packet_handler(self, data, addr):
        """Handle incoming UDP packets."""
        try:
            # Validate packet first
            if not self.codec.validate_packet(data):
                self.logger.warning(f"Invalid packet from {addr}")
                return

            # Get packet info without full decoding
            info = self.codec.get_packet_info(data)

            # Route to appropriate handler based on TLV types
            if TLVType.OWL_METRICS in info['tlv_types']:
                await self.handle_owl_packet(data, addr)
            elif TLVType.ROUTING_INFO in info['tlv_types']:
                await self.handle_routing_packet(data, addr)
            elif TLVType.KEEPALIVE in info['tlv_types']:
                await self.handle_keepalive(data, addr)

        except Exception as e:
            self.logger.error(f"Packet processing error: {e}")
```

### 4. Control Plane Integration

Update your control plane for protocol communication:

```python
# In src/core/control_plane.py
from protocol import DDARPCodec, TLVType, FLAG_REQUEST, FLAG_RESPONSE

class ControlPlane:
    def __init__(self):
        self.codec = DDARPCodec()

    def request_route_computation(self, destination, qos_params):
        """Request route computation from peers."""
        request_data = {
            "request_type": "route_computation",
            "destination": destination,
            "qos_parameters": qos_params,
            "requester_id": self.node_id
        }

        packet = self.codec.encode_packet(
            tunnel_id=self.tunnel_id,
            sequence=self.get_next_sequence(),
            tlv_data=[(TLVType.T3_TERNARY, request_data)],
            flags=FLAG_REQUEST
        )

        # Broadcast to all peers
        for peer in self.peers:
            self.send_packet(peer.address, packet)

    def send_route_response(self, requester_addr, tunnel_id, sequence, routes):
        """Send route computation response."""
        response_data = {
            "request_type": "route_computation",
            "status": "completed",
            "routes": routes,
            "computation_time": self.last_computation_time
        }

        # Include routing info TLV for best route
        best_route = routes[0] if routes else None
        tlv_data = [(TLVType.T3_TERNARY, response_data)]

        if best_route:
            tlv_data.append((
                TLVType.ROUTING_INFO,
                (best_route['dest'], best_route['nexthop'], best_route['metric'])
            ))

        packet = self.codec.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence + 1,
            tlv_data=tlv_data,
            flags=FLAG_RESPONSE
        )

        self.send_packet(requester_addr, packet)
```

## Configuration Updates

### 1. Add Protocol Settings

Update your configuration files to include protocol settings:

```yaml
# configs/node1/ddarp.yml
protocol:
  version: 1
  default_tunnel_ttl: 300
  keepalive_interval: 30
  max_packet_size: 8192
  tlv_skip_unknown: true
  compression_enabled: false
  encryption_enabled: false

logging:
  protocol_debug: true
  packet_dump: false
```

### 2. Update Docker Configuration

If using Docker, ensure protocol files are included:

```dockerfile
# In docker/Dockerfile
COPY src/protocol/ /app/src/protocol/
RUN python3 -m pytest tests/protocol/ --tb=short
```

## Monitoring Integration

### 1. Add Protocol Metrics

```python
# Add to your monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Protocol metrics
protocol_packets_total = Counter(
    'ddarp_protocol_packets_total',
    'Total DDARP protocol packets',
    ['direction', 'tlv_type', 'node_id']
)

protocol_packet_size = Histogram(
    'ddarp_protocol_packet_size_bytes',
    'DDARP protocol packet sizes',
    ['tlv_type']
)

protocol_decode_errors = Counter(
    'ddarp_protocol_decode_errors_total',
    'DDARP protocol decode errors',
    ['error_type', 'node_id']
)

def record_packet_metrics(packet_bytes, direction, node_id):
    """Record metrics for protocol packet."""
    codec = DDARPCodec()
    info = codec.get_packet_info(packet_bytes)

    if info['valid']:
        for tlv_type in info['tlv_types']:
            tlv_name = TLVType(tlv_type).name if tlv_type in TLVType._value2member_map_ else 'UNKNOWN'
            protocol_packets_total.labels(
                direction=direction,
                tlv_type=tlv_name,
                node_id=node_id
            ).inc()

        protocol_packet_size.labels(
            tlv_type='combined'
        ).observe(info['total_length'])
    else:
        protocol_decode_errors.labels(
            error_type='invalid_packet',
            node_id=node_id
        ).inc()
```

### 2. Add Protocol Dashboard

Update your Grafana dashboards to include protocol metrics:

```json
{
  "title": "DDARP Protocol Metrics",
  "panels": [
    {
      "title": "Packet Rate by TLV Type",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(ddarp_protocol_packets_total[5m])",
          "legendFormat": "{{tlv_type}} - {{direction}}"
        }
      ]
    },
    {
      "title": "Packet Size Distribution",
      "type": "histogram",
      "targets": [
        {
          "expr": "ddarp_protocol_packet_size_bytes",
          "legendFormat": "Packet Size"
        }
      ]
    }
  ]
}
```

## Testing Integration

### 1. Add Integration Tests

```python
# tests/integration/test_protocol_integration.py
import unittest
import asyncio
from src.core.composite_node import DDARPNode
from src.protocol import DDARPCodec, TLVType

class TestProtocolIntegration(unittest.TestCase):

    def setUp(self):
        self.node1 = DDARPNode("node1")
        self.node2 = DDARPNode("node2")
        self.codec = DDARPCodec()

    async def test_owl_metrics_exchange(self):
        """Test OWL metrics exchange between nodes."""
        # Node1 sends OWL metrics
        packet = self.node1.create_owl_metrics_packet(
            latency_ns=1500000,
            jitter_ns=50000
        )

        # Node2 receives and processes
        header, tlvs = self.node2.codec.decode_packet(packet)

        # Verify correct processing
        self.assertEqual(len(tlvs), 1)
        self.assertEqual(tlvs[0][0], TLVType.OWL_METRICS)

    def test_end_to_end_communication(self):
        """Test complete communication flow."""
        # Simulate route request/response cycle
        request = self.node1.create_route_request("10.0.0.0/8")
        header, tlvs = self.node2.codec.decode_packet(request)

        # Process request and send response
        response = self.node2.create_route_response(
            header.tunnel_id,
            header.sequence + 1,
            [{"dest": "10.0.0.0/8", "nexthop": "192.168.1.1", "metric": 100}]
        )

        # Verify response
        resp_header, resp_tlvs = self.node1.codec.decode_packet(response)
        self.assertTrue(resp_header.is_flag_set(FLAG_RESPONSE))
```

### 2. Update CI/CD Pipeline

```yaml
# .github/workflows/test.yml
- name: Test Protocol Implementation
  run: |
    python3 run_protocol_tests.py
    python3 examples/protocol_usage.py
    python3 -m pytest tests/integration/test_protocol_integration.py
```

## Migration Strategy

### 1. Gradual Migration

1. **Phase 1**: Add protocol support alongside existing communication
2. **Phase 2**: Migrate non-critical components (keepalive, monitoring)
3. **Phase 3**: Migrate routing and OWL engines
4. **Phase 4**: Remove legacy communication methods

### 2. Backward Compatibility

```python
# Support both old and new protocols during transition
def handle_packet(self, data, addr):
    """Handle packet with backward compatibility."""
    try:
        # Try new protocol first
        if self.codec.validate_packet(data):
            return self.handle_protocol_packet(data, addr)
    except:
        pass

    # Fall back to legacy protocol
    return self.handle_legacy_packet(data, addr)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `src` directory is in Python path
2. **TLV Parsing Errors**: Check byte order and length fields
3. **Unknown TLV Types**: Verify TLV registry is properly initialized
4. **Performance Issues**: Consider packet size and encoding complexity

### Debug Tools

```python
# Enable debug logging
import logging
logging.getLogger('protocol').setLevel(logging.DEBUG)

# Packet inspection
info = codec.get_packet_info(packet_bytes)
print(f"Packet info: {info}")

# TLV analysis
header, tlvs = codec.decode_packet(packet_bytes)
for i, (tlv_type, value) in enumerate(tlvs):
    print(f"TLV {i}: {TLVType(tlv_type).name} = {value}")
```

## Next Steps

1. **Run tests**: `python3 run_protocol_tests.py`
2. **Try examples**: `python3 examples/protocol_usage.py`
3. **Start integration**: Begin with keepalive packets
4. **Add monitoring**: Implement protocol metrics
5. **Test thoroughly**: Use integration tests
6. **Deploy gradually**: Phase-based migration

The protocol implementation is production-ready with comprehensive error handling, extensive testing, and performance optimization. It provides a solid foundation for DDARP's communication needs.