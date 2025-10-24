"""Water heater entity descriptions for Ariston integration."""

from __future__ import annotations

from ariston.const import CustomDeviceFeatures, SystemType, WheType

from ..const import (
    ATTR_TARGET_TEMP_STEP,
    EXTRA_STATE_ATTRIBUTE,
    EXTRA_STATE_DEVICE_METHOD,
    NAME,
)


def create_water_heater_descriptions() -> list[Any]:
    """Create water heater entity descriptions."""
    from ..const import AristonWaterHeaterEntityDescription
    
    return [
        AristonWaterHeaterEntityDescription(
            key="AristonWaterHeater",
            extra_states=[
                {
                    EXTRA_STATE_ATTRIBUTE: ATTR_TARGET_TEMP_STEP,
                    EXTRA_STATE_DEVICE_METHOD: lambda entity: entity.device.water_heater_temperature_step,
                }
            ],
            device_features=[CustomDeviceFeatures.HAS_DHW],
            system_types=[SystemType.GALEVO, SystemType.BSB],
        ),
        AristonWaterHeaterEntityDescription(
            key="AristonWaterHeater",
            extra_states=[
                {
                    EXTRA_STATE_ATTRIBUTE: ATTR_TARGET_TEMP_STEP,
                    EXTRA_STATE_DEVICE_METHOD: lambda entity: entity.device.water_heater_temperature_step,
                }
            ],
            device_features=[CustomDeviceFeatures.HAS_DHW],
            system_types=[SystemType.VELIS],
            whe_types=[
                WheType.Andris2,
                WheType.Evo2,
                WheType.Lux,
                WheType.Lux2,
                WheType.Lydos,
                WheType.LydosHybrid,
                WheType.NuosSplit,
            ],
        ),
    ]


# Create the water heater types list
ARISTON_WATER_HEATER_TYPES = create_water_heater_descriptions()













