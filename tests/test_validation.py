"""Tests for validation module."""

import pytest
from unittest.mock import Mock

from custom_components.ariston.validation import (
    ConfigValidator,
    ValidationError,
    validate_config_entry,
    validate_service_call,
    safe_get_device_name,
    safe_get_temperature,
)


class TestConfigValidator:
    """Test cases for ConfigValidator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ConfigValidator()

    def test_validate_config_valid(self):
        """Test valid configuration validation."""
        config = {
            "username": "test@example.com",
            "password": "password123",
            "api_url_setting": "https://api.example.com",
            "api_user_agent": "TestAgent/1.0",
        }
        
        result = self.validator.validate_config(config)
        assert result == config
        assert not self.validator.has_errors()

    def test_validate_config_invalid_email(self):
        """Test invalid email validation."""
        config = {
            "username": "invalid-email",
            "password": "password123",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_config(config)
        
        assert "Username must be a valid email address" in str(exc_info.value)

    def test_validate_config_short_password(self):
        """Test short password validation."""
        config = {
            "username": "test@example.com",
            "password": "123",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_config(config)
        
        assert "length" in str(exc_info.value).lower()

    def test_validate_device_name_valid(self):
        """Test valid device name validation."""
        valid_names = ["Device 1", "My-Device", "Device_123", "Test Device"]
        
        for name in valid_names:
            result = self.validator.validate_device_name(name)
            assert result == name.strip()

    def test_validate_device_name_invalid(self):
        """Test invalid device name validation."""
        invalid_names = ["", "Device@123", "Device#Test", None, 123]
        
        for name in invalid_names:
            with pytest.raises(ValidationError):
                self.validator.validate_device_name(name)

    def test_validate_temperature_valid(self):
        """Test valid temperature validation."""
        valid_temps = [20, 20.5, "25", -10, 100]
        
        for temp in valid_temps:
            result = self.validator.validate_temperature(temp)
            assert isinstance(result, float)

    def test_validate_temperature_invalid(self):
        """Test invalid temperature validation."""
        invalid_temps = ["invalid", None, -100, 200, "abc"]
        
        for temp in invalid_temps:
            with pytest.raises(ValidationError):
                self.validator.validate_temperature(temp)

    def test_validate_zone_number_valid(self):
        """Test valid zone number validation."""
        valid_zones = [0, 1, 5, 10, "3"]
        
        for zone in valid_zones:
            result = self.validator.validate_zone_number(zone)
            assert isinstance(result, int)

    def test_validate_zone_number_invalid(self):
        """Test invalid zone number validation."""
        invalid_zones = [-1, 11, "invalid", None, 15]
        
        for zone in invalid_zones:
            with pytest.raises(ValidationError):
                self.validator.validate_zone_number(zone)

    def test_validate_scan_interval_valid(self):
        """Test valid scan interval validation."""
        valid_intervals = [30, 60, 300, 1800, "120"]
        
        for interval in valid_intervals:
            result = self.validator.validate_scan_interval(interval)
            assert isinstance(result, int)

    def test_validate_scan_interval_invalid(self):
        """Test invalid scan interval validation."""
        invalid_intervals = [10, 4000, "invalid", None, -30]
        
        for interval in invalid_intervals:
            with pytest.raises(ValidationError):
                self.validator.validate_scan_interval(interval)


class TestValidationFunctions:
    """Test cases for validation functions."""

    def test_validate_config_entry(self):
        """Test config entry validation function."""
        config = {
            "username": "test@example.com",
            "password": "password123",
        }
        
        result = validate_config_entry(config)
        assert result == config

    def test_validate_service_call(self):
        """Test service call validation function."""
        service_data = {
            "device_id": "test_device",
            "item_id": "test_item",
            "zone": 1,
            "value": 25.5,
        }
        
        result = validate_service_call(service_data)
        assert result == service_data

    def test_safe_get_device_name_valid(self):
        """Test safe device name retrieval with valid name."""
        device_data = {"name": "Test Device"}
        result = safe_get_device_name(device_data)
        assert result == "Test Device"

    def test_safe_get_device_name_invalid(self):
        """Test safe device name retrieval with invalid name."""
        device_data = {"name": "Invalid@Device"}
        result = safe_get_device_name(device_data)
        assert result == "Unknown Device"

    def test_safe_get_device_name_missing(self):
        """Test safe device name retrieval with missing name."""
        device_data = {}
        result = safe_get_device_name(device_data)
        assert result == "Unknown Device"

    def test_safe_get_temperature_valid(self):
        """Test safe temperature retrieval with valid value."""
        result = safe_get_temperature(25.5)
        assert result == 25.5

    def test_safe_get_temperature_invalid(self):
        """Test safe temperature retrieval with invalid value."""
        result = safe_get_temperature("invalid")
        assert result == 20.0  # default value

    def test_safe_get_temperature_out_of_range(self):
        """Test safe temperature retrieval with out of range value."""
        result = safe_get_temperature(200)
        assert result == 20.0  # default value













