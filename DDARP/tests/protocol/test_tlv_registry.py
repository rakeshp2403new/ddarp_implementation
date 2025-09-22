"""
Unit tests for DDARP TLV Registry.

Tests the TLVTypeRegistry, TLVDefinition, and related functionality
for managing TLV type definitions and validation.
"""

import pytest
from unittest.mock import Mock

from src.protocol.tlv_registry import (
    TLVTypeRegistry, TLVDefinition,
    StandardTLVType, VendorTLVType, ExperimentalTLVType, CriticalTLVType,
    tlv_registry, get_tlv_definition, is_critical_tlv, is_known_tlv,
    register_vendor_tlv, register_experimental_tlv
)


class TestTLVDefinition:
    """Test TLVDefinition functionality."""

    def test_tlv_definition_creation(self):
        """Test TLVDefinition creation."""
        definition = TLVDefinition(
            tlv_type=0x1001,
            name="TEST_TLV",
            description="Test TLV for unit tests",
            is_vendor_specific=True
        )

        assert definition.tlv_type == 0x1001
        assert definition.name == "TEST_TLV"
        assert definition.description == "Test TLV for unit tests"
        assert definition.is_vendor_specific == True
        assert definition.is_experimental == False
        assert definition.is_critical == False

    def test_type_category_property(self):
        """Test type_category property."""
        # Standard TLV
        std_def = TLVDefinition(0x0001, "STD", "Standard TLV")
        assert std_def.type_category == "standard"

        # Vendor TLV
        vendor_def = TLVDefinition(0x1001, "VENDOR", "Vendor TLV", is_vendor_specific=True)
        assert vendor_def.type_category == "vendor"

        # Experimental TLV
        exp_def = TLVDefinition(0x2001, "EXP", "Experimental TLV", is_experimental=True)
        assert exp_def.type_category == "experimental"

        # Critical TLV
        crit_def = TLVDefinition(0x8001, "CRIT", "Critical TLV", is_critical=True)
        assert crit_def.type_category == "critical"


class TestTLVTypeRegistry:
    """Test TLVTypeRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = TLVTypeRegistry()

    def test_standard_types_registered(self):
        """Test that standard types are pre-registered."""
        # Check some standard types
        t3_def = self.registry.get_tlv_definition(StandardTLVType.T3_TERNARY)
        assert t3_def is not None
        assert t3_def.name == "T3_TERNARY"

        owl_def = self.registry.get_tlv_definition(StandardTLVType.OWL_METRICS)
        assert owl_def is not None
        assert owl_def.name == "OWL_METRICS"

        keepalive_def = self.registry.get_tlv_definition(StandardTLVType.KEEPALIVE)
        assert keepalive_def is not None
        assert keepalive_def.name == "KEEPALIVE"

    def test_register_new_tlv_type(self):
        """Test registering new TLV type."""
        definition = TLVDefinition(
            tlv_type=0x0100,
            name="CUSTOM_TLV",
            description="Custom TLV for testing"
        )

        result = self.registry.register_tlv_type(definition)
        assert result == True

        # Verify it's registered
        retrieved = self.registry.get_tlv_definition(0x0100)
        assert retrieved == definition

        # Verify name lookup
        tlv_type = self.registry.get_tlv_type_by_name("CUSTOM_TLV")
        assert tlv_type == 0x0100

    def test_register_duplicate_type(self):
        """Test registering duplicate TLV type."""
        definition1 = TLVDefinition(0x0200, "TEST1", "First test")
        definition2 = TLVDefinition(0x0200, "TEST2", "Second test")

        assert self.registry.register_tlv_type(definition1) == True
        assert self.registry.register_tlv_type(definition2) == False  # Duplicate

    def test_vendor_type_validation(self):
        """Test vendor TLV type range validation."""
        # Valid vendor type
        valid_vendor = TLVDefinition(
            tlv_type=0x1001,
            name="VENDOR_TLV",
            description="Valid vendor TLV",
            is_vendor_specific=True
        )
        assert self.registry.register_tlv_type(valid_vendor) == True

        # Invalid vendor type (wrong range)
        invalid_vendor = TLVDefinition(
            tlv_type=0x0001,  # Standard range
            name="BAD_VENDOR",
            description="Invalid vendor TLV",
            is_vendor_specific=True
        )
        assert self.registry.register_tlv_type(invalid_vendor) == False

    def test_experimental_type_validation(self):
        """Test experimental TLV type range validation."""
        # Valid experimental type
        valid_exp = TLVDefinition(
            tlv_type=0x2001,
            name="EXP_TLV",
            description="Valid experimental TLV",
            is_experimental=True
        )
        assert self.registry.register_tlv_type(valid_exp) == True

        # Invalid experimental type (wrong range)
        invalid_exp = TLVDefinition(
            tlv_type=0x0001,  # Standard range
            name="BAD_EXP",
            description="Invalid experimental TLV",
            is_experimental=True
        )
        assert self.registry.register_tlv_type(invalid_exp) == False

    def test_critical_type_validation(self):
        """Test critical TLV type range validation."""
        # Valid critical type
        valid_crit = TLVDefinition(
            tlv_type=0x8001,
            name="CRIT_TLV",
            description="Valid critical TLV",
            is_critical=True
        )
        assert self.registry.register_tlv_type(valid_crit) == True

        # Invalid critical type (wrong range)
        invalid_crit = TLVDefinition(
            tlv_type=0x0001,  # Standard range
            name="BAD_CRIT",
            description="Invalid critical TLV",
            is_critical=True
        )
        assert self.registry.register_tlv_type(invalid_crit) == False

    def test_is_known_type(self):
        """Test is_known_type method."""
        # Known standard type
        assert self.registry.is_known_type(StandardTLVType.T3_TERNARY) == True

        # Unknown type
        assert self.registry.is_known_type(0x9999) == False

        # Register new type and check
        definition = TLVDefinition(0x0300, "NEW_TLV", "New TLV")
        self.registry.register_tlv_type(definition)
        assert self.registry.is_known_type(0x0300) == True

    def test_is_critical_type(self):
        """Test is_critical_type method."""
        # Known critical type
        crit_def = TLVDefinition(0x8001, "CRIT", "Critical", is_critical=True)
        self.registry.register_tlv_type(crit_def)
        assert self.registry.is_critical_type(0x8001) == True

        # Non-critical type
        assert self.registry.is_critical_type(StandardTLVType.KEEPALIVE) == False

        # Unknown type in critical range should be considered critical
        assert self.registry.is_critical_type(0x8999) == True

        # Unknown type in non-critical range
        assert self.registry.is_critical_type(0x0999) == False

    def test_is_vendor_type(self):
        """Test is_vendor_type method."""
        assert self.registry.is_vendor_type(0x1001) == True
        assert self.registry.is_vendor_type(0x1FFF) == True
        assert self.registry.is_vendor_type(0x0001) == False
        assert self.registry.is_vendor_type(0x2001) == False

    def test_is_experimental_type(self):
        """Test is_experimental_type method."""
        assert self.registry.is_experimental_type(0x2001) == True
        assert self.registry.is_experimental_type(0x2FFF) == True
        assert self.registry.is_experimental_type(0x0001) == False
        assert self.registry.is_experimental_type(0x1001) == False

    def test_get_types_by_category(self):
        """Test get_types_by_category method."""
        # Register types in different categories
        std_def = TLVDefinition(0x0400, "STD", "Standard")
        vendor_def = TLVDefinition(0x1001, "VENDOR", "Vendor", is_vendor_specific=True)
        exp_def = TLVDefinition(0x2001, "EXP", "Experimental", is_experimental=True)

        self.registry.register_tlv_type(std_def)
        self.registry.register_tlv_type(vendor_def)
        self.registry.register_tlv_type(exp_def)

        # Get by category
        standard_types = self.registry.get_types_by_category("standard")
        vendor_types = self.registry.get_types_by_category("vendor")
        experimental_types = self.registry.get_types_by_category("experimental")

        assert 0x0400 in standard_types
        assert 0x1001 in vendor_types
        assert 0x2001 in experimental_types

    def test_register_vendor_range(self):
        """Test vendor range registration."""
        # Valid range
        result = self.registry.register_vendor_range(123, 0x1100, 0x11FF)
        assert result == True

        # Overlapping range
        result = self.registry.register_vendor_range(456, 0x1150, 0x1200)
        assert result == False

        # Invalid range (outside vendor space)
        result = self.registry.register_vendor_range(789, 0x0100, 0x0200)
        assert result == False

    def test_validate_tlv_value(self):
        """Test TLV value validation."""
        # Register TLV with validator
        validator = Mock(return_value=True)
        definition = TLVDefinition(
            tlv_type=0x0500,
            name="VALIDATED_TLV",
            description="TLV with validator",
            validator=validator
        )
        self.registry.register_tlv_type(definition)

        # Test validation
        result = self.registry.validate_tlv_value(0x0500, "test_value")
        assert result == True
        validator.assert_called_once_with("test_value")

        # Test without validator (should always pass)
        result = self.registry.validate_tlv_value(StandardTLVType.KEEPALIVE, "any_value")
        assert result == True

        # Test with failing validator
        validator.return_value = False
        result = self.registry.validate_tlv_value(0x0500, "bad_value")
        assert result == False

    def test_get_statistics(self):
        """Test statistics generation."""
        # Initial statistics
        stats = self.registry.get_statistics()
        initial_total = stats['total_types']
        initial_standard = stats['standard_types']

        # Register types
        std_def = TLVDefinition(0x0600, "STD", "Standard")
        vendor_def = TLVDefinition(0x1002, "VENDOR", "Vendor", is_vendor_specific=True)
        exp_def = TLVDefinition(0x2002, "EXP", "Experimental", is_experimental=True)
        crit_def = TLVDefinition(0x8002, "CRIT", "Critical", is_critical=True)

        self.registry.register_tlv_type(std_def)
        self.registry.register_tlv_type(vendor_def)
        self.registry.register_tlv_type(exp_def)
        self.registry.register_tlv_type(crit_def)

        # Check updated statistics
        stats = self.registry.get_statistics()
        assert stats['total_types'] == initial_total + 4
        assert stats['standard_types'] == initial_standard + 1
        assert stats['vendor_types'] >= 1
        assert stats['experimental_types'] >= 1
        assert stats['critical_types'] >= 1


class TestGlobalRegistry:
    """Test global registry instance and convenience functions."""

    def test_global_registry_access(self):
        """Test accessing global registry."""
        # Should have standard types pre-registered
        definition = get_tlv_definition(StandardTLVType.T3_TERNARY)
        assert definition is not None
        assert definition.name == "T3_TERNARY"

    def test_is_critical_tlv_function(self):
        """Test is_critical_tlv convenience function."""
        assert is_critical_tlv(StandardTLVType.KEEPALIVE) == False
        assert is_critical_tlv(0x8001) == True

    def test_is_known_tlv_function(self):
        """Test is_known_tlv convenience function."""
        assert is_known_tlv(StandardTLVType.T3_TERNARY) == True
        assert is_known_tlv(0x9999) == False

    def test_register_vendor_tlv_function(self):
        """Test register_vendor_tlv convenience function."""
        result = register_vendor_tlv(123, 0x1003, "VENDOR_TEST", "Test vendor TLV")
        assert result == True

        # Verify registration
        definition = get_tlv_definition(0x1003)
        assert definition is not None
        assert definition.name == "VENDOR_TEST"
        assert definition.is_vendor_specific == True

    def test_register_experimental_tlv_function(self):
        """Test register_experimental_tlv convenience function."""
        result = register_experimental_tlv(0x2003, "EXP_TEST", "Test experimental TLV")
        assert result == True

        # Verify registration
        definition = get_tlv_definition(0x2003)
        assert definition is not None
        assert definition.name == "EXP_TEST"
        assert definition.is_experimental == True


class TestTLVTypeEnums:
    """Test TLV type enum definitions."""

    def test_standard_tlv_type_values(self):
        """Test StandardTLVType enum values."""
        assert StandardTLVType.T3_TERNARY == 0x0001
        assert StandardTLVType.OWL_METRICS == 0x0002
        assert StandardTLVType.ROUTING_INFO == 0x0003
        assert StandardTLVType.KEEPALIVE == 0x0030
        assert StandardTLVType.ERROR_INFO == 0x0031

    def test_vendor_tlv_type_ranges(self):
        """Test VendorTLVType ranges."""
        assert VendorTLVType.VENDOR_RANGE_START == 0x1000
        assert VendorTLVType.VENDOR_RANGE_END == 0x1FFF
        assert VendorTLVType.CISCO_BASE == 0x1000
        assert VendorTLVType.JUNIPER_BASE == 0x1100

    def test_experimental_tlv_type_ranges(self):
        """Test ExperimentalTLVType ranges."""
        assert ExperimentalTLVType.EXPERIMENTAL_RANGE_START == 0x2000
        assert ExperimentalTLVType.EXPERIMENTAL_RANGE_END == 0x2FFF
        assert ExperimentalTLVType.EXPERIMENTAL_BASE == 0x2000

    def test_critical_tlv_type_ranges(self):
        """Test CriticalTLVType ranges."""
        assert CriticalTLVType.CRITICAL_RANGE_START == 0x8000
        assert CriticalTLVType.CRITICAL_RANGE_END == 0xFFFF
        assert CriticalTLVType.CRITICAL_ERROR == 0x8000


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = TLVTypeRegistry()

    def test_empty_name_handling(self):
        """Test handling of empty names."""
        definition = TLVDefinition(0x0700, "", "TLV with empty name")
        result = self.registry.register_tlv_type(definition)
        assert result == True

        # Should be able to retrieve by type but not by name
        retrieved = self.registry.get_tlv_definition(0x0700)
        assert retrieved is not None

        name_lookup = self.registry.get_tlv_type_by_name("")
        assert name_lookup == 0x0700

    def test_boundary_values(self):
        """Test boundary values for type ranges."""
        # Test exact boundaries
        assert self.registry.is_vendor_type(0x1000) == True  # Start of vendor range
        assert self.registry.is_vendor_type(0x1FFF) == True  # End of vendor range
        assert self.registry.is_vendor_type(0x0FFF) == False  # Just before vendor range
        assert self.registry.is_vendor_type(0x2000) == False  # Just after vendor range

    def test_large_tlv_numbers(self):
        """Test very large TLV type numbers."""
        large_tlv = 0xFFFF
        assert self.registry.is_critical_type(large_tlv) == True

        # Register at boundary
        definition = TLVDefinition(large_tlv, "MAX_TLV", "Maximum TLV", is_critical=True)
        result = self.registry.register_tlv_type(definition)
        assert result == True

    def test_validator_exception_handling(self):
        """Test exception handling in validators."""
        def failing_validator(value):
            raise ValueError("Validator failed")

        definition = TLVDefinition(
            tlv_type=0x0800,
            name="FAILING_VALIDATOR",
            description="TLV with failing validator",
            validator=failing_validator
        )
        self.registry.register_tlv_type(definition)

        # Should return False when validator raises exception
        result = self.registry.validate_tlv_value(0x0800, "test")
        assert result == False