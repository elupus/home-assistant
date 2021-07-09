"""Support for lights."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    COLOR_MODE_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import EntryState
from .const import DOMAIN
from .device import COMMAND_LIGHT_ON_OFF, Device, State


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""

    entrystate: EntryState = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [Light(entrystate.coordinator, entrystate.device, entrystate.device_info)]
    )


class Light(CoordinatorEntity[State], LightEntity):
    """Light device."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init Tuya fan device."""
        super().__init__(coordinator)
        self._device = device
        self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
        self._attr_unique_id = device.address
        self._attr_device_info = device_info
        self._attr_name = device_info["name"]
        self._update_from_device_data(coordinator.data)

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
            self._attr_is_on = True
            await self._device.send_dim(int(self._attr_brightness * (100.0 / 255.0)))
        else:
            if not self._attr_is_on:
                await self._device.send_command(COMMAND_LIGHT_ON_OFF)
                self._attr_is_on = True
                self._attr_brightness = 255
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        if self._attr_is_on:
            await self._device.send_command(COMMAND_LIGHT_ON_OFF)
            self._attr_is_on = False
            self._attr_brightness = 0
        self.async_write_ha_state()

    def _update_from_device_data(self, data: State | None) -> None:
        """Handle data update."""
        if data:
            self._attr_is_on = data.light_on
            self._attr_brightness = int(data.dim_level * (255.0 / 100.0))
        else:
            self._attr_is_on = False
            self._attr_brightness = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._update_from_device_data(self.coordinator.data)
        self.async_write_ha_state()
