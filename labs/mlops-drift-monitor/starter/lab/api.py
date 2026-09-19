"""HTTP endpoints (starter). ``create_app`` (lab/app.py) stores ``monitor``, ``metrics`` and ``timer`` on ``app.state``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response  # noqa: F401

from lab.monitor import BatchValidationError  # noqa: F401
from lab.schemas import IngestRequest, IngestResponse

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    """TODO:
    - ``started = request.app.state.timer()``
    - ``summary = monitor.ingest(body.rows)``; ``BatchValidationError`` -> ``HTTPException(422, detail=exc.problems)``
      (a rejected batch must NOT touch the metrics)
    - if ``summary.evaluated``: ``metrics.update_features(summary.results)``
    - ``metrics.observe_ingest(summary.accepted, timer() - started)``
    - return ``IngestResponse(accepted, window_rows, evaluated, alerting)``
    """
    raise NotImplementedError("TODO: /ingest")


@router.get("/metrics")
def prometheus_metrics(request: Request) -> Response:
    """TODO: ``body, content_type = metrics.render()`` and return ``Response(content=body, media_type=content_type)``."""
    raise NotImplementedError("TODO: /metrics")


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    """TODO: return ``monitor.status()``."""
    raise NotImplementedError("TODO: /status")
