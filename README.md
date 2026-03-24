# AI Job Aggregator

Production-ready MVP for collecting new fullstack вакансии, normalizing them into one schema, deduplicating across sources, scoring them against a target profile, storing history in PostgreSQL, notifying via Telegram, and exposing both REST and MCP interfaces.

Current search scope:
- only vacancies in Russia are kept and persisted
- non-Russian vacancies are filtered out before saving and notifying

## Stack
- Backend: FastAPI
- DB: PostgreSQL + SQLAlchemy 2.0 + Alembic
- Scheduler: APScheduler
- Cache/lock: Redis
- Telegram: aiogram
- MCP: Python `FastMCP`
- Tooling: `uv`, `ruff`, `mypy`, `pytest`, Docker Compose

## What is implemented
- Unified vacancy model with required fields:
  - `source`, `external_id`, `source_url`, `title`, `company_name`, `city`, `country`
  - `remote_mode`, `employment_type`, `experience_level`
  - `salary_from`, `salary_to`, `salary_currency`
  - `published_at`, `collected_at`
  - `description_raw`, `description_text`
  - `tech_tags_extracted`, `search_query`, `fingerprint`, `language`
- PostgreSQL schema and migration for:
  - `jobs`
  - `job_snapshots`
  - `source_checkpoints`
  - `user_feedback`
  - `notifications`
  - `application_statuses`
  - `scoring_profiles`
  - `search_queries`
  - `source_errors`
- Collectors with a single interface:
  - `hh`: public HH API
  - `hirify`: public sitemap feed + detail page parsing
  - `superjob`: official API, requires `SUPERJOB_API_KEY`
  - `rabota`: public HTML parsing, experimental
  - `demo`: deterministic local/demo source
- Explainable scoring engine with YAML rules
- Pragmatic deduplication:
  - exact: `source + external_id`
  - exact: canonical URL
  - fingerprint match
  - fuzzy title/company/description fallback with RapidFuzz
- Scheduler and collection orchestration with per-source isolation
- Telegram notifications with inline actions:
  - `Dismiss`
  - `Applied`
  - `Save`
  - `More like this`
  - `Less like this`
- REST API with OpenAPI
- MCP server tools for future agent workflows
- Demo mode and tests

## Source strategy
| Source | Strategy | Status |
|---|---|---|
| HH.ru | Public API | working |
| Hirify | Public sitemap + detail page parsing | working |
| SuperJob | Official API with app key | working when key is configured |
| Rabota.ru | Public HTML parsing | experimental, behind feature flag |
| Telegram channels | TDLib client mode with user authorization | working when TDLib is installed and configured |

Notes:
- The service prefers API/feed-based access when available.
- SuperJob search currently requires an application key; without it the adapter is skipped cleanly.
- Rabota.ru and parts of Hirify depend on public markup and may require maintenance if page structure changes.
- Telegram channel reading in this project uses client mode via TDLib, not Bot API, for channels the bot does not belong to.

## Telegram source
Implemented behavior:
- input channels are accepted as `@channelusername` or `https://t.me/channelusername`
- public channels are resolved through TDLib `searchPublicChat`
- the resolved `chat_id` is persisted
- channel history is read through TDLib `getChatHistory`
- per-channel checkpoints are stored in `telegram_channels`
- every fetched message is stored in `telegram_messages`
- messages are passed through:
  - parse
  - vacancy/non-vacancy classification
  - normalization
  - deduplication
  - scoring
  - notification

Stored per channel:
- `query`
- `channel_username`
- `channel_title`
- `chat_id`
- `last_message_id`
- `last_checked_at`

Stored per message:
- `source=telegram`
- `chat_id`
- `channel_username`
- `channel_title`
- `message_id`
- `post_url`
- `posted_at`
- `raw_text`
- `extracted_links`
- `parsed_fields`
- `is_vacancy`

Private channel limitation:
- private channels are supported only when the authorized user account already has access
- public username resolution works only for public channels
- invite links and channels inaccessible to the account are intentionally out of scope for this MVP

Bot API note:
- Bot API is suitable only for chats/channels where the bot is already present
- reading чужие публичные каналы without adding a bot requires Telegram client mode, which is why this source uses TDLib

## Scoring model
The score is `0..100`, with explainability stored alongside each job.

Main positives:
- strong title alignment to `fullstack`, `react`, `next.js`, `node.js`, `nestjs`, `typescript`
- strong boosts for `TypeScript/React/Next.js` and `Node.js/NestJS` groups
- bonuses for `PostgreSQL`, `Redis`, `Docker`, `GraphQL`, `Prisma`, `RabbitMQ`, `Kafka`, `AWS`, `Serverless`
- bonuses for `e-commerce`, `marketplace`, `fintech`, `SaaS`, `analytics`, `Telegram Mini Apps`, `API integrations`, `performance optimization`
- remote preference

Main penalties:
- `1C`, `Bitrix`, `QA`, `support`, `DevOps-only`, `pure PHP`, `Java backend`
- office-only
- strong seniority mismatch

Rules live in [`config/scoring_rules.yaml`](/Users/yan/projects/pet-projects/ai-job-agregator/config/scoring_rules.yaml).

## Repository layout
```text
src/job_matcher/
  api/           REST routes and dependency wiring
  collectors/    Source adapters
  core/          Settings, logging, HTTP client, constants
  db/            Base metadata and Alembic migrations
  mcp/           MCP server
  models/        SQLAlchemy models
  repositories/  DB access helpers
  schemas/       Pydantic contracts
  scoring/       Explainable scoring engine
  services/      Collection orchestration, scheduler, notifications
  telegram/      Bot and callback handlers
  utils/         Text/date/extraction helpers
tests/
config/
```

## Environment
Start from [`.env.example`](/Users/yan/projects/pet-projects/ai-job-agregator/.env.example).

Important variables:
- `DATABASE_URL`
- `ASYNC_DATABASE_URL`
- `REDIS_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_SOURCE_ENABLED`
- `TELEGRAM_SOURCE_CHANNELS`
- `TELEGRAM_TDLIB_API_ID`
- `TELEGRAM_TDLIB_API_HASH`
- `TELEGRAM_TDLIB_PHONE_NUMBER`
- `TELEGRAM_TDLIB_AUTH_CODE`
- `TELEGRAM_TDLIB_PASSWORD`
- `TELEGRAM_TDJSON_LIB_PATH`
- `SUPERJOB_API_KEY`
- `ENABLE_DEMO_MODE`
- `ENABLE_EXPERIMENTAL_ADAPTERS`
- `MATCH_SCORE_THRESHOLD`

Connection rule:
- when you run commands from the host machine, use `localhost`
- inside `docker compose`, services use `db` and `redis`

## Local run
### Option 1: Docker Compose
1. Copy env:
   - `cp .env.example .env`
2. Start infra:
   - `docker compose up -d db redis`
3. Install local deps:
   - `uv sync --extra dev`
4. Apply migrations:
   - `uv run alembic upgrade head`
5. Run API:
   - `uv run uvicorn job_matcher.main:app --reload --host 0.0.0.0 --port 8000`
6. Run MCP server in another shell:
   - `uv run python -m job_matcher.mcp.server`

### Option 2: Compose full stack
1. `cp .env.example .env`
2. `docker compose up --build`

## Useful commands
- `make install`
- `make lint`
- `make test`
- `make init-db`
- `make run`
- `make demo-collect`
- `make demo-seed`

## Demo mode
If real credentials are not configured:
- `demo` collector can seed relevant sample vacancies
- Telegram notifications are simulated and recorded as sent
- REST/MCP flows still work end-to-end

Use:
- `uv run python -m job_matcher.cli collect --demo`

## Scheduler behavior
- Default interval: every 20 minutes
- Source locks use Redis to prevent overlapping collection runs
- Checkpoints are stored per `source + query`
- Re-discovered jobs update `last_seen_at` and snapshot history
- Already notified jobs are not re-notified

## REST API
OpenAPI/Swagger is available at:
- [http://localhost:8000/docs](http://localhost:8000/docs)

Main endpoints:
- `GET /health`
- `GET /ready`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/status`
- `POST /jobs/rescore`
- `GET /stats`
- `POST /collect/run`
- `GET /search-queries`
- `PUT /scoring-profile`

## MCP server
The MCP server starts on `MCP_HOST:MCP_PORT` and serves Streamable HTTP transport at `/mcp`.

Implemented tools:
- `collect_jobs`
- `list_new_jobs`
- `list_top_matches`
- `score_job`
- `rescore_recent_jobs`
- `mark_job_status`
- `get_job_details`
- `get_search_stats`
- `update_scoring_profile`
- `run_source_adapter`

Example local run:
- `uv run python -m job_matcher.mcp.server`

Typical MCP client URL:
- `http://localhost:8001/mcp`

## Telegram behavior
- Notifications are sent only for jobs with `score >= MATCH_SCORE_THRESHOLD`
- Duplicates are not notified
- Inline callbacks update status/feedback in the database
- Vacancy URL is exposed as a dedicated large inline button
- Polling starts only when `TELEGRAM_ENABLED=true` and bot credentials are present

## Tests and verification
Verified locally:
- `uv run ruff check src tests`
- `uv run pytest`
- `uv run mypy src`

## Trade-offs
- APScheduler runs in-process for MVP. A separate worker is better for larger production loads.
- Hirify detail extraction currently relies on public page parsing; a stable public API would be preferable if confirmed.
- Rabota.ru adapter is intentionally marked experimental.
- SuperJob requires a real app key for live collection.
- Telegram source requires TDLib native library installation and a user-authorized session.
- No full web admin UI yet; admin surface is REST + Swagger.

## Roadmap
- Add pg_trgm-based duplicate search in PostgreSQL for large datasets
- Split API, collector worker, and Telegram worker into separate services
- Learn scoring preferences from `more like this` / `less like this`
- Add stronger source-specific extraction and richer salary/location parsing
- Add webhook mode for Telegram in production
