"""Binary sensor entity descriptions for Ariston integration."""

from __future__ import annotations

from ariston.const import (
    DeviceFeatures,
    DeviceProperties,
    EvoLydosDeviceProperties,
    SystemType,
    WheType,
)
from homeassistant.helpers.entity import EntityCategory

from ..const import (
    ATTR_HOLIDAY,
    EXTRA_STATE_ATTRIBUTE,
    EXTRA_STATE_DEVICE_METHOD,
    NAME,
)


def create_binary_sensor_descriptions() -> list[Any]:
    """Create binary sensor entity descriptions."""
    from ..const import AristonBinarySensorEntityDescription
    
    return [
        AristonBinarySensorEntityDescription(
            key=DeviceProperties.IS_FLAME_ON,
            name=f"{NAME} is flame on",
            icon="mdi:fire",
            get_is_on=lambda entity: entity.device.is_flame_on_value,
            system_types=[SystemType.GALEVO, SystemType.BSB],
        ),
        AristonBinarySensorEntityDescription(
            key=DeviceProperties.IS_HEATING_PUMP_ON,
            name=f"{NAME} is heating pump on",
            icon="mdi:heat-pump-outline",
            get_is_on=lambda entity: entity.device.is_heating_pump_on_value,
            device_features=[DeviceFeatures.HYBRID_SYS],
            system_types=[SystemType.GALEVO],
        ),
        AristonBinarySensorEntityDescription(
            key=DeviceProperties.HOLIDAY,
            name=f"{NAME} holiday mode",
            icon="mdi:island",
            extra_states=[
                {
                    EXTRA_STATE_ATTRIBUTE: ATTR_HOLIDAY,
                    EXTRA_STATE_DEVICE_METHOD: lambda entity: entity.device.holiday_expires_on,
                }
            ],
            get_is_on=lambda entity: entity.device.holiday_mode_value,
            system_types=[SystemType.GALEVO],
        ),
        AristonBinarySensorEntityDescription(
            key=EvoLydosDeviceProperties.HEAT_REQ,
            name=f"{NAME} is heating",
            icon="mdi:fire",
            get_is_on=lambda entity: entity.device.is_heating,
            system_types=[SystemType.VELIS],
            whe_types=[
                WheType.Lux,
                WheType.Evo,
                WheType.Evo2,
                WheType.Lydos,
                WheType.LydosHybrid,
                WheType.Andris2,
                WheType.Lux2,
            ],
        ),
        AristonBinarySensorEntityDescription(
            key=EvoLydosDeviceProperties.ANTI_LEG,
            name=f"{NAME} anti-legionella cycle",
            icon="mdi:bacteria",
            get_is_on=lambda entity: entity.device.is_antileg,
            system_types=[SystemType.VELIS],
            whe_types=[
                WheType.Evo2,
                WheType.Lydos,
                WheType.LydosHybrid,
                WheType.Andris2,
            ],
        ),
    ]


# Create the binary sensor types list
ARISTON_BINARY_SENSOR_TYPES = create_binary_sensor_descriptions()













