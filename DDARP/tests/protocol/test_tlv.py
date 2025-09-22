"""
Unit tests for DDARP TLV system including registry, encoding/decoding, and parsing.
"""

import unittest
import json
import struct
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from protocol.tlv import (
    TLV, TLVType, TLVRegistry, TLVParser, TLVEncoder, TLVDecoder,
    TLV_HEADER_SIZE
)
from protocol.exceptions import TLVParsingError, TLVLengthError, UnknownTLVError


class TestTLV(unittest.TestCase):
    """Test cases for TLV class."""

    def test_tlv_creation(self):
        """Test creating TLV with valid data."""
        value = b"test_value"
        tlv = TLV(TLVType.T3_TERNARY, len(value), value)

        self.assertEqual(tlv.type, TLVType.T3_TERNARY)
        self.assertEqual(tlv.length, len(value))
        self.assertEqual(tlv.value, value)

    def test_tlv_length_mismatch(self):
        """Test TLV creation with length mismatch."""
        value = b"test_value"
        with self.assertRaises(TLVLengthError):
            TLV(TLVType.OWL_METRICS, len(value) + 5, value)  # Wrong length

    def test_tlv_packing(self):
        """Test TLV binary packing."""
        value = b"pack_test"
        tlv = TLV(TLVType.ROUTING_INFO, len(value), value)

        packed = tlv.pack()
        expected_size = TLV_HEADER_SIZE + len(value)
        self.assertEqual(len(packed), expected_size)

        # Verify header
        header = packed[:TLV_HEADER_SIZE]
        tlv_type, tlv_length = struct.unpack("!HH", header)
        self.assertEqual(tlv_type, TLVType.ROUTING_INFO)
        self.assertEqual(tlv_length, len(value))

        # Verify value
        self.assertEqual(packed[TLV_HEADER_SIZE:], value)

    def test_tlv_unpacking(self):
        """Test TLV binary unpacking."""
        # Create test TLV data
        test_value = b"unpack_test_data"
        test_data = struct.pack("!HH", TLVType.KEEPALIVE, len(test_value)) + test_value

        tlv, next_offset = TLV.unpack(test_data, 0)

        self.assertEqual(tlv.type, TLVType.KEEPALIVE)
        self.assertEqual(tlv.length, len(test_value))
        self.assertEqual(tlv.value, test_value)
        self.assertEqual(next_offset, TLV_HEADER_SIZE + len(test_value))

    def test_tlv_unpacking_insufficient_header(self):
        """Test TLV unpacking with insufficient header data."""
        short_data = b"AB"  # Only 2 bytes, need 4 for header
        with self.assertRaises(TLVParsingError):
            TLV.unpack(short_data, 0)

    def test_tlv_unpacking_insufficient_value(self):
        """Test TLV unpacking with insufficient value data."""
        # Header claims 100 bytes but only provide 5
        test_data = struct.pack("!HH", TLVType.T3_TERNARY, 100) + b"short"
        with self.assertRaises(TLVParsingError):
            TLV.unpack(test_data, 0)

    def test_tlv_string_representation(self):
        """Test TLV string representation."""
        value = b"string_test"
        tlv = TLV(TLVType.OWL_METRICS, len(value), value)

        tlv_str = str(tlv)
        self.assertIn("OWL_METRICS", tlv_str)
        self.assertIn(f"len={len(value)}", tlv_str)

    def test_tlv_unknown_type_string(self):
        """Test TLV string representation with unknown type."""
        value = b"unknown"
        tlv = TLV(0x9999, len(value), value)  # Unknown type

        tlv_str = str(tlv)
        self.assertIn("UNKNOWN_9999", tlv_str)


class TestTLVEncoder(unittest.TestCase):
    """Test cases for TLV encoding utilities."""

    def test_encode_string(self):
        """Test string encoding."""
        test_string = "Hello, DDARP!"
        encoded = TLVEncoder.encode_string(test_string)
        self.assertEqual(encoded, test_string.encode('utf-8'))

    def test_encode_uint32(self):
        """Test 32-bit unsigned integer encoding."""
        test_value = 0x12345678
        encoded = TLVEncoder.encode_uint32(test_value)
        self.assertEqual(encoded, struct.pack("!I", test_value))

    def test_encode_uint64(self):
        """Test 64-bit unsigned integer encoding."""
        test_value = 0x123456789ABCDEF0
        encoded = TLVEncoder.encode_uint64(test_value)
        self.assertEqual(encoded, struct.pack("!Q", test_value))

    def test_encode_float(self):
        """Test float encoding."""
        test_value = 3.14159
        encoded = TLVEncoder.encode_float(test_value)
        self.assertEqual(encoded, struct.pack("!f", test_value))

    def test_encode_double(self):
        """Test double encoding."""
        test_value = 2.718281828459045
        encoded = TLVEncoder.encode_double(test_value)
        self.assertEqual(encoded, struct.pack("!d", test_value))

    def test_encode_json(self):
        """Test JSON encoding."""
        test_obj = {"key": "value", "number": 42, "list": [1, 2, 3]}
        encoded = TLVEncoder.encode_json(test_obj)
        expected = json.dumps(test_obj, separators=(',', ':')).encode('utf-8')
        self.assertEqual(encoded, expected)

    def test_encode_owl_metrics(self):
        """Test OWL metrics encoding."""
        latency_ns = 1500000  # 1.5ms
        jitter_ns = 50000     # 50µs
        timestamp = 1634567890

        encoded = TLVEncoder.encode_owl_metrics(latency_ns, jitter_ns, timestamp)
        expected = struct.pack("!QQI", latency_ns, jitter_ns, timestamp)
        self.assertEqual(encoded, expected)

    def test_encode_routing_info(self):
        """Test routing information encoding."""
        dest_ip = "192.168.1.0/24"
        next_hop = "10.0.0.1"
        metric = 100

        encoded = TLVEncoder.encode_routing_info(dest_ip, next_hop, metric)

        # Verify structure
        dest_len, hop_len = struct.unpack("!HH", encoded[:4])
        self.assertEqual(dest_len, len(dest_ip))
        self.assertEqual(hop_len, len(next_hop))

        offset = 4
        decoded_dest = encoded[offset:offset + dest_len].decode('utf-8')
        offset += dest_len
        decoded_hop = encoded[offset:offset + hop_len].decode('utf-8')
        offset += hop_len
        decoded_metric = struct.unpack("!I", encoded[offset:offset + 4])[0]

        self.assertEqual(decoded_dest, dest_ip)
        self.assertEqual(decoded_hop, next_hop)
        self.assertEqual(decoded_metric, metric)


class TestTLVDecoder(unittest.TestCase):
    """Test cases for TLV decoding utilities."""

    def test_decode_string(self):
        """Test string decoding."""
        test_string = "Decode test string"
        data = test_string.encode('utf-8')
        decoded = TLVDecoder.decode_string(data)
        self.assertEqual(decoded, test_string)

    def test_decode_string_invalid_utf8(self):
        """Test string decoding with invalid UTF-8."""
        invalid_data = b'\xff\xfe\xfd'
        with self.assertRaises(TLVParsingError):
            TLVDecoder.decode_string(invalid_data)

    def test_decode_uint32(self):
        """Test 32-bit unsigned integer decoding."""
        test_value = 0x87654321
        data = struct.pack("!I", test_value)
        decoded = TLVDecoder.decode_uint32(data)
        self.assertEqual(decoded, test_value)

    def test_decode_uint32_invalid_length(self):
        """Test uint32 decoding with invalid length."""
        invalid_data = b'ABC'  # 3 bytes instead of 4
        with self.assertRaises(TLVParsingError):
            TLVDecoder.decode_uint32(invalid_data)

    def test_decode_uint64(self):
        """Test 64-bit unsigned integer decoding."""
        test_value = 0xFEDCBA9876543210
        data = struct.pack("!Q", test_value)
        decoded = TLVDecoder.decode_uint64(data)
        self.assertEqual(decoded, test_value)

    def test_decode_float(self):
        """Test float decoding."""
        test_value = -123.456
        data = struct.pack("!f", test_value)
        decoded = TLVDecoder.decode_float(data)
        self.assertAlmostEqual(decoded, test_value, places=5)

    def test_decode_double(self):
        """Test double decoding."""
        test_value = 1.23456789012345
        data = struct.pack("!d", test_value)
        decoded = TLVDecoder.decode_double(data)
        self.assertAlmostEqual(decoded, test_value, places=10)

    def test_decode_json(self):
        """Test JSON decoding."""
        test_obj = {"message": "test", "count": 5, "active": True}
        data = json.dumps(test_obj).encode('utf-8')
        decoded = TLVDecoder.decode_json(data)
        self.assertEqual(decoded, test_obj)

    def test_decode_json_invalid(self):
        """Test JSON decoding with invalid data."""
        invalid_data = b'{"invalid": json data'
        with self.assertRaises(TLVParsingError):
            TLVDecoder.decode_json(invalid_data)

    def test_decode_owl_metrics(self):
        """Test OWL metrics decoding."""
        latency_ns = 2500000
        jitter_ns = 75000
        timestamp = 1634567999

        data = struct.pack("!QQI", latency_ns, jitter_ns, timestamp)
        decoded = TLVDecoder.decode_owl_metrics(data)

        self.assertEqual(decoded, (latency_ns, jitter_ns, timestamp))

    def test_decode_owl_metrics_invalid_length(self):
        """Test OWL metrics decoding with invalid length."""
        invalid_data = b'short_data'
        with self.assertRaises(TLVParsingError):
            TLVDecoder.decode_owl_metrics(invalid_data)

    def test_decode_routing_info(self):
        """Test routing information decoding."""
        dest_ip = "10.0.0.0/8"
        next_hop = "192.168.1.1"
        metric = 250

        # Encode first
        encoded = TLVEncoder.encode_routing_info(dest_ip, next_hop, metric)

        # Then decode
        decoded = TLVDecoder.decode_routing_info(encoded)
        self.assertEqual(decoded, (dest_ip, next_hop, metric))


class TestTLVRegistry(unittest.TestCase):
    """Test cases for TLV registry."""

    def setUp(self):
        """Set up test registry."""
        self.registry = TLVRegistry()

    def test_default_handlers_registered(self):
        """Test that default handlers are registered."""
        self.assertTrue(self.registry.is_known(TLVType.T3_TERNARY))
        self.assertTrue(self.registry.is_known(TLVType.OWL_METRICS))
        self.assertTrue(self.registry.is_known(TLVType.ROUTING_INFO))
        self.assertTrue(self.registry.is_known(TLVType.KEEPALIVE))

    def test_register_custom_handler(self):
        """Test registering custom TLV handler."""
        custom_type = 0x1000

        def custom_encoder(value):
            return value.upper().encode('utf-8')

        def custom_decoder(data):
            return data.decode('utf-8').lower()

        self.registry.register(
            custom_type,
            encoder=custom_encoder,
            decoder=custom_decoder,
            description="Custom test TLV"
        )

        self.assertTrue(self.registry.is_known(custom_type))
        self.assertEqual(
            self.registry.get_description(custom_type),
            "Custom test TLV"
        )

    def test_encode_t3_ternary(self):
        """Test encoding T3_TERNARY TLV."""
        test_data = {"result": "success", "computation": [1, 2, 3]}
        tlv = self.registry.encode(TLVType.T3_TERNARY, test_data)

        self.assertEqual(tlv.type, TLVType.T3_TERNARY)
        # Decode to verify
        decoded = json.loads(tlv.value.decode('utf-8'))
        self.assertEqual(decoded, test_data)

    def test_encode_owl_metrics(self):
        """Test encoding OWL_METRICS TLV."""
        metrics = (1000000, 50000, 1634568000)  # latency, jitter, timestamp
        tlv = self.registry.encode(TLVType.OWL_METRICS, metrics)

        self.assertEqual(tlv.type, TLVType.OWL_METRICS)
        self.assertEqual(tlv.length, 20)  # 8 + 8 + 4 bytes

    def test_encode_routing_info(self):
        """Test encoding ROUTING_INFO TLV."""
        routing_data = ("172.16.0.0/16", "10.1.1.1", 150)
        tlv = self.registry.encode(TLVType.ROUTING_INFO, routing_data)

        self.assertEqual(tlv.type, TLVType.ROUTING_INFO)
        self.assertGreater(tlv.length, 0)

    def test_encode_unknown_type(self):
        """Test encoding unknown TLV type."""
        with self.assertRaises(UnknownTLVError):
            self.registry.encode(0x9999, "unknown_data")

    def test_decode_known_tlv(self):
        """Test decoding known TLV."""
        # Create OWL metrics TLV
        metrics = (2000000, 100000, 1634568100)
        tlv = self.registry.encode(TLVType.OWL_METRICS, metrics)

        # Decode it
        decoded = self.registry.decode(tlv)
        self.assertEqual(decoded, metrics)

    def test_decode_unknown_tlv(self):
        """Test decoding unknown TLV returns raw bytes."""
        unknown_tlv = TLV(0x8888, 8, b"raw_data")  # Fix length to match data
        decoded = self.registry.decode(unknown_tlv)
        self.assertEqual(decoded, b"raw_data")


class TestTLVParser(unittest.TestCase):
    """Test cases for TLV parser."""

    def setUp(self):
        """Set up test parser."""
        self.parser = TLVParser()

    def test_parse_single_tlv(self):
        """Test parsing single TLV."""
        # Create test TLV
        test_data = {"test": "value"}
        tlv = self.parser.create_tlv(TLVType.T3_TERNARY, test_data)
        tlv_binary = tlv.pack()

        # Parse it
        parsed_tlvs = self.parser.parse(tlv_binary)

        self.assertEqual(len(parsed_tlvs), 1)
        self.assertEqual(parsed_tlvs[0].type, TLVType.T3_TERNARY)

    def test_parse_multiple_tlvs(self):
        """Test parsing multiple TLVs."""
        # Create multiple TLVs
        tlv1 = self.parser.create_tlv(TLVType.T3_TERNARY, {"first": "tlv"})
        tlv2 = self.parser.create_tlv(TLVType.OWL_METRICS, (1500000, 25000, 1634568200))
        tlv3 = self.parser.create_tlv(TLVType.KEEPALIVE, None)

        # Combine binary data
        combined_data = tlv1.pack() + tlv2.pack() + tlv3.pack()

        # Parse
        parsed_tlvs = self.parser.parse(combined_data)

        self.assertEqual(len(parsed_tlvs), 3)
        self.assertEqual(parsed_tlvs[0].type, TLVType.T3_TERNARY)
        self.assertEqual(parsed_tlvs[1].type, TLVType.OWL_METRICS)
        self.assertEqual(parsed_tlvs[2].type, TLVType.KEEPALIVE)

    def test_parse_unknown_tlv_skip(self):
        """Test parsing unknown TLV with skip enabled."""
        # Create known TLV
        known_tlv = self.parser.create_tlv(TLVType.KEEPALIVE, None)

        # Create unknown TLV manually
        unknown_data = struct.pack("!HH", 0x9999, 4) + b"test"

        # Combine
        combined_data = known_tlv.pack() + unknown_data

        # Parse (skip_unknown is True by default)
        parsed_tlvs = self.parser.parse(combined_data)

        self.assertEqual(len(parsed_tlvs), 1)  # Only known TLV
        self.assertEqual(parsed_tlvs[0].type, TLVType.KEEPALIVE)

    def test_parse_unknown_tlv_no_skip(self):
        """Test parsing unknown TLV with skip disabled."""
        self.parser.skip_unknown = False

        # Create unknown TLV
        unknown_data = struct.pack("!HH", 0x9999, 4) + b"test"

        # Should raise exception
        with self.assertRaises(UnknownTLVError):
            self.parser.parse(unknown_data)

    def test_encode_tlvs(self):
        """Test encoding list of TLVs."""
        tlvs = [
            self.parser.create_tlv(TLVType.T3_TERNARY, {"encode": "test"}),
            self.parser.create_tlv(TLVType.KEEPALIVE, None)
        ]

        encoded = self.parser.encode_tlvs(tlvs)

        # Should equal sum of individual TLV sizes
        expected_size = sum(len(tlv.pack()) for tlv in tlvs)
        self.assertEqual(len(encoded), expected_size)

        # Parse back to verify
        parsed = self.parser.parse(encoded)
        self.assertEqual(len(parsed), 2)

    def test_create_and_decode_tlv(self):
        """Test TLV creation and decoding round-trip."""
        # Test various TLV types
        test_cases = [
            (TLVType.T3_TERNARY, {"round": "trip", "test": 123}),
            (TLVType.OWL_METRICS, (3000000, 150000, 1634568300)),
            (TLVType.ROUTING_INFO, ("203.0.113.0/24", "198.51.100.1", 200)),
            (TLVType.KEEPALIVE, None)
        ]

        for tlv_type, original_value in test_cases:
            with self.subTest(tlv_type=tlv_type):
                # Create TLV
                tlv = self.parser.create_tlv(tlv_type, original_value)

                # Decode TLV
                decoded_value = self.parser.decode_tlv(tlv)

                self.assertEqual(decoded_value, original_value)


if __name__ == '__main__':
    unittest.main()