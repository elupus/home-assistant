"""The Fjäråskupan integration."""
from __future__ import annotations

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = ["fan"]


class Device:
    """Communication handler."""

    def __init__(self, client: BleakClient) -> None:
        """Initialize handler."""
        self.client = client

    async def send_command(self, cmd):
        """Send a given command."""
        data: str = "1234" + cmd
        await self.client.write_gatt_char(0x000B, data.encode("ASCII"), True)

    async def set_fan_speed(self, speed: int):
        """Set a numbered fan speed."""
        await self.send_command(f"-Luft-{speed}-")

    async def set_fan_off(self):
        """Turn fan off."""
        await self.send_command("Luft-Aus")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fjäråskupan from a config entry."""
    client = BleakClient(entry.data["mac"])
    try:
        await client.connect()
    except (BleakError, TimeoutError) as exc:
        raise ConfigEntryNotReady from exc

    device = Device(client)
    hass.data[DOMAIN][entry.entry_id] = device

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device: Device = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await device.client.disconnect()
        except TimeoutError:
            unload_ok = False

    return unload_ok
