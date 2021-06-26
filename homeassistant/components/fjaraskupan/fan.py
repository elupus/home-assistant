"""Support for Tuya fans."""
from __future__ import annotations

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .const import DOMAIN
from .device import COMMAND_STOP_FAN, Device

ORDERED_NAMED_FAN_SPEEDS = ["1", "2", "3", "4", "5", "6"]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tuya sensors dynamically through tuya discovery."""

    device: Device = hass.data[DOMAIN][config_entry.entry_id]
    await async_add_entities(Fan(device))


class Fan(FanEntity):
    """Tuya fan devices."""

    def __init__(self, device: Device) -> None:
        """Init Tuya fan device."""
        self._device = device
        self._default_on_speed = "1"
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
        new_speed = self._default_on_speed

        if percentage is not None:
            new_speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
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
    def is_on(self):
        """Return true if the entity is on."""
        return True

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        return None

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED
