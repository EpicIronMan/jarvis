#!/usr/bin/env python3
"""LifeOS Bot — AI fitness coach accessible via Telegram (or other chat interfaces).

All code, config, and docs live in /home/openclaw/lifeos/ (git repo).
See architecture.md for the full system map.

Config is driven by environment variables — swap the AI model, API provider,
or chat platform by changing env vars, not code.
"""

import os
import json
import subprocess
import datetime
import logging
import pathlib
import asyncio

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from openai import OpenAI

# --- Config (all from env vars — no personal info in code) ---
CHAT_ID = int(os.environ["CHAT_ID"])
SHEET_ID = os.environ["SHEET_ID"]
DRIVE_UPLOADS_FOLDER = os.environ["DRIVE_UPLOADS_FOLDER"]
UPLOAD_INDEX_FILE_ID = os.environ["UPLOAD_INDEX_FILE_ID"]
GOG = os.environ.get("GOG_PATH", "/usr/local/bin/gog")
GOG_ACCOUNT = os.environ["GOG_ACCOUNT"]

BASE_DIR = pathlib.Path(os.environ.get("LIFEOS_DIR", "/home/openclaw/lifeos"))
MEMORY_DIR = BASE_DIR / "memory"
LOG_DIR = BASE_DIR / "logs"
UPLOAD_DIR = BASE_DIR / "uploads"
SOUL_PATH = BASE_DIR / "soul.md"

# AI model config — swap provider by changing these env vars
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("XAI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.x.ai/v1")
MODEL = os.environ.get("AI_MODEL", "grok-4-1-fast")
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "10"))
MAX_CONVERSATION_MESSAGES = int(os.environ.get("MAX_CONVERSATION_MESSAGES", "200"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("lifeos")

# --- Load system prompt ---
_SOUL_TEXT = SOUL_PATH.read_text() if SOUL_PATH.exists() else ""


def _build_system_prompt() -> str:
    """Build system prompt with current date/time and sheet link injected."""
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now(ZoneInfo("America/Toronto"))
    context = (
        f"\n\nCurrent date/time: {now.strftime('%A, %Y-%m-%d %I:%M %p')} ET\n"
        f"Google Sheet link: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit\n"
    )
    return _SOUL_TEXT + context

# --- gog environment ---
GOG_ENV = {
    **os.environ,
    "HOME": "/home/openclaw",
    "GOG_ACCOUNT": GOG_ACCOUNT,
    "GOG_KEYRING_PASSWORD": os.environ.get("GOG_KEYRING_PASSWORD", ""),
}

# --- Tool definitions (OpenAI format, used by xAI) ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "log_workout",
            "description": (
                "Log workout exercises to the Training Log Google Sheet. "
                "Call ONLY after the user confirms the parsed workout summary. "
                "Columns: Date | Exercise | Sets | Reps | Weight (lbs) | RPE | Volume (lbs) | Session Type | Data Source"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "exercises": {
                        "type": "array",
                        "description": "List of exercises performed",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Exercise name"},
                                "sets": {"type": "integer"},
                                "reps": {"type": "integer"},
                                "weight_lbs": {"type": "number"},
                                "rpe": {"type": "number", "description": "Rate of perceived exertion (1-10), optional"},
                            },
                            "required": ["name", "sets", "reps", "weight_lbs"],
                        },
                    },
                    "session_type": {
                        "type": "string",
                        "description": "e.g. BRO_SPLIT, PUSH_PULL_LEGS",
                        "default": "BRO_SPLIT",
                    },
                },
                "required": ["exercises"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_weight",
            "description": (
                "Log a body weight entry to Body Metrics Google Sheet. "
                "Columns: Date | Weight (lbs) | Weight (kg) | Body Fat % | Muscle Mass (kg) | Water % | BMI | Data Source | Notes"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "weight_lbs": {"type": "number"},
                    "body_fat_pct": {"type": "number", "description": "Optional body fat %"},
                    "data_source": {"type": "string", "default": "RENPHO"},
                    "notes": {"type": "string", "default": ""},
                },
                "required": ["weight_lbs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_nutrition",
            "description": (
                "Log daily nutrition to Nutrition Google Sheet. "
                "Columns: Date | Calories | Protein (g) | Carbs (g) | Fat (g) | Fiber (g) | Sodium (mg) | Data Source | Notes"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fat_g": {"type": "number"},
                    "fiber_g": {"type": "number"},
                    "sodium_mg": {"type": "number"},
                    "data_source": {"type": "string", "default": "MFP"},
                    "notes": {"type": "string", "default": ""},
                },
                "required": ["calories", "protein_g"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_sheet",
            "description": (
                "Read recent rows from any tab in the Google Sheet. "
                "Available tabs: Training Log, Body Metrics, Nutrition, Recovery, Body Scans, Body Measurements"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tab": {"type": "string", "description": "Sheet tab name"},
                    "rows": {"type": "integer", "description": "Number of recent rows to return (default 10)", "default": 10},
                },
                "required": ["tab"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Append an entry to memory.md — the single file where all remembered info is stored. Include the date and context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entry": {"type": "string", "description": "What to remember (e.g. '2026-04-06: Weight goal timeline — target 150lbs by July, 1.5lbs/week')"},
                },
                "required": ["entry"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": "Read memory.md — the file containing everything the user asked to remember.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upload_to_drive",
            "description": "Upload a file to Google Drive (the user LifeOS/fitness/uploads/).",
            "parameters": {
                "type": "object",
                "properties": {
                    "local_path": {"type": "string"},
                    "drive_name": {"type": "string", "description": "Filename on Drive (optional)"},
                },
                "required": ["local_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_fitbit",
            "description": (
                "Trigger an immediate Fitbit data sync. Pulls latest weight, sleep, steps, "
                "HRV, nutrition from Fitbit API into Google Sheets. Normally runs 3x/day "
                "(7am, 12pm, 10pm ET) but this forces an immediate pull."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


# --- Tool implementations ---

def _run_gog(args: list[str], timeout: int = 30) -> str:
    """Run a gog CLI command and return output."""
    cmd = [GOG] + args + ["--account", GOG_ACCOUNT, "--no-input"]
    log.info("gog: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=GOG_ENV,
        )
        if result.returncode != 0:
            return f"ERROR: {result.stderr.strip() or result.stdout.strip()}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "ERROR: gog command timed out after 30s"


def _today() -> str:
    return datetime.datetime.now(
        __import__('zoneinfo').ZoneInfo("America/Toronto")
    ).strftime("%Y-%m-%d")


def _verify_sheet_write(tab: str, expected_date: str, expected_field: str) -> str:
    """Read back the last row of a sheet tab and verify the write landed."""
    check = _run_gog(["sheets", "get", SHEET_ID, f"{tab}!A:Z"])
    if check.startswith("ERROR"):
        return " [VERIFY FAILED: could not read sheet back]"
    last_line = check.strip().split("\n")[-1]
    if expected_date in last_line and expected_field in last_line:
        return " [VERIFIED]"
    return f" [VERIFY FAILED: last row does not match. Got: {last_line[:100]}]"


def tool_log_workout(data: dict) -> str:
    exercises = data["exercises"]
    session_type = data.get("session_type", "BRO_SPLIT")
    date = _today()
    rows = []
    total_volume = 0
    for ex in exercises:
        volume = ex["sets"] * ex["reps"] * ex["weight_lbs"]
        total_volume += volume
        rows.append([
            date,
            ex["name"],
            str(ex["sets"]),
            str(ex["reps"]),
            str(ex["weight_lbs"]),
            str(ex.get("rpe", "")),
            str(volume),
            session_type,
            "TELEGRAM",
        ])
    values_json = json.dumps(rows)
    result = _run_gog([
        "sheets", "append", SHEET_ID, "Training Log!A:I",
        "--values-json", values_json,
        "--insert", "INSERT_ROWS",
        "--input", "RAW",
    ])
    if result.startswith("ERROR"):
        return result
    verify = _verify_sheet_write("Training Log", date, exercises[-1]["name"])
    return f"Logged {len(exercises)} exercises, total volume: {total_volume:,} lbs.{verify}"


def tool_log_weight(data: dict) -> str:
    date = _today()
    lbs = data["weight_lbs"]
    kg = round(lbs / 2.20462, 1)
    bf = str(data.get("body_fat_pct", ""))
    source = data.get("data_source", "RENPHO")
    notes = data.get("notes", "")
    row = [[date, str(lbs), str(kg), bf, "", "", "", source, notes]]
    result = _run_gog([
        "sheets", "append", SHEET_ID, "Body Metrics!A:I",
        "--values-json", json.dumps(row),
        "--insert", "INSERT_ROWS",
        "--input", "RAW",
    ])
    if result.startswith("ERROR"):
        return result
    verify = _verify_sheet_write("Body Metrics", date, str(lbs))
    return f"Logged weight: {lbs} lbs ({kg} kg) on {date}.{verify}"


def tool_log_nutrition(data: dict) -> str:
    date = _today()
    row = [[
        date,
        str(data["calories"]),
        str(data["protein_g"]),
        str(data.get("carbs_g", "")),
        str(data.get("fat_g", "")),
        str(data.get("fiber_g", "")),
        str(data.get("sodium_mg", "")),
        data.get("data_source", "MFP"),
        data.get("notes", ""),
    ]]
    result = _run_gog([
        "sheets", "append", SHEET_ID, "Nutrition!A:I",
        "--values-json", json.dumps(row),
        "--insert", "INSERT_ROWS",
        "--input", "RAW",
    ])
    if result.startswith("ERROR"):
        return result
    verify = _verify_sheet_write("Nutrition", date, str(data["calories"]))
    return f"Logged nutrition for {date}: {data['calories']} cal, {data['protein_g']}g protein.{verify}"


def tool_read_sheet(data: dict) -> str:
    tab = data["tab"]
    num_rows = data.get("rows", 10)
    output = _run_gog(["sheets", "get", SHEET_ID, f"{tab}!A:Z"])
    if output.startswith("ERROR"):
        return output
    lines = output.strip().split("\n")
    header = lines[0] if lines else ""
    recent = lines[-(num_rows):] if len(lines) > num_rows else lines[1:]
    return header + "\n" + "\n".join(recent)


def tool_save_memory(data: dict) -> str:
    path = MEMORY_DIR / "memory.md"
    entry = data["entry"].replace("\\n", "\n").strip()
    # Append to the single memory file
    with open(path, "a") as f:
        f.write(f"\n- {entry}\n")
    # Verify
    content = path.read_text()
    if entry in content:
        return f"Remembered [VERIFIED]"
    return f"Save failed [VERIFY FAILED]"


def tool_read_memory(data: dict) -> str:
    path = MEMORY_DIR / "memory.md"
    if not path.exists():
        return "No memories saved yet."
    return path.read_text()


def tool_upload_to_drive(data: dict) -> str:
    local_path = data["local_path"]
    drive_name = data.get("drive_name", pathlib.Path(local_path).name)
    result = _run_gog([
        "drive", "upload", local_path,
        "--parent", DRIVE_UPLOADS_FOLDER,
        "--name", drive_name,
    ])
    return result


def tool_sync_fitbit(data: dict) -> str:
    """Trigger an immediate Fitbit data sync by running the script directly."""
    try:
        result = subprocess.run(
            ["python3", "/home/openclaw/fitbit_sync.py"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HOME": "/home/openclaw"},
        )
        if result.returncode != 0:
            return f"ERROR: {result.stderr.strip()[:500]}"
        return f"Fitbit sync completed. {result.stdout.strip()[-200:]}"
    except subprocess.TimeoutExpired:
        return "Fitbit sync timed out after 60s. Data may be partially updated."


TOOL_DISPATCH = {
    "log_workout": tool_log_workout,
    "log_weight": tool_log_weight,
    "log_nutrition": tool_log_nutrition,
    "read_sheet": tool_read_sheet,
    "save_memory": tool_save_memory,
    "read_memory": tool_read_memory,
    "upload_to_drive": tool_upload_to_drive,
    "sync_fitbit": tool_sync_fitbit,
}


def execute_tool(name: str, input_data: dict) -> str:
    fn = TOOL_DISPATCH.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return fn(input_data)
    except Exception as e:
        log.exception("Tool %s failed", name)
        return f"ERROR: {e}"


# --- Grok conversation loop (OpenAI-compatible API) ---

client = OpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL,
)


def ask_ai(user_text: str, conversation: list[dict]) -> tuple[str, list]:
    """Send user message to AI, handle tool calls, return (reply, tool_log)."""
    conversation.append({"role": "user", "content": user_text})
    tool_log = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "system", "content": _build_system_prompt()}] + conversation,
            tools=TOOLS,
        )

        msg = response.choices[0].message
        # Build assistant message for history
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        conversation.append(assistant_msg)

        if not msg.tool_calls:
            return msg.content or "", tool_log

        # Execute tools and feed results back
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            log.info("Tool call: %s(%s)", fn_name, json.dumps(fn_args)[:200])
            result = execute_tool(fn_name, fn_args)
            log.info("Tool result: %s", result[:200])
            tool_log.append({"tool": fn_name, "input": fn_args, "result": result[:500]})
            conversation.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "I hit the tool call limit. Please try a simpler request.", tool_log


# --- Conversation state and logging ---

conversations: dict[int, list] = {}


def load_conversation_from_logs() -> list[dict]:
    """Load today's conversation history from log file. Survives restarts."""
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
            conv.append({"role": "user", "content": entry.get("user", "")})
            conv.append({"role": "assistant", "content": entry.get("assistant", "")})
    except Exception as e:
        log.warning("Failed to load conversation history: %s", e)
    # Keep last MAX_CONVERSATION_MESSAGES to stay within context limits
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv = conv[-MAX_CONVERSATION_MESSAGES:]
    log.info("Loaded %d messages from today's log", len(conv))
    return conv


def log_conversation(user_text: str, reply: str, tool_calls: list | None = None):
    today = _today()
    log_file = LOG_DIR / f"{today}.jsonl"
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "user": user_text,
        "assistant": reply,
    }
    if tool_calls:
        entry["tools"] = tool_calls
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --- Telegram handlers ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != CHAT_ID:
        log.warning("Ignoring message from chat %s", update.effective_chat.id)
        return

    user_text = update.message.text
    if not user_text:
        return

    log.info("Message from the user: %s", user_text[:100])

    conv = conversations.get(update.effective_chat.id)
    if conv is None:
        conv = load_conversation_from_logs()
        conversations[update.effective_chat.id] = conv

    # Trim conversation history
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv[:] = conv[-MAX_CONVERSATION_MESSAGES:]

    tools_used = []
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, user_text, conv)
    except Exception as e:
        log.exception("AI API error")
        reply = f"Something went wrong: {e}"

    log_conversation(user_text, reply, tools_used)

    # Telegram has a 4096 char limit per message
    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i : i + 4096])


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation history."""
    if update.effective_chat and update.effective_chat.id == CHAT_ID:
        conversations.pop(CHAT_ID, None)
        await update.message.reply_text("Conversation cleared.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads — download and pass to AI."""
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
    log.info("Downloaded file: %s", local_path)

    caption = update.message.caption or ""
    user_text = f"[File uploaded: {filename} saved to {local_path}] {caption}".strip()

    conv = conversations.setdefault(CHAT_ID, [])
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv[:] = conv[-MAX_CONVERSATION_MESSAGES:]

    tools_used = []
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, user_text, conv)
    except Exception as e:
        log.exception("AI API error")
        reply = f"Something went wrong: {e}"

    log_conversation(user_text, reply, tools_used)
    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i : i + 4096])


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads."""
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != CHAT_ID:
        return

    photo = update.message.photo[-1]  # largest size
    file = await photo.get_file()
    filename = f"photo_{_today()}_{photo.file_unique_id}.jpg"
    local_path = UPLOAD_DIR / filename
    await file.download_to_drive(str(local_path))
    log.info("Downloaded photo: %s", local_path)

    caption = update.message.caption or ""
    user_text = f"[Photo uploaded: {filename} saved to {local_path}] {caption}".strip()

    conv = conversations.setdefault(CHAT_ID, [])
    tools_used = []
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, user_text, conv)
    except Exception as e:
        reply = f"Something went wrong: {e}"

    log_conversation(user_text, reply, tools_used)
    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i : i + 4096])


def main():
    log.info("Starting LifeOS bot (model: %s)", MODEL)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    app = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("clear", handle_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    log.info("Bot is polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
