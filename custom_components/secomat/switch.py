"""Switch platform for Krüger Secomat."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SecoматAPIError
from .const import DOMAIN
from .coordinator import SecomatCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Secomat switches."""
    coordinator: SecomatCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.data.get("serial_number", "unknown")

    entities = [
        SecomatLaundrySwitch(coordinator, entry, serial),
        SecomatRoomDryingSwitch(coordinator, entry, serial),
        SecomatMoistureLockSwitch(coordinator, entry, serial),
        SecomatQuietHoursSwitch(coordinator, entry, serial),
    ]

    async_add_entities(entities)


class SecomatBaseSwitch(CoordinatorEntity[SecomatCoordinator], SwitchEntity):
    """Base class for Secomat switches."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SecomatCoordinator,
        entry: ConfigEntry,
        serial: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._serial = serial
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": f"Secomat {serial}",
            "manufacturer": "Krüger",
            "model": "Secomat",
        }


class SecomatLaundrySwitch(SecomatBaseSwitch):
    """Secomat laundry drying switch."""

    _attr_name = "Laundry Drying"
    _attr_icon = "mdi:washing-machine"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator, entry, serial):
        super().__init__(coordinator, entry, serial)
        self._attr_unique_id = f"{serial}_laundry_drying"
        self._optimistic_on: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return true if laundry drying is active."""
        state = self.coordinator.data.get("secomat_state", 0)
        device_on = state > 0
        if self._optimistic_on is not None:
            if device_on == self._optimistic_on:
                self._optimistic_on = None  # device caught up
            return self._optimistic_on
        return device_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on laundry drying (start now)."""
        try:
            await self.coordinator.api.start_laundry_drying(delay_seconds=0)
            self._optimistic_on = True
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            self._optimistic_on = None
            _LOGGER.error("Failed to turn on laundry drying: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off laundry drying."""
        try:
            await self.coordinator.api.stop_laundry_drying()
            self._optimistic_on = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            self._optimistic_on = None
            _LOGGER.error("Failed to turn off laundry drying: %s", err)


class SecomatRoomDryingSwitch(SecomatBaseSwitch):
    """Secomat room drying switch."""

    _attr_name = "Room Drying"
    _attr_icon = "mdi:home-thermometer"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator, entry, serial):
        super().__init__(coordinator, entry, serial)
        self._attr_unique_id = f"{serial}_room_drying"

    @property
    def is_on(self) -> bool:
        """Return true if room drying is enabled."""
        return self.coordinator.data.get("room_drying_enabled", 0) == 1

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on room drying."""
        try:
            await self.coordinator.api.start_room_drying()
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            _LOGGER.error("Failed to turn on room drying: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off room drying."""
        try:
            await self.coordinator.api.stop_room_drying()
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            _LOGGER.error("Failed to turn off room drying: %s", err)


class SecomatMoistureLockSwitch(SecomatBaseSwitch):
    """Secomat moisture target lock (apply to all drying processes)."""

    _attr_name = "Lock Target Moisture"
    _attr_icon = "mdi:lock"
    _attr_entity_category = "config"

    def __init__(self, coordinator, entry, serial):
        super().__init__(coordinator, entry, serial)
        self._attr_unique_id = f"{serial}_moisture_lock"

    @property
    def is_on(self) -> bool:
        """Return true if target moisture is locked."""
        return self.coordinator.data.get("target_humidity_level_locked", 0) == 1

    async def async_turn_on(self, **kwargs) -> None:
        """Lock target moisture for all drying processes."""
        try:
            await self.coordinator.api.set_target_moisture_lock(True)
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            _LOGGER.error("Failed to lock target moisture: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        """Unlock target moisture."""
        try:
            await self.coordinator.api.set_target_moisture_lock(False)
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            _LOGGER.error("Failed to unlock target moisture: %s", err)


class SecomatQuietHoursSwitch(SecomatBaseSwitch):
    """Enable/disable quiet hours enforcement."""

    _attr_name = "Quiet Hours"
    _attr_icon = "mdi:moon-waning-crescent"

    def __init__(self, coordinator, entry, serial):
        super().__init__(coordinator, entry, serial)
        self._attr_unique_id = f"{serial}_quiet_hours"
        self._enabled = False

    @property
    def is_on(self) -> bool:
        """Return true if quiet hours are enabled."""
        return self._enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable quiet hours."""
        self._enabled = True
        self.coordinator.quiet_hours_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable quiet hours."""
        self._enabled = False
        self.coordinator.quiet_hours_enabled = False
        self.async_write_ha_state()
