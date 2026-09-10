"""Curator degradation: a bad batch must cost items, never the whole email.

Regression cover for a live run where Groq answered one 12-item batch with
`json_validate_failed` (empty `failed_generation`) and `rank_digests` discarded
all four chunks, so the subscriber received nothing.
"""

import pytest
from openai import APIStatusError

from app.agent import curator_agent as ca
from app.agent.curator_agent import CuratorAgent, RankedArticle, _groq_prompt_tpm_reject


class _FakeJSONValidateError(Exception):
    """Mirrors the Groq 400 body without needing a real httpx response."""

    def __init__(self):
        super().__init__(
            "Error code: 400 - {'error': {'message': \"Failed to validate JSON. "
            "Please adjust your prompt. See 'failed_generation' for more details.\", "
            "'type': 'invalid_request_error', 'code': 'json_validate_failed', "
            "'failed_generation': ''}}"
        )


def _digests(n, prefix="d"):
    return [
        {"id": f"{prefix}{i}", "title": f"T{i}", "summary": "s", "article_type": "techcrunch"}
        for i in range(n)
    ]


def _agent(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ca, "GROQ_CHUNK_SLEEP_SECONDS", 0.0)
    return CuratorAgent({"name": "T", "interests": [], "topic_labels": ["Tech"]})


# --- detection -------------------------------------------------------------


def test_json_validate_failure_is_treated_as_too_big():
    """It is a 400, so nothing retries it — splitting is the only recovery."""
    assert _groq_prompt_tpm_reject(_FakeJSONValidateError()) is True


def test_unrelated_errors_are_not_treated_as_too_big():
    assert _groq_prompt_tpm_reject(ValueError("something else")) is False


# --- degradation -----------------------------------------------------------


def test_one_failing_chunk_does_not_lose_the_others(monkeypatch):
    agent = _agent(monkeypatch)
    monkeypatch.setattr(ca, "CURATOR_CHUNK_SIZE", 4)
    digests = _digests(12)

    calls = {"n": 0}

    def rank(chunk):
        calls["n"] += 1
        # Fail the first chunk outright, at every split depth.
        if any(d["id"] in {"d0", "d1", "d2", "d3"} for d in chunk):
            raise RuntimeError("model unavailable")
        return [
            RankedArticle(digest_id=d["id"], relevance_score=8.0, rank=i + 1, reasoning="ok")
            for i, d in enumerate(chunk)
        ]

    monkeypatch.setattr(agent, "_rank_digest_recursive", rank)
    out = agent.rank_digests(digests)

    ids = {a.digest_id for a in out}
    assert len(out) == 12, "every digest should still be represented"
    assert {"d4", "d8"} <= ids, "healthy chunks were discarded"
    # The failed chunk's items survive with the neutral fallback score.
    failed = [a for a in out if a.digest_id in {"d0", "d1", "d2", "d3"}]
    assert len(failed) == 4
    assert all(a.relevance_score == 5.0 for a in failed)


def test_total_failure_still_returns_every_digest(monkeypatch):
    """Even when the model is entirely down, the email should not be empty."""
    agent = _agent(monkeypatch)
    monkeypatch.setattr(ca, "CURATOR_CHUNK_SIZE", 3)

    def always_fail(chunk):
        raise RuntimeError("provider down")

    monkeypatch.setattr(agent, "_rank_digest_recursive", always_fail)
    out = agent.rank_digests(_digests(6))
    assert len(out) == 6
    assert all(a.relevance_score == 5.0 for a in out)


def test_ranks_are_contiguous_after_a_partial_failure(monkeypatch):
    agent = _agent(monkeypatch)
    monkeypatch.setattr(ca, "CURATOR_CHUNK_SIZE", 3)

    def rank(chunk):
        if chunk[0]["id"] == "d0":
            raise RuntimeError("boom")
        return [
            RankedArticle(digest_id=d["id"], relevance_score=9.0, rank=i + 1, reasoning="ok")
            for i, d in enumerate(chunk)
        ]

    monkeypatch.setattr(agent, "_rank_digest_recursive", rank)
    out = agent.rank_digests(_digests(6))
    assert [a.rank for a in out] == list(range(1, 7))
    # Successfully ranked items (9.0) outrank the neutral fallbacks (5.0).
    assert out[0].relevance_score == 9.0
    assert out[-1].relevance_score == 5.0


def test_empty_input_returns_empty(monkeypatch):
    agent = _agent(monkeypatch)
    assert agent.rank_digests([]) == []


def test_split_recovers_when_a_smaller_batch_succeeds(monkeypatch):
    """The real recovery path: 12 fails, 6 fails, 3 works."""
    agent = _agent(monkeypatch)
    monkeypatch.setattr(ca, "CURATOR_CHUNK_SIZE", 12)

    seen = []

    def llm(chunk):
        seen.append(len(chunk))
        if len(chunk) > 3:
            raise _FakeJSONValidateError()
        return [
            RankedArticle(digest_id=d["id"], relevance_score=7.0, rank=i + 1, reasoning="ok")
            for i, d in enumerate(chunk)
        ]

    monkeypatch.setattr(agent, "_llm_rank_list", llm)
    out = agent.rank_digests(_digests(12))

    assert len(out) == 12
    assert all(a.relevance_score == 7.0 for a in out), "should be real scores, not fallbacks"
    assert max(seen) == 12 and min(seen) <= 3, "should have split down to a working size"
