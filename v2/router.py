"""Deterministic intent router for LifeOS v2.

Given a user message string, returns an Intent (name + extracted fields) if
any regex pattern matches. Returns None if nothing matches — callers in
later phases fall through to an LLM classifier for truly ambiguous input.

Key property: the router EXTRACTS tokens but does not RESOLVE them. Dates
stay as raw strings here ("today", "yesterday", "2026-04-10") and get
resolved deterministically by handlers.dates downstream. This keeps the
regex grammar simple and the resolution rules in one place.

Patterns are priority-ordered — first match wins. Keep the most specific
patterns at the top so ambiguous inputs resolve the expected way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Intent:
    name: str
    fields: dict = field(default_factory=dict)


# (name, compiled_pattern, extract_fn)
_PATTERNS: list[tuple[str, re.Pattern, Callable]] = []


def _register(name: str, pattern: str, extract: Callable = lambda m: {}):
    _PATTERNS.append((name, re.compile(pattern, re.IGNORECASE), extract))


# ========= stats (full omnibus snapshot) =========

_register(
    "stats",
    r"^\s*(?:what\s+(?:are|is)\s+)?(?:my\s+)?(?:stats|status|current\s+stats|full\s+stats|all\s+stats|snapshot)\s*\??\s*$",
)


# ========= weight =========

# "weight today" / "weight yesterday" / "weight 2026-04-10"
_register(
    "weight_for",
    r"^\s*(?:what(?:'?s|\s+was|\s+is)?\s+)?(?:my\s+)?weight\s+(today|yesterday|\d{4}-\d{2}-\d{2})\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
# "latest weight" / "current weight"
_register(
    "weight_latest",
    r"^\s*(?:what(?:'?s|\s+is)?\s+)?(?:my\s+)?(?:latest|current|most\s+recent)\s+weight\s*\??\s*$",
)
# bare "weight" / "my weight"
_register(
    "weight_latest",
    r"^\s*(?:what(?:'?s|\s+is)?\s+)?(?:my\s+)?weight\s*\??\s*$",
)


# ========= nutrition =========

_register(
    "nutrition_for",
    r"^\s*(?:what\s+(?:were|was|are)\s+)?(?:my\s+)?(?:calories|cals|nutrition|protein|macros|food)\s+(today|yesterday|\d{4}-\d{2}-\d{2})\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
_register(
    "nutrition_for",
    r"^\s*(?:what\s+(?:did|have)\s+i\s+eat(?:en)?)\s+(today|yesterday|\d{4}-\d{2}-\d{2})\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)


# ========= training / workout =========

_register(
    "training_for",
    r"^\s*(?:what\s+(?:was|did)\s+)?(?:my\s+)?(?:training|workout|lift(?:ing)?|session)\s+(today|yesterday|\d{4}-\d{2}-\d{2})\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
_register(
    "training_latest",
    r"^\s*(?:what\s+was\s+)?(?:my\s+)?(?:last|latest|most\s+recent|previous)\s+(?:training|workout|lift|session)\s*\??\s*$",
)


# ========= recovery / sleep / steps =========

_register(
    "recovery_for",
    r"^\s*(?:what\s+(?:was|is)\s+)?(?:my\s+)?(?:sleep|recovery|steps)\s+(today|yesterday|last\s+night|\d{4}-\d{2}-\d{2})\s*\??\s*$",
    lambda m: {"date": "yesterday" if m.group(1).lower() == "last night" else m.group(1)},
)


# ========= body scan / DEXA =========

_register(
    "body_scan_latest",
    r"^\s*(?:what(?:'?s|\s+is)\s+)?(?:my\s+)?(?:latest\s+)?(?:dexa|body\s+scan|body\s+fat|lean\s+mass|bf\s*%?)\s*\??\s*$",
)


# ========= routine =========

_register(
    "routine_today",
    r"^\s*(?:what\s+(?:should\s+i\s+(?:do|train|lift)|am\s+i\s+doing))\s+today\s*\??\s*$",
)
_register(
    "routine_today",
    r"^\s*(?:today'?s?|my)\s+routine\s*\??\s*$",
)


# ========= last session of specific exercise =========

# "last time i did X" / "last session X" / "last X"
_register(
    "last_exercise",
    r"^\s*(?:when\s+was\s+)?(?:my\s+)?last\s+(?:session\s+of\s+|time\s+(?:i\s+did|doing)\s+)?([a-z][a-z0-9 '\-]*?)\s*\??\s*$",
    lambda m: {"exercise": m.group(1).strip()},
)


# ========= public API =========

def route(message: str) -> Intent | None:
    """Return an Intent if any registered pattern matches, else None."""
    if not message:
        return None
    msg = message.strip()
    if not msg:
        return None
    for name, pat, extract in _PATTERNS:
        m = pat.match(msg)
        if m:
            return Intent(name=name, fields=extract(m))
    return None


def list_intents() -> list[str]:
    """For CLI help / debugging — the set of registered intent names."""
    seen = []
    for name, _, _ in _PATTERNS:
        if name not in seen:
            seen.append(name)
    return seen
