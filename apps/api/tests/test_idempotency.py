import uuid

import pytest

from app.core.errors import ConflictError, IdempotencyKeyReusedError
from app.services.idempotency import compute_request_hash, run_idempotent
from tests.fakes import FakeSupabaseClient


async def test_run_idempotent_executes_handler_once():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    calls = []

    async def handler():
        calls.append(1)
        return 202, {"status": "successful"}

    status_code, body = await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /test",
        idempotency_key="key-1",
        request_payload={"amount": "100"},
        handler=handler,
    )

    assert status_code == 202
    assert body == {"status": "successful"}
    assert len(calls) == 1


async def test_run_idempotent_replays_on_retry_with_same_payload():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    calls = []

    async def handler():
        calls.append(1)
        return 202, {"attempt": len(calls)}

    payload = {"amount": "100"}

    first = await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /test",
        idempotency_key="key-1",
        request_payload=payload,
        handler=handler,
    )
    second = await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /test",
        idempotency_key="key-1",
        request_payload=payload,
        handler=handler,
    )

    assert first == second
    assert len(calls) == 1  # handler only ran once — the retry replayed


async def test_run_idempotent_rejects_key_reused_with_different_payload():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()

    async def handler():
        return 202, {}

    await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /test",
        idempotency_key="key-1",
        request_payload={"amount": "100"},
        handler=handler,
    )

    with pytest.raises(IdempotencyKeyReusedError):
        await run_idempotent(
            client,
            merchant_id=merchant_id,
            endpoint="POST /test",
            idempotency_key="key-1",
            request_payload={"amount": "200"},
            handler=handler,
        )


async def test_run_idempotent_different_merchants_are_independent():
    client = FakeSupabaseClient()
    calls = []

    async def handler():
        calls.append(1)
        return 202, {}

    payload = {"amount": "100"}

    await run_idempotent(
        client,
        merchant_id=uuid.uuid4(),
        endpoint="POST /test",
        idempotency_key="key-1",
        request_payload=payload,
        handler=handler,
    )
    await run_idempotent(
        client,
        merchant_id=uuid.uuid4(),
        endpoint="POST /test",
        idempotency_key="key-1",
        request_payload=payload,
        handler=handler,
    )

    assert len(calls) == 2  # different merchants, same key -> both run


async def test_run_idempotent_deletes_record_on_handler_failure_allowing_retry():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    attempts = []

    async def failing_then_succeeding():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("provider timeout")
        return 202, {"ok": True}

    payload = {"amount": "100"}

    with pytest.raises(RuntimeError):
        await run_idempotent(
            client,
            merchant_id=merchant_id,
            endpoint="POST /test",
            idempotency_key="key-1",
            request_payload=payload,
            handler=failing_then_succeeding,
        )

    status_code, body = await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /test",
        idempotency_key="key-1",
        request_payload=payload,
        handler=failing_then_succeeding,
    )

    assert status_code == 202
    assert body == {"ok": True}
    assert len(attempts) == 2


async def test_run_idempotent_in_progress_conflict():
    """Simulates a concurrent duplicate request racing the insert."""
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()

    # Pre-seed an "in_progress" row, as if a concurrent request got there first.
    client.seed(
        "idempotency_keys",
        {
            "merchant_id": str(merchant_id),
            "key": "key-1",
            "endpoint": "POST /test",
            "request_hash": compute_request_hash({"amount": "100"}),
            "status": "in_progress",
        },
    )

    async def handler():
        return 202, {}

    with pytest.raises(ConflictError):
        await run_idempotent(
            client,
            merchant_id=merchant_id,
            endpoint="POST /test",
            idempotency_key="key-1",
            request_payload={"amount": "100"},
            handler=handler,
        )
