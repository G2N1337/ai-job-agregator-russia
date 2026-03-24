# Plan

## Goal
Build a production-ready MVP that collects relevant fullstack vacancies, normalizes and deduplicates them, scores them against the target resume, persists results in PostgreSQL, sends Telegram notifications, and exposes REST + MCP interfaces.

## Architecture choice
- Stack: FastAPI + SQLAlchemy + Alembic + PostgreSQL + Redis + APScheduler + aiogram + Python MCP server
- Rationale:
  - Fast delivery for mixed API + HTML adapters
  - Strong typing with Pydantic v2 and SQLAlchemy 2.0
  - Easy async IO for collectors, Telegram, and API
  - Good fit for lightweight MCP server in Python

## Delivery phases
1. Project bootstrap
   - Create repository structure
   - Configure Python tooling, linting, formatting, Docker Compose, Makefile, env example
   - Add base docs: README, DECISIONS, TASKS, PROGRESS
2. Data model and persistence
   - SQLAlchemy models
   - Alembic migration
   - Repositories and session management
   - Demo seed data and bootstrap command
3. Collection pipeline
   - Unified source adapter interface
   - HH adapter via public API
   - Hirify adapter via public page parsing
   - Experimental parsers for SuperJob and Rabota.ru with graceful degradation
   - Normalization, checkpoints, source error tracking, retries, timeouts
4. Matching logic
   - Configurable YAML scoring profile
   - Keyword extraction
   - Deduplication by source/external ID, canonical URL, pragmatic fingerprint
   - Explainable score reasons
5. Delivery channels
   - Telegram notifier with callbacks for statuses
   - APScheduler periodic collection job
   - Notification idempotency and thresholding
6. Service interfaces
   - REST API with OpenAPI
   - MCP server tools for agents
7. Quality and verification
   - Unit tests for scoring and deduplication
   - Integration tests for API and collectors in demo mode
   - Final docs and operational notes

## MVP scope decisions
- Fully working adapters in MVP:
  - HH.ru: public API
  - Hirify: public HTML parsing
- Experimental adapters:
  - SuperJob: parsing fallback, guarded by feature flag
  - Rabota.ru: parsing fallback, guarded by feature flag
- Scheduler runs in-process for MVP; can be split later into a worker service.
- Telegram bot supports callback-based status changes and basic preference feedback hooks.

## Completion criteria
- Local `docker compose up --build` starts API, Postgres, Redis
- `make init-db` creates schema
- `make demo-collect` ingests demo or live vacancies
- REST API serves docs and job endpoints
- MCP server exposes requested tools
- Tests and linters pass locally
