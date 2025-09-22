# DDARP Protocol Implementation

This directory contains the complete wire format and TLV (Type-Length-Value) system for the DDARP (Distributed Dynamic Adaptive Routing Protocol).

## Overview

The DDARP protocol implementation provides:

- **Binary packet format** with structured headers
- **TLV system** for extensible message types
- **Encoding/decoding** utilities with error handling
- **Protocol codec** for high-level operations
- **Comprehensive error handling** for malformed packets
- **Support for future extensions** through TLV registry

## Components

### Core Modules

- **`packet.py`** - DDARP packet header structure and basic packet handling
- **`tlv.py`** - TLV registry, encoding/decoding, and parser with unknown TLV support
- **`codec.py`** - High-level encoding/decoding interface
- **`exceptions.py`** - Protocol-specific exceptions

### Packet Structure

```
DDARP Packet Format:
┌─────────────────────────────────────┐
│           Header (20 bytes)         │
├─────────────────────────────────────┤
│           TLV Data (variable)       │
└─────────────────────────────────────┘

Header Format:
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┤
│ Version │  Flags  │         Header Length         │
├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┤
│                        Tunnel ID                          │
├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┤
│                       Sequence Number                     │
├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┤
│                        Timestamp                          │
├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┤
│                       TLV Length                          │
└─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┘
```

### TLV Structure

```
TLV Format:
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┤
│              Type             │             Length            │
├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┤
│                      Value (variable length)                 │
│                              ...                              │
└─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┘
```

## TLV Types

| Type | Name | Description | Value Format |
|------|------|-------------|--------------|
| 0x0001 | T3_TERNARY | Ternary computation results | JSON |
| 0x0002 | OWL_METRICS | One-Way Latency metrics | Binary (latency_ns, jitter_ns, timestamp) |
| 0x0003 | ROUTING_INFO | Routing table information | Binary (dest_ip, next_hop, metric) |
| 0x0010 | NEIGHBOR_LIST | List of neighboring nodes | JSON |
| 0x0011 | TOPOLOGY_UPDATE | Network topology changes | JSON |
| 0x0020 | BANDWIDTH_INFO | Bandwidth measurements | Binary |
| 0x0021 | JITTER_METRICS | Network jitter measurements | Binary |
| 0x0022 | PACKET_LOSS | Packet loss statistics | Binary |
| 0x0030 | KEEPALIVE | Keepalive messages | Empty |
| 0x0031 | ERROR_INFO | Error reporting | String |
| 0x0032 | CAPABILITIES | Node capabilities | JSON |

## Quick Start

### Basic Usage

```python
from protocol import DDARPCodec, TLVType

# Create codec
codec = DDARPCodec()

# Create a simple packet
packet_bytes = codec.create_keepalive_packet(
    tunnel_id=1001,
    sequence=1
)

# Decode packet
header, tlvs = codec.decode_packet(packet_bytes)
print(f"Tunnel: {header.tunnel_id}, Sequence: {header.sequence}")
```

### Advanced Usage

```python
# Create complex packet with multiple TLVs
tlv_data = [
    (TLVType.T3_TERNARY, {"computation": "route_calc", "result": "success"}),
    (TLVType.OWL_METRICS, (1500000, 50000, int(time.time()))),
    (TLVType.ROUTING_INFO, ("192.168.0.0/16", "10.0.0.1", 100))
]

packet_bytes = codec.encode_packet(
    tunnel_id=2001,
    sequence=42,
    tlv_data=tlv_data,
    flags=FLAG_REQUEST
)
```

### Error Handling

```python
try:
    header, tlvs = codec.decode_packet(packet_bytes)
except DDARPProtocolError as e:
    print(f"Protocol error: {e}")
except InvalidPacketError as e:
    print(f"Invalid packet: {e}")
```

## Integration with DDARP

### In Node Implementation

```python
# In your DDARP node class
from protocol import DDARPCodec, TLVType

class DDARPNode:
    def __init__(self):
        self.codec = DDARPCodec()
        self.tunnel_id = self.generate_tunnel_id()
        self.sequence = 0

    def send_owl_metrics(self, peer, latency_ns, jitter_ns):
        """Send OWL metrics to peer."""
        packet = self.codec.create_owl_metrics_packet(
            tunnel_id=self.tunnel_id,
            sequence=self.get_next_sequence(),
            latency_ns=latency_ns,
            jitter_ns=jitter_ns,
            timestamp=int(time.time())
        )
        self.send_to_peer(peer, packet)

    def handle_incoming_packet(self, packet_bytes):
        """Handle incoming DDARP packet."""
        try:
            header, tlvs = self.codec.decode_packet(packet_bytes)

            for tlv_type, value in tlvs:
                if tlv_type == TLVType.OWL_METRICS:
                    self.process_owl_metrics(*value)
                elif tlv_type == TLVType.ROUTING_INFO:
                    self.process_routing_update(*value)
                elif tlv_type == TLVType.KEEPALIVE:
                    self.process_keepalive(header.tunnel_id)

        except Exception as e:
            self.send_error_packet(header.tunnel_id, str(e))
```

### Network Layer Integration

```python
# In your networking module
import asyncio
from protocol import DDARPCodec

class DDARPNetworking:
    def __init__(self):
        self.codec = DDARPCodec()

    async def packet_handler(self, data, addr):
        """Handle incoming UDP packets."""
        try:
            if self.codec.validate_packet(data):
                header, tlvs = self.codec.decode_packet(data)
                await self.process_packet(header, tlvs, addr)
            else:
                self.logger.warning(f"Invalid packet from {addr}")
        except Exception as e:
            self.logger.error(f"Packet processing error: {e}")
```

## Testing

Run the comprehensive test suite:

```bash
# Run all protocol tests
python3 -m pytest tests/protocol/ -v

# Run specific test module
python3 -m pytest tests/protocol/test_packet.py -v

# Run with coverage
python3 -m pytest tests/protocol/ --cov=src/protocol --cov-report=html
```

## Examples

See `examples/protocol_usage.py` for comprehensive usage examples:

```bash
python3 examples/protocol_usage.py
```

This will demonstrate:
- Basic packet creation
- Complex multi-TLV packets
- Protocol flow simulation
- Performance characteristics
- Error handling

## Performance

The protocol implementation is optimized for:

- **Fast encoding/decoding**: ~1000 packets/second on typical hardware
- **Memory efficiency**: Minimal object allocation during parsing
- **Extensibility**: Easy addition of new TLV types
- **Error recovery**: Graceful handling of malformed packets

## Error Handling Features

- **Unknown TLV skip rule**: Unknown TLVs are skipped by default
- **Packet validation**: Comprehensive validation before processing
- **Error reporting**: Detailed error information with context
- **Recovery mechanisms**: Ability to continue processing after errors

## Future Extensions

The protocol is designed for easy extension:

1. **Add new TLV types** to the `TLVType` enum
2. **Register encoders/decoders** in the `TLVRegistry`
3. **Implement custom packet types** using the codec
4. **Add compression/encryption** through packet flags

## Dependencies

- Python 3.9+
- Standard library only (struct, json, time, logging)
- No external dependencies required

## License

This implementation is part of the DDARP project and follows the same licensing terms.