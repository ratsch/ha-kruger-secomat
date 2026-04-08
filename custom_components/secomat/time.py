"""Time platform for Krüger Secomat quiet hours."""
from __future__ import annotations

import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SecomatCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Secomat time entities."""
    coordinator: SecomatCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.data.get("serial_number", "unknown")

    entities = [
        SecomatQuietTime(coordinator, serial, "quiet_start", "Quiet From", time(22, 0)),
        SecomatQuietTime(coordinator, serial, "quiet_end", "Quiet Until", time(6, 30)),
        SecomatQuietTime(coordinator, serial, "quiet_start_weekend", "Quiet From (Weekend)", time(22, 0)),
        SecomatQuietTime(coordinator, serial, "quiet_end_weekend", "Quiet Until (Weekend)", time(8, 0)),
    ]

    async_add_entities(entities)

    # Register time entities with coordinator for quiet hours logic
    for entity in entities:
        coordinator.quiet_time_entities[entity._key] = entity


class SecomatQuietTime(RestoreEntity, TimeEntity):
    """Secomat quiet hours time setting."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = "config"

    def __init__(
        self,
        coordinator: SecomatCoordinator,
        serial: str,
        key: str,
        name: str,
        default: time,
    ) -> None:
        """Initialize the time entity."""
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
            try:
                parts = last_state.state.split(":")
                self._value = time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                self._value = self._default

    @property
    def native_value(self) -> time:
        """Return the current time value."""
        return self._value

    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        self._value = value
        self.async_write_ha_state()
