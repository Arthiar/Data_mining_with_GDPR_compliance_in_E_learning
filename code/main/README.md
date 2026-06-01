# Moodle Learning Analytics Pipeline

A Python tool that downloads student activity data from a Moodle course, anonymises student identities for privacy, and generates charts and statistics for analysis.

---

## What This Project Does

1. **Connects to your Moodle site** using its REST API
2. **Downloads student activity data** — quiz attempts, assignment submissions, forum posts, H5P results, and database entries
3. **Hides student identities** by replacing real IDs with anonymous codes (one-way SHA-256 hashing)
4. **Saves everything as CSV files** that can be opened in Excel or analysed in Python
5. **Generates charts and insights** — score distributions, pass/fail splits, time-vs-score relationships, and submission timing

---

## File Structure

```
code/main/
├── export.py          ← Run this FIRST — downloads data from Moodle
├── analyse.py         ← Run this SECOND — creates charts from the data
├── moodle_client.py   ← Helper used by export.py (do not run directly)
├── charts.py          ← Helper used by analyse.py (do not run directly)
├── requirements.txt   ← Python packages needed
├── .env               ← Your private credentials (you create this)
└── .env.example       ← Template showing what .env should contain
```

```
output/                ← Created automatically when you run the scripts
├── exports/           ← Raw CSV files downloaded from Moodle
├── quizzes/           ← Quiz charts and CSV files
├── assignments/       ← Assignment charts and CSV files
├── h5p/               ← H5P activity charts
├── forums/            ← Forum engagement charts
├── databases/         ← Database activity CSV files
├── summary/           ← One summary CSV per activity type
└── logs/              ← Timestamped log of every run (run.log)
```

---

## How To Run

### Step 0 — Install Python packages (once only)

```bash
pip install -r requirements.txt
```

### Step 1 — Create your credentials file

Copy the template and fill in your own values:

```bash
cp .env.example .env
```

Then open `.env` and edit it (see the Configuration section below).

### Step 2 — Download data from Moodle

```bash
python export.py
```

This will:
- Connect to your Moodle site
- Download data for all the activities listed in your `.env` file
- Save one CSV file per activity into `output/exports/`
- Write a timestamped log to `output/logs/run.log`

### Step 3 — Create charts and statistics

```bash
python analyse.py
```

This will:
- Read the CSV files that Step 2 created
- Generate charts for each activity (histograms, pass/fail bars, scatter plots)
- Save charts into organised folders under `output/`
- Save a summary CSV for quizzes and assignments into `output/summary/`

---

## Configuration (.env file)

Your `.env` file must contain the following. **Never share this file or commit it to Git** — it contains your Moodle login token.

```bash
# The full URL of your Moodle site (no trailing slash)
MOODLE_BASE_URL=https://your-moodle-site.example.com

# Your Moodle Web Services token
# In Moodle: Site Administration > Plugins > Web Services > Manage tokens
MOODLE_WSTOKEN=your_token_here

# The numeric ID of the course you want to analyse
# Found in the URL when you visit the course: ?id=1234
COURSE_ID=1234

# A secret random string used to anonymise student IDs
# Pick any long random string. Changing it will change all anonymous codes.
HASH_SALT=replace_with_a_long_random_secret

# Comma-separated Course Module IDs (CMIDs) for each activity type
# Leave a line blank if you do not want to export that activity type
# Find a CMID: hover over the activity link in Moodle and look at the URL: ?id=456
QUIZ_CMIDS=456, 457, 458
ASSIGN_CMIDS=459, 460
FORUM_CMIDS=461
HVP_CMIDS=462
DATA_CMIDS=463
```

### How to find a CMID

1. Log into Moodle and go to your course
2. Right-click on any activity link and copy the URL
3. The URL will contain `?id=456` — that number is the CMID

---

## What Each File Does

### export.py — Data Downloader

Connects to Moodle and saves student activity data as CSV files.

| Function | What it does |
|---|---|
| `load_settings()` | Reads credentials and settings from the `.env` file |
| `setup_output_folders()` | Clears old output and creates fresh empty folders |
| `write_log()` | Prints a timestamped message and saves it to `run.log` |
| `save_rows_to_csv()` | Writes a list of data rows to a CSV file |
| `export_quizzes()` | Downloads every student's quiz attempts and scores |
| `export_assignments()` | Downloads submission times and grades for each assignment |
| `export_h5p()` | Downloads attempt scores for H5P interactive activities |
| `export_forums()` | Downloads all forum posts and a per-student post count |
| `export_databases()` | Downloads all entries from database activities |
| `main()` | Runs all of the above in order |

### analyse.py — Chart Generator

Reads the CSV files and produces charts and summary statistics.

| Function | What it does |
|---|---|
| `move_csv_to_folder()` | Moves each CSV from exports into the correct type folder |
| `get_numeric_column()` | Reads one column from a table and converts values to numbers |
| `get_first_value()` | Gets the activity name from the first row of data |
| `analyze_quizzes()` | Score histogram + pass/fail bar + time-vs-score scatter per quiz |
| `analyze_assignments()` | Grade histogram + on-time vs late bar per assignment |
| `analyze_h5p()` | Score histogram + pass/fail bar per H5P activity |
| `analyze_forums()` | Active vs single-post contributor bar per forum |
| `analyze_databases()` | Moves files and prints entry count (no charts) |
| `main()` | Runs all of the above in order |

### moodle_client.py — Moodle Connection (helper)

Contains the `MoodleClient` class used by `export.py`.

| Method | What it does |
|---|---|
| `call_api()` | Sends one request to Moodle; retries up to 3 times on failure |
| `get_all_course_modules()` | Fetches all activities in the course |
| `get_enrolled_student_ids()` | Fetches the list of all student IDs |
| `anonymize_student_id()` | Converts a real student ID to an anonymous code |
| `unix_timestamp_to_date()` | Converts a raw timestamp number to a readable date string |
| `duration_in_seconds()` | Calculates how many seconds passed between two timestamps |
| `parse_cmid_list()` | Converts "123, 456" from the `.env` file into a Python list |

### charts.py — Chart Drawing (helper)

Contains the three chart functions used by `analyse.py`.

| Function | What it draws |
|---|---|
| `draw_histogram()` | Bar chart of score distribution with mean and median lines |
| `draw_pass_fail_bar()` | Horizontal bar split into green (pass) and red (fail) sections |
| `draw_scatter_with_trend()` | Dot plot with a trend line and correlation value |

---

## Output Files Explained

### CSV files in output/exports/

| File name | Contents |
|---|---|
| `quiz_<cmid>.csv` | One row per quiz attempt: student code, score %, duration, attempt number |
| `assign_<cmid>.csv` | One row per submission: student code, grade, submission time, late/on-time |
| `h5p_<cmid>.csv` | One row per attempt: student code, score, duration |
| `forum_<cmid>_posts.csv` | One row per post: student code, discussion ID, timestamp |
| `forum_<cmid>_summary.csv` | One row per student: how many posts they made |
| `data_<cmid>.csv` | One row per database entry: student code, timestamp, approval status |

### Summary CSVs in output/summary/

| File name | Contents |
|---|---|
| `quizzes_summary.csv` | One row per quiz: mean score, pass rate, average duration |
| `assignments_summary.csv` | One row per assignment: mean grade, on-time submission rate |

### Charts in output/quizzes/, output/assignments/, etc.

Each activity generates:
- A **score/grade histogram** — shows how scores are spread across the class
- A **pass/fail bar** — shows the percentage who passed vs failed
- A **time vs score scatter** (quizzes only) — shows whether spending more time leads to better scores

Each chart has a one-sentence insight at the bottom that draws a specific conclusion from the data (e.g. "Only 42% of students submitted on time — earlier reminders may help").

---

## Privacy and Data Protection

Student identities are protected using **one-way SHA-256 hashing**:

1. The real student ID (e.g. `12345`) is combined with your secret `HASH_SALT`
2. The result is hashed using SHA-256
3. The first 12 characters of the hash are used: `u_a1b2c3d4e5f6`

This means:
- The same student always gets the same anonymous code (so you can track one student across files)
- You cannot reverse the code to find the real student ID
- Changing `HASH_SALT` changes all codes (useful if you want to reset anonymisation)

**Keep your `.env` file private.** Anyone with the `HASH_SALT` and the original Moodle data could re-identify students.

---

## Troubleshooting

**"Missing configuration in .env file"**
- Check that your `.env` file exists in `code/main/`
- Check that `MOODLE_BASE_URL`, `MOODLE_WSTOKEN`, and `COURSE_ID` are all filled in

**"Connection failed"**
- Check the URL in `MOODLE_BASE_URL` — it must not have a trailing slash
- Check your token in Moodle: Site Administration > Plugins > Web Services > Manage tokens
- Check that Web Services are enabled on your Moodle site

**"No data exported" (empty CSV files)**
- Check that the CMIDs in your `.env` are correct
- Log into Moodle and hover over the activity — the URL should contain `?id=<cmid>`
- Check `output/logs/run.log` for error messages

**"ModuleNotFoundError"**
```bash
pip install -r requirements.txt
```

**"No data found in output/exports/"**
- You must run `export.py` before running `analyse.py`

---

## Requirements

- Python 3.9 or later
- Moodle site with Web Services enabled
- A Moodle Web Services token with access to the course

Python packages (installed via `pip install -r requirements.txt`):

| Package | Version | Used for |
|---|---|---|
| `requests` | >= 2.32 | Sending HTTP requests to the Moodle API |
| `python-dotenv` | >= 1.0 | Reading the `.env` configuration file |
| `pandas` | >= 2.1 | Reading and processing CSV data |
| `matplotlib` | >= 3.8 | Drawing charts |
| `tqdm` | >= 4.66 | Showing a progress bar during export |
