from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_DAR_ES_SALAAM = ZoneInfo("Africa/Dar_es_Salaam")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dar_es_salaam_day_bounds_utc(
    start_date: date | None, end_date: date | None
) -> tuple[datetime | None, datetime | None]:
    """Converts a merchant-facing (start_date, end_date) calendar-day range,
    interpreted in Africa/Dar_es_Salaam (Tanzania has no DST, so this is
    always a fixed UTC+3 — zoneinfo handles it correctly regardless), into
    UTC datetime bounds for comparing against created_at timestamps stored
    in UTC. start is inclusive at 00:00 EAT; end is exclusive at 00:00 EAT
    of the day *after* end_date, so the whole end_date calendar day is
    included. Either side is None if the caller didn't filter on it."""
    start_utc = (
        datetime(start_date.year, start_date.month, start_date.day, tzinfo=_DAR_ES_SALAAM).astimezone(timezone.utc)
        if start_date
        else None
    )
    end_utc = (
        (datetime(end_date.year, end_date.month, end_date.day, tzinfo=_DAR_ES_SALAAM) + timedelta(days=1)).astimezone(
            timezone.utc
        )
        if end_date
        else None
    )
    return start_utc, end_utc


def to_dar_es_salaam(iso_value: str) -> datetime:
    """Parses a UTC ISO timestamp (as stored in created_at columns) and
    converts it to Africa/Dar_es_Salaam local time — for display only
    (e.g. the Wallet Ledger Excel export), never for filtering, which
    already happens in UTC via dar_es_salaam_day_bounds_utc."""
    return datetime.fromisoformat(iso_value.replace("Z", "+00:00")).astimezone(_DAR_ES_SALAAM)
