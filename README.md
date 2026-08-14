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
4. Add the following to `configuration.yaml` and restart again:

   ```yaml
   virtual_shelly:
     name: Virtual Shelly Pro 4PM
     port: 8124
   ```

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

The device also advertises `_shelly._tcp.local.` and `_http._tcp.local.` over mDNS/Bonjour as `shellypro4pm-virtual000001.local`. The records point clients to the configured API port. Docker Desktop networking may prevent multicast announcements from reaching the physical LAN even when they are registered successfully inside the container.

## Pairing diagnostics

Every incoming Shelly HTTP/RPC request is recorded in the Home Assistant log under `custom_components.virtual_shelly.server`. Request bodies are deliberately excluded so passwords and other parameters are not logged. Unsupported RPC methods are logged as warnings, which makes it possible to identify compatibility gaps during pairing.
