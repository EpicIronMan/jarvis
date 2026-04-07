#!/usr/bin/env python3
"""LifeOS Bot — single-agent AI fitness coach via Telegram.

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
import re

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
MODEL = os.environ.get("AI_MODEL", "grok-4.20-0309-reasoning")

# Agent identity — configurable for rebranding
AGENT_NAME = os.environ.get("AGENT_NAME", "J.A.R.V.I.S.")
AGENT_EMOJI = os.environ.get("AGENT_EMOJI", "🤖")

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

# --- Tool definitions (OpenAI format) ---
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
            "name": "log_cardio",
            "description": (
                "Log a cardio session to the Cardio Google Sheet tab. "
                "Columns: Date | Exercise | Duration (min) | Speed | Incline | Net Calories | MET Used | Data Source | Notes. "
                "Use this for treadmill, cycling, HIIT, running, swimming, etc. NOT for strength training."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise": {"type": "string", "description": "e.g. Treadmill, Outdoor Run, Cycling, HIIT, Spin Class"},
                    "duration_min": {"type": "number", "description": "Duration in minutes"},
                    "speed": {"type": "number", "description": "Speed (mph or equivalent), 0 if N/A"},
                    "incline": {"type": "number", "description": "Incline %, 0 if flat"},
                    "net_calories": {"type": "number", "description": "Net calories burned (gross minus baseline). Must be research-backed, not estimated."},
                    "met_used": {"type": "number", "description": "MET value used for the calculation"},
                    "notes": {"type": "string", "default": "", "description": "Calculation breakdown, formula, or other context"},
                },
                "required": ["exercise", "duration_min", "net_calories", "met_used"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_sheet",
            "description": (
                "Read recent rows from any tab in the Google Sheet. "
                "Available tabs: Training Log, Body Metrics, Nutrition, Recovery, Body Scans, Body Measurements, Cardio"
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
            "name": "write_sheet",
            "description": (
                "Write to any cell or range in the Google Sheet. Use for editing cells, "
                "adding columns, or fixing data. Requires a reason explaining WHY the "
                "change is being made — this gets written to the Notes column of the "
                "affected row so any AI reading the sheet later understands the context. "
                "For structural changes (new columns, deleted rows, changed layouts), "
                "tell the user to have Claude Code update architecture.md and push to GitHub. "
                "IMPORTANT: Show the user what you're about to write and get APPROVE before calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "range": {
                        "type": "string",
                        "description": "Sheet range in A1 notation (e.g. 'Body Scans!P1' for a single cell, 'Body Scans!P1:P2' for a range)",
                    },
                    "values": {
                        "type": "array",
                        "description": "2D array of values to write (rows x cols), e.g. [['RMR (cal/day)'], ['1618']]",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this change is being made (e.g. 'Extracted RMR from DEXA PDF 2026-04-02')",
                    },
                },
                "required": ["range", "values", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_row",
            "description": (
                "Clear (blank out) a row or range in the Google Sheet. Use this to remove "
                "bad data, duplicates, or entries that belong in a different tab. "
                "First use read_sheet to find the row, then clear it. "
                "IMPORTANT: You MUST call this tool to actually clear data — do NOT claim you cleared something without calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "range": {
                        "type": "string",
                        "description": "Sheet range in A1 notation (e.g. 'Training Log!A5:J5' to clear row 5)",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this row is being cleared",
                    },
                },
                "required": ["range", "reason"],
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
    """Convert PDF pages to base64-encoded JPEG images for AI vision."""
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
    """Read back the sheet and verify the write landed."""
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
            date, ex["name"], str(ex["sets"]), str(ex["reps"]),
            str(ex["weight_lbs"]), str(ex.get("rpe", "")),
            str(volume), session_type, "TELEGRAM",
        ])
    result = _run_gog([
        "sheets", "append", SHEET_ID, "Training Log!A:I",
        "--values-json", json.dumps(rows), "--insert", "INSERT_ROWS", "--input", "RAW",
    ])
    if result.startswith("ERROR"):
        return result
    verify = _verify_sheet_write("Training Log", date, exercises[-1]["name"])
    return f"Logged {len(exercises)} exercises, total volume: {total_volume:,} lbs.{verify}"


def tool_log_cardio(data: dict) -> str:
    date = _today()
    row = [[
        date, data["exercise"], str(data["duration_min"]),
        str(data.get("speed", "")), str(data.get("incline", "")),
        str(data["net_calories"]), str(data["met_used"]),
        "TELEGRAM", data.get("notes", ""),
    ]]
    result = _run_gog([
        "sheets", "append", SHEET_ID, "Cardio!A:I",
        "--values-json", json.dumps(row), "--insert", "INSERT_ROWS", "--input", "RAW",
    ])
    if result.startswith("ERROR"):
        return result
    verify = _verify_sheet_write("Cardio", date, data["exercise"])
    return f"Logged cardio: {data['exercise']} {data['duration_min']}min, {data['net_calories']} net cal (MET {data['met_used']}).{verify}"


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
        "--values-json", json.dumps(row), "--insert", "INSERT_ROWS", "--input", "RAW",
    ])
    if result.startswith("ERROR"):
        return result
    verify = _verify_sheet_write("Body Metrics", date, str(lbs))
    return f"Logged weight: {lbs} lbs ({kg} kg) on {date}.{verify}"


def tool_log_nutrition(data: dict) -> str:
    date = _today()
    row = [[
        date, str(data["calories"]), str(data["protein_g"]),
        str(data.get("carbs_g", "")), str(data.get("fat_g", "")),
        str(data.get("fiber_g", "")), str(data.get("sodium_mg", "")),
        data.get("data_source", "MFP"), data.get("notes", ""),
    ]]
    result = _run_gog([
        "sheets", "append", SHEET_ID, "Nutrition!A:I",
        "--values-json", json.dumps(row), "--insert", "INSERT_ROWS", "--input", "RAW",
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
    numbered = []
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() and not line.startswith("←") and len(line) > 4 and line[0:4].isdigit():
            numbered.append((i, line))
    numbered.sort(key=lambda x: x[1], reverse=True)
    recent = numbered[:num_rows]
    result_lines = [f"Row 1: {header}"]
    for row_num, line in recent:
        result_lines.append(f"Row {row_num}: {line}")
    return "\n".join(result_lines)


def tool_write_sheet(data: dict) -> str:
    range_str = data["range"]
    values = data["values"]
    reason = data["reason"]
    result = _run_gog([
        "sheets", "update", SHEET_ID, range_str,
        "--values-json", json.dumps(values), "--input", "RAW",
    ])
    if result.startswith("ERROR"):
        return result
    tab = range_str.split("!")[0] if "!" in range_str else range_str
    check = _run_gog(["sheets", "get", SHEET_ID, range_str])
    if check.startswith("ERROR"):
        return f"Write sent but verify failed: {check}"
    written_val = values[0][0] if values and values[0] else ""
    if written_val in check:
        return f"Written to {range_str} [VERIFIED]. Reason: {reason}"
    return f"Write sent to {range_str} but could not verify value in read-back. Reason: {reason}"


def tool_clear_row(data: dict) -> str:
    range_str = data["range"]
    reason = data["reason"]
    result = _run_gog(["sheets", "clear", SHEET_ID, range_str, "--no-input"])
    if result.startswith("ERROR"):
        return result
    check = _run_gog(["sheets", "get", SHEET_ID, range_str])
    if check.startswith("ERROR") or check.strip() == "" or all(c in (' ', '\t', '\n') for c in check):
        return f"Cleared {range_str}. Reason: {reason} [VERIFIED]"
    return f"Clear sent to {range_str} but cells may not be empty. Read-back: {check[:200]}. Reason: {reason}"


def tool_save_memory(data: dict) -> str:
    path = MEMORY_DIR / "memory.md"
    entry = data["entry"].replace("\\n", "\n").strip()
    with open(path, "a") as f:
        f.write(f"\n- {entry}\n")
    content = path.read_text()
    if entry in content:
        return "Remembered [VERIFIED]"
    return "Save failed [VERIFY FAILED]"


def tool_read_memory(data: dict) -> str:
    path = MEMORY_DIR / "memory.md"
    if not path.exists():
        return "No memories saved yet."
    return path.read_text()


def tool_upload_to_drive(data: dict) -> str:
    local_path = data["local_path"]
    drive_name = data.get("drive_name", pathlib.Path(local_path).name)
    return _run_gog(["drive", "upload", local_path, "--parent", DRIVE_UPLOADS_FOLDER, "--name", drive_name])


def tool_list_drive(data: dict) -> str:
    folder_id = data.get("folder_id", DRIVE_UPLOADS_FOLDER)
    return _run_gog(["drive", "ls", "--parent", folder_id])


def tool_download_from_drive(data: dict) -> str:
    file_id = data["file_id"]
    filename = data["filename"]
    local_path = UPLOAD_DIR / filename
    if local_path.exists():
        return f"File already cached locally: {local_path}"
    result = _run_gog(["drive", "download", file_id, "--output", str(local_path)], timeout=60)
    if result.startswith("ERROR"):
        return result
    if local_path.exists() and local_path.stat().st_size > 20 * 1024 * 1024:
        local_path.unlink()
        return "ERROR: File exceeds 20MB limit. Download removed."
    return f"Downloaded to {local_path} ({local_path.stat().st_size // 1024} KB)"


def tool_read_pdf(data: dict, conversation: list[dict] | None = None) -> str:
    filename = data["filename"]
    first_page = data.get("first_page", 1)
    last_page = data.get("last_page", first_page + 4)
    pdf_path = UPLOAD_DIR / filename
    if not pdf_path.exists():
        for f in UPLOAD_DIR.iterdir():
            if f.name.lower() == filename.lower():
                pdf_path = f
                break
        else:
            return f"ERROR: File not found: {filename}. Available: {', '.join(f.name for f in UPLOAD_DIR.iterdir() if f.suffix.lower() == '.pdf')}"
    try:
        b64_images, total_pages = _pdf_to_base64_images(str(pdf_path), first_page=first_page, last_page=last_page)
        pages_read = len(b64_images)
        range_desc = f"pages {first_page}-{first_page + pages_read - 1} of {total_pages}"
        if conversation is not None:
            content_parts = [{"type": "text", "text": f"[PDF content from {filename} — {range_desc}:]"}]
            for b64 in b64_images:
                content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            conversation.append({"role": "user", "content": content_parts})
        log.info("PDF read: %s (%s, %d images)", filename, range_desc, pages_read)
        return f"PDF loaded: {filename} ({range_desc}). The pages are now visible to you as images above."
    except Exception as e:
        return f"ERROR reading PDF: {e}"


def tool_sync_fitbit(data: dict) -> str:
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
    "log_cardio": tool_log_cardio,
    "log_weight": tool_log_weight,
    "log_nutrition": tool_log_nutrition,
    "read_sheet": tool_read_sheet,
    "write_sheet": tool_write_sheet,
    "clear_row": tool_clear_row,
    "save_memory": tool_save_memory,
    "read_memory": tool_read_memory,
    "upload_to_drive": tool_upload_to_drive,
    "list_drive": tool_list_drive,
    "download_from_drive": tool_download_from_drive,
    "read_pdf": tool_read_pdf,
    "sync_fitbit": tool_sync_fitbit,
}

TOOLS_WITH_CONVERSATION = {"read_pdf"}


# --- Monitoring (passive — flags issues, never intervenes) ---

def _append_failure_notice(reply: str, tools_used: list[dict]) -> str:
    """If any tool failed and the bot didn't mention it, append a notice."""
    failed = [t for t in tools_used if "TOOL FAILED" in t.get("result", "") or "ERROR" in t.get("result", "")]
    if not failed:
        return reply
    failure_keywords = ("fail", "error", "could not", "unable", "didn't work", "permission denied")
    if not any(kw in reply.lower() for kw in failure_keywords):
        notice = "\n\n⚠️ " + " | ".join(f"{t['tool']} failed" for t in failed) + " — action(s) did NOT complete."
        return reply + notice
    return reply


WRITE_TOOLS = {"write_sheet", "clear_row", "log_workout", "log_cardio", "log_weight", "log_nutrition", "save_memory"}


def _append_write_hallucination_notice(reply: str, tools_used: list[dict]) -> str:
    """If the bot claims it wrote/updated data but made no write tool calls, append warning."""
    action_phrases = (
        r"i(?:'ve| have) (?:updated|fixed|corrected|logged|written|cleared|deleted|removed|saved|added|appended)",
        r"(?:updated|fixed|corrected|logged|cleared|deleted|removed|saved|added|appended) (?:the|your|it|row|entry|data)",
        r"(?:executing|done|complete).*(?:delet|clear|remov|updat|fix|log|writ|sav)",
        r"let me (?:correct|fix|update|delete|remove|clear|log|save|add)",
        r"i (?:will|can|shall) (?:now )?(?:correct|fix|update|delete|remove|clear|log|save|add)",
        r"the (?:sheet|tab|row|entry|data) (?:has been|is now|was) (?:updated|fixed|corrected|cleared|deleted|removed|saved)",
    )
    reply_lower = reply.lower()
    claimed = any(re.search(p, reply_lower) for p in action_phrases)
    if not claimed:
        return reply
    used_write_tool = any(t.get("tool") in WRITE_TOOLS for t in tools_used)
    if used_write_tool:
        return reply
    return reply + "\n\n⚠️ _I claimed to make changes but didn't call a write tool. The data was NOT changed. Tell me to actually do it._"


# --- Response formatting ---

def _clean_content(reply: str) -> str:
    """Strip model-generated prefixes and fix markdown before sending."""
    # Strip emoji prefixes the model might add
    reply = re.sub(r'^(?:🤖🔬|🤖|🔬)\s*\n?', '', reply).lstrip()
    # Strip agent name prefixes
    _name_pat = re.escape(AGENT_NAME)
    reply = re.sub(rf'^{_name_pat}\s*>?\s*\n?', '', reply, flags=re.IGNORECASE).lstrip()
    # Convert ### Header → *Header* (bold)
    reply = re.sub(r'^#{1,4}\s+(.+)$', r'*\1*', reply, flags=re.MULTILINE)
    # Convert ***text*** → *text*
    reply = re.sub(r'\*{3,}(.+?)\*{3,}', r'*\1*', reply, flags=re.DOTALL)
    # Convert **text** → *text* (MarkdownV2 bold)
    reply = re.sub(r'\*\*(.+?)\*\*', r'*\1*', reply)
    reply = re.sub(r'\*{3,}', '*', reply)
    return reply


def _escape_markdownv2(reply: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    return re.sub(r'([.!()\-=+{}\[\]|~>#])', r'\\\1', reply)


# --- AI conversation loop ---

client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)


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
        return f"⚠️ TOOL FAILED — {name}: {e}. YOU MUST tell the user this action failed. Do NOT say it succeeded."


def ask_ai(user_content: str | list, conversation: list[dict]) -> tuple[str, list]:
    """Send user message to AI, handle tool calls, return (reply, tool_log)."""
    conversation.append({"role": "user", "content": user_content})
    tool_log = []
    system_prompt = _build_system_prompt()

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "system", "content": system_prompt}] + conversation,
            tools=TOOLS,
        )

        msg = response.choices[0].message
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
            if assistant_msg:
                # Strip emoji/name prefixes from history
                assistant_msg = re.sub(r'^[🤖🔬\s]+\n?', '', assistant_msg).lstrip()
                _name_pat = re.escape(AGENT_NAME)
                assistant_msg = re.sub(rf'^{_name_pat}\s*>\s*\n?', '', assistant_msg, flags=re.IGNORECASE).lstrip()
            if user_msg:
                conv.append({"role": "user", "content": user_msg})
            if assistant_msg:
                conv.append({"role": "assistant", "content": assistant_msg})
    except Exception as e:
        log.warning("Failed to load conversation history: %s", e)
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv = conv[-MAX_CONVERSATION_MESSAGES:]
    log.info("Loaded %d messages from today's log", len(conv))
    return conv


def log_conversation(user_text: str, reply: str, tool_calls: list | None = None):
    today = _today()
    log_file = LOG_DIR / f"{today}.jsonl"
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "model": MODEL,
        "user": user_text,
        "assistant": reply,
    }
    if tool_calls:
        entry["tools"] = tool_calls
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def _send_reply(update, user_text: str, reply: str, tools_used: list):
    """Shared send logic: monitoring → log → escape → send."""
    reply = _append_failure_notice(reply, tools_used)
    reply = _append_write_hallucination_notice(reply, tools_used)
    log_conversation(user_text, reply, tools_used)
    reply = _escape_markdownv2(reply)
    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i : i + 4096], parse_mode="MarkdownV2")


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

    cid = update.effective_chat.id
    conv = conversations.get(cid)
    if conv is None:
        conv = load_conversation_from_logs()
        conversations[cid] = conv

    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv[:] = conv[-MAX_CONVERSATION_MESSAGES:]

    tools_used = []
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, user_text, conv)
    except Exception as e:
        log.exception("AI API error")
        reply = f"Something went wrong: {e}"

    reply = _clean_content(reply)
    reply = AGENT_EMOJI + "\n" + reply

    await _send_reply(update, user_text, reply, tools_used)


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation history."""
    if update.effective_chat and update.effective_chat.id == CHAT_ID:
        conversations.pop(CHAT_ID, None)
        await update.message.reply_text("Conversation cleared.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads — PDFs get vision treatment."""
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

    if filename.lower().endswith(".pdf"):
        try:
            b64_images, total_pages = _pdf_to_base64_images(str(local_path), first_page=1, last_page=5)
            remaining = total_pages - len(b64_images)
            remaining_note = f" ({remaining} more pages — use read_pdf to continue)" if remaining > 0 else ""
            content_parts = [
                {"type": "text", "text": f"[PDF uploaded: {filename} — pages 1-{len(b64_images)} of {total_pages}{remaining_note}] {caption}".strip()},
            ]
            for b64 in b64_images:
                content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            user_content = content_parts
        except Exception as e:
            log.exception("PDF conversion failed")
            user_content = f"[File uploaded: {filename} (PDF conversion failed: {e})] {caption}".strip()
    else:
        user_content = f"[File uploaded: {filename} saved to {local_path}] {caption}".strip()

    user_text_for_log = f"[File uploaded: {filename}] {caption}".strip()

    conv = conversations.setdefault(CHAT_ID, [])
    if len(conv) > MAX_CONVERSATION_MESSAGES:
        conv[:] = conv[-MAX_CONVERSATION_MESSAGES:]

    tools_used = []
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, user_content, conv)
    except Exception as e:
        log.exception("AI API error")
        reply = f"Something went wrong: {e}"

    reply = _clean_content(reply)
    reply = AGENT_EMOJI + "\n" + reply

    await _send_reply(update, user_text_for_log, reply, tools_used)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads."""
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != CHAT_ID:
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    filename = f"photo_{_today()}_{photo.file_unique_id}.jpg"
    local_path = UPLOAD_DIR / filename
    await file.download_to_drive(str(local_path))
    log.info("Downloaded photo: %s", local_path)

    caption = update.message.caption or ""
    user_text = f"[Photo uploaded: {filename}] {caption}".strip()

    conv = conversations.setdefault(CHAT_ID, [])
    tools_used = []
    try:
        reply, tools_used = await asyncio.to_thread(ask_ai, user_text, conv)
    except Exception as e:
        reply = f"Something went wrong: {e}"

    reply = _clean_content(reply)
    reply = AGENT_EMOJI + "\n" + reply

    await _send_reply(update, user_text, reply, tools_used)


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
