"""Tests for the deterministic intent router."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from router import route


class TestStats:
    def test_bare_stats(self):
        assert route("stats").name == "stats"

    def test_my_stats(self):
        assert route("my stats").name == "stats"

    def test_what_are_my_stats(self):
        assert route("what are my stats").name == "stats"

    def test_how_am_i_doing(self):
        assert route("how am I doing").name == "stats"

    def test_give_me_summary(self):
        assert route("give me a summary").name == "stats"

    def test_overview(self):
        assert route("overview").name == "stats"

    def test_snapshot(self):
        assert route("snapshot").name == "stats"


class TestWeight:
    def test_weight_today(self):
        r = route("weight today")
        assert r.name == "weight_for"
        assert r.fields["date"] == "today"

    def test_weight_yesterday(self):
        r = route("weight yesterday")
        assert r.name == "weight_for"
        assert r.fields["date"] == "yesterday"

    def test_weight_iso(self):
        r = route("weight 2026-04-10")
        assert r.name == "weight_for"
        assert r.fields["date"] == "2026-04-10"

    def test_weight_monday(self):
        r = route("weight monday")
        assert r.name == "weight_for"
        assert r.fields["date"] == "monday"

    def test_weight_3_days_ago(self):
        r = route("weight 3 days ago")
        assert r.name == "weight_for"
        assert r.fields["date"] == "3 days ago"

    def test_whats_my_weight(self):
        assert route("what's my weight").name == "weight_latest"

    def test_bare_weight(self):
        assert route("weight").name == "weight_latest"

    def test_latest_weight(self):
        assert route("latest weight").name == "weight_latest"

    # Range queries (weight_range, etc.) are handled by the LLM classifier,
    # not the deterministic router — per Musk's Algorithm decision 2026-04-13.


class TestNutrition:
    def test_calories_today(self):
        r = route("calories today")
        assert r.name == "nutrition_for"
        assert r.fields["date"] == "today"

    def test_nutrition_yesterday(self):
        r = route("nutrition yesterday")
        assert r.name == "nutrition_for"
        assert r.fields["date"] == "yesterday"

    def test_protein_today(self):
        r = route("protein today")
        assert r.name == "nutrition_for"

    def test_macros_3_days_ago(self):
        r = route("macros 3 days ago")
        assert r.name == "nutrition_for"
        assert r.fields["date"] == "3 days ago"

    def test_what_did_i_eat_today(self):
        r = route("what did I eat today")
        assert r.name == "nutrition_for"

    def test_what_did_i_eat_bare(self):
        r = route("what did I eat")
        assert r.name == "nutrition_for"
        assert r.fields["date"] == "today"

    def test_bare_nutrition(self):
        r = route("nutrition")
        assert r.name == "nutrition_for"
        assert r.fields["date"] == "today"

    def test_bare_calories(self):
        r = route("calories")
        assert r.name == "nutrition_for"
        assert r.fields["date"] == "today"

    def test_bare_protein(self):
        r = route("protein")
        assert r.name == "nutrition_for"
        assert r.fields["date"] == "today"

    # Range queries handled by LLM classifier, not router.


class TestTraining:
    def test_training_today(self):
        r = route("training today")
        assert r.name == "training_for"
        assert r.fields["date"] == "today"

    def test_workout_yesterday(self):
        r = route("workout yesterday")
        assert r.name == "training_for"

    def test_training_3_days_ago(self):
        r = route("training 3 days ago")
        assert r.name == "training_for"

    def test_what_did_i_lift_monday(self):
        r = route("what did I lift monday")
        assert r.name == "training_for"
        assert r.fields["date"] == "monday"

    def test_last_workout(self):
        assert route("last workout").name == "training_latest"

    def test_latest_session(self):
        assert route("latest session").name == "training_latest"

    def test_previous_training(self):
        assert route("previous training").name == "training_latest"

    def test_bare_workout(self):
        r = route("workout")
        assert r.name == "training_for"
        assert r.fields["date"] == "today"

    # Range queries handled by LLM classifier, not router.


class TestRecovery:
    def test_sleep_last_night(self):
        r = route("sleep last night")
        assert r.name == "recovery_for"
        assert r.fields["date"] == "yesterday"

    def test_how_did_i_sleep(self):
        r = route("how did I sleep")
        assert r.name == "recovery_for"
        assert r.fields["date"] == "yesterday"

    def test_steps_today(self):
        r = route("steps today")
        assert r.name == "recovery_for"
        assert r.fields["date"] == "today"

    def test_bare_steps(self):
        r = route("steps")
        assert r.name == "recovery_for"
        assert r.fields["date"] == "today"

    def test_bare_sleep(self):
        r = route("sleep")
        assert r.name == "recovery_for"
        assert r.fields["date"] == "yesterday"

    def test_bare_recovery(self):
        r = route("recovery")
        assert r.name == "recovery_for"
        assert r.fields["date"] == "today"

    def test_recovery_yesterday(self):
        r = route("recovery yesterday")
        assert r.name == "recovery_for"

    # Range queries handled by LLM classifier, not router.


class TestCardio:
    def test_cardio_today(self):
        r = route("cardio today")
        assert r.name == "cardio_for"

    def test_last_cardio(self):
        assert route("last cardio").name == "cardio_latest"

    def test_bare_cardio(self):
        assert route("cardio").name == "cardio_latest"


class TestBodyScan:
    def test_dexa(self):
        assert route("dexa").name == "body_scan_latest"

    def test_body_scan(self):
        assert route("body scan").name == "body_scan_latest"

    def test_body_fat(self):
        assert route("body fat").name == "body_scan_latest"

    def test_lean_mass(self):
        assert route("lean mass").name == "body_scan_latest"

    def test_body_composition(self):
        assert route("body composition").name == "body_scan_latest"

    def test_latest_dexa(self):
        assert route("latest dexa").name == "body_scan_latest"


class TestRoutine:
    def test_what_should_i_do_today(self):
        assert route("what should I do today").name == "routine_today"

    def test_todays_routine(self):
        assert route("today's routine").name == "routine_today"

    def test_my_routine(self):
        assert route("my routine").name == "routine_today"

    def test_whats_the_plan_today(self):
        assert route("what's the plan today").name == "routine_today"


class TestLastExercise:
    def test_last_bench(self):
        r = route("last bench")
        assert r.name == "last_exercise"
        assert r.fields["exercise"] == "bench"

    def test_last_leg_press(self):
        r = route("last leg press")
        assert r.name == "last_exercise"
        assert r.fields["exercise"] == "leg press"

    def test_last_time_i_did_pull_ups(self):
        r = route("last time i did pull ups")
        assert r.name == "last_exercise"
        assert r.fields["exercise"] == "pull ups"

    def test_last_session_of_lat_pulldown(self):
        r = route("last session of lat pulldown")
        assert r.name == "last_exercise"
        assert r.fields["exercise"] == "lat pulldown"


class TestEdgeCases:
    def test_empty(self):
        assert route("") is None

    def test_none(self):
        assert route(None) is None

    def test_whitespace(self):
        assert route("   ") is None

    def test_question_mark(self):
        assert route("what are my stats?").name == "stats"

    def test_leading_trailing_space(self):
        assert route("  weight today  ").name == "weight_for"

    def test_case_insensitive(self):
        assert route("WEIGHT TODAY").name == "weight_for"

    def test_gibberish_returns_none(self):
        assert route("xyzzy foobar baz") is None
