# Authentication Method for API

**Context**: The API endpoints need authentication for production. Initial release will have no auth (public endpoints), but we must decide on the auth mechanism before exposing to real users.

**Decision**: Defer to ADR. Options to evaluate:
- JWT (stateless, standard, good for microservices)
- API Keys (simple, good for server-to-server)
- OAuth 2.0 / OIDC (delegated auth, integrates with identity providers)
- Session cookies (traditional, requires CSRF protection)

**Trade-offs**:
- JWT: stateless, scales well, but token revocation requires blocklist or short expiry + refresh tokens
- API Keys: simplest to implement, but less secure if leaked, no user context
- OAuth/OIDC: most flexible for user-facing apps, but adds complexity (identity provider needed)
- Sessions: simple for monolith, but requires sticky sessions or shared store in distributed setup

**Next Steps**: Create spike/prototype for JWT vs OAuth before Milestone 2. Decision needed before removing "no auth" from initial release.