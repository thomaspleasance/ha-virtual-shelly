"""Minimal Shelly Gen2-compatible HTTP/RPC server."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from .const import CHANNEL_COUNT, DEVICE_ID
from .device import VirtualShellyPro4PM

_LOGGER = logging.getLogger(__name__)


class RpcError(Exception):
    """Represent a Shelly RPC error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ShellyRpcServer:
    """Serve the subset of Shelly RPC needed for four relay channels."""

    def __init__(self, device: VirtualShellyPro4PM, port: int) -> None:
        self._device = device
        self._port = port
        self._runner: web.AppRunner | None = None

    async def async_start(self) -> None:
        """Start listening for HTTP requests."""
        app = web.Application()
        app.router.add_get("/shelly", self._handle_device_info)
        app.router.add_post("/rpc", self._handle_rpc_frame)
        app.router.add_get("/rpc/{method}", self._handle_method)
        app.router.add_post("/rpc/{method}", self._handle_method)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self._port).start()

    async def async_stop(self) -> None:
        """Stop the HTTP server."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _handle_device_info(self, request: web.Request) -> web.Response:
        self._log_request(request, "/shelly")
        return web.json_response(self._device.device_info())

    async def _handle_rpc_frame(self, request: web.Request) -> web.Response:
        try:
            frame = await request.json()
            request_id = frame.get("id")
            self._log_request(request, frame.get("method"))
            result = self._dispatch(
                frame.get("method"),
                frame.get("params", {}),
                self._local_ip(request),
            )
            return web.json_response(
                {"id": request_id, "src": DEVICE_ID, "result": result}
            )
        except RpcError as err:
            return web.json_response(
                {
                    "id": frame.get("id") if "frame" in locals() else None,
                    "src": DEVICE_ID,
                    "error": {"code": err.code, "message": err.message},
                }
            )
        except (ValueError, TypeError, web.HTTPBadRequest) as err:
            return web.json_response(
                {"id": None, "src": DEVICE_ID, "error": {"code": -103, "message": str(err)}}
            )

    async def _handle_method(self, request: web.Request) -> web.Response:
        try:
            self._log_request(request, request.match_info["method"])
            if request.method == "POST":
                params = await request.json() if request.can_read_body else {}
            else:
                params = dict(request.query)
            return web.json_response(
                self._dispatch(
                    request.match_info["method"], params, self._local_ip(request)
                )
            )
        except RpcError as err:
            return web.json_response({"code": err.code, "message": err.message})
        except (ValueError, TypeError, web.HTTPBadRequest) as err:
            return web.json_response({"code": -103, "message": str(err)})

    def _dispatch(
        self,
        method: str | None,
        params: dict[str, Any],
        local_ip: str | None = None,
    ) -> dict:
        if method == "Shelly.GetDeviceInfo":
            return self._device.device_info()
        if method == "Shelly.GetStatus":
            return {
                "sys": {"mac": self._device.device_info()["mac"], "uptime": 0},
                "wifi": self._wifi_status(local_ip),
                **{
                    f"switch:{channel}": self._device.switch_status(channel)
                    for channel in range(CHANNEL_COUNT)
                },
            }
        if method == "Shelly.ListMethods":
            return {
                "methods": [
                    "Shelly.GetDeviceInfo",
                    "Shelly.GetStatus",
                    "Shelly.ListMethods",
                    "WiFi.GetConfig",
                    "WiFi.GetStatus",
                    "Switch.GetConfig",
                    "Switch.GetStatus",
                    "Switch.Set",
                    "Switch.Toggle",
                ]
            }
        if method in {"WiFi.GetStatus", "Wifi.GetStatus"}:
            return self._wifi_status(local_ip)
        if method in {"WiFi.GetConfig", "Wifi.GetConfig"}:
            return {
                "ap": {
                    "ssid": DEVICE_ID,
                    "is_open": True,
                    "enable": False,
                },
                "sta": {
                    "ssid": "Virtual Shelly Network",
                    "is_open": False,
                    "enable": True,
                    "ipv4mode": "dhcp",
                    "ip": None,
                    "netmask": None,
                    "gw": None,
                    "nameserver": None,
                },
                "sta1": {
                    "ssid": None,
                    "is_open": True,
                    "enable": False,
                    "ipv4mode": "dhcp",
                    "ip": None,
                    "netmask": None,
                    "gw": None,
                    "nameserver": None,
                },
                "roam": {"rssi_thr": -80, "interval": 60},
            }
        if method in {"Switch.GetConfig", "Switch.GetStatus", "Switch.Set", "Switch.Toggle"}:
            channel = self._channel_id(params)
            if method == "Switch.GetStatus":
                return self._device.switch_status(channel)
            if method == "Switch.GetConfig":
                return {"id": channel, "name": f"Channel {channel + 1}", "in_mode": "follow"}
            if method == "Switch.Set":
                previous = self._device.set_output(channel, self._as_bool(params.get("on")))
            else:
                previous = self._device.toggle_output(channel)
            return {"was_on": previous}
        _LOGGER.warning("Unsupported Shelly RPC method requested: %r", method)
        raise RpcError(-32601, f"Method {method!r} not found")

    @staticmethod
    def _channel_id(params: dict[str, Any]) -> int:
        if "id" not in params:
            raise RpcError(-103, "Missing required parameter: id")
        try:
            return int(params["id"])
        except (TypeError, ValueError) as err:
            raise RpcError(-103, "Switch id must be an integer") from err

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise RpcError(-103, "Parameter 'on' must be true or false")

    @staticmethod
    def _local_ip(request: web.Request) -> str | None:
        transport = request.transport
        if transport is None:
            return None
        socket_address = transport.get_extra_info("sockname")
        return socket_address[0] if socket_address else None

    @staticmethod
    def _wifi_status(local_ip: str | None) -> dict:
        return {
            "sta_ip": local_ip,
            "status": "got ip" if local_ip else "connected",
            "ssid": "Virtual Shelly Network",
            "bssid": "02:00:00:00:00:01",
            "channel": 1,
            "rssi": -45,
        }

    @staticmethod
    def _log_request(request: web.Request, method: object) -> None:
        """Log request metadata without logging potentially sensitive parameters."""
        # Keep this at warning level while pairing compatibility is being
        # diagnosed: Home Assistant's Logs page does not normally display
        # INFO records from custom integrations.
        _LOGGER.warning(
            "Shelly request from %s: %s %s (RPC method: %s)",
            request.remote or "unknown",
            request.method,
            request.path,
            method,
        )
