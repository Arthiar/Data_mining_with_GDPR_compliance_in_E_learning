# export.py
# Connects to Moodle via the REST API, downloads course activity data,
# replaces all user IDs with anonymised codes for privacy, and saves
# the results as CSV files in the output/exports/ folder.
#
# How to run:
#   1. Copy .env.example to .env and fill in your Moodle details
#   2. pip install -r requirements.txt
#   3. python export.py

import os
import sys
import time
import shutil
import hashlib
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# Load settings from the .env file
load_dotenv()

MOODLE_URL = os.getenv("MOODLE_BASE_URL", "").rstrip("/")
TOKEN      = os.getenv("MOODLE_WSTOKEN", "")
SALT       = os.getenv("HASH_SALT", "default_salt")
COURSE_ID  = int(os.getenv("COURSE_ID", "0"))
API_URL    = MOODLE_URL + "/webservice/rest/server.php"

# Output folder paths
ROOT    = Path(__file__).parent
OUT     = ROOT / "output"
EXPORTS = OUT / "exports"
LOGS    = OUT / "logs"


# ── Logging ───────────────────────────────────────────────────────────────────

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ── Utility functions ─────────────────────────────────────────────────────────

def anonymise(user_id):
    """Replace a real user ID with a consistent hashed code (SHA-256)."""
    if user_id is None:
        return None
    hashed = hashlib.sha256((SALT + str(user_id)).encode()).hexdigest()
    return "u_" + hashed[:12]


def to_datetime_str(timestamp):
    """Convert a Unix timestamp to a readable date string."""
    if not timestamp or int(timestamp) == 0:
        return None
    return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def calc_duration(start, finish):
    """Return the number of seconds between two Unix timestamps."""
    try:
        return int(finish) - int(start)
    except Exception:
        return None


def parse_cmids(value):
    """Parse a comma-separated string of IDs from the .env file."""
    if not value:
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]


# ── Moodle API ────────────────────────────────────────────────────────────────

def call_moodle(function_name, **params):
    """Send a request to the Moodle REST API and return the response as a Python object."""

    # Build the base payload
    payload = {
        "wstoken":             TOKEN,
        "wsfunction":          function_name,
        "moodlewsrestformat":  "json",
    }

    # Moodle expects list parameters as key[0]=val, key[1]=val, etc.
    for key, value in params.items():
        if isinstance(value, list):
            for i, item in enumerate(value):
                payload[f"{key}[{i}]"] = item
        else:
            payload[key] = value

    # Try up to 3 times in case of a temporary network issue
    for attempt in range(1, 4):
        try:
            response = requests.post(API_URL, data=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get("exception"):
                raise RuntimeError(f"Moodle API error: {data.get('message', str(data))}")
            return data
        except Exception as e:
            if attempt == 3:
                raise
            log(f"Request failed (attempt {attempt}): {e}. Retrying in 3 seconds...")
            time.sleep(3)


# ── Setup ─────────────────────────────────────────────────────────────────────

def reset_output():
    """Delete and recreate the output folder so each run starts fresh."""
    if OUT.exists():
        shutil.rmtree(OUT)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)


def get_modules():
    """Return a dictionary of {cmid: {modname, instance, name}} for every module in the course."""
    modules = {}
    sections = call_moodle("core_course_get_contents", courseid=COURSE_ID)
    for section in sections:
        for mod in section.get("modules", []):
            cmid = mod.get("id")
            if cmid:
                modules[int(cmid)] = {
                    "modname":  mod.get("modname"),
                    "instance": mod.get("instance"),
                    "name":     mod.get("name"),
                }
    return modules


def get_enrolled_users():
    """Return a list of user IDs enrolled in the course."""
    users = call_moodle("core_enrol_get_enrolled_users", courseid=COURSE_ID)
    return [int(u["id"]) for u in users]


# ── Export functions ──────────────────────────────────────────────────────────

def export_quizzes(cmids, modules):
    if not cmids:
        log("[quiz] No quiz CMIDs configured — skipping.")
        return

    # Fetch quiz configuration (names, max scores, time limits, etc.)
    quiz_data = call_moodle("mod_quiz_get_quizzes_by_courses", courseids=[COURSE_ID])
    if isinstance(quiz_data, dict):
        quiz_list = quiz_data.get("quizzes", [])
    else:
        quiz_list = quiz_data or []

    # Build a lookup table: quiz_id -> config
    quiz_config = {}
    for q in quiz_list:
        try:
            quiz_config[int(q["id"])] = q
        except Exception:
            continue

    enrolled_users = get_enrolled_users()

    for cmid in cmids:
        mod = modules.get(cmid, {})
        if mod.get("modname") != "quiz":
            log(f"[quiz] CMID {cmid} is not a quiz — skipping.")
            continue

        quiz_id   = int(mod["instance"])
        config    = quiz_config.get(quiz_id, {})
        name      = config.get("name") or mod.get("name")
        max_score = config.get("sumgrades")
        max_grade = config.get("grade")

        log(f"[quiz] Exporting '{name}' (quizid={quiz_id}, cmid={cmid})")
        rows = []

        for user_id in tqdm(enrolled_users, desc=f"quiz {quiz_id}"):
            try:
                result   = call_moodle("mod_quiz_get_user_attempts", quizid=quiz_id, userid=user_id, status="all")
                attempts = result.get("attempts", []) if isinstance(result, dict) else result or []
            except Exception as e:
                log(f"  Could not get attempts for user {user_id}: {e}")
                continue

            for attempt in attempts:
                start      = attempt.get("timestart")
                finish     = attempt.get("timefinish")
                duration_s = calc_duration(start, finish)
                raw_score  = attempt.get("sumgrades")

                # Work out the percentage score
                if raw_score is not None and max_score:
                    score_pct = round(float(raw_score) / float(max_score) * 100, 3)
                else:
                    score_pct = None

                # Work out the scaled grade
                if raw_score is not None and max_score and max_grade:
                    scaled_grade = round(float(raw_score) / float(max_score) * float(max_grade), 3)
                else:
                    scaled_grade = None

                rows.append({
                    "course_id":         COURSE_ID,
                    "cmid":              cmid,
                    "quizid":            quiz_id,
                    "quiz_name":         name,
                    "anon_user":         anonymise(user_id),
                    "attemptid":         attempt.get("id"),
                    "attempt_no":        attempt.get("attempt"),
                    "state":             attempt.get("state"),
                    "timestart":         to_datetime_str(start),
                    "timefinish":        to_datetime_str(finish),
                    "started_unix":      start,
                    "finished_unix":     finish,
                    "duration_seconds":  duration_s,
                    "duration_minutes":  round(duration_s / 60, 3) if duration_s else None,
                    "raw_score":         raw_score,
                    "raw_max":           max_score,
                    "scaled_max":        max_grade,
                    "score_pct":         score_pct,
                    "scaled_grade":      scaled_grade,
                    "timeopen":          config.get("timeopen"),
                    "timeclose":         config.get("timeclose"),
                    "timelimit_seconds": config.get("timelimit"),
                    "attempts_allowed":  config.get("attempts"),
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            path = EXPORTS / f"quiz_{cmid}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            log(f"[quiz] Wrote {len(df)} rows -> {path.name}")
        else:
            log(f"[quiz] No rows for cmid {cmid}.")


def export_assignments(cmids, modules):
    if not cmids:
        log("[assign] No assignment CMIDs configured — skipping.")
        return

    # Fetch all assignments for this course
    result      = call_moodle("mod_assign_get_assignments", courseids=[COURSE_ID])
    assignments = {}
    for course in result.get("courses", []):
        for a in course.get("assignments", []):
            assignments[int(a["id"])] = a

    # Fetch grades for all assignments
    grades = {}
    if assignments:
        grade_result = call_moodle("mod_assign_get_grades", assignmentids=list(assignments.keys()))
        for ag in grade_result.get("assignments", []):
            aid = int(ag["assignmentid"])
            for g in ag.get("grades", []):
                try:
                    grades[(aid, int(g["userid"]))] = g.get("grade")
                except Exception:
                    pass

    for cmid in cmids:
        mod = modules.get(cmid, {})
        if mod.get("modname") != "assign":
            log(f"[assign] CMID {cmid} is not an assignment — skipping.")
            continue

        assign_id = int(mod["instance"])
        config    = assignments.get(assign_id, {})
        name      = mod.get("name")
        open_date = config.get("allowsubmissionsfromdate")
        due_date  = config.get("duedate")
        cutoff    = config.get("cutoffdate")

        result = call_moodle("mod_assign_get_submissions", assignmentids=[assign_id])
        rows   = []

        for a in result.get("assignments", []):
            for sub in a.get("submissions", []):
                try:
                    uid = int(sub["userid"])
                except Exception:
                    uid = None

                submitted      = sub.get("timemodified") or sub.get("timecreated")
                time_to_submit = None
                if submitted and open_date:
                    time_to_submit = int(submitted) - int(open_date)

                rows.append({
                    "course_id":                COURSE_ID,
                    "cmid":                     cmid,
                    "assignid":                 assign_id,
                    "assign_name":              name,
                    "anon_user":                anonymise(uid),
                    "submissionid":             sub.get("id"),
                    "status":                   sub.get("status"),
                    "submitted_unix":            submitted,
                    "submitted_at":             to_datetime_str(submitted),
                    "allowsubmissionsfromdate": open_date,
                    "duedate":                  due_date,
                    "cutoffdate":               cutoff,
                    "time_to_submit_seconds":   time_to_submit,
                    "time_to_submit_hours":     round(time_to_submit / 3600, 3) if time_to_submit else None,
                    "grade":                    grades.get((assign_id, uid)) if uid else None,
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            path = EXPORTS / f"assign_{cmid}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            log(f"[assign] Wrote {len(df)} rows -> {path.name}")
        else:
            log(f"[assign] No rows for cmid {cmid}.")


def export_h5p(cmids, modules):
    if not cmids:
        log("[h5p] No H5P CMIDs configured — skipping.")
        return

    # Separate modern H5P activities from the legacy HVP plugin
    h5p_cmids = [c for c in cmids if modules.get(c, {}).get("modname") == "h5pactivity"]
    hvp_cmids = [c for c in cmids if modules.get(c, {}).get("modname") == "hvp"]

    if hvp_cmids:
        log(f"[h5p] Skipping legacy 'mod_hvp' CMIDs (not supported): {hvp_cmids}")

    if not h5p_cmids:
        log("[h5p] No 'H5P activity' (mod_h5pactivity) CMIDs to export — skipping.")
        return

    # Map instance ID -> CMID for the H5P modules we care about
    instance_to_cmid = {}
    for cmid in h5p_cmids:
        instance = modules[cmid].get("instance")
        if instance:
            instance_to_cmid[int(instance)] = cmid

    try:
        result     = call_moodle("mod_h5pactivity_get_h5pactivities_by_courses", courseids=[COURSE_ID])
        activities = result.get("h5pactivities", []) if isinstance(result, dict) else result or []
    except Exception as e:
        log(f"[h5p] H5P endpoints not available: {e}")
        return

    for activity in activities:
        try:
            h5p_id = int(activity["id"])
        except Exception:
            continue

        cmid = instance_to_cmid.get(h5p_id)
        if not cmid:
            continue

        name = activity.get("name")
        log(f"[h5p] Exporting '{name}' (h5pactivityid={h5p_id}, cmid={cmid})")

        # Get attempt records
        try:
            att_result = call_moodle("mod_h5pactivity_get_user_attempts", h5pactivityid=h5p_id)
            attempts   = att_result.get("attempts", []) if isinstance(att_result, dict) else att_result or []
        except Exception as e:
            log(f"  Could not get attempts: {e}")
            attempts = []

        # Get score results
        try:
            res_result   = call_moodle("mod_h5pactivity_get_results", h5pactivityid=h5p_id)
            results_list = res_result.get("results", []) if isinstance(res_result, dict) else res_result or []
        except Exception:
            results_list = []

        results_by_id = {r.get("attemptid") or r.get("id"): r for r in results_list}

        rows = []
        for att in attempts:
            uid     = att.get("userid")
            start   = att.get("timecreated") or att.get("timestarted")
            finish  = att.get("timemodified") or att.get("timefinished")
            att_id  = att.get("id")
            res     = results_by_id.get(att_id, {})
            score   = res.get("score")
            max_sc  = res.get("maxscore")

            score_pct = round(score / max_sc * 100, 3) if score is not None and max_sc else None

            rows.append({
                "course_id":        COURSE_ID,
                "cmid":             cmid,
                "h5pactivityid":    h5p_id,
                "h5p_name":         name,
                "anon_user":        anonymise(uid),
                "attemptid":        att_id,
                "timestart":        to_datetime_str(start),
                "timefinish":       to_datetime_str(finish),
                "started_unix":     start,
                "finished_unix":    finish,
                "duration_seconds": calc_duration(start, finish),
                "score":            score,
                "maxscore":         max_sc,
                "score_pct":        score_pct,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            path = EXPORTS / f"h5p_{cmid}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            log(f"[h5p] Wrote {len(df)} rows -> {path.name}")
        else:
            log(f"[h5p] No rows for cmid {cmid}.")


def export_databases(cmids, modules):
    if not cmids:
        log("[data] No database CMIDs configured — skipping.")
        return

    data_cmids = [c for c in cmids if modules.get(c, {}).get("modname") == "data"]
    if not data_cmids:
        log("[data] No 'Database' (mod_data) CMIDs found — skipping.")
        return

    instance_to_cmid = {}
    for cmid in data_cmids:
        instance = modules[cmid].get("instance")
        if instance:
            instance_to_cmid[int(instance)] = cmid

    try:
        result = call_moodle("mod_data_get_databases_by_courses", courseids=[COURSE_ID])
    except Exception as e:
        log(f"[data] mod_data_get_databases_by_courses not available: {e}")
        return

    if isinstance(result, dict) and "databases" in result:
        db_list = result["databases"]
    elif isinstance(result, list):
        db_list = result
    else:
        db_list = []

    for db in db_list:
        try:
            db_id = int(db["id"])
        except Exception:
            continue

        cmid = instance_to_cmid.get(db_id)
        if not cmid:
            continue

        name = db.get("name")
        log(f"[data] Exporting '{name}' (databaseid={db_id}, cmid={cmid})")

        try:
            entries_result = call_moodle("mod_data_get_entries", databaseid=db_id)
            entries = entries_result.get("entries", []) if isinstance(entries_result, dict) else []
        except Exception as e:
            log(f"[data] Could not get entries: {e}")
            entries = []

        rows = []
        for entry in entries:
            uid     = entry.get("userid")
            created = entry.get("timecreated")
            rows.append({
                "course_id":     COURSE_ID,
                "cmid":          cmid,
                "databaseid":    db_id,
                "database_name": name,
                "entryid":       entry.get("id"),
                "anon_user":     anonymise(uid),
                "created_unix":  created,
                "created_at":    to_datetime_str(created),
                "approved":      entry.get("approved"),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            path = EXPORTS / f"data_{cmid}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            log(f"[data] Wrote {len(df)} rows -> {path.name}")
        else:
            log(f"[data] No rows for cmid {cmid}.")


def export_forums(cmids, modules):
    if not cmids:
        log("[forum] None configured — skipping.")
        return

    # Map forum instance ID -> CMID
    instance_to_cmid = {}
    for cmid, mod in modules.items():
        if mod.get("modname") == "forum":
            instance_to_cmid[mod["instance"]] = cmid

    try:
        forums = call_moodle("mod_forum_get_forums_by_courses", courseids=[COURSE_ID])
    except Exception as e:
        log(f"[forum] Forum endpoints not available: {e}")
        return

    for forum in forums:
        forum_id = int(forum["id"])
        cmid     = instance_to_cmid.get(forum_id)
        if cmid not in cmids:
            continue

        name = forum.get("name")
        log(f"[forum] Exporting '{name}' (forumid={forum_id}, cmid={cmid})")

        try:
            disc_result  = call_moodle("mod_forum_get_forum_discussions", forumid=forum_id)
            discussions  = disc_result.get("discussions", []) if isinstance(disc_result, dict) else disc_result or []
        except Exception as e:
            log(f"  Could not get discussions: {e}")
            continue

        rows = []
        for discussion in discussions:
            disc_id = discussion.get("discussion") or discussion.get("id")
            try:
                post_result = call_moodle("mod_forum_get_discussion_posts", discussionid=disc_id)
                posts       = post_result.get("posts", []) if isinstance(post_result, dict) else post_result or []
            except Exception as e:
                log(f"  Could not get posts for discussion {disc_id}: {e}")
                continue

            for post in posts:
                uid     = post.get("userid") or (post.get("author") or {}).get("id")
                created = post.get("timecreated")
                rows.append({
                    "course_id":    COURSE_ID,
                    "cmid":         cmid,
                    "forumid":      forum_id,
                    "forum_name":   name,
                    "discussionid": disc_id,
                    "postid":       post.get("id"),
                    "parentid":     post.get("parent"),
                    "anon_user":    anonymise(uid),
                    "created_unix": created,
                    "created_at":   to_datetime_str(created),
                    "subject":      post.get("subject"),
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            path = EXPORTS / f"forum_{cmid}_posts.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            log(f"[forum] Wrote {len(df)} rows -> {path.name}")
            # Save a simple summary: posts per anonymised user
            summary = df.groupby("anon_user")["postid"].count().reset_index(name="posts")
            summary.to_csv(EXPORTS / f"forum_{cmid}_summary.csv", index=False, encoding="utf-8-sig")
        else:
            log(f"[forum] No posts for cmid {cmid}.")


# ── Main entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not MOODLE_URL or not TOKEN or not COURSE_ID:
        print("Error: Please set MOODLE_BASE_URL, MOODLE_WSTOKEN, and COURSE_ID in your .env file.")
        sys.exit(1)

    quiz_cmids   = parse_cmids(os.getenv("QUIZ_CMIDS",   ""))
    assign_cmids = parse_cmids(os.getenv("ASSIGN_CMIDS", ""))
    forum_cmids  = parse_cmids(os.getenv("FORUM_CMIDS",  ""))
    h5p_cmids    = parse_cmids(os.getenv("HVP_CMIDS",    ""))
    data_cmids   = parse_cmids(os.getenv("DATA_CMIDS",   ""))

    reset_output()
    log("Export started.")

    # Check the connection and confirm which Moodle site we are on
    site_info = call_moodle("core_webservice_get_site_info")
    log(f"Connected to Moodle {site_info.get('sitename')} as user id {site_info.get('userid')}")

    modules = get_modules()
    log(f"Discovered {len(modules)} modules in course {COURSE_ID}.")

    export_quizzes(quiz_cmids, modules)
    export_assignments(assign_cmids, modules)
    export_h5p(h5p_cmids, modules)
    export_databases(data_cmids, modules)
    export_forums(forum_cmids, modules)

    log("Export done. Check the 'output/exports' folder.")
