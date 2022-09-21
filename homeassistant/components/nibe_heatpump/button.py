"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, Coordinator

DESCRIPTIONS = (
    ButtonEntityDescription(
        key="alarm-reset-45171",
        name="Reset Alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(Button(coordinator, description) for description in DESCRIPTIONS)


class Button(CoordinatorEntity[Coordinator], ButtonEntity):
    """Sensor entity."""

    def __init__(
        self, coordinator: Coordinator, description: ButtonEntityDescription
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, set())
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Execute the command."""
        coil = self.coordinator.heatpump.get_coil_by_name(self.entity_description.key)
        await self.coordinator.async_write_coil(coil, 1)
