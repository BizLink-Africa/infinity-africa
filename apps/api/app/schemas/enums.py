"""Mirrors packages/shared enums for the Python backend.

TypeScript and Python cannot share a single source of truth without a
codegen step, so these must be kept in sync with packages/shared/src by
hand until one is introduced. Values also mirror the CHECK constraints in
supabase/migrations.
"""

from enum import StrEnum


class CollectionMethod(StrEnum):
    """How a customer pays a merchant (collections)."""

    USSD_PUSH = "USSD_PUSH"
    STK_PUSH = "STK_PUSH"
    SELCOM_PESA_PUSH = "SELCOM_PESA_PUSH"
    DYNAMIC_QR = "DYNAMIC_QR"


class DisbursementMethod(StrEnum):
    """How a merchant receives payouts from their Infinity Africa balance."""

    SELCOM_PESA = "SELCOM_PESA"
    MOBILE_MONEY = "MOBILE_MONEY"
    BANK_ACCOUNT = "BANK_ACCOUNT"


class UserRole(StrEnum):
    """Platform + merchant-scoped user roles.

    SUPER_ADMIN is platform-wide (platform_admins table). MERCHANT_ADMIN,
    MERCHANT_STAFF, and DEVELOPER are held within a specific merchant
    (merchant_users.role).
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    MERCHANT_ADMIN = "MERCHANT_ADMIN"
    MERCHANT_STAFF = "MERCHANT_STAFF"
    DEVELOPER = "DEVELOPER"


MERCHANT_ROLES = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF, UserRole.DEVELOPER)


class TransactionStatus(StrEnum):
    """Lifecycle status of any ledger movement."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    REVERSED = "reversed"
    CANCELLED = "cancelled"


class InvoiceStatus(StrEnum):
    """Lifecycle status of a merchant-issued invoice."""

    DRAFT = "DRAFT"
    SENT = "SENT"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class PaymentLinkStatus(StrEnum):
    """Lifecycle status of a reusable or one-off payment link."""

    ACTIVE = "ACTIVE"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class DisbursementStatus(StrEnum):
    """Lifecycle status of a payout. Distinct from (uppercase, and without
    CANCELLED) the lowercase TransactionStatus its settling transaction row
    uses. Every withdrawal starts at PENDING_ADMIN_APPROVAL — there is no
    amount-based auto-processing. REJECTED (a Super Admin's deliberate
    decision, nothing was ever reserved) is distinct from FAILED (a
    reserved payout the provider declined, reversed). REVERSED is for
    reversing an already-SUCCESS payout after the fact."""

    PENDING_ADMIN_APPROVAL = "PENDING_ADMIN_APPROVAL"
    INFO_REQUESTED = "INFO_REQUESTED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    NEEDS_ADMIN_ATTENTION = "NEEDS_ADMIN_ATTENTION"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"
    BLOCKED_IP_WHITELIST = "BLOCKED_IP_WHITELIST"
    REVERSED = "REVERSED"


class DestinationCode(StrEnum):
    """Withdrawal destination providers — mobile money telcos and banks —
    supported for merchant_pricing_rules.destination_code and a withdrawal's
    own destination_code snapshot. Mirrors the CHECK constraint in
    supabase/migrations/20260820090000_merchant_pricing_rules.sql."""

    SELCOM = "SELCOM"
    MPESA = "MPESA"
    AIRTELMONEY = "AIRTELMONEY"
    HALOPESA = "HALOPESA"
    MIXXBYYAS = "MIXXBYYAS"
    TTCLPESA = "TTCLPESA"
    CRDB = "CRDB"
    NMB = "NMB"
    NBC = "NBC"
    ABSA = "ABSA"
    BOA = "BOA"
    DTB = "DTB"
    EQUITY = "EQUITY"
    EXIM = "EXIM"
    KCB = "KCB"
    STANBIC = "STANBIC"
    SCB = "SCB"
    TCB = "TCB"


class WebhookEvent(StrEnum):
    """Event names delivered to merchant webhook endpoints."""

    COLLECTION_PENDING = "collection.pending"
    COLLECTION_SUCCESS = "collection.success"
    COLLECTION_FAILED = "collection.failed"
    DISBURSEMENT_SUCCESS = "disbursement.success"
    DISBURSEMENT_FAILED = "disbursement.failed"
    DISBURSEMENT_REVERSED = "disbursement.reversed"
    INVOICE_PAID = "invoice.paid"
    INVOICE_OVERDUE = "invoice.overdue"
    PAYMENT_LINK_CREATED = "payment_link.created"
    PAYMENT_LINK_PAID = "payment_link.paid"
    PAYMENT_LINK_EXPIRED = "payment_link.expired"
    REFUND_SUCCEEDED = "refund.succeeded"
    REFUND_FAILED = "refund.failed"
    CHARGEBACK_OPENED = "chargeback.opened"
    CHARGEBACK_RESOLVED = "chargeback.resolved"


class AccountStatus(StrEnum):
    """Onboarding review lifecycle (onboarding_submissions.review_status) —
    independent of merchants.status/kyc_status; see supabase/migrations'
    20260815090000_onboarding.sql for why these are kept separate."""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INFO_REQUESTED = "INFO_REQUESTED"


class ServiceNeeded(StrEnum):
    """Services a merchant selects during onboarding — deliberately excludes
    withdrawals, a merchant-portal function, not a public/onboarding
    service selection."""

    PAYMENT_COLLECTION = "PAYMENT_COLLECTION"
    PAYMENT_LINKS = "PAYMENT_LINKS"
    INVOICES = "INVOICES"
    DYNAMIC_QR = "DYNAMIC_QR"
    API_INTEGRATION = "API_INTEGRATION"


class DocumentType(StrEnum):
    """Compliance documents required during merchant onboarding."""

    NIDA = "NIDA"
    TIN_CERTIFICATE = "TIN_CERTIFICATE"
    BUSINESS_LICENCE = "BUSINESS_LICENCE"


class DocumentUploadStatus(StrEnum):
    UPLOADED = "UPLOADED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class FraudRiskLevel(StrEnum):
    """Severity of a fraud_alerts finding."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FraudAlertStatus(StrEnum):
    """Review lifecycle of a fraud_alerts row."""

    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    DOCUMENTS_REQUESTED = "DOCUMENTS_REQUESTED"
    CLEARED = "CLEARED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class DocumentRequestStatus(StrEnum):
    """Lifecycle of a merchant_document_requests row."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DisputeReasonCategory(StrEnum):
    """Why a customer reported a transaction via /report-transaction."""

    PRODUCT_NOT_RECEIVED = "PRODUCT_NOT_RECEIVED"
    SERVICE_NOT_DELIVERED = "SERVICE_NOT_DELIVERED"
    WRONG_PRODUCT_OR_SERVICE = "WRONG_PRODUCT_OR_SERVICE"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    UNAUTHORIZED_PAYMENT = "UNAUTHORIZED_PAYMENT"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    OTHER = "OTHER"


class DisputeStatus(StrEnum):
    """Lifecycle of a disputes row."""

    SUBMITTED = "SUBMITTED"
    MERCHANT_NOTIFIED = "MERCHANT_NOTIFIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUNDED = "REFUNDED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class RefundStatus(StrEnum):
    """Lifecycle of a refunds row. Manual workflow — PROCESSING -> SUCCESS/
    FAILED is an admin marking it based on provider/manual confirmation, not
    an automated payment-provider refund call."""

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
