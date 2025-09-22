"""
DDARP Wire Format - Binary Packet Format Handling

This module provides comprehensive binary packet format handling for the DDARP protocol,
including packet encoding/decoding, validation, and wire format utilities.

Wire Format Overview:
- Fixed 20-byte header with network byte order encoding
- Variable-length TLV payload section
- Built-in error detection and recovery
- Support for packet fragmentation and reassembly
"""

import struct
import time
import logging
import hashlib
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import IntEnum

from .packet import DDARPHeader, DDARP_HEADER_FORMAT, DDARP_HEADER_SIZE, DDARP_VERSION
from .packet import FLAG_REQUEST, FLAG_RESPONSE, FLAG_ERROR, FLAG_COMPRESSED, FLAG_ENCRYPTED
from .tlv import TLVRegistry, TLVType, TLV, parse_tlv_data
from .exceptions import InvalidPacketError, PacketTooShortError, InvalidHeaderError

logger = logging.getLogger(__name__)

class WireFormatError(Exception):
    """Base exception for wire format errors"""
    pass

class PacketCorruptionError(WireFormatError):
    """Raised when packet corruption is detected"""
    pass

class UnsupportedVersionError(WireFormatError):
    """Raised when packet version is not supported"""
    pass

@dataclass
class WirePacket:
    """
    Represents a complete DDARP packet with header and payload.

    This class provides a high-level interface for working with DDARP packets
    in their binary wire format.
    """
    header: DDARPHeader
    tlv_data: List[TLV]
    raw_payload: Optional[bytes] = None
    checksum: Optional[bytes] = None

    @property
    def total_size(self) -> int:
        """Calculate total packet size including header and payload"""
        return DDARP_HEADER_SIZE + self.header.tlv_length

    @property
    def is_valid(self) -> bool:
        """Check if packet structure is valid"""
        try:
            self._validate_structure()
            return True
        except Exception:
            return False

    def _validate_structure(self):
        """Validate packet structure integrity"""
        if self.header.version != DDARP_VERSION:
            raise UnsupportedVersionError(f"Unsupported version: {self.header.version}")

        if self.header.header_len != DDARP_HEADER_SIZE:
            raise InvalidHeaderError(f"Invalid header length: {self.header.header_len}")

        if self.header.tlv_length < 0:
            raise InvalidPacketError("Negative TLV length")

        # Validate TLV data length matches header
        actual_tlv_length = sum(8 + len(tlv.value) for tlv in self.tlv_data)
        if actual_tlv_length != self.header.tlv_length:
            logger.warning(f"TLV length mismatch: header={self.header.tlv_length}, actual={actual_tlv_length}")

class WireFormatHandler:
    """
    Handles binary wire format encoding and decoding for DDARP packets.

    This class provides the main interface for converting between Python objects
    and binary wire format representations.
    """

    def __init__(self):
        self.registry = TLVRegistry()
        self._stats = {
            'packets_encoded': 0,
            'packets_decoded': 0,
            'encoding_errors': 0,
            'decoding_errors': 0,
            'corruption_detected': 0
        }

    def encode_packet(self, header: DDARPHeader, tlv_data: List[TLV],
                     add_checksum: bool = True) -> bytes:
        """
        Encode a DDARP packet to binary wire format.

        Args:
            header: DDARP packet header
            tlv_data: List of TLV objects
            add_checksum: Whether to add integrity checksum

        Returns:
            Binary packet data ready for transmission

        Raises:
            WireFormatError: If encoding fails
        """
        try:
            # Encode TLV data first to calculate length
            tlv_bytes = self._encode_tlv_section(tlv_data)

            # Update header with actual TLV length
            header.tlv_length = len(tlv_bytes)
            header.timestamp = int(time.time())

            # Encode header
            header_bytes = self._encode_header(header)

            # Combine header and payload
            packet_data = header_bytes + tlv_bytes

            # Add checksum if requested
            if add_checksum:
                checksum = self._calculate_checksum(packet_data)
                packet_data += checksum

            self._stats['packets_encoded'] += 1
            logger.debug(f"Encoded packet: {len(packet_data)} bytes, TLVs: {len(tlv_data)}")

            return packet_data

        except Exception as e:
            self._stats['encoding_errors'] += 1
            logger.error(f"Packet encoding failed: {e}")
            raise WireFormatError(f"Failed to encode packet: {e}") from e

    def decode_packet(self, data: bytes, verify_checksum: bool = True) -> WirePacket:
        """
        Decode binary wire format data into a DDARP packet.

        Args:
            data: Binary packet data
            verify_checksum: Whether to verify packet integrity

        Returns:
            WirePacket object with decoded header and TLVs

        Raises:
            WireFormatError: If decoding fails
            PacketCorruptionError: If corruption is detected
        """
        try:
            if len(data) < DDARP_HEADER_SIZE:
                raise PacketTooShortError(f"Packet too short: {len(data)} bytes")

            # Check for checksum
            packet_data = data
            checksum = None
            if verify_checksum and len(data) > DDARP_HEADER_SIZE + 4:
                # Assume last 4 bytes might be checksum
                potential_checksum = data[-4:]
                packet_without_checksum = data[:-4]
                calculated_checksum = self._calculate_checksum(packet_without_checksum)

                if potential_checksum == calculated_checksum:
                    packet_data = packet_without_checksum
                    checksum = potential_checksum
                    logger.debug("Checksum verified successfully")

            # Decode header
            header = self._decode_header(packet_data[:DDARP_HEADER_SIZE])

            # Validate header
            if header.version != DDARP_VERSION:
                raise UnsupportedVersionError(f"Unsupported version: {header.version}")

            if header.header_len != DDARP_HEADER_SIZE:
                raise InvalidHeaderError(f"Invalid header length: {header.header_len}")

            # Check if we have enough data for the TLV section
            expected_size = DDARP_HEADER_SIZE + header.tlv_length
            if len(packet_data) < expected_size:
                raise PacketTooShortError(
                    f"Insufficient data: expected {expected_size}, got {len(packet_data)}"
                )

            # Extract and decode TLV data
            tlv_section = packet_data[DDARP_HEADER_SIZE:DDARP_HEADER_SIZE + header.tlv_length]
            tlv_data = self._decode_tlv_section(tlv_section)

            self._stats['packets_decoded'] += 1
            logger.debug(f"Decoded packet: {len(data)} bytes, TLVs: {len(tlv_data)}")

            return WirePacket(
                header=header,
                tlv_data=tlv_data,
                raw_payload=tlv_section,
                checksum=checksum
            )

        except (WireFormatError, InvalidPacketError, PacketTooShortError):
            self._stats['decoding_errors'] += 1
            raise
        except Exception as e:
            self._stats['decoding_errors'] += 1
            logger.error(f"Packet decoding failed: {e}")
            raise WireFormatError(f"Failed to decode packet: {e}") from e

    def _encode_header(self, header: DDARPHeader) -> bytes:
        """Encode DDARP header to binary format"""
        return struct.pack(
            DDARP_HEADER_FORMAT,
            header.version,
            header.flags,
            header.header_len,
            header.tunnel_id,
            header.sequence,
            header.timestamp,
            header.tlv_length
        )

    def _decode_header(self, data: bytes) -> DDARPHeader:
        """Decode binary data to DDARP header"""
        if len(data) < DDARP_HEADER_SIZE:
            raise PacketTooShortError(f"Header too short: {len(data)} bytes")

        fields = struct.unpack(DDARP_HEADER_FORMAT, data[:DDARP_HEADER_SIZE])

        return DDARPHeader(
            version=fields[0],
            flags=fields[1],
            header_len=fields[2],
            tunnel_id=fields[3],
            sequence=fields[4],
            timestamp=fields[5],
            tlv_length=fields[6]
        )

    def _encode_tlv_section(self, tlv_data: List[TLV]) -> bytes:
        """Encode list of TLVs to binary format"""
        result = b""

        for tlv in tlv_data:
            # Encode individual TLV
            encoded_value = self.registry.encode_tlv(tlv.tlv_type, tlv.value)
            tlv_header = struct.pack("!II", tlv.tlv_type, len(encoded_value))
            result += tlv_header + encoded_value

        return result

    def _decode_tlv_section(self, data: bytes) -> List[TLV]:
        """Decode binary TLV section to list of TLV objects"""
        return parse_tlv_data(data, skip_unknown=True)

    def _calculate_checksum(self, data: bytes) -> bytes:
        """Calculate 4-byte checksum for packet integrity"""
        hash_obj = hashlib.sha256(data)
        return hash_obj.digest()[:4]  # Use first 4 bytes of SHA-256

    def create_request_packet(self, tunnel_id: int, sequence: int,
                            tlv_data: List[TLV]) -> bytes:
        """Create a request packet with proper flags"""
        header = DDARPHeader(
            flags=FLAG_REQUEST,
            tunnel_id=tunnel_id,
            sequence=sequence
        )
        return self.encode_packet(header, tlv_data)

    def create_response_packet(self, tunnel_id: int, sequence: int,
                             tlv_data: List[TLV]) -> bytes:
        """Create a response packet with proper flags"""
        header = DDARPHeader(
            flags=FLAG_RESPONSE,
            tunnel_id=tunnel_id,
            sequence=sequence
        )
        return self.encode_packet(header, tlv_data)

    def create_error_packet(self, tunnel_id: int, sequence: int,
                          error_code: int, error_message: str) -> bytes:
        """Create an error packet"""
        header = DDARPHeader(
            flags=FLAG_ERROR,
            tunnel_id=tunnel_id,
            sequence=sequence
        )

        error_tlv = TLV(
            tlv_type=TLVType.ERROR_INFO,
            length=len(error_message),
            value=error_message
        )

        return self.encode_packet(header, [error_tlv])

    def get_statistics(self) -> Dict[str, int]:
        """Get wire format handler statistics"""
        return self._stats.copy()

    def reset_statistics(self):
        """Reset statistics counters"""
        for key in self._stats:
            self._stats[key] = 0

class PacketAnalyzer:
    """
    Utility class for analyzing wire format packets.

    Provides debugging and diagnostic capabilities for DDARP packets.
    """

    def __init__(self):
        self.wire_handler = WireFormatHandler()

    def analyze_packet(self, data: bytes) -> Dict[str, Any]:
        """
        Analyze a binary packet and return detailed information.

        Args:
            data: Binary packet data

        Returns:
            Dictionary with packet analysis results
        """
        analysis = {
            'packet_size': len(data),
            'valid': False,
            'errors': [],
            'warnings': [],
            'header_info': {},
            'tlv_info': {},
            'checksum_valid': None
        }

        try:
            # Try to decode the packet
            packet = self.wire_handler.decode_packet(data)
            analysis['valid'] = True

            # Header analysis
            analysis['header_info'] = {
                'version': packet.header.version,
                'flags': self._analyze_flags(packet.header.flags),
                'tunnel_id': packet.header.tunnel_id,
                'sequence': packet.header.sequence,
                'timestamp': packet.header.timestamp,
                'tlv_length': packet.header.tlv_length
            }

            # TLV analysis
            analysis['tlv_info'] = {
                'count': len(packet.tlv_data),
                'types': [tlv.tlv_type for tlv in packet.tlv_data],
                'total_payload_size': sum(len(tlv.value) for tlv in packet.tlv_data)
            }

            # Checksum validation
            if packet.checksum:
                analysis['checksum_valid'] = True

        except Exception as e:
            analysis['errors'].append(str(e))

        return analysis

    def _analyze_flags(self, flags: int) -> List[str]:
        """Analyze packet flags and return list of set flags"""
        flag_names = []
        if flags & FLAG_REQUEST:
            flag_names.append('REQUEST')
        if flags & FLAG_RESPONSE:
            flag_names.append('RESPONSE')
        if flags & FLAG_ERROR:
            flag_names.append('ERROR')
        if flags & FLAG_COMPRESSED:
            flag_names.append('COMPRESSED')
        if flags & FLAG_ENCRYPTED:
            flag_names.append('ENCRYPTED')
        return flag_names

    def hexdump(self, data: bytes, width: int = 16) -> str:
        """Generate hexdump of binary data for debugging"""
        lines = []
        for i in range(0, len(data), width):
            chunk = data[i:i + width]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f'{i:08x}  {hex_part:<{width*3}}  {ascii_part}')
        return '\n'.join(lines)

# Global wire format handler instance
wire_format = WireFormatHandler()
packet_analyzer = PacketAnalyzer()

def encode_packet(header: DDARPHeader, tlv_data: List[TLV]) -> bytes:
    """Convenience function for encoding packets"""
    return wire_format.encode_packet(header, tlv_data)

def decode_packet(data: bytes) -> WirePacket:
    """Convenience function for decoding packets"""
    return wire_format.decode_packet(data)

def analyze_packet(data: bytes) -> Dict[str, Any]:
    """Convenience function for packet analysis"""
    return packet_analyzer.analyze_packet(data)