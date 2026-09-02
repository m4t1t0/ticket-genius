# Ticket Genius - AI Agent Instructions

## Project Overview
This project is a production-grade REST API built with Python and Flask that consumes the Ticketmaster Discovery API v2. It serves as the backend for a separate frontend application written in **Vue.js**. The codebase follows professional, production-ready standards.

## Architecture & Design Patterns
The project will strictly follow the conventions and structure outlined in the **Cosmic Python** book:
- **Domain-Driven Design (DDD):** Clear separation of the core domain model from infrastructure.
- **Provider-Agnostic Domain Model:** The core domain entities (e.g., `Concert`, `Venue`, `Artist`, `PriceRange`) must remain 100% agnostic of Ticketmaster or any third-party event provider. Ticketmaster is treated merely as one of several potential ingestion adapters. Translation layers/mappers will convert provider-specific payloads into standard domain models.
- **Hexagonal Architecture:** Use ports and adapters to isolate the domain from external concerns (web frameworks, databases, message buses).
- **CQRS:** Separate read operations (queries) from write operations (commands).
- **Event-Driven & Outbox Pattern:** The system will write domain events to a dedicated `events` table (Outbox Pattern) within the same transaction as business data. A separate CDC (Change Data Capture) process or background worker will read this table and forward events to a message broker like **Apache Kafka**.

## API Design & Integrations
- **Translation Layer:** Use **Marshmallow** schemas at the API boundaries (entrypoints) to handle validation, serialization, and deserialization. This ensures the pure domain models remain completely decoupled from HTTP/JSON concerns while strictly enforcing the `snake_case` API contract.
- **API Contracts:** Standardize JSON payloads and URLs strictly using `snake_case` to ensure high HTTP friendliness and a 1:1 mapping with Python's PEP-8 conventions for seamless Vue.js integration.
- **Payments:** The checkout and payment process will be simulated initially. The architecture must use interfaces/ports for payments so that integrating a real service (like Stripe) later requires minimal refactoring.

## Database & Data Modeling
- **Primary Database:** **PostgreSQL** exclusively. There will be no in-memory repositories.
- **Data Model:** Design a normalized, provider-agnostic relational schema for core entities (Concerts, Venues, Artists, Ticket Links). Ticketmaster and future providers (e.g., Eventbrite, SeatGeek) will map into this canonical schema via ingestion adapters.
- **Caching:** Use **Redis** as the caching layer to mitigate the Ticketmaster API rate limits and improve query read performance.

## Coding Standards & Conventions
When writing or refactoring Python code, please adhere to the following patterns:
- **Data Structures:** Prefer list and dictionary comprehensions for efficient data manipulation when mapping API responses to domain models.
- **Type Hinting:** Strictly type all functions. Utilize `TypeVar` and Generics for generic repositories, message handlers, or utility classes.
- **Object-Oriented Design:** Implement robust models. Use `@classmethod` for alternative constructors or factory methods (e.g., `Event.from_ticketmaster_json(data)`).
- **Debugging:** Ensure every domain class implements a clear and descriptive `__repr__` method.

## Target Milestones for Next Session
1. Scaffold the Cosmic Python directory structure (`domain`, `adapters`, `service_layer`, `entrypoints`).
2. Implement the Provider-Agnostic Core Domain Models (`Concert`, `Venue`, `Artist`, etc.) using pure Python `dataclasses`.
3. Create the Marshmallow schemas to translate Ticketmaster's payload into the pure domain models.
4. Set up the PostgreSQL relational schema and implement the Repository and Unit of Work patterns using SQLAlchemy Imperative Mapping.
5. Set up the Outbox `events` table and write a simulated command that successfully persists a domain event.