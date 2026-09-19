"""HTTP endpoints (reference solution)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from lab.monitor import BatchValidationError
from lab.schemas import IngestRequest, IngestResponse

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    monitor, metrics, timer = request.app.state.monitor, request.app.state.metrics, request.app.state.timer
    started = timer()
    try:
        summary = monitor.ingest(body.rows)
    except BatchValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.problems) from exc
    if summary.evaluated:
        metrics.update_features(summary.results)
    metrics.observe_ingest(summary.accepted, timer() - started)
    return IngestResponse(
        accepted=summary.accepted,
        window_rows=summary.window_rows,
        evaluated=summary.evaluated,
        alerting=summary.alerting,
    )


@router.get("/metrics")
def prometheus_metrics(request: Request) -> Response:
    body, content_type = request.app.state.metrics.render()
    return Response(content=body, media_type=content_type)


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    return request.app.state.monitor.status()
