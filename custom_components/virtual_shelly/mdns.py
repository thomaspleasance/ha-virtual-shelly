"""mDNS advertising for the virtual Shelly device."""

from __future__ import annotations

from ipaddress import ip_address

from homeassistant.components import network
from homeassistant.components.zeroconf import async_get_async_instance
from homeassistant.core import HomeAssistant
from zeroconf.asyncio import AsyncServiceInfo

from .const import (
    ALL_ADDRESSES,
    DEVICE_MODEL_ID,
    MDNS_SERVICE_TYPES,
)


class ShellyMdnsAdvertiser:
    """Publish Shelly Gen2-compatible Bonjour records."""

    def __init__(
        self, hass: HomeAssistant, device_id: str, mac: str, host: str, port: int
    ) -> None:
        self._hass = hass
        self._device_id = device_id
        self._mac = mac
        self._host = host
        self._port = port
        self._aio_zeroconf = None
        self._services: list[AsyncServiceInfo] = []

    async def async_start(self) -> None:
        """Register the virtual device's mDNS services."""
        if self._host == ALL_ADDRESSES:
            addresses = [
                address
                for address in await network.async_get_announce_addresses(self._hass)
                if ip_address(address.split("%", 1)[0]).version == 4
            ]
            if not addresses:
                raise RuntimeError(
                    "Virtual Shelly requires an IPv4 address for discovery"
                )
        else:
            addresses = [self._host]
        properties = {
            "gen": "2",
            "id": self._device_id,
            "mac": self._mac,
            "app": "FourPro",
            "model": DEVICE_MODEL_ID,
        }
        server = f"{self._device_id}.local."
        self._aio_zeroconf = await async_get_async_instance(self._hass)

        for service_type in MDNS_SERVICE_TYPES:
            service = AsyncServiceInfo(
                service_type,
                name=f"{self._device_id}.{service_type}",
                server=server,
                parsed_addresses=addresses,
                port=self._port,
                properties=properties,
            )
            await self._aio_zeroconf.async_register_service(
                service, allow_name_change=False
            )
            self._services.append(service)

    async def async_stop(self) -> None:
        """Send goodbye packets and unregister all mDNS services."""
        if self._aio_zeroconf is None:
            return
        for service in reversed(self._services):
            await self._aio_zeroconf.async_unregister_service(service)
        self._services.clear()
        self._aio_zeroconf = None
