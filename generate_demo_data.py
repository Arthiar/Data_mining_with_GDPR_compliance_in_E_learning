# generate_demo_data.py
# Augments existing assignment and quiz CSVs with realistic synthetic student records
# so that the analysis charts are statistically meaningful for demonstration purposes.
#
# Run ONCE after export.py, BEFORE analyse.py:
#   python generate_demo_data.py
#   python analyse.py
#
# All synthetic records have status="submitted" and anonymised user IDs in the same
# u_<12hex> format as the real data. No real student information is fabricated.

import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

np.random.seed(42)
random.seed(42)

OUT        = Path("output")
ASSIGN_DIR = OUT / "assignments"
QUIZ_DIR   = OUT / "quizzes"

# ── Student pool ───────────────────────────────────────────────────────────────
# 6 users observed in real export + 14 synthetic = class of 20
REAL_USERS = [
    "u_06257cfc6863", "u_76ea28c9c37e", "u_008f7bf89bda",
    "u_4c38066be671", "u_b78a33fdea2a", "u_b2854143ca7e",
]
SYNTH_USERS = [
    "u_a1b2c3d4e5f6", "u_f6e5d4c3b2a1", "u_1a2b3c4d5e6f",
    "u_9e8d7c6b5a4f", "u_3f4e5d6c7b8a", "u_c7b6a5d4e3f2",
    "u_5e6f7a8b9c0d", "u_2d3c4b5a6f7e", "u_8b9a0c1d2e3f",
    "u_4f5e6d7c8b9a", "u_0a1b2c3d4e5f", "u_7c8d9e0f1a2b",
    "u_6b7c8d9e0f1a", "u_e3f4a5b6c7d8",
]
ALL_USERS = REAL_USERS + SYNTH_USERS   # 20 students

# Running ID counters — high enough to not clash with any real Moodle IDs
_SUB_ID = 5000
_ATT_ID = 8000


def _next_sub():
    global _SUB_ID
    _SUB_ID += 1
    return _SUB_ID


def _next_att():
    global _ATT_ID
    _ATT_ID += 1
    return _ATT_ID


def _ts_str(unix: int) -> str:
    return datetime.fromtimestamp(unix, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _grade(mu: float = 72.0, sigma: float = 12.0, lo: float = 30.0, hi: float = 100.0) -> float:
    return round(float(np.clip(np.random.normal(mu, sigma), lo, hi)), 2)


def _submit_unix(open_ts: int, due_ts: int) -> int:
    """Return a realistic submission timestamp relative to the assignment window."""
    if due_ts > 0 and due_ts > open_ts:
        window = due_ts - open_ts
        r = random.random()
        if r < 0.15:
            # Early submitters — first 20 % of the window
            offset = int(np.random.uniform(0.05, 0.20) * window)
        elif r < 0.87:
            # Majority — last 50 % of the window (submit close to deadline)
            offset = int(np.random.uniform(0.50, 1.0) * window)
        else:
            # Late submitters — up to 5 days after deadline
            offset = int(window + np.random.uniform(0, 5 * 86_400))
        return open_ts + offset
    else:
        # No deadline — spread over 14 days from opening
        return open_ts + int(np.random.uniform(0.5 * 86_400, 14 * 86_400))


# ── Grade characteristics per assignment (by keyword in name) ─────────────────
_ASSIGN_GRADE_PARAMS = {
    "finalisation":  (68, 13),
    "project":       (70, 13),
    "group":         (76, 10),
    "turnitin":      (76, 10),
    "participant":   (74, 12),
    "interactive":   (72, 11),
    "resource":      (75, 10),
    "hands":         (73, 12),
    "mini":          (71, 13),
}


def _grade_params(name: str):
    name_l = name.lower()
    for kw, params in _ASSIGN_GRADE_PARAMS.items():
        if kw in name_l:
            return params
    return (72, 12)


# ── Augment assignments ───────────────────────────────────────────────────────

def augment_assignments():
    for csv_path in sorted(ASSIGN_DIR.glob("assign_*.csv")):
        df = pd.read_csv(csv_path)
        if df.empty:
            continue

        row0 = df.iloc[0]
        course_id   = int(row0["course_id"])
        cmid        = int(row0["cmid"])
        assignid    = int(row0["assignid"])
        assign_name = str(row0["assign_name"])
        open_ts     = int(row0["allowsubmissionsfromdate"])

        due_val  = row0.get("duedate",   0)
        cut_val  = row0.get("cutoffdate", 0)
        due_ts   = int(due_val)  if pd.notna(due_val)  and str(due_val)  not in ("", "0") else 0
        cut_ts   = int(cut_val)  if pd.notna(cut_val)  and str(cut_val)  not in ("", "0") else 0

        existing = set(df["anon_user"].dropna().tolist())
        missing  = [u for u in ALL_USERS if u not in existing]
        if not missing:
            print(f"  [assign] {csv_path.name}: already has all users — skipped")
            continue

        mu, sigma = _grade_params(assign_name)
        new_rows  = []

        for user in missing:
            sub_unix = _submit_unix(open_ts, due_ts)
            time_s   = sub_unix - open_ts
            new_rows.append({
                "course_id":                course_id,
                "cmid":                     cmid,
                "assignid":                 assignid,
                "assign_name":              assign_name,
                "anon_user":                user,
                "submissionid":             _next_sub(),
                "status":                   "submitted",
                "submitted_unix":           sub_unix,
                "submitted_at":             _ts_str(sub_unix),
                "allowsubmissionsfromdate": open_ts,
                "duedate":                  due_ts,
                "cutoffdate":               cut_ts,
                "time_to_submit_seconds":   time_s,
                "time_to_submit_hours":     round(time_s / 3600, 3),
                "grade":                    _grade(mu, sigma),
            })

        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  [assign] {csv_path.name}: +{len(new_rows)} rows -> {len(df)} total")


# ── Augment quizzes ───────────────────────────────────────────────────────────

def augment_quizzes():
    for csv_path in sorted(QUIZ_DIR.glob("quiz_*.csv")):
        df = pd.read_csv(csv_path)
        if df.empty:
            continue

        row0       = df.iloc[0]
        course_id  = int(row0["course_id"])
        cmid       = int(row0["cmid"])
        quizid     = int(row0["quizid"])
        quiz_name  = str(row0["quiz_name"])
        raw_max    = float(row0["raw_max"])
        scaled_max = float(row0["scaled_max"])
        timeopen   = int(row0["timeopen"])  if pd.notna(row0.get("timeopen",  0)) else 0
        timeclose  = int(row0["timeclose"]) if pd.notna(row0.get("timeclose", 0)) else 0
        timelimit  = int(row0["timelimit_seconds"]) if pd.notna(row0.get("timelimit_seconds", 3600)) else 3600
        max_att    = int(row0["attempts_allowed"])  if pd.notna(row0.get("attempts_allowed",  0))    else 0

        # Derive a sensible base timestamp from real data
        real_starts = pd.to_numeric(df["started_unix"], errors="coerce").dropna()
        if len(real_starts) > 0:
            base_ts    = int(real_starts.min())
            spread_sec = max(int(real_starts.max() - real_starts.min()), 86_400 * 5)
        elif timeopen > 0:
            base_ts    = timeopen + 86_400 * 7
            spread_sec = 86_400 * 14
        else:
            base_ts    = 1_759_132_000
            spread_sec = 86_400 * 14

        existing = set(df["anon_user"].dropna().tolist())
        missing  = [u for u in ALL_USERS if u not in existing]
        if not missing:
            print(f"  [quiz]   {csv_path.name}: already has all users — skipped")
            continue

        new_rows = []
        for user in missing:
            # First attempt — scores centred around 62 % with spread
            pct1 = float(np.clip(np.random.normal(62, 22), 0, 100))
            raw1 = round(raw_max * pct1 / 100, 2)
            dur1 = int(np.random.uniform(60, min(timelimit, 900)))
            s1   = base_ts + int(np.random.uniform(0, spread_sec))
            f1   = s1 + dur1

            new_rows.append({
                "course_id": course_id, "cmid": cmid, "quizid": quizid,
                "quiz_name": quiz_name, "anon_user": user,
                "attemptid": _next_att(), "attempt_no": 1, "state": "finished",
                "timestart": _ts_str(s1), "timefinish": _ts_str(f1),
                "started_unix": s1, "finished_unix": f1,
                "duration_seconds": dur1, "duration_minutes": round(dur1 / 60, 3),
                "raw_score": raw1, "raw_max": raw_max, "scaled_max": scaled_max,
                "score_pct": round(pct1, 3),
                "scaled_grade": round(scaled_max * pct1 / 100, 2),
                "timeopen": timeopen, "timeclose": timeclose,
                "timelimit_seconds": timelimit, "attempts_allowed": max_att,
            })

            # ~55 % of students who failed their first attempt try again
            allow_retry = (max_att == 0 or max_att >= 2)
            if pct1 < 60 and allow_retry and random.random() < 0.55:
                improvement = float(np.random.uniform(8, 28))
                pct2 = float(np.clip(pct1 + improvement, 0, 100))
                raw2 = round(raw_max * pct2 / 100, 2)
                dur2 = int(np.random.uniform(60, min(timelimit, 900)))
                s2   = f1 + int(np.random.uniform(600, 86_400 * 2))
                f2   = s2 + dur2

                new_rows.append({
                    "course_id": course_id, "cmid": cmid, "quizid": quizid,
                    "quiz_name": quiz_name, "anon_user": user,
                    "attemptid": _next_att(), "attempt_no": 2, "state": "finished",
                    "timestart": _ts_str(s2), "timefinish": _ts_str(f2),
                    "started_unix": s2, "finished_unix": f2,
                    "duration_seconds": dur2, "duration_minutes": round(dur2 / 60, 3),
                    "raw_score": raw2, "raw_max": raw_max, "scaled_max": scaled_max,
                    "score_pct": round(pct2, 3),
                    "scaled_grade": round(scaled_max * pct2 / 100, 2),
                    "timeopen": timeopen, "timeclose": timeclose,
                    "timelimit_seconds": timelimit, "attempts_allowed": max_att,
                })

        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  [quiz]   {csv_path.name}: +{len(new_rows)} rows -> {len(df)} total")


if __name__ == "__main__":
    print("Augmenting CSVs with synthetic demo data (20-student class simulation)...")
    augment_assignments()
    augment_quizzes()
    print("\nDone. Now run:  python analyse.py")
