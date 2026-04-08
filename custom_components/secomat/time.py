"""Time selectors for Krüger Secomat quiet hours (using SelectEntity)."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import SecomatCoordinator

_LOGGER = logging.getLogger(__name__)

# Generate time options in 30-min increments
_TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Secomat time select entities."""
    coordinator: SecomatCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.data.get("serial_number", "unknown")

    entities = [
        SecomatQuietTimeSelect(coordinator, serial, "silent_from_wd", "Quiet From", "22:00"),
        SecomatQuietTimeSelect(coordinator, serial, "silent_to_wd", "Quiet Until", "06:30"),
        SecomatQuietTimeSelect(coordinator, serial, "silent_from_we", "Quiet From (Weekend)", "22:00"),
        SecomatQuietTimeSelect(coordinator, serial, "silent_to_we", "Quiet Until (Weekend)", "08:00"),
    ]

    async_add_entities(entities)

    for entity in entities:
        coordinator.quiet_time_entities[entity._key] = entity


class SecomatQuietTimeSelect(RestoreEntity, SelectEntity):
    """Secomat quiet hours time as select (HH:MM in 30-min steps)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = "config"
    _attr_options = _TIME_OPTIONS

    def __init__(
        self,
        coordinator: SecomatCoordinator,
        serial: str,
        key: str,
        name: str,
        default: str,
    ) -> None:
        """Initialize the select entity."""
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

    async def async_added_to_hass(self) -> None:
        """Restore previous state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) and last_state.state in _TIME_OPTIONS:
            self._value = last_state.state

    @property
    def current_option(self) -> str:
        """Return current time selection."""
        return self._value

    def as_time(self):
        """Parse as datetime.time for coordinator."""
        from datetime import time
        parts = self._value.split(":")
        return time(int(parts[0]), int(parts[1]))

    async def async_select_option(self, option: str) -> None:
        """Set the time."""
        self._value = option
        self.async_write_ha_state()
