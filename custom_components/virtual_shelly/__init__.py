"""Virtual Shelly integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PORT, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .device import VirtualShellyPro4PM
from .mdns import ShellyMdnsAdvertiser
from .server import ShellyRpcServer

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("name", default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Virtual Shelly from YAML."""
    integration_config = config[DOMAIN]
    device = VirtualShellyPro4PM(integration_config["name"])
    server = ShellyRpcServer(device, integration_config[CONF_PORT])
    advertiser = ShellyMdnsAdvertiser(hass, integration_config[CONF_PORT])

    try:
        await server.async_start()
        await advertiser.async_start()
    except Exception:
        await advertiser.async_stop()
        await server.async_stop()
        raise
    hass.data[DOMAIN] = device

    async def _async_stop(_event: Event) -> None:
        await advertiser.async_stop()
        await server.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    await async_load_platform(hass, "switch", DOMAIN, {}, config)

    _LOGGER.info(
        "Virtual Shelly Pro 4PM is listening on port %s and advertising via mDNS",
        integration_config[CONF_PORT],
    )
    return True
