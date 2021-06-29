"""Device communication library."""

from dataclasses import dataclass
import logging
from uuid import UUID

from bleak import BleakClient

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


@dataclass
class CharacteristicCallbackData:
    """Data received from characteristics."""

    light_on: bool
    after_venting_on: bool
    carbon_filter_available: bool
    fan_speed: int
    grease_filter_full: bool
    carbon_filter_full: bool
    dim_level: int
    periodic_venting: int


def parse_tx_characteristics_v1(data: str):
    """Parse characteristics as android app."""

    return CharacteristicCallbackData(
        fan_speed=int(data[4]),
        light_on=data[5] == "L",
        after_venting_on=data[6] == "N",
        carbon_filter_available=data[7] == "C",
        grease_filter_full=data[8] == "F",
        carbon_filter_full=data[9] == "K",
        dim_level=int(data[10:13]),
        periodic_venting=int(data[13:14]),
    )


class Device:
    """Communication handler."""

    def __init__(self, client: BleakClient) -> None:
        """Initialize handler."""
        self.client = client
        self._tx_char = client.services.get_characteristic(UUID_TX)
        self._rx_char = client.services.get_characteristic(UUID_RX)
        self._keycode = "1234"

    async def _callback(self, sender: int, databytes: bytearray):
        """Handle callback on characteristic change."""
        _LOGGER.debug("Characteristic callback: %s", databytes)

        data = databytes.decode("ASCII")
        assert len(data) == 15
        assert data[0:4] == self._keycode

        result = parse_tx_characteristics_v1(data)

        _LOGGER.info("Characteristic callback result: %s", result)

    async def start(self):
        """Start listening for broadcasts."""
        await self.client.start_notify(self._tx_char, self._callback)

    async def stop(self):
        """Stop listening for broadcasts."""
        await self.client.stop_notify(self._tx_char)

    async def send_command(self, cmd):
        """Send given command."""
        data: str = self._keycode + cmd
        await self.client.write_gatt_char(self._rx_char, data.encode("ASCII"), True)

    async def send_fan_speed(self, speed: int):
        """Set numbered fan speed."""
        await self.send_command(COMMAND_FORMAT_FAN_SPEED_FORMAT.format(speed))

    async def send_periodic_venting(self, period: int):
        """Set periodic venting."""
        await self.send_command(COMMAND_FORMAT_PERIODIC_VENTING.format(period))

    async def send_dim(self, level: int):
        """Ask to dim to a certain level."""
        await self.send_command(COMMAND_FORMAT_DIM.format(level))
