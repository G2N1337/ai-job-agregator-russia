from __future__ import annotations

import argparse
import asyncio

from job_matcher.api.dependencies import build_container
from job_matcher.core.config import get_settings, get_telegram_source_channels
from job_matcher.db.session import AsyncSessionLocal
from job_matcher.services.bootstrap import bootstrap_defaults


async def _run_collect(source: str | None) -> None:
    settings = get_settings()
    container = build_container(settings, AsyncSessionLocal)
    await bootstrap_defaults(
        AsyncSessionLocal,
        [
            name
            for name in container.collection_service.collectors.keys()
            if name not in {"demo", "telegram"}
        ],
        telegram_channels=get_telegram_source_channels(settings),
    )
    result = await container.collection_service.collect_all(source)
    print(result)
    await container.http_client.close()
    await container.redis_client.aclose()


async def _run_seed_demo() -> None:
    await _run_collect("demo")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Job Aggregator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--source", default=None)
    collect_parser.add_argument("--demo", action="store_true")

    subparsers.add_parser("seed-demo")

    args = parser.parse_args()

    if args.command == "collect":
        source = "demo" if args.demo else args.source
        asyncio.run(_run_collect(source))
        return
    if args.command == "seed-demo":
        asyncio.run(_run_seed_demo())


if __name__ == "__main__":
    main()
