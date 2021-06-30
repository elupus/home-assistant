"""The Fjäråskupan integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DISPATCH_DETECTION, DOMAIN
from .device import Device, State

PLATFORMS = ["fan", "light"]

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntryState:
    """Store state of config entry."""

    scanner: BleakScanner
    client: BleakClient
    device: Device
    coordinator: Coordinator


class Coordinator(DataUpdateCoordinator[State]):
    """Update coordinator for device."""

    def __init__(self, hass: HomeAssistant, device: Device) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass, logger=_LOGGER, name="Fjäråskupan Updater", update_interval=None
        )
        self.device = device

    def detection_callback(self, advertisement_data: AdvertisementData):
        """Handle callback when we get new data."""
        self.device.detection_callback(advertisement_data)
        self.async_set_updated_data(self.device.state)

    def characteristic_callback(self, sender: int, databytes: bytearray):
        """Handle callback on changes to characteristics."""
        self.device.characteristic_callback(sender, databytes)
        self.async_set_updated_data(self.device.state)


async def async_startup_scanner(hass):
    """Startup the background event scanner."""
    scanner = BleakScanner()
    await scanner.start()

    def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData):
        _LOGGER.debug("Detection: %s - %s", device, advertisement_data)
        async_dispatcher_send(hass, DISPATCH_DETECTION, device, advertisement_data)

    scanner.register_detection_callback(detection_callback)
    return scanner


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fjäråskupan from a config entry."""

    scanner = async_startup_scanner(hass)

    address: str = entry.data["mac"]
    client = BleakClient(address)
    try:
        await client.connect()
    except (BleakError, TimeoutError) as exc:
        raise ConfigEntryNotReady from exc

    device = Device(client)
    coordinator = Coordinator(hass, device)

    def detection_handler(ble_device: BLEDevice, advertisement_data: AdvertisementData):
        if ble_device.address == address:
            coordinator.detection_callback(advertisement_data)

    async_dispatcher_connect(hass, DISPATCH_DETECTION, detection_handler)

    await client.start_notify(device.tx_char, coordinator.characteristic_callback)

    hass.data[DOMAIN][entry.entry_id] = EntryState(scanner, client, device, coordinator)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entrystate: EntryState = hass.data[DOMAIN].pop(entry.entry_id)
        await entrystate.client.disconnect()
        await entrystate.scanner.stop()

    return unload_ok
