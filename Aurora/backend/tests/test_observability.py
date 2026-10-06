"""Error tracking: off without a DSN, privacy-safe when on, and never the reason the app can't start."""
import logging
import sys
import types

import pytest

from backend import observability


class FakeSentry(types.ModuleType):
    """Stands in for sentry_sdk and records how init was called."""

    def __init__(self, error: Exception | None = None):
        super().__init__("sentry_sdk")
        self.calls: list[dict] = []
        self.error = error

    def init(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error


@pytest.fixture
def fake_sentry(monkeypatch):
    fake = FakeSentry()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    return fake


def test_without_a_dsn_nothing_is_started_and_the_sdk_is_not_even_imported(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)       # importing it would raise
    assert observability.init_error_tracking("", "production") is False


def test_with_a_dsn_it_starts_with_every_privacy_setting_on(fake_sentry, caplog):
    with caplog.at_level(logging.INFO, logger="aura.observability"):
        assert observability.init_error_tracking("https://key@sentry.example.com/1", "production") is True
    assert fake_sentry.calls == [dict(
        dsn="https://key@sentry.example.com/1", environment="production",
        send_default_pii=False, max_request_body_size="never", include_local_variables=False,
    )]
    assert "enabled" in caplog.text


def test_a_missing_sdk_is_a_warning_not_a_crash(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    with caplog.at_level(logging.WARNING, logger="aura.observability"):
        assert observability.init_error_tracking("https://key@sentry.example.com/1", "production") is False
    assert "isn't installed" in caplog.text


def test_a_bad_dsn_is_logged_and_the_app_carries_on(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "sentry_sdk", FakeSentry(error=ValueError("Unsupported scheme")))
    with caplog.at_level(logging.ERROR, logger="aura.observability"):
        assert observability.init_error_tracking("nonsense", "production") is False
    assert "SENTRY_DSN correct" in caplog.text


# ── Against the real SDK, so the options we pass are known to be valid for the pinned version ─────

def test_the_real_sdk_accepts_these_options_and_keeps_them():
    sentry_sdk = pytest.importorskip("sentry_sdk")
    try:
        assert observability.init_error_tracking("https://public@o0.ingest.invalid/1", "test") is True
        options = sentry_sdk.get_client().options
        assert options["send_default_pii"] is False
        assert options["max_request_body_size"] == "never"
        assert options["include_local_variables"] is False
        assert options["environment"] == "test"
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()          # back to a disabled client


def test_the_real_sdk_rejects_a_garbage_dsn_without_taking_the_app_down(caplog):
    pytest.importorskip("sentry_sdk")
    with caplog.at_level(logging.ERROR, logger="aura.observability"):
        assert observability.init_error_tracking("this is not a dsn", "test") is False
    assert "continuing without error tracking" in caplog.text
