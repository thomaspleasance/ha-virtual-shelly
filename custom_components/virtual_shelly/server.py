"""Minimal Shelly Gen2-compatible HTTP/RPC server."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from .const import CHANNEL_COUNT, DEVICE_ID
from .device import VirtualShellyPro4PM


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

    async def _handle_device_info(self, _request: web.Request) -> web.Response:
        return web.json_response(self._device.device_info())

    async def _handle_rpc_frame(self, request: web.Request) -> web.Response:
        try:
            frame = await request.json()
            request_id = frame.get("id")
            result = self._dispatch(frame.get("method"), frame.get("params", {}))
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
            if request.method == "POST":
                params = await request.json() if request.can_read_body else {}
            else:
                params = dict(request.query)
            return web.json_response(self._dispatch(request.match_info["method"], params))
        except RpcError as err:
            return web.json_response({"code": err.code, "message": err.message})
        except (ValueError, TypeError, web.HTTPBadRequest) as err:
            return web.json_response({"code": -103, "message": str(err)})

    def _dispatch(self, method: str | None, params: dict[str, Any]) -> dict:
        if method == "Shelly.GetDeviceInfo":
            return self._device.device_info()
        if method == "Shelly.GetStatus":
            return {
                "sys": {"mac": self._device.device_info()["mac"], "uptime": 0},
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
                    "Switch.GetConfig",
                    "Switch.GetStatus",
                    "Switch.Set",
                    "Switch.Toggle",
                ]
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
