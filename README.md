# E-Learning Data Mining with GDPR Compliance

**Master's Thesis Project**  
Fachhochschule Dortmund — University of Applied Sciences and Arts  
Author: Arthisree Saraswathi Rajamanickam (Student ID: 7216696)

---

## What This Project Does

This project implements a **privacy-preserving learning analytics pipeline** for Moodle-based e-learning systems. It automatically extracts course activity data from a Moodle instance via its REST API, anonymises all user identifiers, and produces statistical summaries and visualisation charts — all without exposing any personal or identifiable information.

The workflow follows GDPR principles:
- **Data minimisation** — only the fields needed for analysis are collected
- **Purpose limitation** — data is used exclusively for aggregate learning analytics
- **Privacy by design** — user IDs are pseudonymised with SHA-256 before any output is written

---

## Supported Activity Types

| Activity | What is extracted |
|---|---|
| **Quizzes** | Attempts, scores, duration, pass/fail status |
| **Assignments** | Submissions, grades, on-time vs late rates |
| **H5P Interactive Content** | Attempts, scores, pass/fail status |
| **Forums** | Post counts per anonymised user, engagement levels |
| **Database modules** | Entry counts, submission dates |

---

## Project Structure

```
Course_1516_Python_Script/
│
├── export.py           # Step 1 — Pull data from Moodle API and write raw CSVs
├── analyse.py          # Step 2 — Anonymise, analyse, and generate charts
├── requirements.txt    # Python dependencies
├── .env.example        # Configuration template (copy to .env and fill in)
├── .gitignore          # Keeps .env and generated outputs out of version control
│
└── output/             # Created automatically when you run the scripts
    ├── quizzes/        # Per-quiz CSVs and charts
    ├── assignments/    # Per-assignment CSVs and charts
    ├── h5p/            # H5P activity CSVs and charts
    ├── forums/         # Forum post CSVs and charts
    ├── databases/      # Database module CSVs and charts
    └── summary/        # Cross-activity comparison charts and overview CSV
```

> The `output/` folder is excluded from version control. Run the scripts to regenerate it.

---

## Prerequisites

- Python 3.9 or newer
- A Moodle instance with **Web Services** enabled and a valid token
- The following Moodle web service functions enabled for your token:
  - `core_course_get_contents`
  - `core_enrol_get_enrolled_users`
  - `mod_quiz_get_quizzes_by_courses`, `mod_quiz_get_user_attempts`
  - `mod_assign_get_assignments`, `mod_assign_get_submissions`
  - `mod_h5pactivity_get_attempts`, `mod_h5pactivity_get_results`
  - `mod_forum_get_forum_discussions`, `mod_forum_get_discussion_posts`
  - `mod_data_get_entries`

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Arthiar/E_learning_Data_mining_with_GDPR_compliance.git
cd E_learning_Data_mining_with_GDPR_compliance
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv

# On Windows
.venv\Scripts\activate

# On macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure your environment

Copy the template and fill in your Moodle credentials:

```bash
cp .env.example .env
```

Open `.env` in any text editor and set:

```
MOODLE_BASE_URL=https://your-moodle-instance.example.com
MOODLE_WSTOKEN=your_actual_token
COURSE_ID=1234
QUIZ_CMIDS=111,222          # comma-separated module IDs; leave blank if unused
ASSIGN_CMIDS=333,444
FORUM_CMIDS=
HVP_CMIDS=555
DATA_CMIDS=666
HASH_SALT=any_long_random_secret_string
```

> **Important:** The `.env` file is listed in `.gitignore` and will never be committed.

---

## Running the Scripts

Run the two scripts in order:

### Step 1 — Export data from Moodle

```bash
python export.py
```

This connects to your Moodle instance, fetches activity data for the configured course, pseudonymises all user IDs, and writes raw CSV files to `output/exports/`.

A progress log is written to `output/logs/run.log`.

### Step 2 — Analyse and visualise

```bash
python analyse.py
```

This reads the exported CSVs, organises them by activity type, generates charts, and writes summary files. When complete, `output/exports/` is deleted and all data lives in the type-specific subfolders under `output/`.

---

## What the Analysis Produces

### Per-activity charts (saved alongside each CSV)

| Chart | What it shows |
|---|---|
| `*_score_hist.png` | Score distribution with mean, median, and pass threshold |
| `*_pass_fail.png` | Pass / fail split with exact counts |
| `*_duration_hist.png` | Time-on-task distribution (quizzes) |
| `*_time_vs_score.png` | Scatter plot of time vs score with trend line and correlation |
| `*_grade_hist.png` | Grade distribution (assignments) |
| `*_ontime_vs_late.png` | On-time vs late submission donut chart |
| `*_posts_per_user.png` | Forum post count per anonymised user |
| `*_engagement.png` | Active (≥2 posts) vs single-post participants |
| `*_entries_per_day.png` | Database entry submissions over time |

### Cross-activity summary charts (in `output/summary/`)

| File | What it shows |
|---|---|
| `quizzes_mean_score_comparison.png` | Mean score compared across all quizzes |
| `quizzes_pass_rate_comparison.png` | Pass rate compared across all quizzes |
| `quizzes_duration_comparison.png` | Mean time-on-task compared across all quizzes |
| `assignments_mean_grade_comparison.png` | Mean grade compared across all assignments |
| `assignments_ontime_rate_comparison.png` | On-time submission rate across all assignments |
| `overview_participation.png` | Total records collected by activity type |

### Summary CSV files (in `output/summary/`)

- `quizzes_summary.csv` — mean, median, p10/p90 scores, pass rate, correlation
- `assignments_summary.csv` — grades, submission timing, on-time rate
- `h5p_summary.csv` — scores, pass rate
- `forums_summary.csv` — post counts, unique users, mean posts per user
- `databases_summary.csv` — entry counts, unique users
- `overview.csv` — high-level row counts per activity type

---

## Privacy and GDPR Compliance

- All user identifiers are replaced with a **deterministic SHA-256 hash** (salted) before any CSV is written. The original ID never appears in any output.
- No names, email addresses, or any direct identifiers are stored or exported.
- All outputs are **aggregated statistics** that cannot be used to infer individual learner behaviour.
- The anonymisation salt (`HASH_SALT`) is stored only in your local `.env` and is never committed to the repository.
- Temporary export files are deleted automatically after analysis completes.

These measures align with GDPR Articles 5, 25, and 89 (privacy by design, data minimisation, and pseudonymisation for research purposes), as discussed in Chapters 5 and 6 of the accompanying thesis.

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP client for Moodle REST API calls |
| `python-dotenv` | Load configuration from `.env` |
| `pandas` | Data manipulation and CSV I/O |
| `matplotlib` | Chart generation |
| `numpy` | Numerical operations (trend lines, statistics) |
| `tqdm` | Progress bars during export |

Install all at once:

```bash
pip install -r requirements.txt
```

---

## Scope and Limitations

- Developed and tested against a single Moodle 4.x course.
- Intended for **academic demonstration and validation**, not production deployment.
- Moodle Web Services must be configured by a site administrator before use.
- Adaptation is required for different institutional environments or activity structures.

---

## Academic Context

This code supports the implementation described in:

- **Chapter 5** — Aggregated Data Analytics and Anonymised Statistics
- **Chapter 6** — Python Automation for Data Analysis
- **Appendix** — Implementation Evidence and Validation

The thesis (not included in this repository) is the primary source of documentation and context.

---

## Disclaimer

This code is provided solely for **academic evaluation purposes**.  
It should not be used in a production environment without further security review, institutional approval, and GDPR compliance validation.
