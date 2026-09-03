# Ticket Genius - Agent Instructions

## Run the App
```bash
source .venv/bin/activate
python app.py
```
Runs on http://localhost:5000

## Invoke Commands (Recommended)
```bash
source .venv/bin/activate
python -m invoke start      # Start server (waits until ready)
python -m invoke stop       # Stop server
python -m invoke restart    # Restart server
python -m invoke --list     # List all tasks
```

## Install Dependencies
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Project Structure
- `app.py` - Application factory with Flask app creation
- `tasks.py` - Invoke tasks for start/stop/restart
- `requirements.txt` - Dependencies (flask, invoke, requests, sqlalchemy, marshmallow, pydantic, redis, httpx, alembic, etc.)
- `.venv/` - Virtual environment (already exists)
- `domain/` - Core domain models (Concert, Venue, Artist, etc.)
- `adapters/` - Infrastructure adapters (Ticketmaster, SQLAlchemy repos, Redis, Payment)
- `service_layer/` - Use cases / application services
- `entrypoints/` - HTTP entrypoints (Flask routes, Marshmallow schemas)

## Notes
- Uses Python 3.14 (from .venv)
- Architecture: Cosmic Python (DDD + Hexagonal + CQRS + Event-Driven/Outbox)
- Database: PostgreSQL with SQLAlchemy Imperative Mapping + Alembic migrations
- Caching: Redis for Ticketmaster rate limit mitigation and read performance
- Message Bus: Outbox pattern with deferred background worker (Kafka-ready) — see ADR-0002
- Testing: pytest with unit, integration, and contract tests
- No CI/CD workflows configured yet
- Default port: 5000 (configurable via `invoke start --port=8080`)
- Debug mode off by default for background runs (use `--debug=true` to enable)