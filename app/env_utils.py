"""
Numeric environment settings that survive CI.

GitHub Actions renders `VAR: ${{ vars.X }}` as an **empty string** when the
repository variable doesn't exist. `os.getenv("VAR", "5")` then returns `""`,
not `"5"`, and `int("")` raises — which is exactly how the Instagram workflow
died on a box where everything was configured correctly.

These helpers treat empty, whitespace and unparseable values as "not set", log
once, and clamp to the supported range. Prefer them over `int(os.getenv(...))`
for anything a workflow can pass.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _raw(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _clamp(value: float, minimum: Optional[float], maximum: Optional[float]) -> float:
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def env_int(
    name: str,
    default: int,
    *,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    raw = _raw(name)
    if not raw:
        return int(_clamp(default, minimum, maximum))
    try:
        parsed = int(float(raw))  # tolerate "5.0" from a templated value
    except ValueError:
        logger.warning("%s=%r is not a number — using %s", name, raw, default)
        parsed = default
    return int(_clamp(parsed, minimum, maximum))


def env_float(
    name: str,
    default: float,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    raw = _raw(name)
    if not raw:
        return float(_clamp(default, minimum, maximum))
    try:
        parsed = float(raw)
    except ValueError:
        logger.warning("%s=%r is not a number — using %s", name, raw, default)
        parsed = default
    return float(_clamp(parsed, minimum, maximum))


def env_str(name: str, default: str = "") -> str:
    """Empty or whitespace-only (an unset Actions variable) means "not set"."""
    return _raw(name) or default
