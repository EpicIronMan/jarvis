-- LifeOS v2 — SQLite schema
-- Source of truth for all body, training, and recovery data.
-- Replaces Google Sheets as primary storage (sheets becomes a one-way read-only view).
--
-- Design principles:
--   * STRICT tables — real type enforcement, not SQLite's usual anything-goes.
--   * Dates are TEXT ISO (YYYY-MM-DD). SQLite has no native date type; ISO strings
--     sort and compare correctly and are human-readable.
--   * Time-series tables that logically have one row per day use `date` as PRIMARY KEY
--     (upsert semantics match current Fitbit sync behavior).
--   * Tables that can have multiple rows per day (workout, cardio) use an auto-increment id.
--   * Source column on every data table for provenance (FITBIT, TELEGRAM, DEXA, MANUAL, etc.).
--   * Notes column on every data table for human-readable context.
--   * Foreign keys are NOT used — these are independent time-series, not relational.
--
-- Last updated: 2026-04-11 (Phase 0 of v2 rebuild)

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;   -- concurrent readers while bot writes

-- =====================================================================
-- Schema metadata
-- =====================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version       INTEGER PRIMARY KEY,
    applied_at    TEXT    NOT NULL,
    description   TEXT    NOT NULL
) STRICT;

INSERT OR IGNORE INTO schema_version (version, applied_at, description)
VALUES (1, '2026-04-11', 'Phase 0 initial schema');

-- =====================================================================
-- Body Metrics — one row per day (upsert). Mirrors Body Metrics tab.
-- Source: Fitbit/Renpho scale sync (primary) or manual Telegram log (fallback).
-- =====================================================================

CREATE TABLE IF NOT EXISTS body_metrics (
    date            TEXT    PRIMARY KEY,              -- YYYY-MM-DD
    weight_lbs      REAL,
    weight_kg       REAL,
    body_fat_pct    REAL,                              -- Renpho bioimpedance, NOT DEXA truth
    muscle_mass_kg  REAL,                              -- nullable: Fitbit doesn't always return
    water_pct       REAL,                              -- nullable
    bmi             REAL,
    source          TEXT    NOT NULL,                  -- FITBIT | TELEGRAM | RENPHO | MANUAL
    notes           TEXT
) STRICT;

-- =====================================================================
-- Body Scans — DEXA results. Low frequency (~monthly), high authority.
-- This is the SINGLE source of truth for body fat % and lean mass.
-- Never use body_metrics.body_fat_pct for coaching — use latest body_scan instead.
-- =====================================================================

CREATE TABLE IF NOT EXISTS body_scan (
    date                        TEXT    PRIMARY KEY,  -- YYYY-MM-DD
    scan_type                   TEXT    NOT NULL,     -- DEXA | InBody | other
    total_bf_pct                REAL,
    lean_mass_lbs               REAL,
    lean_mass_kg                REAL,
    bone_density                REAL,                  -- g/cm²
    visceral_fat_area           REAL,                  -- cm²
    trunk_fat_pct               REAL,
    arms_fat_pct                REAL,
    legs_fat_pct                REAL,
    renpho_bf_same_week         REAL,                  -- for DEXA-Renpho offset calibration
    dexa_renpho_offset          REAL,                  -- BF% delta for reconciling Renpho readings
    rmr_cal                     REAL,                  -- DEXA-derived RMR
    source                      TEXT    NOT NULL,      -- usually DEXA
    source_file                 TEXT,                  -- original PDF filename
    notes                       TEXT
) STRICT;

-- =====================================================================
-- Nutrition — one row per day (upsert). Daily aggregates, not per-meal.
-- Source: MyFitnessPal → Fitbit → fitbit_sync (primary) or manual.
-- =====================================================================

CREATE TABLE IF NOT EXISTS nutrition (
    date         TEXT    PRIMARY KEY,
    calories     REAL,
    protein_g    REAL,
    carbs_g      REAL,
    fat_g        REAL,
    fiber_g      REAL,
    sodium_mg    REAL,
    source       TEXT    NOT NULL,                      -- FITBIT | TELEGRAM | MANUAL
    notes        TEXT
) STRICT;

-- =====================================================================
-- Workout — strength training log. Multiple rows per day (one per exercise).
-- Source: user via Telegram shorthand, parsed by deterministic router.
-- =====================================================================

CREATE TABLE IF NOT EXISTS workout (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,
    exercise      TEXT    NOT NULL,
    sets          INTEGER NOT NULL,
    reps          INTEGER NOT NULL,
    weight_lbs    REAL    NOT NULL,                    -- 0 OK for bodyweight
    rpe           REAL,                                  -- nullable; RPE 0–10
    volume_lbs    REAL,                                  -- stored (not computed) to match sheet
    session_type  TEXT,                                  -- BRO_SPLIT_LEGS, UPPER, etc.
    source        TEXT    NOT NULL,                      -- TELEGRAM | MANUAL
    notes         TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS idx_workout_date       ON workout(date);
CREATE INDEX IF NOT EXISTS idx_workout_exercise   ON workout(exercise);
CREATE INDEX IF NOT EXISTS idx_workout_date_ex    ON workout(date, exercise);

-- =====================================================================
-- Cardio — cardio sessions. Multiple rows per day possible.
-- Source: Telegram or Fitbit activity log.
-- =====================================================================

CREATE TABLE IF NOT EXISTS cardio (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT    NOT NULL,
    exercise       TEXT    NOT NULL,                     -- Treadmill, Bike, etc.
    duration_min   REAL    NOT NULL,
    speed          REAL,                                 -- mph or km/h
    incline        REAL,                                 -- %
    net_calories   REAL,
    met_used       REAL,
    source         TEXT    NOT NULL,
    notes          TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS idx_cardio_date ON cardio(date);

-- =====================================================================
-- Recovery — one row per day. Mirrors Recovery tab post-2026-04-11 fixes
-- (col B renamed Efficiency %, col J Sleep Score computed, col K Time in Bed).
-- =====================================================================

CREATE TABLE IF NOT EXISTS recovery (
    date                  TEXT    PRIMARY KEY,
    efficiency_pct        REAL,                          -- % of time in bed asleep (was misnamed "Sleep Score")
    sleep_hours           REAL,                          -- total actual asleep (all sessions, post-04-11 fix)
    steps                 INTEGER,
    active_minutes        INTEGER,
    hrv                   REAL,                          -- nullable: not in standard Fitbit Web API
    resting_hr            INTEGER,
    sleep_score_computed  REAL,                          -- 0-100 proxy formula (added 2026-04-11)
    time_in_bed_h         REAL,                          -- raw, includes wake within sessions (added 2026-04-11)
    source                TEXT    NOT NULL,
    notes                 TEXT
) STRICT;

-- =====================================================================
-- Routine — versioned. Per recommendation #1: effective-dated table so
-- historical queries stay correct ("what was my routine on 2026-01-15?").
-- One row per (day_of_week, effective_from). effective_to NULL = current.
-- exercises_json is a JSON array of exercise names for that day's session.
-- =====================================================================

CREATE TABLE IF NOT EXISTS routine (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from  TEXT    NOT NULL,                    -- YYYY-MM-DD
    effective_to    TEXT,                                -- NULL = current
    day_of_week     INTEGER NOT NULL,                    -- 0=Mon .. 6=Sun (ISO)
    session_type    TEXT    NOT NULL,                    -- BRO_SPLIT_LEGS | REST | etc.
    exercises_json  TEXT    NOT NULL,                    -- JSON array of exercise names
    notes           TEXT,
    CHECK (day_of_week BETWEEN 0 AND 6)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_routine_active ON routine(effective_from, effective_to);

-- =====================================================================
-- User facts — key/value store for mutable user state that queries need.
-- Things like height_cm, birth_date, goal_weight_lbs, goal_bf_pct.
-- Static facts live here so every script queries one source (not markdown).
-- =====================================================================

CREATE TABLE IF NOT EXISTS user_facts (
    key         TEXT    PRIMARY KEY,
    value       TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
) STRICT;

-- =====================================================================
-- Events — audit substrate. Every router decision, every handler call,
-- every model invocation, every tool error appends here. Replaces the
-- JSONL conversation log as the primary audit trail.
--
-- kind values (convention, not enforced):
--   router_intent      : router matched an intent
--   router_miss        : router fell through to LLM classifier
--   handler_call       : handler executed
--   handler_error      : handler threw
--   model_call         : LLM invoked (with latency + cost)
--   sheet_push         : one-way export to sheet ran
--   backup             : DB snapshot taken
--   coaching_trigger   : proactive trigger fired
-- =====================================================================

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,                       -- ISO8601 with tz offset
    kind         TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,                       -- free-form per kind
    user_msg_id  TEXT                                    -- Telegram msg id, nullable
) STRICT;

CREATE INDEX IF NOT EXISTS idx_events_ts    ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_kind  ON events(kind);

-- =====================================================================
-- Convenience views — keep queries human-readable elsewhere.
-- =====================================================================

-- Latest body scan (the authoritative BF% and lean mass source)
CREATE VIEW IF NOT EXISTS latest_body_scan AS
SELECT * FROM body_scan ORDER BY date DESC LIMIT 1;

-- Latest weight
CREATE VIEW IF NOT EXISTS latest_weight AS
SELECT * FROM body_metrics ORDER BY date DESC LIMIT 1;

-- Today's routine (resolves versioning)
-- Use: SELECT * FROM active_routine WHERE day_of_week = strftime('%w','now','weekday 1')-1;
-- (Python app layer will resolve this deterministically — view is for ad-hoc SQL.)
CREATE VIEW IF NOT EXISTS active_routine AS
SELECT * FROM routine
WHERE effective_to IS NULL
   OR effective_to >= date('now');
