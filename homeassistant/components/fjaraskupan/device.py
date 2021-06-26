"""Device communication library."""

from dataclasses import dataclass
from enum import IntEnum
import logging

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


class CharacteristicCallbackEnum(IntEnum):
    """Enumeration for data fields on characteristic callback."""

    KEY_1 = 0
    KEY_2 = 1
    KEY_3 = 2
    KEY_4 = 3
    FANSTAGE = 4
    LIGHT = 5
    AFTER_COOKING_TIMER = 6
    CARBON_FILTER_AVAILABLE = 7
    GREASE_FILTER_SATURATION = 8
    CARBON_FILTER_SATURATION = 9
    DIMMER_1 = 10
    DIMMER_2 = 11
    DIMMER_3 = 12
    PERIOD_HI = 13
    PERIOD_LO = 14


@dataclass
class CharacteristicCallbackData:
    """Data received from characteristics."""

    light_on: bool
    after_venting_on: bool
    carbon_filter_available: bool
    fan_speed: int
    grease_filter_full: bool
    dim_level: int
    periodic_venting: int


class Device:
    """Communication handler."""

    def __init__(self, client: BleakClient) -> None:
        """Initialize handler."""
        self.client = client
        self._characteristics = 0x000B
        self._keycode = "1234"

    async def _callback(self, sender: int, databytes: bytearray):
        """Handle callback on characteristic change."""
        _LOGGER.debug("Characteristic callback: %s", databytes)

        data = databytes.decode("ASCII")
        assert len(data) == 15
        assert data[0:4] == self._keycode

        result = CharacteristicCallbackData(
            light_on=data[CharacteristicCallbackEnum.LIGHT] == "L",
            after_venting_on=data[CharacteristicCallbackEnum.AFTER_COOKING_TIMER]
            == "N",
            carbon_filter_available=data[
                CharacteristicCallbackEnum.CARBON_FILTER_AVAILABLE
            ]
            == "C",
            fan_speed=int(data[CharacteristicCallbackEnum.FANSTAGE]),
            grease_filter_full=data[CharacteristicCallbackEnum.GREASE_FILTER_SATURATION]
            != "F",
            dim_level=int(
                data[
                    CharacteristicCallbackEnum.DIMMER_1 : CharacteristicCallbackEnum.DIMMER_3
                    + 1
                ]
            ),
            periodic_venting=int(
                data[
                    CharacteristicCallbackEnum.PERIOD_HI : CharacteristicCallbackEnum.PERIOD_LO
                ]
            ),
        )

        _LOGGER.info("Characteristic callback result: %s", result)

    async def start(self):
        """Start listening for broadcasts."""
        await self.client.start_notify(self._characteristics, self._callback)

    async def stop(self):
        """Stop listening for broadcasts."""
        await self.client.stop_notify(self._characteristics)

    async def send_command(self, cmd):
        """Send a given command."""
        data: str = self._keycode + cmd
        await self.client.write_gatt_char(
            self._characteristics, data.encode("ASCII"), True
        )

    async def send_fan_speed(self, speed: int):
        """Set a numbered fan speed."""
        await self.send_command(COMMAND_FORMAT_FAN_SPEED_FORMAT.format(speed))

    async def send_periodic_venting(self, period: int):
        """Set a periodic venting."""
        await self.send_command(COMMAND_FORMAT_PERIODIC_VENTING.format(period))

    async def send_dim(self, level: int):
        """Ask to dim to a certain level."""
        await self.send_command(COMMAND_FORMAT_DIM.format(level))
