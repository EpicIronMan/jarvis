"""Deterministic intent router for LifeOS v2.

Given a user message string, returns an Intent (name + extracted fields) if
any regex pattern matches. Returns None if nothing matches — callers fall
through to the LLM classifier (handlers.classify) for ambiguous input.

Key property: the router EXTRACTS tokens but does not RESOLVE them. Dates
stay as raw strings here ("today", "yesterday", "3 days ago", "monday",
"2026-04-10") and get resolved deterministically by handlers.dates downstream.
This keeps the regex grammar simple and the resolution rules in one place.

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


# ---------------------------------------------------------------------------
# Shared token fragments — reused across multiple intent patterns.
# ---------------------------------------------------------------------------

# Single date: "today", "yesterday", "now", "3 days ago", weekday names, ISO
_D = (
    r"(today|yesterday|now"
    r"|\d+\s+days?\s+ago"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun"
    r"|\d{4}-\d{2}-\d{2})"
)

# Range queries are handled by the LLM, not the router.

# Optional leading fluff: "what is/was/are/were", "what's", "what did"
_WH = r"(?:what(?:'?s|\s+(?:is|was|are|were|did))\s+)?"

# Optional "my "
_MY = r"(?:my\s+)?"


# ========= stats (full omnibus snapshot) =========

_register(
    "stats",
    r"^\s*" + _WH + _MY
    + r"(?:stats|status|current\s+stats|full\s+stats|all\s+stats|snapshot|overview|summary|dashboard)"
    + r"\s*\??\s*$",
)
_register(
    "stats",
    r"^\s*(?:how\s+am\s+i\s+doing|give\s+me\s+(?:a\s+)?(?:summary|overview|rundown))\s*\??\s*$",
)


# ========= weight =========

# weight + date: "weight today", "weight monday", "weight 3 days ago"
_register(
    "weight_for",
    r"^\s*" + _WH + _MY + r"weight\s+" + _D + r"\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
# weight + range: handled by LLM (natural language like "past few days")
# "weight trend" / "am I losing weight": handled by LLM
# "latest weight" / "current weight"
_register(
    "weight_latest",
    r"^\s*" + _WH + _MY + r"(?:latest|current|most\s+recent)\s+weight\s*\??\s*$",
)
# bare "weight" / "my weight"
_register(
    "weight_latest",
    r"^\s*" + _WH + _MY + r"weight\s*\??\s*$",
)


# ========= nutrition =========

# nutrition + date
_register(
    "nutrition_for",
    r"^\s*" + _WH + _MY
    + r"(?:calories|cals|nutrition|protein|macros|food)\s+"
    + _D + r"\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
# "what did I eat today/yesterday"
_register(
    "nutrition_for",
    r"^\s*(?:what\s+(?:did|have)\s+i\s+eat(?:en)?)\s+" + _D + r"\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
# nutrition + range: handled by LLM
# bare "nutrition" / "calories" / "macros" / "protein" → today
_register(
    "nutrition_for",
    r"^\s*" + _WH + _MY + r"(?:calories|cals|nutrition|protein|macros)\s*\??\s*$",
    lambda m: {"date": "today"},
)
# "what did I eat" (no date) → today
_register(
    "nutrition_for",
    r"^\s*(?:what\s+(?:did|have)\s+i\s+eat(?:en)?)\s*\??\s*$",
    lambda m: {"date": "today"},
)


# ========= training / workout =========

# training + date
_register(
    "training_for",
    r"^\s*" + _WH + _MY
    + r"(?:training|workout|lift(?:ing)?|session|exercises?)\s+"
    + _D + r"\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
# "what did I train/lift today"
_register(
    "training_for",
    r"^\s*(?:what\s+did\s+i\s+(?:train|lift|do))\s+" + _D + r"\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
# training + range: handled by LLM
# "last workout" / "latest session" / "previous training"
_register(
    "training_latest",
    r"^\s*" + _WH + _MY
    + r"(?:last|latest|most\s+recent|previous)\s+(?:training|workout|lift|session)"
    + r"\s*\??\s*$",
)
# bare "training" / "workout" → today
_register(
    "training_for",
    r"^\s*" + _WH + _MY + r"(?:training|workout)\s*\??\s*$",
    lambda m: {"date": "today"},
)


# ========= recovery / sleep / steps =========

# recovery + date (including "last night" → yesterday)
_register(
    "recovery_for",
    r"^\s*" + _WH + _MY
    + r"(?:sleep|recovery|steps|rest|hrv|resting\s+(?:heart\s+rate|hr))\s+"
    + _D.replace(")", "|last\\s+night)")  # extend date token with "last night"
    + r"\s*\??\s*$",
    lambda m: {"date": "yesterday" if "last night" in m.group(1).lower() else m.group(1)},
)
# "how did I sleep" / "how was my sleep" → yesterday
_register(
    "recovery_for",
    r"^\s*how\s+(?:did\s+i|was\s+(?:my\s+)?)\s*sleep\s*\??\s*$",
    lambda m: {"date": "yesterday"},
)
# "how many steps" / "steps today" already covered above, but also bare:
_register(
    "recovery_for",
    r"^\s*(?:how\s+many\s+)?steps\s*\??\s*$",
    lambda m: {"date": "today"},
)
# recovery + range: handled by LLM
# bare "sleep" / "recovery" → yesterday for sleep, today for recovery
_register(
    "recovery_for",
    r"^\s*" + _WH + _MY + r"sleep\s*\??\s*$",
    lambda m: {"date": "yesterday"},
)
_register(
    "recovery_for",
    r"^\s*" + _WH + _MY + r"recovery\s*\??\s*$",
    lambda m: {"date": "today"},
)


# ========= cardio =========

# cardio + date
_register(
    "cardio_for",
    r"^\s*" + _WH + _MY + r"cardio\s+" + _D + r"\s*\??\s*$",
    lambda m: {"date": m.group(1)},
)
# "last cardio" / "recent cardio"
_register(
    "cardio_latest",
    r"^\s*" + _WH + _MY + r"(?:last|latest|most\s+recent|previous|recent)\s+cardio\s*\??\s*$",
)
# bare "cardio"
_register(
    "cardio_latest",
    r"^\s*" + _WH + _MY + r"cardio\s*\??\s*$",
)


# ========= body scan / DEXA =========

_register(
    "body_scan_latest",
    r"^\s*" + _WH + _MY
    + r"(?:latest\s+)?(?:dexa|body\s+scan|body\s+fat|lean\s+mass|bf\s*%?|body\s+composition)"
    + r"\s*\??\s*$",
)


# ========= routine =========

_register(
    "routine_today",
    r"^\s*(?:what\s+(?:should\s+i\s+(?:do|train|lift|work\s+on)|am\s+i\s+doing))\s+today\s*\??\s*$",
)
_register(
    "routine_today",
    r"^\s*(?:today'?s?|my)\s+routine\s*\??\s*$",
)
_register(
    "routine_today",
    r"^\s*(?:what'?s?\s+(?:on\s+)?(?:the\s+)?plan\s+(?:for\s+)?today)\s*\??\s*$",
)


# ========= write intents =========

# "log weight 172" / "weight 172 lbs" / "log weight 172.5 renpho"
_register(
    "log_weight",
    r"^\s*(?:log\s+)?weight\s+(\d+(?:\.\d+)?)\s*(?:lbs?)?\s*(renpho|fitbit|manual)?\s*$",
    lambda m: {"weight_lbs": float(m.group(1)), "source": (m.group(2) or "TELEGRAM").upper()},
)

# Workout shorthand: "bench 275x5x3" / "bench 275x5x3 @8"
# Pattern: exercise_name weight x reps x sets [@ rpe]
_register(
    "log_workout_shorthand",
    r"^\s*([a-zA-Z][a-zA-Z \']+?)\s+(\d+(?:\.\d+)?)x(\d+)x(\d+)\s*(?:@\s*(\d+(?:\.\d+)?))?\s*$",
    lambda m: {
        "exercises": [{"name": m.group(1).strip(), "weight_lbs": float(m.group(2)),
                       "reps": int(m.group(3)), "sets": int(m.group(4)),
                       "rpe": float(m.group(5)) if m.group(5) else None}],
    },
)

# "log nutrition 2100 cal 170g protein" / "log 2100 cal 170 protein"
_register(
    "log_nutrition_shorthand",
    r"^\s*(?:log\s+)?(?:nutrition\s+)?(\d+)\s*(?:cal(?:ories?)?\s+)(\d+)\s*g?\s*(?:protein|prot|p)\s*$",
    lambda m: {"calories": float(m.group(1)), "protein_g": float(m.group(2))},
)

# "rename exercise old name to new name"
_register(
    "rename_exercise",
    r"^\s*rename\s+(?:exercise\s+)?(.+?)\s+to\s+(.+?)\s*$",
    lambda m: {"old_name": m.group(1).strip(), "new_name": m.group(2).strip()},
)

# "edit weight 2026-04-10 to 171.5"
_register(
    "edit_weight",
    r"^\s*edit\s+weight\s+(\d{4}-\d{2}-\d{2})\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*$",
    lambda m: {"date": m.group(1), "weight_lbs": float(m.group(2))},
)

# "sync fitbit" / "fitbit sync"
_register(
    "sync_fitbit",
    r"^\s*(?:sync\s+fitbit|fitbit\s+sync|pull\s+fitbit)\s*$",
)


# ========= last session of specific exercise =========

# "last time i did X" / "last session X" / "last X"
_register(
    "last_exercise",
    r"^\s*(?:when\s+was\s+)?(?:my\s+)?last\s+(?:session\s+(?:of|with)\s+|time\s+(?:i\s+did|doing)\s+)?([a-z][a-z0-9 '\-]*?)\s*\??\s*$",
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


def all_intent_names() -> set[str]:
    """All unique intent names — used by classify.py to validate LLM output."""
    names = {name for name, _, _ in _PATTERNS}
    # Range intents are handled by the LLM, not the router, but the
    # classifier still needs to know they exist so it can route to them.
    names |= {"weight_range", "nutrition_range", "training_range", "recovery_range"}
    return names
