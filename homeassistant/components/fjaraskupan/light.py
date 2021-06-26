"""Support for Tuya fans."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    COLOR_MODE_BRIGHTNESS,
    LightEntity,
)
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .const import DOMAIN
from .device import COMMAND_LIGHT_ON_OFF, Device

ORDERED_DIM_LEVEL = ["1", "2", "3"]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tuya sensors dynamically through tuya discovery."""

    device: Device = hass.data[DOMAIN][config_entry.entry_id]
    await async_add_entities(Light(device))


class Light(LightEntity):
    """Tuya fan devices."""

    def __init__(self, device: Device) -> None:
        """Init Tuya fan device."""
        self._device = device
        self._attr_name = "Fjäråskupan"
        self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}

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

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return True
