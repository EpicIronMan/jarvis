#!/usr/bin/env python3
"""Manage the Hevy webhook subscription.

Subcommands:
    status   — show current subscription
    register — set webhook URL + authToken (uses HEVY_WEBHOOK_TOKEN from env)
    delete   — remove the subscription

Hevy allows exactly ONE subscription per account.
"""

import argparse
import sys
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(V2_DIR))

from ingest_hevy import hevy_get, hevy_post, read_api_key  # noqa: E402
from hevy_webhook import read_env_var  # noqa: E402

import json
import urllib.request

DEFAULT_URL = "https://159.203.35.105/hevy-webhook"

SENSITIVE_FIELDS = {"auth_token", "authToken", "api_key", "apiKey", "secret", "password", "token"}


def _redact(obj):
    if isinstance(obj, dict):
        return {k: ("<REDACTED>" if k in SENSITIVE_FIELDS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def status():
    key = read_api_key()
    try:
        data = hevy_get("/webhook-subscription", key)
        print(json.dumps(_redact(data), indent=2))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("no subscription registered")
        else:
            raise


def register(url: str):
    key = read_api_key()
    token = read_env_var("HEVY_WEBHOOK_TOKEN")
    if not token:
        sys.exit("HEVY_WEBHOOK_TOKEN missing from /opt/openclaw.env")
    body = {"url": url, "authToken": token}
    hevy_post("/webhook-subscription", key, body)
    print(f"registered: url={url} (authToken not echoed)")


def delete():
    key = read_api_key()
    req = urllib.request.Request(
        "https://api.hevyapp.com/v1/webhook-subscription",
        headers={"api-key": key, "accept": "application/json"},
        method="DELETE",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"deleted (HTTP {r.status})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_reg = sub.add_parser("register")
    p_reg.add_argument("--url", default=DEFAULT_URL)
    sub.add_parser("delete")
    args = ap.parse_args()

    {"status": status, "register": lambda: register(args.url), "delete": delete}[args.cmd]()


if __name__ == "__main__":
    main()
