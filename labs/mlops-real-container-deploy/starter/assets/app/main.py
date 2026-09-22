"""The FastAPI model server you are shipping.

The model itself, its loading, and the request/response schemas are provided (``model.py``,
``schemas.py``) - your job is the ``/predict`` route below, plus the Dockerfile (see the README).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.model import load_model
from app.schemas import PredictRequest, PredictResponse

app = FastAPI(title="iris-model-server", version="1.0.0")

# Loaded once, at process startup (module import time) - not on every request.
_model = load_model()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _model is not None}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    """Predict the iris species for one flower's measurements.

    TODO:
    1. If the model failed to load (``_model is None``), raise ``HTTPException(status_code=503, ...)``
       instead of crashing - a caller should get a clear "not ready" response, not an unhandled error.
    2. Build the feature row in the SAME order ``app.model.FEATURE_NAMES`` documents
       (sepal_length, sepal_width, petal_length, petal_width) - scikit-learn cares about column order,
       not column names.
    3. Call ``_model["classifier"].predict(...)`` for the predicted class index and
       ``.predict_proba(...)`` for the per-class probabilities.
    4. Map the predicted index to its class name via ``_model["target_names"]``, and build the
       ``probabilities`` dict keyed by class name (not by index).
    5. Return a ``PredictResponse``. See ``schemas.py`` for the exact field names.
    """
    raise NotImplementedError("predict is not implemented yet - see the TODO above and README task 1")
