#!/bin/bash
# Quick read-only inspector for lifeos.db. Use to spot-check data against source.
#
# Usage:
#   peek.sh                       # menu of tables
#   peek.sh body_metrics          # last 10 rows
#   peek.sh nutrition 30          # last 30 rows
#   peek.sh workouts              # sessions w/ hevy_id (use this to cross-reference Hevy)
#   peek.sh session 19            # all sets in workout_session id=19
#   peek.sh date 2026-05-03       # everything logged on a specific date
#
# All output is read-only.

set -euo pipefail
DB="${LIFEOS_DB:-/home/openclaw/lifeos/v2/lifeos.db}"
N="${2:-10}"

q() { sqlite3 -header -column "$DB" "$1"; }

case "${1:-help}" in
    body_metrics|weight)
        q "SELECT date, weight_lbs, body_fat_pct, bmi, source, notes FROM body_metrics ORDER BY date DESC LIMIT $N"
        ;;
    body_scan|dexa)
        q "SELECT date, scan_type, total_bf_pct, lean_mass_lbs, rmr_cal, source FROM body_scan ORDER BY date DESC LIMIT $N"
        ;;
    nutrition|food)
        q "SELECT date, calories, protein_g, carbs_g, fat_g, fiber_g, source FROM nutrition ORDER BY date DESC LIMIT $N"
        ;;
    recovery|sleep)
        q "SELECT date, sleep_hours, time_in_bed_h, efficiency_pct, sleep_score_computed, steps, resting_hr, source FROM recovery ORDER BY date DESC LIMIT $N"
        ;;
    cardio)
        q "SELECT date, exercise, duration_min, speed, incline, net_calories, source FROM cardio ORDER BY date DESC LIMIT $N"
        ;;
    workouts|sessions)
        q "SELECT s.id, s.date, s.started_at, s.title, s.source, s.hevy_id, (SELECT COUNT(*) FROM workout_set WHERE session_id=s.id) AS sets FROM workout_session s ORDER BY s.started_at DESC LIMIT $N"
        ;;
    session)
        # peek.sh session <id>
        SID="${2:?session id required: peek.sh session 19}"
        q "SELECT s.date, s.title, s.source, s.hevy_id FROM workout_session s WHERE s.id=$SID"
        echo
        q "SELECT exercise, set_index, weight_lbs, reps, rpe, set_type, superset_id FROM workout_set WHERE session_id=$SID ORDER BY id"
        ;;
    date)
        # peek.sh date YYYY-MM-DD — everything logged on that date across all tables
        D="${2:?date required: peek.sh date 2026-05-03}"
        echo "=== body_metrics ==="; q "SELECT * FROM body_metrics WHERE date='$D'" || true
        echo; echo "=== nutrition ==="; q "SELECT * FROM nutrition WHERE date='$D'" || true
        echo; echo "=== recovery ==="; q "SELECT * FROM recovery WHERE date='$D'" || true
        echo; echo "=== cardio ==="; q "SELECT * FROM cardio WHERE date='$D'" || true
        echo; echo "=== workout_session(s) ==="; q "SELECT id, started_at, title, source, hevy_id FROM workout_session WHERE date='$D'" || true
        echo; echo "=== workout_set rows for $D ==="; q "SELECT s.title AS session, ws.exercise, ws.set_index, ws.weight_lbs, ws.reps, ws.rpe FROM workout_set ws JOIN workout_session s ON s.id=ws.session_id WHERE s.date='$D' ORDER BY s.started_at, ws.id" || true
        ;;
    events)
        q "SELECT id, ts, kind, substr(payload_json, 1, 100) AS payload FROM events ORDER BY id DESC LIMIT $N"
        ;;
    tables|help|*)
        echo "Usage: peek.sh <view> [n]"
        echo
        echo "Views:"
        echo "  body_metrics  | weight    — daily weight + BF%"
        echo "  body_scan     | dexa      — DEXA scans"
        echo "  nutrition     | food      — calories/protein/carbs/fat"
        echo "  recovery      | sleep     — sleep, steps, HR"
        echo "  cardio                    — cardio sessions"
        echo "  workouts      | sessions  — workout_session list with hevy_id"
        echo "  session <id>              — all sets in one session"
        echo "  date <YYYY-MM-DD>         — everything from that date across tables"
        echo "  events                    — audit log"
        echo
        echo "Examples:"
        echo "  peek.sh weight 30"
        echo "  peek.sh date 2026-05-03"
        echo "  peek.sh session 20"
        ;;
esac
