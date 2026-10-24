"""Constants for Virtual Shelly."""

DOMAIN = "virtual_shelly"
VERSION = "0.4.0"
CONF_HOST = "host"
CONF_MAC = "mac"
CONF_NAME = "name"
CONF_PORT = "port"
CONF_POWER_ENTITIES = "power_entities"
CONF_ENERGY_ENTITIES = "energy_entities"
CONF_ENABLE_DIAGNOSTICS = "enable_diagnostics"
DEFAULT_NAME = "Virtual Shelly Pro 4PM"
DEFAULT_PORT = 8124
CHANNEL_COUNT = 4
DEVICE_ID_PREFIX = "shellypro4pm-"
LEGACY_MAC = "020000000001"
DEVICE_MODEL = "Shelly Pro 4PM"
DEVICE_MODEL_ID = "SPSW-004PE16EU"
ALL_ADDRESSES = "0.0.0.0"
MDNS_SERVICE_TYPES = ("_shelly._tcp.local.", "_http._tcp.local.")
