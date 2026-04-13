"""DEXA PDF vision handler for LifeOS v2.

Converts DEXA scan PDFs to images, sends to Claude for data extraction,
writes the result to the body_scan table. The LLM's role is narrow:
extract numbers from a scan image. It never decides what to do with them.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sqlite3
from pathlib import Path

import anthropic


def extract_dexa_from_pdf(pdf_path: str | Path, conn: sqlite3.Connection, date_str: str) -> dict:
    """Extract DEXA data from a PDF scan and write to body_scan table.

    Returns the extracted data dict or an error dict.
    """
    from pdf2image import convert_from_path

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {"error": f"PDF not found: {pdf_path}"}

    # Convert first 3 pages to images
    images = convert_from_path(str(pdf_path), dpi=200, first_page=1, last_page=3)
    b64_images = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64_images.append(base64.b64encode(buf.getvalue()).decode())

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}

    client = anthropic.Anthropic(api_key=api_key)

    # Build vision message
    content = [{"type": "text", "text": (
        "Extract ALL numerical data from this DEXA body scan. Return ONLY a JSON object with these fields "
        "(use null for any field not found):\n"
        '{"total_bf_pct": float, "lean_mass_lbs": float, "lean_mass_kg": float, '
        '"bone_density": float (g/cm2), "visceral_fat_area": float (cm2), '
        '"trunk_fat_pct": float, "arms_fat_pct": float, "legs_fat_pct": float, '
        '"rmr_cal": float (resting metabolic rate)}\n'
        "Return ONLY the JSON, no other text."
    )}]
    for b64 in b64_images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })

    resp = client.messages.create(
        model="claude-sonnet-4-5-20241022",
        max_tokens=500,
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.content[0].text.strip()

    # Parse JSON
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": f"LLM returned non-JSON: {raw[:200]}"}

    # Import to body_scan table
    from handlers.log import log_body_scan
    result = log_body_scan(
        conn,
        scan_type="DEXA",
        total_bf_pct=data.get("total_bf_pct"),
        lean_mass_lbs=data.get("lean_mass_lbs"),
        lean_mass_kg=data.get("lean_mass_kg"),
        bone_density=data.get("bone_density"),
        visceral_fat_area=data.get("visceral_fat_area"),
        trunk_fat_pct=data.get("trunk_fat_pct"),
        arms_fat_pct=data.get("arms_fat_pct"),
        legs_fat_pct=data.get("legs_fat_pct"),
        rmr_cal=data.get("rmr_cal"),
        source="DEXA",
        source_file=pdf_path.name,
        notes=f"extracted via Claude vision from {pdf_path.name}",
        date_str=date_str,
    )

    return {**result, "extracted": data}
