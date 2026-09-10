"""Subscriber tiers: Free is fixed, Pro customizes, admin overrides everything.

The gate has to hold on the server. Before this, the only thing stopping a
non-paying account from tracking keywords was a disabled button.
"""

import importlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import entitlements as ent
from app.services.user_service import UserService
from app.topic_packs.keywords import keyword_source_key
from app.topic_packs.registry import ALLOWED_TOPIC_IDS


# --- tier resolution -------------------------------------------------------


@pytest.mark.parametrize(
    "role,plan,tier",
    [
        ("user", "free", "free"),
        ("user", "pro", "pro"),
        ("admin", "free", "admin"),
        ("admin", "pro", "admin"),
        ("ADMIN", None, "admin"),
        ("user", None, "free"),
        (None, None, "free"),
        ("user", "PRO", "pro"),
    ],
)
def test_effective_tier(role, plan, tier):
    assert ent.effective_tier(role, plan) == tier


@pytest.mark.parametrize("raw", ["", None, "enterprise", "premium", 7, "  "])
def test_unknown_plans_are_free_never_pro(raw):
    assert ent.normalize_plan(raw) == "free"


@pytest.mark.parametrize(
    "role,plan,allowed",
    [("user", "free", False), ("user", "pro", True), ("admin", "free", True)],
)
def test_customization_and_keywords_follow_tier(role, plan, allowed):
    assert ent.can_customize(role, plan) is allowed
    assert ent.can_track_keywords(role, plan) is allowed


@pytest.mark.parametrize(
    "role,plan,status,exempt",
    [
        ("user", "free", "trial", False),
        ("user", "free", "expired", False),
        ("user", "free", None, False),
        ("user", "pro", "trial", True),
        ("admin", "free", "trial", True),
        # Admin-activated Free subscriber: must survive the next run's expiry pass.
        ("user", "free", "active", True),
        ("user", "free", "ACTIVE", True),
    ],
)
def test_trial_exemption(role, plan, status, exempt):
    assert ent.is_trial_exempt(role, plan, status) is exempt


# --- profile enforcement ---------------------------------------------------


def _profile(role, plan):
    user = SimpleNamespace(
        name="Sub",
        title="Eng",
        expertise_level="Advanced",
        role=role,
        plan=plan,
        preferences=json.dumps({"topics": ["cricket"], "keywords": ["ai agents"]}),
    )
    svc = UserService.__new__(UserService)  # skip DB session setup
    return svc.get_user_profile(user)


def test_free_subscriber_gets_the_fixed_briefing():
    """Stored preferences are ignored — e.g. terms saved before a downgrade."""
    prof = _profile("user", "free")
    assert prof["topics"] == list(ALLOWED_TOPIC_IDS)
    assert prof["keywords"] == []
    assert prof["keyword_source_keys"] == frozenset()


def test_pro_subscriber_customization_is_honoured():
    prof = _profile("user", "pro")
    assert prof["topics"] == ["cricket"]
    assert prof["keywords"] == ["ai agents"]
    assert prof["keyword_source_keys"] == {keyword_source_key("ai agents")}


def test_admin_customization_is_honoured_regardless_of_plan():
    prof = _profile("admin", "free")
    assert prof["topics"] == ["cricket"]
    assert prof["keywords"] == ["ai agents"]


# --- database-backed -------------------------------------------------------


@pytest.fixture()
def tier_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/tiers.db")
    from app.database import connection as conn_mod

    importlib.reload(conn_mod)
    import app.database.repository as repo_mod

    importlib.reload(repo_mod)
    from app.database.models import Base, User

    Base.metadata.create_all(conn_mod.engine)
    repo = repo_mod.Repository()
    now = datetime.now(timezone.utc) - timedelta(days=1)
    for uid, role, plan, kws in [
        ("free1", "user", "free", ["free term"]),
        ("pro1", "user", "pro", ["pro term"]),
        ("adm1", "admin", "free", ["admin term"]),
    ]:
        repo.session.add(
            User(
                id=uid,
                email=f"{uid}@example.com",
                name=uid,
                is_active="true",
                role=role,
                plan=plan,
                preferences=json.dumps({"keywords": kws}),
                created_at=now,
            )
        )
    repo.session.commit()
    return repo


def test_only_entitled_subscribers_spawn_keyword_lanes(tier_repo):
    """A Free user's saved terms must not cost ingest, not just stay out of email."""
    assert sorted(tier_repo.get_tracked_keywords()) == ["admin term", "pro term"]


def test_new_users_default_to_free(tier_repo):
    from app.database.models import User

    tier_repo.session.add(
        User(
            id="fresh",
            email="fresh@example.com",
            name="Fresh",
            preferences="{}",
            created_at=datetime.now(timezone.utc),
        )
    )
    tier_repo.session.commit()
    row = tier_repo.session.query(User).filter_by(id="fresh").first()
    assert row.plan == "free"
    assert row.role == "user"


def test_snapshot_carries_plan(tier_repo):
    snaps = {s.id: s for s in tier_repo.get_active_user_snapshots()}
    assert snaps["pro1"].plan == "pro"
    assert snaps["free1"].plan == "free"


def test_delivery_log_records_what_was_sent(tier_repo):
    from app.database.models import EmailDelivery

    ok = tier_repo.record_email_delivery(
        user_id="pro1",
        email="pro1@example.com",
        kind="digest",
        status="sent",
        subject="Your Daily AI Digest",
        digest_ids=["techcrunch:a", "kw_x:b"],
        pipeline_run_id="run-1",
    )
    assert ok is True
    row = tier_repo.session.query(EmailDelivery).one()
    assert row.status == "sent"
    assert row.kind == "digest"
    assert json.loads(row.digest_ids) == ["techcrunch:a", "kw_x:b"]


def test_delivery_log_records_failures_with_the_error(tier_repo):
    from app.database.models import EmailDelivery

    tier_repo.record_email_delivery(
        user_id="free1",
        email="free1@example.com",
        kind="digest",
        status="failed",
        error="535 Username and Password not accepted",
    )
    row = tier_repo.session.query(EmailDelivery).one()
    assert row.status == "failed"
    assert "535" in row.error


def test_delivery_log_never_raises(tier_repo, monkeypatch):
    """Logging is observability; it must not abort a send that already happened."""

    def boom(fn, retries=3):
        raise RuntimeError("database gone")

    monkeypatch.setattr(tier_repo, "_safe_execute", boom)
    assert (
        tier_repo.record_email_delivery(
            user_id="pro1", email="pro1@example.com", kind="digest", status="sent"
        )
        is False
    )
