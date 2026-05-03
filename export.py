# export.py — export Moodle course data (quizzes, assignments, H5P, database, forums),
# anonymise users, write CSVs, and reset ./output on every run.
#
# Usage:
#   1) Create .env (see values below)
#   2) pip install -r requirements.txt
#   3) python export.py
#
# .env keys (example):
#   MOODLE_BASE_URL=https://moodle-dev.go-study-europe.de
#   MOODLE_WSTOKEN=YOUR_TOKEN_HERE
#   COURSE_ID=1516
#   QUIZ_CMIDS=2641,2672,2657
#   ASSIGN_CMIDS=2652,2659,2660,2664,2665,2667,2673
#   FORUM_CMIDS=
#   HVP_CMIDS=2649,2650
#   DATA_CMIDS=2653
#   HASH_SALT=any_long_random_string

import os, sys, time, shutil, hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# ----------------- Paths & simple logger -----------------

ROOT = Path(__file__).parent.resolve()
OUT = ROOT / "output"
EXPORTS = OUT / "exports"
LOGS = OUT / "logs"

def log(msg: str):
    """Console + file log with timestamp."""
    stamp = datetime.now().isoformat(timespec="seconds")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def reset_output():
    """Delete and recreate output/ tree so each run is fresh."""
    if OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

def write_csv(df: pd.DataFrame, path: Path):
    EXPORTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")

# ----------------- Helpers -----------------

def parse_ids(s: Optional[str]) -> List[int]:
    if not s:
        return []
    return [int(x.strip()) for x in s.split(",") if x.strip().isdigit()]

def to_iso(ts: Optional[int]) -> Optional[str]:
    if not ts or int(ts) == 0:
        return None
    return datetime.fromtimestamp(int(ts)).isoformat(sep=" ", timespec="seconds")

def duration_secs(start: Optional[int], finish: Optional[int]) -> Optional[int]:
    try:
        if not start or not finish:
            return None
        return int(finish) - int(start)
    except Exception:
        return None

def pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    try:
        if a is None or b in (None, 0, 0.0):
            return None
        return float(a) / float(b) * 100.0
    except Exception:
        return None

def anon_user(userid: Optional[int], salt: str) -> Optional[str]:
    if userid is None:
        return None
    h = hashlib.sha256((salt + str(userid)).encode("utf-8")).hexdigest()
    return f"u_{h[:12]}"

# ----------------- REST API client with retries -----------------

# ----------------- REST API client with retries + array flatten -----------------

class API:
    """Thin Moodle REST client with robust retries, clear errors, and correct array encoding."""
    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.token = token
        self.endpoint = f"{self.base}/webservice/rest/server.php"
        self.headers = {"User-Agent": "Course1516-Exporter/1.0"}

    def _flatten_params(self, params: dict) -> dict:
        """
        Moodle expects arrays/dicts as:
          key[0]=..., key[1]=...
          key[sub]=...
        This flattens nested lists/dicts into that format.
        """
        flat = {}

        def _walk(prefix, value):
            if isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    _walk(f"{prefix}[{i}]", v)
            elif isinstance(value, dict):
                for k, v in value.items():
                    _walk(f"{prefix}[{k}]", v)
            else:
                flat[prefix] = value

        for k, v in params.items():
            _walk(k, v)
        return flat

    def call(self, fn: str, **params):
        # base payload
        base_payload = {
            "wstoken": self.token,
            "wsfunction": fn,
            "moodlewsrestformat": "json",
        }
        # flatten any arrays/dicts (e.g., courseids=[1516] → courseids[0]=1516)
        payload = {**base_payload, **self._flatten_params(params)}

        backoff = 2  # seconds
        last_error = None
        for attempt in range(1, 6):
            try:
                resp = requests.post(self.endpoint, data=payload, headers=self.headers, timeout=60)
                if resp.status_code in self.RETRY_STATUSES:
                    last_error = f"{resp.status_code} {resp.reason}"
                    log(f"[api] {fn} → transient {last_error} (attempt {attempt}); retrying after {backoff}s")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue

                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    snippet = (resp.text or "")[:300].replace("\n", " ")
                    raise RuntimeError(f"{fn} returned non-JSON (status {resp.status_code}): {snippet}")

                if isinstance(data, dict) and data.get("exception"):
                    raise RuntimeError(f"{fn} error: {data}")

                return data

            except requests.RequestException as e:
                last_error = str(e)
                log(f"[api] {fn} → network error '{last_error}' (attempt {attempt}); retrying after {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        raise RuntimeError(f"{fn} failed after retries: {last_error}")

# ----------------- Discovery -----------------

def discover_modules(api: API, course_id: int) -> Dict[int, Dict[str, Any]]:
    """Return {cmid: {'modname','instance','name'}} using core_course_get_contents."""
    modules: Dict[int, Dict[str, Any]] = {}
    sections = api.call("core_course_get_contents", courseid=course_id)
    for sec in sections:
        for m in sec.get("modules", []):
            cmid = m.get("id")
            if cmid:
                modules[int(cmid)] = {
                    "modname": m.get("modname"),
                    "instance": m.get("instance"),
                    "name": m.get("name"),
                }
    return modules

def get_enrolled_user_ids(api: API, course_id: int) -> List[int]:
    users = api.call("core_enrol_get_enrolled_users", courseid=course_id)
    return [int(u["id"]) for u in users]

# ----------------- Exporters -----------------

def export_quizzes(api: API, course_id: int, cmids: List[int], cmmap: Dict[int, Dict[str, Any]], salt: str):
    if not cmids:
        log("[quiz] None configured — skipping.")
        return

    # Robust fetch: some Moodles return {"quizzes":[...]}, others return a plain list
    resp = api.call("mod_quiz_get_quizzes_by_courses", courseids=[course_id])
    if isinstance(resp, dict):
        quizzes = resp.get("quizzes", []) or []
    elif isinstance(resp, list):
        quizzes = resp
    else:
        quizzes = []

    # quizid -> quiz config (sumgrades, grade, timeopen, timeclose, timelimit, attempts, name, ...)
    qcfg: Dict[int, Dict[str, Any]] = {}
    for q in quizzes:
        try:
            qcfg[int(q.get("id"))] = q
        except Exception:
            continue

    enrolled = get_enrolled_user_ids(api, course_id)

    for cmid in cmids:
        meta = cmmap.get(cmid, {})
        if meta.get("modname") != "quiz":
            log(f"[quiz] CMID {cmid} is not a quiz (found {meta.get('modname')}); skipping")
            continue

        quizid = int(meta.get("instance"))
        qc = qcfg.get(quizid, {})  # may be empty if API didn’t return it
        qname = qc.get("name") or meta.get("name")

        rows: List[Dict[str, Any]] = []
        log(f"[quiz] Exporting '{qname}' (quizid={quizid}, cmid={cmid})")

        for uid in tqdm(enrolled, desc=f"quiz {quizid} users"):
            # attempts may be a list OR a dict with {"attempts":[...]}
            try:
                attempts = api.call("mod_quiz_get_user_attempts", quizid=quizid, userid=uid, status="all")
                if isinstance(attempts, dict) and "attempts" in attempts:
                    attempts = attempts["attempts"]
            except Exception as e:
                log(f"   ! attempts failed for user {uid}: {e}")
                continue

            for a in attempts or []:
                started = a.get("timestart") or a.get("timeStart")
                finished = a.get("timefinish") or a.get("timeFinish")
                dur_s = duration_secs(started, finished)
                dur_m = (dur_s / 60.0) if dur_s is not None else None

                raw_max    = qc.get("sumgrades")
                scaled_max = qc.get("grade")
                raw_score  = a.get("sumgrades")
                score_pct  = pct(raw_score, raw_max)

                if (raw_score is not None and raw_max not in (None, 0) and scaled_max):
                    try:
                        scaled_grade = float(raw_score) / float(raw_max) * float(scaled_max)
                    except Exception:
                        scaled_grade = None
                else:
                    scaled_grade = None

                rows.append({
                    "course_id": course_id,
                    "cmid": cmid,
                    "quizid": quizid,
                    "quiz_name": qname,
                    "anon_user": anon_user(uid, salt),
                    "attemptid": a.get("id"),
                    "attempt_no": a.get("attempt"),
                    "state": a.get("state"),
                    "timestart": to_iso(started),
                    "timefinish": to_iso(finished),
                    "started_unix": started,
                    "finished_unix": finished,
                    "duration_seconds": dur_s,
                    "duration_minutes": round(dur_m, 3) if dur_m is not None else None,
                    "raw_score": raw_score,
                    "raw_max": raw_max,
                    "scaled_max": scaled_max,
                    "score_pct": round(score_pct, 3) if score_pct is not None else None,
                    "scaled_grade": round(scaled_grade, 3) if scaled_grade is not None else None,
                    "timeopen": qc.get("timeopen"),
                    "timeclose": qc.get("timeclose"),
                    "timelimit_seconds": qc.get("timelimit"),
                    "attempts_allowed": qc.get("attempts"),
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            fp = EXPORTS / f"quiz_{cmid}.csv"
            write_csv(df, fp)
            log(f"[quiz] Wrote {len(df)} rows → {fp.name}")
        else:
            log(f"[quiz] No rows for cmid {cmid}.")

        df = pd.DataFrame(rows)
        if not df.empty:
            fp = EXPORTS / f"quiz_{cmid}.csv"
            write_csv(df, fp)
            log(f"[quiz] Wrote {len(df)} rows → {fp.name}")
        else:
            log(f"[quiz] No rows for cmid {cmid}.")

def export_assignments(api: API, course_id: int, cmids: List[int], cmmap: Dict[int, Dict[str, Any]], salt: str):
    if not cmids:
        log("[assign] None configured — skipping.")
        return
    assigns_raw = api.call("mod_assign_get_assignments", courseids=[course_id])
    assigns = {}
    for c in assigns_raw.get("courses", []):
        for a in c.get("assignments", []):
            assigns[int(a["id"])] = a
    # grades map
    graw = api.call("mod_assign_get_grades", assignmentids=list(assigns.keys()) or [])
    grades_map = {}
    for g in graw.get("assignments", []):
        aid = int(g["assignmentid"])
        for gr in g.get("grades", []):
            try:
                grades_map[(aid, int(gr["userid"]))] = gr.get("grade")
            except Exception:
                pass

    for cmid in cmids:
        meta = cmmap.get(cmid, {})
        if meta.get("modname") != "assign":
            log(f"[assign] CMID {cmid} is not an assignment (found {meta.get('modname')}); skipping")
            continue
        aid = int(meta["instance"])
        cfg = assigns.get(aid, {})
        open_ts, due_ts, cut_ts = cfg.get("allowsubmissionsfromdate"), cfg.get("duedate"), cfg.get("cutoffdate")

        subs_all = api.call("mod_assign_get_submissions", assignmentids=[aid])
        rows = []
        for a in subs_all.get("assignments", []):
            for sub in a.get("submissions", []):
                try:
                    uid = int(sub["userid"])
                except Exception:
                    uid = None
                submitted = sub.get("timemodified") or sub.get("timecreated")
                tts = (int(submitted) - int(open_ts)) if (submitted and open_ts) else None
                rows.append({
                    "course_id": course_id, "cmid": cmid,
                    "assignid": aid, "assign_name": meta.get("name"),
                    "anon_user": anon_user(uid, salt) if uid is not None else None,
                    "submissionid": sub.get("id"),
                    "status": sub.get("status"),
                    "submitted_unix": submitted,
                    "submitted_at": to_iso(submitted),
                    "allowsubmissionsfromdate": open_ts,
                    "duedate": due_ts, "cutoffdate": cut_ts,
                    "time_to_submit_seconds": tts,
                    "time_to_submit_hours": round(tts/3600.0, 3) if tts is not None else None,
                    "grade": grades_map.get((aid, uid)) if uid is not None else None
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            fp = EXPORTS / f"assign_{cmid}.csv"
            write_csv(df, fp)
            log(f"[assign] Wrote {len(df)} rows → {fp.name}")
        else:
            log(f"[assign] No rows for cmid {cmid}.")

def export_h5p(api: API, course_id: int, cmids: List[int], cmmap: Dict[int, Dict[str, Any]], salt: str):
    if not cmids:
        log("[h5p] None configured — skipping.")
        return

    # Separate requested CMIDs by module type
    h5p_cmids_only = [c for c in cmids if cmmap.get(c, {}).get("modname") == "h5pactivity"]
    hvp_cmids      = [c for c in cmids if cmmap.get(c, {}).get("modname") == "hvp"]

    if hvp_cmids:
        # Old plugin “mod_hvp” (H5P by Joubel) usually doesn’t expose the same WS for attempts/results.
        log(f"[h5p] Skipping legacy 'mod_hvp' CMIDs (not supported by mod_h5pactivity web services): {hvp_cmids}")

    if not h5p_cmids_only:
        log("[h5p] No 'H5P activity' (mod_h5pactivity) CMIDs to export — skipping.")
        return

    # Map instance id -> cmid for the *h5pactivity* modules only
    inst2cm = {}
    for cmid in h5p_cmids_only:
        meta = cmmap.get(cmid, {})
        inst = meta.get("instance")
        if inst is not None:
            inst2cm[int(inst)] = cmid

    # Get activities (handle dict or list)
    try:
        resp = api.call("mod_h5pactivity_get_h5pactivities_by_courses", courseids=[course_id])
    except Exception as e:
        log(f"[h5p] H5P endpoints not available: {e}")
        return

    if isinstance(resp, dict):
        activities = resp.get("h5pactivities") or resp.get("activities") or []
    elif isinstance(resp, list):
        activities = resp
    else:
        activities = []

    for h in activities:
        try:
            hid = int(h.get("id"))
        except Exception:
            continue

        cmid = inst2cm.get(hid)
        if not cmid:
            # This H5P activity isn’t in the requested CMID list
            continue

        hname = h.get("name")
        log(f"[h5p] Exporting '{hname}' (h5pactivityid={hid}, cmid={cmid})")

        # Attempts (shape-proof)
        attempts_resp = {}
        attempts = []
        try:
            attempts_resp = api.call("mod_h5pactivity_get_user_attempts", h5pactivityid=hid)
            if isinstance(attempts_resp, dict) and "attempts" in attempts_resp:
                attempts = attempts_resp["attempts"] or []
            elif isinstance(attempts_resp, list):
                attempts = attempts_resp
            else:
                attempts = []
        except Exception as e:
            log(f"   ! attempts fetch failed: {e}")
            attempts = []

        # Results (shape-proof)
        results = []
        try:
            res = api.call("mod_h5pactivity_get_results", h5pactivityid=hid)
            if isinstance(res, dict) and "results" in res:
                results = res["results"] or []
            elif isinstance(res, list):
                results = res
            else:
                results = []
        except Exception:
            results = []

        # Map attemptid -> result
        rmap = {}
        for r in results:
            rid = r.get("attemptid") or r.get("id")
            rmap[rid] = r

        # Build rows
        from math import isfinite
        rows = []
        for a in attempts:
            uid      = a.get("userid")
            started  = a.get("timecreated") or a.get("timestarted")
            finished = a.get("timemodified") or a.get("timefinished")
            rid      = a.get("id")
            rr       = rmap.get(rid, {}) if rid is not None else {}

            score    = rr.get("score")
            maxscore = rr.get("maxscore")

            rows.append({
                "course_id": course_id,
                "cmid": cmid,
                "h5pactivityid": hid,
                "h5p_name": hname,
                "anon_user": anon_user(uid, salt) if uid is not None else None,
                "attemptid": rid,
                "timestart": to_iso(started),
                "timefinish": to_iso(finished),
                "started_unix": started,
                "finished_unix": finished,
                "duration_seconds": duration_secs(started, finished),
                "score": score,
                "maxscore": maxscore,
                "score_pct": pct(score, maxscore) if (score is not None and maxscore) else None
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            fp = EXPORTS / f"h5p_{cmid}.csv"
            write_csv(df, fp)
            log(f"[h5p] Wrote {len(df)} rows → {fp.name}")
        else:
            log(f"[h5p] No rows for cmid {cmid}.")

        df = pd.DataFrame(rows)
        if not df.empty:
            fp = EXPORTS / f"h5p_{cmid}.csv"
            write_csv(df, fp)
            log(f"[h5p] Wrote {len(df)} rows → {fp.name}")
        else:
            log(f"[h5p] No rows for cmid {cmid}.")

def export_database(api: API, course_id: int, cmids: List[int], cmmap: Dict[int, Dict[str, Any]], salt: str):
    if not cmids:
        log("[data] None configured — skipping.")
        return

    # Only CMIDs that are actually Database activities (mod_data)
    data_cmids_only = [c for c in cmids if cmmap.get(c, {}).get("modname") == "data"]
    if not data_cmids_only:
        log("[data] No 'Database' (mod_data) CMIDs to export — skipping.")
        return

    # Map instance id -> cmid for the requested Database activities
    inst2cm = {}
    for cmid in data_cmids_only:
        meta = cmmap.get(cmid, {})
        inst = meta.get("instance")
        if inst is not None:
            inst2cm[int(inst)] = cmid

    # --- Fetch databases (handle dict or list shapes) ---
    try:
        resp = api.call("mod_data_get_databases_by_courses", courseids=[course_id])
    except Exception as e:
        log(f"[data] mod_data_get_databases_by_courses not available: {e}")
        return

    if isinstance(resp, dict):
        if "databases" in resp and isinstance(resp["databases"], list):
            databases = resp["databases"]
        elif "courses" in resp and isinstance(resp["courses"], list):
            # Some versions nest per-course
            databases = []
            for c in resp["courses"]:
                dbs = c.get("databases") or c.get("instances") or []
                if isinstance(dbs, list):
                    databases.extend(dbs)
        else:
            # Fallback: collect any list-of-dicts values
            databases = []
            for v in resp.values():
                if isinstance(v, list):
                    databases.extend([x for x in v if isinstance(x, dict) and "id" in x])
    elif isinstance(resp, list):
        databases = resp
    else:
        databases = []

    if not databases:
        log("[data] No databases returned by the API — skipping.")
        return

    for d in databases:
        try:
            did = int(d.get("id"))
        except Exception:
            continue

        cmid = inst2cm.get(did)
        if not cmid:
            # This database instance isn't one of the requested CMIDs
            continue

        dname = d.get("name")
        log(f"[data] Exporting '{dname}' (databaseid={did}, cmid={cmid})")

        # Entries (shape-proof)
        try:
            eresp = api.call("mod_data_get_entries", databaseid=did)
            if isinstance(eresp, dict) and "entries" in eresp:
                entries = eresp["entries"] or []
            elif isinstance(eresp, list):
                entries = eresp
            else:
                entries = []
        except Exception as e:
            log(f"[data] entries failed: {e}")
            entries = []

        rows: List[Dict[str, Any]] = []
        for e in entries:
            uid = e.get("userid")
            created = e.get("timecreated")
            rows.append({
                "course_id": course_id,
                "cmid": cmid,
                "databaseid": did,
                "database_name": dname,
                "entryid": e.get("id"),
                "anon_user": anon_user(uid, salt) if uid is not None else None,
                "created_unix": created,
                "created_at": to_iso(created),
                "approved": e.get("approved"),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            fp = EXPORTS / f"data_{cmid}.csv"
            write_csv(df, fp)
            log(f"[data] Wrote {len(df)} rows → {fp.name}")
        else:
            log(f"[data] No rows for cmid {cmid}.")


def export_forums(api: API, course_id: int, cmids: List[int], cmmap: Dict[int, Dict[str, Any]], salt: str):
    """Optional: requires forum WS functions in your external service."""
    if not cmids:
        log("[forum] None configured — skipping.")
        return
    inst2cm = {meta["instance"]: cmid for cmid, meta in cmmap.items() if meta.get("modname") == "forum"}
    try:
        forums = api.call("mod_forum_get_forums_by_courses", courseids=[course_id])
    except Exception as e:
        log(f"[forum] Forum endpoints not available: {e}")
        return

    for f in forums:
        fid = int(f.get("id"))
        cmid = inst2cm.get(fid)
        if cmid not in cmids:
            continue
        fname = f.get("name")
        log(f"[forum] Exporting '{fname}' (forumid={fid}, cmid={cmid})")

        # Discussions
        try:
            discussions = api.call("mod_forum_get_forum_discussions", forumid=fid)
            if isinstance(discussions, dict) and "discussions" in discussions:
                discussions = discussions["discussions"]
        except Exception:
            # fallback to paginated
            try:
                d2 = api.call("mod_forum_get_forum_discussions_paginated", forumid=fid, page=0, perpage=1000)
                discussions = d2.get("discussions", [])
            except Exception as e2:
                log(f"   ! could not fetch discussions: {e2}")
                continue

        posts_rows: List[Dict[str, Any]] = []
        for d in discussions or []:
            did = d.get("discussion") or d.get("id")
            try:
                posts = api.call("mod_forum_get_discussion_posts", discussionid=did)
                if isinstance(posts, dict) and "posts" in posts:
                    posts = posts["posts"]
            except Exception as e:
                log(f"   ! posts failed for discussion {did}: {e}")
                continue
            for p in posts or []:
                uid = p.get("userid") or (p.get("author") or {}).get("id")
                created = p.get("timecreated")
                posts_rows.append({
                    "course_id": course_id,
                    "cmid": cmid,
                    "forumid": fid,
                    "forum_name": fname,
                    "discussionid": did,
                    "postid": p.get("id"),
                    "parentid": p.get("parent"),
                    "anon_user": anon_user(uid, salt) if uid is not None else None,
                    "created_unix": created,
                    "created_at": to_iso(created),
                    "subject": p.get("subject"),
                })

        df = pd.DataFrame(posts_rows)
        if not df.empty:
            fp = EXPORTS / f"forum_{cmid}_posts.csv"
            write_csv(df, fp)
            log(f"[forum] Wrote {len(df)} rows → {fp.name}")
            # simple summary
            summary = df.groupby("anon_user", dropna=True)["postid"].count().reset_index(name="posts")
            write_csv(summary, EXPORTS / f"forum_{cmid}_summary.csv")
        else:
            log(f"[forum] No posts for cmid {cmid}.")

# ----------------- Main -----------------

def main():
    load_dotenv()
    base = os.getenv("MOODLE_BASE_URL")
    token = os.getenv("MOODLE_WSTOKEN")
    salt = os.getenv("HASH_SALT", "anonymous")
    try:
        course_id = int(os.getenv("COURSE_ID", "0"))
    except ValueError:
        print("COURSE_ID must be an integer.", file=sys.stderr); sys.exit(1)

    quiz_cmids   = parse_ids(os.getenv("QUIZ_CMIDS", ""))
    assign_cmids = parse_ids(os.getenv("ASSIGN_CMIDS", ""))
    forum_cmids  = parse_ids(os.getenv("FORUM_CMIDS", ""))
    h5p_cmids    = parse_ids(os.getenv("HVP_CMIDS", ""))
    data_cmids   = parse_ids(os.getenv("DATA_CMIDS", ""))

    if not base or not token or not course_id:
        print("Please set MOODLE_BASE_URL, MOODLE_WSTOKEN, COURSE_ID in .env", file=sys.stderr); sys.exit(1)

    reset_output()
    log("Export started.")

    api = API(base, token)
    # quick token sanity:
    site = api.call("core_webservice_get_site_info")
    log(f"Connected to {site.get('sitename')} as user id {site.get('userid')}")

    cmmap = discover_modules(api, course_id)
    log(f"Discovered {len(cmmap)} modules in course {course_id}.")

    # Do exports
    export_quizzes(api, course_id, quiz_cmids, cmmap, salt)
    export_assignments(api, course_id, assign_cmids, cmmap, salt)
    export_h5p(api, course_id, h5p_cmids, cmmap, salt)
    export_database(api, course_id, data_cmids, cmmap, salt)
    export_forums(api, course_id, forum_cmids, cmmap, salt)

    log("Export done. Check the 'output/exports' folder.")

if __name__ == "__main__":
    main()
