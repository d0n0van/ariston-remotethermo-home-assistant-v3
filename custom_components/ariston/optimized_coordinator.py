"""Optimized coordinator with intelligent batching and reduced API calls."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_manager import APICallManager, CallType, OptimizedDeviceDataUpdateCoordinator
from .const import DOMAIN
from .logging_config import get_ariston_logger

_LOGGER = get_ariston_logger(__name__)


class BatchedDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that batches multiple API calls to reduce network requests."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Any,
        scan_interval_seconds: int,
        coordinator_name: str,
        api_manager: APICallManager,
        call_types: List[CallType],
    ) -> None:
        """Initialize the batched coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.name}-{coordinator_name}",
            update_interval=timedelta(seconds=scan_interval_seconds),
            update_method=self._async_batched_update,
        )

        self.device = device
        self.api_manager = api_manager
        self.call_types = call_types
        self._consecutive_failures = 0
        self._last_successful_update: Optional[datetime] = None
        self._last_update_attempt: Optional[datetime] = None
        self._is_updating = False
        self._update_results: Dict[CallType, Any] = {}

    async def async_update(self) -> None:
        """Public method to trigger coordinator update."""
        await self._async_batched_update()

    async def _async_batched_update(self) -> Dict[str, Any]:
        """Perform batched update for multiple call types."""
        if self._is_updating:
            _LOGGER.debug("Batched update already in progress for %s, skipping", self.device.name)
            return {"status": "skipped", "device": self.device.name}
        
        self._is_updating = True
        self._last_update_attempt = datetime.now()
        
        try:
            # Execute all call types in parallel for maximum efficiency
            tasks = []
            for call_type in self.call_types:
                task = self._execute_single_call(call_type)
                tasks.append(task)
            
            # Wait for all calls to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            success_count = 0
            for i, result in enumerate(results):
                call_type = self.call_types[i]
                if isinstance(result, Exception):
                    _LOGGER.warning("Call %s failed: %s", call_type.value, result)
                else:
                    self._update_results[call_type] = result
                    success_count += 1
            
            if success_count > 0:
                self._consecutive_failures = 0
                self._last_successful_update = datetime.now()
                _LOGGER.debug(
                    "Batched update completed: %d/%d calls successful",
                    success_count,
                    len(self.call_types)
                )
            else:
                self._consecutive_failures += 1
                raise UpdateFailed("All batched calls failed")
            
            return {
                "status": "success",
                "device": self.device.name,
                "successful_calls": success_count,
                "total_calls": len(self.call_types),
                "results": self._update_results
            }
            
        except Exception as err:
            self._consecutive_failures += 1
            _LOGGER.error("Batched update failed for %s: %s", self.device.name, err)
            raise UpdateFailed(f"Batched update failed: {err}") from err
        finally:
            self._is_updating = False

    async def _execute_single_call(self, call_type: CallType) -> Any:
        """Execute a single API call with caching."""
        update_method = self._get_update_method(call_type)
        return await self.api_manager.call_with_retry(
            call_type,
            update_method,
            force_refresh=False
        )

    def _get_update_method(self, call_type: CallType) -> Callable:
        """Get the appropriate update method based on call type."""
        method_map = {
            CallType.STATE_UPDATE: self.device.async_update_state,
            CallType.BUS_ERRORS: self.device.async_get_bus_errors,
            CallType.ENERGY_DATA: self.device.async_update_energy,
            CallType.FEATURES: self.device.async_get_features,
        }
        return method_map.get(call_type, self.device.async_update_state)

    @property
    def is_available(self) -> bool:
        """Return if the device is available."""
        if self._last_successful_update is None:
            return False
        
        # Consider device unavailable if no successful update in the last 2 intervals
        time_since_success = (datetime.now() - self._last_successful_update).total_seconds()
        max_interval = self.update_interval.total_seconds() * 2
        
        return time_since_success < max_interval

    @property
    def consecutive_failures(self) -> int:
        """Return the number of consecutive update failures."""
        return self._consecutive_failures

    def get_result(self, call_type: CallType) -> Optional[Any]:
        """Get cached result for a specific call type."""
        return self._update_results.get(call_type)

    def force_refresh(self, call_type: Optional[CallType] = None) -> None:
        """Force refresh of specific call type or all types."""
        if call_type:
            # Clear cache for specific call type
            self.api_manager.clear_cache(call_type)
        else:
            # Clear all cache
            self.api_manager.clear_cache()


class SmartCoordinatorManager:
    """Manages multiple coordinators with intelligent scheduling."""

    def __init__(self, hass: HomeAssistant, device: Any) -> None:
        """Initialize the smart coordinator manager."""
        self.hass = hass
        self.device = device
        self.api_manager = APICallManager(hass, device)
        self.coordinators: Dict[str, BatchedDeviceDataUpdateCoordinator] = {}
        self._update_tasks: Dict[str, asyncio.Task] = {}
        self._is_running = False

    def add_coordinator(
        self,
        name: str,
        scan_interval_seconds: int,
        call_types: List[CallType],
    ) -> BatchedDeviceDataUpdateCoordinator:
        """Add a new coordinator."""
        coordinator = BatchedDeviceDataUpdateCoordinator(
            self.hass,
            self.device,
            scan_interval_seconds,
            name,
            self.api_manager,
            call_types,
        )
        self.coordinators[name] = coordinator
        return coordinator

    async def start(self) -> None:
        """Start all coordinators."""
        if self._is_running:
            return
        
        self._is_running = True
        _LOGGER.info("Starting smart coordinator manager for %s", self.device.name)
        
        # Start each coordinator
        for name, coordinator in self.coordinators.items():
            task = asyncio.create_task(self._run_coordinator(name, coordinator))
            self._update_tasks[name] = task

    async def stop(self) -> None:
        """Stop all coordinators."""
        if not self._is_running:
            return
        
        self._is_running = False
        _LOGGER.info("Stopping smart coordinator manager for %s", self.device.name)
        
        # Cancel all tasks
        for task in self._update_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._update_tasks.values(), return_exceptions=True)
        self._update_tasks.clear()

    async def _run_coordinator(
        self, 
        name: str, 
        coordinator: BatchedDeviceDataUpdateCoordinator
    ) -> None:
        """Run a single coordinator."""
        while self._is_running:
            try:
                await coordinator.async_update()
                await asyncio.sleep(coordinator.update_interval.total_seconds())
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.error("Coordinator %s failed: %s", name, err)
                # Wait before retrying
                await asyncio.sleep(30)

    def get_coordinator(self, name: str) -> Optional[BatchedDeviceDataUpdateCoordinator]:
        """Get a coordinator by name."""
        return self.coordinators.get(name)

    def get_api_stats(self) -> Dict[str, Any]:
        """Get API call statistics."""
        return self.api_manager.get_call_stats()

    def force_refresh_all(self) -> None:
        """Force refresh all coordinators."""
        self.api_manager.force_refresh_all()
        for coordinator in self.coordinators.values():
            coordinator.force_refresh()
