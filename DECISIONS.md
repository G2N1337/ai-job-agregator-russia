# Architecture Decisions

## ADR-001: Choose FastAPI stack for MVP
- Status: accepted
- Date: 2026-03-24
- Decision:
  - Use Python with FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, PostgreSQL, Redis, APScheduler, aiogram, and a Python MCP server.
- Context:
  - The service needs async HTTP collection, HTML parsing fallbacks, Telegram integration, and an MCP layer.
  - The workspace is empty; fastest reliable delivery matters more than strict language alignment with the candidate profile.
- Consequences:
  - Faster implementation of collectors and parsing logic.
  - In-process scheduler is acceptable for MVP, with a documented path to external workers later.
  - Python MCP tooling is straightforward with `FastMCP`.

## ADR-002: Hybrid source strategy
- Status: accepted
- Date: 2026-03-24
- Decision:
  - Prefer official/public APIs first. Use public-page parsing only where practical and clearly mark unstable adapters as experimental.
- Consequences:
  - HH gets a reliable primary implementation.
  - Hirify uses public sitemap feed plus detail-page parsing, which is more stable than scraping search results.
  - SuperJob uses official API when `SUPERJOB_API_KEY` is configured.
  - Rabota.ru stays behind an explicit experimental flag because it relies on public HTML.

## ADR-003: Pragmatic deduplication
- Status: accepted
- Date: 2026-03-24
- Decision:
  - Deduplicate by `(source, external_id)` and canonical URL first, then by a normalized fingerprint plus fuzzy title/description similarity.
- Consequences:
  - Good MVP quality without heavy ML or expensive similarity search infrastructure.
  - Cross-source duplicates are preserved as rows but linked via `duplicate_of_id`, so no source visibility is lost.

## ADR-004: Config-driven scoring
- Status: accepted
- Date: 2026-03-24
- Decision:
  - Store scoring rules in YAML, with runtime override support through DB scoring profiles later.
- Consequences:
  - Simple tuning without code changes.
  - MCP/API can expose controlled updates.

## ADR-005: Graceful degradation over hard failure
- Status: accepted
- Date: 2026-03-24
- Decision:
  - Each source/query pair runs independently. Errors are recorded in `source_errors` and checkpoints, but the overall collection cycle continues.
- Consequences:
  - One broken adapter does not stop notifications from healthier sources.
  - Operational debugging remains possible from DB and logs.

## ADR-006: Demo mode must be first-class
- Status: accepted
- Date: 2026-03-24
- Decision:
  - When live credentials are unavailable, the system still works end-to-end with a `demo` collector and simulated Telegram sends.
- Consequences:
  - Local onboarding is fast and deterministic.
  - CI and tests do not depend on external job boards or Telegram.

## ADR-007: Telegram channel collection must use client mode
- Status: accepted
- Date: 2026-03-24
- Decision:
  - Use TDLib client mode with a user-authorized Telegram account for reading third-party channels.
- Context:
  - Bot API can only read channels where the bot is explicitly present.
  - The product requirement includes reading public channels the bot does not control.
- Consequences:
  - Requires native TDLib installation and user credentials (`api_id`, `api_hash`, phone number, auth flow).
  - Public channels can be resolved by username through `searchPublicChat`.
  - Private channels are only supported when the user account already has access.
