# Test Fragment 2 — Kafka Consumer

Reference test fragment used as a learning example for the digital-twin
platform. The worker subscribes to the `f1.events` Kafka topic produced
by test-fragment-1, forwards each event to its own API for persistence,
and the API exposes the resulting event log over REST. Pair it with
test-fragment-1 (producer) and test-fragment-3 (REST poller) to see a
complete Kafka producer → consumer → REST chain across three fragments.

**Repository:** https://github.com/DatiGroup/fragment-test-2
**Fragment ID:** `test-fragment-2`

## Architecture

The worker is a Kafka consumer that POSTs every received event into its
own API, which writes it to PostgreSQL. Downstream readers (widgets, or
test-fragment-3) query the API for the historical event log.

```
   test-fragment-1 ──▶ Kafka: f1.events
                              │
                              ▼
                       ┌──────────┐
                       │  Worker  │
                       └─────┬────┘
                             │ HTTP POST /events (internal)
                             ▼
                        ┌────────┐
                        │  API   │ ◀─▶ PostgreSQL
                        └────┬───┘
                             │ HTTP GET /events
                             ▼
                  widgets / test-fragment-3
```

### Components

- **Worker** — kafka-python consumer that subscribes to `KAFKA_TOPIC` and
  POSTs each message body to the local API at `/events`. Duplicate
  events (same `event_id`) are absorbed via a `409` response and logged
  as warnings. Any other failure — an event the API rejects, or the API
  being unreachable — is logged as an error and the event is skipped, not
  retried.
- **API** — FastAPI service backed by PostgreSQL. Exposes REST endpoints
  for listing events and looking them up by `event_id`. Has no
  WebSocket. The `event_log` table is created on startup (Alembic
  migration, plus `create_all` as a fallback).

### Event log

Each event becomes one `event_log` row:

| Field | Content |
|---|---|
| `id` | Row id |
| `event_id` | The event's `event_id` (unique, up to 36 characters) |
| `source_fragment_id` | The event's `fragment_id` |
| `event_type` | Always `counter_update` |
| `payload` | `event_id`, `fragment_id`, `counter`, `delta`, `timestamp`, `metadata` as received |
| `event_timestamp` | The event's `timestamp` (ISO 8601) |
| `received_at` | When the API stored it (UTC) |

An event without `event_id`, `fragment_id`, `counter` or `timestamp` is
rejected with `422`; a `timestamp` that is not ISO 8601 fails with `500`.
Other fields of the message are dropped. Rows are never removed.

## REST API endpoints

| Method | Path                                  | Description                                              |
|--------|---------------------------------------|----------------------------------------------------------|
| GET    | `/healthcheck`                        | Health status                                            |
| GET    | `/events?skip=0&limit=100&source=...` | List event-log entries, newest received first; `limit` 1–1000. `source` filters by `source_fragment_id` |
| GET    | `/events/{event_id}`                  | Fetch a specific event by its source `event_id`; `404` if unknown |
| POST   | `/events`                             | Internal write endpoint used by the worker; `201`, or `409` for a duplicate `event_id` |

`POST /events` is hidden from the API's own `/docs`, but the published
contract `schemas/produces/openapi/produces.openapi.json` does list it.

## WebSocket endpoints

This fragment does not expose any WebSocket endpoints.

## Kafka topics

### Consumes

| Topic       | Payload class               | Description                                  |
|-------------|-----------------------------|----------------------------------------------|
| `f1.events` | `com.example.f1.CounterEvent` | Counter events emitted by test-fragment-1. |

The fragment does not produce any Kafka topic.

The worker consumes in the group `KAFKA_CONSUMER_GROUP`, starting from the
**oldest** retained message when the group has no committed offset, so a
fresh deployment (or a new group name) logs the topic's whole history.
Offsets are committed automatically, including for skipped events.

`manifest.yaml` points the consumed schema at
`/schemas/produces/kafka/f1.events.counter-event.v1.json`, but the file in
this repository is `schemas/consumes/kafka/f1.events.counter-event.v1.json`.

## Authentication

The API uses
[dt-fragment-auth](https://github.com/DatiGroup/dt-fragment-auth)
and refuses every request without a valid caller, including routes added
later. Accepted callers:

- **Portal widgets** send the signed-in user's Keycloak token
  (`Authorization: Bearer <token>`).
  Only members of this digital twin are admitted.
- **Other fragments of the same twin** send a token of the twin's Keycloak
  client.
- **This fragment's own worker** sends `X-Fragment-Token: <FRAGMENT_INTERNAL_TOKEN>`.

The platform injects everything below at deploy time; none of it goes in the
instance config. In `enforce` or `log` mode the API refuses to start when a
required variable is missing.

| Variable | Component | Description |
|---|---|---|
| `FRAGMENT_AUTH_MODE` | api | `enforce` (platform), `log` (check and log, refuse nothing) or `off` (the local Docker Compose stack) |
| `FRAGMENT_AUTH_JWKS_URL`, `FRAGMENT_AUTH_ISSUER`, `FRAGMENT_AUTH_AUDIENCE` | api | Keycloak token validation |
| `FRAGMENT_AUTH_DT_API_URL`, `DIGITAL_TWIN_ID` | api | Twin membership check for user tokens |
| `FRAGMENT_AUTH_TWIN_CLIENT_ID` | api | The twin's Keycloak client (`dt-<short-twin-id>`), accepted from same-twin fragments |
| `FRAGMENT_INTERNAL_TOKEN` | api, worker | This instance's internal token, from its Kubernetes Secret |

## Configuration

Variables read by the code. `KAFKA_TOPIC` and `KAFKA_CONSUMER_GROUP` are
passed to the worker by `k8s/manifest.yaml`; the rest are injected by the
platform at deploy time.

| Variable                | Component | Description                                            | Default                      |
|-------------------------|-----------|--------------------------------------------------------|------------------------------|
| `KAFKA_TOPIC`           | worker    | Topic to subscribe to                                  | `f1.events`                  |
| `KAFKA_CONSUMER_GROUP`  | worker    | Consumer group ID                                      | `test-fragment-2-consumer`   |
| `KAFKA_BOOTSTRAP_SERVERS` | worker  | Kafka brokers (**required**; without it the worker logs an error and exits) | — |
| `API_URL`               | worker    | Fragment API base URL                                  | `http://localhost:8000`      |
| `DB_NAME`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` / `DATABASE_URL` | api | Database connection; the API refuses to start without one | port `5432` |

Both components also load a `.env` file if present (see `.env.example`).

None of these is declared in `manifest.yaml`, so none can be set in the
instance config. The consumer group can be chosen per connection instead (see
[Connections](#connections)).

## Sample configuration

What the digital-twin builder stores for this fragment. You enter it in the
builder, not in a file; the platform turns it into environment variables and
Kubernetes resources at deploy time.

### Instance config

This fragment has no operator settings, so an instance only needs config
to change its CPU or memory:

```json
{
  "resources": {
    "api":    { "memoryRequest": "128Mi", "memoryLimit": "512Mi" },
    "worker": { "memoryRequest": "128Mi", "memoryLimit": "512Mi" }
  }
}
```

`resources` is optional: it overrides the CPU and memory in
`k8s/manifest.yaml`, whose values the builder pre-fills (shown above). The keys
are `cpuRequest`, `cpuLimit`, `memoryRequest` and `memoryLimit`; flat keys apply
to both containers, an `api` or `worker` block to one. Leave the config empty
(`{}`) to keep the defaults.

### Connections

Drawing a connection in the builder stores a record like these (shown without
the fragment and widget ids).

Kafka, from test-fragment-1. `config.topicName` is the one topic both ends use.
The consumer group defaults to `<short-twin-id>-<short-fragment-id>-consumer-group`;
add `"overrides": { "kafkaConsumerGroup": "<group>" }` to `config` to choose
another.

```json
{
  "type": "kafka",
  "from_config": { "topicKey": "f1.events", "topic": "f1.events" },
  "to_config":   { "topicKey": "f1.events", "topic": "f1.events" },
  "config":      { "topicName": "f1.events" }
}
```

REST, to test-fragment-3. test-fragment-3 receives
`EVENTS_API_URL=<this fragment's base URL>/events`; `to_config.key` can be left
out because test-fragment-3 has only one REST slot. The optional
`config.overrides` sets variables on test-fragment-3 for this connection.

```json
{
  "type": "rest",
  "from_config": { "apiPath": "/events", "method": "GET" },
  "to_config":   { "key": "events_api_url" },
  "config":      { "overrides": { "pollIntervalSeconds": 600 } }
}
```

REST, to a data-grid widget, which shows the event log as a table:

```json
{
  "type": "rest",
  "from_config": { "apiPath": "/events", "method": "GET" },
  "to_config":   { "key": "grid-data-stream", "method": "GET" }
}
```

## Dependencies

- **Platform fragments:** test-fragment-1 (producer of `f1.events`).
- **External services:** none.
- **Datastore:** PostgreSQL, holding the `event_log` table.

## Local development

```bash
docker compose up --build
```

- API: <http://localhost:8001> (`API_PORT`; OpenAPI docs at `/docs`)
- Kafka UI: <http://localhost:8081> (`KAFKA_UI_PORT`)
- Kafka broker from the host: `localhost:9093` (`KAFKA_PORT`)

The host ports are offset from test-fragment-1's so both stacks can run at
once. The stack starts its own Kafka broker and the worker is wired to it
(`kafka:29092`); for a multi-fragment local setup, change the worker's
`KAFKA_BOOTSTRAP_SERVERS` in `docker-compose.yml` to the broker
test-fragment-1 publishes to.

## Schemas

- Kafka consumed payload schemas: `schemas/consumes/kafka/*.json`
- REST API description: `schemas/produces/openapi/produces.openapi.json`

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
