"""
Unit tests for DDARP packet header structure and packet handling.
"""

import unittest
import time
import struct
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from protocol.packet import (
    DDARPHeader, DDARPPacket, DDARP_VERSION, DDARP_HEADER_SIZE,
    FLAG_REQUEST, FLAG_RESPONSE, FLAG_ERROR, FLAG_COMPRESSED, FLAG_ENCRYPTED
)
from protocol.exceptions import (
    InvalidPacketError, PacketTooShortError, InvalidHeaderError
)


class TestDDARPHeader(unittest.TestCase):
    """Test cases for DDARPHeader class."""

    def test_default_header_creation(self):
        """Test creating header with default values."""
        header = DDARPHeader()

        self.assertEqual(header.version, DDARP_VERSION)
        self.assertEqual(header.flags, 0)
        self.assertEqual(header.header_len, DDARP_HEADER_SIZE)
        self.assertEqual(header.tunnel_id, 0)
        self.assertEqual(header.sequence, 0)
        self.assertEqual(header.tlv_length, 0)
        self.assertGreater(header.timestamp, 0)  # Auto-generated

    def test_custom_header_creation(self):
        """Test creating header with custom values."""
        timestamp = int(time.time())
        header = DDARPHeader(
            tunnel_id=12345,
            sequence=678,
            flags=FLAG_REQUEST,
            timestamp=timestamp,
            tlv_length=100
        )

        self.assertEqual(header.tunnel_id, 12345)
        self.assertEqual(header.sequence, 678)
        self.assertEqual(header.flags, FLAG_REQUEST)
        self.assertEqual(header.timestamp, timestamp)
        self.assertEqual(header.tlv_length, 100)

    def test_invalid_version(self):
        """Test header with invalid version."""
        with self.assertRaises(InvalidHeaderError):
            DDARPHeader(version=2)

    def test_invalid_header_length(self):
        """Test header with invalid length."""
        with self.assertRaises(InvalidHeaderError):
            DDARPHeader(header_len=30)

    def test_invalid_tlv_length(self):
        """Test header with negative TLV length."""
        with self.assertRaises(InvalidHeaderError):
            DDARPHeader(tlv_length=-1)

    def test_flag_operations(self):
        """Test flag setting and checking operations."""
        header = DDARPHeader()

        # Test setting flags
        header.set_flag(FLAG_REQUEST)
        self.assertTrue(header.is_flag_set(FLAG_REQUEST))
        self.assertFalse(header.is_flag_set(FLAG_RESPONSE))

        header.set_flag(FLAG_ERROR)
        self.assertTrue(header.is_flag_set(FLAG_REQUEST))
        self.assertTrue(header.is_flag_set(FLAG_ERROR))

        # Test clearing flags
        header.clear_flag(FLAG_REQUEST)
        self.assertFalse(header.is_flag_set(FLAG_REQUEST))
        self.assertTrue(header.is_flag_set(FLAG_ERROR))

    def test_header_packing(self):
        """Test header binary packing."""
        header = DDARPHeader(
            tunnel_id=0x12345678,
            sequence=0x87654321,
            timestamp=0xABCDEF00,
            tlv_length=0x1000,
            flags=FLAG_REQUEST | FLAG_COMPRESSED
        )

        packed = header.pack()
        self.assertEqual(len(packed), DDARP_HEADER_SIZE)

        # Verify the packed format
        unpacked = struct.unpack("!BBHIIII", packed)
        self.assertEqual(unpacked[0], DDARP_VERSION)  # version
        self.assertEqual(unpacked[1], FLAG_REQUEST | FLAG_COMPRESSED)  # flags
        self.assertEqual(unpacked[2], DDARP_HEADER_SIZE)  # header_len
        self.assertEqual(unpacked[3], 0x12345678)  # tunnel_id
        self.assertEqual(unpacked[4], 0x87654321)  # sequence
        self.assertEqual(unpacked[5], 0xABCDEF00)  # timestamp
        self.assertEqual(unpacked[6], 0x1000)  # tlv_length

    def test_header_unpacking(self):
        """Test header binary unpacking."""
        # Create test data
        test_data = struct.pack(
            "!BBHIIII",
            DDARP_VERSION,
            FLAG_RESPONSE | FLAG_ENCRYPTED,
            DDARP_HEADER_SIZE,
            0x11223344,
            0x55667788,
            0x99AABBCC,
            0x2000
        )

        header = DDARPHeader.unpack(test_data)

        self.assertEqual(header.version, DDARP_VERSION)
        self.assertEqual(header.flags, FLAG_RESPONSE | FLAG_ENCRYPTED)
        self.assertEqual(header.header_len, DDARP_HEADER_SIZE)
        self.assertEqual(header.tunnel_id, 0x11223344)
        self.assertEqual(header.sequence, 0x55667788)
        self.assertEqual(header.timestamp, 0x99AABBCC)
        self.assertEqual(header.tlv_length, 0x2000)

    def test_header_unpacking_too_short(self):
        """Test unpacking data that's too short."""
        short_data = b"short"
        with self.assertRaises(PacketTooShortError):
            DDARPHeader.unpack(short_data)

    def test_header_string_representation(self):
        """Test header string representation."""
        header = DDARPHeader(
            tunnel_id=123,
            sequence=456,
            flags=FLAG_REQUEST | FLAG_ERROR
        )

        header_str = str(header)
        self.assertIn("tunnel_id=123", header_str)
        self.assertIn("seq=456", header_str)
        self.assertIn("REQ|ERR", header_str)


class TestDDARPPacket(unittest.TestCase):
    """Test cases for DDARPPacket class."""

    def test_packet_creation(self):
        """Test creating packet with header and TLV data."""
        header = DDARPHeader(tunnel_id=123, sequence=456)
        tlv_data = b"test_tlv_data"

        packet = DDARPPacket(header, tlv_data)

        self.assertEqual(packet.header.tunnel_id, 123)
        self.assertEqual(packet.header.sequence, 456)
        self.assertEqual(packet.header.tlv_length, len(tlv_data))
        self.assertEqual(packet.tlv_data, tlv_data)

    def test_packet_packing(self):
        """Test packet binary packing."""
        header = DDARPHeader(tunnel_id=789, sequence=101112)
        tlv_data = b"sample_tlv_payload"

        packet = DDARPPacket(header, tlv_data)
        packed = packet.pack()

        self.assertEqual(len(packed), DDARP_HEADER_SIZE + len(tlv_data))
        self.assertEqual(packed[:DDARP_HEADER_SIZE], header.pack())
        self.assertEqual(packed[DDARP_HEADER_SIZE:], tlv_data)

    def test_packet_unpacking(self):
        """Test packet binary unpacking."""
        # Create test packet
        original_header = DDARPHeader(tunnel_id=999, sequence=777)
        original_tlv = b"test_payload_data"
        original_packet = DDARPPacket(original_header, original_tlv)
        packed_data = original_packet.pack()

        # Unpack and verify
        unpacked_packet = DDARPPacket.unpack(packed_data)

        self.assertEqual(unpacked_packet.header.tunnel_id, 999)
        self.assertEqual(unpacked_packet.header.sequence, 777)
        self.assertEqual(unpacked_packet.header.tlv_length, len(original_tlv))
        self.assertEqual(unpacked_packet.tlv_data, original_tlv)

    def test_packet_unpacking_too_short(self):
        """Test unpacking data that's too short for packet."""
        short_data = b"too_short"
        with self.assertRaises(PacketTooShortError):
            DDARPPacket.unpack(short_data)

    def test_packet_unpacking_insufficient_tlv_data(self):
        """Test unpacking packet with insufficient TLV data."""
        # Create header claiming 100 bytes of TLV data
        header = DDARPHeader(tlv_length=100)
        header_data = header.pack()

        # But only provide 10 bytes of TLV data
        insufficient_data = header_data + b"only_10_by"

        with self.assertRaises(PacketTooShortError):
            DDARPPacket.unpack(insufficient_data)

    def test_packet_validation_success(self):
        """Test successful packet validation."""
        header = DDARPHeader(tunnel_id=111, sequence=222)
        tlv_data = b"valid_tlv_data"
        packet = DDARPPacket(header, tlv_data)

        self.assertTrue(packet.validate())

    def test_packet_validation_failure(self):
        """Test packet validation failure."""
        header = DDARPHeader(tunnel_id=333, sequence=444, tlv_length=100)
        tlv_data = b"short"  # Much shorter than claimed in header

        # Manually create packet without updating header
        packet = DDARPPacket.__new__(DDARPPacket)
        packet.header = header
        packet.tlv_data = tlv_data

        self.assertFalse(packet.validate())

    def test_packet_length(self):
        """Test packet length calculation."""
        header = DDARPHeader()
        tlv_data = b"test_data_12345"
        packet = DDARPPacket(header, tlv_data)

        expected_length = DDARP_HEADER_SIZE + len(tlv_data)
        self.assertEqual(len(packet), expected_length)

    def test_packet_string_representation(self):
        """Test packet string representation."""
        header = DDARPHeader(tunnel_id=555)
        tlv_data = b"string_test_data"
        packet = DDARPPacket(header, tlv_data)

        packet_str = str(packet)
        self.assertIn("tunnel_id=555", packet_str)
        self.assertIn(f"tlv_data={len(tlv_data)} bytes", packet_str)


class TestPacketRoundTrip(unittest.TestCase):
    """Test round-trip encoding/decoding of packets."""

    def test_empty_packet_round_trip(self):
        """Test round-trip with empty TLV data."""
        original_header = DDARPHeader(tunnel_id=1001, sequence=2002)
        original_packet = DDARPPacket(original_header, b"")

        # Pack and unpack
        packed = original_packet.pack()
        unpacked = DDARPPacket.unpack(packed)

        self.assertEqual(unpacked.header.tunnel_id, 1001)
        self.assertEqual(unpacked.header.sequence, 2002)
        self.assertEqual(unpacked.header.tlv_length, 0)
        self.assertEqual(unpacked.tlv_data, b"")

    def test_large_packet_round_trip(self):
        """Test round-trip with large TLV data."""
        original_header = DDARPHeader(tunnel_id=3003, sequence=4004)
        large_tlv_data = b"X" * 10000  # 10KB of data
        original_packet = DDARPPacket(original_header, large_tlv_data)

        # Pack and unpack
        packed = original_packet.pack()
        unpacked = DDARPPacket.unpack(packed)

        self.assertEqual(unpacked.header.tunnel_id, 3003)
        self.assertEqual(unpacked.header.sequence, 4004)
        self.assertEqual(unpacked.header.tlv_length, 10000)
        self.assertEqual(unpacked.tlv_data, large_tlv_data)

    def test_all_flags_round_trip(self):
        """Test round-trip with all flags set."""
        all_flags = FLAG_REQUEST | FLAG_RESPONSE | FLAG_ERROR | FLAG_COMPRESSED | FLAG_ENCRYPTED
        original_header = DDARPHeader(
            tunnel_id=5005,
            sequence=6006,
            flags=all_flags
        )
        original_packet = DDARPPacket(original_header, b"flags_test")

        # Pack and unpack
        packed = original_packet.pack()
        unpacked = DDARPPacket.unpack(packed)

        self.assertEqual(unpacked.header.flags, all_flags)
        self.assertTrue(unpacked.header.is_flag_set(FLAG_REQUEST))
        self.assertTrue(unpacked.header.is_flag_set(FLAG_RESPONSE))
        self.assertTrue(unpacked.header.is_flag_set(FLAG_ERROR))
        self.assertTrue(unpacked.header.is_flag_set(FLAG_COMPRESSED))
        self.assertTrue(unpacked.header.is_flag_set(FLAG_ENCRYPTED))


if __name__ == '__main__':
    unittest.main()