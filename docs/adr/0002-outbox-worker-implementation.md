# ADR-0002: Defer Outbox Background Worker Implementation

**Status**: Accepted (Deferred)

**Date**: 2026-09-02

**Context**

The outbox pattern (writing domain events to an `outbox` table within the same transaction as domain changes) requires a background process to poll the outbox table and publish events to downstream consumers (message broker, webhooks, etc.). 

Current implementation in `adapters/unit_of_work.py` correctly writes events to the outbox table on commit (`_write_outbox_events`), but no worker exists to process them.

**Decision**

**Defer implementation of the outbox worker.** The outbox table will accumulate events but they will not be processed until a future milestone.

**Rationale**

1. **No downstream consumers exist yet** — No message broker (Kafka/RabbitMQ), webhook system, or event-driven services are implemented. Processing events with no consumers provides zero value.

2. **Simpler operational model for development** — Running without a worker avoids:
   - Managing a separate process lifecycle (supervisor, systemd, K8s Job)
   - Duplicate processing risk when scaling app replicas
   - Complex retry/dead-letter logic before it's needed
   - Infrastructure dependencies (Kafka, Debezium, schema registry) in dev

3. **Outbox table acts as audit log** — Even unprocessed, the outbox table provides a complete, queryable history of all domain events for debugging and future reconciliation.

4. **YAGNI** — The worker adds significant complexity (polling, batching, retries, idempotency, monitoring). Build it when a consumer needs it.

**Alternatives Considered**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| In-process thread | Simplest, shares DB pool | Blocks on app restart, duplicate processing if scaled | Defer |
| Supervisor (systemd/supervisord) | Independent lifecycle, standard Linux | Extra process management, config complexity | Defer |
| Cron job | Zero infrastructure | Minimum 1min latency, no backpressure | Defer |
| CDC (Debezium → Kafka) | Robust, exactly-once, no app code | Requires Kafka cluster + Debezium + schema registry | Defer |
| K8s Job | Cloud-native | Only if on Kubernetes | Defer |

**Implementation Note**

The outbox table schema (`adapters/orm.py:137-150`) includes:
- `processed_at` (NULL = unprocessed)
- `retry_count` (for exponential backoff)
- `payload` (JSONB with event envelope)
- Partial index on `processed_at IS NULL` for efficient polling

This schema supports any future worker implementation.

**Next Steps (Trigger for Revisit)**

Implement the worker when **any** of the following exist:
1. A message broker (Kafka/RabbitMQ) is provisioned and a consumer service needs events
2. Webhook delivery system is implemented
3. Inter-service communication via events is required
4. Audit/replay requirements demand processed events

**Milestone Target**: Evaluate at Milestone 5 (or when first event consumer is added).

**References**
- CONTEXT.md §13: "Outbox worker: In-process thread polling every 5s, batch 100, max 5 retries"
- `adapters/unit_of_work.py:209-218` — `_write_outbox_events` implementation
- `adapters/orm.py:137-150` — Outbox table schema