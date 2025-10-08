"""Validation utilities for Ariston integration."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

import voluptuous as vol
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv

from .const import API_URL_SETTING, API_USER_AGENT, DOMAIN
from .logging_config import get_ariston_logger

_LOGGER = get_ariston_logger(__name__)

# Validation patterns
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
DEVICE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_]+$")
API_URL_PATTERN = re.compile(r"^https?://[a-zA-Z0-9.-]+(?::[0-9]+)?(?:/[^\s]*)?$")

# Validation schemas
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): vol.All(
            cv.string,
            vol.Length(min=3, max=100),
            vol.Match(USERNAME_PATTERN, msg="Username must be a valid email address"),
        ),
        vol.Required(CONF_PASSWORD): vol.All(
            cv.string,
            vol.Length(min=6, max=100),
        ),
        vol.Optional(API_URL_SETTING): vol.All(
            cv.string,
            vol.Match(API_URL_PATTERN, msg="API URL must be a valid HTTP/HTTPS URL"),
        ),
        vol.Optional(API_USER_AGENT): vol.All(
            cv.string,
            vol.Length(min=10, max=200),
        ),
    }
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("item_id"): vol.All(
            cv.string,
            vol.Length(min=1, max=50),
            vol.Match(r"^[a-zA-Z0-9_]+$", msg="Item ID must contain only alphanumeric characters and underscores"),
        ),
        vol.Required("zone"): vol.All(
            cv.positive_int,
            vol.Range(min=0, max=10, msg="Zone must be between 0 and 10"),
        ),
        vol.Required("value"): vol.All(
            vol.Coerce(float),
            vol.Range(min=-1000, max=1000, msg="Value must be between -1000 and 1000"),
        ),
    }
)


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        """Initialize validation error."""
        super().__init__(message)
        self.field = field
        self.message = message


class ConfigValidator:
    """Configuration validator for Ariston integration."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self._errors: List[str] = []

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration data."""
        self._errors.clear()
        
        _LOGGER.debug("Validating config: type=%s, value=%s", type(config), config)
        
        if not isinstance(config, dict):
            error_msg = f"Configuration must be a dictionary, got: {type(config)}"
            _LOGGER.error(error_msg)
            raise ValidationError(error_msg)
        
        try:
            validated_config = CONFIG_SCHEMA(config)
            _LOGGER.debug("Configuration validation successful")
            return validated_config
        except vol.Invalid as err:
            error_msg = f"Configuration validation failed: {err}"
            _LOGGER.error(error_msg)
            raise ValidationError(error_msg) from err

    def validate_service_data(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate service call data."""
        self._errors.clear()
        
        try:
            validated_data = SERVICE_SCHEMA(service_data)
            _LOGGER.debug("Service data validation successful")
            return validated_data
        except vol.Invalid as err:
            error_msg = f"Service data validation failed: {err}"
            _LOGGER.error(error_msg)
            raise ValidationError(error_msg) from err

    def validate_device_name(self, name: str) -> str:
        """Validate device name."""
        if not name or not isinstance(name, str):
            raise ValidationError("Device name must be a non-empty string")
        
        if not DEVICE_NAME_PATTERN.match(name):
            raise ValidationError("Device name contains invalid characters")
        
        if len(name) > 50:
            raise ValidationError("Device name must be 50 characters or less")
        
        return name.strip()

    def validate_temperature(self, temp: Union[int, float], min_temp: float = -50, max_temp: float = 100) -> float:
        """Validate temperature value."""
        try:
            temp_float = float(temp)
        except (ValueError, TypeError):
            raise ValidationError(f"Temperature must be a number, got: {temp}")
        
        if not min_temp <= temp_float <= max_temp:
            raise ValidationError(f"Temperature must be between {min_temp} and {max_temp}, got: {temp_float}")
        
        return temp_float

    def validate_zone_number(self, zone: Union[int, str]) -> int:
        """Validate zone number."""
        try:
            zone_int = int(zone)
        except (ValueError, TypeError):
            raise ValidationError(f"Zone must be a number, got: {zone}")
        
        if not 0 <= zone_int <= 10:
            raise ValidationError(f"Zone must be between 0 and 10, got: {zone_int}")
        
        return zone_int

    def validate_scan_interval(self, interval: Union[int, str]) -> int:
        """Validate scan interval."""
        try:
            interval_int = int(interval)
        except (ValueError, TypeError):
            raise ValidationError(f"Scan interval must be a number, got: {interval}")
        
        if not 30 <= interval_int <= 3600:  # 30 seconds to 1 hour
            raise ValidationError(f"Scan interval must be between 30 and 3600 seconds, got: {interval_int}")
        
        return interval_int

    @property
    def errors(self) -> List[str]:
        """Get validation errors."""
        return self._errors.copy()

    def has_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self._errors) > 0


def validate_config_entry(entry_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a configuration entry."""
    validator = ConfigValidator()
    return validator.validate_config(entry_data)


def validate_service_call(service_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a service call."""
    validator = ConfigValidator()
    return validator.validate_service_data(service_data)


def safe_get_device_name(device_data: Dict[str, Any], default: str = "Unknown Device") -> str:
    """Safely get device name with validation."""
    try:
        name = device_data.get("name", default)
        if not name or not isinstance(name, str):
            return default
        validator = ConfigValidator()
        return validator.validate_device_name(name)
    except (ValidationError, KeyError, TypeError) as err:
        _LOGGER.warning("Invalid device name '%s', using default '%s': %s", name, default, err)
        return default


def safe_get_temperature(value: Any, default: float = 20.0, min_temp: float = -50, max_temp: float = 100) -> float:
    """Safely get temperature value with validation."""
    try:
        if value is None:
            return default
        validator = ConfigValidator()
        return validator.validate_temperature(value, min_temp, max_temp)
    except (ValidationError, TypeError, ValueError) as err:
        _LOGGER.warning("Invalid temperature value '%s', using default '%s': %s", value, default, err)
        return default


def safe_get_zone_number(value: Any, default: int = 0) -> int:
    """Safely get zone number with validation."""
    try:
        if value is None:
            return default
        validator = ConfigValidator()
        return validator.validate_zone_number(value)
    except (ValidationError, TypeError, ValueError) as err:
        _LOGGER.warning("Invalid zone number '%s', using default '%s': %s", value, default, err)
        return default


def safe_get_scan_interval(value: Any, default: int = 180) -> int:
    """Safely get scan interval with validation."""
    try:
        if value is None:
            return default
        validator = ConfigValidator()
        return validator.validate_scan_interval(value)
    except (ValidationError, TypeError, ValueError) as err:
        _LOGGER.warning("Invalid scan interval '%s', using default '%s': %s", value, default, err)
        return default

