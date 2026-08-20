"""app/config/settings.py's Settings.cors_origins parsing — accepts both a
JSON array and a plain comma-separated string (Railway's env var UI makes
typing quoted JSON error-prone), and refuses a "*" wildcard outside local
development (CORSMiddleware in app/main.py sets allow_credentials=True, so
a wildcard origin is both browser-rejected and a real credential-leak risk
— see app/config/settings.py's _reject_wildcard_cors_outside_development)."""

import pytest

from app.config.settings import Settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_cors_origins_defaults_to_localhost():
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:3000"]


def test_cors_origins_parses_a_json_array(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://infinityafrica.net","https://www.infinityafrica.net"]')
    settings = Settings()
    assert settings.cors_origins == ["https://infinityafrica.net", "https://www.infinityafrica.net"]


def test_cors_origins_parses_a_comma_separated_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://infinityafrica.net, https://www.infinityafrica.net")
    settings = Settings()
    assert settings.cors_origins == ["https://infinityafrica.net", "https://www.infinityafrica.net"]


def test_cors_origins_single_origin_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://infinityafrica.net")
    settings = Settings()
    assert settings.cors_origins == ["https://infinityafrica.net"]


def test_cors_origins_blank_string_parses_to_empty_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "")
    settings = Settings()
    assert settings.cors_origins == []


def test_wildcard_cors_origin_rejected_outside_development(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="CORS_ORIGINS must not contain"):
        Settings()


def test_wildcard_cors_origin_allowed_in_development(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("ENVIRONMENT", "development")
    settings = Settings()
    assert settings.cors_origins == ["*"]
