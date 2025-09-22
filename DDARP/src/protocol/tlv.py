"""
DDARP TLV (Type-Length-Value) System

Implements TLV registry, encoding/decoding, and parsing with support for
unknown TLV types and future extensions.

TLV Format (variable length):
+--------+--------+--------+--------+
|        Type (2 bytes)             |
+--------+--------+--------+--------+
|        Length (2 bytes)           |
+--------+--------+--------+--------+
|        Value (variable)           |
+--------+--------+--------+--------+

Type: 2-byte TLV type identifier
Length: 2-byte length of value field (excluding type and length)
Value: Variable-length value data
"""

import struct
import logging
import json
from enum import IntEnum
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass

from .exceptions import TLVParsingError, TLVLengthError, UnknownTLVError

logger = logging.getLogger(__name__)

# TLV header format and size
TLV_HEADER_FORMAT = "!HH"  # Type (2 bytes) + Length (2 bytes)
TLV_HEADER_SIZE = 4


class TLVType(IntEnum):
    """DDARP TLV type registry."""

    # Core protocol TLVs
    T3_TERNARY = 0x0001      # Ternary computation results
    OWL_METRICS = 0x0002     # One-Way Latency metrics
    ROUTING_INFO = 0x0003    # Routing table information

    # Network topology TLVs
    NEIGHBOR_LIST = 0x0010   # List of neighboring nodes
    TOPOLOGY_UPDATE = 0x0011 # Network topology changes

    # Performance metrics TLVs
    BANDWIDTH_INFO = 0x0020  # Bandwidth measurements
    JITTER_METRICS = 0x0021  # Network jitter measurements
    PACKET_LOSS = 0x0022     # Packet loss statistics

    # Control and signaling TLVs
    KEEPALIVE = 0x0030       # Keepalive messages
    ERROR_INFO = 0x0031      # Error reporting
    CAPABILITIES = 0x0032    # Node capabilities

    # Future extensions (reserved ranges)
    # 0x1000-0x1FFF: Vendor-specific TLVs
    # 0x2000-0x2FFF: Experimental TLVs
    # 0x8000-0xFFFF: Critical TLVs (must be understood)


@dataclass
class TLV:
    """Single TLV entry."""

    type: int
    length: int
    value: bytes

    def __post_init__(self):
        """Validate TLV after initialization."""
        if self.length != len(self.value):
            raise TLVLengthError(
                f"TLV length mismatch: header={self.length}, actual={len(self.value)}"
            )

    def pack(self) -> bytes:
        """Pack TLV into binary format."""
        try:
            header = struct.pack(TLV_HEADER_FORMAT, self.type, self.length)
            return header + self.value
        except struct.error as e:
            raise TLVParsingError(f"Failed to pack TLV type {self.type}: {e}")

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> Tuple['TLV', int]:
        """Unpack TLV from binary data, return TLV and next offset."""
        if len(data) - offset < TLV_HEADER_SIZE:
            raise TLVParsingError(
                f"Insufficient data for TLV header at offset {offset}"
            )

        try:
            tlv_type, tlv_length = struct.unpack(
                TLV_HEADER_FORMAT,
                data[offset:offset + TLV_HEADER_SIZE]
            )
        except struct.error as e:
            raise TLVParsingError(f"Failed to unpack TLV header at offset {offset}: {e}")

        value_start = offset + TLV_HEADER_SIZE
        value_end = value_start + tlv_length

        if len(data) < value_end:
            raise TLVParsingError(
                f"Insufficient data for TLV value: need {value_end}, have {len(data)}"
            )

        value = data[value_start:value_end]
        tlv = cls(tlv_type, tlv_length, value)

        return tlv, value_end

    def __str__(self) -> str:
        """String representation of TLV."""
        type_name = TLVType(self.type).name if self.type in TLVType._value2member_map_ else f"UNKNOWN_{self.type:04X}"
        return f"TLV({type_name}, len={self.length}, value={self.value.hex()[:20]}{'...' if len(self.value) > 10 else ''})"


class TLVEncoder:
    """TLV encoding utilities for different data types."""

    @staticmethod
    def encode_string(s: str) -> bytes:
        """Encode string as UTF-8 bytes."""
        return s.encode('utf-8')

    @staticmethod
    def encode_uint32(value: int) -> bytes:
        """Encode 32-bit unsigned integer."""
        return struct.pack("!I", value)

    @staticmethod
    def encode_uint64(value: int) -> bytes:
        """Encode 64-bit unsigned integer."""
        return struct.pack("!Q", value)

    @staticmethod
    def encode_float(value: float) -> bytes:
        """Encode IEEE 754 float."""
        return struct.pack("!f", value)

    @staticmethod
    def encode_double(value: float) -> bytes:
        """Encode IEEE 754 double."""
        return struct.pack("!d", value)

    @staticmethod
    def encode_json(obj: Any) -> bytes:
        """Encode object as JSON bytes."""
        return json.dumps(obj, separators=(',', ':')).encode('utf-8')

    @staticmethod
    def encode_owl_metrics(latency_ns: int, jitter_ns: int, timestamp: int) -> bytes:
        """Encode OWL metrics (latency, jitter, timestamp)."""
        return struct.pack("!QQI", latency_ns, jitter_ns, timestamp)

    @staticmethod
    def encode_routing_info(dest_ip: str, next_hop: str, metric: int) -> bytes:
        """Encode routing information."""
        dest_bytes = dest_ip.encode('utf-8')
        hop_bytes = next_hop.encode('utf-8')
        return struct.pack("!HH", len(dest_bytes), len(hop_bytes)) + dest_bytes + hop_bytes + struct.pack("!I", metric)


class TLVDecoder:
    """TLV decoding utilities for different data types."""

    @staticmethod
    def decode_string(data: bytes) -> str:
        """Decode UTF-8 string."""
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError as e:
            raise TLVParsingError(f"Invalid UTF-8 string: {e}")

    @staticmethod
    def decode_uint32(data: bytes) -> int:
        """Decode 32-bit unsigned integer."""
        if len(data) != 4:
            raise TLVParsingError(f"Invalid uint32 length: {len(data)}")
        return struct.unpack("!I", data)[0]

    @staticmethod
    def decode_uint64(data: bytes) -> int:
        """Decode 64-bit unsigned integer."""
        if len(data) != 8:
            raise TLVParsingError(f"Invalid uint64 length: {len(data)}")
        return struct.unpack("!Q", data)[0]

    @staticmethod
    def decode_float(data: bytes) -> float:
        """Decode IEEE 754 float."""
        if len(data) != 4:
            raise TLVParsingError(f"Invalid float length: {len(data)}")
        return struct.unpack("!f", data)[0]

    @staticmethod
    def decode_double(data: bytes) -> float:
        """Decode IEEE 754 double."""
        if len(data) != 8:
            raise TLVParsingError(f"Invalid double length: {len(data)}")
        return struct.unpack("!d", data)[0]

    @staticmethod
    def decode_json(data: bytes) -> Any:
        """Decode JSON object."""
        try:
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise TLVParsingError(f"Invalid JSON data: {e}")

    @staticmethod
    def decode_owl_metrics(data: bytes) -> Tuple[int, int, int]:
        """Decode OWL metrics (latency_ns, jitter_ns, timestamp)."""
        if len(data) != 20:  # 8 + 8 + 4 bytes
            raise TLVParsingError(f"Invalid OWL metrics length: {len(data)}")
        return struct.unpack("!QQI", data)

    @staticmethod
    def decode_routing_info(data: bytes) -> Tuple[str, str, int]:
        """Decode routing information (dest_ip, next_hop, metric)."""
        if len(data) < 8:  # Minimum: 2 length fields + 4 byte metric
            raise TLVParsingError(f"Invalid routing info length: {len(data)}")

        dest_len, hop_len = struct.unpack("!HH", data[:4])
        offset = 4

        if len(data) < offset + dest_len + hop_len + 4:
            raise TLVParsingError("Insufficient data for routing info")

        dest_ip = data[offset:offset + dest_len].decode('utf-8')
        offset += dest_len

        next_hop = data[offset:offset + hop_len].decode('utf-8')
        offset += hop_len

        metric = struct.unpack("!I", data[offset:offset + 4])[0]

        return dest_ip, next_hop, metric


class TLVRegistry:
    """Registry for TLV types and their handlers."""

    def __init__(self):
        """Initialize TLV registry with default handlers."""
        self._handlers: Dict[int, Dict[str, Any]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default TLV handlers."""
        # T3_TERNARY - JSON encoded ternary computation results
        self.register(
            TLVType.T3_TERNARY,
            encoder=TLVEncoder.encode_json,
            decoder=TLVDecoder.decode_json,
            description="Ternary computation results"
        )

        # OWL_METRICS - Binary encoded latency metrics
        self.register(
            TLVType.OWL_METRICS,
            encoder=TLVEncoder.encode_owl_metrics,
            decoder=TLVDecoder.decode_owl_metrics,
            description="One-Way Latency metrics"
        )

        # ROUTING_INFO - Binary encoded routing information
        self.register(
            TLVType.ROUTING_INFO,
            encoder=TLVEncoder.encode_routing_info,
            decoder=TLVDecoder.decode_routing_info,
            description="Routing table information"
        )

        # KEEPALIVE - Empty value
        self.register(
            TLVType.KEEPALIVE,
            encoder=lambda x: b"",
            decoder=lambda data: None,
            description="Keepalive message"
        )

        # ERROR_INFO - String encoded error message
        self.register(
            TLVType.ERROR_INFO,
            encoder=TLVEncoder.encode_string,
            decoder=TLVDecoder.decode_string,
            description="Error information"
        )

    def register(self, tlv_type: int, encoder=None, decoder=None, description: str = ""):
        """Register a TLV type with optional encoder/decoder."""
        self._handlers[tlv_type] = {
            'encoder': encoder,
            'decoder': decoder,
            'description': description
        }
        logger.debug(f"Registered TLV type {tlv_type:04X}: {description}")

    def encode(self, tlv_type: int, value: Any) -> TLV:
        """Encode value into TLV using registered encoder."""
        if tlv_type not in self._handlers:
            raise UnknownTLVError(tlv_type)

        encoder = self._handlers[tlv_type].get('encoder')
        if encoder is None:
            raise TLVParsingError(f"No encoder registered for TLV type {tlv_type:04X}")

        try:
            if tlv_type == TLVType.OWL_METRICS:
                # Special case for OWL metrics - value should be tuple
                encoded_value = encoder(*value)
            elif tlv_type == TLVType.ROUTING_INFO:
                # Special case for routing info - value should be tuple
                encoded_value = encoder(*value)
            else:
                encoded_value = encoder(value)

            return TLV(tlv_type, len(encoded_value), encoded_value)
        except Exception as e:
            raise TLVParsingError(f"Failed to encode TLV type {tlv_type:04X}: {e}")

    def decode(self, tlv: TLV) -> Any:
        """Decode TLV value using registered decoder."""
        if tlv.type not in self._handlers:
            logger.warning(f"Unknown TLV type {tlv.type:04X}, returning raw bytes")
            return tlv.value

        decoder = self._handlers[tlv.type].get('decoder')
        if decoder is None:
            logger.warning(f"No decoder for TLV type {tlv.type:04X}, returning raw bytes")
            return tlv.value

        try:
            return decoder(tlv.value)
        except Exception as e:
            logger.error(f"Failed to decode TLV type {tlv.type:04X}: {e}")
            return tlv.value

    def is_known(self, tlv_type: int) -> bool:
        """Check if TLV type is registered."""
        return tlv_type in self._handlers

    def get_description(self, tlv_type: int) -> str:
        """Get description for TLV type."""
        return self._handlers.get(tlv_type, {}).get('description', f"Unknown TLV {tlv_type:04X}")


class TLVParser:
    """TLV parser with support for unknown TLVs and skip rules."""

    def __init__(self, registry: Optional[TLVRegistry] = None):
        """Initialize parser with optional TLV registry."""
        self.registry = registry or TLVRegistry()
        self.skip_unknown = True  # Skip unknown TLVs by default

    def parse(self, data: bytes) -> List[TLV]:
        """Parse TLV data into list of TLV objects."""
        tlvs = []
        offset = 0

        while offset < len(data):
            try:
                tlv, next_offset = TLV.unpack(data, offset)

                # Log TLV parsing
                logger.debug(f"Parsed TLV: {tlv}")

                # Check if TLV type is known
                if not self.registry.is_known(tlv.type):
                    if self.skip_unknown:
                        logger.warning(f"Skipping unknown TLV type {tlv.type:04X}")
                        offset = next_offset
                        continue
                    else:
                        raise UnknownTLVError(tlv.type, tlv.value)

                tlvs.append(tlv)
                offset = next_offset

            except TLVParsingError as e:
                logger.error(f"TLV parsing error at offset {offset}: {e}")
                if self.skip_unknown:
                    # Try to skip to next potential TLV
                    offset += 1
                    continue
                else:
                    raise

        return tlvs

    def encode_tlvs(self, tlvs: List[TLV]) -> bytes:
        """Encode list of TLVs into binary data."""
        result = b""
        for tlv in tlvs:
            result += tlv.pack()
        return result

    def create_tlv(self, tlv_type: int, value: Any) -> TLV:
        """Create TLV using registry encoder."""
        return self.registry.encode(tlv_type, value)

    def decode_tlv(self, tlv: TLV) -> Any:
        """Decode TLV using registry decoder."""
        return self.registry.decode(tlv)