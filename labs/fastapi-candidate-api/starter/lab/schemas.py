"""Pydantic v2 request/response schemas (starter)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# TODO 1: tighten these three aliases (Pydantic v2 ``Annotated`` + constraints).
#   Email: must look like ``local@domain.tld`` (use ``StringConstraints(pattern=...)``; the lab does not
#          depend on email-validator), at most 254 chars, surrounding whitespace stripped.
#   Name:  1..100 chars after stripping whitespace (so "   " is rejected).
#   Score: a float between 0 and 100 inclusive (``Field(ge=0, le=100)``).
Email = str
Name = str
Score = float

SortKey = Literal["id", "score", "-score", "name", "-name"]


class RegisterRequest(BaseModel):
    # TODO 2: forbid unknown fields (``ConfigDict(extra="forbid")``) so a client sending "role": "admin"
    #         gets a 422 instead of having the field silently ignored.
    # TODO 3: password must be >= 8 characters AND <= 72 BYTES once UTF-8 encoded (bcrypt's limit;
    #         19 emoji are only 19 characters but 76 bytes). Use ``Field(min_length=8)`` plus a
    #         ``@field_validator("password")`` that checks ``len(value.encode("utf-8"))``.
    email: Email
    password: str


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

    # TODO 4: omitted field = "leave unchanged" (fine) but an explicit ``null`` would write NULL into a
    #         NOT NULL column. Add a ``@model_validator(mode="after")`` that raises ``ValueError`` when a
    #         field in ``self.model_fields_set`` is None.


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
