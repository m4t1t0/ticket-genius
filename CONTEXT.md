# Ticket Genius

Core domain for a ticketing platform that aggregates events from multiple providers (starting with Ticketmaster) and enables ticket purchasing.

## Language

**Provider-Agnostic Domain**:
The core domain entities (Concert, Venue, Artist, etc.) contain zero knowledge of any external ticket provider. All provider-specific data (Ticketmaster IDs, Eventbrite IDs, etc.) lives exclusively in infrastructure adapters.

**Repository Port**:
An interface (abstract base class) defined in the domain layer that declares data access operations. Adapters in `adapters/` implement these ports. The domain depends on the port, not the implementation.

**External ID**:
An identifier from an external system (e.g., `ticketmaster_id`, `eventbrite_id`). These never appear in domain entities — they exist only in adapter mapping layers and database columns.

**Ingestion Adapter**:
An adapter that translates a third-party API payload (e.g., Ticketmaster Discovery API) into the provider-agnostic domain model.

**CQRS (Command Query Responsibility Segregation)**:
Separate read and write operations at the repository port and service layer level. Read repositories serve queries; write repositories serve commands. Read models are not yet projected from events — they query write tables directly behind separate port interfaces.

**Outbox Pattern**:
Domain events are written to an `outbox` table within the same database transaction as business data. A background worker polls this table and processes events (initially logs them; later forwards to Kafka when a consumer exists). No Kafka dependency for the initial release.

**Schema Migration Strategy**:
SQLAlchemy Imperative Mapping defines tables and mappers explicitly in `adapters/orm.py`. Alembic manages migrations (`alembic revision --autogenerate`). The domain layer has no dependency on SQLAlchemy.

**Payment Port**:
An interface (abstract base class) defined in the domain layer for payment operations. Initially provides `create_payment_intent(amount, currency, metadata) -> client_secret` and `confirm_payment(payment_intent_id) -> PaymentResult`. A simulated adapter implements this for Milestone 1-2; Stripe adapter will implement it later. Refunds and webhook handling are deferred.

**Redis Cache Strategy**:
TTL-based caching for Ticketmaster responses. Key patterns: `tm:search:{params_hash}` for search results, `tm:event:{id}` for event details. TTL = 300s (configurable). Invalidation is TTL-only for now — no event-driven invalidation. Sufficient for rate-limit mitigation and read performance.

**Directory Layout**:
Flat structure under each Cosmic Python layer: `domain/concert.py`, `domain/venue.py`, `adapters/ticketmaster.py`, `adapters/sqlalchemy_repo.py`, `service_layer/orders.py`, `entrypoints/api.py`. Group by aggregate only when the domain grows.

**Plan (Aggregate Root)**:
A scheduled concert/show sourced from a ticket provider (Ticketmaster, etc.). Called "Plan" instead of "Event" to avoid ambiguity with domain events. Read-only locally — populated via ingestion adapter. Contains venue, artist(s), date range, seat map, price ranges.

**Value Objects**:
Immutable frozen dataclasses representing domain primitives:
- `Money(amount: Decimal, currency: Currency = EUR)` — 2 decimal places, ISO 4217 currency codes, default EUR (company base currency)
- `Seat(section: str, row: str, number: str)` — immutable, validated against plan seat map
- `DateRange(start: datetime, end: datetime, timezone: str)` — UTC datetimes, timezone for display
- `TicketQuantity(value: int)` — 1-8 tickets per order
- `AttendeeInfo(name: str, email: str, phone: str | None)` — name/email required, phone optional

**Domain Events**:
Events emitted by aggregates, stored in outbox table with envelope (event_id, occurred_at, correlation_id, causation_id):
- `OrderCreated(order_id, plan_id, quantity, total_amount, attendee_info)`
- `PaymentInitiated(order_id, payment_id, provider, intent_id)`
- `PaymentConfirmed(order_id, payment_id, provider_ref)`
- `PaymentFailed(order_id, payment_id, reason)`
- `OrderConfirmed(order_id, tickets)`
- `OrderCancelled(order_id, reason)`

**Repository Ports (Write)**:
```python
# OrderRepository (write)
add(order: Order) -> None
get(order_id: OrderId) -> Order | None
get_by_payment_id(payment_id: PaymentId) -> Order | None

# PaymentRepository (write)
add(payment: Payment) -> None
get(payment_id: PaymentId) -> Payment | None
get_by_order_id(order_id: OrderId) -> Payment | None
```
No update/delete — aggregate tracks changes, UoW flushes.

**Repository Ports (Read)**:
Read repositories query write tables directly for now, behind separate port interfaces for future projection swap:
```python
# OrderReadRepository
get_order_summary(order_id: OrderId) -> OrderSummary | None
list_orders(customer_email: Email, page: int, size: int) -> Paginated[OrderSummary]

# PlanReadRepository
search_plans(query: PlanSearchQuery) -> list[PlanSummary]
get_plan(plan_id: PlanId) -> PlanDetail | None
```

**Unit of Work**:
Explicit `UnitOfWork` class used as context manager in service functions. On `__exit__` (no exception): flush session → collect domain events from all loaded aggregates → write events to `outbox` table → commit transaction. On exception: rollback. Session scoped to UoW lifetime.

**Service Layer / Use Cases**:
Service functions take Pydantic input models, return Pydantic output models or raise custom exceptions:
- `create_order(cmd: CreateOrderCommand) -> OrderCreatedResult`
- `confirm_payment(cmd: ConfirmPaymentCommand) -> PaymentConfirmedResult`
- `search_plans(query: PlanSearchQuery) -> PlanSearchResult`
- `get_plan(plan_id: PlanId) -> PlanDetail`
- `cancel_order(order_id: OrderId, reason: str) -> None`
- `get_order_status(order_id: OrderId) -> OrderStatus`

**PlanSummary (Read Model)**:
Minimal fields cached from Ticketmaster search: `id`, `name`, `url`, `images[0].url`, `dates.start.localDate`, `dates.start.localTime`, `dates.timezone`, `venue.name`, `venue.city`, `venue.state`, `priceRanges[0].min/max/currency`. TTL 300s. Search hash key = normalized query params (sorted). Adapter handles TM pagination internally, returns flat list. Extensible for future fields.

**Ticketmaster Sandbox**:
All development and testing uses Ticketmaster Discovery API sandbox environment. No real orders are placed. Production migration will switch to live credentials.

**API Endpoints**:
REST with Pydantic schemas, no auth for initial release (auth method TBD — see ADR-0001):
- `POST /api/v1/orders` — CreateOrderCommand → OrderCreatedResult (201)
- `POST /api/v1/orders/{order_id}/confirm-payment` — ConfirmPaymentCommand → PaymentConfirmedResult (200)
- `GET /api/v1/orders/{order_id}` — OrderStatus (200)
- `DELETE /api/v1/orders/{order_id}` — 204
- `GET /api/v1/plans/search?q=&lat=&lon=&radius=&page=&size=` — PlanSearchResult (200)
- `GET /api/v1/plans/{plan_id}` — PlanDetail (200)
All errors → RFC 7807 Problem Details.

**Configuration Management**:
Single `Settings` class in `config.py` using Pydantic Settings v2, with nested models: `DatabaseSettings`, `RedisSettings`, `TicketmasterSettings`, `PaymentSettings`, `AppSettings`. Loaded from `.env` + env vars. `APP_ENV` controls log level and debug.

**Error Handling**:
Exception hierarchy rooted at `TicketGeniusError`. FastAPI exception handlers map each to RFC 7807 response with `type`, `title`, `status`, `detail`, `instance`. Domain errors include `code` (e.g., `INSUFFICIENT_INVENTORY`, `PAYMENT_DECLINED`). Log all 5xx with traceback, 4xx as info.

**SQLAlchemy Imperative Mapping**:
Explicit `Table` per aggregate in `adapters/orm.py`. Composite columns for simple VOs (Money→amount_cents+currency, Seat→section+row+number, DateRange→start+end+timezone, TicketQuantity→value). Separate `attendees` table with FK to `orders` (no JSON columns). Imperative mappers with `mapper_registry.map_imperatively(Aggregate, table, properties={...})`.

**Outbox Table & Worker**:
Table: `id` (PK, UUID), `aggregate_id` (UUID), `aggregate_type` (str), `event_type` (str), `payload` (JSONB), `created_at` (timestamp), `processed_at` (timestamp, nullable), `retry_count` (int, default 0). Worker implementation TBD — see ADR-0002. For Milestone 5: in-process thread polling every 5s, batch 100, max 5 retries with exponential backoff.

**Payment Adapter (Simulated)**:
In-memory dict for payment intents. `create_payment_intent(amount, currency, metadata)` → returns test ID (`pi_test_...`), client_secret, status `requires_payment_method`. `confirm_payment(payment_intent_id, payment_method="pm_card_visa")` → returns `status="succeeded"` unless amount > €100 (then `failed`). No external HTTP calls.

**Ticketmaster Adapter**:
OAuth2 client credentials (client_id/secret from settings), token cached with 5min buffer before expiry. Token bucket rate limiter (capacity 5, refill 5/s) per process. Sync `httpx.Client` with 10s connect / 30s read timeouts. TM error codes mapped to domain exceptions (PlanNotFound, SearchFailed, PurchaseFailed). Retry 429/5xx up to 3x with exponential backoff.

**Alembic Migration Strategy**:
Single `alembic.ini` + `migrations/` with `env.py` reading from Settings. Initial migration autogenerated for orders/payments/plans/outbox/attendees; hand-edit for indexes/FKs. Subsequent changes via `alembic revision --autogenerate` (generates DDL diff, never truncates data). Review generated scripts before `upgrade`.

**Testing Strategy**:
Unit: pytest + mocks, >90% domain coverage. Integration: pytest + testcontainers (Postgres, Redis), respx for TM HTTP; Contract: schemathesis against OpenAPI; sync-only tests, no pytest-asyncio needed. **Test isolation**: Separate test database (`.env.test` with `DATABASE_URL_TEST`). Redis keys prefixed with `test:` or in-memory fakes for Redis adapter (simpler, preferred for unit tests).

**Logging & Observability**:
JSON structured logs via structlog; correlation ID via contextvars per request; prometheus-client counters for key business metrics (`orders_created`, `payments_succeeded`, `payments_failed`, `tm_search_latency`, `tm_purchase_latency`); log domain events at DEBUG. **OpenTelemetry**: instrumented from day one (traces + metrics export), visualization deferred (Grafana/Tempo later).

**Local Development**:
No Docker currently (machine constraints). PostgreSQL, Redis, and other services installed locally on developer machines. Environment configured via `.env` file. **Docker support**: docker-compose.yml maintained for CI/CD and future local use; CI/CD uses containers (testcontainers, GitHub Actions).

**API Versioning & OpenAPI**:
URL path versioning `/api/v1/`; OpenAPI spec manually maintained at `docs/openapi.yaml` (flask-apispec has Pydantic v2 compatibility issues — see ADR-0003); serve spec at `/openapi.json`, Swagger UI at `/docs` using manual YAML spec. Pydantic v2 models used for runtime validation directly in route handlers.

**Concurrency Control (Optimistic Locking)**:
Integer `version` column on orders, payments, plans tables (default 1). UoW includes `WHERE version = :old_version` on UPDATE; rowcount=0 → OptimisticLockError → 409 Conflict. Plans version protects seat availability.

**Outbox Event Serialization**:
JSONB payload with envelope: `{ event_type, aggregate_id, occurred_at, correlation_id, causation_id, data }`. No Avro/Protobuf; schema validated by Pydantic on read. Sufficient for local simulation; no schema registry needed.

**Idempotency for Payment Confirmation**:
Server-generated idempotency key returned from `create_payment_intent`; client passes key on `confirm_payment`; Redis key `payment:{id}:confirm:{key}` with 24h TTL prevents duplicate processing.

**Order State Machine**:
States: `PENDING` → `SEATS_RESERVED` → `PAYMENT_INITIATED` → `PAID` → `FULFILLED` | `CANCELLED` (from PENDING/SEATS_RESERVED/PAYMENT_INITIATED) | `REFUNDED` (from PAID/FULFILLED). Transitions enforced in aggregate methods, not setters.

**Payment State Machine**:
States: `CREATED` → `AUTHORIZED` → `CAPTURED` | `FAILED` | `REFUNDED` | `PARTIALLY_REFUNDED`. Webhook drives transitions; idempotency key prevents duplicate processing.

**Plan Population Strategy**:
Initial sync via admin CLI (`sync-plans --since=2024-01-01`). Webhook for real-time updates (TM sends plan changes). Redis cache invalidated on webhook + TTL fallback (5 min). Plan aggregate is read-heavy, write-light.

**Seat Hold Mechanism**:
Redis `SEAT_HOLD:{plan_id}:{seat_id}` with 10-min TTL, value = `order_id`. Acquired in `ReserveSeats` use case before payment. Released on: payment failure, order cancellation, TTL expiry. Plan aggregate `version` increments on hold/release for optimistic concurrency.

**TM Purchase Flow**:
`create_order` orchestrates: ReserveSeats → CreatePayment(PENDING) → TM CreateOffer (idempotency_key=order_id) → return order_id to client. Client calls `confirm_payment` → TM AcceptOffer → PaymentCapture → TM FulfillmentWebhook → OrderFULFILLED. Idempotency key = `order_id` passed to all TM calls.

**Database Indexes**:
- `plans`: `idx_plans_date_range (start_date, end_date)`, `idx_plans_tm_id (tm_plan_id)`
- `orders`: `idx_orders_customer (customer_email)`, `idx_orders_status (status)`, `idx_orders_plan (plan_id)`
- `payments`: `idx_payments_order (order_id)`, `idx_payments_status (status)`
- `outbox`: `idx_outbox_unprocessed (processed_at) WHERE processed_at IS NULL` (partial index)

**Redis Cache Invalidation (Plans)**:
Cache-aside with `redis.lock("plan:{id}:lock", timeout=5s)` on miss. Only one request rebuilds cache. Webhook publishes `PlanUpdated` to Redis channel; subscriber deletes key. Admin UI has "Purge Cache" button.

**Health Checks**:
- `/health/live` → 200 OK (process alive)
- `/health/ready` → checks: DB `SELECT 1`, Redis `PING`, TM OAuth token valid (cached), outbox worker heartbeat < 30s old. Returns 503 if any fail.

**Graceful Shutdown**:
`shutdown_event = threading.Event()`. Flask `before_request` checks `shutdown_event.is_set()` → 503. Worker thread polls `shutdown_event.wait(timeout=1)`. Main thread: `shutdown_event.set()` → `worker.join(timeout=30)` → `outbox.flush()` → `engine.dispose()` → `redis.close()`.

**Dependency Injection**:
`python-dependency-injector` for container-based wiring. Declarative providers (Factory, Singleton), module wiring, overrides for testing. Adapters bound in container config; `create_app()` resolves from container.

**Request/Response Validation**:
`pydantic` models for request/response. Middleware: `@app.before_request` validates `request.json` against endpoint's `RequestModel`. `@app.after_request` validates response against `ResponseModel` (dev mode only). Errors → RFC 7807.

**Pagination Strategy**:
Cursor-based (keyset pagination) for performance: `?cursor=opaque_token&limit=20`. Cursor = base64(last_seen_id, last_seen_sort_key). No total count. Max limit 100, default 20. For orders: sort by `created_at DESC, id DESC`.

**OpenTelemetry Tracing**:
`opentelemetry-instrument` wrapper + manual spans for domain operations; sampler `ParentBased(TraceIdRatioBased(0.1))`; resource attributes `service.name=ticket-genius`, `deployment.environment`. Auto-instrument Flask, SQLAlchemy, httpx, Redis; custom spans for TM calls (`tm.create_offer`, `tm.accept_offer`), payment calls, outbox worker; propagate `traceparent` to TM webhooks; export to OTLP endpoint (Jaeger/Tempo).

**Metrics & Observability (Deferred)**:
`prometheus-client` + `prometheus-flask-exporter` expose `/metrics` endpoint now. **Grafana Cloud** for hosted Prometheus + Grafana + Alertmanager in future (free tier available). Local Docker Compose for dev if needed. SLIs: request_latency_p99 < 500ms, error_rate < 0.1%, order_success_rate > 99.5%, outbox_lag_seconds < 30, seat_hold_conflict_rate < 1%.

**Deployment Strategy (Deferred)**:
Local environment only for now. Future: Kubernetes (EKS/GKE) with Helm charts; ArgoCD for GitOps; environments: dev (namespace), staging (namespace), prod (separate cluster); blue/green via Argo Rollouts; HPA on CPU/memory + custom metric `queue_depth`.

**Database Backup/Restore (Deferred)**:
No backups or CDC for local dev. Future: RDS PostgreSQL with automated snapshots (daily, 30-day retention) + PITR (5-min RPO); `pg_dump` for logical backups weekly to S3 (Glacier); test restore quarterly; RTO < 1hr, RPO < 5min. Enable `wal_level=logical` for CDC.

**Disaster Recovery (Deferred)**:
No DR plan for local dev. Future: Multi-AZ PostgreSQL, Redis ElastiCache Multi-AZ, TM webhook per AZ, runbooks in `docs/runbooks/`, quarterly DR drill. RTO < 15min AZ, < 4hr region.

**Load Testing (Deferred)**:
No load testing for local dev. Future: k6 scripts in `load/` (browse 80%, create order 15%, webhook 5%); 200 RPS sustained, 500 spike; p99 < 800ms; CI gate on p95 regression > 10%.

**API Documentation Publishing**:
CI generates OpenAPI from apispec → `docs/openapi.yaml`; publish to Redocly/Stoplight via GitHub Pages on tag; developer portal at `docs.ticket-genius.com`; breaking change detection (`oasdiff`) in PR checks. `apispec` + `flask-apispec`; `spectral` linting; versioned URLs `/api/v1/openapi.yaml`.

**Secret Management (Deferred)**:
No secret management for local dev (`.env` file only). Future: AWS Secrets Manager for prod; Doppler/1Password for dev/staging; SOPS-encrypted `.env.secrets.enc` in repo for CI; rotate every 90 days via Lambda.

**CI/CD Pipeline (Deferred)**:
No CI/CD for local dev. Future: GitHub Actions (lint → test → build → scan → deploy-staging → deploy-prod); reusable workflows; `cosign` sign images; SLSA Level 2; dependabot auto-merge for patch.

**DB Migration Execution**:
`alembic upgrade head` in initContainer before app starts; `alembic downgrade -1` rollback script in Helm `pre-delete` hook; backward-compatible migrations only (expand/contract); `pg_lock` advisory lock for concurrent deploys. `alembic check` in CI; `migration_annotations` table; zero-downtime: add column → deploy → backfill → drop.

**Plan Freshness Tracking**:
Each `Plan` aggregate includes `last_synced_at` (timestamp) and `tm_last_modified` (timestamp from Ticketmaster `lastUpdated` field). Freshness = `now() - last_synced_at`. Admin CLI `sync-plans` updates both fields. Staleness threshold (e.g., > 24h) triggers re-sync recommendation. Future: cron job runs `sync-plans --stale-only` nightly.

## Pending Items (Deferred)

1. **Swagger UI Fix** (ADR-0003) — Fix `/docs` endpoint to render manual OpenAPI YAML spec
2. **JWT Authentication** (ADR-0001) — Implement JWT auth for API endpoints
3. **Outbox Worker** (ADR-0002) — Implement background worker for outbox event processing
4. **Contract Tests Enhancement** — Add schemathesis property-based testing with base_url
5. **JWT Authentication Implementation** — Add JWT auth middleware
6. **Outbox Background Worker** — Implement polling worker for outbox events
7. **Docker Compose** — Local development environment with PostgreSQL, Redis
8. **CI/CD Pipeline** — GitHub Actions workflow (lint, test, build, scan, deploy)
9. **Monitoring/Alerting** — Grafana dashboards, OpenTelemetry visualization
10. **Backup/DR/Load Testing/Secrets** — Production readiness items
11. **Kubernetes/Helm/ArgoCD** — Production deployment infrastructure