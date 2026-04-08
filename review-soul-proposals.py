#!/usr/bin/env python3
"""Review pending soul proposals using AI, then send to user for APPROVE/REJECT.

Runs via cron at 8pm ET daily. Reads soul-proposals.jsonl for pending entries,
reviews each against current soul.md for conflicts/redundancy/quality,
and sends approved ones to the user via Telegram.

Rejected proposals are marked with a reason. The user never sees them unless
they check the JSONL file directly.
"""

import os
import json
import pathlib
import datetime
import urllib.request
import urllib.parse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("soul-review")

PROPOSALS_PATH = pathlib.Path("/home/openclaw/lifeos/soul-proposals.jsonl")
SOUL_PATH = pathlib.Path("/home/openclaw/lifeos/soul.md")
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("XAI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.x.ai/v1")
AI_MODEL = os.environ.get("AI_MODEL", "grok-4-1-fast")


def load_pending():
    """Load all pending proposals from the JSONL file."""
    if not PROPOSALS_PATH.exists():
        return []
    pending = []
    for line in PROPOSALS_PATH.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("status") == "pending":
                pending.append(entry)
        except json.JSONDecodeError:
            continue
    return pending


def update_proposal_status(proposal_id, new_status, review_notes=""):
    """Rewrite the JSONL file, updating the matching proposal."""
    lines = PROPOSALS_PATH.read_text().strip().split("\n")
    updated = []
    for line in lines:
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue
        if entry.get("id") == proposal_id:
            entry["status"] = new_status
            entry["review_notes"] = review_notes
            entry["reviewed_at"] = datetime.datetime.now().isoformat()
        updated.append(json.dumps(entry, ensure_ascii=False))
    PROPOSALS_PATH.write_text("\n".join(updated) + "\n")


def review_proposal(proposal, soul_text):
    """Use AI to review a single proposal against current soul.md."""
    from openai import OpenAI
    client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)
    prompt = f"""Review this proposed soul.md change:

**Proposed text:** {proposal['proposed_text']}
**Target section:** {proposal['section']}
**Reasoning:** {proposal['reasoning']}
**User's original message:** {proposal['source_message']}

Current soul.md:
{soul_text}

Evaluate:
1. Does this conflict with existing rules?
2. Is it redundant with something already there?
3. Is the wording clear and specific enough?
4. Is this actually soul.md material (behavioral rule) or should it be memory (fact/preference)?
5. If the wording could be tighter or more precise, suggest improved text.

Respond ONLY in JSON (no markdown fences): {{"action": "APPROVE", "reason": "...", "suggested_text": "..."}} or {{"action": "REJECT", "reason": "..."}} or {{"action": "MODIFY", "reason": "...", "suggested_text": "..."}}"""

    response = client.chat.completions.create(
        model=AI_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def send_telegram(text):
    """Send a message via Telegram Bot API."""
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "parse_mode": "Markdown",
        "text": text,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=data,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False


def main():
    pending = load_pending()
    if not pending:
        log.info("No pending soul proposals.")
        return

    soul_text = SOUL_PATH.read_text() if SOUL_PATH.exists() else ""
    log.info("Reviewing %d pending proposal(s)", len(pending))

    for proposal in pending:
        try:
            review_raw = review_proposal(proposal, soul_text)
        except Exception as e:
            log.error("AI review failed for #%s: %s", proposal["id"], e)
            continue

        # Parse AI review
        try:
            # Strip markdown fences if the model added them
            cleaned = review_raw.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
            if cleaned.endswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[:-1])
            review_data = json.loads(cleaned.strip())
        except (json.JSONDecodeError, ValueError):
            log.warning("Could not parse AI review for #%s, defaulting to APPROVE", proposal["id"])
            review_data = {"action": "APPROVE", "reason": review_raw[:500], "suggested_text": proposal["proposed_text"]}

        action = review_data.get("action", "APPROVE").upper()

        if action == "REJECT":
            update_proposal_status(proposal["id"], "rejected", review_data.get("reason", ""))
            send_telegram(
                f"*Soul Proposal #{proposal['id']} -- REJECTED by review*\n\n"
                f"*Proposed:* {proposal['proposed_text'][:300]}\n"
                f"*Reason:* {review_data.get('reason', 'No reason given')[:400]}"
            )
            log.info("Rejected #%s: %s", proposal["id"], review_data.get("reason", ""))
        else:
            # APPROVE or MODIFY — send to user for final decision
            suggested = review_data.get("suggested_text", proposal["proposed_text"])
            notes = review_data.get("reason", "")
            update_proposal_status(proposal["id"], "awaiting_user", notes)

            msg_parts = [
                f"*Soul Proposal #{proposal['id']}*\n",
                f"*Section:* {proposal['section']}",
                f"*Original:* {proposal['proposed_text'][:300]}",
            ]
            if action == "MODIFY" and suggested != proposal["proposed_text"]:
                msg_parts.append(f"*Suggested edit:* {suggested[:300]}")
            if notes:
                msg_parts.append(f"*Review notes:* {notes[:300]}")
            msg_parts.append(f"\nReply: APPROVE {proposal['id']} or REJECT {proposal['id']}")

            send_telegram("\n".join(msg_parts))
            log.info("Sent #%s to user for approval", proposal["id"])


if __name__ == "__main__":
    main()
