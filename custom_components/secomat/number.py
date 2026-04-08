"""Number platform for Krüger Secomat."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SecomatCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Secomat number entities."""
    coordinator: SecomatCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.data.get("serial_number", "unknown")

    async_add_entities([SecomatStartDelay(coordinator, entry, serial)])


class SecomatStartDelay(CoordinatorEntity[SecomatCoordinator], NumberEntity):
    """Secomat start delay (minutes from now)."""

    _attr_has_entity_name = True
    _attr_name = "Start Delay"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 1440  # 24 hours
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SecomatCoordinator, entry: ConfigEntry, serial: str) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial}_start_delay"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": f"Secomat {serial}",
            "manufacturer": "Krüger",
            "model": "Secomat",
        }

    @property
    def native_value(self) -> float:
        """Return the current start delay in minutes."""
        seconds = self.coordinator.data.get("next_start", 0)
        try:
            return round(int(seconds) / 60)
        except (ValueError, TypeError):
            return 0

    async def async_set_native_value(self, value: float) -> None:
        """Set start delay and start laundry drying."""
        from .api import SecoматAPIError
        delay_seconds = int(value * 60)
        try:
            await self.coordinator.api.start_laundry_drying(delay_seconds=delay_seconds)
            await self.coordinator.async_request_refresh()
        except SecoматAPIError as err:
            _LOGGER.error("Failed to start with delay: %s", err)
