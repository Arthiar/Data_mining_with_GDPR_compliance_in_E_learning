# analyse.py
# Main analysis script: reads the CSV files saved by export.py and creates charts.
# Run AFTER export.py has finished.
#
# How to run:
#   python analyse.py

import shutil
from pathlib import Path

import pandas as pd

from charts import draw_histogram, draw_pass_fail_bar, draw_scatter_with_trend, PASS_THRESHOLD


# ─── FOLDER PATHS ─────────────────────────────────────────────────────────────

# This script lives at code/main/. Go up three levels to reach the project root.
ROOT_FOLDER = Path(__file__).parent.parent.parent.resolve()
OUTPUT_FOLDER = ROOT_FOLDER / "output"
EXPORTS_FOLDER = OUTPUT_FOLDER / "exports"

QUIZ_FOLDER = OUTPUT_FOLDER / "quizzes"
ASSIGN_FOLDER = OUTPUT_FOLDER / "assignments"
H5P_FOLDER = OUTPUT_FOLDER / "h5p"
FORUM_FOLDER = OUTPUT_FOLDER / "forums"
DATABASE_FOLDER = OUTPUT_FOLDER / "databases"
SUMMARY_FOLDER = OUTPUT_FOLDER / "summary"

# Create all output folders if they do not already exist
for folder in [QUIZ_FOLDER, ASSIGN_FOLDER, H5P_FOLDER, FORUM_FOLDER, DATABASE_FOLDER, SUMMARY_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)


# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────────

def move_csv_to_folder(source_path, destination_folder):
    # Move a CSV file from the exports folder into the correct type folder.
    # Falls back to copy-then-delete if the move fails (e.g., across drives).
    destination_path = destination_folder / source_path.name

    if destination_path.exists():
        destination_path.unlink()

    try:
        shutil.move(str(source_path), str(destination_path))
    except Exception:
        shutil.copy2(source_path, destination_path)
        try:
            source_path.unlink()
        except Exception:
            pass

    return destination_path


def get_numeric_column(dataframe, column_name):
    # Extract a column from the table, convert every value to a number, and drop blanks.
    if column_name not in dataframe.columns:
        return pd.Series(dtype=float)

    numeric_values = pd.to_numeric(dataframe[column_name], errors="coerce").dropna()
    return numeric_values


def get_first_value(dataframe, column_name):
    # Return the first non-empty value in a column, or None if the column is empty.
    if column_name not in dataframe.columns:
        return None

    non_empty = dataframe[column_name].dropna()
    if non_empty.empty:
        return None

    return non_empty.iloc[0]


# ─── QUIZ ANALYSIS ────────────────────────────────────────────────────────────

def analyze_quizzes():
    # For each quiz CSV: create a score histogram, a pass/fail bar, and a time-vs-score scatter plot.
    # Then save one summary CSV covering all quizzes.

    print("\n" + "=" * 70)
    print("ANALYZING QUIZZES")
    print("=" * 70)

    # Move quiz CSV files from the exports folder into the quizzes folder
    for csv_file in sorted(EXPORTS_FOLDER.glob("quiz_*.csv")):
        move_csv_to_folder(csv_file, QUIZ_FOLDER)

    summaries = []

    for csv_file in sorted(QUIZ_FOLDER.glob("quiz_*.csv")):
        dataframe = pd.read_csv(csv_file)

        # Get the activity ID from the filename: "quiz_456.csv" -> "456"
        cmid = csv_file.stem.split("_", 1)[1] if "_" in csv_file.stem else "unknown"
        quiz_name = get_first_value(dataframe, "quiz_name") or "Unknown Quiz"

        print(f"\n  Processing: {quiz_name}")

        scores = get_numeric_column(dataframe, "score_pct")
        durations = get_numeric_column(dataframe, "duration_minutes")

        # Default summary values in case scores are empty
        number_passed = 0
        number_failed = 0
        pass_rate = None

        if not scores.empty:
            number_passed = int((scores >= PASS_THRESHOLD).sum())
            number_failed = len(scores) - number_passed
            pass_rate = round(100.0 * number_passed / len(scores), 1)
            mean_score = round(scores.mean(), 1)
            median_score = round(scores.median(), 1)

            # Chart 1: Histogram of score distribution
            # Insight: one specific sentence about what the pass rate and mean together reveal
            if mean_score < 60 and pass_rate >= 50:
                histogram_insight = (
                    f"{pass_rate}% of students passed, but the mean score of {mean_score}% suggests "
                    f"most are just scraping through — not confidently mastering the material."
                )
            elif pass_rate < 50:
                histogram_insight = (
                    f"Only {pass_rate}% of students passed, with a mean score of {mean_score}%. "
                    f"More than half the class is below the threshold — this quiz may need extra review support."
                )
            else:
                histogram_insight = (
                    f"{pass_rate}% of students passed with a mean of {mean_score}% and a median of {median_score}% "
                    f"— overall the class is performing well on this quiz."
                )

            draw_histogram(
                scores, f"{quiz_name}\nScore Distribution",
                QUIZ_FOLDER / f"{csv_file.stem}_score_histogram.png",
                show_pass_line=True, insight=histogram_insight
            )

            # Chart 2: Pass/fail split
            # Insight: one specific sentence about whether the pass rate is a concern
            if pass_rate < 70:
                pass_fail_insight = (
                    f"{number_passed} students passed and {number_failed} failed — "
                    f"a pass rate below 70% typically suggests students need more guided practice before assessments."
                )
            else:
                pass_fail_insight = (
                    f"{number_passed} students passed and {number_failed} failed — "
                    f"a pass rate of {pass_rate}% is a healthy result for this quiz."
                )

            draw_pass_fail_bar(
                number_passed, number_failed,
                f"{quiz_name}\nPass / Fail Split",
                QUIZ_FOLDER / f"{csv_file.stem}_pass_fail.png",
                insight=pass_fail_insight
            )

        # Chart 3: Time spent vs score
        # Insight: one specific sentence about what the correlation value means for teaching
        if not scores.empty and not durations.empty:
            correlation = round(float(scores.corr(durations)), 2)

            if correlation > 0.3:
                time_insight = (
                    f"Students who spent more time scored higher (r = {correlation:+.2f}). "
                    f"Encouraging students not to rush — or providing more time — could improve results."
                )
            elif correlation < -0.3:
                time_insight = (
                    f"Students who spent more time actually scored lower (r = {correlation:+.2f}). "
                    f"This may mean stronger students finish quickly, or longer attempts reflect struggling."
                )
            else:
                time_insight = (
                    f"Time spent and score are not meaningfully related (r = {correlation:+.2f}). "
                    f"How long a student spends on this quiz does not predict how well they will do."
                )

            draw_scatter_with_trend(
                durations, scores,
                f"{quiz_name}\nTime Spent vs Score",
                "Time (minutes)", "Score (%)",
                QUIZ_FOLDER / f"{csv_file.stem}_time_vs_score.png",
                insight=time_insight
            )

        # Collect stats for the summary CSV
        unique_students = None
        if "anon_user" in dataframe.columns:
            unique_students = dataframe["anon_user"].nunique()

        summaries.append({
            "quiz_name": quiz_name,
            "cmid": cmid,
            "attempts": len(dataframe),
            "unique_students": unique_students,
            "mean_score_%": round(scores.mean(), 2) if not scores.empty else None,
            "median_score_%": round(scores.median(), 2) if not scores.empty else None,
            "pass_rate_%": pass_rate,
            "mean_duration_min": round(durations.mean(), 2) if not durations.empty else None,
        })

    if summaries:
        summary_df = pd.DataFrame(summaries)
        summary_df.to_csv(SUMMARY_FOLDER / "quizzes_summary.csv", index=False, encoding="utf-8-sig")
        print(f"\n  Summary saved: quizzes_summary.csv ({len(summaries)} quizzes)")


# ─── ASSIGNMENT ANALYSIS ──────────────────────────────────────────────────────

def analyze_assignments():
    # For each assignment CSV: create a grade histogram and an on-time vs late bar chart.
    # Then save one summary CSV covering all assignments.

    print("\n" + "=" * 70)
    print("ANALYZING ASSIGNMENTS")
    print("=" * 70)

    for csv_file in sorted(EXPORTS_FOLDER.glob("assign_*.csv")):
        move_csv_to_folder(csv_file, ASSIGN_FOLDER)

    summaries = []

    for csv_file in sorted(ASSIGN_FOLDER.glob("assign_*.csv")):
        dataframe = pd.read_csv(csv_file)
        cmid = csv_file.stem.split("_", 1)[1] if "_" in csv_file.stem else "unknown"
        assign_name = get_first_value(dataframe, "assign_name") or "Unknown Assignment"

        print(f"\n  Processing: {assign_name}")

        # Get grades — exclude -1, which Moodle uses to mean "not yet graded"
        grades = get_numeric_column(dataframe, "grade")
        grades = grades[grades >= 0]

        mean_grade = None
        median_grade = None

        if not grades.empty:
            mean_grade = round(grades.mean(), 1)
            median_grade = round(grades.median(), 1)

            # Describe performance level based on the mean grade
            if mean_grade >= 70:
                performance_description = "strong"
            elif mean_grade >= 50:
                performance_description = "moderate"
            else:
                performance_description = "struggling"

            # Chart 1: Grade distribution histogram
            # Insight: one specific sentence — note if the median is much lower than the mean
            if median_grade < mean_grade - 10:
                grade_insight = (
                    f"The average grade is {mean_grade}/100 but the median is only {median_grade} — "
                    f"a few high scorers are pulling the mean up while most students sit below it."
                )
            else:
                grade_insight = (
                    f"Average grade is {mean_grade}/100, with {performance_description} overall class performance. "
                    f"The median of {median_grade} confirms most students are clustered around that level."
                )

            draw_histogram(
                grades, f"{assign_name}\nGrade Distribution",
                ASSIGN_FOLDER / f"{csv_file.stem}_grade_histogram.png",
                show_pass_line=False, insight=grade_insight
            )

        # Check on-time vs late submissions
        n_ontime = 0
        n_late = 0
        ontime_rate = None

        if "duedate" in dataframe.columns and "submitted_unix" in dataframe.columns:
            due_dates = pd.to_numeric(dataframe["duedate"], errors="coerce")
            submitted_times = pd.to_numeric(dataframe["submitted_unix"], errors="coerce")

            # Only count rows where both values are present and a due date is set
            valid_rows = (~due_dates.isna()) & (~submitted_times.isna()) & (due_dates > 0)

            if valid_rows.any():
                total_valid = int(valid_rows.sum())
                n_ontime = int((submitted_times[valid_rows] <= due_dates[valid_rows]).sum())
                n_late = total_valid - n_ontime
                ontime_rate = round(100.0 * n_ontime / total_valid, 1)

                # Chart 2: On-time vs late bar
                # Insight: one specific sentence about what the late rate implies
                if ontime_rate < 60:
                    timing_insight = (
                        f"Only {ontime_rate}% of students submitted on time ({n_late} submitted late). "
                        f"With fewer than 60% on time, earlier reminders or a review of the deadline window may help."
                    )
                else:
                    timing_insight = (
                        f"{ontime_rate}% of students submitted on time ({n_ontime} on time, {n_late} late). "
                        f"The late submissions may indicate students who are overloaded or need better planning support."
                    )

                draw_pass_fail_bar(
                    n_ontime, n_late,
                    f"{assign_name}\nOn-Time vs Late",
                    ASSIGN_FOLDER / f"{csv_file.stem}_ontime_split.png",
                    insight=timing_insight
                )

        unique_students = None
        if "anon_user" in dataframe.columns:
            unique_students = dataframe["anon_user"].nunique()

        summaries.append({
            "assign_name": assign_name,
            "cmid": cmid,
            "submissions": len(dataframe),
            "unique_students": unique_students,
            "mean_grade": mean_grade,
            "median_grade": median_grade,
            "ontime_submission_%": ontime_rate,
            "n_ontime": n_ontime,
            "n_late": n_late,
        })

    if summaries:
        summary_df = pd.DataFrame(summaries)
        summary_df.to_csv(SUMMARY_FOLDER / "assignments_summary.csv", index=False, encoding="utf-8-sig")
        print(f"\n  Summary saved: assignments_summary.csv ({len(summaries)} assignments)")


# ─── H5P ANALYSIS ─────────────────────────────────────────────────────────────

def analyze_h5p():
    # For each H5P activity CSV: create a score histogram and a pass/fail bar chart.

    print("\n" + "=" * 70)
    print("ANALYZING H5P ACTIVITIES")
    print("=" * 70)

    for csv_file in sorted(EXPORTS_FOLDER.glob("h5p_*.csv")):
        local_csv = move_csv_to_folder(csv_file, H5P_FOLDER)
        dataframe = pd.read_csv(local_csv)

        h5p_name = get_first_value(dataframe, "h5p_name") or "Unknown H5P"
        print(f"  Processing: {h5p_name}")

        scores = get_numeric_column(dataframe, "score_pct")

        if not scores.empty:
            number_passed = int((scores >= PASS_THRESHOLD).sum())
            number_failed = len(scores) - number_passed
            pass_rate = round(100.0 * number_passed / len(scores), 1)

            # Insight: one specific sentence about this H5P activity's results
            if pass_rate < 50:
                insight = (
                    f"Only {pass_rate}% of students passed this H5P activity — "
                    f"the content may be too difficult or students are not engaging with it carefully."
                )
            else:
                insight = (
                    f"{pass_rate}% of students passed this H5P activity — "
                    f"a useful check that students are actively engaging with the interactive content."
                )

            draw_histogram(
                scores, f"{h5p_name}\nScore Distribution",
                H5P_FOLDER / f"{local_csv.stem}_score_histogram.png",
                show_pass_line=True, insight=insight
            )
            draw_pass_fail_bar(
                number_passed, number_failed,
                f"{h5p_name}\nPass / Fail",
                H5P_FOLDER / f"{local_csv.stem}_pass_fail.png"
            )


# ─── FORUM ANALYSIS ───────────────────────────────────────────────────────────

def analyze_forums():
    # For each forum CSV: create a bar chart comparing active contributors vs one-time posters.

    print("\n" + "=" * 70)
    print("ANALYZING FORUMS")
    print("=" * 70)

    for csv_file in sorted(EXPORTS_FOLDER.glob("forum_*_posts.csv")):
        local_csv = move_csv_to_folder(csv_file, FORUM_FOLDER)
        dataframe = pd.read_csv(local_csv)

        # Get the forum ID from the filename: "forum_789_posts" -> "789"
        cmid = local_csv.stem.split("_")[1]
        print(f"  Processing: Forum {cmid} ({len(dataframe)} posts)")

        if "anon_user" in dataframe.columns:
            # Count how many posts each student made
            post_counts = dataframe["anon_user"].value_counts()

            # "Active" means 2 or more posts; "single-post" means exactly 1
            number_active = int((post_counts >= 2).sum())
            number_single_post = int((post_counts == 1).sum())

            if number_active + number_single_post > 0:
                total_contributors = number_active + number_single_post
                active_rate = round(100.0 * number_active / total_contributors, 1)

                # Insight: one specific sentence about whether real discussion is happening
                if active_rate < 40:
                    insight = (
                        f"Only {number_active} of {total_contributors} students posted more than once — "
                        f"most seem to be fulfilling a minimum requirement rather than engaging in genuine discussion."
                    )
                else:
                    insight = (
                        f"{number_active} students made multiple posts and {number_single_post} posted only once — "
                        f"a mix suggesting real discussion is happening alongside participation-driven posts."
                    )

                draw_pass_fail_bar(
                    number_active, number_single_post,
                    f"Forum {cmid}\nActive vs Single-Post",
                    FORUM_FOLDER / f"{local_csv.stem}_engagement.png",
                    insight=insight
                )


# ─── DATABASE ANALYSIS ────────────────────────────────────────────────────────

def analyze_databases():
    # Move database CSV files to their folder and print a count of entries (no charts).

    print("\n" + "=" * 70)
    print("ANALYZING DATABASES")
    print("=" * 70)

    for csv_file in sorted(EXPORTS_FOLDER.glob("data_*.csv")):
        local_csv = move_csv_to_folder(csv_file, DATABASE_FOLDER)
        dataframe = pd.read_csv(local_csv)

        db_name = get_first_value(dataframe, "database_name") or "Unknown Database"
        print(f"  Processing: {db_name} ({len(dataframe)} entries)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    # Run all five analyses in order.

    print("\n" + "=" * 70)
    print("MOODLE DATA ANALYSIS")
    print("=" * 70)

    if not EXPORTS_FOLDER.exists():
        print("Error: No data found in output/exports/")
        print("   Please run: python export.py")
        return

    analyze_quizzes()
    analyze_assignments()
    analyze_h5p()
    analyze_forums()
    analyze_databases()

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"  Quizzes:     {QUIZ_FOLDER}")
    print(f"  Assignments: {ASSIGN_FOLDER}")
    print(f"  H5P:         {H5P_FOLDER}")
    print(f"  Forums:      {FORUM_FOLDER}")
    print(f"  Databases:   {DATABASE_FOLDER}")
    print(f"  Summaries:   {SUMMARY_FOLDER}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
