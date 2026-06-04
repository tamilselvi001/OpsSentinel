# alert-simulator — mock Elastic/PagerDuty/Grafana signal generator

Emits **Phase-1 normalized alert events** onto `opssentinel-alerts` via `lib/pubsub.py` — the
**synthetic telemetry** used to exercise Phase 2 (and, later, the Phase-5 storm test). It reuses
`lib/events.py` and introduces **no new schema**.

## Modes

| Command | Output |
|---|---|
| `python -m app.main signal` | One realistic incident — the 02:47 payment-service DB-connection-pool event |
| `python -m app.main storm --count 50` | 50+ related signals that **all share one `correlation_key`** |

Via the harness: `make signal` and `make storm`.

The storm signals deliberately share a `correlation_key` so the Agent Layer (Phase 3) can fold
them into a single incident with time-windowed spatial correlation. **This service only produces
the signals and lands them on the queue** — the storm-deduplication validation itself is Phase 5.

## Run / build

```bash
make dev      # also starts the simulator container in the local stack
make storm    # publish 50+ correlated signals to the emulator

docker build -f services/alert-simulator/Dockerfile -t alert-simulator .   # non-root
```
