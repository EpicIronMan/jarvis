#!/usr/bin/env python3
"""LifeOS Bot v2 — deterministic CRUD + Grok coaching via Telegram.

Architecture (v2):
  - CRUD (weight, nutrition, training, recovery, cardio, stats): deterministic
    Python router → SQLite handlers. No LLM involved in data operations.
  - Coaching, analysis, ambiguous queries: Grok via xAI (OpenAI-compatible SDK).
  - DEXA PDF parsing: Claude vision (narrow scope, extracts numbers only).
  - All data lives in v2/lifeos.db (SQLite).

See architecture.md and v2/README.md for the full system map.
"""

import os
import json
import subprocess
import datetime
import logging
import pathlib
import asyncio
import base64
import io
import re
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from openai import OpenAI
from zoneinfo import ZoneInfo

# --- Config ---
CHAT_ID = int(os.environ["CHAT_ID"])
ET = ZoneInfo("America/Toronto")

BASE_DIR = pathlib.Path(os.environ.get("LIFEOS_DIR", "/home/openclaw/lifeos"))
V2_DIR = BASE_DIR / "v2"
DB_PATH = V2_DIR / "lifeos.db"
MEMORY_DIR = BASE_DIR / "memory"
LOG_DIR = BASE_DIR / "logs"
UPLOAD_DIR = BASE_DIR / "uploads"
SOUL_PATH = BASE_DIR / "soul.md"

# Add v2 to path for imports
sys.path.insert(0, str(V2_DIR))

from router import route, Intent, all_intent_names
from handlers import dates, query, log as log_handlers
from handlers.classify import classify

AGENT_NAME = os.environ.get("AGENT_NAME", "J.A.R.V.I.S.")
AGENT_EMOJI = os.environ.get("AGENT_EMOJI", "\U0001f916")
MAX_CONVERSATION_MESSAGES = int(os.environ.get("MAX_CONVERSATION_MESSAGES", "200"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
lg = logging.getLogger("lifeos")

# --- xAI / Grok client (OpenAI-compatible) ---
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("XAI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.x.ai/v1")
MODEL = os.environ.get("AI_MODEL", "grok-4-1-fast")
_client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)


# --- System prompt ---

def _build_system_prompt() -> str:
    soul_text = SOUL_PATH.read_text() if SOUL_PATH.exists() else ""
    now = datetime.datetime.now(ET)
    return (
        soul_text
        + f"\n\nCurrent date/time: {now.strftime('%A, %Y-%m-%d %I:%M %p')} ET\n"
    )


# --- Formatting helpers ---

def _format_result(intent_name: str, result: dict | list | None, fields: dict = None) -> str:
    """Format a handler result into a readable Telegram message."""
    if result is None:
        return "No data found."

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if isinstance(result, dict) and "note" in result:
        return result["note"]

    # Stats snapshot
    if intent_name == "stats":
        return _format_stats(result)

    # Weight
    if intent_name == "weight_latest" and isinstance(result, dict):
        return f"Weight ({result.get('date', '?')}): {result.get('weight_lbs', '?')} lbs ({result.get('weight_kg', '?')} kg)"

    if intent_name == "weight_for" and isinstance(result, dict):
        return f"Weight ({result.get('date', '?')}): {result.get('weight_lbs', '?')} lbs"

    if intent_name == "weight_range" and isinstance(result, dict):
        n = result.get("n", 0)
        if n == 0:
            return "No weight data for that range."
        return (
            f"Weight trend ({n} days): {result.get('start_weight')} → {result.get('end_weight')} lbs "
            f"({result.get('change', 0):+.1f} lbs)\n"
            f"Range: {result.get('min_weight')} – {result.get('max_weight')} lbs"
        )

    # Nutrition
    if intent_name == "nutrition_for" and isinstance(result, dict):
        return (
            f"Nutrition ({result.get('date', '?')}): {result.get('calories', '?')} cal, "
            f"{result.get('protein_g', '?')}g protein"
        )

    if intent_name == "nutrition_range" and isinstance(result, dict):
        return (
            f"Nutrition avg ({result.get('n_with_calories', '?')} days): "
            f"{result.get('avg_calories', '?')} cal, {result.get('avg_protein_g', '?')}g protein"
        )

    # Training
    if intent_name in ("training_for", "training_latest"):
        if isinstance(result, dict) and "exercises" in result:
            exercises = result.get("exercises", [])
            if not exercises:
                return f"No training logged for {result.get('date', 'that date')}."
            lines = [f"Training ({result.get('date', '?')}):"]
            for ex in exercises:
                rpe = f" @{ex['rpe']}" if ex.get('rpe') else ""
                lines.append(f"  {ex['exercise']}: {ex['sets']}x{ex['reps']} @ {ex['weight_lbs']} lbs{rpe}")
            return "\n".join(lines)
        if isinstance(result, list):
            if not result:
                return "No training logged for that date."
            lines = [f"Training ({result[0].get('date', '?')}):"]
            for ex in result:
                rpe = f" @{ex['rpe']}" if ex.get('rpe') else ""
                lines.append(f"  {ex['exercise']}: {ex['sets']}x{ex['reps']} @ {ex['weight_lbs']} lbs{rpe}")
            return "\n".join(lines)

    if intent_name == "training_range" and isinstance(result, dict):
        return (
            f"Training ({result.get('n_sessions', 0)} sessions, "
            f"{result.get('n_exercises', 0)} exercises): {', '.join(result.get('dates', []))}"
        )

    # Recovery
    if intent_name == "recovery_for" and isinstance(result, dict):
        parts = [f"Recovery ({result.get('date', '?')}):"]
        if result.get('sleep_hours') is not None:
            parts.append(f"  Sleep: {result['sleep_hours']}h")
        if result.get('efficiency_pct') is not None:
            parts.append(f"  Efficiency: {result['efficiency_pct']}%")
        if result.get('steps') is not None:
            parts.append(f"  Steps: {result['steps']:,}")
        if result.get('resting_hr') is not None:
            parts.append(f"  Resting HR: {result['resting_hr']} bpm")
        return "\n".join(parts)

    if intent_name == "recovery_range" and isinstance(result, dict):
        return (
            f"Recovery avg ({result.get('n', 0)} days): "
            f"{result.get('avg_sleep_hours', '?')}h sleep, {result.get('avg_steps', '?')} steps"
        )

    # Body scan
    if intent_name == "body_scan_latest" and isinstance(result, dict):
        return (
            f"DEXA ({result.get('date', '?')}): {result.get('total_bf_pct', '?')}% BF, "
            f"{result.get('lean_mass_lbs', '?')} lbs lean mass, "
            f"RMR {result.get('rmr_cal', '?')} cal"
        )

    # Cardio
    if intent_name == "cardio_latest" and isinstance(result, list):
        if not result:
            return "No cardio sessions logged."
        lines = ["Recent cardio:"]
        for c in result[:5]:
            lines.append(f"  {c.get('date', '?')}: {c.get('exercise', '?')} {c.get('duration_min', '?')}min")
        return "\n".join(lines)

    if intent_name == "cardio_for" and isinstance(result, list):
        if not result:
            return "No cardio logged for that date."
        lines = []
        for c in result:
            lines.append(f"Cardio ({c.get('date', '?')}): {c.get('exercise', '?')} {c.get('duration_min', '?')}min, {c.get('net_calories', '?')} cal")
        return "\n".join(lines)

    # Write confirmations
    if intent_name in ("log_weight", "log_workout_shorthand", "log_nutrition_shorthand",
                        "log_cardio", "log_body_scan", "rename_exercise", "edit_weight"):
        return _format_write_confirmation(result)

    # Last exercise
    if intent_name == "last_exercise" and isinstance(result, dict):
        if not result.get("date"):
            ex = fields.get("exercise", "that exercise") if fields else "that exercise"
            return f"No sessions found for '{ex}'."
        matched = result.get("matched_exercise", "")
        exercises = result.get("exercises", [])
        lines = [f"Last session with {matched} ({result['date']}):"]
        for ex in exercises:
            rpe = f" @{ex['rpe']}" if ex.get('rpe') else ""
            lines.append(f"  {ex['exercise']}: {ex['sets']}x{ex['reps']} @ {ex['weight_lbs']} lbs{rpe}")
        return "\n".join(lines)

    # Fallback: JSON dump
    return json.dumps(result, indent=2, default=str)


def _format_stats(result: dict) -> str:
    lines = ["Here's your current snapshot:"]

    w = result.get("latest_weight")
    if w:
        lines.append(f"\nWeight: {w.get('weight_lbs', '?')} lbs ({w.get('date', '?')})")

    scan = result.get("latest_body_scan")
    if scan:
        lines.append(f"DEXA BF%: {scan.get('total_bf_pct', '?')}% ({scan.get('date', '?')})")
        if scan.get("lean_mass_lbs"):
            lines.append(f"Lean mass: {scan['lean_mass_lbs']} lbs")

    nut = result.get("nutrition", {})
    nut_data = nut.get("data") if isinstance(nut, dict) else nut
    if nut_data:
        label = f" ({nut.get('as_of', '')})" if isinstance(nut, dict) else ""
        lines.append(f"\nNutrition{label}: {nut_data.get('calories', '?')} cal, {nut_data.get('protein_g', '?')}g protein")

    rec = result.get("recovery", {})
    rec_data = rec.get("data") if isinstance(rec, dict) else rec
    if rec_data:
        label = f" ({rec.get('as_of', '')})" if isinstance(rec, dict) else ""
        parts = []
        if rec_data.get("sleep_hours"):
            parts.append(f"{rec_data['sleep_hours']}h sleep")
        if rec_data.get("steps"):
            parts.append(f"{rec_data['steps']:,} steps")
        if parts:
            lines.append(f"Recovery{label}: {', '.join(parts)}")

    t = result.get("last_training")
    if t and t.get("date"):
        exercises = [ex["exercise"] for ex in t.get("exercises", [])[:4]]
        lines.append(f"\nLast workout ({t['date']}): {', '.join(exercises)}")

    return "\n".join(lines)


def _format_write_confirmation(result: dict) -> str:
    action = result.get("action", "unknown")
    if action == "log_weight":
        return f"Logged weight: {result.get('weight_lbs')} lbs ({result.get('weight_kg')} kg) on {result.get('date')}"
    if action == "log_workout":
        exercises = result.get("exercises", [])
        names = [e["exercise"] for e in exercises]
        return f"Logged {len(exercises)} exercises ({', '.join(names)}), total volume: {result.get('total_volume', 0):,.0f} lbs"
    if action == "log_nutrition":
        return f"Logged nutrition: {result.get('calories')} cal, {result.get('protein_g')}g protein on {result.get('date')}"
    if action == "log_cardio":
        return f"Logged cardio: {result.get('exercise')} {result.get('duration_min')}min, {result.get('net_calories')} cal"
    if action == "rename_exercise":
        return f"Renamed '{result.get('old_name')}' → '{result.get('new_name')}' ({result.get('rows_updated', 0)} rows updated)"
    if action == "edit_weight":
        return f"Updated weight for {result.get('date')}: {result.get('weight_lbs')} lbs"
    return json.dumps(result, default=str)


# --- v2 CRUD dispatch ---

def _handle_crud(intent: Intent, conn) -> str:
    """Dispatch a routed intent to the appropriate handler. Returns formatted text."""
    name = intent.name
    f = intent.fields

    # Read intents (zero-field)
    if name == "stats":
        return _format_result(name, query.stats_snapshot(conn))
    if name == "weight_latest":
        return _format_result(name, query.latest_weight(conn))
    if name == "training_latest":
        return _format_result(name, query.last_training_session(conn))
    if name == "body_scan_latest":
        return _format_result(name, query.latest_body_scan(conn))
    if name == "cardio_latest":
        return _format_result(name, query.cardio_recent(conn))
    if name == "routine_today":
        return "Routine table not yet seeded. Tell me your weekly split and I'll set it up."

    # Date-bearing reads
    if name in ("weight_for", "nutrition_for", "training_for", "recovery_for", "cardio_for"):
        raw = f.get("date", "")
        d = dates.resolve_date(raw)
        if not d:
            return f"Couldn't resolve date: '{raw}'"
        handlers = {
            "weight_for": lambda: query.weight_for_date(conn, d),
            "nutrition_for": lambda: query.nutrition_for_date(conn, d),
            "training_for": lambda: query.training_on_date(conn, d),
            "recovery_for": lambda: query.recovery_for_date(conn, d),
            "cardio_for": lambda: query.cardio_on_date(conn, d),
        }
        result = handlers[name]()
        return _format_result(name, result, f)

    # Range reads
    if name in ("weight_range", "nutrition_range", "training_range", "recovery_range"):
        raw = f.get("range", "")
        r = dates.resolve_range(raw)
        if not r:
            return f"Couldn't resolve range: '{raw}'"
        start, end = r
        handlers = {
            "weight_range": lambda: query.weight_range(conn, start, end),
            "nutrition_range": lambda: query.nutrition_range_summary(conn, start, end),
            "training_range": lambda: query.training_range(conn, start, end),
            "recovery_range": lambda: query.recovery_range(conn, start, end),
        }
        return _format_result(name, handlers[name](), f)

    # Exercise lookup
    if name == "last_exercise":
        ex = f.get("exercise", "").strip()
        if not ex:
            return "No exercise specified."
        return _format_result(name, query.last_session_of_exercise(conn, ex), f)

    # Write intents
    if name == "log_weight":
        result = log_handlers.log_weight(conn, f["weight_lbs"], source=f.get("source", "TELEGRAM"))
        return _format_result(name, result)
    if name == "log_workout_shorthand":
        result = log_handlers.log_workout(conn, f["exercises"])
        return _format_result(name, result)
    if name == "log_nutrition_shorthand":
        result = log_handlers.log_nutrition(conn, f["calories"], f["protein_g"])
        return _format_result(name, result)
    if name == "rename_exercise":
        result = log_handlers.rename_exercise(conn, f["old_name"], f["new_name"])
        return _format_result(name, result)
    if name == "edit_weight":
        result = log_handlers.edit_weight(conn, f["date"], f["weight_lbs"])
        return _format_result(name, result)
    if name == "sync_fitbit":
        return _do_fitbit_sync()

    return f"Intent '{name}' recognized but no handler implemented."


def _do_fitbit_sync() -> str:
    try:
        result = subprocess.run(
            ["python3", str(V2_DIR / "ingest_fitbit.py")],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HOME": "/home/openclaw"},
        )
        if result.returncode != 0:
            return f"Fitbit sync failed: {result.stderr.strip()[:300]}"
        return "Fitbit sync completed — data updated in SQLite."
    except subprocess.TimeoutExpired:
        return "Fitbit sync timed out after 60s."


# --- LLM tools (OpenAI format for xAI/Grok) ---

def _tool(name, desc, params):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": params}}

TOOLS = [
    _tool("save_memory", "Save a user decision, preference, or goal to memory.md.",
          {"type": "object", "properties": {"entry": {"type": "string"}}, "required": ["entry"]}),
    _tool("propose_soul_change", "Propose a change to soul.md behavioral rules for Claude Code to review.",
          {"type": "object", "properties": {
              "proposed_text": {"type": "string"}, "section": {"type": "string"},
              "reasoning": {"type": "string"}, "source_message": {"type": "string"},
          }, "required": ["proposed_text", "section", "reasoning", "source_message"]}),
    _tool("read_memory", "Read the user's saved memories and goals.",
          {"type": "object", "properties": {}}),
    _tool("query_data",
          "Query fitness data from SQLite. Available: stats, weight_latest, weight_for, weight_range, "
          "nutrition_for, nutrition_range, training_for, training_latest, training_range, recovery_for, "
          "recovery_range, body_scan_latest, cardio_latest, last_exercise.",
          {"type": "object", "properties": {
              "intent": {"type": "string", "description": "Query intent name"},
              "date": {"type": "string", "description": "Date token"},
              "range": {"type": "string", "description": "Range token"},
              "exercise": {"type": "string", "description": "Exercise name"},
          }, "required": ["intent"]}),
    _tool("log_workout", "Log workout exercises to SQLite.",
          {"type": "object", "properties": {
              "exercises": {"type": "array", "items": {"type": "object", "properties": {
                  "name": {"type": "string"}, "sets": {"type": "integer"},
                  "reps": {"type": "integer"}, "weight_lbs": {"type": "number"},
                  "rpe": {"type": "number"},
              }, "required": ["name", "sets", "reps", "weight_lbs"]}},
              "session_type": {"type": "string"},
          }, "required": ["exercises"]}),
    _tool("log_weight", "Log a body weight entry to SQLite.",
          {"type": "object", "properties": {
              "weight_lbs": {"type": "number"}, "source": {"type": "string"}, "notes": {"type": "string"},
          }, "required": ["weight_lbs"]}),
    _tool("log_nutrition", "Log daily nutrition to SQLite.",
          {"type": "object", "properties": {
              "calories": {"type": "number"}, "protein_g": {"type": "number"},
              "carbs_g": {"type": "number"}, "fat_g": {"type": "number"},
          }, "required": ["calories", "protein_g"]}),
    _tool("log_cardio", "Log a cardio session to SQLite.",
          {"type": "object", "properties": {
              "exercise": {"type": "string"}, "duration_min": {"type": "number"},
              "net_calories": {"type": "number"}, "met_used": {"type": "number"}, "notes": {"type": "string"},
          }, "required": ["exercise", "duration_min", "net_calories"]}),
    _tool("sync_fitbit", "Trigger an immediate Fitbit data sync to SQLite.",
          {"type": "object", "properties": {}}),
]


def _execute_tool(name: str, input_data: dict, conn) -> str:
    """Execute a tool call from the LLM."""
    if name == "save_memory":
        path = MEMORY_DIR / "memory.md"
        entry = input_data["entry"].strip()
        with open(path, "a") as f:
            f.write(f"\n- {entry}\n")
        return "Remembered."

    if name == "propose_soul_change":
        proposals_path = BASE_DIR / "soul-proposals.jsonl"
        now = datetime.datetime.now(ET)
        entry = {
            "id": now.strftime("%Y%m%d%H%M%S"),
            "timestamp": now.isoformat(),
            "status": "pending",
            "proposed_text": input_data["proposed_text"],
            "section": input_data["section"],
            "reasoning": input_data["reasoning"],
            "source_message": input_data["source_message"],
        }
        with open(proposals_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return f"Soul proposal #{entry['id']} filed for review."

    if name == "read_memory":
        path = MEMORY_DIR / "memory.md"
        return path.read_text() if path.exists() else "No memories saved yet."

    if name == "query_data":
        intent = Intent(name=input_data["intent"], fields={
            k: v for k, v in input_data.items() if k != "intent" and v
        })
        return _handle_crud(intent, conn)

    if name == "log_workout":
        result = log_handlers.log_workout(conn, input_data["exercises"],
                                          session_type=input_data.get("session_type", "BRO_SPLIT"))
        return _format_write_confirmation(result)

    if name == "log_weight":
        result = log_handlers.log_weight(conn, input_data["weight_lbs"],
                                         source=input_data.get("source", "TELEGRAM"),
                                         notes=input_data.get("notes", ""))
        return _format_write_confirmation(result)

    if name == "log_nutrition":
        result = log_handlers.log_nutrition(conn, input_data["calories"], input_data["protein_g"],
                                            carbs_g=input_data.get("carbs_g"),
                                            fat_g=input_data.get("fat_g"))
        return _format_write_confirmation(result)

    if name == "log_cardio":
        result = log_handlers.log_cardio(conn, input_data["exercise"], input_data["duration_min"],
                                         input_data["net_calories"],
                                         met_used=input_data.get("met_used"),
                                         notes=input_data.get("notes", ""))
        return _format_write_confirmation(result)

    if name == "sync_fitbit":
        return _do_fitbit_sync()

    return f"Unknown tool: {name}"


# --- AI conversation (Anthropic SDK) ---

def ask_ai(user_content: str | list, conversation: list[dict]) -> tuple[str, list]:
    """Send to Grok for coaching/analysis. Handles tool calls.

    Creates its own SQLite connection because this runs in a worker thread
    via asyncio.to_thread — SQLite connections can't cross threads.
    """
    import time as _time
    conn = query.connect(DB_PATH)
    conversation.append({"role": "user", "content": user_content})
    tool_log = []
    system_prompt = _build_system_prompt()

    # Inject current stats context so the model doesn't need to query for basic stuff
    stats = query.stats_snapshot(conn)
    stats_context = (
        f"\n\n[Current data from SQLite — use this, don't query unless you need something specific]\n"
        f"{json.dumps(stats, indent=2, default=str)}\n"
    )

    for _ in range(10):  # max tool rounds
        try:
            response = _client.chat.completions.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "system", "content": system_prompt + stats_context}] + conversation,
                tools=TOOLS,
            )
        except Exception as e:
            if "429" in str(e):
                conn.close()
                return "API rate limited. Try again in a minute.", tool_log
            conn.close()
            return f"API error: {e}", tool_log

        msg = response.choices[0].message
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        conversation.append(assistant_msg)

        if not msg.tool_calls:
            conn.close()
            return msg.content or "I'm not sure how to help with that.", tool_log

        # Execute tools and add results
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            lg.info("Tool call: %s(%s)", fn_name, json.dumps(fn_args)[:200])
            result = _execute_tool(fn_name, fn_args, conn)
            lg.info("Tool result: %s", result[:200])
            tool_log.append({"tool": fn_name, "input": fn_args, "result": result[:500]})
            conversation.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    conn.close()
    return "Hit the tool call limit. Try a simpler request.", tool_log


# --- PDF handling ---

def _pdf_to_base64_images(pdf_path: str, first_page: int = 1, last_page: int | None = None):
    from pdf2image import convert_from_path
    from pdf2image.pdf2image import pdfinfo_from_path
    info = pdfinfo_from_path(pdf_path)
    total_pages = info["Pages"]
    kwargs = {"dpi": 200, "first_page": first_page}
    if last_page is not None:
        kwargs["last_page"] = last_page
    images = convert_from_path(pdf_path, **kwargs)
    b64_images = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64_images.append(base64.b64encode(buf.getvalue()).decode())
    return b64_images, total_pages


# --- Conversation logging ---

def _today() -> str:
    return datetime.datetime.now(ET).strftime("%Y-%m-%d")


def log_conversation(user_text: str, reply: str, tool_calls: list | None = None):
    today = _today()
    log_file = LOG_DIR / f"{today}.jsonl"
    entry = {
        "ts": datetime.datetime.now(ET).isoformat(),
        "model": MODEL,
        "user": user_text,
        "assistant": reply,
    }
    if tool_calls:
        entry["tools"] = tool_calls
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_conversation_from_logs() -> list[dict]:
    """Reload today's conversation from log."""
    today = _today()
    log_file = LOG_DIR / f"{today}.jsonl"
    conv = []
    if not log_file.exists():
        return conv
    try:
        for line in log_file.read_text().strip().split("\n"):
            if not line:
                continue
            entry = json.loads(line)
            user_msg = entry.get("user", "")
            assistant_msg = entry.get("assistant", "")
            if user_msg:
                conv.append({"role": "user", "content": user_msg})
            if assistant_msg:
                # Strip emoji prefix from history
                assistant_msg = re.sub(r'^[\U0001f916\U0001f52c\s]+\n?', '', assistant_msg).lstrip()
                conv.append({"role": "assistant", "content": assistant_msg})
    except Exception as e:
        lg.warning("Failed to load conversation history: %s", e)
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv = conv[-MAX_CONVERSATION_MESSAGES:]
    return conv


# --- Monitoring (passive — flags issues, never intervenes) ---

WRITE_TOOLS = {"log_workout", "log_weight", "log_nutrition", "log_cardio",
               "save_memory", "propose_soul_change", "query_data", "sync_fitbit"}


def _append_failure_notice(reply: str, tools_used: list[dict]) -> str:
    """If any tool failed and the bot didn't mention it, append a notice."""
    failed = [t for t in tools_used
              if any(kw in t.get("result", "") for kw in ("FAILED", "ERROR", "error", "failed"))]
    if not failed:
        return reply
    failure_keywords = ("fail", "error", "could not", "unable", "didn't work")
    if not any(kw in reply.lower() for kw in failure_keywords):
        notice = "\n\n" + " | ".join(f"{t['tool']} failed" for t in failed) + " — action(s) did NOT complete."
        return reply + notice
    return reply


def _append_write_hallucination_notice(reply: str, tools_used: list[dict]) -> str:
    """If the bot claims it wrote data but made no write tool calls, append warning."""
    action_phrases = (
        r"i(?:'ve| have) (?:just |now )?(?:updated|fixed|corrected|logged|written|cleared|deleted|removed|saved|added)",
        r"let me (?:correct|fix|update|delete|remove|clear|log|save|add)",
        r"i (?:will|shall) (?:now )?(?:correct|fix|update|delete|remove|clear|log|save|add)",
    )
    reply_lower = reply.lower()
    claimed = any(re.search(p, reply_lower) for p in action_phrases)
    if not claimed:
        return reply
    used_write_tool = any(t.get("tool") in WRITE_TOOLS for t in tools_used)
    if used_write_tool:
        return reply
    return reply + "\n\n_I claimed to make changes but didn't call a write tool. The data was NOT changed. Tell me to actually do it._"


# --- Response formatting ---

def _clean_content(reply: str) -> str:
    reply = re.sub(r'^[\U0001f916\U0001f52c\s]*\n?', '', reply).lstrip()
    _name_pat = re.escape(AGENT_NAME)
    reply = re.sub(rf'^{_name_pat}\s*>?\s*\n?', '', reply, flags=re.IGNORECASE).lstrip()
    return reply


# --- Telegram handlers ---

conversations: dict[int, list] = {}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != CHAT_ID:
        return

    user_text = update.message.text
    if not user_text:
        return

    lg.info("Message: %s", user_text[:100])

    conn = query.connect(DB_PATH)
    try:
        # Step 1: Try deterministic routing
        intent = route(user_text)
        source = "router"

        if intent:
            # CRUD — no LLM call needed
            reply = _handle_crud(intent, conn)
            tools_used = []
        else:
            # Step 2: Try LLM classifier
            try:
                classified = classify(user_text)
                if classified and classified.get("intent") != "unknown" and classified.get("confidence") != "low":
                    intent = Intent(name=classified["intent"], fields=classified.get("fields", {}))
                    reply = _handle_crud(intent, conn)
                    tools_used = []
                    source = "llm_classifier"
                else:
                    # Step 3: Full coaching conversation with Claude Sonnet
                    source = "llm_coaching"
                    cid = update.effective_chat.id
                    conv = conversations.get(cid)
                    if conv is None:
                        conv = load_conversation_from_logs()
                        conversations[cid] = conv
                    if len(conv) > MAX_CONVERSATION_MESSAGES:
                        conv[:] = conv[-MAX_CONVERSATION_MESSAGES:]
                    reply, tools_used = await asyncio.to_thread(ask_ai, user_text, conv)
            except Exception as e:
                lg.exception("Classification/coaching error")
                reply = f"Something went wrong: {e}"
                tools_used = []

    finally:
        conn.close()

    reply = _clean_content(reply)
    # Apply monitors (only relevant for coaching mode with tool calls)
    if tools_used:
        reply = _append_failure_notice(reply, tools_used)
        reply = _append_write_hallucination_notice(reply, tools_used)
    reply = AGENT_EMOJI + "\n" + reply

    log_conversation(user_text, reply, tools_used if tools_used else None)

    # Send to Telegram
    for i in range(0, len(reply), 4096):
        try:
            await update.message.reply_text(reply[i:i+4096])
        except Exception as e:
            lg.error("Telegram send failed: %s", e)


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.id == CHAT_ID:
        conversations.pop(CHAT_ID, None)
        await update.message.reply_text("Conversation cleared.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != CHAT_ID:
        return

    doc = update.message.document
    if not doc:
        return

    file = await doc.get_file()
    filename = doc.file_name or f"upload_{_today()}"
    local_path = UPLOAD_DIR / filename
    await file.download_to_drive(str(local_path))
    lg.info("Downloaded: %s", local_path)

    caption = update.message.caption or ""

    try:
        if filename.lower().endswith(".pdf"):
            # Check if it's a DEXA scan
            is_dexa = "dexa" in filename.lower() or "dexa" in caption.lower()
            if is_dexa:
                from handlers.dexa import extract_dexa_from_pdf
                conn = query.connect(DB_PATH)
                # Extract date from filename or use today
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
                scan_date = date_match.group(1) if date_match else _today()
                result = extract_dexa_from_pdf(str(local_path), conn, scan_date)
                conn.close()
                if "error" in result:
                    reply = f"DEXA extraction failed: {result['error']}"
                else:
                    reply = f"DEXA scan processed ({scan_date}): {result.get('extracted', {}).get('total_bf_pct', '?')}% BF"
                tools_used = [{"tool": "extract_dexa", "input": {"file": filename}, "result": str(result)[:500]}]
            else:
                # Generic PDF — send to LLM with vision
                try:
                    b64_images, total_pages = _pdf_to_base64_images(str(local_path), first_page=1, last_page=5)
                    content = [
                        {"type": "text", "text": f"[PDF uploaded: {filename}] {caption}".strip()},
                    ]
                    for b64 in b64_images:
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        })
                    conv = conversations.setdefault(CHAT_ID, [])
                    reply, tools_used = await asyncio.to_thread(ask_ai, content, conv)
                except Exception as e:
                    reply = f"PDF processing failed: {e}"
                    tools_used = []
        else:
            reply = f"File saved: {filename}"
            tools_used = []
    except Exception as e:
        lg.exception("Document handler error")
        reply = f"Something went wrong: {e}"
        tools_used = []

    reply = _clean_content(reply)
    reply = AGENT_EMOJI + "\n" + reply
    log_conversation(f"[File: {filename}] {caption}", reply, tools_used if tools_used else None)

    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i:i+4096])


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != CHAT_ID:
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    filename = f"photo_{_today()}_{photo.file_unique_id}.jpg"
    local_path = UPLOAD_DIR / filename
    await file.download_to_drive(str(local_path))

    caption = update.message.caption or ""

    # Send photo to LLM with vision
    with open(local_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    content = [
        {"type": "text", "text": f"[Photo uploaded: {filename}] {caption}".strip()},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]

    conv = conversations.setdefault(CHAT_ID, [])
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, content, conv)
    except Exception as e:
        reply = f"Something went wrong: {e}"
        tools_used = []

    reply = _clean_content(reply)
    reply = AGENT_EMOJI + "\n" + reply
    log_conversation(f"[Photo: {filename}] {caption}", reply, tools_used if tools_used else None)

    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i:i+4096])


def main():
    lg.info("Starting LifeOS bot v2 (model: %s)", MODEL)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    app = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("clear", handle_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    lg.info("Bot is polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
