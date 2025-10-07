"""Entity object for shared properties of Ariston entities."""

from __future__ import annotations

from abc import ABC
import logging
from typing import Any

from ariston.const import WheType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    EXTRA_STATE_ATTRIBUTE,
    EXTRA_STATE_DEVICE_METHOD,
    AristonBaseEntityDescription,
)
from .coordinator import DeviceDataUpdateCoordinator
from .logging_config import get_ariston_logger

_LOGGER = get_ariston_logger(__name__)


class AristonEntity(CoordinatorEntity, ABC):
    """Generic Ariston entity (base class)."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        description: AristonBaseEntityDescription,
        zone: int = 0,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.device = coordinator.device
        self.entity_description: AristonBaseEntityDescription = description
        self.zone = zone

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        try:
            return DeviceInfo(
                identifiers={(DOMAIN, self.device.serial_number or "unknown")},
                manufacturer=DOMAIN,
                name=self.device.name or "Unknown Device",
                sw_version=self.device.firmware_version or "Unknown",
                model=self.model,
            )
        except Exception as err:
            _LOGGER.warning("Failed to get device info: %s", err)
            return DeviceInfo(
                identifiers={(DOMAIN, "unknown")},
                manufacturer=DOMAIN,
                name="Unknown Device",
                model="Unknown",
            )

    @property
    def model(self) -> str:
        """Return the model of the entity."""
        try:
            if self.device.whe_model_type == 0:
                if self.device.whe_type is WheType.Unknown:
                    return f"{self.device.system_type.name}"
                return f"{self.device.system_type.name} {self.device.whe_type.name}"
            return f"{self.device.system_type.name} {self.device.whe_type.name} | Model {self.device.whe_model_type}"
        except Exception as err:
            _LOGGER.warning("Failed to get device model: %s", err)
            return "Unknown Model"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.extra_states is None:
            return None

        state_attributes: dict[str, Any] = {}

        try:
            for extra_state in self.entity_description.extra_states:
                device_method = extra_state.get(EXTRA_STATE_DEVICE_METHOD)
                if device_method is None:
                    continue

                try:
                    state_attribute = device_method(self)
                    if state_attribute is not None:
                        attribute_key = extra_state.get(EXTRA_STATE_ATTRIBUTE)
                        if attribute_key:
                            state_attributes[attribute_key] = state_attribute
                except Exception as err:
                    _LOGGER.warning(
                        "Failed to get extra state attribute %s: %s",
                        extra_state.get(EXTRA_STATE_ATTRIBUTE, "unknown"),
                        err,
                    )
                    continue

        except Exception as err:
            _LOGGER.warning("Failed to process extra state attributes: %s", err)

        return state_attributes if state_attributes else None

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        try:
            gateway = getattr(self.device, 'gateway', 'unknown')
            name = getattr(self, 'name', 'unknown')
            if self.zone:
                return f"{gateway}-{name}-{self.zone}"
            return f"{gateway}-{name}"
        except Exception as err:
            _LOGGER.warning("Failed to generate unique ID: %s", err)
            return f"unknown-{id(self)}"

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.is_available
            and self.coordinator.last_update_success
        )
