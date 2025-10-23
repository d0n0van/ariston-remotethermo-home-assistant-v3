"""Support for Ariston boilers."""

from __future__ import annotations

import logging

from ariston.const import PlantMode, ZoneMode, BsbZoneMode
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from .const import ARISTON_CLIMATE_TYPES, DOMAIN, AristonClimateEntityDescription
from .coordinator import DeviceDataUpdateCoordinator
from .entity import AristonEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Ariston device from config entry."""
    ariston_climates: list[AristonThermostat] = []

    for description in ARISTON_CLIMATE_TYPES:
        coordinator: DeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.unique_id][
            description.coordinator
        ]
        if (
            coordinator
            and coordinator.device
            and coordinator.device.are_device_features_available(
                description.device_features,
                description.system_types,
                description.whe_types,
            )
        ):
            for zone_number in coordinator.device.zone_numbers:
                ariston_climates.append(
                    AristonThermostat(
                        zone_number,
                        coordinator,
                        description,
                    )
                )

    async_add_entities(ariston_climates)


class AristonThermostat(AristonEntity, ClimateEntity):
    """Ariston Thermostat Device."""

    def __init__(
        self,
        zone: int,
        coordinator: DeviceDataUpdateCoordinator,
        description: AristonClimateEntityDescription,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator, description, zone)

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self.device.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for the device."""
        return f"{self.device.gateway}_{self.zone}"

    @property
    def icon(self):
        """Return the icon of the thermostat device."""
        if self.device.is_plant_in_heat_mode:
            return "mdi:radiator"
        return "mdi:radiator-off"

    @property
    def temperature_unit(self) -> str:
        """Return the temperature units for the device."""
        return self.device.get_measured_temp_unit(self.zone)

    @property
    def precision(self) -> float:
        """Return the precision of temperature for the device."""
        return 1 / 10 ** self.device.get_measured_temp_decimals(self.zone)

    @property
    def min_temp(self):
        """Return minimum temperature."""
        return self.device.get_comfort_temp_min(self.zone)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.device.get_comfort_temp_max(self.zone)

    @property
    def target_temperature_step(self) -> float:
        """Return the target temperature step support by the device."""
        return self.device.get_target_temp_step(self.zone)

    @property
    def current_temperature(self) -> float:
        """Return the reported current temperature for the device."""
        return self.device.get_measured_temp_value(self.zone)

    @property
    def target_temperature(self) -> float:
        """Return the target temperature for the device."""
        return self.device.get_target_temp_value(self.zone)

    @property
    def supported_features(self) -> int:
        """Return the supported features for this device integration."""
        # Only support temperature setting - let thermostat control everything else
        features = ClimateEntityFeature.TARGET_TEMPERATURE
        return features

    @property
    def hvac_mode(self) -> str:
        """Return the current HVAC mode for the device."""
        # Simply read the current state - don't try to "fix" or change anything
        # The thermostat should control the HVAC mode, not Home Assistant
        curr_hvac_mode = HVACMode.OFF

        if self.device.is_plant_in_heat_mode:
            if self.device.is_zone_in_manual_mode(self.zone):
                curr_hvac_mode = HVACMode.HEAT
            elif self.device.is_zone_in_time_program_mode(self.zone):
                curr_hvac_mode = HVACMode.AUTO
        if self.device.is_plant_in_cool_mode:
            if self.device.is_zone_in_manual_mode(self.zone):
                curr_hvac_mode = HVACMode.COOL
            elif self.device.is_zone_in_time_program_mode(self.zone):
                curr_hvac_mode = HVACMode.AUTO
        
        # Debug logging for HVAC mode determination
        _LOGGER.debug(
            "HVAC mode for %s zone %s: %s (plant_heat: %s, plant_cool: %s, zone_manual: %s, zone_time_program: %s)",
            self.name, self.zone, curr_hvac_mode,
            self.device.is_plant_in_heat_mode,
            self.device.is_plant_in_cool_mode,
            self.device.is_zone_in_manual_mode(self.zone),
            self.device.is_zone_in_time_program_mode(self.zone)
        )
        
        return curr_hvac_mode

    # hvac_modes property removed - thermostat controls HVAC modes

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if_flame_on = bool(self.device.is_flame_on_value)

        curr_hvac_action = HVACAction.OFF
        if self.device.is_plant_in_heat_mode:
            if if_flame_on:
                curr_hvac_action = HVACAction.HEATING
            else:
                curr_hvac_action = HVACAction.IDLE
        if self.device.is_plant_in_cool_mode:
            if if_flame_on:
                curr_hvac_action = HVACAction.COOLING
            else:
                curr_hvac_action = HVACAction.IDLE
        return curr_hvac_action

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        return self.device.plant_mode_text

    # preset_modes property removed - thermostat controls preset modes

    # async_set_hvac_mode removed - let thermostat control HVAC mode changes

    # async_set_preset_mode removed - let thermostat control preset mode changes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise ValueError(f"Missing parameter {ATTR_TEMPERATURE}")

        temperature = kwargs[ATTR_TEMPERATURE]
        _LOGGER.debug(
            "Setting temperature to %s for %s",
            temperature,
            self.name,
        )

        # Only set temperature - let the thermostat handle HVAC mode
        # Don't force zone mode changes as the thermostat should control this
        await self.device.async_set_comfort_temp(temperature, self.zone)
        self.async_write_ha_state()
