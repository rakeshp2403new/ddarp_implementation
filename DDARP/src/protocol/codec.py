"""
DDARP Codec - High-level encoding/decoding interface

Provides a high-level interface for encoding and decoding complete DDARP
packets with TLV data. Handles packet assembly, validation, and error recovery.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from .packet import DDARPPacket, DDARPHeader, FLAG_REQUEST, FLAG_RESPONSE, FLAG_ERROR
from .tlv import TLV, TLVParser, TLVRegistry, TLVType
from .exceptions import DDARPProtocolError, InvalidPacketError, TLVParsingError

logger = logging.getLogger(__name__)


class DDARPCodec:
    """High-level DDARP packet codec."""

    def __init__(self, registry: Optional[TLVRegistry] = None):
        """Initialize codec with TLV registry."""
        self.registry = registry or TLVRegistry()
        self.parser = TLVParser(self.registry)

    def encode_packet(
        self,
        tunnel_id: int,
        sequence: int,
        tlv_data: List[Tuple[int, Any]],
        flags: int = 0,
        timestamp: Optional[int] = None
    ) -> bytes:
        """
        Encode a complete DDARP packet.

        Args:
            tunnel_id: Tunnel identifier
            sequence: Packet sequence number
            tlv_data: List of (tlv_type, value) tuples
            flags: Packet flags
            timestamp: Unix timestamp (auto-generated if None)

        Returns:
            Binary packet data

        Raises:
            DDARPProtocolError: If encoding fails
        """
        try:
            # Create TLVs from data
            tlvs = []
            for tlv_type, value in tlv_data:
                tlv = self.parser.create_tlv(tlv_type, value)
                tlvs.append(tlv)

            # Encode TLV binary data
            tlv_binary = self.parser.encode_tlvs(tlvs)

            # Create header
            header = DDARPHeader(
                tunnel_id=tunnel_id,
                sequence=sequence,
                flags=flags,
                tlv_length=len(tlv_binary),
                timestamp=timestamp or 0  # Will be auto-set in __post_init__
            )

            # Create and pack complete packet
            packet = DDARPPacket(header, tlv_binary)
            return packet.pack()

        except Exception as e:
            raise DDARPProtocolError(f"Failed to encode packet: {e}")

    def decode_packet(self, data: bytes) -> Tuple[DDARPHeader, List[Tuple[int, Any]]]:
        """
        Decode a complete DDARP packet.

        Args:
            data: Binary packet data

        Returns:
            Tuple of (header, [(tlv_type, decoded_value), ...])

        Raises:
            DDARPProtocolError: If decoding fails
        """
        try:
            # Unpack packet
            packet = DDARPPacket.unpack(data)

            # Validate packet
            if not packet.validate():
                raise InvalidPacketError("Packet validation failed")

            # Parse TLVs
            tlvs = self.parser.parse(packet.tlv_data)

            # Decode TLV values
            decoded_tlvs = []
            for tlv in tlvs:
                try:
                    decoded_value = self.parser.decode_tlv(tlv)
                    decoded_tlvs.append((tlv.type, decoded_value))
                except Exception as e:
                    logger.warning(f"Failed to decode TLV {tlv.type:04X}: {e}")
                    # Include raw bytes for failed decoding
                    decoded_tlvs.append((tlv.type, tlv.value))

            return packet.header, decoded_tlvs

        except Exception as e:
            raise DDARPProtocolError(f"Failed to decode packet: {e}")

    def create_request_packet(
        self,
        tunnel_id: int,
        sequence: int,
        tlv_data: List[Tuple[int, Any]]
    ) -> bytes:
        """Create a request packet with REQUEST flag set."""
        return self.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=tlv_data,
            flags=FLAG_REQUEST
        )

    def create_response_packet(
        self,
        tunnel_id: int,
        sequence: int,
        tlv_data: List[Tuple[int, Any]]
    ) -> bytes:
        """Create a response packet with RESPONSE flag set."""
        return self.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=tlv_data,
            flags=FLAG_RESPONSE
        )

    def create_error_packet(
        self,
        tunnel_id: int,
        sequence: int,
        error_msg: str
    ) -> bytes:
        """Create an error packet with ERROR flag set."""
        error_tlv = [(TLVType.ERROR_INFO, error_msg)]
        return self.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=error_tlv,
            flags=FLAG_ERROR
        )

    def create_keepalive_packet(self, tunnel_id: int, sequence: int) -> bytes:
        """Create a keepalive packet."""
        keepalive_tlv = [(TLVType.KEEPALIVE, None)]
        return self.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=keepalive_tlv
        )

    def create_owl_metrics_packet(
        self,
        tunnel_id: int,
        sequence: int,
        latency_ns: int,
        jitter_ns: int,
        timestamp: int
    ) -> bytes:
        """Create a packet with OWL metrics."""
        owl_tlv = [(TLVType.OWL_METRICS, (latency_ns, jitter_ns, timestamp))]
        return self.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=owl_tlv
        )

    def create_routing_info_packet(
        self,
        tunnel_id: int,
        sequence: int,
        dest_ip: str,
        next_hop: str,
        metric: int
    ) -> bytes:
        """Create a packet with routing information."""
        routing_tlv = [(TLVType.ROUTING_INFO, (dest_ip, next_hop, metric))]
        return self.encode_packet(
            tunnel_id=tunnel_id,
            sequence=sequence,
            tlv_data=routing_tlv
        )

    def validate_packet(self, data: bytes) -> bool:
        """
        Validate packet without full decoding.

        Returns True if packet appears valid, False otherwise.
        """
        try:
            packet = DDARPPacket.unpack(data)
            return packet.validate()
        except Exception as e:
            logger.debug(f"Packet validation failed: {e}")
            return False

    def get_packet_info(self, data: bytes) -> Dict[str, Any]:
        """
        Extract basic packet information without full TLV decoding.

        Returns dictionary with packet metadata.
        """
        try:
            packet = DDARPPacket.unpack(data)
            header = packet.header

            info = {
                'version': header.version,
                'flags': header.flags,
                'tunnel_id': header.tunnel_id,
                'sequence': header.sequence,
                'timestamp': header.timestamp,
                'tlv_length': header.tlv_length,
                'total_length': len(data),
                'valid': packet.validate()
            }

            # Parse TLV types without decoding values
            try:
                tlvs = self.parser.parse(packet.tlv_data)
                info['tlv_types'] = [tlv.type for tlv in tlvs]
                info['tlv_count'] = len(tlvs)
            except Exception as e:
                logger.debug(f"Failed to parse TLVs for info: {e}")
                info['tlv_types'] = []
                info['tlv_count'] = 0

            return info

        except Exception as e:
            return {
                'error': str(e),
                'valid': False,
                'data_length': len(data)
            }