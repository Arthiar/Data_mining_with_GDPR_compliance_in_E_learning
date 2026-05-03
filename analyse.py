# analyse.py — Organise outputs per activity type, generate charts, write summaries.
# Run AFTER export.py (or after generate_demo_data.py for demonstration purposes).
# It will:
#   - Move CSVs from output/exports/ into the right sub-folder
#   - Create charts beside each CSV and comparison charts in /summary
#   - Write per-type summaries and a global overview
#   - Delete output/exports when done

from pathlib import Path
import shutil
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

ROOT = Path(__file__).parent.resolve()
OUT  = ROOT / "output"
EXPORTS = OUT / "exports"

QUIZ_DIR    = OUT / "quizzes"
ASSIGN_DIR  = OUT / "assignments"
H5P_DIR     = OUT / "h5p"
FORUM_DIR   = OUT / "forums"
DATA_DIR    = OUT / "databases"
SUMMARY_DIR = OUT / "summary"

for d in [QUIZ_DIR, ASSIGN_DIR, H5P_DIR, FORUM_DIR, DATA_DIR, SUMMARY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Consistent chart style
plt.rcParams.update({
    "figure.facecolor":   "white",
    "axes.facecolor":     "#F4F7FB",
    "axes.grid":          True,
    "grid.color":         "white",
    "grid.linewidth":     1.3,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.edgecolor":     "#CCCCCC",
    "font.family":        "sans-serif",
    "font.size":          11,
    "axes.labelsize":     12,
    "axes.titlesize":     13,
    "axes.titleweight":   "bold",
    "xtick.labelsize":    10,
    "ytick.labelsize":    10,
    "legend.fontsize":    10,
    "legend.framealpha":  0.9,
})

BLUE   = "#2E86AB"
GREEN  = "#44BBA4"
RED    = "#E84855"
ORANGE = "#F5A623"
PURPLE = "#7B2D8B"

PASS_THRESHOLD = 50.0


def move_file(src, dst_dir):
    dst = dst_dir / src.name
    if dst.exists():
        dst.unlink()
    try:
        shutil.move(str(src), str(dst))
    except Exception:
        shutil.copy2(src, dst)
        try:
            src.unlink()
        except Exception:
            pass
    return dst


def wrap_text(text, width=48):
    return "\n".join(textwrap.wrap(str(text), width))


def percent(n, d):
    try:
        n, d = float(n), float(d)
        return 100.0 * n / d if d else None
    except Exception:
        return None


def get_numeric(df, col):
    if col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce").dropna()


def add_caption(fig, text):
    fig.text(
        0.5, 0.005,
        textwrap.fill(text, 110),
        ha="center", va="bottom",
        fontsize=8.5, style="italic", color="#555555",
        transform=fig.transFigure,
    )


# Chart functions

def save_histogram(series, title, xlabel, outpath, pass_line=False, note=""):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return False

    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.hist(s, bins=10, color=BLUE, alpha=0.85, edgecolor="white", linewidth=0.8)

    mean_val   = s.mean()
    median_val = s.median()
    ax.axvline(mean_val,   color=RED,    linewidth=2, linestyle="--",
               label=f"Mean {mean_val:.1f}")
    ax.axvline(median_val, color=ORANGE, linewidth=2, linestyle=":",
               label=f"Median {median_val:.1f}")

    if pass_line and s.max() <= 101:
        ax.axvline(PASS_THRESHOLD, color=GREEN, linewidth=2, linestyle="-.",
                   label=f"Pass threshold ({PASS_THRESHOLD:.0f}%)")
        n_pass = int((s >= PASS_THRESHOLD).sum())
        pct    = 100.0 * n_pass / len(s)
        y_top  = ax.get_ylim()[1]
        ax.text(PASS_THRESHOLD + (s.max() - s.min()) * 0.03,
                y_top * 0.88,
                f"Pass rate\n{pct:.1f}%  ({n_pass}/{len(s)})",
                fontsize=9.5, color=GREEN, fontweight="bold")

    ax.set_title(wrap_text(title))
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Number of submissions")
    ax.legend()
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    if note:
        add_caption(fig, note)
    fig.tight_layout(rect=[0, 0.05 if note else 0, 1, 1])
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def save_scatter(x, y, title, xlabel, ylabel, outpath, note=""):
    x = pd.to_numeric(x, errors="coerce")
    y = pd.to_numeric(y, errors="coerce")
    df = pd.DataFrame({"x": x, "y": y}).dropna()
    if df.empty:
        return False

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(df["x"], df["y"], color=BLUE, alpha=0.75,
               edgecolors="white", linewidths=0.5, s=65, zorder=3)

    if len(df) >= 3:
        coeffs = np.polyfit(df["x"], df["y"], 1)
        poly   = np.poly1d(coeffs)
        x_ln   = np.linspace(df["x"].min(), df["x"].max(), 200)
        corr_r = float(df["x"].corr(df["y"]))
        ax.plot(x_ln, poly(x_ln), color=GREEN, linewidth=2, linestyle="--",
                label=f"Trend  r = {corr_r:+.2f}")
        ax.legend()

        strength  = "strong" if abs(corr_r) >= 0.6 else "moderate" if abs(corr_r) >= 0.3 else "weak"
        direction = "positive" if corr_r >= 0 else "negative"
        ax.set_xlabel(f"{xlabel}  -  {strength} {direction} correlation")
    else:
        ax.set_xlabel(xlabel)

    ax.set_title(wrap_text(title))
    ax.set_ylabel(ylabel)

    if note:
        add_caption(fig, note)
    fig.tight_layout(rect=[0, 0.05 if note else 0, 1, 1])
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def save_bar_chart(counts, title, xlabel, ylabel, outpath, note=""):
    if counts is None or counts.empty:
        return False

    horizontal = len(counts) > 8
    fig_h = max(5, len(counts) * 0.45) if horizontal else 5.4
    fig, ax = plt.subplots(figsize=(10, fig_h))

    labels = [str(l)[:25] for l in counts.index]
    values = counts.values.astype(float)

    if horizontal:
        bars = ax.barh(labels, values, color=BLUE, alpha=0.85,
                       edgecolor="white", linewidth=0.8)
        for bar in bars:
            w = bar.get_width()
            ax.text(w + max(values) * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(w)}", va="center", fontsize=9, color="#333333")
        ax.set_xlabel(ylabel)
        ax.set_ylabel(xlabel)
        ax.invert_yaxis()
    else:
        bars = ax.bar(labels, values, color=BLUE, alpha=0.85,
                      edgecolor="white", linewidth=0.8)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=30, ha="right")
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2,
                    h + max(values) * 0.01, f"{int(h)}",
                    ha="center", va="bottom", fontsize=9, color="#333333")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

    ax.set_title(wrap_text(title))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    if note:
        add_caption(fig, note)
    fig.tight_layout(rect=[0, 0.05 if note else 0, 1, 1])
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def save_pass_fail_bar(n_pass, n_fail, title, outpath, note=""):
    total = n_pass + n_fail
    if total == 0:
        return False

    pct_pass = 100.0 * n_pass / total
    pct_fail = 100.0 * n_fail / total

    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.barh([""], [pct_pass], color=GREEN, edgecolor="white",
            label=f"Pass  {pct_pass:.1f}%  (n={n_pass})")
    ax.barh([""], [pct_fail], left=[pct_pass], color=RED, edgecolor="white",
            label=f"Fail  {pct_fail:.1f}%  (n={n_fail})")

    ax.set_xlim(0, 100)
    ax.set_xlabel("Percentage of attempts (%)")
    ax.set_title(wrap_text(title))
    ax.legend(loc="lower right")
    ax.grid(False)

    if pct_pass > 8:
        ax.text(pct_pass / 2, 0, f"{n_pass}", ha="center", va="center",
                fontsize=12, fontweight="bold", color="white")
    if pct_fail > 8:
        ax.text(pct_pass + pct_fail / 2, 0, f"{n_fail}", ha="center", va="center",
                fontsize=12, fontweight="bold", color="white")

    if note:
        add_caption(fig, note)
    fig.tight_layout(rect=[0, 0.06 if note else 0, 1, 1])
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def save_comparison_chart(names, values, title, ylabel, outpath, color=BLUE, ref_line=None, note=""):
    if names is None or values is None or len(names) == 0 or len(values) == 0:
        return False

    paired = [(n, v) for n, v in zip(names, values) if v is not None]
    if not paired:
        return False

    names_f, values_f = zip(*paired)
    labels = [wrap_text(str(n), 20) for n in names_f]

    fig, ax = plt.subplots(figsize=(max(7, len(names_f) * 1.8), 5.4))
    bars = ax.bar(range(len(labels)), values_f, color=color, alpha=0.85,
                  edgecolor="white", linewidth=0.8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha="right")

    for bar, v in zip(bars, values_f):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values_f) * 0.01,
                f"{v:.1f}", ha="center", va="bottom", fontsize=10,
                fontweight="bold", color="#333333")

    if ref_line is not None:
        ax.axhline(ref_line, color=ORANGE, linewidth=1.8, linestyle="--",
                   label=f"Reference line: {ref_line}")
        ax.legend()

    ax.set_title(wrap_text(title))
    ax.set_ylabel(ylabel)

    if note:
        add_caption(fig, note)
    fig.tight_layout(rect=[0, 0.06 if note else 0, 1, 1])
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


# Analysers

def analyze_quizzes():
    # Move any new exports into the quiz folder first
    for csv in sorted(EXPORTS.glob("quiz_*.csv")):
        move_file(csv, QUIZ_DIR)

    summaries = []
    for csv in sorted(QUIZ_DIR.glob("quiz_*.csv")):
        df   = pd.read_csv(csv)
        cmid = csv.stem.split("_", 1)[1] if "_" in csv.stem else "unknown"

        if "quiz_name" in df.columns and not df["quiz_name"].dropna().empty:
            quiz_name = df["quiz_name"].dropna().iloc[0]
        else:
            quiz_name = f"quiz_{cmid}"

        score_s = get_numeric(df, "score_pct")
        dur_s   = get_numeric(df, "duration_minutes")

        save_histogram(
            score_s, f"{quiz_name}\nScore Distribution", "Score (%)",
            QUIZ_DIR / f"{csv.stem}_score_hist.png",
            pass_line=True,
            note=f"Histogram of scores (%) across all {len(score_s)} attempts. "
                 "Each bar shows how many students fell in that score range. "
                 "The dashed red line is the mean; the dotted orange line is the median; "
                 "the green line marks the 50% passing threshold.")

        if not score_s.empty:
            n_pass = int((score_s >= PASS_THRESHOLD).sum())
            n_fail = len(score_s) - n_pass
            save_pass_fail_bar(
                n_pass, n_fail,
                f"{quiz_name}\nPass / Fail Split",
                QUIZ_DIR / f"{csv.stem}_pass_fail.png",
                note=f"Out of {n_pass + n_fail} total attempts, {n_pass} scored at or above 50% (pass) "
                     f"and {n_fail} scored below (fail). Each count includes retake attempts.")

        save_histogram(
            dur_s, f"{quiz_name}\nTime-on-Task Distribution", "Duration (min)",
            QUIZ_DIR / f"{csv.stem}_duration_hist.png",
            note="Distribution of how long students took to complete the quiz (in minutes). "
                 "A wide spread indicates students worked at different paces; "
                 "a narrow peak suggests most students finished in a similar time frame.")

        save_scatter(
            df.get("duration_minutes"), df.get("score_pct"),
            f"{quiz_name}\nTime Spent vs Score Achieved",
            "Duration (min)", "Score (%)",
            QUIZ_DIR / f"{csv.stem}_time_vs_score.png",
            note="Each dot is one attempt. The dashed trend line shows whether spending more time is "
                 "associated with a higher or lower score. The correlation coefficient r ranges from "
                 "-1 (perfect negative) to +1 (perfect positive); values near 0 mean no clear relationship.")

        unique_users = df["anon_user"].nunique(dropna=True) if "anon_user" in df.columns else None

        corr = None
        if "duration_minutes" in df.columns and "score_pct" in df.columns:
            tmp = df[["duration_minutes", "score_pct"]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(tmp) >= 3:
                corr = float(tmp["duration_minutes"].corr(tmp["score_pct"]))

        n_pass_r  = int((score_s >= PASS_THRESHOLD).sum()) if not score_s.empty else None
        pass_rate = percent(n_pass_r, len(score_s)) if n_pass_r is not None else None

        summaries.append({
            "cmid": cmid, "quiz_name": quiz_name,
            "attempts": len(df), "unique_users": unique_users,
            "mean_score_pct":         round(score_s.mean(),          3) if not score_s.empty else None,
            "median_score_pct":       round(score_s.median(),        3) if not score_s.empty else None,
            "p10_score_pct":          round(score_s.quantile(0.10),  3) if not score_s.empty else None,
            "p90_score_pct":          round(score_s.quantile(0.90),  3) if not score_s.empty else None,
            "pass_rate_pct":          round(pass_rate, 2)               if pass_rate is not None else None,
            "mean_duration_min":      round(dur_s.mean(),            3) if not dur_s.empty else None,
            "corr_duration_vs_score": round(corr,                    3) if corr is not None else None,
        })

    if summaries:
        df_sum = pd.DataFrame(summaries)
        df_sum.to_csv(SUMMARY_DIR / "quizzes_summary.csv", index=False, encoding="utf-8-sig")

        save_comparison_chart(
            df_sum["quiz_name"], df_sum["mean_score_pct"],
            "Mean Score (%) - Comparison Across All Quizzes", "Mean Score (%)",
            SUMMARY_DIR / "quizzes_mean_score_comparison.png",
            color=BLUE, ref_line=PASS_THRESHOLD,
            note="Each bar is one quiz. The orange reference line marks the passing threshold (50%). "
                 "Bars above this line indicate the class average passed that quiz.")

        save_comparison_chart(
            df_sum["quiz_name"], df_sum["pass_rate_pct"],
            "Pass Rate (%) - Comparison Across All Quizzes", "Pass Rate (%)",
            SUMMARY_DIR / "quizzes_pass_rate_comparison.png",
            color=GREEN, ref_line=50.0,
            note="Percentage of attempts that scored at or above 50%. "
                 "A pass rate above 50% means more than half the class passed the quiz.")

        if df_sum["mean_duration_min"].notna().any():
            save_comparison_chart(
                df_sum["quiz_name"], df_sum["mean_duration_min"],
                "Mean Time-on-Task (min) - All Quizzes", "Minutes",
                SUMMARY_DIR / "quizzes_duration_comparison.png", color=ORANGE,
                note="Average time students spent on each quiz (from starting to submitting). "
                     "Longer times may indicate higher difficulty or more careful review of answers.")


def analyze_assignments():
    # Move any new exports into the assignments folder first
    for csv in sorted(EXPORTS.glob("assign_*.csv")):
        move_file(csv, ASSIGN_DIR)

    summaries = []
    for csv in sorted(ASSIGN_DIR.glob("assign_*.csv")):
        df    = pd.read_csv(csv)
        cmid  = csv.stem.split("_", 1)[1] if "_" in csv.stem else "unknown"

        if "assign_name" in df.columns and not df["assign_name"].dropna().empty:
            aname = df["assign_name"].dropna().iloc[0]
        else:
            aname = f"assign_{cmid}"

        grade_s = get_numeric(df, "grade")
        grade_s = grade_s[grade_s >= 0]   # remove -1 (Moodle "not graded" sentinel)
        time_s  = get_numeric(df, "time_to_submit_hours")
        n_total = len(df)

        if not grade_s.empty:
            save_histogram(
                grade_s, f"{aname}\nGrade Distribution", "Grade (0-100)",
                ASSIGN_DIR / f"{csv.stem}_grade_hist.png",
                note=f"Grade distribution for {n_total} student submissions. "
                     "The red dashed line shows the class mean grade and the orange dotted line the median. "
                     "A left-skewed distribution (tail to the left) indicates most students scored well.")

        if not time_s.empty:
            save_histogram(
                time_s, f"{aname}\nSubmission Timing", "Hours since assignment opened",
                ASSIGN_DIR / f"{csv.stem}_submit_timing_hist.png",
                note="How many hours after the assignment opened each student submitted their work. "
                     "A large cluster on the right edge suggests students tend to submit close to (or after) "
                     "the deadline - useful for planning reminder communications.")

        ontime_rate = None
        n_ontime, n_late = 0, 0
        if "duedate" in df.columns and "submitted_unix" in df.columns:
            duedate   = pd.to_numeric(df["duedate"],        errors="coerce")
            submitted = pd.to_numeric(df["submitted_unix"], errors="coerce")
            mask = (~duedate.isna()) & (~submitted.isna()) & (duedate > 0)
            if mask.any():
                n_ontime    = int((submitted[mask] <= duedate[mask]).sum())
                n_late      = int(mask.sum()) - n_ontime
                ontime_rate = percent(n_ontime, int(mask.sum()))

        unique_users = df["anon_user"].nunique(dropna=True) if "anon_user" in df.columns else None

        summaries.append({
            "cmid": cmid, "assign_name": aname,
            "submissions":  n_total, "unique_users": unique_users,
            "mean_grade":   round(grade_s.mean(),   3) if not grade_s.empty else None,
            "median_grade": round(grade_s.median(), 3) if not grade_s.empty else None,
            "mean_time_to_submit_h":      round(time_s.mean(), 3) if not time_s.empty else None,
            "ontime_submission_rate_pct": round(ontime_rate, 2) if ontime_rate is not None else None,
            "n_ontime": n_ontime, "n_late": n_late,
        })

    if summaries:
        df_sum = pd.DataFrame(summaries)
        df_sum.to_csv(SUMMARY_DIR / "assignments_summary.csv", index=False, encoding="utf-8-sig")

        if df_sum["mean_grade"].notna().any():
            save_comparison_chart(
                df_sum["assign_name"], df_sum["mean_grade"],
                "Mean Grade - Comparison Across All Assignments", "Mean Grade (0-100)",
                SUMMARY_DIR / "assignments_mean_grade_comparison.png", color=BLUE,
                note="Each bar shows the class average grade for one assignment. "
                     "Higher bars indicate assignments where students performed better overall. "
                     "Large differences between bars may point to varying difficulty levels.")

        if df_sum["ontime_submission_rate_pct"].notna().any():
            save_comparison_chart(
                df_sum["assign_name"], df_sum["ontime_submission_rate_pct"],
                "On-time Submission Rate (%) - All Assignments", "On-time Rate (%)",
                SUMMARY_DIR / "assignments_ontime_rate_comparison.png",
                color=GREEN, ref_line=80.0,
                note="Percentage of students who submitted before the deadline. "
                     "The orange reference line marks 80% - a common benchmark for healthy engagement. "
                     "Assignments with low rates may need earlier reminders or deadline adjustments.")


def analyze_h5p():
    summaries = []
    for csv in sorted(EXPORTS.glob("h5p_*.csv")):
        local_csv = move_file(csv, H5P_DIR)
        df  = pd.read_csv(local_csv)
        cmid  = local_csv.stem.split("_", 1)[1] if "_" in local_csv.stem else "unknown"

        if "h5p_name" in df.columns and not df["h5p_name"].dropna().empty:
            hname = df["h5p_name"].dropna().iloc[0]
        else:
            hname = f"h5p_{cmid}"

        score_s = get_numeric(df, "score_pct")
        if not score_s.empty:
            save_histogram(
                score_s, f"{hname}\nScore Distribution", "Score (%)",
                H5P_DIR / f"{local_csv.stem}_score_hist.png",
                pass_line=True,
                note="Score distribution for all H5P interactive activity attempts. "
                     "The green line shows the pass threshold; the annotation shows what percentage of "
                     "students achieved a passing score.")
            n_pass = int((score_s >= PASS_THRESHOLD).sum())
            n_fail = len(score_s) - n_pass
            save_pass_fail_bar(
                n_pass, n_fail, f"{hname}\nPass / Fail Split",
                H5P_DIR / f"{local_csv.stem}_pass_fail.png",
                note="Summary of how many attempts passed (>=50%) versus failed the H5P activity.")

        unique_users = df["anon_user"].nunique(dropna=True) if "anon_user" in df.columns else None
        n_pass_r  = int((score_s >= PASS_THRESHOLD).sum()) if not score_s.empty else None
        pass_rate = percent(n_pass_r, len(score_s)) if n_pass_r is not None else None

        summaries.append({
            "cmid": cmid, "h5p_name": hname,
            "attempts": len(df), "unique_users": unique_users,
            "mean_score_pct":   round(score_s.mean(),   3) if not score_s.empty else None,
            "median_score_pct": round(score_s.median(), 3) if not score_s.empty else None,
            "pass_rate_pct":    round(pass_rate, 2) if pass_rate is not None else None,
        })

    if summaries:
        pd.DataFrame(summaries).to_csv(SUMMARY_DIR / "h5p_summary.csv",
                                       index=False, encoding="utf-8-sig")


def analyze_forums():
    per_forum = []
    for csv in sorted(EXPORTS.glob("forum_*_posts.csv")):
        local_posts = move_file(csv, FORUM_DIR)
        df   = pd.read_csv(local_posts)
        parts = local_posts.stem.split("_")
        cmid  = parts[1] if len(parts) > 2 else "unknown"

        if "anon_user" in df.columns:
            counts = df["anon_user"].value_counts()
            save_bar_chart(
                counts,
                f"Forum {cmid} - Posts per Anonymised User",
                "Anonymised User ID", "Post Count",
                FORUM_DIR / f"forum_{cmid}_posts_per_user.png",
                note="Number of posts each anonymised student contributed to the forum. "
                     "Students with high counts are active contributors; those with just 1 post "
                     "may benefit from encouragement to engage more in discussions.")

            engaged = int((counts >= 2).sum())
            lurk    = int((counts == 1).sum())
            if (engaged + lurk) > 0:
                save_pass_fail_bar(
                    engaged, lurk,
                    f"Forum {cmid} - Active (>=2 posts) vs Single-Post Participants",
                    FORUM_DIR / f"forum_{cmid}_engagement.png",
                    note="Students with 2 or more posts are classified as 'active' participants; "
                         "those with exactly 1 post are 'single-post' contributors. "
                         "A high proportion of single-post contributors may indicate low forum engagement.")

        per_forum.append({
            "cmid": cmid,
            "posts":          len(df),
            "unique_users":   df["anon_user"].nunique(dropna=True) if "anon_user" in df.columns else None,
            "mean_posts_per_user": round(df["anon_user"].value_counts().mean(), 2)
                              if "anon_user" in df.columns else None,
        })

    for csv in sorted(EXPORTS.glob("forum_*_summary.csv")):
        move_file(csv, FORUM_DIR)

    if per_forum:
        pd.DataFrame(per_forum).to_csv(SUMMARY_DIR / "forums_summary.csv",
                                       index=False, encoding="utf-8-sig")


def analyze_databases():
    summaries = []
    for csv in sorted(EXPORTS.glob("data_*.csv")):
        local_csv = move_file(csv, DATA_DIR)
        df  = pd.read_csv(local_csv)
        cmid  = local_csv.stem.split("_", 1)[1] if "_" in local_csv.stem else "unknown"

        if "database_name" in df.columns and not df["database_name"].dropna().empty:
            dname = df["database_name"].dropna().iloc[0]
        else:
            dname = f"data_{cmid}"

        if "created_at" in df.columns:
            dates = pd.to_datetime(df["created_at"], errors="coerce").dt.date.dropna()
            if not dates.empty:
                counts = pd.Series(dates).value_counts().sort_index()
                save_bar_chart(
                    counts, f"{dname}\nEntries Submitted per Day", "Date", "Entries",
                    DATA_DIR / f"{local_csv.stem}_entries_per_day.png",
                    note="Number of database entries submitted on each calendar day. "
                         "Peaks show days of high activity; gaps may correspond to weekends or holidays.")

        summaries.append({
            "cmid": cmid, "database_name": dname,
            "entries":      len(df),
            "unique_users": df["anon_user"].nunique(dropna=True) if "anon_user" in df.columns else None,
        })

    if summaries:
        pd.DataFrame(summaries).to_csv(SUMMARY_DIR / "databases_summary.csv",
                                       index=False, encoding="utf-8-sig")


def write_overview_and_cleanup():
    categories = [
        ("quizzes",     QUIZ_DIR,   "quiz"),
        ("assignments", ASSIGN_DIR, "assign"),
        ("h5p",         H5P_DIR,    "h5p"),
        ("forums",      FORUM_DIR,  "forum"),
        ("databases",   DATA_DIR,   "data"),
    ]
    rows = []
    for cat, folder, prefix in categories:
        files = list(folder.glob(f"{prefix}_*.csv"))
        total_rows = 0
        for f in files:
            try:
                total_rows += len(pd.read_csv(f))
            except Exception:
                pass
        rows.append({"category": cat, "files": len(files), "rows": total_rows})

    df_ov = pd.DataFrame(rows)
    df_ov.to_csv(SUMMARY_DIR / "overview.csv", index=False, encoding="utf-8-sig")

    if df_ov["rows"].sum() > 0:
        visible = df_ov[df_ov["rows"] > 0]
        save_comparison_chart(
            visible["category"], visible["rows"],
            "Total Records Collected - by Activity Type", "Number of Records",
            SUMMARY_DIR / "overview_participation.png",
            color=PURPLE,
            note="Total number of student interaction records collected across each activity type. "
                 "This gives a high-level view of which parts of the course generated the most engagement data.")

    try:
        shutil.rmtree(EXPORTS, ignore_errors=True)
    except Exception:
        pass


if __name__ == "__main__":
    analyze_quizzes()
    analyze_assignments()
    analyze_h5p()
    analyze_forums()
    analyze_databases()
    write_overview_and_cleanup()
    print("Done. CSVs in type folders. Charts beside each CSV. Summaries in output/summary/")
