"""
Unit tests for DDARP codec - high-level encoding/decoding interface.
"""

import unittest
import time
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from protocol.codec import DDARPCodec
from protocol.packet import DDARPHeader, FLAG_REQUEST, FLAG_RESPONSE, FLAG_ERROR
from protocol.tlv import TLVType
from protocol.exceptions import DDARPProtocolError, InvalidPacketError


class TestDDARPCodec(unittest.TestCase):
    """Test cases for DDARPCodec class."""

    def setUp(self):
        """Set up test codec."""
        self.codec = DDARPCodec()

    def test_encode_simple_packet(self):
        """Test encoding simple packet with one TLV."""
        tunnel_id = 12345
        sequence = 67890
        tlv_data = [(TLVType.KEEPALIVE, None)]

        packet_bytes = self.codec.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=tlv_data
        )

        self.assertIsInstance(packet_bytes, bytes)
        self.assertGreater(len(packet_bytes), 20)  # At least header size

    def test_encode_multiple_tlvs_packet(self):
        """Test encoding packet with multiple TLVs."""
        tunnel_id = 11111
        sequence = 22222
        tlv_data = [
            (TLVType.T3_TERNARY, {"computation": "result", "value": 42}),
            (TLVType.OWL_METRICS, (1500000, 50000, int(time.time()))),
            (TLVType.ROUTING_INFO, ("192.168.0.0/16", "10.0.0.1", 100)),
            (TLVType.KEEPALIVE, None)
        ]

        packet_bytes = self.codec.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=tlv_data
        )

        self.assertIsInstance(packet_bytes, bytes)
        # Should be header + multiple TLV data
        self.assertGreater(len(packet_bytes), 100)

    def test_encode_packet_with_flags(self):
        """Test encoding packet with custom flags."""
        packet_bytes = self.codec.encode_packet(
            tunnel_id=33333,
            sequence=44444,
            tlv_data=[(TLVType.KEEPALIVE, None)],
            flags=FLAG_REQUEST | FLAG_ERROR
        )

        # Decode to verify flags
        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertTrue(header.is_flag_set(FLAG_REQUEST))
        self.assertTrue(header.is_flag_set(FLAG_ERROR))
        self.assertFalse(header.is_flag_set(FLAG_RESPONSE))

    def test_decode_packet(self):
        """Test decoding a valid packet."""
        original_tunnel_id = 55555
        original_sequence = 66666
        original_tlv_data = [
            (TLVType.T3_TERNARY, {"decode": "test", "number": 123}),
            (TLVType.OWL_METRICS, (2000000, 75000, 1634568400))
        ]

        # Encode packet
        packet_bytes = self.codec.encode_packet(
            tunnel_id=original_tunnel_id,
            sequence=original_sequence,
            tlv_data=original_tlv_data
        )

        # Decode packet
        header, decoded_tlvs = self.codec.decode_packet(packet_bytes)

        # Verify header
        self.assertEqual(header.tunnel_id, original_tunnel_id)
        self.assertEqual(header.sequence, original_sequence)

        # Verify TLVs
        self.assertEqual(len(decoded_tlvs), 2)

        # Check T3_TERNARY TLV
        t3_tlv = next((t for t in decoded_tlvs if t[0] == TLVType.T3_TERNARY), None)
        self.assertIsNotNone(t3_tlv)
        self.assertEqual(t3_tlv[1], {"decode": "test", "number": 123})

        # Check OWL_METRICS TLV
        owl_tlv = next((t for t in decoded_tlvs if t[0] == TLVType.OWL_METRICS), None)
        self.assertIsNotNone(owl_tlv)
        self.assertEqual(owl_tlv[1], (2000000, 75000, 1634568400))

    def test_create_request_packet(self):
        """Test creating request packet."""
        packet_bytes = self.codec.create_request_packet(
            tunnel_id=77777,
            sequence=88888,
            tlv_data=[(TLVType.KEEPALIVE, None)]
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertTrue(header.is_flag_set(FLAG_REQUEST))
        self.assertEqual(header.tunnel_id, 77777)
        self.assertEqual(header.sequence, 88888)

    def test_create_response_packet(self):
        """Test creating response packet."""
        packet_bytes = self.codec.create_response_packet(
            tunnel_id=99999,
            sequence=11111,
            tlv_data=[(TLVType.T3_TERNARY, {"response": "data"})]
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertTrue(header.is_flag_set(FLAG_RESPONSE))
        self.assertEqual(header.tunnel_id, 99999)
        self.assertEqual(header.sequence, 11111)

    def test_create_error_packet(self):
        """Test creating error packet."""
        error_message = "Test error message"
        packet_bytes = self.codec.create_error_packet(
            tunnel_id=12121,
            sequence=34343,
            error_msg=error_message
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertTrue(header.is_flag_set(FLAG_ERROR))
        self.assertEqual(len(tlvs), 1)
        self.assertEqual(tlvs[0][0], TLVType.ERROR_INFO)

    def test_create_keepalive_packet(self):
        """Test creating keepalive packet."""
        packet_bytes = self.codec.create_keepalive_packet(
            tunnel_id=56565,
            sequence=78787
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertEqual(header.tunnel_id, 56565)
        self.assertEqual(header.sequence, 78787)
        self.assertEqual(len(tlvs), 1)
        self.assertEqual(tlvs[0][0], TLVType.KEEPALIVE)

    def test_create_owl_metrics_packet(self):
        """Test creating OWL metrics packet."""
        latency_ns = 3500000
        jitter_ns = 125000
        timestamp = int(time.time())

        packet_bytes = self.codec.create_owl_metrics_packet(
            tunnel_id=13131,
            sequence=24242,
            latency_ns=latency_ns,
            jitter_ns=jitter_ns,
            timestamp=timestamp
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertEqual(len(tlvs), 1)
        self.assertEqual(tlvs[0][0], TLVType.OWL_METRICS)
        self.assertEqual(tlvs[0][1], (latency_ns, jitter_ns, timestamp))

    def test_create_routing_info_packet(self):
        """Test creating routing info packet."""
        dest_ip = "10.0.0.0/8"
        next_hop = "172.16.1.1"
        metric = 500

        packet_bytes = self.codec.create_routing_info_packet(
            tunnel_id=14141,
            sequence=25252,
            dest_ip=dest_ip,
            next_hop=next_hop,
            metric=metric
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertEqual(len(tlvs), 1)
        self.assertEqual(tlvs[0][0], TLVType.ROUTING_INFO)
        self.assertEqual(tlvs[0][1], (dest_ip, next_hop, metric))

    def test_validate_packet_valid(self):
        """Test packet validation with valid packet."""
        packet_bytes = self.codec.create_keepalive_packet(
            tunnel_id=16161,
            sequence=37373
        )

        self.assertTrue(self.codec.validate_packet(packet_bytes))

    def test_validate_packet_invalid(self):
        """Test packet validation with invalid packet."""
        invalid_packet = b"not_a_valid_packet"
        self.assertFalse(self.codec.validate_packet(invalid_packet))

    def test_get_packet_info(self):
        """Test getting packet information."""
        tunnel_id = 18181
        sequence = 39393
        packet_bytes = self.codec.create_request_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=[
                (TLVType.T3_TERNARY, {"info": "test"}),
                (TLVType.KEEPALIVE, None)
            ]
        )

        info = self.codec.get_packet_info(packet_bytes)

        self.assertTrue(info['valid'])
        self.assertEqual(info['tunnel_id'], tunnel_id)
        self.assertEqual(info['sequence'], sequence)
        self.assertTrue(info['flags'] & FLAG_REQUEST)
        self.assertEqual(info['tlv_count'], 2)
        self.assertIn(TLVType.T3_TERNARY, info['tlv_types'])
        self.assertIn(TLVType.KEEPALIVE, info['tlv_types'])

    def test_get_packet_info_invalid(self):
        """Test getting packet information for invalid packet."""
        invalid_packet = b"invalid_data"
        info = self.codec.get_packet_info(invalid_packet)

        self.assertFalse(info['valid'])
        self.assertIn('error', info)
        self.assertEqual(info['data_length'], len(invalid_packet))

    def test_round_trip_encoding_decoding(self):
        """Test complete round-trip encoding and decoding."""
        original_data = [
            (TLVType.T3_TERNARY, {
                "computation_id": "test_123",
                "result": {"success": True, "value": 3.14159},
                "metadata": {"timestamp": 1634568500, "node": "test_node"}
            }),
            (TLVType.OWL_METRICS, (4500000, 200000, 1634568600)),
            (TLVType.ROUTING_INFO, ("203.0.113.0/24", "198.51.100.254", 750)),
            (TLVType.KEEPALIVE, None)
        ]

        # Encode
        packet_bytes = self.codec.encode_packet(
            tunnel_id=20202,
            sequence=40404,
            tlv_data=original_data,
            flags=FLAG_REQUEST
        )

        # Decode
        header, decoded_tlvs = self.codec.decode_packet(packet_bytes)

        # Verify header
        self.assertEqual(header.tunnel_id, 20202)
        self.assertEqual(header.sequence, 40404)
        self.assertTrue(header.is_flag_set(FLAG_REQUEST))

        # Verify TLVs (order and content)
        self.assertEqual(len(decoded_tlvs), len(original_data))

        for original_tlv, decoded_tlv in zip(original_data, decoded_tlvs):
            original_type, original_value = original_tlv
            decoded_type, decoded_value = decoded_tlv

            self.assertEqual(decoded_type, original_type)
            self.assertEqual(decoded_value, original_value)

    def test_error_handling_encoding_failure(self):
        """Test error handling when encoding fails."""
        # Try to encode with invalid TLV type
        with self.assertRaises(DDARPProtocolError):
            self.codec.encode_packet(
                tunnel_id=21212,
                sequence=42424,
                tlv_data=[(0x9999, "unknown_type")]  # Unknown TLV type
            )

    def test_error_handling_decoding_failure(self):
        """Test error handling when decoding fails."""
        # Try to decode invalid packet data
        invalid_data = b"completely_invalid_packet_data"
        with self.assertRaises(DDARPProtocolError):
            self.codec.decode_packet(invalid_data)

    def test_decode_packet_with_failed_tlv(self):
        """Test decoding packet where some TLVs fail to decode."""
        # Create a valid packet first
        packet_bytes = self.codec.create_keepalive_packet(
            tunnel_id=22222,
            sequence=43434
        )

        # Mock the TLV parser to simulate decode failure
        with patch.object(self.codec.parser, 'decode_tlv') as mock_decode:
            mock_decode.side_effect = Exception("Decode failed")

            header, tlvs = self.codec.decode_packet(packet_bytes)

            # Should still return header and TLVs (with raw bytes for failed ones)
            self.assertEqual(header.tunnel_id, 22222)
            self.assertEqual(len(tlvs), 1)
            # TLV value should be raw bytes due to decode failure
            self.assertIsInstance(tlvs[0][1], bytes)

    def test_custom_timestamp(self):
        """Test encoding packet with custom timestamp."""
        custom_timestamp = 1500000000
        packet_bytes = self.codec.encode_packet(
            tunnel_id=23232,
            sequence=45454,
            tlv_data=[(TLVType.KEEPALIVE, None)],
            timestamp=custom_timestamp
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertEqual(header.timestamp, custom_timestamp)

    def test_empty_tlv_data(self):
        """Test encoding packet with no TLVs."""
        packet_bytes = self.codec.encode_packet(
            tunnel_id=24242,
            sequence=46464,
            tlv_data=[]
        )

        header, tlvs = self.codec.decode_packet(packet_bytes)
        self.assertEqual(header.tunnel_id, 24242)
        self.assertEqual(header.sequence, 46464)
        self.assertEqual(len(tlvs), 0)
        self.assertEqual(header.tlv_length, 0)


class TestCodecIntegration(unittest.TestCase):
    """Integration tests for codec with real-world scenarios."""

    def setUp(self):
        """Set up integration test codec."""
        self.codec = DDARPCodec()

    def test_ddarp_protocol_flow(self):
        """Test a complete DDARP protocol flow simulation."""
        # Node 1 sends request
        request_packet = self.codec.create_request_packet(
            tunnel_id=1001,
            sequence=1,
            tlv_data=[
                (TLVType.T3_TERNARY, {"query": "route_to", "destination": "10.0.0.0/8"}),
                (TLVType.OWL_METRICS, (1200000, 30000, int(time.time())))
            ]
        )

        # Decode request
        req_header, req_tlvs = self.codec.decode_packet(request_packet)
        self.assertTrue(req_header.is_flag_set(FLAG_REQUEST))
        self.assertEqual(req_header.tunnel_id, 1001)

        # Node 2 sends response
        response_packet = self.codec.create_response_packet(
            tunnel_id=1001,  # Same tunnel
            sequence=2,      # Next sequence
            tlv_data=[
                (TLVType.ROUTING_INFO, ("10.0.0.0/8", "192.168.1.1", 150)),
                (TLVType.T3_TERNARY, {"route_computation": "completed", "hops": 3})
            ]
        )

        # Decode response
        resp_header, resp_tlvs = self.codec.decode_packet(response_packet)
        self.assertTrue(resp_header.is_flag_set(FLAG_RESPONSE))
        self.assertEqual(resp_header.tunnel_id, 1001)
        self.assertEqual(resp_header.sequence, 2)

        # Verify routing info in response
        routing_tlv = next((t for t in resp_tlvs if t[0] == TLVType.ROUTING_INFO), None)
        self.assertIsNotNone(routing_tlv)
        dest, nexthop, metric = routing_tlv[1]
        self.assertEqual(dest, "10.0.0.0/8")
        self.assertEqual(nexthop, "192.168.1.1")
        self.assertEqual(metric, 150)

    def test_keepalive_exchange(self):
        """Test keepalive packet exchange."""
        keepalive_packets = []

        # Create keepalive packets for multiple nodes
        for node_id in range(1, 4):
            packet = self.codec.create_keepalive_packet(
                tunnel_id=node_id * 1000,
                sequence=node_id
            )
            keepalive_packets.append(packet)

        # Verify all keepalive packets
        for i, packet in enumerate(keepalive_packets, 1):
            header, tlvs = self.codec.decode_packet(packet)
            self.assertEqual(header.tunnel_id, i * 1000)
            self.assertEqual(header.sequence, i)
            self.assertEqual(len(tlvs), 1)
            self.assertEqual(tlvs[0][0], TLVType.KEEPALIVE)

    def test_error_reporting(self):
        """Test error packet creation and handling."""
        error_messages = [
            "Route computation failed",
            "Invalid tunnel configuration",
            "Network unreachable"
        ]

        for i, error_msg in enumerate(error_messages):
            error_packet = self.codec.create_error_packet(
                tunnel_id=5000 + i,
                sequence=100 + i,
                error_msg=error_msg
            )

            header, tlvs = self.codec.decode_packet(error_packet)
            self.assertTrue(header.is_flag_set(FLAG_ERROR))
            self.assertEqual(header.tunnel_id, 5000 + i)
            self.assertEqual(len(tlvs), 1)
            self.assertEqual(tlvs[0][0], TLVType.ERROR_INFO)


if __name__ == '__main__':
    unittest.main()