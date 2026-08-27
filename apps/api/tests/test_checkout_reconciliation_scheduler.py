"""app/main.py's backend-initiated reconciliation loop — the piece that
actually keeps Selcom Checkout collections crediting now that the inbound
webhook fails closed on every real (unsigned) delivery. The reconciliation
logic itself (app/services/checkout_reconciliation.py::
reconcile_pending_checkout_collections) is fully covered in
tests/test_checkout_reconciliation.py; this just proves the scheduler
actually calls it on a timer and keeps running afterward.
"""

import asyncio

import pytest

from app.main import _checkout_reconciliation_loop


async def _run_loop_briefly(interval: float, duration: float) -> None:
    task = asyncio.create_task(_checkout_reconciliation_loop(interval))
    await asyncio.sleep(duration)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_loop_calls_reconciliation_repeatedly_until_cancelled(monkeypatch):
    calls = []

    async def _fake_reconcile(client):
        calls.append(1)
        return {"checked": 0, "resolved": 0, "still_pending": 0}

    monkeypatch.setattr("app.main.reconcile_pending_checkout_collections", _fake_reconcile)
    monkeypatch.setattr("app.main.get_supabase_admin", lambda: object())

    asyncio.run(_run_loop_briefly(interval=0.01, duration=0.05))

    assert len(calls) >= 2  # ran more than once — genuinely on a timer, not a one-shot


def test_loop_survives_a_failed_sweep_and_keeps_running(monkeypatch):
    """One bad tick (e.g. Selcom/DB unreachable) must never kill the loop
    for the rest of the app's lifetime — the next tick tries again."""
    calls = []

    async def _flaky_reconcile(client):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("simulated Selcom outage")
        return {"checked": 0, "resolved": 0, "still_pending": 0}

    monkeypatch.setattr("app.main.reconcile_pending_checkout_collections", _flaky_reconcile)
    monkeypatch.setattr("app.main.get_supabase_admin", lambda: object())

    asyncio.run(_run_loop_briefly(interval=0.01, duration=0.05))

    assert len(calls) >= 2  # kept ticking after the first tick raised
