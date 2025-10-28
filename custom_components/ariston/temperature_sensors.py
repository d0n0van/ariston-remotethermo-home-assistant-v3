"""Enhanced temperature sensors for Ariston integration."""

from __future__ import annotations

import logging
from typing import Any

from ariston.const import SystemType, WheType
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import DeviceDataUpdateCoordinator
from .entity import AristonEntity
from .logging_config import get_ariston_logger

_LOGGER = get_ariston_logger(__name__)


class TemperatureSensor(AristonEntity, SensorEntity):
    """Base class for temperature sensors."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        sensor_key: str,
        sensor_name: str,
        get_value_func: Any,
        get_unit_func: Any = None,
        zone: int = 0,
    ) -> None:
        """Initialize the temperature sensor."""
        from .const import AristonSensorEntityDescription
        
        description = AristonSensorEntityDescription(
            key=sensor_key,
            name=sensor_name,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            get_native_value=get_value_func,
            get_native_unit_of_measurement=get_unit_func,
        )
        
        super().__init__(coordinator, description, zone)
        self._get_value_func = get_value_func
        self._get_unit_func = get_unit_func
        self._last_value = None
        self._value_change_count = 0

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        try:
            value = self._get_value_func(self)
            if value is None:
                _LOGGER.debug("Temperature value is None for %s", self.name)
                return None
            
            # Validate temperature range (-50°C to 100°C)
            if not isinstance(value, (int, float)):
                _LOGGER.warning("Invalid temperature value type for %s: %s (type: %s)", 
                             self.name, value, type(value))
                return None
                
            if value < -50 or value > 100:
                _LOGGER.warning("Temperature value out of range for %s: %s°C", self.name, value)
                return None
            
            # Track value changes for debugging
            float_value = float(value)
            if self._last_value is not None:
                if abs(float_value - self._last_value) > 0.1:  # Only log significant changes
                    self._value_change_count += 1
                    _LOGGER.debug("Temperature change for %s: %.1f°C -> %.1f°C (change #%d)", 
                                self.name, self._last_value, float_value, self._value_change_count)
                    
                    # Log warning if values are fluctuating too much, then reset counter
                    if self._value_change_count > 10:
                        _LOGGER.warning("High temperature fluctuation detected for %s: %d changes", 
                                      self.name, self._value_change_count)
                        self._value_change_count = 0  # Reset counter after warning
            
            self._last_value = float_value
            return float_value
        except Exception as err:
            _LOGGER.warning("Failed to get temperature value for %s: %s", self.name, err)
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self._get_unit_func:
            try:
                return self._get_unit_func(self)
            except Exception as err:
                _LOGGER.warning("Failed to get temperature unit for %s: %s", self.name, err)
        
        return UnitOfTemperature.CELSIUS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up temperature sensors from config entry."""
    temperature_sensors: list[TemperatureSensor] = []
    
    # Get the main coordinator
    coordinator: DeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.unique_id]["coordinator"]
    
    if not coordinator or not coordinator.device:
        _LOGGER.warning("No device available for temperature sensors")
        return
        
    device = coordinator.device

    # Add zone temperature sensors for GALEVO and BSB systems
    if device.system_type in [SystemType.GALEVO, SystemType.BSB]:
        for zone_number in device.zone_numbers:
            # Current temperature sensor for each zone
            current_temp_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key=f"zone_{zone_number}_current_temperature",
                sensor_name=f"{device.name} Zone {zone_number} Current Temperature",
                get_value_func=lambda entity, zone=zone_number: entity.device.get_measured_temp_value(zone),
                get_unit_func=lambda entity, zone=zone_number: entity.device.get_measured_temp_unit(zone),
                zone=zone_number,
            )
            temperature_sensors.append(current_temp_sensor)
            
            # Target temperature sensor for each zone
            target_temp_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key=f"zone_{zone_number}_target_temperature",
                sensor_name=f"{device.name} Zone {zone_number} Target Temperature",
                get_value_func=lambda entity, zone=zone_number: entity.device.get_target_temp_value(zone),
                get_unit_func=lambda entity, zone=zone_number: entity.device.get_measured_temp_unit(zone),
                zone=zone_number,
            )
            temperature_sensors.append(target_temp_sensor)
            
            # Comfort temperature sensor for each zone
            comfort_temp_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key=f"zone_{zone_number}_comfort_temperature",
                sensor_name=f"{device.name} Zone {zone_number} Comfort Temperature",
                get_value_func=lambda entity, zone=zone_number: entity.device.get_comfort_temp_value(zone),
                get_unit_func=lambda entity, zone=zone_number: entity.device.get_measured_temp_unit(zone),
                zone=zone_number,
            )
            temperature_sensors.append(comfort_temp_sensor)
            
            # Economy temperature sensor for each zone
            economy_temp_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key=f"zone_{zone_number}_economy_temperature",
                sensor_name=f"{device.name} Zone {zone_number} Economy Temperature",
                get_value_func=lambda entity, zone=zone_number: entity.device.get_economy_temp_value(zone),
                get_unit_func=lambda entity, zone=zone_number: entity.device.get_measured_temp_unit(zone),
                zone=zone_number,
            )
            temperature_sensors.append(economy_temp_sensor)

    # Add water heater temperature sensors for VELIS systems
    if device.system_type == SystemType.VELIS:
        # Current water heater temperature
        if hasattr(device, 'water_heater_current_temperature'):
            water_heater_current_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key="water_heater_current_temperature",
                sensor_name=f"{device.name} Water Heater Current Temperature",
                get_value_func=lambda entity: entity.device.water_heater_current_temperature,
                get_unit_func=lambda entity: getattr(entity.device, 'water_heater_temperature_unit', UnitOfTemperature.CELSIUS),
            )
            temperature_sensors.append(water_heater_current_sensor)
        
        # Target water heater temperature
        if hasattr(device, 'water_heater_target_temperature'):
            water_heater_target_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key="water_heater_target_temperature",
                sensor_name=f"{device.name} Water Heater Target Temperature",
                get_value_func=lambda entity: entity.device.water_heater_target_temperature,
                get_unit_func=lambda entity: getattr(entity.device, 'water_heater_temperature_unit', UnitOfTemperature.CELSIUS),
            )
            temperature_sensors.append(water_heater_target_sensor)
        
        # Minimum water heater temperature
        if hasattr(device, 'water_heater_minimum_temperature'):
            water_heater_min_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key="water_heater_minimum_temperature",
                sensor_name=f"{device.name} Water Heater Minimum Temperature",
                get_value_func=lambda entity: entity.device.water_heater_minimum_temperature,
                get_unit_func=lambda entity: getattr(entity.device, 'water_heater_temperature_unit', UnitOfTemperature.CELSIUS),
            )
            temperature_sensors.append(water_heater_min_sensor)
        
        # Maximum water heater temperature
        if hasattr(device, 'water_heater_maximum_temperature'):
            water_heater_max_sensor = TemperatureSensor(
                coordinator=coordinator,
                sensor_key="water_heater_maximum_temperature",
                sensor_name=f"{device.name} Water Heater Maximum Temperature",
                get_value_func=lambda entity: entity.device.water_heater_maximum_temperature,
                get_unit_func=lambda entity: getattr(entity.device, 'water_heater_temperature_unit', UnitOfTemperature.CELSIUS),
            )
            temperature_sensors.append(water_heater_max_sensor)

    # Add additional temperature sensors based on device features
    if hasattr(device, 'outside_temp_value') and device.outside_temp_value is not None:
        outside_temp_sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="outside_temperature",
            sensor_name=f"{device.name} Outside Temperature",
            get_value_func=lambda entity: entity.device.outside_temp_value,
            get_unit_func=lambda entity: entity.device.outside_temp_unit,
        )
        temperature_sensors.append(outside_temp_sensor)

    # Add CH flow temperature if available
    if hasattr(device, 'ch_flow_temp_value') and device.ch_flow_temp_value is not None:
        ch_flow_temp_sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="ch_flow_temperature",
            sensor_name=f"{device.name} CH Flow Temperature",
            get_value_func=lambda entity: entity.device.ch_flow_temp_value,
            get_unit_func=lambda entity: entity.device.ch_flow_temp_unit,
        )
        temperature_sensors.append(ch_flow_temp_sensor)

    # Add CH return temperature if available
    if hasattr(device, 'ch_return_temp_value') and device.ch_return_temp_value is not None:
        ch_return_temp_sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="ch_return_temperature",
            sensor_name=f"{device.name} CH Return Temperature",
            get_value_func=lambda entity: entity.device.ch_return_temp_value,
            get_unit_func=lambda entity: entity.device.ch_return_temp_unit,
        )
        temperature_sensors.append(ch_return_temp_sensor)

    # Add CH flow setpoint temperature if available
    if hasattr(device, 'ch_flow_setpoint_temp_value') and device.ch_flow_setpoint_temp_value is not None:
        ch_flow_setpoint_sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="ch_flow_setpoint_temperature",
            sensor_name=f"{device.name} CH Flow Setpoint Temperature",
            get_value_func=lambda entity: entity.device.ch_flow_setpoint_temp_value,
            get_unit_func=lambda entity: entity.device.ch_flow_setpoint_temp_unit,
        )
        temperature_sensors.append(ch_flow_setpoint_sensor)

    # Add proc req temperature for VELIS systems
    if (device.system_type == SystemType.VELIS and 
        hasattr(device, 'proc_req_temp_value') and 
        device.proc_req_temp_value is not None):
        proc_req_temp_sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="proc_req_temperature",
            sensor_name=f"{device.name} Process Request Temperature",
            get_value_func=lambda entity: entity.device.proc_req_temp_value,
            get_unit_func=lambda entity: UnitOfTemperature.CELSIUS,
        )
        temperature_sensors.append(proc_req_temp_sensor)

    _LOGGER.info("Created %d temperature sensors for device %s", len(temperature_sensors), device.name)
    
    if temperature_sensors:
        # Add entities to Home Assistant
        async_add_entities(temperature_sensors)
        _LOGGER.info("Successfully registered %d temperature sensors", len(temperature_sensors))
    else:
        _LOGGER.warning("No temperature sensors created for device %s", device.name)
