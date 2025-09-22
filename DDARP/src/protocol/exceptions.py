"""
DDARP Protocol Exceptions

Custom exceptions for DDARP protocol parsing and handling.
"""


class DDARPProtocolError(Exception):
    """Base exception for all DDARP protocol errors."""
    pass


class InvalidPacketError(DDARPProtocolError):
    """Raised when a packet is malformed or invalid."""

    def __init__(self, message: str, packet_data: bytes = None):
        super().__init__(message)
        self.packet_data = packet_data


class TLVParsingError(DDARPProtocolError):
    """Raised when TLV parsing fails."""

    def __init__(self, message: str, tlv_type: int = None, tlv_data: bytes = None):
        super().__init__(message)
        self.tlv_type = tlv_type
        self.tlv_data = tlv_data


class UnknownTLVError(TLVParsingError):
    """Raised when encountering an unknown TLV type."""

    def __init__(self, tlv_type: int, tlv_data: bytes = None):
        message = f"Unknown TLV type: {tlv_type}"
        super().__init__(message, tlv_type, tlv_data)


class PacketTooShortError(InvalidPacketError):
    """Raised when packet is too short to contain valid header or TLVs."""
    pass


class InvalidHeaderError(InvalidPacketError):
    """Raised when packet header is invalid."""
    pass


class TLVLengthError(TLVParsingError):
    """Raised when TLV length field is invalid or inconsistent."""
    pass