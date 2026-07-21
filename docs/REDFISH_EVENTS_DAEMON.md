# Redfish event daemon

The Redfish event daemon is a long-running process that subscribes to BMC event streams (SSE or webhook fallback), batches bursts of events, and runs the same serviceability analysis path as on-demand `node-scraper run-plugins`.

## Install

```bash
cd ~/node-scraper_public
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,events]"
```

The `[events]` extra pulls in `httpx`, required for async Redfish ingest.

## Run

```bash
node-scraper daemon --daemon-config config/redfish_events_daemon.example.json
```

Copy the example config, set BMC credentials, hub module paths, and (for webhook transport) point each target's `webhook_url` at this daemon's HTTP listener.

## On-demand CLI vs daemon

| | On-demand (`run-plugins`) | Daemon (`daemon`) |
|---|---|---|
| Lifecycle | One-shot collection + analysis | Long-lived background process |
| Event source | Redfish log pull during plugin run | Continuous SSE or webhook ingest |
| Analysis trigger | After collection completes | Sliding window (default: 3 events in 10s) |
| Output | Log directory + artifacts | Logs + HTTP `/recommendations` JSON |
| Use when | Ad-hoc debug, CI, field capture | Live monitoring, NOC integration |

The on-demand MI3XX plugin path is unchanged. Both flows call `analyze_serviceability_window()` so hub configuration stays aligned.

## Configuration

Top-level sections in the daemon JSON:

- **stream** — global ingest settings (`EventStreamConfig`): severities, dedupe, baseline re-pull, webhook fallback.
- **targets** — one entry per BMC (`EventTargetConfig`): host, credentials, transport (`auto`, `sse`, or `webhook`), optional `webhook_url`.
- **trigger** — sliding window thresholds (`TriggerConfig`): `min_events`, `window_seconds`, `cooldown_seconds`.
- **analysis** — same fields as `ServiceabilityAnalyzerArgs` in plugin configs (`hub_python_module`, `afid_sag_path`, etc.).
- **http** — optional listener for webhook ingest and live recommendations.

See `config/redfish_events_daemon.example.json`.

### Webhook transport

When SSE is unavailable, set `transport` to `webhook` (or rely on `auto` + `enable_webhook_fallback`) and configure:

1. `http.enabled: true` on the daemon with a reachable host/port.
2. Each target's `webhook_url` → `http://<daemon-host>:<port>/hook/<target_key>`.
3. `allow_loopback_webhook: true` only for local testing (BMCs cannot reach loopback).

### Trigger engine

Events accumulate per `target_key`. When at least `min_events` arrive within `window_seconds`, the daemon runs serviceability analysis on that batch and ignores further triggers until `cooldown_seconds` elapse.

## HTTP endpoints

When `http.enabled` is true (default):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/status` | Daemon health and per-target transport state |
| GET | `/recommendations` | Latest analysis snapshot for all targets |
| GET | `/recommendations/{target_key}` | Latest snapshot for one target |
| POST | `/hook/{target_key}` | Webhook payload → `handle_webhook_payload()` |

Recommendations responses include `serviceability` (hub output), `afid_events`, and trigger metadata.

## Tests

```bash
pytest test/unit/redfish_events/ test/unit/plugins/test_analysis_window.py -v
```

## Deployment notes

Systemd unit files and Docker images are not bundled yet. Run the daemon under your process supervisor of choice; ensure the HTTP port is reachable from BMCs when using webhook transport.
