"""app.core.time — Africa/Dar_es_Salaam date-range/display helpers used by
the Wallet Ledger's date filter and Excel export
(app/services/ledger.py, app/services/wallet_ledger_export.py)."""

from datetime import date, datetime, timezone

from app.core.time import dar_es_salaam_day_bounds_utc, to_dar_es_salaam


def test_day_bounds_cover_the_whole_dar_es_salaam_calendar_day():
    # Dar es Salaam is a fixed UTC+3 (no DST) — 2026-08-15 00:00 EAT is
    # 2026-08-14 21:00 UTC, and the day ends at 2026-08-16 00:00 EAT =
    # 2026-08-15 21:00 UTC (exclusive).
    start_utc, end_utc = dar_es_salaam_day_bounds_utc(date(2026, 8, 15), date(2026, 8, 15))
    assert start_utc == datetime(2026, 8, 14, 21, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 8, 15, 21, 0, tzinfo=timezone.utc)


def test_day_bounds_are_none_when_the_side_is_not_given():
    start_utc, end_utc = dar_es_salaam_day_bounds_utc(None, None)
    assert start_utc is None
    assert end_utc is None


def test_day_bounds_multi_day_range_is_inclusive_of_the_end_date():
    start_utc, end_utc = dar_es_salaam_day_bounds_utc(date(2026, 8, 1), date(2026, 8, 31))
    # An entry at 23:59 EAT on Aug 31 must still be inside [start, end).
    aug_31_late = datetime(2026, 8, 31, 20, 59, tzinfo=timezone.utc)  # 23:59 EAT
    assert start_utc <= aug_31_late < end_utc


def test_to_dar_es_salaam_converts_utc_iso_to_eat_local_time():
    local = to_dar_es_salaam("2026-08-15T09:00:00+00:00")
    assert local.hour == 12  # UTC+3
    assert local.date() == date(2026, 8, 15)


def test_to_dar_es_salaam_handles_a_z_suffixed_timestamp():
    local = to_dar_es_salaam("2026-08-15T21:30:00Z")
    assert local.date() == date(2026, 8, 16)  # rolls into the next EAT day
    assert local.hour == 0
    assert local.minute == 30
