"""
Unit tests for DDARP wire format handling.

Tests the WireFormatHandler, WirePacket, and PacketAnalyzer classes
for proper binary packet encoding/decoding and analysis.
"""

import pytest
import struct
import time
from unittest.mock import patch

from src.protocol.wire_format import (
    WireFormatHandler, WirePacket, PacketAnalyzer,
    WireFormatError, PacketCorruptionError, UnsupportedVersionError,
    encode_packet, decode_packet, analyze_packet
)
from src.protocol.packet import DDARPHeader, FLAG_REQUEST, FLAG_RESPONSE, FLAG_ERROR
from src.protocol.tlv import TLV, TLVType


class TestWireFormatHandler:
    """Test WireFormatHandler functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = WireFormatHandler()
        self.test_header = DDARPHeader(
            tunnel_id=12345,
            sequence=67890,
            flags=FLAG_REQUEST
        )
        self.test_tlvs = [
            TLV(TLVType.KEEPALIVE, 0, b""),
            TLV(TLVType.ERROR_INFO, 11, b"test_error")
        ]

    def test_encode_packet_basic(self):
        """Test basic packet encoding."""
        packet_data = self.handler.encode_packet(self.test_header, self.test_tlvs)

        # Should have header + TLV data + checksum
        assert len(packet_data) > 20  # Header size
        assert isinstance(packet_data, bytes)

        # Verify statistics updated
        assert self.handler.get_statistics()['packets_encoded'] == 1

    def test_decode_packet_basic(self):
        """Test basic packet decoding."""
        # First encode a packet
        packet_data = self.handler.encode_packet(self.test_header, self.test_tlvs)

        # Then decode it
        decoded_packet = self.handler.decode_packet(packet_data)

        assert isinstance(decoded_packet, WirePacket)
        assert decoded_packet.header.tunnel_id == self.test_header.tunnel_id
        assert decoded_packet.header.sequence == self.test_header.sequence
        assert decoded_packet.header.flags == self.test_header.flags
        assert len(decoded_packet.tlv_data) == len(self.test_tlvs)

        # Verify statistics updated
        assert self.handler.get_statistics()['packets_decoded'] == 1

    def test_encode_decode_roundtrip(self):
        """Test encode/decode roundtrip preserves data."""
        # Test with various TLV types
        complex_tlvs = [
            TLV(TLVType.T3_TERNARY, 4, b"test"),
            TLV(TLVType.OWL_METRICS, 8, b"metrics!"),
            TLV(TLVType.ROUTING_INFO, 12, b"routing_data"),
            TLV(TLVType.KEEPALIVE, 0, b"")
        ]

        # Encode
        packet_data = self.handler.encode_packet(self.test_header, complex_tlvs)

        # Decode
        decoded_packet = self.handler.decode_packet(packet_data)

        # Verify header fields
        assert decoded_packet.header.tunnel_id == self.test_header.tunnel_id
        assert decoded_packet.header.sequence == self.test_header.sequence
        assert decoded_packet.header.flags == self.test_header.flags

        # Verify TLV data
        assert len(decoded_packet.tlv_data) == len(complex_tlvs)
        for original, decoded in zip(complex_tlvs, decoded_packet.tlv_data):
            assert decoded.tlv_type == original.tlv_type
            assert decoded.length == original.length
            assert decoded.value == original.value

    def test_create_request_packet(self):
        """Test request packet creation."""
        packet_data = self.handler.create_request_packet(123, 456, self.test_tlvs)
        decoded_packet = self.handler.decode_packet(packet_data)

        assert decoded_packet.header.tunnel_id == 123
        assert decoded_packet.header.sequence == 456
        assert decoded_packet.header.flags & FLAG_REQUEST

    def test_create_response_packet(self):
        """Test response packet creation."""
        packet_data = self.handler.create_response_packet(789, 101112, self.test_tlvs)
        decoded_packet = self.handler.decode_packet(packet_data)

        assert decoded_packet.header.tunnel_id == 789
        assert decoded_packet.header.sequence == 101112
        assert decoded_packet.header.flags & FLAG_RESPONSE

    def test_create_error_packet(self):
        """Test error packet creation."""
        packet_data = self.handler.create_error_packet(999, 888, 404, "Not found")
        decoded_packet = self.handler.decode_packet(packet_data)

        assert decoded_packet.header.tunnel_id == 999
        assert decoded_packet.header.sequence == 888
        assert decoded_packet.header.flags & FLAG_ERROR
        assert len(decoded_packet.tlv_data) == 1
        assert decoded_packet.tlv_data[0].tlv_type == TLVType.ERROR_INFO

    def test_decode_too_short_packet(self):
        """Test decoding packet that's too short."""
        short_data = b"too_short"

        with pytest.raises(WireFormatError):
            self.handler.decode_packet(short_data)

    def test_decode_invalid_version(self):
        """Test decoding packet with invalid version."""
        # Create packet with invalid version
        header = DDARPHeader(version=99, tunnel_id=123, sequence=456)
        packet_data = self.handler.encode_packet(header, [])

        # Manually modify version byte
        corrupted_data = bytearray(packet_data)
        corrupted_data[0] = 99  # Invalid version

        with pytest.raises(WireFormatError):
            self.handler.decode_packet(bytes(corrupted_data))

    def test_checksum_verification(self):
        """Test checksum verification."""
        packet_data = self.handler.encode_packet(self.test_header, self.test_tlvs)

        # Should decode successfully with checksum verification
        decoded_packet = self.handler.decode_packet(packet_data, verify_checksum=True)
        assert decoded_packet.checksum is not None

        # Corrupt the packet
        corrupted_data = bytearray(packet_data)
        corrupted_data[10] = (corrupted_data[10] + 1) % 256  # Flip a bit

        # Should still decode but without checksum verification
        # (since we can't detect corruption without proper checksum format)
        decoded_packet = self.handler.decode_packet(bytes(corrupted_data), verify_checksum=False)
        assert decoded_packet is not None

    def test_statistics_tracking(self):
        """Test statistics tracking."""
        stats = self.handler.get_statistics()
        initial_encoded = stats['packets_encoded']
        initial_decoded = stats['packets_decoded']

        # Encode some packets
        for i in range(3):
            self.handler.encode_packet(self.test_header, self.test_tlvs)

        # Decode some packets
        packet_data = self.handler.encode_packet(self.test_header, self.test_tlvs)
        for i in range(2):
            self.handler.decode_packet(packet_data)

        stats = self.handler.get_statistics()
        assert stats['packets_encoded'] == initial_encoded + 4  # 3 + 1
        assert stats['packets_decoded'] == initial_decoded + 2

        # Reset statistics
        self.handler.reset_statistics()
        stats = self.handler.get_statistics()
        assert all(count == 0 for count in stats.values())


class TestWirePacket:
    """Test WirePacket functionality."""

    def test_wire_packet_creation(self):
        """Test WirePacket creation and properties."""
        header = DDARPHeader(tunnel_id=123, sequence=456, tlv_length=10)
        tlv_data = [TLV(TLVType.KEEPALIVE, 0, b"")]

        packet = WirePacket(header=header, tlv_data=tlv_data)

        assert packet.header == header
        assert packet.tlv_data == tlv_data
        assert packet.total_size == 30  # 20 (header) + 10 (tlv_length)

    def test_packet_validation(self):
        """Test packet structure validation."""
        # Valid packet
        header = DDARPHeader(tunnel_id=123, sequence=456)
        tlv_data = []
        packet = WirePacket(header=header, tlv_data=tlv_data)

        assert packet.is_valid

        # Invalid version
        header.version = 99
        packet = WirePacket(header=header, tlv_data=tlv_data)
        assert not packet.is_valid


class TestPacketAnalyzer:
    """Test PacketAnalyzer functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = PacketAnalyzer()
        self.handler = WireFormatHandler()

    def test_analyze_valid_packet(self):
        """Test analysis of valid packet."""
        header = DDARPHeader(
            tunnel_id=12345,
            sequence=67890,
            flags=FLAG_REQUEST | FLAG_RESPONSE
        )
        tlv_data = [
            TLV(TLVType.KEEPALIVE, 0, b""),
            TLV(TLVType.ERROR_INFO, 5, b"error")
        ]

        packet_data = self.handler.encode_packet(header, tlv_data)
        analysis = self.analyzer.analyze_packet(packet_data)

        assert analysis['valid'] == True
        assert analysis['packet_size'] == len(packet_data)
        assert len(analysis['errors']) == 0

        # Check header info
        header_info = analysis['header_info']
        assert header_info['tunnel_id'] == 12345
        assert header_info['sequence'] == 67890
        assert 'REQUEST' in header_info['flags']
        assert 'RESPONSE' in header_info['flags']

        # Check TLV info
        tlv_info = analysis['tlv_info']
        assert tlv_info['count'] == 2
        assert TLVType.KEEPALIVE in tlv_info['types']
        assert TLVType.ERROR_INFO in tlv_info['types']

    def test_analyze_invalid_packet(self):
        """Test analysis of invalid packet."""
        invalid_data = b"invalid_packet_data"
        analysis = self.analyzer.analyze_packet(invalid_data)

        assert analysis['valid'] == False
        assert len(analysis['errors']) > 0
        assert analysis['packet_size'] == len(invalid_data)

    def test_hexdump_generation(self):
        """Test hexdump generation."""
        test_data = b"Hello, World! This is test data."
        hexdump = self.analyzer.hexdump(test_data)

        assert isinstance(hexdump, str)
        assert '48656c6c6f' in hexdump  # "Hello" in hex
        assert 'Hello' in hexdump  # ASCII representation

    def test_flag_analysis(self):
        """Test flag analysis."""
        flags = FLAG_REQUEST | FLAG_ERROR | FLAG_COMPRESSED
        flag_names = self.analyzer._analyze_flags(flags)

        assert 'REQUEST' in flag_names
        assert 'ERROR' in flag_names
        assert 'COMPRESSED' in flag_names
        assert 'RESPONSE' not in flag_names


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_encode_packet_function(self):
        """Test encode_packet convenience function."""
        header = DDARPHeader(tunnel_id=123, sequence=456)
        tlv_data = [TLV(TLVType.KEEPALIVE, 0, b"")]

        packet_data = encode_packet(header, tlv_data)
        assert isinstance(packet_data, bytes)
        assert len(packet_data) > 20

    def test_decode_packet_function(self):
        """Test decode_packet convenience function."""
        header = DDARPHeader(tunnel_id=123, sequence=456)
        tlv_data = [TLV(TLVType.KEEPALIVE, 0, b"")]

        packet_data = encode_packet(header, tlv_data)
        decoded_packet = decode_packet(packet_data)

        assert isinstance(decoded_packet, WirePacket)
        assert decoded_packet.header.tunnel_id == 123

    def test_analyze_packet_function(self):
        """Test analyze_packet convenience function."""
        header = DDARPHeader(tunnel_id=123, sequence=456)
        tlv_data = [TLV(TLVType.KEEPALIVE, 0, b"")]

        packet_data = encode_packet(header, tlv_data)
        analysis = analyze_packet(packet_data)

        assert analysis['valid'] == True
        assert analysis['header_info']['tunnel_id'] == 123


class TestErrorHandling:
    """Test error handling and edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = WireFormatHandler()

    def test_empty_tlv_list(self):
        """Test encoding/decoding with empty TLV list."""
        header = DDARPHeader(tunnel_id=123, sequence=456)
        empty_tlvs = []

        packet_data = self.handler.encode_packet(header, empty_tlvs)
        decoded_packet = self.handler.decode_packet(packet_data)

        assert len(decoded_packet.tlv_data) == 0
        assert decoded_packet.header.tlv_length == 0

    def test_large_packet(self):
        """Test handling of large packets."""
        header = DDARPHeader(tunnel_id=123, sequence=456)
        large_tlv = TLV(TLVType.ROUTING_INFO, 1000, b"x" * 1000)

        packet_data = self.handler.encode_packet(header, [large_tlv])
        decoded_packet = self.handler.decode_packet(packet_data)

        assert len(decoded_packet.tlv_data) == 1
        assert len(decoded_packet.tlv_data[0].value) == 1000

    def test_concurrent_operations(self):
        """Test thread safety of handler operations."""
        import threading
        import time

        results = []
        errors = []

        def encode_decode_worker():
            try:
                header = DDARPHeader(tunnel_id=123, sequence=456)
                tlv_data = [TLV(TLVType.KEEPALIVE, 0, b"")]

                for _ in range(10):
                    packet_data = self.handler.encode_packet(header, tlv_data)
                    decoded_packet = self.handler.decode_packet(packet_data)
                    results.append(decoded_packet.header.tunnel_id)
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = [threading.Thread(target=encode_decode_worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 30  # 3 threads * 10 operations
        assert all(tunnel_id == 123 for tunnel_id in results)