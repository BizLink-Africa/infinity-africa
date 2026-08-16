from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.routers import (
    admin,
    admin_disputes,
    admin_onboarding,
    admin_risk,
    collections,
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
    system,
    transactions,
    webhooks,
)

settings = get_settings()

app = FastAPI(
    title="Infinity Africa API",
    description="Payment infrastructure for African merchants — collections, payment links, invoices, and merchant tools.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)

app.include_router(merchants.router, prefix="/v1")
app.include_router(merchant_portal.router, prefix="/v1")
app.include_router(onboarding.router, prefix="/v1")
app.include_router(admin_onboarding.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
app.include_router(admin_risk.router, prefix="/v1")
app.include_router(admin_disputes.router, prefix="/v1")
app.include_router(public_disputes.router, prefix="/v1")
app.include_router(payment_links.router, prefix="/v1")
app.include_router(payment_links.public_router)  # /public/payment-links — no /v1 prefix
app.include_router(invoices.router, prefix="/v1")
app.include_router(collections.router, prefix="/v1")
app.include_router(collections.initiate_router, prefix="/v1")
app.include_router(disbursements.router, prefix="/v1")  # /v1/disbursements — fully flat
app.include_router(transactions.router, prefix="/v1")
app.include_router(transactions.by_reference_router, prefix="/v1")
app.include_router(webhooks.router, prefix="/v1")
app.include_router(webhooks.callback_router, prefix="/v1")
app.include_router(developer_docs.router, prefix="/v1")
app.include_router(merchant_webhooks.router, prefix="/v1")
app.include_router(system.router, prefix="/v1")
