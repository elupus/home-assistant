"""Support for Tuya fans."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    COLOR_MODE_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import percentage_to_ordered_list_item

from . import Coordinator, EntryState
from .const import DOMAIN
from .device import COMMAND_LIGHT_ON_OFF, Device, State

ORDERED_DIM_LEVEL = ["1", "2", "3"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""

    entrystate: EntryState = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([Light(entrystate.coordinator, entrystate.device)])


class Light(CoordinatorEntity[State], LightEntity):
    """Tuya fan devices."""

    def __init__(self, coordinator: Coordinator, device: Device) -> None:
        """Init Tuya fan device."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = "Fjäråskupan"
        self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
        self._attr_is_on = True

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            level = percentage_to_ordered_list_item(
                ORDERED_DIM_LEVEL, kwargs[ATTR_BRIGHTNESS]
            )
            await self._device.send_dim(int(level))
        else:
            await self._device.send_command(COMMAND_LIGHT_ON_OFF)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._device.send_command(COMMAND_LIGHT_ON_OFF)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        if data := self.coordinator.data:
            self._attr_is_on = data.light_on
            self._attr_brightness = data.dim_level
        else:
            self._attr_is_on = False
            self._attr_brightness = None

        self.async_write_ha_state()
