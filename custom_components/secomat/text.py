"""Text platform for Krüger Secomat quiet hours."""
from __future__ import annotations

import logging
import re
from datetime import time

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import SecomatCoordinator

_LOGGER = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Secomat text entities for quiet hours times."""
    coordinator: SecomatCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.data.get("serial_number", "unknown")

    entities = [
        SecomatQuietTimeText(coordinator, serial, "quiet_start", "Quiet From", "22:00"),
        SecomatQuietTimeText(coordinator, serial, "quiet_end", "Quiet Until", "06:30"),
        SecomatQuietTimeText(coordinator, serial, "quiet_start_weekend", "Quiet From (Weekend)", "22:00"),
        SecomatQuietTimeText(coordinator, serial, "quiet_end_weekend", "Quiet Until (Weekend)", "08:00"),
    ]

    async_add_entities(entities)

    for entity in entities:
        coordinator.quiet_time_entities[entity._key] = entity


class SecomatQuietTimeText(RestoreEntity, TextEntity):
    """Secomat quiet hours time as text input (HH:MM)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = "config"
    _attr_mode = TextMode.TEXT
    _attr_pattern = r"\d{1,2}:\d{2}"
    _attr_native_min = 4
    _attr_native_max = 5

    def __init__(
        self,
        coordinator: SecomatCoordinator,
        serial: str,
        key: str,
        name: str,
        default: str,
    ) -> None:
        """Initialize the text entity."""
        self._coordinator = coordinator
        self._serial = serial
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{serial}_{key}"
        self._default = default
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
        if (last_state := await self.async_get_last_state()) and last_state.state:
            if _TIME_RE.match(last_state.state):
                self._value = last_state.state

    @property
    def native_value(self) -> str:
        """Return the current time value as HH:MM."""
        return self._value

    def as_time(self) -> time:
        """Parse the stored value as a time object."""
        m = _TIME_RE.match(self._value)
        if m:
            return time(int(m.group(1)), int(m.group(2)))
        return time(0, 0)

    async def async_set_value(self, value: str) -> None:
        """Set the time value."""
        value = value.strip()
        if not _TIME_RE.match(value):
            _LOGGER.warning("Invalid time format: %s (expected HH:MM)", value)
            return
        self._value = value
        self.async_write_ha_state()
