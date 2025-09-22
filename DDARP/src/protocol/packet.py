"""
DDARP Packet Header Structure

Implements the DDARP packet header format and basic packet handling.

Packet Header Format (20 bytes):
+--------+--------+--------+--------+
| Version|  Flags |   Header Len    |
+--------+--------+--------+--------+
|            Tunnel ID              |
+--------+--------+--------+--------+
|             Sequence              |
+--------+--------+--------+--------+
|            Timestamp              |
+--------+--------+--------+--------+
|           TLV Length              |
+--------+--------+--------+--------+

Fields:
- Version (1 byte): Protocol version (currently 1)
- Flags (1 byte): Control flags
- Header Len (2 bytes): Length of header in bytes (always 20)
- Tunnel ID (4 bytes): Unique tunnel identifier
- Sequence (4 bytes): Packet sequence number
- Timestamp (4 bytes): Unix timestamp
- TLV Length (4 bytes): Total length of TLV data following header
"""

import struct
import time
import logging
from typing import Optional, NamedTuple
from dataclasses import dataclass

from .exceptions import InvalidPacketError, PacketTooShortError, InvalidHeaderError

logger = logging.getLogger(__name__)

# Protocol constants
DDARP_VERSION = 1
DDARP_HEADER_SIZE = 20
DDARP_HEADER_FORMAT = "!BBHIIII"  # Network byte order

# Flag bits
FLAG_REQUEST = 0x01
FLAG_RESPONSE = 0x02
FLAG_ERROR = 0x04
FLAG_COMPRESSED = 0x08
FLAG_ENCRYPTED = 0x10


@dataclass
class DDARPHeader:
    """DDARP packet header structure."""

    version: int = DDARP_VERSION
    flags: int = 0
    header_len: int = DDARP_HEADER_SIZE
    tunnel_id: int = 0
    sequence: int = 0
    timestamp: int = 0
    tlv_length: int = 0

    def __post_init__(self):
        """Validate header fields after initialization."""
        if self.version != DDARP_VERSION:
            raise InvalidHeaderError(f"Unsupported version: {self.version}")
        if self.header_len != DDARP_HEADER_SIZE:
            raise InvalidHeaderError(f"Invalid header length: {self.header_len}")
        if self.tlv_length < 0:
            raise InvalidHeaderError(f"Invalid TLV length: {self.tlv_length}")
        if self.timestamp == 0:
            self.timestamp = int(time.time())

    def pack(self) -> bytes:
        """Pack header into binary format."""
        try:
            return struct.pack(
                DDARP_HEADER_FORMAT,
                self.version,
                self.flags,
                self.header_len,
                self.tunnel_id,
                self.sequence,
                self.timestamp,
                self.tlv_length
            )
        except struct.error as e:
            raise InvalidHeaderError(f"Failed to pack header: {e}")

    @classmethod
    def unpack(cls, data: bytes) -> 'DDARPHeader':
        """Unpack binary data into header structure."""
        if len(data) < DDARP_HEADER_SIZE:
            raise PacketTooShortError(
                f"Packet too short for header: {len(data)} < {DDARP_HEADER_SIZE}"
            )

        try:
            fields = struct.unpack(DDARP_HEADER_FORMAT, data[:DDARP_HEADER_SIZE])
            return cls(
                version=fields[0],
                flags=fields[1],
                header_len=fields[2],
                tunnel_id=fields[3],
                sequence=fields[4],
                timestamp=fields[5],
                tlv_length=fields[6]
            )
        except struct.error as e:
            raise InvalidHeaderError(f"Failed to unpack header: {e}")

    def is_flag_set(self, flag: int) -> bool:
        """Check if a specific flag is set."""
        return bool(self.flags & flag)

    def set_flag(self, flag: int):
        """Set a specific flag."""
        self.flags |= flag

    def clear_flag(self, flag: int):
        """Clear a specific flag."""
        self.flags &= ~flag

    def __str__(self) -> str:
        """String representation of header."""
        flags_str = []
        if self.is_flag_set(FLAG_REQUEST):
            flags_str.append("REQ")
        if self.is_flag_set(FLAG_RESPONSE):
            flags_str.append("RESP")
        if self.is_flag_set(FLAG_ERROR):
            flags_str.append("ERR")
        if self.is_flag_set(FLAG_COMPRESSED):
            flags_str.append("COMP")
        if self.is_flag_set(FLAG_ENCRYPTED):
            flags_str.append("ENC")

        flags_display = "|".join(flags_str) if flags_str else "NONE"

        return (
            f"DDARPHeader(v={self.version}, flags={flags_display}, "
            f"tunnel_id={self.tunnel_id}, seq={self.sequence}, "
            f"ts={self.timestamp}, tlv_len={self.tlv_length})"
        )


class DDARPPacket:
    """Complete DDARP packet with header and TLV data."""

    def __init__(self, header: DDARPHeader, tlv_data: bytes = b""):
        """Initialize packet with header and optional TLV data."""
        self.header = header
        self.tlv_data = tlv_data

        # Update header TLV length to match actual data
        self.header.tlv_length = len(tlv_data)

    def pack(self) -> bytes:
        """Pack complete packet into binary format."""
        header_bytes = self.header.pack()
        return header_bytes + self.tlv_data

    @classmethod
    def unpack(cls, data: bytes) -> 'DDARPPacket':
        """Unpack binary data into packet structure."""
        if len(data) < DDARP_HEADER_SIZE:
            raise PacketTooShortError(
                f"Data too short for packet: {len(data)} < {DDARP_HEADER_SIZE}"
            )

        header = DDARPHeader.unpack(data)

        expected_total_len = DDARP_HEADER_SIZE + header.tlv_length
        if len(data) < expected_total_len:
            raise PacketTooShortError(
                f"Packet shorter than expected: {len(data)} < {expected_total_len}"
            )

        tlv_data = data[DDARP_HEADER_SIZE:DDARP_HEADER_SIZE + header.tlv_length]

        logger.debug(
            f"Unpacked packet: tunnel_id={header.tunnel_id}, "
            f"seq={header.sequence}, tlv_len={header.tlv_length}"
        )

        return cls(header, tlv_data)

    def validate(self) -> bool:
        """Validate packet structure and consistency."""
        try:
            # Header validation is done in __post_init__
            if len(self.tlv_data) != self.header.tlv_length:
                raise InvalidPacketError(
                    f"TLV data length mismatch: "
                    f"header={self.header.tlv_length}, actual={len(self.tlv_data)}"
                )
            return True
        except Exception as e:
            logger.warning(f"Packet validation failed: {e}")
            return False

    def __len__(self) -> int:
        """Return total packet size in bytes."""
        return DDARP_HEADER_SIZE + len(self.tlv_data)

    def __str__(self) -> str:
        """String representation of packet."""
        return f"DDARPPacket({self.header}, tlv_data={len(self.tlv_data)} bytes)"