# Swagger UI with Pydantic v2 Models

**Context**: The project uses Pydantic v2 models for request/response validation. Flask-apispec with marshmallow 3.x has compatibility issues with Pydantic v2 models - the `marshal_with` and `use_kwargs` decorators fail with `TypeError: BaseModel.__init__() takes 1 positional argument but 2 were given`.

**Decision**: 
1. Keep Pydantic v2 models for request/response validation (superior developer experience, performance)
2. Use flask-apispec only for OpenAPI spec generation (not for runtime marshaling)
3. Implement custom decorators for Pydantic validation/serialization
4. Generate OpenAPI spec manually (YAML file) for contract testing

**Consequences**:
- Swagger UI at `/docs` will use manual OpenAPI YAML spec
- Runtime validation uses Pydantic directly in route handlers
- OpenAPI spec at `/openapi.json` serves the manual YAML spec
- Contract tests use the manual OpenAPI YAML spec

**Status**: In progress - fix Swagger UI endpoint