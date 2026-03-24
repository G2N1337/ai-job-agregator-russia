from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from job_matcher.api.dependencies import AppContainer, get_container
from job_matcher.schemas.api import (
    JobListResponse,
    JobResponse,
    RescoreResponse,
    RunCollectionResponse,
    SearchQueryResponse,
    StatsResponse,
    StatusUpdateRequest,
    UpdateScoringProfileRequest,
)

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    min_score: int | None = None,
    source: str | None = None,
    include_duplicates: bool = False,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    container: AppContainer = Depends(get_container),
) -> JobListResponse:
    items, total = await container.job_service.list_jobs(
        status=status_filter,
        min_score=min_score,
        source=source,
        include_duplicates=include_duplicates,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(items=[JobResponse.model_validate(item) for item in items], total=total)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, container: AppContainer = Depends(get_container)) -> JobResponse:
    job = await container.job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse.model_validate(job)


@router.post("/jobs/{job_id}/status", response_model=JobResponse)
async def mark_job_status(
    job_id: int,
    payload: StatusUpdateRequest,
    container: AppContainer = Depends(get_container),
) -> JobResponse:
    try:
        job = await container.job_service.mark_status(
            job_id=job_id,
            status=payload.status,
            note=payload.note,
            source=payload.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JobResponse.model_validate(job)


@router.post("/jobs/rescore", response_model=RescoreResponse)
async def rescore_recent_jobs(
    limit: int = Query(default=100, le=1000),
    container: AppContainer = Depends(get_container),
) -> RescoreResponse:
    rescored = await container.job_service.rescore_recent_jobs(limit=limit)
    return RescoreResponse(rescored=rescored)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(container: AppContainer = Depends(get_container)) -> StatsResponse:
    return await container.job_service.get_stats()


@router.post("/collect/run", response_model=RunCollectionResponse)
async def run_collection(
    source: str | None = None, container: AppContainer = Depends(get_container)
) -> RunCollectionResponse:
    await container.collection_service.collect_all(source)
    return RunCollectionResponse(started=True, source=source, message="Collection finished")


@router.get("/search-queries", response_model=list[SearchQueryResponse])
async def list_search_queries(container: AppContainer = Depends(get_container)) -> list[SearchQueryResponse]:
    async with container.session_factory() as session:
        from sqlalchemy import select

        from job_matcher.models.source import SearchQuery

        queries = (await session.scalars(select(SearchQuery).order_by(SearchQuery.source, SearchQuery.priority))).all()
        return [SearchQueryResponse.model_validate(item) for item in queries]


@router.put("/scoring-profile", status_code=status.HTTP_204_NO_CONTENT)
async def update_scoring_profile(
    payload: UpdateScoringProfileRequest,
    container: AppContainer = Depends(get_container),
) -> None:
    await container.job_service.update_scoring_profile(
        name=payload.name,
        rules_yaml=payload.rules_yaml,
        activate=payload.activate,
    )
