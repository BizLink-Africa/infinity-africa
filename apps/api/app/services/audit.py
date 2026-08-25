"""Audit log helper — every mutating router action calls this after the
fact, writing to the append-only public.audit_logs table.
"""

import uuid
from typing import Any, Literal

from supabase import Client


def write_audit_log(
    client: Client,
    *,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    actor_type: Literal["user", "system", "api_key"] = "user",
    merchant_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    client.table("audit_logs").insert(
        {
            "actor_id": str(actor_id) if actor_id else None,
            "actor_type": actor_type,
            "merchant_id": str(merchant_id) if merchant_id else None,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "metadata": metadata or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
    ).execute()
