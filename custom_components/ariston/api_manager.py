"""API call manager with caching, batching, and advanced retry logic."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import weakref

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .logging_config import get_ariston_logger

_LOGGER = get_ariston_logger(__name__)


class CallType(Enum):
    """Types of API calls for prioritization and batching."""
    STATE_UPDATE = "state_update"
    BUS_ERRORS = "bus_errors"
    ENERGY_DATA = "energy_data"
    FEATURES = "features"
    USER_ACTION = "user_action"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class APICallManager:
    """Manages API calls with caching, batching, and circuit breaker pattern."""

    def __init__(self, hass: HomeAssistant, device: Any) -> None:
        """Initialize the API call manager."""
        self.hass = hass
        self.device = device
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: Dict[str, timedelta] = {}
        self._pending_calls: Dict[CallType, List[Callable]] = {}
        self._last_call_time: Dict[CallType, datetime] = {}
        self._circuit_breaker_state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._call_stats: Dict[CallType, Dict[str, int]] = {
            call_type: {"success": 0, "failure": 0, "cached": 0}
            for call_type in CallType
        }
        
        # Circuit breaker configuration
        self._max_failures = 5
        self._failure_window = timedelta(minutes=5)
        self._recovery_timeout = timedelta(minutes=2)
        
        # Rate limiting
        self._min_call_interval = timedelta(seconds=2)  # Minimum 2 seconds between calls
        self._batch_window = timedelta(seconds=5)  # Batch calls within 5 seconds
        
        # Cache TTL configuration
        self._cache_ttl[CallType.STATE_UPDATE] = timedelta(seconds=30)  # 30 seconds
        self._cache_ttl[CallType.BUS_ERRORS] = timedelta(minutes=5)     # 5 minutes
        self._cache_ttl[CallType.ENERGY_DATA] = timedelta(minutes=10)   # 10 minutes
        self._cache_ttl[CallType.FEATURES] = timedelta(hours=1)         # 1 hour
        self._cache_ttl[CallType.USER_ACTION] = timedelta(seconds=0)    # No caching for user actions

    async def call_with_retry(
        self,
        call_type: CallType,
        call_func: Callable,
        *args,
        force_refresh: bool = False,
        **kwargs
    ) -> Any:
        """Make an API call with caching, batching, and retry logic."""
        
        # Check circuit breaker
        if not self._is_circuit_breaker_closed():
            raise UpdateFailed("Circuit breaker is open - too many recent failures")
        
        # Check cache first (unless force refresh)
        if not force_refresh and call_type != CallType.USER_ACTION:
            cached_result = self._get_cached_result(call_type)
            if cached_result is not None:
                self._call_stats[call_type]["cached"] += 1
                _LOGGER.debug("Returning cached result for %s", call_type.value)
                return cached_result
        
        # Rate limiting - batch calls if possible
        if self._should_batch_call(call_type):
            return await self._batch_call(call_type, call_func, *args, **kwargs)
        
        # Make the actual call with retry logic
        try:
            result = await self._execute_call_with_retry(call_type, call_func, *args, **kwargs)
            
            # Cache successful results
            if call_type != CallType.USER_ACTION:
                self._cache_result(call_type, result)
            
            self._call_stats[call_type]["success"] += 1
            self._reset_circuit_breaker()
            return result
            
        except Exception as err:
            self._call_stats[call_type]["failure"] += 1
            self._handle_call_failure()
            _LOGGER.error("API call failed for %s: %s", call_type.value, err)
            raise UpdateFailed(f"API call failed: {err}") from err

    def _get_cached_result(self, call_type: CallType) -> Optional[Any]:
        """Get cached result if available and not expired."""
        cache_key = call_type.value
        if cache_key not in self._cache:
            return None
        
        cache_entry = self._cache[cache_key]
        if "timestamp" not in cache_entry:
            return None
        
        cache_time = cache_entry["timestamp"]
        ttl = self._cache_ttl.get(call_type, timedelta(seconds=30))
        
        if datetime.now() - cache_time > ttl:
            # Cache expired
            del self._cache[cache_key]
            return None
        
        return cache_entry.get("data")

    def _cache_result(self, call_type: CallType, result: Any) -> None:
        """Cache the result with timestamp."""
        cache_key = call_type.value
        self._cache[cache_key] = {
            "data": result,
            "timestamp": datetime.now()
        }

    def _should_batch_call(self, call_type: CallType) -> bool:
        """Check if call should be batched."""
        if call_type == CallType.USER_ACTION:
            return False  # User actions should be immediate
        
        last_call = self._last_call_time.get(call_type)
        if last_call is None:
            return False
        
        return datetime.now() - last_call < self._batch_window

    async def _batch_call(
        self, 
        call_type: CallType, 
        call_func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """Batch multiple calls of the same type."""
        _LOGGER.debug("Batching call for %s", call_type.value)
        
        # For now, just execute immediately but with rate limiting
        await self._rate_limit_call(call_type)
        return await self._execute_call_with_retry(call_type, call_func, *args, **kwargs)

    async def _rate_limit_call(self, call_type: CallType) -> None:
        """Ensure minimum time between calls."""
        last_call = self._last_call_time.get(call_type)
        if last_call is not None:
            time_since_last = datetime.now() - last_call
            if time_since_last < self._min_call_interval:
                sleep_time = (self._min_call_interval - time_since_last).total_seconds()
                _LOGGER.debug("Rate limiting: sleeping for %.2f seconds", sleep_time)
                await asyncio.sleep(sleep_time)
        
        self._last_call_time[call_type] = datetime.now()

    async def _execute_call_with_retry(
        self, 
        call_type: CallType, 
        call_func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """Execute API call with exponential backoff retry logic."""
        max_retries = self._get_max_retries(call_type)
        base_delay = self._get_base_delay(call_type)
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                _LOGGER.debug(
                    "Executing %s call (attempt %d/%d)",
                    call_type.value,
                    attempt + 1,
                    max_retries + 1,
                )
                
                result = await call_func(*args, **kwargs)
                return result
                
            except Exception as err:
                last_exception = err
                
                if attempt < max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)  # ±10% jitter
                    total_delay = max(0, delay + jitter)
                    
                    _LOGGER.warning(
                        "%s call failed (attempt %d/%d), retrying in %.2fs: %s",
                        call_type.value,
                        attempt + 1,
                        max_retries + 1,
                        total_delay,
                        err,
                    )
                    await asyncio.sleep(total_delay)
                else:
                    _LOGGER.error(
                        "%s call failed after %d attempts: %s",
                        call_type.value,
                        max_retries + 1,
                        err,
                    )
        
        raise last_exception

    def _get_max_retries(self, call_type: CallType) -> int:
        """Get maximum retries based on call type."""
        retry_config = {
            CallType.STATE_UPDATE: 3,
            CallType.BUS_ERRORS: 2,
            CallType.ENERGY_DATA: 2,
            CallType.FEATURES: 1,
            CallType.USER_ACTION: 5,  # User actions get more retries
        }
        return retry_config.get(call_type, 2)

    def _get_base_delay(self, call_type: CallType) -> float:
        """Get base delay for exponential backoff."""
        delay_config = {
            CallType.STATE_UPDATE: 1.0,
            CallType.BUS_ERRORS: 2.0,
            CallType.ENERGY_DATA: 2.0,
            CallType.FEATURES: 3.0,
            CallType.USER_ACTION: 0.5,  # User actions retry faster
        }
        return delay_config.get(call_type, 1.0)

    def _is_circuit_breaker_closed(self) -> bool:
        """Check if circuit breaker allows calls."""
        if self._circuit_breaker_state == CircuitBreakerState.CLOSED:
            return True
        
        if self._circuit_breaker_state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (self._last_failure_time and 
                datetime.now() - self._last_failure_time > self._recovery_timeout):
                self._circuit_breaker_state = CircuitBreakerState.HALF_OPEN
                _LOGGER.info("Circuit breaker moving to HALF_OPEN state")
                return True
            return False
        
        # HALF_OPEN state - allow one call to test
        return True

    def _handle_call_failure(self) -> None:
        """Handle API call failure for circuit breaker."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        
        if self._failure_count >= self._max_failures:
            self._circuit_breaker_state = CircuitBreakerState.OPEN
            _LOGGER.warning(
                "Circuit breaker opened after %d failures in %s",
                self._failure_count,
                self._failure_window,
            )

    def _reset_circuit_breaker(self) -> None:
        """Reset circuit breaker on successful call."""
        if self._circuit_breaker_state != CircuitBreakerState.CLOSED:
            _LOGGER.info("Circuit breaker reset to CLOSED state")
        self._circuit_breaker_state = CircuitBreakerState.CLOSED
        self._failure_count = 0

    def clear_cache(self, call_type: Optional[CallType] = None) -> None:
        """Clear cache for specific call type or all types."""
        if call_type:
            cache_key = call_type.value
            if cache_key in self._cache:
                del self._cache[cache_key]
                _LOGGER.debug("Cleared cache for %s", call_type.value)
        else:
            self._cache.clear()
            _LOGGER.debug("Cleared all cache")

    def get_call_stats(self) -> Dict[str, Any]:
        """Get call statistics for monitoring."""
        total_calls = sum(
            stats["success"] + stats["failure"] + stats["cached"]
            for stats in self._call_stats.values()
        )
        
        return {
            "total_calls": total_calls,
            "circuit_breaker_state": self._circuit_breaker_state.value,
            "failure_count": self._failure_count,
            "cache_size": len(self._cache),
            "call_breakdown": {
                call_type.value: stats for call_type, stats in self._call_stats.items()
            }
        }

    def force_refresh_all(self) -> None:
        """Force refresh all cached data on next call."""
        self.clear_cache()
        _LOGGER.info("Forced refresh of all cached data")


class OptimizedDeviceDataUpdateCoordinator:
    """Optimized coordinator that uses the API call manager."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Any,
        scan_interval_seconds: int,
        coordinator_name: str,
        call_type: CallType,
        api_manager: APICallManager,
    ) -> None:
        """Initialize the optimized coordinator."""
        self.hass = hass
        self.device = device
        self.coordinator_name = coordinator_name
        self.call_type = call_type
        self.api_manager = api_manager
        self.update_interval = timedelta(seconds=scan_interval_seconds)
        
        self._consecutive_failures = 0
        self._last_successful_update: Optional[datetime] = None
        self._last_update_attempt: Optional[datetime] = None
        self._is_updating = False

    async def async_update(self) -> Dict[str, Any]:
        """Update device data using the API manager."""
        if self._is_updating:
            _LOGGER.debug("Update already in progress for %s, skipping", self.device.name)
            return {"status": "skipped", "device": self.device.name}
        
        self._is_updating = True
        self._last_update_attempt = datetime.now()
        
        try:
            # Get the appropriate update method based on call type
            update_method = self._get_update_method()
            
            result = await self.api_manager.call_with_retry(
                self.call_type,
                update_method,
                force_refresh=False
            )
            
            self._consecutive_failures = 0
            self._last_successful_update = datetime.now()
            
            _LOGGER.debug("Successfully updated %s data", self.device.name)
            return {"status": "success", "device": self.device.name, "data": result}
            
        except Exception as err:
            self._consecutive_failures += 1
            _LOGGER.error("Failed to update %s data: %s", self.device.name, err)
            raise UpdateFailed(f"Failed to update {self.device.name}: {err}") from err
        finally:
            self._is_updating = False

    def _get_update_method(self) -> Callable:
        """Get the appropriate update method based on call type."""
        method_map = {
            CallType.STATE_UPDATE: self.device.async_update_state,
            CallType.BUS_ERRORS: self.device.async_get_bus_errors,
            CallType.ENERGY_DATA: self.device.async_update_energy,
            CallType.FEATURES: self.device.async_get_features,
        }
        return method_map.get(self.call_type, self.device.async_update_state)

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
