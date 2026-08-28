import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.database.session import get_supabase_admin
from app.middleware.api_request_log import ApiRequestLogMiddleware
from app.routers import (
    admin,
    admin_disputes,
    admin_onboarding,
    admin_pricing,
    admin_risk,
    admin_withdrawals,
    auth_actions,
    collections,
    collections_api,
    developer_docs,
    disbursements,
    health,
    invoices,
    merchant_portal,
    merchant_webhooks,
    merchants,
    onboarding,
    payment_links,
    public_disputes,
    public_inquiries,
    system,
    transactions,
    webhooks,
)
from app.services.checkout_reconciliation import reconcile_pending_checkout_collections

settings = get_settings()

logger = logging.getLogger("infinity.scheduler")


async def _checkout_reconciliation_loop(interval_seconds: float) -> None:
    """Backend-initiated, webhook-independent sweep — see
    Settings.selcom_checkout_reconcile_interval_seconds and
    app/services/checkout_reconciliation.py::reconcile_pending_checkout_collections's
    own docstring for why this, not the inbound webhook, is what actually
    keeps Selcom Checkout collections crediting in production. Runs for
    the lifetime of the app process; a single failed sweep is logged and
    never crashes the loop (or the app) — the next tick tries again.

    Logs every tick unconditionally (not just when there's work) —
    deliberately, so "is this actually running at all" is answerable from
    Railway logs alone without waiting for a real pending collection to
    show up. Per-collection detail (which id, what it resolved to) comes
    from reconcile_pending_checkout_collections itself."""
    logger.info("checkout_reconciliation_loop_running interval_seconds=%s", interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            client = get_supabase_admin()
            summary = await reconcile_pending_checkout_collections(client)
            logger.info("scheduled_checkout_reconciliation %s", summary)
        except Exception:
            logger.exception("scheduled_checkout_reconciliation_failed")


def _start_checkout_reconciliation_task() -> asyncio.Task | None:
    """Split out from lifespan() so tests can exercise the start/no-start
    decision directly without spinning up the whole app. 0 (the
    default — see .env.example) disables it entirely, so local dev/tests
    never have a background task running unless explicitly opted in."""
    interval = settings.selcom_checkout_reconcile_interval_seconds
    if interval <= 0:
        logger.info("checkout_reconciliation_scheduler_disabled interval_seconds=%s", interval)
        return None
    logger.info("checkout_reconciliation_scheduler_started interval_seconds=%s", interval)
    return asyncio.create_task(_checkout_reconciliation_loop(interval))


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    task = _start_checkout_reconciliation_task()
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="Infinity Africa API",
    description="Payment infrastructure for African merchants — collections, payment links, invoices, and merchant tools.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiRequestLogMiddleware)

register_exception_handlers(app)

app.include_router(health.router)

app.include_router(merchants.router, prefix="/v1")
app.include_router(merchant_portal.router, prefix="/v1")
app.include_router(onboarding.router, prefix="/v1")
app.include_router(admin_onboarding.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
app.include_router(admin_risk.router, prefix="/v1")
app.include_router(admin_disputes.router, prefix="/v1")
app.include_router(admin_withdrawals.router, prefix="/v1")
app.include_router(admin_pricing.router, prefix="/v1")
app.include_router(public_disputes.router, prefix="/v1")
app.include_router(payment_links.router, prefix="/v1")
app.include_router(payment_links.public_router)  # /public/payment-links — no /v1 prefix
app.include_router(invoices.router, prefix="/v1")
app.include_router(collections.router, prefix="/v1")
app.include_router(collections.initiate_router, prefix="/v1")
app.include_router(collections_api.router, prefix="/v1")
app.include_router(disbursements.router, prefix="/v1")  # /v1/disbursements — fully flat
app.include_router(transactions.router, prefix="/v1")
app.include_router(transactions.by_reference_router, prefix="/v1")
app.include_router(webhooks.router, prefix="/v1")
app.include_router(webhooks.callback_router, prefix="/v1")
app.include_router(developer_docs.router, prefix="/v1")
app.include_router(merchant_webhooks.router, prefix="/v1")
app.include_router(system.router, prefix="/v1")
app.include_router(auth_actions.router, prefix="/v1")
app.include_router(public_inquiries.router, prefix="/v1")
