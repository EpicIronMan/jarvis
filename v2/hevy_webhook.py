#!/usr/bin/env python3
"""Hevy webhook receiver for LifeOS.

Listens on 127.0.0.1:18789 (Caddy reverse-proxies https://<box>/ to here).
Hevy POSTs `{"id": "..."}` on workout completion. We:
  1. Validate the Authorization header against HEVY_WEBHOOK_TOKEN.
  2. Return 200 immediately (Hevy times out at 5s).
  3. In the background: GET /v1/workouts/{id} from Hevy and upsert into SQLite.
"""

import asyncio
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

from aiohttp import web

V2_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(V2_DIR))

from ingest_hevy import (  # noqa: E402
    DB_PATH, fetch_workout, read_api_key, upsert_workout,
)

ENV_PATH = "/opt/openclaw.env"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 18789

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("hevy_webhook")


def read_env_var(name: str) -> str | None:
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith(f"{name}="):
                return line[len(name) + 1:].rstrip("\n").strip()
    return None


async def ingest_async(hevy_id: str):
    """Fetch the workout from Hevy and upsert. Runs after the 200 has been sent."""
    try:
        key = read_api_key()
        workout = await asyncio.to_thread(fetch_workout, hevy_id, key)
        if not workout:
            log.warning(f"empty workout response for id={hevy_id}")
            return

        def _write():
            con = sqlite3.connect(DB_PATH)
            con.execute("PRAGMA foreign_keys = ON")
            try:
                created, n_sets = upsert_workout(con, workout)
                con.commit()
                return created, n_sets
            finally:
                con.close()

        created, n_sets = await asyncio.to_thread(_write)
        log.info(f"hevy_id={hevy_id} {'NEW' if created else 'UPDATED'} sets={n_sets}")
    except Exception:
        log.exception(f"ingest failed for hevy_id={hevy_id}")


async def handle_webhook(request: web.Request) -> web.Response:
    expected_token = read_env_var("HEVY_WEBHOOK_TOKEN")
    if not expected_token:
        log.error("HEVY_WEBHOOK_TOKEN missing from env")
        return web.Response(status=500, text="server misconfigured")

    auth = request.headers.get("Authorization", "")
    if auth != expected_token:
        log.warning(f"webhook auth rejected: header_present={bool(auth)}")
        return web.Response(status=401, text="unauthorized")

    raw = await request.read()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning(f"json decode failed: {e}; body={raw[:200]!r}")
        return web.Response(status=400, text="invalid json")

    hevy_id = body.get("workoutId")
    if not hevy_id:
        log.warning(f"no workoutId in payload, keys={list(body.keys())}")
        return web.Response(status=400, text="missing workoutId")

    asyncio.create_task(ingest_async(hevy_id))
    return web.Response(status=200, text="ok")


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="hevy-webhook ok")


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/hevy-webhook", handle_webhook)
    app.router.add_get("/hevy-webhook/health", handle_health)
    return app


def main():
    app = make_app()
    log.info(f"hevy-webhook listening on {LISTEN_HOST}:{LISTEN_PORT}")
    web.run_app(app, host=LISTEN_HOST, port=LISTEN_PORT, access_log=log)


if __name__ == "__main__":
    main()
