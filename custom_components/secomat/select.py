"""Select platform for Krüger Secomat."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SecoматAPIError
from .const import DOMAIN, TARGET_MOISTURE_LEVELS, TARGET_MOISTURE_TO_INT
from .coordinator import SecomatCoordinator

# Time options in 30-min increments for quiet hours
_TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Secomat select entities."""
    coordinator: SecomatCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.data.get("serial_number", "unknown")

    time_selects = [
        SecomatQuietTimeSelect(coordinator, serial, "silent_from_wd", "Quiet From", "22:00"),
        SecomatQuietTimeSelect(coordinator, serial, "silent_to_wd", "Quiet Until", "06:30"),
        SecomatQuietTimeSelect(coordinator, serial, "silent_from_we", "Quiet From (Weekend)", "22:00"),
        SecomatQuietTimeSelect(coordinator, serial, "silent_to_we", "Quiet Until (Weekend)", "08:00"),
    ]

    async_add_entities([SecomatTargetMoistureSelect(coordinator, entry, serial)] + time_selects)

    for entity in time_selects:
        coordinator.quiet_time_entities[entity._key] = entity


class SecomatTargetMoistureSelect(CoordinatorEntity[SecomatCoordinator], SelectEntity):
    """Secomat target moisture level selector."""

    _attr_has_entity_name = True
    _attr_name = "Target Moisture"
    _attr_icon = "mdi:water-percent"
    _attr_options = list(TARGET_MOISTURE_LEVELS.values())

    def __init__(self, coordinator: SecomatCoordinator, entry: ConfigEntry, serial: str) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial}_target_moisture"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": f"Secomat {serial}",
            "manufacturer": "Krüger",
            "model": "Secomat",
        }

    @property
    def current_option(self) -> str | None:
        """Return the current target moisture level."""
        level = self.coordinator.data.get("target_humidity_level", 0)
        return TARGET_MOISTURE_LEVELS.get(level, "moist")

    async def async_select_option(self, option: str) -> None:
        """Set the target moisture level."""
        level = TARGET_MOISTURE_TO_INT.get(option)
        if level is None:
            _LOGGER.error("Unknown target moisture option: %s", option)
            return
        try:
            await self.coordinator.api.set_target_moisture(level)
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            _LOGGER.error("Failed to set target moisture: %s", err)


class SecomatQuietTimeSelect(SelectEntity):
    """Secomat quiet hours time as select (HH:MM in 30-min steps)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_options = _TIME_OPTIONS

    def __init__(self, coordinator, serial, key, name, default):
        self._coordinator = coordinator
        self._serial = serial
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{serial}_{key}"
        self._value = default
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": f"Secomat {serial}",
            "manufacturer": "Krüger",
            "model": "Secomat",
        }

    @property
    def current_option(self):
        return self._value

    def as_time(self):
        from datetime import time
        h, m = self._value.split(":")
        return time(int(h), int(m))

    async def async_select_option(self, option):
        self._value = option
        self.async_write_ha_state()
