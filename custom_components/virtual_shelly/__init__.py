"""Virtual Shelly integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PORT, CONF_POWER_ENTITIES, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
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
                vol.Optional(CONF_POWER_ENTITIES, default={}): {
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=4)): cv.entity_id,
                },
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Virtual Shelly from YAML."""
    integration_config = config[DOMAIN]
    power_entities = integration_config[CONF_POWER_ENTITIES]

    def _read_power(channel: int) -> float:
        entity_id = power_entities.get(channel + 1)
        state = hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in {"unknown", "unavailable"}:
            return 0.0
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return 0.0
        unit = state.attributes.get("unit_of_measurement")
        multipliers = {
            "mW": 0.001,
            "W": 1.0,
            "kW": 1000.0,
            "MW": 1_000_000.0,
        }
        return round(value * multipliers.get(unit, 1.0), 3)

    device = VirtualShellyPro4PM(integration_config["name"], _read_power)
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
