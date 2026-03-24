from __future__ import annotations

from fastapi.encoders import jsonable_encoder
from mcp.server.fastmcp import FastMCP

from job_matcher.api.dependencies import build_container
from job_matcher.core.config import get_settings, get_telegram_source_channels
from job_matcher.db.session import AsyncSessionLocal
from job_matcher.services.bootstrap import bootstrap_defaults

settings = get_settings()
container = build_container(settings, AsyncSessionLocal)
mcp = FastMCP(
    name="ai-job-aggregator",
    instructions="MCP tools for collecting, scoring and managing matched jobs.",
    host=settings.mcp_host,
    port=settings.mcp_port,
)


@mcp.tool()
async def collect_jobs(source: str | None = None) -> dict:
    await bootstrap_defaults(
        AsyncSessionLocal,
        [
            name
            for name in container.collection_service.collectors.keys()
            if name not in {"demo", "telegram"}
        ],
        telegram_channels=get_telegram_source_channels(settings),
    )
    return await container.collection_service.collect_all(source)


@mcp.tool()
async def list_new_jobs(limit: int = 20) -> dict:
    items, total = await container.job_service.list_jobs(
        status="new",
        min_score=None,
        source=None,
        include_duplicates=False,
        limit=limit,
        offset=0,
    )
    return {"total": total, "items": jsonable_encoder(items)}


@mcp.tool()
async def list_top_matches(limit: int = 20, min_score: int | None = None) -> dict:
    items, total = await container.job_service.list_jobs(
        status=None,
        min_score=min_score or settings.match_score_threshold,
        source=None,
        include_duplicates=False,
        limit=limit,
        offset=0,
    )
    return {"total": total, "items": jsonable_encoder(items)}


@mcp.tool()
async def score_job(job_id: int) -> dict:
    job = await container.job_service.get_job(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")
    return {"job_id": job.id, "score": job.score, "reasons": job.score_reasons}


@mcp.tool()
async def rescore_recent_jobs(limit: int = 100) -> dict:
    rescored = await container.job_service.rescore_recent_jobs(limit=limit)
    return {"rescored": rescored}


@mcp.tool()
async def mark_job_status(job_id: int, status: str, note: str | None = None) -> dict:
    job = await container.job_service.mark_status(job_id=job_id, status=status, note=note, source="mcp")
    return {"job_id": job.id, "status": job.status}


@mcp.tool()
async def get_job_details(job_id: int) -> dict:
    job = await container.job_service.get_job(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")
    return jsonable_encoder(job)


@mcp.tool()
async def get_search_stats() -> dict:
    return (await container.job_service.get_stats()).model_dump()


@mcp.tool()
async def update_scoring_profile(name: str, rules_yaml: str, activate: bool = True) -> dict:
    await container.job_service.update_scoring_profile(name=name, rules_yaml=rules_yaml, activate=activate)
    return {"updated": True, "name": name, "activate": activate}


@mcp.tool()
async def run_source_adapter(source: str) -> dict:
    return await container.collection_service.collect_all(source)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
