"""The FastAPI model server you are shipping.

The model itself, its loading, and the request/response schemas are provided (``model.py``,
``schemas.py``) - the ``/predict`` route below is the reference implementation of README task 1.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.model import FEATURE_NAMES, load_model
from app.schemas import PredictRequest, PredictResponse

app = FastAPI(title="iris-model-server", version="1.0.0")

# Loaded once, at process startup (module import time) - not on every request.
_model = load_model()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _model is not None}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    """Predict the iris species for one flower's measurements."""
    if _model is None:
        raise HTTPException(status_code=503, detail="model not loaded - the image was built without a model artifact")

    classifier = _model["classifier"]
    target_names = _model["target_names"]

    # FEATURE_NAMES fixes the column order the classifier was trained on.
    row = [[getattr(payload, name) for name in FEATURE_NAMES]]

    predicted_index = int(classifier.predict(row)[0])
    probabilities = classifier.predict_proba(row)[0]

    return PredictResponse(
        predicted_class=target_names[predicted_index],
        predicted_class_index=predicted_index,
        probabilities={name: float(p) for name, p in zip(target_names, probabilities, strict=True)},
    )
