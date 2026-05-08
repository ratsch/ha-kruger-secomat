"""Data update coordinator for Krüger Secomat."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SecomatAPI, SecoматAPIError
from .const import (
    DEFAULT_SCAN_INTERVAL, DOMAIN,
    QUIET_START_WEEKDAY, QUIET_END_WEEKDAY,
    QUIET_START_WEEKEND, QUIET_END_WEEKEND,
)

STORAGE_KEY = f"{DOMAIN}_quiet_state"
STORAGE_VERSION = 1

_LOGGER = logging.getLogger(__name__)


class SecomatCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Secomat data update coordinator."""

    def __init__(self, hass: HomeAssistant, api: SecomatAPI) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

        # Quiet hours state
        self.quiet_hours_enabled: bool = False
        self.quiet_time_entities: dict[str, Any] = {}
        self._was_running_laundry: bool = False
        self._was_running_room: bool = False
        self._quiet_was_active: bool = False
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._store_loaded: bool = False

        # Auto room drying after laundry
        self.auto_room_after_laundry: bool = False
        self._prev_laundry_active: bool = False

    async def _save_quiet_state(self) -> None:
        """Persist quiet hours running state to disk."""
        await self._store.async_save({
            "was_running_laundry": self._was_running_laundry,
            "was_running_room": self._was_running_room,
            "quiet_was_active": self._quiet_was_active,
        })

    async def _load_quiet_state(self) -> None:
        """Restore quiet hours running state from disk."""
        if self._store_loaded:
            return
        self._store_loaded = True
        data = await self._store.async_load()
        if data:
            self._was_running_laundry = data.get("was_running_laundry", False)
            self._was_running_room = data.get("was_running_room", False)
            self._quiet_was_active = data.get("quiet_was_active", False)
            _LOGGER.warning("Restored quiet state: was_laundry=%s was_room=%s was_active=%s",
                            self._was_running_laundry, self._was_running_room, self._quiet_was_active)

    def _get_quiet_time(self, key: str, default: time) -> time:
        """Get a quiet hours time value from the select entities."""
        entity = self.quiet_time_entities.get(key)
        if entity:
            return entity.as_time()
        return default

    @property
    def is_quiet_hours_active(self) -> bool:
        """Check if we're currently in quiet hours."""
        if not self.quiet_hours_enabled:
            return False

        now = datetime.now()
        weekday = now.weekday()  # 0=Mon, 6=Sun
        is_weekend = weekday >= 5  # Sat, Sun

        if is_weekend:
            start = self._get_quiet_time("silent_from_we", time(*QUIET_START_WEEKEND))
            end = self._get_quiet_time("silent_to_we", time(*QUIET_END_WEEKEND))
        else:
            start = self._get_quiet_time("silent_from_wd", time(*QUIET_START_WEEKDAY))
            end = self._get_quiet_time("silent_to_wd", time(*QUIET_END_WEEKDAY))

        now_time = now.time()

        # Handle overnight window (e.g. 22:00 - 06:30)
        if start > end:
            return now_time >= start or now_time < end
        else:
            return start <= now_time < end

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Secomat API and enforce quiet hours."""
        try:
            data = await self.api.get_state()
        except SecoматAPIError as err:
            raise UpdateFailed(f"Error fetching Secomat data: {err}") from err

        await self._enforce_quiet_hours(data)
        await self._auto_room_after_laundry_check(data)

        return data

    async def _auto_room_after_laundry_check(self, data: dict[str, Any]) -> None:
        """Auto-start room drying when a laundry cycle ends."""
        state = data.get("secomat_state", 0)
        # Active drying states: running, drying, cooling, pause
        laundry_active = state in (2, 3, 4, 5)
        room_on = data.get("room_drying_enabled", 0) == 1

        if (self.auto_room_after_laundry
                and self._prev_laundry_active
                and not laundry_active
                and not self.is_quiet_hours_active
                and not room_on):
            _LOGGER.warning(
                "Laundry cycle ended (state=%s), auto-starting room drying", state)
            try:
                await self.api.start_room_drying()
            except SecoматAPIError:
                _LOGGER.warning("Failed to auto-start room drying")

        self._prev_laundry_active = laundry_active

    async def _enforce_quiet_hours(self, data: dict[str, Any]) -> None:
        """Enforce quiet hours: turn off device and remember state."""
        await self._load_quiet_state()
        quiet_active = self.is_quiet_hours_active
        state = data.get("secomat_state", 0)
        device_on = state > 0
        room_on = data.get("room_drying_enabled", 0) == 1
        if self.quiet_hours_enabled:
            _LOGGER.warning("Quiet hours check: active=%s was_active=%s device_on=%s room_on=%s entities=%s",
                            quiet_active, self._quiet_was_active, device_on, room_on,
                            list(self.quiet_time_entities.keys()))

        # Entering quiet hours
        if quiet_active and not self._quiet_was_active:
            _LOGGER.warning("Quiet hours started")
            if device_on:
                _LOGGER.warning("Saving laundry state and turning off for quiet hours")
                self._was_running_laundry = True
                try:
                    await self.api.stop_laundry_drying()
                except SecoматAPIError:
                    _LOGGER.warning("Failed to turn off laundry for quiet hours")
            if room_on:
                _LOGGER.warning("Saving room drying state and turning off for quiet hours")
                self._was_running_room = True
                try:
                    await self.api.stop_room_drying()
                except SecoматAPIError:
                    _LOGGER.warning("Failed to turn off room drying for quiet hours")
            self._quiet_was_active = quiet_active
            await self._save_quiet_state()

        # During quiet hours: enforce off
        elif quiet_active:
            if device_on:
                _LOGGER.warning("Device turned on during quiet hours, turning off")
                if not self._was_running_laundry:
                    self._was_running_laundry = True
                    await self._save_quiet_state()
                try:
                    await self.api.stop_laundry_drying()
                except SecoматAPIError:
                    pass
            if room_on:
                _LOGGER.warning("Room drying on during quiet hours, turning off")
                if not self._was_running_room:
                    self._was_running_room = True
                    await self._save_quiet_state()
                try:
                    await self.api.stop_room_drying()
                except SecoматAPIError:
                    pass

        # Leaving quiet hours
        elif not quiet_active and self._quiet_was_active:
            _LOGGER.warning("Quiet hours ended")
            if self._was_running_laundry:
                _LOGGER.warning("Restoring laundry drying after quiet hours")
                try:
                    await self.api.start_laundry_drying(delay_seconds=0)
                except SecoматAPIError:
                    _LOGGER.warning("Failed to restore laundry after quiet hours")
                self._was_running_laundry = False
            if self._was_running_room:
                _LOGGER.warning("Restoring room drying after quiet hours")
                try:
                    await self.api.start_room_drying()
                except SecoматAPIError:
                    _LOGGER.warning("Failed to restore room drying after quiet hours")
                self._was_running_room = False
            self._quiet_was_active = quiet_active
            await self._save_quiet_state()

        else:
            self._quiet_was_active = quiet_active
