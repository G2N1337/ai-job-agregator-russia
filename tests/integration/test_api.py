from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from job_matcher.models.job import Job


@pytest.mark.asyncio
async def test_list_jobs_endpoint(test_app, seeded_job: Job) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/jobs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == seeded_job.title


@pytest.mark.asyncio
async def test_mark_status_endpoint(test_app, seeded_job: Job) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            f"/jobs/{seeded_job.id}/status",
            json={"status": "applied", "note": "Sent CV", "source": "api"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "applied"
