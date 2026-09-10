"""What each subscriber tier is allowed to do.

Three tiers, derived from two columns:

* ``role="admin"`` — everything, plus the admin console. Overrides ``plan``.
* ``plan="pro"`` — full customization: topic bundles and keyword tracking.
* ``plan="free"`` (the default) — a fixed briefing: every bundle, no keywords.

This is the single source of truth for the pipeline. The web app mirrors it in
``web/src/lib/entitlements.ts``; keep the two in step.

Enforcement lives on the server, not just the UI. Previously the only gate was a
disabled button, so any account could still write keywords through the API, and
a subscriber downgraded from a paid tier would keep getting their custom lanes.
"""

from __future__ import annotations

from typing import Any

ROLE_USER = "user"
ROLE_ADMIN = "admin"
ALLOWED_ROLES: tuple[str, ...] = (ROLE_USER, ROLE_ADMIN)

PLAN_FREE = "free"
PLAN_PRO = "pro"
ALLOWED_PLANS: tuple[str, ...] = (PLAN_FREE, PLAN_PRO)

STATUS_TRIAL = "trial"
STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
ALLOWED_STATUSES: tuple[str, ...] = (STATUS_TRIAL, STATUS_ACTIVE, STATUS_EXPIRED)

TIER_FREE = "free"
TIER_PRO = "pro"
TIER_ADMIN = "admin"


def _clean(raw: Any) -> str:
    return str(raw or "").strip().lower()


def normalize_plan(raw: Any) -> str:
    """Unknown or missing plans are Free — never accidentally Pro."""
    plan = _clean(raw)
    return plan if plan in ALLOWED_PLANS else PLAN_FREE


def is_admin(role: Any) -> bool:
    return _clean(role) == ROLE_ADMIN


def effective_tier(role: Any, plan: Any) -> str:
    if is_admin(role):
        return TIER_ADMIN
    return TIER_PRO if normalize_plan(plan) == PLAN_PRO else TIER_FREE


def can_customize(role: Any, plan: Any) -> bool:
    """Choose topic bundles."""
    return effective_tier(role, plan) in (TIER_PRO, TIER_ADMIN)


def can_track_keywords(role: Any, plan: Any) -> bool:
    """Run private keyword lanes."""
    return effective_tier(role, plan) in (TIER_PRO, TIER_ADMIN)


def is_trial_exempt(role: Any, plan: Any, status: Any = None) -> bool:
    """Whether the 27-day trial clock may expire this subscriber.

    Admins and Pro are always exempt. So is anyone an admin has explicitly
    marked ``active``: the pipeline recomputes expiry from ``created_at`` on
    every run, so without this an admin reactivating a Free subscriber from the
    console would be silently reverted by the next run.
    """
    if effective_tier(role, plan) in (TIER_PRO, TIER_ADMIN):
        return True
    return _clean(status) == STATUS_ACTIVE
