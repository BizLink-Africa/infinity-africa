import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.enums import UserRole


class AuthenticatedUser(BaseModel):
    """The caller identified by a verified Supabase Auth JWT."""

    id: uuid.UUID
    email: str | None = None


class MerchantMembership(BaseModel):
    """A user's active role within a specific merchant (merchant_users row)."""

    merchant_id: uuid.UUID
    user_id: uuid.UUID
    role: UserRole


class ApiKeyContext(BaseModel):
    """The merchant/environment identified by a verified merchant API key."""

    id: uuid.UUID
    merchant_id: uuid.UUID
    environment: str
    status: str
    scopes: list[str] = []


class MerchantActor(BaseModel):
    """The caller for endpoints that accept either a dashboard JWT or a
    merchant API key — e.g. initiating a collection or disbursement."""

    merchant_id: uuid.UUID
    actor_type: Literal["user", "api_key"]
    actor_id: uuid.UUID | None = None
    scopes: list[str] = []  # only meaningful for actor_type == "api_key"


class AuthenticatedCaller(BaseModel):
    """An authenticated caller (API key or dashboard JWT) *before* they're
    pinned to a specific merchant — for flat resource routes (e.g.
    /v1/payment-links) that have no merchant_id path segment to resolve it
    from. An API key already implies its merchant_id; a user's doesn't,
    until authorize_merchant_action() checks it against one."""

    actor_type: Literal["user", "api_key"]
    actor_id: uuid.UUID
    merchant_id: uuid.UUID | None = None  # known immediately for api_key callers
    user: AuthenticatedUser | None = None  # set for user callers, for the membership check
    scopes: list[str] = []  # only meaningful for actor_type == "api_key"
    environment: str | None = None  # "sandbox" | "live" — only set for actor_type == "api_key"
