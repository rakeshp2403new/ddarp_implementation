#!/usr/bin/env python3
"""
DDARP Protocol Usage Examples

This script demonstrates how to use the DDARP wire format and TLV system
for various protocol operations including packet creation, encoding/decoding,
and real-world protocol scenarios.

Run this script to see the protocol in action:
    python3 examples/protocol_usage.py
"""

import sys
import os
import time
import json
from typing import List, Tuple, Any

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from protocol import (
    DDARPCodec, DDARPHeader, DDARPPacket, TLVType,
    FLAG_REQUEST, FLAG_RESPONSE, FLAG_ERROR
)


def print_header(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_packet_info(packet_bytes: bytes, codec: DDARPCodec, title: str = "Packet"):
    """Print detailed packet information."""
    print(f"\n--- {title} ---")
    print(f"Raw packet size: {len(packet_bytes)} bytes")
    print(f"Raw packet (hex): {packet_bytes.hex()[:80]}{'...' if len(packet_bytes) > 40 else ''}")

    # Get packet info
    info = codec.get_packet_info(packet_bytes)
    print(f"Valid: {info['valid']}")

    if info['valid']:
        print(f"Tunnel ID: {info['tunnel_id']}")
        print(f"Sequence: {info['sequence']}")
        print(f"Timestamp: {info['timestamp']} ({time.ctime(info['timestamp'])})")
        print(f"Flags: 0x{info['flags']:02X}")
        print(f"TLV Count: {info['tlv_count']}")
        print(f"TLV Types: {[f'0x{t:04X}' for t in info['tlv_types']]}")

        # Decode and show TLV contents
        try:
            header, tlvs = codec.decode_packet(packet_bytes)
            print(f"TLV Data:")
            for i, (tlv_type, value) in enumerate(tlvs):
                tlv_name = TLVType(tlv_type).name if tlv_type in TLVType._value2member_map_ else f"UNKNOWN_{tlv_type:04X}"
                print(f"  [{i}] {tlv_name}: {value}")
        except Exception as e:
            print(f"TLV decode error: {e}")
    else:
        print(f"Error: {info.get('error', 'Unknown error')}")


def example_basic_packets():
    """Demonstrate basic packet creation and encoding."""
    print_header("Basic Packet Examples")

    codec = DDARPCodec()

    # 1. Simple keepalive packet
    print("\n1. Creating keepalive packet...")
    keepalive_packet = codec.create_keepalive_packet(
        tunnel_id=1001,
        sequence=1
    )
    print_packet_info(keepalive_packet, codec, "Keepalive Packet")

    # 2. OWL metrics packet
    print("\n2. Creating OWL metrics packet...")
    owl_packet = codec.create_owl_metrics_packet(
        tunnel_id=1002,
        sequence=2,
        latency_ns=1500000,  # 1.5ms
        jitter_ns=50000,     # 50µs
        timestamp=int(time.time())
    )
    print_packet_info(owl_packet, codec, "OWL Metrics Packet")

    # 3. Routing info packet
    print("\n3. Creating routing info packet...")
    routing_packet = codec.create_routing_info_packet(
        tunnel_id=1003,
        sequence=3,
        dest_ip="192.168.0.0/16",
        next_hop="10.0.0.1",
        metric=100
    )
    print_packet_info(routing_packet, codec, "Routing Info Packet")

    # 4. Error packet
    print("\n4. Creating error packet...")
    error_packet = codec.create_error_packet(
        tunnel_id=1004,
        sequence=4,
        error_msg="Route computation failed - network unreachable"
    )
    print_packet_info(error_packet, codec, "Error Packet")


def example_complex_packets():
    """Demonstrate complex packets with multiple TLVs."""
    print_header("Complex Multi-TLV Packets")

    codec = DDARPCodec()

    # Request packet with multiple TLVs
    print("\n1. Creating complex request packet...")
    complex_tlvs = [
        (TLVType.T3_TERNARY, {
            "computation_id": "route_calc_001",
            "algorithm": "dijkstra_modified",
            "parameters": {
                "max_hops": 10,
                "weight_latency": 0.7,
                "weight_bandwidth": 0.3
            },
            "destination_networks": [
                "10.0.0.0/8",
                "172.16.0.0/12",
                "192.168.0.0/16"
            ]
        }),
        (TLVType.OWL_METRICS, (2500000, 100000, int(time.time()))),
        (TLVType.ROUTING_INFO, ("0.0.0.0/0", "192.168.1.1", 50))
    ]

    complex_packet = codec.encode_packet(
        tunnel_id=2001,
        sequence=101,
        tlv_data=complex_tlvs,
        flags=FLAG_REQUEST
    )
    print_packet_info(complex_packet, codec, "Complex Request Packet")

    # Response packet
    print("\n2. Creating complex response packet...")
    response_tlvs = [
        (TLVType.T3_TERNARY, {
            "computation_id": "route_calc_001",
            "status": "completed",
            "results": {
                "optimal_routes": [
                    {"dest": "10.0.0.0/8", "nexthop": "172.16.1.1", "metric": 75},
                    {"dest": "172.16.0.0/12", "nexthop": "192.168.2.1", "metric": 120},
                    {"dest": "192.168.0.0/16", "nexthop": "10.1.1.1", "metric": 90}
                ],
                "computation_time_ms": 15.7,
                "convergence_iterations": 3
            }
        }),
        (TLVType.OWL_METRICS, (1800000, 75000, int(time.time()))),
        (TLVType.ROUTING_INFO, ("10.0.0.0/8", "172.16.1.1", 75))
    ]

    response_packet = codec.encode_packet(
        tunnel_id=2001,  # Same tunnel as request
        sequence=102,
        tlv_data=response_tlvs,
        flags=FLAG_RESPONSE
    )
    print_packet_info(response_packet, codec, "Complex Response Packet")


def example_protocol_flow():
    """Demonstrate a complete DDARP protocol flow between nodes."""
    print_header("DDARP Protocol Flow Simulation")

    codec = DDARPCodec()

    print("\nSimulating communication between Node A and Node B...")

    # Step 1: Node A requests route information
    print("\n📤 Node A -> Node B: Route Request")
    request = codec.create_request_packet(
        tunnel_id=5001,
        sequence=1,
        tlv_data=[
            (TLVType.T3_TERNARY, {
                "request_type": "route_discovery",
                "target_network": "203.0.113.0/24",
                "qos_requirements": {
                    "max_latency_ms": 50,
                    "min_bandwidth_mbps": 100
                }
            }),
            (TLVType.OWL_METRICS, (3000000, 150000, int(time.time())))
        ]
    )
    print_packet_info(request, codec, "Route Request")

    # Step 2: Node B responds with route information
    print("\n📥 Node B -> Node A: Route Response")
    response = codec.create_response_packet(
        tunnel_id=5001,
        sequence=2,
        tlv_data=[
            (TLVType.T3_TERNARY, {
                "request_type": "route_discovery",
                "status": "success",
                "routes_found": 2,
                "recommended_route": {
                    "path": ["NodeB", "NodeC", "NodeD"],
                    "estimated_latency_ms": 45,
                    "available_bandwidth_mbps": 150
                }
            }),
            (TLVType.ROUTING_INFO, ("203.0.113.0/24", "10.1.2.3", 200)),
            (TLVType.OWL_METRICS, (2800000, 120000, int(time.time())))
        ]
    )
    print_packet_info(response, codec, "Route Response")

    # Step 3: Periodic keepalive exchange
    print("\n💓 Keepalive Exchange")
    for node, seq in [("A", 3), ("B", 4)]:
        keepalive = codec.create_keepalive_packet(
            tunnel_id=5001,
            sequence=seq
        )
        print_packet_info(keepalive, codec, f"Keepalive from Node {node}")

    # Step 4: Error scenario
    print("\n❌ Error Scenario")
    error = codec.create_error_packet(
        tunnel_id=5001,
        sequence=5,
        error_msg="BGP session down - rerouting required"
    )
    print_packet_info(error, codec, "Error Notification")


def example_performance_test():
    """Demonstrate protocol performance characteristics."""
    print_header("Protocol Performance Test")

    codec = DDARPCodec()

    # Test different packet sizes
    packet_sizes = []

    for i in range(5):
        # Create increasingly complex T3_TERNARY data
        complexity = 2 ** i
        ternary_data = {
            "test_run": i + 1,
            "complexity_factor": complexity,
            "data": {f"key_{j}": f"value_{j}" * 10 for j in range(complexity)}
        }

        packet = codec.encode_packet(
            tunnel_id=9000 + i,
            sequence=i + 1,
            tlv_data=[
                (TLVType.T3_TERNARY, ternary_data),
                (TLVType.OWL_METRICS, (1000000 + i * 100000, 50000 + i * 10000, int(time.time()))),
                (TLVType.KEEPALIVE, None)
            ]
        )

        packet_sizes.append(len(packet))
        print(f"Packet {i+1}: {len(packet)} bytes (complexity: {complexity})")

    print(f"\nPacket size range: {min(packet_sizes)} - {max(packet_sizes)} bytes")

    # Test encoding/decoding speed
    print("\nTesting encoding/decoding speed...")
    test_tlvs = [
        (TLVType.T3_TERNARY, {"performance": "test", "data": list(range(100))}),
        (TLVType.OWL_METRICS, (2000000, 75000, int(time.time()))),
        (TLVType.ROUTING_INFO, ("10.0.0.0/8", "192.168.1.1", 150))
    ]

    start_time = time.time()
    iterations = 1000

    for i in range(iterations):
        packet = codec.encode_packet(
            tunnel_id=i,
            sequence=i,
            tlv_data=test_tlvs
        )
        header, tlvs = codec.decode_packet(packet)

    end_time = time.time()
    total_time = end_time - start_time

    print(f"Processed {iterations} encode/decode cycles in {total_time:.3f}s")
    print(f"Average time per cycle: {total_time/iterations*1000:.3f}ms")
    print(f"Throughput: {iterations/total_time:.1f} packets/second")


def example_error_handling():
    """Demonstrate error handling and recovery."""
    print_header("Error Handling Examples")

    codec = DDARPCodec()

    # Test 1: Invalid packet data
    print("\n1. Testing invalid packet data...")
    invalid_data = b"This is not a valid DDARP packet"

    try:
        header, tlvs = codec.decode_packet(invalid_data)
        print("❌ Should have raised an exception")
    except Exception as e:
        print(f"✅ Correctly caught exception: {type(e).__name__}: {e}")

    # Test 2: Packet validation
    print("\n2. Testing packet validation...")
    valid_packet = codec.create_keepalive_packet(1001, 1)
    print(f"Valid packet validation: {codec.validate_packet(valid_packet)}")
    print(f"Invalid data validation: {codec.validate_packet(b'invalid')}")

    # Test 3: Unknown TLV handling
    print("\n3. Testing unknown TLV handling...")
    # Create packet with known TLVs first
    normal_packet = codec.encode_packet(
        tunnel_id=3001,
        sequence=1,
        tlv_data=[(TLVType.KEEPALIVE, None)]
    )

    # Manually append unknown TLV (this simulates receiving packet with unknown TLV)
    unknown_tlv = b'\x99\x99\x00\x04test'  # Type 0x9999, length 4, value "test"
    packet_with_unknown = normal_packet + unknown_tlv

    try:
        # Try to decode - should handle unknown TLV gracefully
        header, tlvs = codec.decode_packet(packet_with_unknown)
        print("❌ Should have failed due to invalid packet structure")
    except Exception as e:
        print(f"✅ Correctly handled invalid packet structure: {type(e).__name__}")


def main():
    """Run all examples."""
    print("DDARP Protocol Usage Examples")
    print("=" * 80)

    try:
        example_basic_packets()
        example_complex_packets()
        example_protocol_flow()
        example_performance_test()
        example_error_handling()

        print_header("Examples Complete")
        print("All examples completed successfully!")
        print("\nNext steps:")
        print("1. Run unit tests: python3 -m pytest tests/protocol/")
        print("2. Integrate with DDARP node implementation")
        print("3. Add protocol to networking layer")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())