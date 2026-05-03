# generate_demo_data.py
# Adds sample student records to the exported CSVs so the charts have enough
# data to be meaningful. Run this once after export.py, before analyse.py.
#
# Usage:
#   python generate_demo_data.py
#   python analyse.py

import random
from pathlib import Path
import pandas as pd

random.seed(42)

OUT        = Path("output")
ASSIGN_DIR = OUT / "assignments"
QUIZ_DIR   = OUT / "quizzes"

# 14 additional anonymised student IDs to fill out the class to ~20 students
EXTRA_STUDENTS = [
    "u_a1b2c3d4e5f6", "u_f6e5d4c3b2a1", "u_1a2b3c4d5e6f",
    "u_9e8d7c6b5a4f", "u_3f4e5d6c7b8a", "u_c7b6a5d4e3f2",
    "u_5e6f7a8b9c0d", "u_2d3c4b5a6f7e", "u_8b9a0c1d2e3f",
    "u_4f5e6d7c8b9a", "u_0a1b2c3d4e5f", "u_7c8d9e0f1a2b",
    "u_6b7c8d9e0f1a", "u_e3f4a5b6c7d8",
]

_sub_id = 5000   # synthetic submission counter
_att_id = 8000   # synthetic attempt counter


# ── Assignments ───────────────────────────────────────────────────────────────

for csv_path in sorted(ASSIGN_DIR.glob("assign_*.csv")):
    df = pd.read_csv(csv_path)
    if df.empty:
        continue

    # Read the existing assignment metadata from the first row
    first      = df.iloc[0]
    open_ts    = int(first["allowsubmissionsfromdate"])
    due_ts     = int(first["duedate"]) if str(first.get("duedate", 0)) not in ("0", "", "nan") else 0
    existing   = set(df["anon_user"].dropna())
    missing    = [u for u in EXTRA_STUDENTS if u not in existing]

    new_rows = []
    for user in missing:
        # Submit somewhere between the open date and 2 weeks later (or before due date)
        window    = (due_ts - open_ts) if due_ts > open_ts else 14 * 86_400
        sub_unix  = open_ts + random.randint(int(window * 0.3), int(window * 0.95))
        time_s    = sub_unix - open_ts
        grade     = round(random.uniform(50, 100), 2)

        _sub_id += 1
        new_rows.append({
            **{col: first[col] for col in ["course_id", "cmid", "assignid", "assign_name",
                                            "allowsubmissionsfromdate", "duedate", "cutoffdate"]},
            "anon_user":             user,
            "submissionid":          _sub_id,
            "status":                "submitted",
            "submitted_unix":        sub_unix,
            "submitted_at":          pd.Timestamp(sub_unix, unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M:%S"),
            "time_to_submit_seconds": time_s,
            "time_to_submit_hours":  round(time_s / 3600, 2),
            "grade":                 grade,
        })

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  {csv_path.name}: added {len(new_rows)} students -> {len(df)} total")


# ── Quizzes ───────────────────────────────────────────────────────────────────

for csv_path in sorted(QUIZ_DIR.glob("quiz_*.csv")):
    df = pd.read_csv(csv_path)
    if df.empty:
        continue

    first     = df.iloc[0]
    raw_max   = float(first["raw_max"])
    base_ts   = int(pd.to_numeric(df["started_unix"], errors="coerce").dropna().min())
    existing  = set(df["anon_user"].dropna())
    missing   = [u for u in EXTRA_STUDENTS if u not in existing]

    new_rows = []
    for user in missing:
        score_pct = round(random.uniform(30, 100), 2)
        raw_score = round(raw_max * score_pct / 100, 2)
        duration  = random.randint(60, 600)           # 1–10 minutes
        start_ts  = base_ts + random.randint(0, 7 * 86_400)
        finish_ts = start_ts + duration

        _att_id += 1
        new_rows.append({
            **{col: first[col] for col in ["course_id", "cmid", "quizid", "quiz_name",
                                            "raw_max", "scaled_max", "timeopen", "timeclose",
                                            "timelimit_seconds", "attempts_allowed"]},
            "anon_user":       user,
            "attemptid":       _att_id,
            "attempt_no":      1,
            "state":           "finished",
            "timestart":       pd.Timestamp(start_ts,  unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M:%S"),
            "timefinish":      pd.Timestamp(finish_ts, unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M:%S"),
            "started_unix":    start_ts,
            "finished_unix":   finish_ts,
            "duration_seconds": duration,
            "duration_minutes": round(duration / 60, 2),
            "raw_score":       raw_score,
            "score_pct":       score_pct,
            "scaled_grade":    round(float(first["scaled_max"]) * score_pct / 100, 2),
        })

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  {csv_path.name}: added {len(new_rows)} students -> {len(df)} total")

print("\nDone. Now run:  python analyse.py")
