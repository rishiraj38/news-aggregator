"""Pipeline alerting: what counts as an incident, and what is just a quiet day."""

import pytest

from app.services import alerts


def _results(**over):
    base = {
        "scraping": {"openai": 8, "techcrunch": 20, "topic_sport_bbcsport": 40},
        "digests": {"total": 50, "processed": 50, "failed": 0},
        "user_digests": 5,
        "emails_sent": 5,
        "duration_seconds": 120.0,
    }
    base.update(over)
    return base


def test_healthy_run_raises_no_alert():
    assert alerts.detect_pipeline_problems(_results()) == []


def test_zero_emails_with_users_is_an_incident():
    """The exact September regression: subscribers processed, nothing delivered."""
    problems = alerts.detect_pipeline_problems(_results(emails_sent=0))
    assert any("0 emails" in p for p in problems)


def test_no_users_and_no_emails_is_not_an_incident():
    """An empty subscriber list is a quiet day, not a failure."""
    assert alerts.detect_pipeline_problems(_results(user_digests=0, emails_sent=0)) == []


def test_total_ingest_failure_is_an_incident():
    """Every source at zero — the dead-proxy signature."""
    problems = alerts.detect_pipeline_problems(
        _results(scraping={"openai": 0, "techcrunch": 0, "topic_sport_bbcsport": 0})
    )
    assert any("ingestion is broken" in p for p in problems)


def test_majority_of_sources_dead_is_an_incident():
    problems = alerts.detect_pipeline_problems(
        _results(scraping={"a": 5, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0})
    )
    assert any("returned nothing" in p for p in problems)


def test_one_quiet_feed_is_tolerated():
    """Feeds go quiet routinely; that must not page anyone."""
    problems = alerts.detect_pipeline_problems(
        _results(scraping={"a": 5, "b": 3, "c": 7, "d": 0})
    )
    assert problems == []


def test_all_digests_failing_is_an_incident():
    problems = alerts.detect_pipeline_problems(
        _results(digests={"total": 50, "processed": 0, "failed": 50})
    )
    assert any("digest generations failed" in p for p in problems)


def test_explicit_error_is_reported():
    problems = alerts.detect_pipeline_problems(_results(error="boom"))
    assert any("boom" in p for p in problems)


def test_missing_scraping_key_does_not_crash():
    assert alerts.detect_pipeline_problems({"user_digests": 0, "emails_sent": 0}) == []


def test_alert_is_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("PIPELINE_ALERTS_ENABLED", "false")
    assert alerts.send_pipeline_alert(_results(emails_sent=0)) is None


def test_alert_never_raises_when_sending_fails(monkeypatch):
    """A broken SMTP must not take down a run that is already failing."""
    monkeypatch.setenv("PIPELINE_ALERTS_ENABLED", "true")
    monkeypatch.setenv("PIPELINE_ALERT_EMAIL", "ops@example.com")

    import app.services.email_sender as sender

    def boom(*a, **k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(sender, "send_email", boom)
    assert alerts.send_pipeline_alert(_results(emails_sent=0)) is False


def test_alert_sends_to_configured_recipients(monkeypatch):
    monkeypatch.setenv("PIPELINE_ALERTS_ENABLED", "true")
    monkeypatch.setenv("PIPELINE_ALERT_EMAIL", "a@example.com, b@example.com")

    captured = {}

    import app.services.email_sender as sender

    def capture(subject, text, html=None, recipients=None):
        captured.update(subject=subject, text=text, html=html, recipients=recipients)

    monkeypatch.setattr(sender, "send_email", capture)

    assert alerts.send_pipeline_alert(_results(emails_sent=0)) is True
    assert captured["recipients"] == ["a@example.com", "b@example.com"]
    assert "0 emails" in captured["text"]
    assert "Helix pipeline" in captured["subject"]


def test_healthy_run_sends_nothing(monkeypatch):
    monkeypatch.setenv("PIPELINE_ALERTS_ENABLED", "true")
    monkeypatch.setenv("PIPELINE_ALERT_EMAIL", "a@example.com")

    import app.services.email_sender as sender

    monkeypatch.setattr(
        sender, "send_email", lambda *a, **k: pytest.fail("alerted on a healthy run")
    )
    assert alerts.send_pipeline_alert(_results()) is None
