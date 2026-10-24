"""Helpers for Virtual Shelly."""

from __future__ import annotations

from ipaddress import ip_address

from homeassistant.components import network
from homeassistant.core import HomeAssistant


async def async_get_ipv4_addresses(hass: HomeAssistant) -> list[str]:
    """Return deduplicated non-loopback IPv4 addresses of this host."""
    addresses: list[str] = []
    for address in await network.async_get_announce_addresses(hass):
        parsed = ip_address(address.split("%", 1)[0])
        if parsed.version == 4 and not parsed.is_loopback:
            addresses.append(str(parsed))
    for adapter in await network.async_get_adapters(hass):
        for ipv4 in adapter["ipv4"]:
            parsed = ip_address(ipv4["address"])
            if parsed.version == 4 and not parsed.is_loopback:
                addresses.append(str(parsed))
    return list(dict.fromkeys(addresses))


async def async_get_default_host(hass: HomeAssistant) -> str | None:
    """Return the primary IPv4 address, or None if the host has none."""
    addresses = await async_get_ipv4_addresses(hass)
    return addresses[0] if addresses else None
