import uuid
from datetime import datetime, timezone


def generate_reference(prefix: str) -> str:
    """A short, human-showable reference like "TXN-20260814-9F3A1C2B"."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"
