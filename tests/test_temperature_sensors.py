"""Test temperature sensors functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from custom_components.ariston.temperature_sensors import TemperatureSensor, async_setup_entry
from custom_components.ariston.const import DOMAIN
from custom_components.ariston.coordinator import DeviceDataUpdateCoordinator


class TestTemperatureSensor:
    """Test TemperatureSensor class."""

    def test_temperature_sensor_init(self):
        """Test temperature sensor initialization."""
        # Mock coordinator and device
        coordinator = MagicMock(spec=DeviceDataUpdateCoordinator)
        coordinator.device = MagicMock()
        coordinator.device.name = "Test Device"
        coordinator.device.gateway = "test_gateway"
        
        # Create temperature sensor
        sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="test_temperature",
            sensor_name="Test Temperature",
            get_value_func=lambda entity: 25.5,
            get_unit_func=lambda entity: "°C",
        )
        
        assert sensor.name == "Test Temperature"
        assert sensor.unique_id == "test_gateway-Test Temperature"
        assert sensor.native_value == 25.5
        assert sensor.native_unit_of_measurement == "°C"

    def test_temperature_sensor_value_error_handling(self):
        """Test temperature sensor handles value errors gracefully."""
        # Mock coordinator and device
        coordinator = MagicMock(spec=DeviceDataUpdateCoordinator)
        coordinator.device = MagicMock()
        coordinator.device.name = "Test Device"
        coordinator.device.gateway = "test_gateway"
        
        # Create temperature sensor with failing value function
        def failing_value_func(entity):
            raise Exception("Value error")
        
        sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="test_temperature",
            sensor_name="Test Temperature",
            get_value_func=failing_value_func,
            get_unit_func=lambda entity: "°C",
        )
        
        # Should return None when value function fails
        assert sensor.native_value is None

    def test_temperature_sensor_unit_error_handling(self):
        """Test temperature sensor handles unit errors gracefully."""
        # Mock coordinator and device
        coordinator = MagicMock(spec=DeviceDataUpdateCoordinator)
        coordinator.device = MagicMock()
        coordinator.device.name = "Test Device"
        coordinator.device.gateway = "test_gateway"
        
        # Create temperature sensor with failing unit function
        def failing_unit_func(entity):
            raise Exception("Unit error")
        
        sensor = TemperatureSensor(
            coordinator=coordinator,
            sensor_key="test_temperature",
            sensor_name="Test Temperature",
            get_value_func=lambda entity: 25.5,
            get_unit_func=failing_unit_func,
        )
        
        # Should return default unit when unit function fails
        assert sensor.native_unit_of_measurement == "°C"


@pytest.mark.asyncio
class TestTemperatureSensorsSetup:
    """Test temperature sensors setup."""

    async def test_async_setup_entry_no_device(self):
        """Test setup when no device is available."""
        # Mock Home Assistant and config entry
        hass = MagicMock()
        entry = MagicMock()
        entry.unique_id = "test_entry"
        
        # Mock data structure with no device
        hass.data = {
            DOMAIN: {
                "test_entry": {
                    "coordinator": None
                }
            }
        }
        
        # Mock async_add_entities
        async_add_entities = MagicMock()
        
        # Should not raise exception and should not add entities
        await async_setup_entry(hass, entry, async_add_entities)
        async_add_entities.assert_not_called()

    async def test_async_setup_entry_with_device(self):
        """Test setup with a valid device."""
        # Mock Home Assistant and config entry
        hass = MagicMock()
        entry = MagicMock()
        entry.unique_id = "test_entry"
        
        # Mock device
        device = MagicMock()
        device.name = "Test Device"
        device.gateway = "test_gateway"
        device.system_type = "GALEVO"
        device.zone_numbers = [1, 2]
        
        # Mock device methods
        device.get_measured_temp_value = MagicMock(return_value=22.5)
        device.get_measured_temp_unit = MagicMock(return_value="°C")
        device.get_target_temp_value = MagicMock(return_value=23.0)
        device.get_comfort_temp_value = MagicMock(return_value=24.0)
        device.get_economy_temp_value = MagicMock(return_value=20.0)
        
        # Mock coordinator
        coordinator = MagicMock(spec=DeviceDataUpdateCoordinator)
        coordinator.device = device
        
        # Mock data structure
        hass.data = {
            DOMAIN: {
                "test_entry": {
                    "coordinator": coordinator
                }
            }
        }
        
        # Mock async_add_entities
        async_add_entities = MagicMock()
        
        # Set up temperature sensors
        await async_setup_entry(hass, entry, async_add_entities)
        
        # Should have added entities (zone sensors for GALEVO system)
        async_add_entities.assert_called_once()
        added_entities = async_add_entities.call_args[0][0]
        assert len(added_entities) > 0  # Should have created zone temperature sensors

    async def test_async_setup_entry_velis_system(self):
        """Test setup with VELIS system (water heater)."""
        # Mock Home Assistant and config entry
        hass = MagicMock()
        entry = MagicMock()
        entry.unique_id = "test_entry"
        
        # Mock VELIS device
        device = MagicMock()
        device.name = "Test Water Heater"
        device.gateway = "test_gateway"
        device.system_type = "VELIS"
        device.zone_numbers = []
        
        # Mock water heater properties
        device.water_heater_current_temperature = 45.0
        device.water_heater_target_temperature = 50.0
        device.water_heater_minimum_temperature = 30.0
        device.water_heater_maximum_temperature = 80.0
        device.water_heater_temperature_unit = "°C"
        
        # Mock coordinator
        coordinator = MagicMock(spec=DeviceDataUpdateCoordinator)
        coordinator.device = device
        
        # Mock data structure
        hass.data = {
            DOMAIN: {
                "test_entry": {
                    "coordinator": coordinator
                }
            }
        }
        
        # Mock async_add_entities
        async_add_entities = MagicMock()
        
        # Set up temperature sensors
        await async_setup_entry(hass, entry, async_add_entities)
        
        # Should have added entities (water heater sensors for VELIS system)
        async_add_entities.assert_called_once()
        added_entities = async_add_entities.call_args[0][0]
        assert len(added_entities) > 0  # Should have created water heater temperature sensors
