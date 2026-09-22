"""Model training and loading. (Provided - do not edit.)

The training side runs once, INSIDE the Docker builder stage, on the iris dataset that ships inside
scikit-learn itself (no network access needed to train). Only the pickled artifact - not this code's
training path, and not scikit-learn's copy of the dataset - is copied into the runtime stage. This is
the same shape as a real pipeline: train once (here, at image-build time), ship a versioned artifact,
let the serving process only ever load and predict.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression

MODEL_PATH = Path(os.environ.get("MODEL_PATH", "/srv/model/model.joblib"))
FEATURE_NAMES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]


def train() -> tuple[Any, list[str]]:
    """Train a small, fast, fully-deterministic classifier (fixed random_state) and return it with
    the human-readable class names, in prediction-index order."""
    data = load_iris()
    classifier = LogisticRegression(max_iter=200, random_state=0)
    classifier.fit(data.data, data.target)
    return classifier, list(data.target_names)


def save(classifier: Any, target_names: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"classifier": classifier, "target_names": target_names}, path)


def load_model(path: Path = MODEL_PATH) -> dict[str, Any] | None:
    """Load the artifact baked into the image at build time.

    Returns None (rather than raising) if the artifact is missing, so /health can report a clear
    "model_loaded": false instead of the process crashing at import time.
    """
    if not path.is_file():
        return None
    return joblib.load(path)
