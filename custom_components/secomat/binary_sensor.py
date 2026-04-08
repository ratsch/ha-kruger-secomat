"""Binary sensor platform for Krüger Secomat."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SecomatCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Secomat binary sensors."""
    coordinator: SecomatCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.data.get("serial_number", "unknown")

    async_add_entities([SecomatQuietActiveSensor(coordinator, entry, serial)])


class SecomatQuietActiveSensor(CoordinatorEntity[SecomatCoordinator], BinarySensorEntity):
    """Shows whether quiet hours are currently active."""

    _attr_has_entity_name = True
    _attr_name = "Quiet Hours Active"
    _attr_icon = "mdi:moon-waning-crescent"

    def __init__(self, coordinator: SecomatCoordinator, entry: ConfigEntry, serial: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial}_quiet_active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": f"Secomat {serial}",
            "manufacturer": "Krüger",
            "model": "Secomat",
        }

    @property
    def is_on(self) -> bool:
        """Return true if quiet hours are currently active."""
        return self.coordinator.is_quiet_hours_active
