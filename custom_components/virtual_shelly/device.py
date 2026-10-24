"""Shared state for a virtual Shelly Pro 4PM."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .const import (
    CHANNEL_COUNT,
    DEVICE_ID_PREFIX,
    DEVICE_MODEL_ID,
    LEGACY_MAC,
    VERSION,
)

StateListener = Callable[[int], None]
PowerReader = Callable[[int], float]
EnergyReader = Callable[[int], float]


def device_id_for_mac(mac: str) -> str:
    """Return the Shelly device id for a MAC address."""
    return f"{DEVICE_ID_PREFIX}{mac.lower()}"


def next_mac(existing: Iterable[str]) -> str:
    """Return the next unused MAC address after the highest existing one."""
    ints = []
    for mac in existing:
        try:
            ints.append(int(mac, 16))
        except (TypeError, ValueError):
            continue
    return f"{max(ints, default=int(LEGACY_MAC, 16) - 1) + 1:012X}"


class VirtualShellyPro4PM:
    """Represent the four relay outputs of a Shelly Pro 4PM."""

    def __init__(
        self,
        name: str,
        mac: str,
        power_reader: PowerReader | None = None,
        energy_reader: EnergyReader | None = None,
    ) -> None:
        self.name = name
        self.mac = mac.upper()
        self.device_id = device_id_for_mac(mac)
        self.states = [False] * CHANNEL_COUNT
        self._power_reader = power_reader or (lambda _channel: 0.0)
        self._energy_reader = energy_reader or (lambda _channel: 0.0)
        self._listeners: set[StateListener] = set()

    def add_listener(self, listener: StateListener) -> Callable[[], None]:
        """Register a state listener and return its unsubscribe callback."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def set_output(self, channel: int, state: bool) -> bool:
        """Set an output and return its previous state."""
        self._validate_channel(channel)
        previous = self.states[channel]
        self.states[channel] = state
        if previous != state:
            for listener in tuple(self._listeners):
                listener(channel)
        return previous

    def toggle_output(self, channel: int) -> bool:
        """Toggle an output and return its previous state."""
        return self.set_output(channel, not self.states[channel])

    def switch_status(self, channel: int) -> dict:
        """Return a Shelly-compatible switch status object."""
        self._validate_channel(channel)
        return {
            "id": channel,
            "source": "http",
            "output": self.states[channel],
            "apower": self._power_reader(channel),
            "voltage": 230.0,
            "current": 0.0,
            "freq": 50.0,
            "aenergy": {
                "total": self._energy_reader(channel),
                "by_minute": [0.0, 0.0, 0.0],
            },
            "temperature": {"tC": 25.0, "tF": 77.0},
        }

    def device_info(self) -> dict:
        """Return the Gen2 device-information response."""
        return {
            "id": self.device_id,
            "mac": self.mac,
            "model": DEVICE_MODEL_ID,
            "gen": 2,
            "fw_id": f"virtual-{VERSION}",
            "ver": VERSION,
            "app": "FourPro",
            "auth_en": False,
            "auth_domain": None,
            "discoverable": False,
            "enhanced_security": False,
        }

    @staticmethod
    def _validate_channel(channel: int) -> None:
        if not 0 <= channel < CHANNEL_COUNT:
            raise ValueError(f"Switch id must be between 0 and {CHANNEL_COUNT - 1}")
