"""Coordinator class for Ariston module."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from ariston.base_device import AristonBaseDevice
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .logging_config import get_ariston_logger

_LOGGER = get_ariston_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
BACKOFF_MULTIPLIER = 2
MAX_CONSECUTIVE_FAILURES = 5


class DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: AristonBaseDevice,
        scan_interval_seconds: int,
        coordinator_name: str,
        async_update_state: Callable,
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.name}-{coordinator_name}",
            update_interval=timedelta(seconds=scan_interval_seconds),
            update_method=self._async_update_with_retry,
        )

        self.device = device
        self._async_update_state = async_update_state
        self._consecutive_failures = 0
        self._last_successful_update: datetime | None = None
        self._last_update_attempt: datetime | None = None
        self._is_updating = False

    async def _async_update_with_retry(self) -> dict[str, Any]:
        """Update device data with retry logic and exponential backoff."""
        # Prevent concurrent updates
        if self._is_updating:
            _LOGGER.debug("Update already in progress for %s, skipping", self.device.name)
            return {"status": "skipped", "device": self.device.name}
        
        self._is_updating = True
        self._last_update_attempt = datetime.now()
        last_exception = None
        
        try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    _LOGGER.debug(
                        "Updating %s data (attempt %d/%d)",
                        self.device.name,
                        attempt + 1,
                        MAX_RETRIES + 1,
                    )
                    
                    await self._async_update_state()
                    
                    # Reset failure counter on success
                    self._consecutive_failures = 0
                    self._last_successful_update = datetime.now()
                    
                    _LOGGER.debug(
                        "Successfully updated %s data",
                        self.device.name,
                    )
                    
                    return {"status": "success", "device": self.device.name}
                    
                except Exception as err:
                    last_exception = err
                    self._consecutive_failures += 1
                    
                    error_msg = f"Failed to update {self.device.name} data: {err}"
                    
                    if attempt < MAX_RETRIES:
                        delay = RETRY_DELAY * (BACKOFF_MULTIPLIER ** attempt)
                        _LOGGER.warning(
                            "%s (attempt %d/%d, retrying in %ds)",
                            error_msg,
                            attempt + 1,
                            MAX_RETRIES + 1,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        _LOGGER.error(
                            "%s (all %d attempts failed)",
                            error_msg,
                            MAX_RETRIES + 1,
                        )
            
            # If we get here, all retries failed
            raise UpdateFailed(f"Failed to update {self.device.name} after {MAX_RETRIES + 1} attempts") from last_exception
            
        finally:
            self._is_updating = False

    @property
    def is_available(self) -> bool:
        """Return if the device is available based on recent update success."""
        if self._last_successful_update is None:
            return False
        
        # Consider device unavailable if no successful update in the last 2 intervals
        time_since_success = (datetime.now() - self._last_successful_update).total_seconds()
        max_interval = self.update_interval.total_seconds() * 2
        
        # Also consider device unavailable if too many consecutive failures
        if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            _LOGGER.warning(
                "Device %s marked as unavailable due to %d consecutive failures",
                self.device.name,
                self._consecutive_failures,
            )
            return False
        
        return time_since_success < max_interval

    @property
    def consecutive_failures(self) -> int:
        """Return the number of consecutive update failures."""
        return self._consecutive_failures

    @property
    def last_successful_update(self) -> datetime | None:
        """Return the timestamp of the last successful update."""
        return self._last_successful_update

    @property
    def last_update_attempt(self) -> datetime | None:
        """Return the timestamp of the last update attempt."""
        return self._last_update_attempt

    @property
    def is_updating(self) -> bool:
        """Return whether an update is currently in progress."""
        return self._is_updating

    async def force_update(self) -> bool:
        """Force an immediate update, bypassing the normal schedule."""
        if self._is_updating:
            _LOGGER.debug("Update already in progress for %s, cannot force update", self.device.name)
            return False
        
        try:
            _LOGGER.info("Forcing update for %s", self.device.name)
            await self._async_update_with_retry()
            return True
        except Exception as err:
            _LOGGER.error("Failed to force update for %s: %s", self.device.name, err)
            return False
