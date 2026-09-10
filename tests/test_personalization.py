"""Email slot allocation and reconnect-safe user handling."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.topic_packs.diversify import KEYWORD_RESERVE_RATIO, diversify_curated_pick
from app.topic_packs.keywords import keyword_source_key

KW_LANE = keyword_source_key("ai agents")


def _fixture(article_types):
    """Build (ranked, digest_by_id) where list order is curator rank order."""
    digests, ranked = {}, []
    for i, at in enumerate(article_types, start=1):
        did = f"d{i}"
        digests[did] = {"article_type": at}
        ranked.append(SimpleNamespace(digest_id=did, rank=i))
    return ranked, digests


def _lanes(picked, digests):
    return [digests[a.digest_id]["article_type"] for a in picked]


def test_keyword_hits_surface_even_when_ranked_low():
    # Keyword matches sit at ranks 7-9, past the top_n=6 cutoff.
    ranked, digests = _fixture(
        ["techcrunch"] * 6 + [KW_LANE] * 3 + ["topic_startup_ychn"] * 3
    )
    picked = diversify_curated_pick(ranked, digests, {"technology", "startups"}, 6)

    assert len(picked) == 6
    assert _lanes(picked, digests).count(KW_LANE) >= 1


def test_keyword_reserve_does_not_crowd_out_topics():
    """With bundle content available, keywords take their share and no more."""
    ranked, digests = _fixture([KW_LANE] * 20 + ["techcrunch"] * 10 + ["topic_startup_ychn"] * 10)
    top_n = 10
    picked = diversify_curated_pick(ranked, digests, {"technology", "startups"}, top_n)
    lanes = _lanes(picked, digests)
    expected = max(1, round(top_n * KEYWORD_RESERVE_RATIO))

    assert lanes.count(KW_LANE) == expected
    assert len(picked) == top_n
    assert {"techcrunch", "topic_startup_ychn"} <= set(lanes), "bundle lanes starved"


def test_reserve_is_a_floor_not_a_ceiling():
    """When keyword hits are the only content, they may fill the whole email.

    Capping here would ship a near-empty digest instead of a full one, which is
    strictly worse for the subscriber who opted into those terms.
    """
    ranked, digests = _fixture([KW_LANE] * 20)
    picked = diversify_curated_pick(ranked, digests, {"technology", "startups"}, 10)
    assert len(picked) == 10
    assert _lanes(picked, digests).count(KW_LANE) == 10


def test_no_duplicates_in_output():
    ranked, digests = _fixture([KW_LANE, KW_LANE, "techcrunch", "topic_startup_ychn"] * 3)
    picked = diversify_curated_pick(ranked, digests, {"technology", "startups"}, 8)
    ids = [a.digest_id for a in picked]
    assert len(ids) == len(set(ids))


def test_single_topic_user_still_gets_keyword_reserve():
    ranked, digests = _fixture(["techcrunch"] * 5 + [KW_LANE] * 2)
    picked = diversify_curated_pick(ranked, digests, {"technology"}, 5)
    assert KW_LANE in _lanes(picked, digests)


def test_without_keywords_behaviour_is_plain_rank_order():
    ranked, digests = _fixture(["techcrunch"] * 5)
    picked = diversify_curated_pick(ranked, digests, {"technology"}, 3)
    assert [a.digest_id for a in picked] == ["d1", "d2", "d3"]


def test_multi_topic_user_gets_interleaved_lanes():
    ranked, digests = _fixture(["techcrunch"] * 5 + ["topic_sport_bbcsport"] * 5)
    picked = diversify_curated_pick(ranked, digests, {"technology", "sports"}, 4)
    lanes = set(_lanes(picked, digests))
    assert lanes == {"techcrunch", "topic_sport_bbcsport"}, "one lane starved the other"


def test_empty_input_is_safe():
    assert diversify_curated_pick([], {}, {"technology"}, 5) == []
    ranked, digests = _fixture(["techcrunch"])
    assert diversify_curated_pick(ranked, digests, {"technology"}, 0) == []


# --- reconnect safety -------------------------------------------------------


@pytest.fixture()
def sqlite_repo(tmp_path, monkeypatch):
    """A Repository bound to a throwaway SQLite file."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    import importlib

    from app.database import connection as conn_mod

    importlib.reload(conn_mod)
    import app.database.repository as repo_mod

    importlib.reload(repo_mod)

    from app.database.models import Base, User

    Base.metadata.create_all(conn_mod.engine)
    repo = repo_mod.Repository()
    repo.session.add(
        User(
            id="u1",
            email="u1@example.com",
            name="U One",
            is_active="true",
            role="user",
            title="Eng",
            expertise_level="Advanced",
            preferences=json.dumps({"topics": ["technology"], "keywords": ["ai agents"]}),
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    repo.session.commit()
    return repo, repo_mod


def test_snapshots_survive_a_session_reconnect(sqlite_repo):
    """The zero-email regression: a mid-run reconnect detached every User.

    A commit expires loaded attributes; closing the session then leaves ORM
    objects unable to refresh, so ``user.email`` raised DetachedInstanceError
    and the whole send collapsed.
    """
    repo, _ = sqlite_repo
    snapshots = repo.get_active_user_snapshots()
    orm_users = repo.get_active_users()

    repo.session.commit()
    repo._reconnect()

    with pytest.raises(Exception):
        _ = orm_users[0].email

    assert snapshots[0].email == "u1@example.com"
    assert snapshots[0].name == "U One"
    assert snapshots[0].role == "user"


def test_flag_writes_work_after_reconnect(sqlite_repo):
    repo, repo_mod = sqlite_repo
    repo._reconnect()

    assert repo.set_user_flag("u1", "admin_welcome_sent") is True
    assert repo.update_user_status("u1", "expired") is True

    from app.database.models import User

    row = repo.session.query(User).filter_by(id="u1").first()
    assert row.admin_welcome_sent == "true"
    assert row.subscription_status == "expired"


def test_set_user_flag_rejects_arbitrary_columns(sqlite_repo):
    """Guards against a typo or caller turning this into an arbitrary setattr."""
    repo, _ = sqlite_repo
    with pytest.raises(ValueError):
        repo.set_user_flag("u1", "email", "attacker@example.com")


def test_tracked_keywords_are_deduped_across_users(sqlite_repo):
    repo, _ = sqlite_repo
    from app.database.models import User

    repo.session.add(
        User(
            id="u2",
            email="u2@example.com",
            name="U Two",
            is_active="true",
            role="user",
            preferences=json.dumps({"keywords": ["AI Agents", "nvidia earnings"]}),
            created_at=datetime.now(timezone.utc),
        )
    )
    repo.session.commit()

    tracked = repo.get_tracked_keywords()
    assert tracked[0] == "ai agents", "shared term should rank first"
    assert sorted(tracked) == ["ai agents", "nvidia earnings"]
