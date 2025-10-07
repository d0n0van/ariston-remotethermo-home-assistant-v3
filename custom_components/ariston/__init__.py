"""The Ariston integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from ariston import Ariston, DeviceAttribute, SystemType
from ariston.const import ARISTON_API_URL, ARISTON_USER_AGENT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    API_URL_SETTING,
    API_USER_AGENT,
    BUS_ERRORS_COORDINATOR,
    BUS_ERRORS_SCAN_INTERVAL,
    COORDINATOR,
    DEFAULT_BUS_ERRORS_SCAN_INTERVAL_SECONDS,
    DEFAULT_ENERGY_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    ENERGY_COORDINATOR,
    ENERGY_SCAN_INTERVAL,
)
from .coordinator import DeviceDataUpdateCoordinator
from .optimized_coordinator import SmartCoordinatorManager
from .api_manager import CallType
from .validation import validate_config_entry, ValidationError
from .logging_config import get_ariston_logger

_LOGGER = get_ariston_logger(__name__)

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

# Additional platforms for enhanced functionality
ADDITIONAL_PLATFORMS: list[str] = [
    "temperature_sensors",  # Custom temperature sensors platform
]

SERVICE_SET_ITEM_BY_ID = "set_item_by_id"
SERVICE_GET_API_STATS = "get_api_stats"
SERVICE_FORCE_REFRESH = "force_refresh"
ATTR_ITEM_ID = "item_id"
ATTR_ZONE = "zone"
ATTR_VALUE = "value"

SET_ITEM_BY_ID_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_ITEM_ID): cv.string,
        vol.Required(ATTR_ZONE): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Coerce(float),
    }
)

GET_API_STATS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)

FORCE_REFRESH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ariston from a config entry."""
    _LOGGER.info("Setting up Ariston integration for device: %s", entry.title)
    
    try:
        # Validate configuration data
        validated_config = await _validate_and_prepare_config(entry)
        
        # Establish connection to Ariston API
        ariston = await _establish_connection(validated_config)
        
        # Initialize device
        device = await _initialize_device(hass, ariston, validated_config)
        
        # Set up coordinators
        await _setup_coordinators(hass, entry, device)
        
        # Set up platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Set up additional platforms
        await _setup_additional_platforms(hass, entry)
        
        # Set up update listener
        entry.async_on_unload(entry.add_update_listener(update_listener))
        
        # Set up services
        await _setup_services(hass)
            
        _LOGGER.info("Successfully set up Ariston integration for device: %s", device.name)
        return True
        
    except ConfigEntryAuthFailed:
        raise
    except Exception as error:
        _LOGGER.exception("Failed to set up Ariston integration: %s", error)
        raise ConfigEntryNotReady from error


async def _validate_and_prepare_config(entry: ConfigEntry) -> dict[str, Any]:
    """Validate configuration and prepare for setup."""
    try:
        validated_config = validate_config_entry(entry.data)
        _LOGGER.debug("Configuration validation successful")
    except ValidationError as err:
        _LOGGER.error("Configuration validation failed: %s", err)
        raise ConfigEntryNotReady(f"Configuration validation failed: {err}") from err
    
    if not entry.data.get(CONF_DEVICE):
        _LOGGER.error("Missing device configuration")
        raise ConfigEntryNotReady("Missing device configuration")
    
    return validated_config


async def _establish_connection(config: dict[str, Any]) -> Ariston:
    """Establish connection to Ariston API with retry logic."""
    ariston = Ariston()
    api_url_setting = config.get(API_URL_SETTING, ARISTON_API_URL)
    api_user_agent = config.get(API_USER_AGENT, ARISTON_USER_AGENT)
    
    _LOGGER.debug("Connecting to Ariston API at: %s", api_url_setting)
    
    # Attempt connection with retry logic
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = await ariston.async_connect(
                config[CONF_USERNAME],
                config[CONF_PASSWORD],
                api_url_setting,
                api_user_agent,
            )
            if response:
                _LOGGER.debug("Successfully connected to Ariston API")
                return ariston
            else:
                _LOGGER.warning("Connection attempt %d failed, retrying...", attempt + 1)
        except Exception as err:
            _LOGGER.warning("Connection attempt %d failed with error: %s", attempt + 1, err)
            if attempt == max_attempts - 1:  # Last attempt
                raise
    
    device_name = config[CONF_DEVICE].get(DeviceAttribute.NAME, "Unknown")
    _LOGGER.error(
        "Failed to connect to Ariston API after %d attempts for device: %s",
        max_attempts,
        device_name,
    )
    raise ConfigEntryAuthFailed("Failed to connect to Ariston API")


async def _initialize_device(hass: HomeAssistant, ariston: Ariston, config: dict[str, Any]) -> Any:
    """Initialize the Ariston device."""
    device_gw = config[CONF_DEVICE].get(DeviceAttribute.GW)
    if not device_gw:
        _LOGGER.error("Missing device gateway information")
        raise ConfigEntryNotReady("Missing device gateway information")
    
    _LOGGER.debug("Initializing device with gateway: %s", device_gw)
    
    device = await ariston.async_hello(
        device_gw,
        hass.config.units is METRIC_SYSTEM,
    )
    
    if device is None:
        _LOGGER.error("Failed to initialize device with gateway: %s", device_gw)
        raise ConfigEntryNotReady("Failed to initialize device")

    _LOGGER.info("Successfully initialized device: %s", device.name)
    
    # Get device features (non-critical, continue if fails)
    try:
        await device.async_get_features()
        _LOGGER.debug("Retrieved device features for: %s", device.name)
    except Exception as err:
        _LOGGER.warning("Failed to get device features: %s", err)
        # Continue setup even if features fail - device might still work
    
    return device


async def _setup_coordinators(hass: HomeAssistant, entry: ConfigEntry, device: Any) -> None:
    """Set up all coordinators for the device with optimized API call management."""
    # Initialize data structure
    hass.data.setdefault(DOMAIN, {}).setdefault(
        entry.unique_id, {COORDINATOR: {}, ENERGY_COORDINATOR: {}, "smart_manager": None}
    )
    
    # Create smart coordinator manager
    smart_manager = SmartCoordinatorManager(hass, device)
    hass.data[DOMAIN][entry.unique_id]["smart_manager"] = smart_manager
    
    # Get scan intervals
    scan_interval_seconds = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
    )
    bus_errors_scan_interval_seconds = entry.options.get(
        BUS_ERRORS_SCAN_INTERVAL, DEFAULT_BUS_ERRORS_SCAN_INTERVAL_SECONDS
    )
    energy_interval_minutes = entry.options.get(
        ENERGY_SCAN_INTERVAL, DEFAULT_ENERGY_SCAN_INTERVAL_MINUTES
    )
    
    # Create optimized coordinators with intelligent batching
    main_coordinator = smart_manager.add_coordinator(
        COORDINATOR,
        scan_interval_seconds,
        [CallType.STATE_UPDATE, CallType.FEATURES]  # Batch state and features
    )
    hass.data[DOMAIN][entry.unique_id][COORDINATOR] = main_coordinator
    
    # Bus errors coordinator (less frequent, separate)
    bus_errors_coordinator = smart_manager.add_coordinator(
        BUS_ERRORS_COORDINATOR,
        bus_errors_scan_interval_seconds,
        [CallType.BUS_ERRORS]
    )
    hass.data[DOMAIN][entry.unique_id][BUS_ERRORS_COORDINATOR] = bus_errors_coordinator
    
    # Energy coordinator (if device supports metering)
    if device.has_metering:
        energy_coordinator = smart_manager.add_coordinator(
            ENERGY_COORDINATOR,
            energy_interval_minutes * 60,
            [CallType.ENERGY_DATA]
        )
        hass.data[DOMAIN][entry.unique_id][ENERGY_COORDINATOR] = energy_coordinator
    
    # Start the smart coordinator manager
    await smart_manager.start()
    
    # Perform initial refresh
    await main_coordinator.async_update()
    await bus_errors_coordinator.async_update()
    if device.has_metering:
        await energy_coordinator.async_update()
    
    _LOGGER.info(
        "Set up optimized coordinators for %s with intelligent API call management",
        device.name
    )


async def _setup_additional_platforms(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up additional platforms for enhanced functionality."""
    try:
        # Import and set up temperature sensors
        from .temperature_sensors import async_setup_entry as setup_temperature_sensors
        
        # Set up temperature sensors
        await setup_temperature_sensors(hass, entry, lambda entities: None)
        _LOGGER.info("Set up temperature sensors platform")
            
    except Exception as err:
        _LOGGER.warning("Failed to set up additional platforms: %s", err)


async def _setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Ariston integration."""
    
    async def async_set_item_by_id_service(service_call):
        """Set item by ID on the target device."""
        try:
            device_id = service_call.data.get(ATTR_DEVICE_ID)
            item_id = service_call.data.get(ATTR_ITEM_ID)
            zone = service_call.data.get(ATTR_ZONE)
            value = service_call.data.get(ATTR_VALUE)

            device_registry = dr.async_get(hass)
            device = device_registry.devices[device_id]

            entry = hass.config_entries.async_get_entry(
                next(iter(device.config_entries))
            )
            coordinator: DeviceDataUpdateCoordinator = hass.data[DOMAIN][
                entry.unique_id
            ][COORDINATOR]
            await coordinator.device.async_set_item_by_id(item_id, value, zone)
            _LOGGER.info("Successfully set item %s to %s for zone %s", item_id, value, zone)
        except Exception as err:
            _LOGGER.error("Failed to set item by ID: %s", err)
            raise

    async def async_get_api_stats_service(service_call):
        """Get API call statistics for monitoring."""
        try:
            device_id = service_call.data.get(ATTR_DEVICE_ID)
            device_registry = dr.async_get(hass)
            device = device_registry.devices[device_id]
            entry = hass.config_entries.async_get_entry(
                next(iter(device.config_entries))
            )
            
            smart_manager = hass.data[DOMAIN][entry.unique_id].get("smart_manager")
            if smart_manager:
                stats = smart_manager.get_api_stats()
                _LOGGER.info("API Stats for %s: %s", device.name, stats)
                # You could also send this to a sensor or log it
            else:
                _LOGGER.warning("Smart manager not available for device %s", device.name)
        except Exception as err:
            _LOGGER.error("Failed to get API stats: %s", err)

    async def async_force_refresh_service(service_call):
        """Force refresh all cached data."""
        try:
            device_id = service_call.data.get(ATTR_DEVICE_ID)
            device_registry = dr.async_get(hass)
            device = device_registry.devices[device_id]
            entry = hass.config_entries.async_get_entry(
                next(iter(device.config_entries))
            )
            
            smart_manager = hass.data[DOMAIN][entry.unique_id].get("smart_manager")
            if smart_manager:
                smart_manager.force_refresh_all()
                _LOGGER.info("Forced refresh for device %s", device.name)
            else:
                _LOGGER.warning("Smart manager not available for device %s", device.name)
        except Exception as err:
            _LOGGER.error("Failed to force refresh: %s", err)

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ITEM_BY_ID,
        async_set_item_by_id_service,
        schema=SET_ITEM_BY_ID_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_API_STATS,
        async_get_api_stats_service,
        schema=GET_API_STATS_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_REFRESH,
        async_force_refresh_service,
        schema=FORCE_REFRESH_SCHEMA,
    )


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Stop the smart coordinator manager
        if entry.unique_id in hass.data[DOMAIN]:
            smart_manager = hass.data[DOMAIN][entry.unique_id].get("smart_manager")
            if smart_manager:
                await smart_manager.stop()
                _LOGGER.info("Stopped smart coordinator manager for %s", entry.title)
        
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok
