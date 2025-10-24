"""Sensor entity descriptions for Ariston integration."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ariston.const import (
    ConsumptionProperties,
    ConsumptionType,
    CustomDeviceFeatures,
    DeviceFeatures,
    DeviceProperties,
    EvoDeviceProperties,
    EvoLydosDeviceProperties,
    MenuItemNames,
    MedDeviceSettings,
    NuosSplitProperties,
    SeDeviceSettings,
    SlpDeviceSettings,
    SystemType,
    VelisDeviceProperties,
    WheType,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import EntityCategory

from ..const import (
    ARISTON_BUS_ERRORS,
    ATTR_ERRORS,
    BUS_ERRORS_COORDINATOR,
    ENERGY_COORDINATOR,
    EXTRA_STATE_ATTRIBUTE,
    EXTRA_STATE_DEVICE_METHOD,
    NAME,
)


def create_sensor_descriptions() -> list[Any]:
    """Create sensor entity descriptions."""
    from ..const import AristonSensorEntityDescription
    
    return [
        AristonSensorEntityDescription(
            key=DeviceProperties.HEATING_CIRCUIT_PRESSURE,
            name=f"{NAME} heating circuit pressure",
            device_class=SensorDeviceClass.PRESSURE,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
            get_native_value=lambda entity: entity.device.heating_circuit_pressure_value,
            get_native_unit_of_measurement=lambda entity: entity.device.heating_circuit_pressure_unit,
            system_types=[SystemType.GALEVO],
        ),
        AristonSensorEntityDescription(
            key=DeviceProperties.CH_FLOW_SETPOINT_TEMP,
            name=f"{NAME} CH flow setpoint temp",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            get_native_value=lambda entity: entity.device.ch_flow_setpoint_temp_value,
            get_native_unit_of_measurement=lambda entity: entity.device.ch_flow_setpoint_temp_unit,
            system_types=[SystemType.GALEVO],
        ),
        AristonSensorEntityDescription(
            key=DeviceProperties.CH_FLOW_TEMP,
            name=f"{NAME} CH flow temp",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            get_native_value=lambda entity: entity.device.ch_flow_temp_value,
            get_native_unit_of_measurement=lambda entity: entity.device.ch_flow_temp_unit,
            device_features=[DeviceProperties.CH_FLOW_TEMP],
            system_types=[SystemType.GALEVO],
        ),
        AristonSensorEntityDescription(
            key=str(MenuItemNames.SIGNAL_STRENGTH),
            name=f"{NAME} signal strength",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            get_native_value=lambda entity: entity.device.signal_strength_value,
            get_native_unit_of_measurement=lambda entity: entity.device.signal_strength_unit,
            system_types=[SystemType.GALEVO],
        ),
        AristonSensorEntityDescription(
            key=str(MenuItemNames.CH_RETURN_TEMP),
            name=f"{NAME} CH return temp",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            get_native_value=lambda entity: entity.device.ch_return_temp_value,
            get_native_unit_of_measurement=lambda entity: entity.device.ch_return_temp_unit,
            system_types=[SystemType.GALEVO],
        ),
        AristonSensorEntityDescription(
            key=DeviceProperties.OUTSIDE_TEMP,
            name=f"{NAME} Outside temp",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            device_features=[CustomDeviceFeatures.HAS_OUTSIDE_TEMP],
            get_native_value=lambda entity: entity.device.outside_temp_value,
            get_native_unit_of_measurement=lambda entity: entity.device.outside_temp_unit,
            system_types=[SystemType.GALEVO, SystemType.BSB],
        ),
        AristonSensorEntityDescription(
            key=EvoLydosDeviceProperties.AV_SHW,
            name=f"{NAME} average showers",
            icon="mdi:shower-head",
            state_class=SensorStateClass.MEASUREMENT,
            get_native_value=lambda entity: entity.device.av_shw_value,
            native_unit_of_measurement="",
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
        # Energy consumption sensors
        AristonSensorEntityDescription(
            key="Gas consumption for heating last month",
            name=f"{NAME} gas consumption for heating last month",
            icon="mdi:cash",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_features=[DeviceFeatures.HAS_METERING],
            coordinator=ENERGY_COORDINATOR,
            get_native_value=lambda entity: entity.device.gas_consumption_for_heating_last_month,
            system_types=[SystemType.GALEVO],
        ),
        AristonSensorEntityDescription(
            key="Electricity consumption for heating last month",
            name=f"{NAME} electricity consumption for heating last month",
            icon="mdi:cash",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_features=[DeviceFeatures.HAS_METERING],
            coordinator=ENERGY_COORDINATOR,
            get_native_value=lambda entity: entity.device.electricity_consumption_for_heating_last_month,
            system_types=[SystemType.GALEVO],
        ),
        # Bus errors sensor
        AristonSensorEntityDescription(
            key=ARISTON_BUS_ERRORS,
            name=f"{NAME} errors count",
            icon="mdi:alert-outline",
            coordinator=BUS_ERRORS_COORDINATOR,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            get_native_value=lambda entity: len(entity.device.bus_errors),
            native_unit_of_measurement="",
            extra_states=[
                {
                    EXTRA_STATE_ATTRIBUTE: ATTR_ERRORS,
                    EXTRA_STATE_DEVICE_METHOD: lambda entity: entity.device.bus_errors,
                },
            ],
        ),
    ]


# Create the sensor types list
ARISTON_SENSOR_TYPES = create_sensor_descriptions()













