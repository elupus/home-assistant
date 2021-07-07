"""Device communication library."""

from dataclasses import dataclass, replace
import logging
from uuid import UUID

from bleak import BleakClient
from bleak.backends.scanner import AdvertisementData

COMMAND_FORMAT_FAN_SPEED_FORMAT = "-Luft-%01d-"
COMMAND_FORMAT_DIM = "-Dim%03d-"
COMMAND_FORMAT_PERIODIC_VENTING = "Period%02d"

COMMAND_STOP_FAN = "Luft-Aus"
COMMAND_LIGHT_ON_OFF = "Kochfeld"
COMMAND_RESETGREASEFILTER = "ResFett-"
COMMAND_RESETCHARCOALFILTER = "ResKohle"
COMMAND_AFTERCOOKINGTIMERMANUAL = "Nachlauf"
COMMAND_AFTERCOOKINGTIMERAUTO = "NachlAut"
COMMAND_AFTERCOOKINGSTRENGTHMANUAL = "Nachla-"
COMMAND_AFTERCOOKINGTIMEROFF = "NachlAus"
COMMAND_ACTIVATECARBONFILTER = "coal-ava"

_LOGGER = logging.getLogger(__name__)

UUID_SERVICE = UUID("{77a2bd49-1e5a-4961-bba1-21f34fa4bc7b}")
UUID_RX = UUID("{23123e0a-1ad6-43a6-96ac-06f57995330d}")
UUID_TX = UUID("{68ecc82c-928d-4af0-aa60-0d578ffb35f7}")
UUID_CONFIG = UUID("{3e06fdc2-f432-404f-b321-dfa909f5c12c}")

DEVICE_NAME = "COOKERHOOD_FJAR"
ANNOUNCE_PREFIX = b"HOODFJAR"

MANUFACTURER_ID1 = 12849
MANUFACTURER_ID2 = 20296


@dataclass
class State:
    """Data received from characteristics."""

    light_on: bool = False
    after_venting_fan_speed: int = 0
    after_venting_on: bool = False
    carbon_filter_available: bool = False
    fan_speed: int = 0
    grease_filter_full: bool = False
    carbon_filter_full: bool = False
    dim_level: int = 0
    periodic_venting: int = 0
    periodic_venting_on: bool = False

    def replace_from_tx_char(self, databytes: bytes):
        """Update state based on tx characteristics."""
        data = databytes.decode("ASCII")
        return replace(
            self,
            fan_speed=int(data[4]),
            light_on=data[5] == "L",
            after_venting_on=data[6] == "N",
            carbon_filter_available=data[7] == "C",
            grease_filter_full=data[8] == "F",
            carbon_filter_full=data[9] == "K",
            dim_level=_range_check_dim(int(data[10:13]), self.dim_level),
            periodic_venting=_range_check_period(
                int(data[13:14]), self.periodic_venting
            ),
        )

    def replace_from_manufacture_data(self, data: bytes):
        """Update state based on broadcasted data."""
        return replace(
            self,
            fan_speed=int(data[8]),
            after_venting_fan_speed=int(data[9]),
            light_on=_bittest(data[10], 0),
            after_venting_on=_bittest(data[10], 1),
            peridic_venting_on=_bittest(data[10], 2),
            grease_filter_full=_bittest(data[11], 0),
            carbon_filter_full=_bittest(data[11], 1),
            carbon_filter_available=_bittest(data[11], 2),
            dim_level=_range_check_dim(data[13], self.dim_level),
            periodic_venting=_range_check_period(data[14], self.periodic_venting),
        )


def _range_check_dim(value: int, fallback: int):
    if value >= 0 and value <= 100:
        return value
    else:
        return fallback


def _range_check_period(value: int, fallback: int):
    if value >= 0 and value < 60:
        return value
    else:
        return fallback


def _bittest(data: int, bit: int):
    return (data & (1 << bit)) != 0


class Device:
    """Communication handler."""

    def __init__(self, client: BleakClient, keycode=b"1234") -> None:
        """Initialize handler."""
        self.client = client
        self.tx_char = client.services.get_characteristic(UUID_TX)
        self.rx_char = client.services.get_characteristic(UUID_RX)
        self.config_char = client.services.get_characteristic(UUID_CONFIG)
        self._keycode = keycode
        self.state = State()

    async def characteristic_callback(self, data: bytearray):
        """Handle callback on characteristic change."""
        _LOGGER.debug("Characteristic callback: %s", data)

        if data[0:4] != self._keycode:
            _LOGGER.warning("Wrong keycode in data %s", data)
            return

        self.state = self.state.replace_from_tx_char(data)

        _LOGGER.debug("Characteristic callback result: %s", self.state)

    async def detection_callback(self, advertisement_data: AdvertisementData):
        """Handle scanner data."""

        data = advertisement_data.manufacturer_data.get(MANUFACTURER_ID1)
        if data is None:
            data = advertisement_data.manufacturer_data.get(MANUFACTURER_ID2)

        if data is None:
            _LOGGER.warning(
                "Missing manufacturer data in advertisement %s", advertisement_data
            )
            return

        if data[0:8] != ANNOUNCE_PREFIX:
            _LOGGER.debug("Missing key in manufacturer data %s", data)
            return

        self.state = self.state.replace_from_manufacture_data(data)

        _LOGGER.debug("Detection callback result: %s", self.state)

    async def send_command(self, cmd):
        """Send given command."""
        data: str = self._keycode + cmd
        await self.client.write_gatt_char(self.rx_char, data.encode("ASCII"), True)

    async def send_fan_speed(self, speed: int):
        """Set numbered fan speed."""
        await self.send_command(COMMAND_FORMAT_FAN_SPEED_FORMAT.format(speed))

    async def send_periodic_venting(self, period: int):
        """Set periodic venting."""
        await self.send_command(COMMAND_FORMAT_PERIODIC_VENTING.format(period))

    async def send_dim(self, level: int):
        """Ask to dim to a certain level."""
        await self.send_command(COMMAND_FORMAT_DIM.format(level))
