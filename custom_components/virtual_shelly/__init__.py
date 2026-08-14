"""Virtual Shelly integration."""

from __future__ import annotations

from dataclasses import dataclass

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CHANNEL_COUNT,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_NAME,
    CONF_PORT,
    CONF_POWER_ENTITIES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from .device import VirtualShellyPro4PM
from .mdns import ShellyMdnsAdvertiser
from .server import ShellyRpcServer

PLATFORMS = [Platform.SWITCH]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_ENABLE_DIAGNOSTICS, default=False): cv.boolean,
                vol.Optional(CONF_POWER_ENTITIES, default={}): {
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=CHANNEL_COUNT)): cv.entity_id,
                },
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class VirtualShellyRuntimeData:
    """Runtime objects owned by one config entry."""

    device: VirtualShellyPro4PM
    server: ShellyRpcServer
    advertiser: ShellyMdnsAdvertiser


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import a legacy YAML configuration into the UI."""
    if legacy_config := config.get(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=dict(legacy_config),
            )
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[VirtualShellyRuntimeData]
) -> bool:
    """Set up Virtual Shelly from a config entry."""
    settings = {**entry.data, **entry.options}
    power_entities = {
        int(channel): entity_id
        for channel, entity_id in settings.get(CONF_POWER_ENTITIES, {}).items()
    }

    def _read_power(channel: int) -> float:
        entity_id = power_entities.get(channel + 1)
        state = hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in {"unknown", "unavailable"}:
            return 0.0
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return 0.0
        multipliers = {
            "mW": 0.001,
            "W": 1.0,
            "kW": 1000.0,
            "MW": 1_000_000.0,
        }
        unit = state.attributes.get("unit_of_measurement")
        return round(value * multipliers.get(unit, 1.0), 3)

    device = VirtualShellyPro4PM(settings[CONF_NAME], _read_power)
    server = ShellyRpcServer(
        device,
        settings[CONF_PORT],
        settings.get(CONF_ENABLE_DIAGNOSTICS, False),
    )
    advertiser = ShellyMdnsAdvertiser(hass, settings[CONF_PORT])

    try:
        await server.async_start()
        await advertiser.async_start()
    except Exception:
        await advertiser.async_stop()
        await server.async_stop()
        raise

    entry.runtime_data = VirtualShellyRuntimeData(device, server, advertiser)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[VirtualShellyRuntimeData]
) -> bool:
    """Unload a Virtual Shelly config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.advertiser.async_stop()
    await entry.runtime_data.server.async_stop()
    return True
