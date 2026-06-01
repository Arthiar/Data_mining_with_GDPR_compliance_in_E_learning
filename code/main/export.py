# export.py
# Main export script: downloads Moodle student activity data and saves it as CSV files.
# Run this first. Then run analyse.py to create charts from the saved data.
#
# How to run:
#   1. Create a .env file with your Moodle credentials
#   2. pip install -r requirements.txt
#   3. python export.py

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from moodle_client import MoodleClient


# ─── SETUP ───────────────────────────────────────────────────────────────────

def load_settings():
    # Read all configuration values from the .env file and return them as a dictionary.
    load_dotenv()

    return {
        "moodle_url": os.getenv("MOODLE_BASE_URL", ""),
        "token": os.getenv("MOODLE_WSTOKEN", ""),
        "salt": os.getenv("HASH_SALT", "default_salt"),
        "course_id": int(os.getenv("COURSE_ID", "0")),
        "quiz_cmids": os.getenv("QUIZ_CMIDS", ""),
        "assign_cmids": os.getenv("ASSIGN_CMIDS", ""),
        "forum_cmids": os.getenv("FORUM_CMIDS", ""),
        "h5p_cmids": os.getenv("HVP_CMIDS", ""),
        "data_cmids": os.getenv("DATA_CMIDS", ""),
    }


def setup_output_folders(root_folder):
    # Delete any previous output folder and create fresh empty folders for exports and logs.
    output_folder = root_folder / "output"
    exports_folder = output_folder / "exports"
    logs_folder = output_folder / "logs"

    if output_folder.exists():
        shutil.rmtree(output_folder)

    exports_folder.mkdir(parents=True, exist_ok=True)
    logs_folder.mkdir(parents=True, exist_ok=True)

    return exports_folder, logs_folder


def write_log(logs_folder, message):
    # Print a message to the screen with a timestamp and also save it to the log file.
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)

    with open(logs_folder / "run.log", "a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


def save_rows_to_csv(rows, file_path):
    # Save a list of data rows to a CSV file. Returns True if the file was written.
    dataframe = pd.DataFrame(rows)
    if not dataframe.empty:
        dataframe.to_csv(file_path, index=False, encoding="utf-8-sig")
        return True
    return False


# ─── QUIZ EXPORT ─────────────────────────────────────────────────────────────

def export_quizzes(client, course_id, quiz_cmids, all_modules, exports_folder, logs_folder):
    # Download every student's quiz attempts for each quiz and save to quiz_<cmid>.csv.

    if not quiz_cmids:
        write_log(logs_folder, "[quiz] No quiz CMIDs configured — skipping.")
        return

    # Get the configuration for all quizzes in the course (name, max score, time limit, etc.)
    quiz_response = client.call_api("mod_quiz_get_quizzes_by_courses", courseids=[course_id])

    if isinstance(quiz_response, dict):
        quiz_list = quiz_response.get("quizzes", [])
    else:
        quiz_list = quiz_response or []

    # Build a lookup table: quiz ID → quiz settings
    quiz_settings = {}
    for quiz in quiz_list:
        if "id" in quiz:
            quiz_settings[int(quiz["id"])] = quiz

    all_student_ids = client.get_enrolled_student_ids(course_id)

    for cmid in quiz_cmids:
        module = all_modules.get(cmid, {})

        if module.get("modname") != "quiz":
            write_log(logs_folder, f"[quiz] CMID {cmid} is not a quiz — skipping.")
            continue

        quiz_id = int(module["instance"])
        settings = quiz_settings.get(quiz_id, {})
        quiz_name = settings.get("name") or module.get("name")
        max_possible_score = settings.get("sumgrades")
        max_possible_grade = settings.get("grade")

        write_log(logs_folder, f"[quiz] Exporting '{quiz_name}'")

        rows = []

        # Loop through every student and collect their quiz attempts
        for student_id in tqdm(all_student_ids, desc=f"quiz {quiz_id}", leave=False):
            try:
                attempts_response = client.call_api(
                    "mod_quiz_get_user_attempts",
                    quizid=quiz_id,
                    userid=student_id,
                    status="all"
                )
            except Exception as error:
                write_log(logs_folder, f"    Could not fetch attempts for user {student_id}: {error}")
                continue

            if isinstance(attempts_response, dict):
                attempts_list = attempts_response.get("attempts", [])
            else:
                attempts_list = attempts_response or []

            for attempt in attempts_list:
                start_time = attempt.get("timestart")
                finish_time = attempt.get("timefinish")
                duration_seconds = client.duration_in_seconds(start_time, finish_time)
                raw_score = attempt.get("sumgrades")

                # Calculate what percentage of the total marks this score represents
                if raw_score is not None and max_possible_score:
                    score_pct = round(float(raw_score) / float(max_possible_score) * 100, 3)
                else:
                    score_pct = None

                # Calculate the score on the quiz's grading scale (e.g., out of 10)
                if raw_score is not None and max_possible_score and max_possible_grade:
                    scaled_grade = round(float(raw_score) / float(max_possible_score) * float(max_possible_grade), 3)
                else:
                    scaled_grade = None

                # Convert duration from seconds to minutes
                if duration_seconds is not None:
                    duration_minutes = round(duration_seconds / 60, 3)
                else:
                    duration_minutes = None

                rows.append({
                    "course_id": course_id,
                    "cmid": cmid,
                    "quizid": quiz_id,
                    "quiz_name": quiz_name,
                    "anon_user": client.anonymize_student_id(student_id),
                    "attemptid": attempt.get("id"),
                    "attempt_no": attempt.get("attempt"),
                    "state": attempt.get("state"),
                    "timestart": client.unix_timestamp_to_date(start_time),
                    "timefinish": client.unix_timestamp_to_date(finish_time),
                    "started_unix": start_time,
                    "finished_unix": finish_time,
                    "duration_seconds": duration_seconds,
                    "duration_minutes": duration_minutes,
                    "raw_score": raw_score,
                    "raw_max": max_possible_score,
                    "scaled_max": max_possible_grade,
                    "score_pct": score_pct,
                    "scaled_grade": scaled_grade,
                    "timeopen": settings.get("timeopen"),
                    "timeclose": settings.get("timeclose"),
                    "timelimit_seconds": settings.get("timelimit"),
                    "attempts_allowed": settings.get("attempts"),
                })

        file_path = exports_folder / f"quiz_{cmid}.csv"
        if save_rows_to_csv(rows, file_path):
            write_log(logs_folder, f"  → Saved {len(rows)} rows to {file_path.name}")


# ─── ASSIGNMENT EXPORT ───────────────────────────────────────────────────────

def export_assignments(client, course_id, assignment_cmids, all_modules, exports_folder, logs_folder):
    # Download every student's assignment submission and grade, save to assign_<cmid>.csv.

    if not assignment_cmids:
        write_log(logs_folder, "[assign] No CMIDs configured — skipping.")
        return

    # Get all assignments and their configurations from Moodle
    assignments_response = client.call_api("mod_assign_get_assignments", courseids=[course_id])

    all_assignments = {}
    for course_data in assignments_response.get("courses", []):
        for assignment in course_data.get("assignments", []):
            all_assignments[int(assignment["id"])] = assignment

    # Get all grades for all assignments in one request
    all_grades = {}
    if all_assignments:
        assignment_id_list = list(all_assignments.keys())
        grades_response = client.call_api("mod_assign_get_grades", assignmentids=assignment_id_list)

        for assignment_grade_data in grades_response.get("assignments", []):
            assign_id = int(assignment_grade_data["assignmentid"])
            for grade_entry in assignment_grade_data.get("grades", []):
                try:
                    student_id = int(grade_entry["userid"])
                    all_grades[(assign_id, student_id)] = grade_entry.get("grade")
                except Exception:
                    pass

    for cmid in assignment_cmids:
        module = all_modules.get(cmid, {})

        if module.get("modname") != "assign":
            write_log(logs_folder, f"[assign] CMID {cmid} is not an assignment — skipping.")
            continue

        assign_id = int(module["instance"])
        assign_config = all_assignments.get(assign_id, {})
        assign_name = module.get("name")

        write_log(logs_folder, f"[assign] Exporting '{assign_name}'")

        submissions_response = client.call_api("mod_assign_get_submissions", assignmentids=[assign_id])
        rows = []

        for assignment_data in submissions_response.get("assignments", []):
            for submission in assignment_data.get("submissions", []):
                try:
                    student_id = int(submission["userid"])
                except Exception:
                    student_id = None

                submitted_time = submission.get("timemodified") or submission.get("timecreated")
                open_time = assign_config.get("allowsubmissionsfromdate")

                # Calculate how many seconds the student took after the assignment opened
                if submitted_time and open_time:
                    time_to_submit = int(submitted_time) - int(open_time)
                    time_to_submit_hours = round(time_to_submit / 3600, 3)
                else:
                    time_to_submit = None
                    time_to_submit_hours = None

                grade = all_grades.get((assign_id, student_id)) if student_id else None

                rows.append({
                    "course_id": course_id,
                    "cmid": cmid,
                    "assignid": assign_id,
                    "assign_name": assign_name,
                    "anon_user": client.anonymize_student_id(student_id),
                    "submissionid": submission.get("id"),
                    "status": submission.get("status"),
                    "submitted_unix": submitted_time,
                    "submitted_at": client.unix_timestamp_to_date(submitted_time),
                    "allowsubmissionsfromdate": open_time,
                    "duedate": assign_config.get("duedate"),
                    "cutoffdate": assign_config.get("cutoffdate"),
                    "time_to_submit_seconds": time_to_submit,
                    "time_to_submit_hours": time_to_submit_hours,
                    "grade": grade,
                })

        file_path = exports_folder / f"assign_{cmid}.csv"
        if save_rows_to_csv(rows, file_path):
            write_log(logs_folder, f"  → Saved {len(rows)} rows to {file_path.name}")


# ─── H5P EXPORT ──────────────────────────────────────────────────────────────

def export_h5p(client, course_id, h5p_cmids, all_modules, exports_folder, logs_folder):
    # Download student attempt data for H5P interactive activities, save to h5p_<cmid>.csv.

    if not h5p_cmids:
        write_log(logs_folder, "[h5p] No CMIDs configured — skipping.")
        return

    # Keep only CMIDs that actually point to H5P activity modules
    valid_h5p_cmids = []
    for cmid in h5p_cmids:
        if all_modules.get(cmid, {}).get("modname") == "h5pactivity":
            valid_h5p_cmids.append(cmid)

    if not valid_h5p_cmids:
        write_log(logs_folder, "[h5p] No H5P activity modules found — skipping.")
        return

    # Build a lookup: h5p instance ID → cmid
    instance_to_cmid = {}
    for cmid in valid_h5p_cmids:
        instance = all_modules[cmid].get("instance")
        if instance:
            instance_to_cmid[int(instance)] = cmid

    try:
        result = client.call_api("mod_h5pactivity_get_h5pactivities_by_courses", courseids=[course_id])
        if isinstance(result, dict):
            activities = result.get("h5pactivities", [])
        else:
            activities = result or []
    except Exception as error:
        write_log(logs_folder, f"[h5p] H5P endpoints not available: {error}")
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
        write_log(logs_folder, f"[h5p] Exporting '{name}'")

        # Get all student attempts for this activity
        try:
            attempts_result = client.call_api("mod_h5pactivity_get_user_attempts", h5pactivityid=h5p_id)
            if isinstance(attempts_result, dict):
                attempts = attempts_result.get("attempts", [])
            else:
                attempts = attempts_result or []
        except Exception as error:
            write_log(logs_folder, f"    Could not get attempts: {error}")
            attempts = []

        # Get the scores for each attempt
        try:
            results_result = client.call_api("mod_h5pactivity_get_results", h5pactivityid=h5p_id)
            if isinstance(results_result, dict):
                results_list = results_result.get("results", [])
            else:
                results_list = []
        except Exception:
            results_list = []

        # Build a lookup table: attempt ID → score data
        results_by_attempt_id = {}
        for result_item in results_list:
            key = result_item.get("attemptid") or result_item.get("id")
            results_by_attempt_id[key] = result_item

        rows = []
        for attempt in attempts:
            user_id = attempt.get("userid")
            start = attempt.get("timecreated") or attempt.get("timestarted")
            finish = attempt.get("timemodified") or attempt.get("timefinished")
            attempt_id = attempt.get("id")

            result_data = results_by_attempt_id.get(attempt_id, {})
            score = result_data.get("score")
            max_score = result_data.get("maxscore")

            if score is not None and max_score:
                score_pct = round(score / max_score * 100, 3)
            else:
                score_pct = None

            rows.append({
                "course_id": course_id,
                "cmid": cmid,
                "h5pactivityid": h5p_id,
                "h5p_name": name,
                "anon_user": client.anonymize_student_id(user_id),
                "attemptid": attempt_id,
                "timestart": client.unix_timestamp_to_date(start),
                "timefinish": client.unix_timestamp_to_date(finish),
                "started_unix": start,
                "finished_unix": finish,
                "duration_seconds": client.duration_in_seconds(start, finish),
                "score": score,
                "maxscore": max_score,
                "score_pct": score_pct,
            })

        file_path = exports_folder / f"h5p_{cmid}.csv"
        if save_rows_to_csv(rows, file_path):
            write_log(logs_folder, f"  → Saved {len(rows)} rows to {file_path.name}")


# ─── FORUM EXPORT ────────────────────────────────────────────────────────────

def export_forums(client, course_id, forum_cmids, all_modules, exports_folder, logs_folder):
    # Download all forum posts for each forum and save to forum_<cmid>_posts.csv.

    if not forum_cmids:
        write_log(logs_folder, "[forum] No CMIDs configured — skipping.")
        return

    # Build a lookup: forum instance ID → cmid
    instance_to_cmid = {}
    for cmid, module in all_modules.items():
        if module.get("modname") == "forum":
            instance_to_cmid[module["instance"]] = cmid

    try:
        forums = client.call_api("mod_forum_get_forums_by_courses", courseids=[course_id])
    except Exception as error:
        write_log(logs_folder, f"[forum] Forum endpoints not available: {error}")
        return

    for forum in forums:
        forum_id = int(forum["id"])
        cmid = instance_to_cmid.get(forum_id)

        if cmid not in forum_cmids:
            continue

        name = forum.get("name")
        write_log(logs_folder, f"[forum] Exporting '{name}'")

        try:
            disc_result = client.call_api("mod_forum_get_forum_discussions", forumid=forum_id)
            if isinstance(disc_result, dict):
                discussions = disc_result.get("discussions", [])
            else:
                discussions = disc_result or []
        except Exception as error:
            write_log(logs_folder, f"    Could not get discussions: {error}")
            continue

        rows = []
        for discussion in discussions:
            disc_id = discussion.get("discussion") or discussion.get("id")

            try:
                post_result = client.call_api("mod_forum_get_discussion_posts", discussionid=disc_id)
                if isinstance(post_result, dict):
                    posts = post_result.get("posts", [])
                else:
                    posts = post_result or []
            except Exception as error:
                write_log(logs_folder, f"    Could not get posts for discussion {disc_id}: {error}")
                continue

            for post in posts:
                # User ID may be directly on the post, or nested inside an "author" object
                user_id = post.get("userid")
                if user_id is None:
                    author = post.get("author") or {}
                    user_id = author.get("id")

                created = post.get("timecreated")
                rows.append({
                    "course_id": course_id,
                    "cmid": cmid,
                    "forumid": forum_id,
                    "forum_name": name,
                    "discussionid": disc_id,
                    "postid": post.get("id"),
                    "parentid": post.get("parent"),
                    "anon_user": client.anonymize_student_id(user_id),
                    "created_unix": created,
                    "created_at": client.unix_timestamp_to_date(created),
                    "subject": post.get("subject"),
                })

        posts_file = exports_folder / f"forum_{cmid}_posts.csv"
        if save_rows_to_csv(rows, posts_file):
            write_log(logs_folder, f"  → Saved {len(rows)} rows to {posts_file.name}")

            # Also save a summary: how many posts each student made
            posts_df = pd.DataFrame(rows)
            summary = posts_df.groupby("anon_user")["postid"].count().reset_index(name="posts")
            summary.to_csv(exports_folder / f"forum_{cmid}_summary.csv", index=False, encoding="utf-8-sig")


# ─── DATABASE EXPORT ─────────────────────────────────────────────────────────

def export_databases(client, course_id, database_cmids, all_modules, exports_folder, logs_folder):
    # Download all database activity entries and save to data_<cmid>.csv.

    if not database_cmids:
        write_log(logs_folder, "[data] No CMIDs configured — skipping.")
        return

    # Keep only CMIDs that actually point to database activity modules
    valid_database_cmids = []
    for cmid in database_cmids:
        if all_modules.get(cmid, {}).get("modname") == "data":
            valid_database_cmids.append(cmid)

    if not valid_database_cmids:
        write_log(logs_folder, "[data] No database modules found — skipping.")
        return

    # Build a lookup: database instance ID → cmid
    instance_to_cmid = {}
    for cmid in valid_database_cmids:
        instance = all_modules[cmid].get("instance")
        if instance:
            instance_to_cmid[int(instance)] = cmid

    try:
        result = client.call_api("mod_data_get_databases_by_courses", courseids=[course_id])
    except Exception as error:
        write_log(logs_folder, f"[data] Database endpoints not available: {error}")
        return

    if isinstance(result, dict) and "databases" in result:
        db_list = result.get("databases", [])
    else:
        db_list = result or []

    for database in db_list:
        try:
            db_id = int(database["id"])
        except Exception:
            continue

        cmid = instance_to_cmid.get(db_id)
        if not cmid:
            continue

        name = database.get("name")
        write_log(logs_folder, f"[data] Exporting '{name}'")

        try:
            entries_result = client.call_api("mod_data_get_entries", databaseid=db_id)
            if isinstance(entries_result, dict):
                entries = entries_result.get("entries", [])
            else:
                entries = []
        except Exception as error:
            write_log(logs_folder, f"    Could not get entries: {error}")
            entries = []

        rows = []
        for entry in entries:
            user_id = entry.get("userid")
            created = entry.get("timecreated")
            rows.append({
                "course_id": course_id,
                "cmid": cmid,
                "databaseid": db_id,
                "database_name": name,
                "entryid": entry.get("id"),
                "anon_user": client.anonymize_student_id(user_id),
                "created_unix": created,
                "created_at": client.unix_timestamp_to_date(created),
                "approved": entry.get("approved"),
            })

        file_path = exports_folder / f"data_{cmid}.csv"
        if save_rows_to_csv(rows, file_path):
            write_log(logs_folder, f"  → Saved {len(rows)} rows to {file_path.name}")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    # Load settings, connect to Moodle, and download all activity data.

    settings = load_settings()

    # Stop immediately if required settings are missing
    if not settings["moodle_url"] or not settings["token"] or not settings["course_id"]:
        print("Error: Missing configuration in .env file")
        print("Required: MOODLE_BASE_URL, MOODLE_WSTOKEN, COURSE_ID")
        sys.exit(1)

    # Set up the output folders (this deletes any previous output)
    root_folder = Path(__file__).parent.parent.parent
    exports_folder, logs_folder = setup_output_folders(root_folder)

    # Create the connection to Moodle
    client = MoodleClient(
        base_url=settings["moodle_url"],
        token=settings["token"],
        salt=settings["salt"],
    )
    course_id = settings["course_id"]

    write_log(logs_folder, "=" * 70)
    write_log(logs_folder, "MOODLE EXPORT STARTED")
    write_log(logs_folder, "=" * 70)

    # Test the connection before doing anything else
    try:
        site_info = client.call_api("core_webservice_get_site_info")
        write_log(logs_folder, f"✓ Connected to: {site_info.get('sitename')}")
        write_log(logs_folder, f"  User: {site_info.get('username')} (ID: {site_info.get('userid')})")
    except Exception as error:
        write_log(logs_folder, f"✗ Connection failed: {error}")
        sys.exit(1)

    # Get the list of all activities in the course
    all_modules = client.get_all_course_modules(course_id)
    write_log(logs_folder, f"✓ Found {len(all_modules)} modules in course {course_id}")
    write_log(logs_folder, "")
    write_log(logs_folder, "Starting exports...")

    # Read which activity IDs to export from the .env settings
    quiz_cmids = client.parse_cmid_list(settings["quiz_cmids"])
    assign_cmids = client.parse_cmid_list(settings["assign_cmids"])
    forum_cmids = client.parse_cmid_list(settings["forum_cmids"])
    h5p_cmids = client.parse_cmid_list(settings["h5p_cmids"])
    data_cmids = client.parse_cmid_list(settings["data_cmids"])

    # Export each activity type in turn
    export_quizzes(client, course_id, quiz_cmids, all_modules, exports_folder, logs_folder)
    export_assignments(client, course_id, assign_cmids, all_modules, exports_folder, logs_folder)
    export_h5p(client, course_id, h5p_cmids, all_modules, exports_folder, logs_folder)
    export_databases(client, course_id, data_cmids, all_modules, exports_folder, logs_folder)
    export_forums(client, course_id, forum_cmids, all_modules, exports_folder, logs_folder)

    write_log(logs_folder, "")
    write_log(logs_folder, "=" * 70)
    write_log(logs_folder, "✓ EXPORT COMPLETED")
    write_log(logs_folder, f"  Data saved to: {exports_folder}")
    write_log(logs_folder, "=" * 70)


if __name__ == "__main__":
    main()
