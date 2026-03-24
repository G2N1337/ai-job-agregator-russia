SHELL := /bin/zsh

.PHONY: install lint format test run migrate init-db demo-collect demo-seed

install:
	uv sync --extra dev

lint:
	uv run ruff check .
	uv run mypy src

format:
	uv run ruff check . --fix
	uv run ruff format .

test:
	uv run pytest

run:
	uv run uvicorn job_matcher.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	uv run alembic upgrade head

init-db: migrate

demo-collect:
	uv run python -m job_matcher.cli collect --demo

demo-seed:
	uv run python -m job_matcher.cli seed-demo
