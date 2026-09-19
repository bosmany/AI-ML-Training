"""Pydantic v2 request/response schemas (reference solution)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Email = Annotated[str, StringConstraints(pattern=EMAIL_PATTERN, max_length=254, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
Score = Annotated[float, Field(ge=0, le=100)]

SortKey = Literal["id", "score", "-score", "name", "-name"]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a client sending "role" must get a 422, not escalation

    email: Email
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes when UTF-8 encoded")
        return value


class LoginRequest(BaseModel):
    email: Email
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class CandidateCreate(BaseModel):
    name: Name
    email: Email
    city: Name
    score: Score


class CandidateUpdate(BaseModel):
    """Partial update: every field optional; only fields the client sent are applied."""

    name: Name | None = None
    email: Email | None = None
    city: Name | None = None
    score: Score | None = None

    @model_validator(mode="after")
    def no_explicit_nulls(self) -> CandidateUpdate:
        # Omitted = "leave unchanged" (fine); explicit null would write NULL into a NOT NULL column.
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} may be omitted but not null")
        return self


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    city: str
    score: float
    created_by: int | None
    created_at: datetime


class CandidatePage(BaseModel):
    items: list[CandidateOut]
    total: int
    page: int
    page_size: int
    pages: int
