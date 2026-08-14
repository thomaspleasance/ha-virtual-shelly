"""Shared state for a virtual Shelly Pro 4PM."""

from __future__ import annotations

from collections.abc import Callable

from .const import CHANNEL_COUNT, DEVICE_ID, DEVICE_MAC, DEVICE_MODEL_ID, VERSION

StateListener = Callable[[int], None]


class VirtualShellyPro4PM:
    """Represent the four relay outputs of a Shelly Pro 4PM."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.states = [False] * CHANNEL_COUNT
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
            "apower": 0.0,
            "voltage": 230.0,
            "current": 0.0,
            "freq": 50.0,
            "aenergy": {"total": 0.0, "by_minute": [0.0, 0.0, 0.0]},
            "temperature": {"tC": 25.0, "tF": 77.0},
        }

    def device_info(self) -> dict:
        """Return the Gen2 device-information response."""
        return {
            "id": DEVICE_ID,
            "mac": DEVICE_MAC,
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
