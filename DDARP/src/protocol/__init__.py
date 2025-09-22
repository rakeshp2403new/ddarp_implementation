"""
DDARP Protocol Package

This package implements the wire format and TLV (Type-Length-Value) system
for the DDARP (Distributed Dynamic Adaptive Routing Protocol).

Modules:
    packet: DDARP packet header structure and basic packet handling
    tlv: TLV registry, encoding/decoding, and parser
    codec: High-level encoding/decoding functions
    exceptions: Protocol-specific exceptions
"""

from .packet import (
    DDARPPacket, DDARPHeader,
    FLAG_REQUEST, FLAG_RESPONSE, FLAG_ERROR, FLAG_COMPRESSED, FLAG_ENCRYPTED
)
from .tlv import TLVRegistry, TLVParser, TLVType
from .codec import DDARPCodec
from .exceptions import (
    DDARPProtocolError,
    InvalidPacketError,
    TLVParsingError,
    UnknownTLVError
)

__all__ = [
    'DDARPPacket',
    'DDARPHeader',
    'FLAG_REQUEST',
    'FLAG_RESPONSE',
    'FLAG_ERROR',
    'FLAG_COMPRESSED',
    'FLAG_ENCRYPTED',
    'TLVRegistry',
    'TLVParser',
    'TLVType',
    'DDARPCodec',
    'DDARPProtocolError',
    'InvalidPacketError',
    'TLVParsingError',
    'UnknownTLVError'
]

__version__ = '1.0.0'