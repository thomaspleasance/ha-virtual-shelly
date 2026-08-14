"""Config flow for Virtual Shelly."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CHANNEL_COUNT,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_NAME,
    CONF_PORT,
    CONF_POWER_ENTITIES,
    DEFAULT_NAME,
    DEVICE_ID,
    DOMAIN,
)

UI_DEFAULT_PORT = 80


def _power_key(channel: int) -> str:
    return f"power_entity_{channel}"


def _schema(settings: dict[str, Any]) -> vol.Schema:
    """Build the user/options form schema."""
    power_entities = settings.get(CONF_POWER_ENTITIES, {})
    fields: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_NAME,
            description={"suggested_value": settings.get(CONF_NAME, DEFAULT_NAME)},
        ): str,
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
    return vol.Schema(fields)


def _settings_from_form(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert flat UI fields to runtime settings."""
    return {
        CONF_NAME: user_input[CONF_NAME],
        CONF_PORT: user_input[CONF_PORT],
        CONF_ENABLE_DIAGNOSTICS: user_input[CONF_ENABLE_DIAGNOSTICS],
        CONF_POWER_ENTITIES: {
            channel: entity_id
            for channel in range(1, CHANNEL_COUNT + 1)
            if (entity_id := user_input.get(_power_key(channel)))
        },
    }


def _settings_from_import(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy YAML settings."""
    return {
        CONF_NAME: data.get(CONF_NAME, DEFAULT_NAME),
        CONF_PORT: data.get(CONF_PORT, UI_DEFAULT_PORT),
        CONF_ENABLE_DIAGNOSTICS: data.get(CONF_ENABLE_DIAGNOSTICS, False),
        CONF_POWER_ENTITIES: {
            int(channel): entity_id
            for channel, entity_id in data.get(CONF_POWER_ENTITIES, {}).items()
        },
    }


class VirtualShellyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Virtual Shelly config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the single virtual Pro 4PM."""
        await self.async_set_unique_id(DEVICE_ID)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            settings = _settings_from_form(user_input)
            return self.async_create_entry(title=settings[CONF_NAME], data=settings)
        return self.async_show_form(step_id="user", data_schema=_schema({}))

    async def async_step_import(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Import the existing YAML configuration."""
        settings = _settings_from_import(user_input)
        await self.async_set_unique_id(DEVICE_ID)
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
        if user_input is not None:
            return self.async_create_entry(data=_settings_from_form(user_input))
        settings = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(settings))
