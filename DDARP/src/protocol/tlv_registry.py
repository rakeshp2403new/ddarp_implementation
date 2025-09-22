"""
DDARP TLV Registry - Centralized TLV Type Definitions and Management

This module provides a centralized registry for all DDARP TLV types, including
standard types, vendor extensions, and experimental types. It also provides
utilities for TLV type management and validation.

TLV Type Allocation:
- 0x0001-0x0FFF: Standard DDARP TLVs
- 0x1000-0x1FFF: Vendor-specific TLVs
- 0x2000-0x2FFF: Experimental TLVs
- 0x3000-0x7FFF: Reserved for future use
- 0x8000-0xFFFF: Critical TLVs (must be understood)
"""

import logging
from enum import IntEnum, unique
from typing import Dict, Set, Optional, Callable, Any, Type
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@unique
class StandardTLVType(IntEnum):
    """Standard DDARP TLV types - must be supported by all implementations."""

    # Core protocol TLVs (0x0001-0x000F)
    T3_TERNARY = 0x0001         # Ternary computation results
    OWL_METRICS = 0x0002        # One-Way Latency metrics
    ROUTING_INFO = 0x0003       # Routing table information
    PATH_VECTOR = 0x0004        # Path vector information
    ALGORITHM_RESULT = 0x0005   # Algorithm computation results

    # Network topology TLVs (0x0010-0x001F)
    NEIGHBOR_LIST = 0x0010      # List of neighboring nodes
    TOPOLOGY_UPDATE = 0x0011    # Network topology changes
    LINK_STATE = 0x0012         # Link state advertisements
    NETWORK_GRAPH = 0x0013      # Complete network graph
    NODE_CAPABILITIES = 0x0014  # Node capability announcements

    # Performance metrics TLVs (0x0020-0x002F)
    BANDWIDTH_INFO = 0x0020     # Bandwidth measurements
    JITTER_METRICS = 0x0021     # Network jitter measurements
    PACKET_LOSS = 0x0022        # Packet loss statistics
    LATENCY_MATRIX = 0x0023     # Latency measurement matrix
    QOS_METRICS = 0x0024        # Quality of Service metrics
    PERFORMANCE_STATS = 0x0025  # General performance statistics

    # Control and signaling TLVs (0x0030-0x003F)
    KEEPALIVE = 0x0030          # Keepalive messages
    ERROR_INFO = 0x0031         # Error reporting
    CAPABILITIES = 0x0032       # Node capabilities
    SESSION_INFO = 0x0033       # Session establishment
    AUTH_TOKEN = 0x0034         # Authentication tokens
    HEARTBEAT = 0x0035          # Node heartbeat

    # Data plane TLVs (0x0040-0x004F)
    TUNNEL_INFO = 0x0040        # Tunnel configuration
    FORWARDING_RULE = 0x0041    # Forwarding rules
    TRAFFIC_CLASS = 0x0042      # Traffic classification
    VPP_CONFIG = 0x0043         # VPP configuration
    INTERFACE_CONFIG = 0x0044   # Interface configuration

    # Security TLVs (0x0050-0x005F)
    CERTIFICATE = 0x0050        # X.509 certificates
    SIGNATURE = 0x0051          # Digital signatures
    ENCRYPTION_PARAMS = 0x0052  # Encryption parameters
    KEY_EXCHANGE = 0x0053       # Key exchange data

    # Enhanced OWL TLVs (0x0060-0x006F)
    OWL_MATRIX_ENTRY = 0x0060   # Single matrix entry
    OWL_PREDICTION = 0x0061     # Latency predictions
    OWL_QUALITY = 0x0062        # Measurement quality indicators
    OWL_CALIBRATION = 0x0063    # Calibration parameters

    # Multi-algorithm TLVs (0x0070-0x007F)
    ALGORITHM_SELECTION = 0x0070 # Algorithm selection criteria
    ML_MODEL_DATA = 0x0071      # Machine learning model data
    GENETIC_PARAMS = 0x0072     # Genetic algorithm parameters
    HYBRID_CONFIG = 0x0073      # Hybrid algorithm configuration

@unique
class VendorTLVType(IntEnum):
    """Vendor-specific TLV types (0x1000-0x1FFF)."""

    # Cisco vendor TLVs (0x1000-0x10FF)
    CISCO_BASE = 0x1000
    CISCO_PROPRIETARY = 0x1001

    # Juniper vendor TLVs (0x1100-0x11FF)
    JUNIPER_BASE = 0x1100
    JUNIPER_PROPRIETARY = 0x1101

    # Generic vendor range start
    VENDOR_RANGE_START = 0x1000
    VENDOR_RANGE_END = 0x1FFF

@unique
class ExperimentalTLVType(IntEnum):
    """Experimental TLV types (0x2000-0x2FFF)."""

    EXPERIMENTAL_BASE = 0x2000
    RESEARCH_PROTOTYPE = 0x2001
    TESTING_FRAMEWORK = 0x2002
    SIMULATION_DATA = 0x2003
    DEBUG_INFO = 0x2004

    # Range bounds
    EXPERIMENTAL_RANGE_START = 0x2000
    EXPERIMENTAL_RANGE_END = 0x2FFF

@unique
class CriticalTLVType(IntEnum):
    """Critical TLVs that must be understood (0x8000-0xFFFF)."""

    CRITICAL_ERROR = 0x8000     # Critical error condition
    MANDATORY_UPGRADE = 0x8001  # Mandatory protocol upgrade
    SECURITY_ALERT = 0x8002     # Security alert
    SHUTDOWN_NOTICE = 0x8003    # Graceful shutdown notice

    # Range bounds
    CRITICAL_RANGE_START = 0x8000
    CRITICAL_RANGE_END = 0xFFFF

@dataclass
class TLVDefinition:
    """Complete definition of a TLV type."""

    tlv_type: int
    name: str
    description: str
    is_critical: bool = False
    is_vendor_specific: bool = False
    is_experimental: bool = False
    encoder: Optional[Callable[[Any], bytes]] = None
    decoder: Optional[Callable[[bytes], Any]] = None
    validator: Optional[Callable[[Any], bool]] = None

    @property
    def type_category(self) -> str:
        """Get the category of this TLV type."""
        if self.is_critical:
            return "critical"
        elif self.is_vendor_specific:
            return "vendor"
        elif self.is_experimental:
            return "experimental"
        else:
            return "standard"

class TLVTypeRegistry:
    """
    Centralized registry for all TLV types.

    Manages TLV type definitions, provides validation, and handles
    encoding/decoding function registration.
    """

    def __init__(self):
        self._registry: Dict[int, TLVDefinition] = {}
        self._name_to_type: Dict[str, int] = {}
        self._registered_ranges: Set[range] = set()

        # Initialize with standard types
        self._register_standard_types()

    def _register_standard_types(self):
        """Register all standard DDARP TLV types."""

        # Standard type definitions
        standard_definitions = {
            StandardTLVType.T3_TERNARY: TLVDefinition(
                StandardTLVType.T3_TERNARY,
                "T3_TERNARY",
                "Ternary computation results"
            ),
            StandardTLVType.OWL_METRICS: TLVDefinition(
                StandardTLVType.OWL_METRICS,
                "OWL_METRICS",
                "One-Way Latency metrics"
            ),
            StandardTLVType.ROUTING_INFO: TLVDefinition(
                StandardTLVType.ROUTING_INFO,
                "ROUTING_INFO",
                "Routing table information"
            ),
            StandardTLVType.NEIGHBOR_LIST: TLVDefinition(
                StandardTLVType.NEIGHBOR_LIST,
                "NEIGHBOR_LIST",
                "List of neighboring nodes"
            ),
            StandardTLVType.BANDWIDTH_INFO: TLVDefinition(
                StandardTLVType.BANDWIDTH_INFO,
                "BANDWIDTH_INFO",
                "Bandwidth measurements"
            ),
            StandardTLVType.KEEPALIVE: TLVDefinition(
                StandardTLVType.KEEPALIVE,
                "KEEPALIVE",
                "Keepalive messages"
            ),
            StandardTLVType.ERROR_INFO: TLVDefinition(
                StandardTLVType.ERROR_INFO,
                "ERROR_INFO",
                "Error reporting"
            ),
            StandardTLVType.CAPABILITIES: TLVDefinition(
                StandardTLVType.CAPABILITIES,
                "CAPABILITIES",
                "Node capabilities"
            )
        }

        for tlv_type, definition in standard_definitions.items():
            self._registry[tlv_type] = definition
            self._name_to_type[definition.name] = tlv_type

    def register_tlv_type(self, definition: TLVDefinition) -> bool:
        """
        Register a new TLV type.

        Args:
            definition: TLV type definition

        Returns:
            True if registration successful, False if already exists
        """
        if definition.tlv_type in self._registry:
            logger.warning(f"TLV type {definition.tlv_type} already registered")
            return False

        # Validate type ranges
        if not self._validate_type_range(definition.tlv_type, definition):
            return False

        self._registry[definition.tlv_type] = definition
        self._name_to_type[definition.name] = definition.tlv_type

        logger.info(f"Registered TLV type {definition.tlv_type}: {definition.name}")
        return True

    def _validate_type_range(self, tlv_type: int, definition: TLVDefinition) -> bool:
        """Validate that TLV type is in correct range for its category."""

        if definition.is_critical:
            return CriticalTLVType.CRITICAL_RANGE_START <= tlv_type <= CriticalTLVType.CRITICAL_RANGE_END
        elif definition.is_vendor_specific:
            return VendorTLVType.VENDOR_RANGE_START <= tlv_type <= VendorTLVType.VENDOR_RANGE_END
        elif definition.is_experimental:
            return ExperimentalTLVType.EXPERIMENTAL_RANGE_START <= tlv_type <= ExperimentalTLVType.EXPERIMENTAL_RANGE_END
        else:
            # Standard types
            return 0x0001 <= tlv_type <= 0x0FFF

    def get_tlv_definition(self, tlv_type: int) -> Optional[TLVDefinition]:
        """Get TLV definition by type."""
        return self._registry.get(tlv_type)

    def get_tlv_type_by_name(self, name: str) -> Optional[int]:
        """Get TLV type by name."""
        return self._name_to_type.get(name)

    def is_known_type(self, tlv_type: int) -> bool:
        """Check if TLV type is known."""
        return tlv_type in self._registry

    def is_critical_type(self, tlv_type: int) -> bool:
        """Check if TLV type is critical."""
        definition = self._registry.get(tlv_type)
        if definition:
            return definition.is_critical
        # Unknown types in critical range are considered critical
        return CriticalTLVType.CRITICAL_RANGE_START <= tlv_type <= CriticalTLVType.CRITICAL_RANGE_END

    def is_vendor_type(self, tlv_type: int) -> bool:
        """Check if TLV type is vendor-specific."""
        return VendorTLVType.VENDOR_RANGE_START <= tlv_type <= VendorTLVType.VENDOR_RANGE_END

    def is_experimental_type(self, tlv_type: int) -> bool:
        """Check if TLV type is experimental."""
        return ExperimentalTLVType.EXPERIMENTAL_RANGE_START <= tlv_type <= ExperimentalTLVType.EXPERIMENTAL_RANGE_END

    def get_all_types(self) -> Dict[int, TLVDefinition]:
        """Get all registered TLV types."""
        return self._registry.copy()

    def get_types_by_category(self, category: str) -> Dict[int, TLVDefinition]:
        """Get TLV types filtered by category."""
        return {
            tlv_type: definition
            for tlv_type, definition in self._registry.items()
            if definition.type_category == category
        }

    def register_vendor_range(self, vendor_id: int, start: int, end: int) -> bool:
        """
        Register a vendor-specific TLV range.

        Args:
            vendor_id: Vendor identifier
            start: Start of range (inclusive)
            end: End of range (inclusive)

        Returns:
            True if registration successful
        """
        if not (VendorTLVType.VENDOR_RANGE_START <= start <= end <= VendorTLVType.VENDOR_RANGE_END):
            logger.error(f"Vendor range {start}-{end} outside vendor range")
            return False

        vendor_range = range(start, end + 1)

        # Check for conflicts
        for existing_range in self._registered_ranges:
            if (start <= existing_range.stop - 1 and end >= existing_range.start):
                logger.error(f"Vendor range {start}-{end} conflicts with existing range")
                return False

        self._registered_ranges.add(vendor_range)
        logger.info(f"Registered vendor range {start}-{end} for vendor {vendor_id}")
        return True

    def validate_tlv_value(self, tlv_type: int, value: Any) -> bool:
        """Validate TLV value using registered validator."""
        definition = self._registry.get(tlv_type)
        if definition and definition.validator:
            try:
                return definition.validator(value)
            except Exception as e:
                logger.error(f"Validation error for TLV {tlv_type}: {e}")
                return False
        return True  # No validator means always valid

    def get_statistics(self) -> Dict[str, int]:
        """Get registry statistics."""
        stats = {
            'total_types': len(self._registry),
            'standard_types': 0,
            'vendor_types': 0,
            'experimental_types': 0,
            'critical_types': 0
        }

        for definition in self._registry.values():
            if definition.is_critical:
                stats['critical_types'] += 1
            elif definition.is_vendor_specific:
                stats['vendor_types'] += 1
            elif definition.is_experimental:
                stats['experimental_types'] += 1
            else:
                stats['standard_types'] += 1

        return stats

# Global registry instance
tlv_registry = TLVTypeRegistry()

# Convenience functions for common operations
def get_tlv_definition(tlv_type: int) -> Optional[TLVDefinition]:
    """Get TLV definition by type."""
    return tlv_registry.get_tlv_definition(tlv_type)

def is_critical_tlv(tlv_type: int) -> bool:
    """Check if TLV type is critical."""
    return tlv_registry.is_critical_type(tlv_type)

def is_known_tlv(tlv_type: int) -> bool:
    """Check if TLV type is known."""
    return tlv_registry.is_known_type(tlv_type)

def register_vendor_tlv(vendor_id: int, tlv_type: int, name: str, description: str) -> bool:
    """Register a vendor-specific TLV type."""
    definition = TLVDefinition(
        tlv_type=tlv_type,
        name=name,
        description=description,
        is_vendor_specific=True
    )
    return tlv_registry.register_tlv_type(definition)

def register_experimental_tlv(tlv_type: int, name: str, description: str) -> bool:
    """Register an experimental TLV type."""
    definition = TLVDefinition(
        tlv_type=tlv_type,
        name=name,
        description=description,
        is_experimental=True
    )
    return tlv_registry.register_tlv_type(definition)

# Export important types and constants
__all__ = [
    'StandardTLVType',
    'VendorTLVType',
    'ExperimentalTLVType',
    'CriticalTLVType',
    'TLVDefinition',
    'TLVTypeRegistry',
    'tlv_registry',
    'get_tlv_definition',
    'is_critical_tlv',
    'is_known_tlv',
    'register_vendor_tlv',
    'register_experimental_tlv'
]