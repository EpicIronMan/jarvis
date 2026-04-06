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
import base64
import io

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
            "name": "list_drive",
            "description": (
                "List files in a Google Drive folder. Use to browse the user's Drive and find "
                "files (DEXA scans, blood work, photos, etc.). Returns file names, IDs, types, "
                "and sizes. Use the file ID with download_from_drive to fetch a file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_id": {
                        "type": "string",
                        "description": (
                            "Google Drive folder ID to list. Omit to list the default "
                            "fitness/uploads/ folder."
                        ),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_from_drive",
            "description": (
                "Download a file from Google Drive to local disk. Use the file ID from "
                "list_drive. After downloading, use read_pdf to read PDFs with vision. "
                "Files are cached locally — subsequent reads don't re-download. "
                "Max file size: 20MB."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "Google Drive file ID (from list_drive results)",
                    },
                    "filename": {
                        "type": "string",
                        "description": "What to name the file locally (e.g. 'dexa_2026-04-02.pdf')",
                    },
                },
                "required": ["file_id", "filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_pdf",
            "description": (
                "Read a PDF file using AI vision. Converts PDF pages to images and injects "
                "them into the conversation so you can see the content. Use this to extract "
                "data from DEXA scans, blood work, or any PDF. The file must be in the local "
                "uploads directory — use download_from_drive first if it's on Google Drive. "
                "Reads 5 pages at a time by default. If you don't find what you need, call "
                "again with the next page range (e.g. first_page=6). The result tells you "
                "the total page count so you know how many remain."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename in the uploads directory (e.g. 'dexa_scan.pdf')",
                    },
                    "first_page": {
                        "type": "integer",
                        "description": "First page to read (default: 1)",
                    },
                    "last_page": {
                        "type": "integer",
                        "description": "Last page to read (default: first_page + 4, i.e. 5 pages)",
                    },
                },
                "required": ["filename"],
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


def _pdf_to_base64_images(
    pdf_path: str, first_page: int = 1, last_page: int | None = None
) -> tuple[list[str], int]:
    """Convert PDF pages to base64-encoded JPEG images for AI vision.

    Returns (list of base64 strings, total page count in the PDF).
    If last_page is None, converts all pages.
    """
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
        b64_images.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
    return b64_images, total_pages


def _verify_sheet_write(tab: str, expected_date: str, expected_field: str) -> str:
    """Read back the sheet and verify the write landed (searches all rows for the date)."""
    check = _run_gog(["sheets", "get", SHEET_ID, f"{tab}!A:Z"])
    if check.startswith("ERROR"):
        return " [VERIFY FAILED: could not read sheet back]"
    for line in check.strip().split("\n"):
        if expected_date in line and expected_field in line:
            return " [VERIFIED]"
    return f" [VERIFY FAILED: could not find {expected_date} with {expected_field}]"


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
    # Filter data rows, sort by date descending (newest first — matches sheet order)
    data_lines = [l for l in lines[1:] if l.strip() and not l.startswith("←") and len(l) > 4 and l[0:4].isdigit()]
    data_lines.sort(reverse=True)
    recent = data_lines[:num_rows]
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


def tool_list_drive(data: dict) -> str:
    """List files in a Google Drive folder."""
    folder_id = data.get("folder_id", DRIVE_UPLOADS_FOLDER)
    result = _run_gog(["drive", "ls", "--parent", folder_id])
    if result.startswith("ERROR"):
        return result
    return result


def tool_download_from_drive(data: dict) -> str:
    """Download a file from Google Drive to local uploads directory."""
    file_id = data["file_id"]
    filename = data["filename"]
    local_path = UPLOAD_DIR / filename

    # Cache: skip download if file already exists locally
    if local_path.exists():
        return f"File already cached locally: {local_path}"

    result = _run_gog(["drive", "download", file_id, "--output", str(local_path)], timeout=60)
    if result.startswith("ERROR"):
        return result

    # Size guardrail: reject files over 20MB
    if local_path.exists() and local_path.stat().st_size > 20 * 1024 * 1024:
        local_path.unlink()
        return "ERROR: File exceeds 20MB limit. Download removed."

    return f"Downloaded to {local_path} ({local_path.stat().st_size // 1024} KB)"


def tool_read_pdf(data: dict, conversation: list[dict] | None = None) -> str:
    """Read a PDF by converting to images and injecting into conversation for AI vision."""
    filename = data["filename"]
    first_page = data.get("first_page", 1)
    last_page = data.get("last_page", first_page + 4)  # default: 5 pages per read
    pdf_path = UPLOAD_DIR / filename
    if not pdf_path.exists():
        # Try matching without exact case
        for f in UPLOAD_DIR.iterdir():
            if f.name.lower() == filename.lower():
                pdf_path = f
                break
        else:
            return f"ERROR: File not found: {filename}. Available files: {', '.join(f.name for f in UPLOAD_DIR.iterdir() if f.suffix.lower() == '.pdf')}"
    try:
        b64_images, total_pages = _pdf_to_base64_images(
            str(pdf_path), first_page=first_page, last_page=last_page,
        )
        pages_read = len(b64_images)
        range_desc = f"pages {first_page}-{first_page + pages_read - 1} of {total_pages}"
        if conversation is not None:
            content_parts = [{"type": "text", "text": f"[PDF content from {filename} — {range_desc}:]"}]
            for b64 in b64_images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            conversation.append({"role": "user", "content": content_parts})
        log.info("PDF read: %s (%s, %d images)", filename, range_desc, pages_read)
        return f"PDF loaded: {filename} ({range_desc}). The pages are now visible to you as images above."
    except Exception as e:
        return f"ERROR reading PDF: {e}"


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
    "list_drive": tool_list_drive,
    "download_from_drive": tool_download_from_drive,
    "read_pdf": tool_read_pdf,
    "sync_fitbit": tool_sync_fitbit,
}

# Tools that need conversation context injected (for multimodal content)
TOOLS_WITH_CONVERSATION = {"read_pdf"}


def execute_tool(name: str, input_data: dict, conversation: list[dict] | None = None) -> str:
    fn = TOOL_DISPATCH.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        if name in TOOLS_WITH_CONVERSATION:
            return fn(input_data, conversation=conversation)
        return fn(input_data)
    except Exception as e:
        log.exception("Tool %s failed", name)
        return f"ERROR: {e}"


# --- Grok conversation loop (OpenAI-compatible API) ---

client = OpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL,
)


def ask_ai(user_content: str | list, conversation: list[dict]) -> tuple[str, list]:
    """Send user message to AI, handle tool calls, return (reply, tool_log).

    user_content can be a plain string or a list of content parts (for multimodal
    messages containing images, e.g. when a PDF is uploaded).
    """
    conversation.append({"role": "user", "content": user_content})
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
            result = execute_tool(fn_name, fn_args, conversation=conversation)
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
    """Reload today's conversation from log, but only user messages.

    Why not reload assistant responses: if the AI hallucinated (e.g. said
    174.6 lbs when the sheet shows 175.3), that hallucination would get
    baked into history and repeated forever. By only loading user messages
    with a brief summary placeholder for assistant turns, the AI knows
    what was discussed but re-derives all data from fresh tool calls.
    """
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
            if user_msg:
                conv.append({"role": "user", "content": user_msg})
                conv.append({"role": "assistant", "content": "(responded — pull fresh data if needed)"})
    except Exception as e:
        log.warning("Failed to load conversation history: %s", e)
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv = conv[-MAX_CONVERSATION_MESSAGES:]
    log.info("Loaded %d user messages from today's log", len(conv) // 2)
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
    """Handle file uploads — download and pass to AI.

    PDFs are converted to images and sent as multimodal vision content so the AI
    can actually read the document (e.g. DEXA scans, blood work). Other files are
    passed as text references.
    """
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

    # For PDFs: convert to images and send as multimodal content so AI can see them
    if filename.lower().endswith(".pdf"):
        try:
            b64_images, total_pages = _pdf_to_base64_images(str(local_path), first_page=1, last_page=5)
            remaining = total_pages - len(b64_images)
            remaining_note = f" ({remaining} more pages available — use read_pdf to continue)" if remaining > 0 else ""
            content_parts = [
                {"type": "text", "text": f"[PDF uploaded: {filename} saved to {local_path} — showing pages 1-{len(b64_images)} of {total_pages}{remaining_note}] {caption}".strip()},
            ]
            for b64 in b64_images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            user_content = content_parts
            log.info("PDF converted to %d page image(s) for AI vision", len(b64_images))
        except Exception as e:
            log.exception("PDF conversion failed, falling back to text-only")
            user_content = f"[File uploaded: {filename} saved to {local_path} (PDF conversion failed: {e})] {caption}".strip()
    else:
        user_content = f"[File uploaded: {filename} saved to {local_path}] {caption}".strip()

    # For logging, always store the text version
    user_text_for_log = f"[File uploaded: {filename} saved to {local_path}] {caption}".strip()

    conv = conversations.setdefault(CHAT_ID, [])
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv[:] = conv[-MAX_CONVERSATION_MESSAGES:]

    tools_used = []
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, user_content, conv)
    except Exception as e:
        log.exception("AI API error")
        reply = f"Something went wrong: {e}"

    log_conversation(user_text_for_log, reply, tools_used)
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
