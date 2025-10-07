"""Tests for coordinator module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
import pytest

from custom_components.ariston.coordinator import DeviceDataUpdateCoordinator


class TestDeviceDataUpdateCoordinator:
    """Test cases for DeviceDataUpdateCoordinator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.hass = Mock()
        self.device = Mock()
        self.device.name = "Test Device"
        self.async_update_state = AsyncMock()
        
        self.coordinator = DeviceDataUpdateCoordinator(
            hass=self.hass,
            device=self.device,
            scan_interval_seconds=60,
            coordinator_name="test",
            async_update_state=self.async_update_state,
        )

    def test_init(self):
        """Test coordinator initialization."""
        assert self.coordinator.device == self.device
        assert self.coordinator._async_update_state == self.async_update_state
        assert self.coordinator._consecutive_failures == 0
        assert self.coordinator._last_successful_update is None

    @pytest.mark.asyncio
    async def test_async_update_with_retry_success(self):
        """Test successful update with retry."""
        self.async_update_state.return_value = None
        
        result = await self.coordinator._async_update_with_retry()
        
        assert result == {"status": "success", "device": "Test Device"}
        assert self.coordinator._consecutive_failures == 0
        assert self.coordinator._last_successful_update is not None
        self.async_update_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_with_retry_failure_then_success(self):
        """Test update failure followed by success."""
        self.async_update_state.side_effect = [Exception("Network error"), None]
        
        result = await self.coordinator._async_update_with_retry()
        
        assert result == {"status": "success", "device": "Test Device"}
        assert self.coordinator._consecutive_failures == 0
        assert self.async_update_state.call_count == 2

    @pytest.mark.asyncio
    async def test_async_update_with_retry_all_failures(self):
        """Test update with all retries failing."""
        self.async_update_state.side_effect = Exception("Persistent error")
        
        with pytest.raises(Exception) as exc_info:
            await self.coordinator._async_update_with_retry()
        
        assert "Failed to update Test Device after 4 attempts" in str(exc_info.value)
        assert self.coordinator._consecutive_failures == 4
        assert self.async_update_state.call_count == 4

    @pytest.mark.asyncio
    async def test_async_update_with_retry_exponential_backoff(self):
        """Test exponential backoff on retries."""
        self.async_update_state.side_effect = [Exception("Error 1"), Exception("Error 2"), None]
        
        with patch('asyncio.sleep') as mock_sleep:
            result = await self.coordinator._async_update_with_retry()
        
        # Should have 2 sleep calls with exponential backoff
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 5  # First retry: 5 seconds
        assert mock_sleep.call_args_list[1][0][0] == 10  # Second retry: 10 seconds
        assert result == {"status": "success", "device": "Test Device"}

    def test_is_available_no_successful_update(self):
        """Test availability when no successful update."""
        self.coordinator._last_successful_update = None
        assert not self.coordinator.is_available

    def test_is_available_recent_success(self):
        """Test availability with recent successful update."""
        # Set last successful update to 50 seconds ago (within 2 intervals of 60 seconds)
        self.coordinator._last_successful_update = datetime.now() - timedelta(seconds=50)
        
        # Mock the update_interval object
        mock_interval = Mock()
        mock_interval.total_seconds.return_value = 60
        self.coordinator.update_interval = mock_interval
        
        assert self.coordinator.is_available

    def test_is_available_old_success(self):
        """Test availability with old successful update."""
        # Set last successful update to 200 seconds ago (beyond 2 intervals of 60 seconds)
        self.coordinator._last_successful_update = datetime.now() - timedelta(seconds=200)
        
        # Mock the update_interval object
        mock_interval = Mock()
        mock_interval.total_seconds.return_value = 60
        self.coordinator.update_interval = mock_interval
        
        assert not self.coordinator.is_available

    def test_consecutive_failures_property(self):
        """Test consecutive failures property."""
        self.coordinator._consecutive_failures = 3
        assert self.coordinator.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_async_update_with_retry_resets_failures_on_success(self):
        """Test that failures are reset on successful update."""
        # First, simulate some failures
        self.coordinator._consecutive_failures = 2
        
        # Then succeed
        self.async_update_state.return_value = None
        
        await self.coordinator._async_update_with_retry()
        
        assert self.coordinator._consecutive_failures == 0
