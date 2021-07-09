"""The Fjäråskupan integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DISPATCH_DETECTION, DOMAIN
from .device import DEVICE_NAME, Device, State

PLATFORMS = ["fan", "light", "binary_sensor"]

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntryState:
    """Store state of config entry."""

    scanner: BleakScanner
    device: Device
    coordinator: DataUpdateCoordinator[State]
    device_info: DeviceInfo


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
    address: str = entry.data["address"]
    ble_device = await BleakScanner.find_device_by_address(address)
    if ble_device is None:
        raise ConfigEntryNotReady("Can't find device")

    scanner = await async_startup_scanner(hass)
    try:
        device = Device(ble_device)

        async def async_update_data():
            """Handle an explicit update request."""
            await device.update()
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

        entry.async_on_unload(
            async_dispatcher_connect(hass, DISPATCH_DETECTION, detection_callback)
        )

        await coordinator.async_config_entry_first_refresh()

        device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, address)},
            "manufacturer": "Fjäråskupan",
            "name": "Fjäråskupan",
        }

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = EntryState(
            scanner, device, coordinator, device_info
        )

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
        await entrystate.scanner.stop()

    return unload_ok
