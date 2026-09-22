"""A tiny real model-serving FastAPI app, instrumented with prometheus_client.

This is intentionally a stand-in for lab 2's container-deploy app (this lab is buildable and
gradable on its own): a trivial "model" (mean of the input features, scaled) behind /predict,
a real /health endpoint, and a real /metrics endpoint that a real Prometheus container scrapes.

``simulate_latency_seconds`` on /predict is not a hack for its own sake - it is how the automated
test induces a REAL wall-clock latency spike (an actual ``time.sleep`` inside the request handler)
so the p95-latency Prometheus alert fires on real histogram data instead of being asserted by hand.
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

from lab import metrics

REFERENCE_MEAN = 0.0  # the "training-time" mean this trivial model was fit against


class PredictRequest(BaseModel):
    features: list[float] = Field(..., min_length=1, max_length=64)
    simulate_latency_seconds: float = Field(0.0, ge=0.0, le=10.0)


class PredictResponse(BaseModel):
    prediction: float
    drift_score: float
    model_version: str = "v1"


def create_app() -> FastAPI:
    app = FastAPI(title="mlops-real-monitoring-stack demo model", version="1.0.0")

    @app.middleware("http")
    async def prometheus_middleware(request, call_next):
        # TODO 7: time the call to call_next(request) with time.perf_counter(), call
        #         metrics.record_request(method, endpoint, status_code, duration) both on the
        #         success path and (with status_code=500) if call_next raises, then re-raise.
        raise NotImplementedError

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/predict", response_model=PredictResponse)
    def predict(payload: PredictRequest) -> PredictResponse:
        # TODO 8: sleep for payload.simulate_latency_seconds if > 0, compute
        #         prediction = mean(features) * 2.0, call metrics.update_drift(features,
        #         REFERENCE_MEAN) for the drift score, and return a PredictResponse.
        raise NotImplementedError

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        # TODO 9: return Response(content=body, media_type=content_type) from
        #         metrics.render_latest().
        raise NotImplementedError

    return app


app = create_app()
