"""Real, deterministic dataset for the lab. Provided - do not edit.

Uses scikit-learn's bundled breast-cancer dataset (no download, no network) so training is real
but the lab never depends on an external file or service.
"""

from __future__ import annotations

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split


def load_dataset(
    test_size: float = 0.25, random_state: int = 42
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(X_train, X_test, y_train, y_test)`` for the breast-cancer binary classification task."""
    data = load_breast_cancer()
    return train_test_split(
        data.data,
        data.target,
        test_size=test_size,
        random_state=random_state,
        stratify=data.target,
    )
