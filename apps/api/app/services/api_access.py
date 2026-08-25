"""Gates whether a merchant may create/rotate a `live` API key.

Five conditions from the task brief, three of them already implied by
existing state rather than needing their own new checks:
  - KYC approved            -> merchants.kyc_status == 'verified'
  - merchant status APPROVED -> merchants.status == 'active'
  - wallet created           -> already lazily created the moment a
                                 merchant is approved (see
                                 onboarding.py::approve_onboarding_submission
                                 -> get_wallet_balance) — nothing new to
                                 check here, it always exists by the time
                                 status/kyc_status reach the values above.
  - pricing rule assigned    -> the existing 6-tier precedence resolver
                                 (app/services/withdrawals/fee_calculator.py)
                                 always resolves *something* once a
                                 platform fallback rule exists, same as
                                 for every other merchant — not a
                                 merchant-specific gate.
  - Super Admin enables production API access -> merchants.api_production_enabled,
                                 the one genuinely new, explicit flag.

So the real gate is just: status == 'active' AND kyc_status == 'verified'
AND api_production_enabled is true. Sandbox keys are never gated — every
merchant, regardless of approval state, can always create/use a sandbox
key (that's the whole point of a sandbox).
"""

from app.core.errors import ProductionAccessRestrictedError


def is_production_api_access_allowed(merchant: dict) -> bool:
    return (
        merchant.get("status") == "active"
        and merchant.get("kyc_status") == "verified"
        and bool(merchant.get("api_production_enabled"))
    )


def check_production_api_access(merchant: dict) -> None:
    if is_production_api_access_allowed(merchant):
        return

    if merchant.get("status") != "active" or merchant.get("kyc_status") != "verified":
        raise ProductionAccessRestrictedError(
            "Production API access requires an approved, KYC-verified merchant account. "
            "Complete onboarding verification first."
        )
    raise ProductionAccessRestrictedError(
        "Production API access has not been enabled for this account yet. "
        "Contact Infinity Africa to request live API access."
    )
