"""Support for Tuya fans."""
from __future__ import annotations

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import Coordinator, EntryState
from .const import DOMAIN
from .device import COMMAND_STOP_FAN, Device, State

ORDERED_NAMED_FAN_SPEEDS = ["1", "2", "3", "4", "5", "6"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""

    entrystate: EntryState = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([Fan(entrystate.coordinator, entrystate.device)])


class Fan(CoordinatorEntity[State], FanEntity):
    """Fan device."""

    def __init__(self, coordinator: Coordinator, device: Device) -> None:
        """Init fan device."""
        super().__init__(coordinator)
        self._device = device
        self._default_on_speed = 100
        self._percentage: int = 0
        self._attr_name = "Fjäråskupan"

    async def async_set_percentage(self, percentage: int) -> None:
        """Set speed."""
        new_speed = percentage_to_ordered_list_item(
            ORDERED_NAMED_FAN_SPEEDS, percentage
        )
        await self._device.send_fan_speed(int(new_speed))

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""

        if percentage is not None:
            self._percentage = percentage
        else:
            self._percentage = self._default_on_speed

        new_speed = percentage_to_ordered_list_item(
            ORDERED_NAMED_FAN_SPEEDS, self._percentage
        )

        await self._device.send_fan_speed(int(new_speed))

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._device.send_command(COMMAND_STOP_FAN)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        return self._percentage

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""

        if data := self.coordinator.data:
            self._attr_is_on = data.fan_speed != 0
            self._percentage = ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS, str(data.fan_speed)
            )
        else:
            self._attr_is_on = False
            self._percentage = 0

        self.async_write_ha_state()
