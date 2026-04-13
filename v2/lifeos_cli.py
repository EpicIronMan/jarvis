#!/usr/bin/env python3
"""lifeos_cli.py — deterministic read-path harness for LifeOS v2.

Takes a Telegram-style message string, runs it through the router, dispatches
to a query handler, and prints the structured result as JSON. If the router
misses, falls through to the LLM classifier (handlers.classify).

Usage:
    python3 lifeos_cli.py "what are my stats"
    python3 lifeos_cli.py "weight yesterday"
    python3 lifeos_cli.py "nutrition last 7 days"
    python3 lifeos_cli.py "how did I sleep"
    python3 lifeos_cli.py "last bench"
    python3 lifeos_cli.py --list-intents

Exit codes:
    0  — routed and handled (even if result is empty)
    1  — routed but handler errored
    2  — unroutable message (no pattern matched AND LLM couldn't classify)
    3  — usage error
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
DB_PATH = V2_DIR / "lifeos.db"

# make sibling modules importable
sys.path.insert(0, str(V2_DIR))

from router import route, Intent, list_intents  # noqa: E402
from handlers import dates, query  # noqa: E402


def handle(intent: Intent, conn: sqlite3.Connection) -> dict:
    """Dispatch a routed Intent to the appropriate query function.

    Returns a result envelope dict. Always includes 'intent'. May include
    'date'/'range' (if the intent carried one), 'result' (handler output),
    or 'error' (if handler couldn't proceed).
    """
    name = intent.name
    f = intent.fields

    # --- zero-field intents ---
    if name == "stats":
        return {"intent": name, "result": query.stats_snapshot(conn)}
    if name == "weight_latest":
        return {"intent": name, "result": query.latest_weight(conn)}
    if name == "training_latest":
        return {"intent": name, "result": query.last_training_session(conn)}
    if name == "body_scan_latest":
        return {"intent": name, "result": query.latest_body_scan(conn)}
    if name == "cardio_latest":
        return {"intent": name, "result": query.cardio_recent(conn)}
    if name == "routine_today":
        return {
            "intent": name,
            "result": {
                "note": "routine table not yet seeded (Phase 2 seeds it). "
                        "Until then the bot has no deterministic answer for 'what should I do today'."
            },
        }

    # --- date-bearing intents ---
    if name in ("weight_for", "nutrition_for", "training_for", "recovery_for", "cardio_for"):
        raw = f.get("date", "")
        d = dates.resolve_date(raw)
        if not d:
            return {"intent": name, "error": f"could not resolve date token: {raw!r}"}
        if name == "weight_for":
            return {"intent": name, "date": d, "result": query.weight_for_date(conn, d)}
        if name == "nutrition_for":
            return {"intent": name, "date": d, "result": query.nutrition_for_date(conn, d)}
        if name == "training_for":
            return {"intent": name, "date": d, "result": query.training_on_date(conn, d)}
        if name == "recovery_for":
            return {"intent": name, "date": d, "result": query.recovery_for_date(conn, d)}
        if name == "cardio_for":
            return {"intent": name, "date": d, "result": query.cardio_on_date(conn, d)}

    # --- range intents ---
    if name in ("weight_range", "nutrition_range", "training_range", "recovery_range"):
        raw = f.get("range", "")
        r = dates.resolve_range(raw)
        if not r:
            return {"intent": name, "error": f"could not resolve range token: {raw!r}"}
        start, end = r
        if name == "weight_range":
            return {"intent": name, "range": [start, end], "result": query.weight_range(conn, start, end)}
        if name == "nutrition_range":
            return {"intent": name, "range": [start, end], "result": query.nutrition_range_summary(conn, start, end)}
        if name == "training_range":
            return {"intent": name, "range": [start, end], "result": query.training_range(conn, start, end)}
        if name == "recovery_range":
            return {"intent": name, "range": [start, end], "result": query.recovery_range(conn, start, end)}

    # --- last session of a specific exercise ---
    if name == "last_exercise":
        ex = f.get("exercise", "").strip()
        if not ex:
            return {"intent": name, "error": "no exercise extracted"}
        return {"intent": name, "exercise": ex, "result": query.last_session_of_exercise(conn, ex)}

    return {"intent": name, "error": "no handler implemented"}


def main():
    ap = argparse.ArgumentParser(description="LifeOS v2 read-path harness")
    ap.add_argument("message", nargs="*", help="the Telegram-style message to route")
    ap.add_argument("--db", default=str(DB_PATH), help="path to lifeos.db")
    ap.add_argument("--list-intents", action="store_true",
                    help="list all registered router intent names and exit")
    ap.add_argument("--no-llm", action="store_true",
                    help="disable LLM fallback classifier (router-only mode)")
    args = ap.parse_args()

    if args.list_intents:
        for n in list_intents():
            print(n)
        return 0

    if not args.message:
        print("usage: python3 lifeos_cli.py '<message>'", file=sys.stderr)
        return 3

    message = " ".join(args.message)
    intent = route(message)
    source = "router"

    # LLM fallback if router missed
    if intent is None and not args.no_llm:
        try:
            from handlers.classify import classify
            result = classify(message)
            if result and result.get("intent") and result["intent"] != "unknown":
                intent = Intent(name=result["intent"], fields=result.get("fields", {}))
                source = "llm_classifier"
        except Exception as e:
            # LLM classifier failed — fall through to unroutable
            source = f"llm_error: {e}"

    if intent is None:
        print(json.dumps({
            "message": message,
            "routed": False,
            "source": source,
            "note": "no pattern matched and LLM classifier could not classify",
        }, indent=2, default=str))
        return 2

    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"DB not found: {db_path}"}), file=sys.stderr)
        return 1

    conn = query.connect(db_path)
    try:
        result = handle(intent, conn)
    except Exception as e:
        conn.close()
        print(json.dumps({
            "message": message,
            "intent": intent.name,
            "fields": intent.fields,
            "error": f"handler raised {type(e).__name__}: {e}",
        }, indent=2, default=str), file=sys.stderr)
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    envelope = {"message": message, "routed": True, "source": source, **result}
    print(json.dumps(envelope, indent=2, default=str))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
