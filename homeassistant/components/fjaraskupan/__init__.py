"""The Fjäråskupan integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DISPATCH_DETECTION, DOMAIN
from .device import DEVICE_NAME, Device, State

PLATFORMS = ["fan", "light", "sensor"]

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntryState:
    """Store state of config entry."""

    scanner: BleakScanner
    client: BleakClient
    device: Device
    coordinator: DataUpdateCoordinator[State]


async def async_startup_scanner(hass):
    """Startup the background event scanner."""
    scanner = BleakScanner()
    await scanner.start()

    async def detection_callback(
        device: BLEDevice, advertisement_data: AdvertisementData
    ):
        if device.name == DEVICE_NAME:
            _LOGGER.debug(
                "Detection: %s %s - %s", device.name, device, advertisement_data
            )
            async_dispatcher_send(hass, DISPATCH_DETECTION, device, advertisement_data)

    scanner.register_detection_callback(detection_callback)
    return scanner


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fjäråskupan from a config entry."""

    scanner = await async_startup_scanner(hass)
    try:
        address: str = entry.data["address"]
        client = BleakClient(address)
        try:
            await client.connect()
        except (BleakError, TimeoutError) as exc:
            raise ConfigEntryNotReady from exc

        device = Device(client)

        async def async_update_data():
            """Handle an explicit update request."""
            async with device.lock:
                databytes = await client.read_gatt_char(device.rx_char)
                device.characteristic_callback(databytes)
            return device.state

        coordinator = DataUpdateCoordinator[State](
            hass,
            logger=_LOGGER,
            name="Fjäråskupan Updater",
            update_interval=timedelta(seconds=60),
            update_method=async_update_data,
        )

        @callback
        def detection_callback(
            ble_device: BLEDevice, advertisement_data: AdvertisementData
        ):
            """Handle callback when we get new data."""
            if ble_device.address == address:
                device.detection_callback(advertisement_data)
                coordinator.async_set_updated_data(device.state)

        @callback
        def characteristic_callback(sender: int, databytes: bytearray):
            """Handle callback on changes to characteristics."""
            device.characteristic_callback(databytes)
            coordinator.async_set_updated_data(device.state)

        entry.async_on_unload(
            async_dispatcher_connect(hass, DISPATCH_DETECTION, detection_callback)
        )

        if device.tx_char:
            await client.start_notify(device.rx_char, characteristic_callback)
        else:
            _LOGGER.debug("Unable to find tx characteristics, skipping notify")

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = EntryState(
            scanner, client, device, coordinator
        )

        await coordinator.async_config_entry_first_refresh()

        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    except Exception:
        await scanner.stop()
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entrystate: EntryState = hass.data[DOMAIN].pop(entry.entry_id)
        await entrystate.client.stop_notify(entrystate.device.tx_char)
        await entrystate.client.disconnect()
        await entrystate.scanner.stop()

    return unload_ok
