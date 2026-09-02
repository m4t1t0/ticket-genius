# Outbox Background Worker Implementation

**Context**: The outbox pattern requires a background process to poll the `outbox` table and process domain events. The implementation approach impacts operations, scaling, and reliability.

**Decision**: Defer to ADR. Options to evaluate:
- In-process thread (current recommendation for simplicity)
- Separate process managed by supervisor (systemd, supervisord)
- Cron job (simple but latency = cron interval)
- CDC (Debezium) → Kafka → consumer (production-grade, adds infrastructure)
- Kubernetes CronJob / Job (if deployed on K8s)

**Trade-offs**:
- In-process: simplest, shares app memory/DB pool, but blocks if app restarts, scales with app replicas (duplicate processing risk)
- Supervisor: separate lifecycle, can scale independently, standard Linux service management
- Cron: zero infrastructure, but minimum latency = cron interval (typically 1min), no backpressure handling
- CDC/Kafka: most robust, exactly-once semantics, but requires Kafka cluster + Debezium + schema registry
- K8s Job: cloud-native, but only if on Kubernetes

**Next Steps**: Prototype in-process for Milestone 5 (simplest). Evaluate supervisor vs CDC before production release. Document decision in ADR before removing "simulation" label.