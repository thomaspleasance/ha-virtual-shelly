"""Config flow for Virtual Shelly."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    ALL_ADDRESSES,
    CHANNEL_COUNT,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENERGY_ENTITIES,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_POWER_ENTITIES,
    DEFAULT_NAME,
    DOMAIN,
    LEGACY_MAC,
)
from .device import device_id_for_mac, next_mac
from .helpers import async_get_ipv4_addresses

UI_DEFAULT_PORT = 80


def _power_key(channel: int) -> str:
    return f"power_entity_{channel}"


def _energy_key(channel: int) -> str:
    return f"energy_entity_{channel}"


def _valid_ipv4(value: Any) -> bool:
    """Return True if the value is an IPv4 address."""
    try:
        return ip_address(value).version == 4
    except ValueError:
        return False


def _schema(settings: dict[str, Any], addresses: list[str]) -> vol.Schema:
    """Build the user/options form schema."""
    power_entities = settings.get(CONF_POWER_ENTITIES, {})
    energy_entities = settings.get(CONF_ENERGY_ENTITIES, {})
    fields: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_NAME,
            description={"suggested_value": settings.get(CONF_NAME, DEFAULT_NAME)},
        ): str,
        vol.Required(
            CONF_HOST,
            description={
                "suggested_value": settings.get(CONF_HOST)
                or (addresses[0] if addresses else ALL_ADDRESSES)
            },
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    *(
                        selector.SelectOptionDict(value=address, label=address)
                        for address in addresses
                    ),
                    selector.SelectOptionDict(
                        value=ALL_ADDRESSES, label="0.0.0.0 (all addresses)"
                    ),
                ],
                custom_value=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_PORT,
            description={"suggested_value": settings.get(CONF_PORT, UI_DEFAULT_PORT)},
        ): cv.port,
        vol.Required(
            CONF_ENABLE_DIAGNOSTICS,
            default=settings.get(CONF_ENABLE_DIAGNOSTICS, False),
        ): bool,
    }
    for channel in range(1, CHANNEL_COUNT + 1):
        entity_id = power_entities.get(channel) or power_entities.get(str(channel))
        marker = vol.Optional(_power_key(channel))
        if entity_id:
            marker = vol.Optional(
                _power_key(channel), description={"suggested_value": entity_id}
            )
        fields[marker] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        energy_entity_id = energy_entities.get(channel) or energy_entities.get(
            str(channel)
        )
        energy_marker = vol.Optional(_energy_key(channel))
        if energy_entity_id:
            energy_marker = vol.Optional(
                _energy_key(channel),
                description={"suggested_value": energy_entity_id},
            )
        fields[energy_marker] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
    return vol.Schema(fields)


async def _async_used_endpoints(
    hass, exclude_entry_id: str | None
) -> list[tuple[str, int]]:
    """Return (host, port) endpoints already used by other config entries."""
    endpoints = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id:
            continue
        settings = {**entry.data, **entry.options}
        host = settings.get(CONF_HOST, ALL_ADDRESSES)
        endpoints.append((host, settings[CONF_PORT]))
    return endpoints


def _endpoint_conflicts(host: str, port: int, used: list[tuple[str, int]]) -> bool:
    """Return True if (host, port) overlaps an endpoint already in use."""
    return any(
        port == used_port and (host == used_host or ALL_ADDRESSES in (host, used_host))
        for used_host, used_port in used
    )


def _settings_from_form(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert flat UI fields to runtime settings."""
    return {
        CONF_NAME: user_input[CONF_NAME],
        CONF_HOST: user_input[CONF_HOST],
        CONF_PORT: user_input[CONF_PORT],
        CONF_ENABLE_DIAGNOSTICS: user_input[CONF_ENABLE_DIAGNOSTICS],
        CONF_POWER_ENTITIES: {
            channel: entity_id
            for channel in range(1, CHANNEL_COUNT + 1)
            if (entity_id := user_input.get(_power_key(channel)))
        },
        CONF_ENERGY_ENTITIES: {
            channel: entity_id
            for channel in range(1, CHANNEL_COUNT + 1)
            if (entity_id := user_input.get(_energy_key(channel)))
        },
    }


def _settings_from_import(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy YAML settings."""
    settings = {
        CONF_NAME: data.get(CONF_NAME, DEFAULT_NAME),
        CONF_PORT: data.get(CONF_PORT, UI_DEFAULT_PORT),
        CONF_ENABLE_DIAGNOSTICS: data.get(CONF_ENABLE_DIAGNOSTICS, False),
        CONF_POWER_ENTITIES: {
            int(channel): entity_id
            for channel, entity_id in data.get(CONF_POWER_ENTITIES, {}).items()
        },
        CONF_ENERGY_ENTITIES: {
            int(channel): entity_id
            for channel, entity_id in data.get(CONF_ENERGY_ENTITIES, {}).items()
        },
    }
    settings[CONF_HOST] = data.get(CONF_HOST, ALL_ADDRESSES)
    settings[CONF_MAC] = data.get(CONF_MAC, LEGACY_MAC)
    return settings


class VirtualShellyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Virtual Shelly config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create a virtual Pro 4PM."""
        existing = self._async_current_entries(include_ignore=False)
        addresses = await async_get_ipv4_addresses(self.hass)
        used = await _async_used_endpoints(self.hass, None)
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _valid_ipv4(user_input.get(CONF_HOST)):
                errors[CONF_HOST] = "invalid_host"
            elif _endpoint_conflicts(
                user_input[CONF_HOST], user_input[CONF_PORT], used
            ):
                errors[CONF_HOST] = "address_in_use"
            else:
                settings = _settings_from_form(user_input)
                mac = next_mac(
                    entry.data.get(CONF_MAC, LEGACY_MAC) for entry in existing
                )
                await self.async_set_unique_id(device_id_for_mac(mac))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=settings[CONF_NAME],
                    data={**settings, CONF_MAC: mac},
                )
        if user_input:
            form_settings = _settings_from_form(user_input)
        else:
            used_hosts = {host for host, _ in used}
            suggested_host = next(
                (
                    address
                    for address in addresses
                    if address not in used_hosts
                    and ALL_ADDRESSES not in used_hosts
                ),
                addresses[0] if addresses else ALL_ADDRESSES,
            )
            suggested_name = (
                DEFAULT_NAME
                if not existing
                else f"{DEFAULT_NAME} {len(existing) + 1}"
            )
            form_settings = {
                CONF_NAME: suggested_name,
                CONF_HOST: suggested_host,
            }
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(form_settings, addresses),
            errors=errors,
        )

    async def async_step_import(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Import the existing YAML configuration."""
        settings = _settings_from_import(user_input)
        await self.async_set_unique_id(device_id_for_mac(LEGACY_MAC))
        self._abort_if_unique_id_configured(updates=settings)
        return self.async_create_entry(title=settings[CONF_NAME], data=settings)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return VirtualShellyOptionsFlow()


class VirtualShellyOptionsFlow(config_entries.OptionsFlowWithReload):
    """Edit Virtual Shelly settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show editable device and channel settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _valid_ipv4(user_input.get(CONF_HOST)):
                errors[CONF_HOST] = "invalid_host"
            else:
                used = await _async_used_endpoints(
                    self.hass, self.config_entry.entry_id
                )
                if _endpoint_conflicts(
                    user_input[CONF_HOST], user_input[CONF_PORT], used
                ):
                    errors[CONF_HOST] = "address_in_use"
                else:
                    return self.async_create_entry(
                        data=_settings_from_form(user_input)
                    )
        settings = {**self.config_entry.data, **self.config_entry.options}
        addresses = await async_get_ipv4_addresses(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                _settings_from_form(user_input) if user_input else settings,
                addresses,
            ),
            errors=errors,
        )
