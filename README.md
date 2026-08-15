# Virtual Shelly

A standalone Home Assistant custom integration for emulating Shelly devices. Home Assistant Core is installed into the development container and is not vendored into this repository.

## Development

1. Open this repository in Visual Studio Code.
2. Run **Dev Containers: Reopen in Container**.
3. After the container finishes building, run:

   ```bash
   hass -c config
   ```

4. Open <http://localhost:8123> for Home Assistant.
5. The emulated Shelly API is available at <http://localhost:8124/shelly>.

The integration source is in `custom_components/virtual_shelly`. The development container links it into `config/custom_components` so the same files are used by Home Assistant locally and by HACS installations.

## Install with HACS

1. In HACS, open the three-dot menu and select **Custom repositories**.
2. Add `https://github.com/thomaspleasance/ha-virtual-shelly` as an **Integration**.
3. Download **Virtual Shelly** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and select **Virtual Shelly**.
5. Keep HTTP port `80` for mySigen/Sigenergy compatibility and optionally select Home Assistant power and cumulative energy sensors for each channel.

Use **Configure** on the integration entry to change the device name, port, channel mappings, or diagnostics setting later. Power values reported in mW, W, kW, or MW are converted to watts for Shelly's `apower` response. Energy values reported in mWh, Wh, kWh, or MWh are converted to watt-hours for `aenergy.total`. Missing or unavailable sensors report zero. The per-minute energy array remains zero because Home Assistant cumulative sensors do not provide the three one-minute buckets expected by Shelly.

### Migrating from YAML

Version 0.2.0 imports an existing `virtual_shelly:` YAML block into a UI config entry when Home Assistant starts. After the entry appears under **Settings → Devices & services**, remove the entire `virtual_shelly:` block from `configuration.yaml` and restart once more. The imported name, port, and power sensor mappings are preserved.

## Try the virtual device

The four Home Assistant entities are named `switch.virtual_shelly_pro_4pm_channel_1` through `channel_4`. State is shared with the Shelly-compatible API:

```bash
curl http://localhost:8124/shelly
curl http://localhost:8124/rpc/Switch.GetStatus?id=0
curl http://localhost:8124/rpc/WiFi.GetStatus
curl -X POST -H 'Content-Type: application/json' \
  -d '{"id":0,"on":true}' \
  http://localhost:8124/rpc/Switch.Set
```

The device also advertises `_shelly._tcp.local.` and `_http._tcp.local.` over mDNS/Bonjour as `shellypro4pm-020000000001.local`. The records point clients to the configured API port. Docker Desktop networking may prevent multicast announcements from reaching the physical LAN even when they are registered successfully inside the container.

## Pairing diagnostics

Every incoming Shelly HTTP/RPC request is recorded at info level in the Home Assistant log under `custom_components.virtual_shelly.server`. Request bodies are deliberately excluded so passwords and other parameters are not logged. Unsupported RPC methods are logged as warnings, which makes it possible to identify compatibility gaps during pairing.

For troubleshooting, enable **Request diagnostics endpoint** from the integration's **Configure** screen. While enabled, safe metadata for the most recent 200 requests is retained in memory and available at `/debug/requests` on the configured Shelly port. The response includes the running build number, excludes request bodies and parameters, and is cleared whenever the integration reloads. Keep this option disabled during normal use because the endpoint is accessible to other devices on the local network.
