# Ticket Genius

A production-grade ticketing platform built with Python and Flask that aggregates events from Ticketmaster Discovery API v2 and enables ticket purchases. Follows Cosmic Python architecture (DDD + Hexagonal + CQRS + Event-Driven/Outbox).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Flask App (app.py)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    API Layer (entrypoints)                   │
│  • register_routes() - Flask Blueprint with REST endpoints   │
│  • bootstrap() - Dependency injection & wiring               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Service Layer (service_layer)              │
│  • Commands/Queries (CQRS)                                   │
│  • Handlers - Business logic orchestration                   │
│  • MessageBus - Dispatches commands/queries to handlers      │
│  • UnitOfWork - Transaction boundary abstraction             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     Domain Layer (domain)                    │
│  • Order, Payment, Plan - Aggregate roots                    │
│  • Value Objects (Money, Seat, DateRange, etc.)              │
│  • Domain Events (OrderCreated, PaymentConfirmed, etc.)      │
│  • Repository Interfaces (Abstract)                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Adapters (adapters)                        │
│  • SqlAlchemyOrderRepository - PostgreSQL persistence        │
│  • TicketmasterAdapter - External API integration            │
│  • PaymentAdapter - Simulated/Stripe payment port            │
│  • SqlAlchemyUnitOfWork / InMemoryUnitOfWork                 │
│  • ORM Mapping (SQLAlchemy imperative)                       │
└──────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Project info |
| GET | `/health` | Health check |
| POST | `/api/v1/orders` | Create order |
| POST | `/api/v1/orders/{id}/confirm-payment` | Confirm payment |
| GET | `/api/v1/orders/{id}` | Get order status |
| DELETE | `/api/v1/orders/{id}` | Cancel order |
| GET | `/api/v1/plans/search` | Search plans/events |
| GET | `/api/v1/plans/{id}` | Get plan details |

## Quick Start

### Prerequisites
- Python 3.14+
- PostgreSQL
- Redis

### Setup
```bash
# Clone and enter project
git clone <repo-url>
cd ticket-genius

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure database (edit .env)
DATABASE_URL=postgresql://user:pass@localhost:5432/ticket_genius
REDIS_URL=redis://localhost:6379/0
TM_API_KEY=your_ticketmaster_key
TM_API_SECRET=your_ticketmaster_secret

# Run server
invoke start
# Or directly: python app.py
```

Server runs at `http://localhost:5000`

### Development Commands (via Invoke)
```bash
invoke start          # Start server (waits until ready)
invoke stop           # Stop server
invoke restart        # Restart server
invoke debug          # Start with debug/reload
invoke watch          # Auto-restart on file changes
invoke test           # Run all tests
invoke test -v        # Verbose
invoke test --coverage # With coverage report
invoke test --unit    # Unit tests only
invoke test --integration # Integration tests only

# Admin CLI commands
invoke cli -- --help           # Show all CLI commands
invoke sync-plans              # Sync plans from Ticketmaster
invoke sync-plans --full       # Full sync from beginning
invoke purge-cache             # Purge Redis cache
invoke toggle-flag FLAG on     # Enable feature flag
invoke health-check            # Run health checks
```

## Testing

Tests use a separate database (`ticket_genius_test`) with transactional isolation - each test runs in a rolled-back transaction.

```bash
# Create test database (one-time)
createdb ticket_genius_test
psql -d ticket_genius_test -c "GRANT ALL ON SCHEMA public TO ticket_genius;"

# Run tests
invoke test
invoke test --coverage
```

## Key Patterns Implemented

- **Clean Architecture** - Domain independent of frameworks
- **DDD** - Rich domain models with aggregates and value objects
- **CQRS** - Separate Commands (writes) and Queries (reads)
- **Hexagonal Architecture** - Ports and adapters
- **Event-Driven/Outbox** - Domain events stored in outbox table
- **Unit of Work** - Transaction management abstraction
- **Repository Pattern** - Swappable persistence
- **Domain Events** - Decoupled side effects
- **Value Objects** - Self-validating domain primitives
- **Dependency Injection** - python-dependency-injector

## Project Structure

```
ticket-genius/
├── app.py                    # Flask application factory
├── tasks.py                  # Invoke tasks (start, stop, test, etc.)
├── requirements.txt          # Dependencies
├── .env                      # Database URL (not committed)
├── .env.test                 # Test database URL
├── domain/                   # Pure domain logic
│   ├── model.py              # Order, Payment, Plan aggregates
│   ├── value_objects.py      # Money, Seat, DateRange, etc.
│   ├── events.py             # Domain events
│   ├── repositories.py       # Repository interfaces (ports)
│   └── exceptions.py         # Domain exceptions
├── service_layer/            # Application services
│   ├── commands.py           # Write operations
│   ├── queries.py            # Read operations
│   ├── handlers.py           # Command/query handlers
│   ├── messagebus.py         # Dispatcher
│   └── unit_of_work.py       # UoW abstraction
├── adapters/                 # Infrastructure
│   ├── orm.py                # SQLAlchemy mapping
│   ├── repository.py         # Repository implementations
│   ├── unit_of_work.py       # UoW implementations
│   ├── ticketmaster.py       # Ticketmaster API adapter
│   └── payment.py            # Payment adapter (simulated/Stripe)
├── entrypoints/              # API & bootstrap
│   ├── api.py                # Flask routes
│   ├── schemas.py            # Pydantic schemas
│   └── bootstrap.py          # DI container
├── cli/                      # Admin CLI
│   └── commands.py           # Click commands
└── tests/                    # Pytest suite
    ├── conftest.py           # Test fixtures (DB isolation)
    ├── test_api.py           # Integration tests
    ├── test_bootstrap.py     # Wiring tests
    ├── test_domain.py        # Domain unit tests
    └── test_service_layer.py # Service layer tests
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `TM_API_KEY` | Ticketmaster API key | Required |
| `TM_API_SECRET` | Ticketmaster API secret | Required |
| `FLASK_DEBUG` | Enable debug mode | `0` |
| `FLASK_APP` | Flask app module | `app.py` |

## License

MIT