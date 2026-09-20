"""
Numeric env parsing.

GitHub Actions renders an unset `${{ vars.X }}` as an empty string, so
`int(os.getenv("X", "5"))` raises ValueError instead of using the default —
that crash took the Instagram workflow down on 2026-09-21.
"""

import pytest

from app.env_utils import env_float, env_int, env_str


def test_unset_variable_uses_the_default(monkeypatch):
    monkeypatch.delenv("HELIX_TEST_N", raising=False)
    assert env_int("HELIX_TEST_N", 5) == 5
    assert env_float("HELIX_TEST_N", 2.5) == 2.5
    assert env_str("HELIX_TEST_N", "carousel") == "carousel"


@pytest.mark.parametrize("blank", ["", "   ", "\n", "\t "])
def test_empty_actions_variable_is_not_a_value(monkeypatch, blank):
    monkeypatch.setenv("HELIX_TEST_N", blank)
    assert env_int("HELIX_TEST_N", 5) == 5
    assert env_float("HELIX_TEST_N", 2.5) == 2.5
    assert env_str("HELIX_TEST_N", "carousel") == "carousel"


def test_real_values_are_read(monkeypatch):
    monkeypatch.setenv("HELIX_TEST_N", "7")
    assert env_int("HELIX_TEST_N", 5) == 7
    monkeypatch.setenv("HELIX_TEST_N", "7.0")  # a templated value can arrive like this
    assert env_int("HELIX_TEST_N", 5) == 7
    monkeypatch.setenv("HELIX_TEST_N", "1.5")
    assert env_float("HELIX_TEST_N", 2.5) == 1.5
    monkeypatch.setenv("HELIX_TEST_N", " reel ")
    assert env_str("HELIX_TEST_N", "carousel") == "reel"


def test_garbage_falls_back_instead_of_crashing(monkeypatch):
    monkeypatch.setenv("HELIX_TEST_N", "five")
    assert env_int("HELIX_TEST_N", 5) == 5
    assert env_float("HELIX_TEST_N", 2.5) == 2.5


def test_values_are_clamped_to_the_supported_range(monkeypatch):
    monkeypatch.setenv("HELIX_TEST_N", "99")
    assert env_int("HELIX_TEST_N", 5, minimum=1, maximum=8) == 8
    monkeypatch.setenv("HELIX_TEST_N", "-4")
    assert env_int("HELIX_TEST_N", 5, minimum=1, maximum=8) == 1
    assert env_float("HELIX_TEST_N", 2.5, minimum=0.0) == 0.0


def test_carousel_story_count_survives_an_unset_repo_variable(monkeypatch):
    """The exact failure: publish_instagram_card.py's --slides default."""
    monkeypatch.setenv("INSTAGRAM_CAROUSEL_STORIES", "")
    assert env_int("INSTAGRAM_CAROUSEL_STORIES", 5, minimum=1, maximum=8) == 5
