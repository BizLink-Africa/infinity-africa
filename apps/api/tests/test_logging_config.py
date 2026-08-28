"""app/main.py::_configure_logging — before this existed, nothing anywhere
in this codebase ever configured Python's logging system, which meant
every logger.info()/.debug() call across the whole app (not just the
checkout reconciliation scheduler's own confirmation logs — that's just
what exposed it) was silently dropped in production: the root logger
defaults to WARNING with no handler, so only .warning()/.error()/
.exception() calls were ever visible in Railway logs. Confirmed directly
against this exact symptom on 2026-08-28.
"""

import logging

from app.main import _configure_logging


def _reset_infinity_logger() -> None:
    """Every logger in this app is a child of "infinity" — tests must
    restore this shared, module-global logger's state afterward so one
    test can't leave the level/handlers changed for every other test
    that runs after it in the same session."""
    infinity_logger = logging.getLogger("infinity")
    infinity_logger.handlers.clear()
    infinity_logger.setLevel(logging.NOTSET)
    infinity_logger.propagate = True


def test_info_level_logs_are_silently_dropped_without_configuration():
    """The bug this whole fix exists for, proven directly: a fresh,
    never-configured "infinity.*" logger really does swallow .info()
    calls by default."""
    _reset_infinity_logger()
    logger = logging.getLogger("infinity.test_unconfigured")
    assert logger.isEnabledFor(logging.INFO) is False


def test_configure_logging_enables_info_level():
    _reset_infinity_logger()
    try:
        _configure_logging("INFO")
        logger = logging.getLogger("infinity.test_configured")
        assert logger.isEnabledFor(logging.INFO) is True
    finally:
        _reset_infinity_logger()


def test_configure_logging_actually_emits_a_record():
    """Not just "the level allows it" — a real record reaches a real
    handler, matching what Railway's log capture depends on."""
    _reset_infinity_logger()
    try:
        _configure_logging("INFO")
        logger = logging.getLogger("infinity.test_emits")

        records = []

        class _CapturingHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logging.getLogger("infinity").addHandler(_CapturingHandler())
        logger.info("hello from a test")

        assert any(r.getMessage() == "hello from a test" for r in records)
    finally:
        _reset_infinity_logger()


def test_configure_logging_respects_a_stricter_level():
    _reset_infinity_logger()
    try:
        _configure_logging("WARNING")
        logger = logging.getLogger("infinity.test_strict")
        assert logger.isEnabledFor(logging.INFO) is False
        assert logger.isEnabledFor(logging.WARNING) is True
    finally:
        _reset_infinity_logger()


def test_configure_logging_is_idempotent_about_handlers():
    """Calling it twice (e.g. if the module were ever re-imported) must
    never attach a second handler — that would double-print every line."""
    _reset_infinity_logger()
    try:
        _configure_logging("INFO")
        _configure_logging("INFO")
        assert len(logging.getLogger("infinity").handlers) == 1
    finally:
        _reset_infinity_logger()


def test_configure_logging_does_not_touch_the_root_logger():
    """Deliberately scoped to the "infinity" logger only — never
    logging.basicConfig() on the root logger, which risks interfering
    with pytest's own caplog handler (or uvicorn's loggers in
    production). See _configure_logging's own docstring."""
    root_handlers_before = list(logging.getLogger().handlers)
    _reset_infinity_logger()
    try:
        _configure_logging("INFO")
        assert list(logging.getLogger().handlers) == root_handlers_before
    finally:
        _reset_infinity_logger()
