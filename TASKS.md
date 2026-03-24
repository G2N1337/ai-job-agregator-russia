# Tasks

## In Progress
- [ ] None

## Completed
- [x] Add Python tooling, Docker, Makefile, environment configuration
- [x] Implement SQLAlchemy models and Alembic migration
- [x] Implement scoring profile loader and explainable scoring engine
- [x] Implement deduplication service
- [x] Implement source adapters: HH, Hirify, SuperJob API, Rabota.ru experimental, demo
- [x] Implement collection orchestration with checkpoints and source error isolation
- [x] Implement Telegram bot and notification workflow
- [x] Implement REST API endpoints and OpenAPI tags
- [x] Implement MCP server tools
- [x] Add tests, demo mode, and final documentation
- [x] Add Telegram channel source in TDLib client mode with checkpoints and message persistence

## Follow-up
- [ ] Improve Hirify detail extraction via public API if a stable endpoint is confirmed
- [ ] Add Redis-backed preference learning for `more like this` / `less like this`
- [ ] Split scheduler and bot polling into dedicated worker services for production scaling
- [ ] Add explicit CLI workflow for first-time TDLib authorization code entry without env vars
