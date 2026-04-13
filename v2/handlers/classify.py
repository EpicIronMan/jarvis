"""LLM fallback classifier for router misses.

When the deterministic router (router.py) returns None, this module sends
the user message to Claude Haiku with a strict JSON contract. The model
picks an intent name from the known set or returns "unknown". Any
hallucinated intent name is rejected — dispatch only happens through
the same handler functions the router uses.

This is the ONLY place in v2 where the model makes a routing decision.
It must never run SQL, resolve dates, or produce user-facing prose here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

from router import all_intent_names

# Lazy client — initialized on first call
_client: anthropic.Anthropic | None = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # Source API key from env (loaded from /opt/openclaw.env by caller)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — cannot use LLM classifier")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def classify(message: str) -> dict | None:
    """Classify a message into a known intent using Claude Haiku.

    Returns a dict with:
      - intent: str (a valid intent name from router.all_intent_names, or "unknown")
      - fields: dict (extracted fields like {"date": "today"}, {"exercise": "bench"})
      - confidence: str ("high" | "medium" | "low")

    Returns None only on API/parsing failure (caller should treat as unroutable).
    """
    valid_intents = sorted(all_intent_names())

    system_prompt = f"""You are a strict intent classifier for a fitness tracking bot.

Given a user message, classify it into exactly one of these intents:
{json.dumps(valid_intents)}

Or return "unknown" if the message doesn't fit any intent.

Rules:
- Only return intent names from the list above. No other names.
- Extract relevant fields: "date" for date-bearing queries, "exercise" for exercise queries, "range" for range queries.
- Date fields should be the raw token from the message (e.g. "today", "yesterday", "monday", "3 days ago", "2026-04-10").
- Range fields should be the raw token (e.g. "last 7 days", "this week").
- For bare queries with no date, infer the most logical default (e.g. "how's my protein" → nutrition_for with date "today").
- Respond with ONLY a JSON object, no other text.

Response format:
{{"intent": "<intent_name>", "fields": {{}}, "confidence": "high|medium|low"}}"""

    try:
        client = _get_client()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        )
        raw = resp.content[0].text.strip()

        # Parse JSON — strip markdown fences if the model wraps it
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        parsed = json.loads(raw)

        intent = parsed.get("intent", "unknown")
        fields = parsed.get("fields", {})
        confidence = parsed.get("confidence", "low")

        # Reject hallucinated intent names
        if intent not in valid_intents and intent != "unknown":
            return {"intent": "unknown", "fields": {}, "confidence": "low",
                    "note": f"model returned invalid intent '{intent}', rejected"}

        return {"intent": intent, "fields": fields, "confidence": confidence}

    except (json.JSONDecodeError, anthropic.APIError, KeyError, IndexError) as e:
        return None
