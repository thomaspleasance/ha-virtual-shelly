"""Switch entities for Virtual Shelly."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CHANNEL_COUNT, DEVICE_ID, DEVICE_MODEL, DOMAIN, VERSION
from .device import VirtualShellyPro4PM


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up four relay entities."""
    device: VirtualShellyPro4PM = hass.data[DOMAIN]
    async_add_entities(VirtualShellySwitch(device, channel) for channel in range(CHANNEL_COUNT))


class VirtualShellySwitch(SwitchEntity):
    """Represent one relay on the virtual device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: VirtualShellyPro4PM, channel: int) -> None:
        self._device = device
        self._channel = channel
        self._attr_name = f"Channel {channel + 1}"
        self._attr_unique_id = f"{DEVICE_ID}-switch-{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DEVICE_ID)},
            name=device.name,
            manufacturer="Shelly (virtual)",
            model=DEVICE_MODEL,
            sw_version=VERSION,
        )
        self._remove_listener = None

    @property
    def is_on(self) -> bool:
        """Return whether this relay is on."""
        return self._device.states[self._channel]

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the relay."""
        self._device.set_output(self._channel, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the relay."""
        self._device.set_output(self._channel, False)

    async def async_added_to_hass(self) -> None:
        """Subscribe to state changes made through the RPC server."""
        self._remove_listener = self._device.add_listener(self._handle_state_change)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from shared state updates."""
        if self._remove_listener is not None:
            self._remove_listener()

    def _handle_state_change(self, channel: int) -> None:
        if channel == self._channel:
            self.async_write_ha_state()
