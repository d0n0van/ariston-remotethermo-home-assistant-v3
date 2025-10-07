"""Climate entity descriptions for Ariston integration."""

from __future__ import annotations

from ariston.const import SystemType

from ..const import (
    ATTR_ECONOMY_TEMP,
    ATTR_HEAT_REQUEST,
    ATTR_ZONE,
    EXTRA_STATE_ATTRIBUTE,
    EXTRA_STATE_DEVICE_METHOD,
    NAME,
)


def create_climate_descriptions() -> list[Any]:
    """Create climate entity descriptions."""
    from ..const import AristonClimateEntityDescription
    
    return [
        AristonClimateEntityDescription(
            key="AristonClimate",
            extra_states=[
                {
                    EXTRA_STATE_ATTRIBUTE: ATTR_HEAT_REQUEST,
                    EXTRA_STATE_DEVICE_METHOD: lambda entity: entity.device.get_zone_heat_request_value(
                        entity.zone
                    ),
                },
                {
                    EXTRA_STATE_ATTRIBUTE: ATTR_ECONOMY_TEMP,
                    EXTRA_STATE_DEVICE_METHOD: lambda entity: entity.device.get_zone_economy_temp_value(
                        entity.zone
                    ),
                },
                {
                    EXTRA_STATE_ATTRIBUTE: ATTR_ZONE,
                    EXTRA_STATE_DEVICE_METHOD: lambda entity: entity.zone,
                },
            ],
            system_types=[SystemType.GALEVO],
        ),
        AristonClimateEntityDescription(
            key="AristonClimate",
            system_types=[SystemType.BSB],
        ),
    ]


# Create the climate types list
ARISTON_CLIMATE_TYPES = create_climate_descriptions()

