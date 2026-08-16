"""Idempotency-Key handling for money-moving endpoints (initiating a
collection or disbursement), backed by public.idempotency_keys.
"""

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from supabase import Client

from app.core.errors import ConflictError, IdempotencyKeyReusedError
from app.services.crud import execute_maybe_single


def compute_request_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def run_idempotent(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    endpoint: str,
    idempotency_key: str,
    request_payload: dict[str, Any],
    handler: Callable[[], Awaitable[tuple[int, dict]]],
) -> tuple[int, dict]:
    """Run `handler()` at most once per (merchant_id, idempotency_key, endpoint).

    A retried request — same key, same endpoint, same body — replays the
    stored (status_code, body) instead of re-running `handler`. The same key
    reused with a *different* body is rejected outright rather than either
    silently re-executing or silently returning a response for the wrong
    request.
    """
    request_hash = compute_request_hash(request_payload)

    existing = execute_maybe_single(
        client.table("idempotency_keys")
        .select("*")
        .eq("merchant_id", str(merchant_id))
        .eq("key", idempotency_key)
        .eq("endpoint", endpoint)
        .maybe_single()
    )

    if existing:
        return _handle_existing(existing, request_hash)

    try:
        insert_result = (
            client.table("idempotency_keys")
            .insert(
                {
                    "merchant_id": str(merchant_id),
                    "key": idempotency_key,
                    "endpoint": endpoint,
                    "request_hash": request_hash,
                }
            )
            .execute()
        )
    except Exception as exc:
        # Most likely cause: a concurrent request raced us and already
        # inserted this same (merchant_id, key, endpoint) — the unique
        # constraint rejected ours. Treat as "already in progress" rather
        # than leaking a raw 500.
        raise ConflictError("A request with this Idempotency-Key is already in progress") from exc

    record = insert_result.data[0]

    try:
        status_code, body = await handler()
    except Exception:
        # Don't leave a permanently "in_progress" row behind a failed
        # attempt — let a retry with the same key try again.
        client.table("idempotency_keys").delete().eq("id", record["id"]).execute()
        raise

    client.table("idempotency_keys").update(
        {"status": "completed", "response_status": status_code, "response_body": body}
    ).eq("id", record["id"]).execute()

    return status_code, body


def _handle_existing(existing: dict, request_hash: str) -> tuple[int, dict]:
    if existing["request_hash"] != request_hash:
        raise IdempotencyKeyReusedError(
            "This Idempotency-Key was already used with a different request body"
        )

    if existing["status"] == "completed":
        return existing["response_status"], existing["response_body"]

    raise ConflictError("A request with this Idempotency-Key is already in progress")
