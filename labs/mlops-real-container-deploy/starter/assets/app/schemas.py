"""Request/response models for the model server. (Provided - do not edit.)"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """The four iris measurements, in centimeters."""

    sepal_length: float = Field(..., gt=0, description="cm")
    sepal_width: float = Field(..., gt=0, description="cm")
    petal_length: float = Field(..., gt=0, description="cm")
    petal_width: float = Field(..., gt=0, description="cm")


class PredictResponse(BaseModel):
    predicted_class: str
    predicted_class_index: int
    probabilities: dict[str, float]
