# Moodle Course Data Analysis - Complete Guide

## Overview

This project downloads student activity data from Moodle (quizzes, assignments, forums, H5P activities, databases) and creates meaningful charts with insights about student performance.

**Two main scripts:**
1. **export.py** - Downloads data from Moodle and saves as CSV
2. **analyse.py** - Analyzes the CSV data and creates charts with insights

---

## Quick Start

```bash
# 1. Setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Moodle credentials

# 2. Export data from Moodle
python export.py

# 3. Analyze and create charts
python analyse.py

# 4. View results in output/ folder
```

---

## Detailed Code Explanations

### **export.py - Line by Line**

#### **BLOCK 1: Imports & Module Declarations**
```python
import os, sys, time, shutil, hashlib
from pathlib import Path
from datetime import datetime
import requests, pandas, dotenv, tqdm
```

**What it does:**
- `os` - Access environment variables (.env file)
- `sys` - Exit program if configuration is wrong
- `time` - Wait between API retries
- `shutil` - Delete/move folders
- `hashlib` - Hash student IDs for anonymization
- `pathlib.Path` - Handle file paths (cross-platform compatible)
- `datetime` - Create timestamps for logging
- `requests` - Send HTTP requests to Moodle
- `pandas` - Create and save DataFrames (CSV files)
- `dotenv` - Load .env configuration file
- `tqdm` - Show progress bars

**Why these?** These are industry-standard Python libraries for data processing and API communication.

---

#### **BLOCK 2: Class Definition & Initialization**
```python
class MoodleExporter:
    def __init__(self):
        load_dotenv()
        self.moodle_url = os.getenv("MOODLE_BASE_URL", "")
        self.token = os.getenv("MOODLE_WSTOKEN", "")
        # ... etc
```

**What it does:**
- Creates a class to organize all export functions together
- Loads .env file with Moodle credentials
- Stores configuration as instance variables (self.moodle_url, self.token, etc.)

**Why a class?** Classes group related functions, making code:
- Organized and easy to maintain
- Reusable
- Easier to understand (like a toolbox organizing tools by type)

**What's loaded from .env?**
- `MOODLE_BASE_URL` - URL of Moodle site (e.g., https://moodle.example.com)
- `MOODLE_WSTOKEN` - API authentication token (like a password)
- `HASH_SALT` - Random string to hide real student IDs
- `COURSE_ID` - Which course to download
- `QUIZ_CMIDS`, `ASSIGN_CMIDS`, etc. - Which activities to export

---

#### **BLOCK 3: Logging Function**
```python
def log(self, message):
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)  # Print to screen
    with open(LOGS / "run.log", "a") as f:
        f.write(line + "\n")  # Save to file
```

**What it does:**
- Prints message with timestamp to console
- Saves the same message to `output/logs/run.log`

**Why timestamp?** If something goes wrong, we need to know WHEN it happened for debugging.

**Example output:**
```
[2024-06-02T10:32:45] ✓ Connected to: My Moodle Site
[2024-06-02T10:32:47] [quiz] Exporting 'Quiz 1'
[2024-06-02T10:33:12] → Saved 45 rows to quiz_123.csv
```

---

#### **BLOCK 4: Student ID Anonymization**
```python
def anonymize_student_id(self, real_student_id):
    combined = self.salt + str(real_student_id)
    hashed = hashlib.sha256(combined.encode()).hexdigest()
    return "u_" + hashed[:12]
```

**What it does:**
1. Takes real student ID (e.g., 12345)
2. Adds salt (random string from .env) to it
3. Hashes using SHA-256 (one-way encryption)
4. Takes first 12 characters and adds "u_" prefix

**Example:**
```
Real ID: 12345
Salt: "my_secret_salt"
Combined: "my_secret_salt12345"
Hash: "a1b2c3d4e5f6..." (256 characters)
Result: "u_a1b2c3d4e5" (anonymized)

→ Same student (12345) ALWAYS gets same code (u_a1b2c3d4e5)
→ Can't reverse it - can't find real ID from anonymous code
```

**Why?** Privacy! Real student IDs shouldn't be in analysis results.

---

#### **BLOCK 5: Unix Timestamp Conversion**
```python
def convert_unix_timestamp_to_readable_date(self, unix_timestamp):
    if not unix_timestamp or int(unix_timestamp) == 0:
        return None
    return datetime.fromtimestamp(int(unix_timestamp)).strftime("%Y-%m-%d %H:%M:%S")
```

**What it does:**
Converts Unix timestamps (seconds since 1970) to human-readable format.

**Example:**
```
Input: 1717255120
Output: "2024-06-02 10:32:00"
```

**Why?** Timestamps are hard to understand. Humans need dates/times.

---

#### **BLOCK 6: Time Duration Calculation**
```python
def calculate_time_difference_in_seconds(self, start_unix, finish_unix):
    try:
        difference = int(finish_unix) - int(start_unix)
        return difference
    except Exception:
        return None
```

**What it does:**
Calculates seconds between two timestamps.

**Example:**
```
Start: 1717255200 (10:00:00)
Finish: 1717255530 (10:05:30)
Duration: 330 seconds = 5.5 minutes
```

**Why?** We want to know how long students spent on each activity.

---

#### **BLOCK 7: Parse CSV CMIDs from Environment**
```python
def parse_comma_separated_cmids_from_env(self, env_value):
    if not env_value:
        return []
    cmid_list = []
    for item in env_value.split(","):
        if item.strip().isdigit():
            cmid_list.append(int(item.strip()))
    return cmid_list
```

**What it does:**
Converts comma-separated string to list of integers.

**Example:**
```
Input (from .env): "QUIZ_CMIDS = 123, 456, 789"
Output: [123, 456, 789]
```

**Why?** .env values are strings. Python functions need integers.

---

#### **BLOCK 8: Moodle API Communication**
```python
def call_moodle_api(self, function_name, **parameters):
    payload = {
        "wstoken": self.token,
        "wsfunction": function_name,
        "moodlewsrestformat": "json",
    }
    # Convert parameters...
    # Retry logic (try 3 times)...
    # Send POST request...
```

**What it does:**
1. Creates a request payload with:
   - Authentication token (wstoken)
   - Function name (which Moodle function to call)
   - Format (JSON)
2. Converts list parameters to Moodle format: `key[0]=val, key[1]=val`
3. Sends POST request with retry logic:
   - Try 1: Send request
   - Fail? Wait 3 seconds, try again
   - Fail again? Wait 3 seconds, try once more
   - Fail 3rd time? Give up and raise error

**Why retry logic?** Networks sometimes have temporary hiccups. Retrying handles those gracefully.

---

#### **BLOCK 9: Fetch Course Modules**
```python
def get_all_modules_in_course(self):
    modules = {}
    sections = self.call_moodle_api("core_course_get_contents", courseid=self.course_id)
    for section in sections:
        for module in section.get("modules", []):
            cmid = module.get("id")
            if cmid:
                modules[int(cmid)] = {
                    "modname": module.get("modname"),
                    "instance": module.get("instance"),
                    "name": module.get("name"),
                }
    return modules
```

**What it does:**
Fetches all modules (quizzes, assignments, forums) from course structure.

**Returns:**
```python
{
    123: {"modname": "quiz", "instance": 1, "name": "Quiz 1"},
    124: {"modname": "assign", "instance": 2, "name": "Assignment 1"},
    125: {"modname": "forum", "instance": 1, "name": "General Forum"},
    ...
}
```

**Why?** We need to know:
- Which CMIDs are quizzes vs assignments (modname)
- The actual instance ID (needed for API calls)
- The display name

---

#### **BLOCK 10: Quiz Export**
```python
def export_quiz_data(self, quiz_cmids, all_modules):
    # For each quiz:
    #   1. Get quiz config (name, max score, etc.)
    #   2. For each student:
    #      a. Get all their attempts
    #      b. Calculate score %, duration, etc.
    #   3. Save all rows to CSV
```

**What it does:**
1. Fetches quiz configurations from Moodle
2. For each quiz to export:
   - Get quiz name, max score, time limit
   - For each student:
     - Fetch their quiz attempts
     - Calculate percentage score
     - Calculate grade (scaled score)
     - Record duration
   - Save all data to CSV

**CSV columns saved:**
- `course_id` - Course ID
- `cmid` - Course module ID
- `quizid` - Quiz ID
- `quiz_name` - Quiz display name
- `anon_user` - Anonymized student ID
- `attemptid` - Attempt ID
- `attempt_no` - Which attempt (1st, 2nd, 3rd)
- `state` - attempt state (finished, inprogress, etc.)
- `timestart`, `timefinish` - Human-readable times
- `started_unix`, `finished_unix` - Unix timestamps
- `duration_seconds` - How long they spent
- `duration_minutes` - In minutes
- `raw_score` - Raw points
- `raw_max` - Max points possible
- `score_pct` - Score as percentage (0-100)
- `scaled_grade` - Letter grade

---

#### **BLOCK 11: Assignment Export**
```python
def export_assignment_data(self, assignment_cmids, all_modules):
    # Similar to quizzes, but:
    # 1. Fetch grades separately (not part of submission data)
    # 2. Calculate time from opening to submission
    # 3. Check if submission is on-time
```

**What it does:**
Fetches assignment submissions and grades.

**Key difference from quizzes:**
- Quizzes: Data comes from attempts
- Assignments: Data split between submissions + grades

**CSV columns:**
- Similar to quizzes
- Plus: `grade`, `duedate`, `time_to_submit_hours`

---

#### **BLOCK 12: H5P, Forums, Databases Export**
These follow similar patterns:
- Fetch data from Moodle API
- Process and transform
- Save to CSV

---

#### **BLOCK 13: Main Orchestration**
```python
def run_export(self):
    # 1. Validate config
    # 2. Clean output folders
    # 3. Test connection
    # 4. Get course modules
    # 5. Parse CMIDs from env
    # 6. Call export functions
    # 7. Report completion
```

**The master workflow:**
- Validates that .env is set up
- Cleans old data
- Tests Moodle connection (fails fast if credentials wrong)
- Gets course structure
- Parses which activities to export
- Calls export functions for each activity type
- Reports completion

---

### **analyse.py - Line by Line**

#### **BLOCK 1: Setup & Configuration**
```python
# Define folders
QUIZ_FOLDER = OUTPUT_FOLDER / "quizzes"
ASSIGN_FOLDER = OUTPUT_FOLDER / "assignments"
# ... etc

# Configure matplotlib for charts
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#F4F7FB",
    # ... styling ...
})
```

**What it does:**
- Sets up output folders for organizing results
- Configures matplotlib (chart library) for consistent styling

**Why consistent styling?** Professional-looking charts that all look like they're from the same project.

---

#### **BLOCK 2: Chart Functions**

**create_score_distribution_histogram()**
```python
# Draws bar chart showing how many students got each score
# Lines for: mean, median, pass threshold
# Shows pass rate percentage
```

**Creates:**
- X-axis: Scores (0-100%)
- Y-axis: Number of students
- Bars: Distribution
- Red line: Mean score
- Orange line: Median
- Green line: Pass threshold (50%)
- Annotation: Pass rate %

**create_pass_fail_comparison_chart()**
```python
# Horizontal stacked bar
# Left side: Passed (green)
# Right side: Failed (red)
# Shows percentages and counts
```

**create_scatter_plot_with_trend()**
```python
# Scatter plot with trend line
# Each dot = one student/attempt
# Trend line shows relationship
# Correlation coefficient (r) shows strength
```

---

#### **BLOCK 3: Quiz Analysis**
```python
def analyze_quiz_data():
    # For each quiz:
    # 1. Create histogram of scores (Insight 1)
    # 2. Create pass/fail breakdown (Insight 2)
    # 3. Analyze time vs score (Insight 3)
    # 4. Save summary CSV
```

**Insights generated:**
- **Insight 1:** Pass rate, mean score, class performance
- **Insight 2:** Number passing vs failing
- **Insight 3:** Does time spent correlate with score?

---

#### **BLOCK 4: Assignment Analysis**
```python
def analyze_assignment_data():
    # For each assignment:
    # 1. Create histogram of grades (Insight 1)
    # 2. Create on-time vs late breakdown (Insight 2)
    # 3. Save summary CSV
```

**Insights generated:**
- **Insight 1:** Mean grade, class performance level
- **Insight 2:** On-time submission rate, late submission count

---

#### **BLOCK 5: Other Activity Analysis**
- H5P: Score distribution, pass rate
- Forums: Post count per student, active vs lurking
- Databases: Entry count per student

---

#### **BLOCK 6: Main Analysis Orchestration**
```python
def main():
    # Check data exists
    # Run analysis for each activity type
    # Report completion
```

---

## Interview Talking Points

### "Tell me about your export.py"

> "Export.py is a class-based script that downloads activity data from Moodle. Here's how it works:
> 
> **1. Configuration:** It loads Moodle credentials from a .env file - the URL, API token, course ID, and which activities to export.
>
> **2. Data Fetching:** For each activity type (quizzes, assignments, forums, etc.), it:
>    - Fetches all students in the course
>    - For each student, fetches their interaction data
>    - Calls Moodle's REST API with retry logic (tries 3 times if network fails)
>
> **3. Data Transformation:** It transforms the raw Moodle data:
>    - Anonymizes student IDs (hashes them so real IDs aren't exposed)
>    - Converts Unix timestamps to readable dates
>    - Calculates derived values (score percentages, grades, duration)
>
> **4. Data Storage:** Saves everything to CSV files organized by activity type:
>    - `quiz_*.csv` - Quiz attempts
>    - `assign_*.csv` - Assignment submissions
>    - `h5p_*.csv` - H5P activities
>    - `forum_*_posts.csv` - Forum posts
>    - `data_*.csv` - Database entries
>
> **Key design choice:** Using a class organization keeps the code maintainable and easy to extend."

### "Tell me about your analyse.py"

> "Analyse.py reads the CSV files exported by export.py and creates visualizations with meaningful insights.
>
> **For each quiz:**
> - Histogram showing score distribution
> - Pass/fail breakdown (percentage who scored ≥50%)
> - Scatter plot: time spent vs score (shows if longer time helps)
>
> **For each assignment:**
> - Histogram of grades
> - On-time vs late submission breakdown
> - Summary statistics
>
> **Insights included:** Each chart has a caption explaining what the data means and what action might be needed (e.g., 'only 40% passed' suggests students need support).
>
> **Technology:** Using matplotlib for charts - customized styling so all charts look professional and consistent."

### "Why is anonymization important?"

> "Privacy protection. Real student IDs shouldn't appear in analysis results. We use SHA-256 hashing:
> - One-way (can't reverse to find real ID)
> - Deterministic (same student always gets same anonymous code)
> - Can still track individual students across data
> - GDPR compliant"

### "How do you handle errors?"

> "We use try-except blocks and retry logic:
> - **API calls:** Retry up to 3 times with 3-second delays (handles network hiccups)
> - **Data parsing:** Use `errors='coerce'` to safely convert values, dropping invalid ones
> - **Validation:** Check configuration before running (fail fast if .env is wrong)
> - **Logging:** Every action is logged with timestamp so we can debug issues"

---

## File Structure

```
output/
├── exports/              ← CSV files from export.py (temporary)
│   ├── quiz_123.csv
│   ├── assign_456.csv
│   ├── h5p_789.csv
│   ├── forum_101_posts.csv
│   └── data_202.csv
│
├── quizzes/             ← Organized quiz analyses
│   ├── quiz_123_score_histogram.png
│   ├── quiz_123_pass_fail.png
│   ├── quiz_123_time_vs_score.png
│   └── ...
│
├── assignments/         ← Organized assignment analyses
│   ├── assign_456_grade_histogram.png
│   ├── assign_456_ontime_split.png
│   └── ...
│
├── h5p/
├── forums/
├── databases/
│
├── summary/             ← Summary CSVs
│   ├── quizzes_summary.csv
│   ├── assignments_summary.csv
│   └── ...
│
└── logs/
    └── run.log         ← Execution log
```

---

## Example .env File

```bash
# Moodle Connection
MOODLE_BASE_URL=https://moodle.example.com
MOODLE_WSTOKEN=your_api_token_here
COURSE_ID=123

# Privacy
HASH_SALT=your_secret_salt_string

# Which activities to export (comma-separated CMIDs)
QUIZ_CMIDS=123, 124, 125
ASSIGN_CMIDS=201, 202
FORUM_CMIDS=301
HVP_CMIDS=401
DATA_CMIDS=501
```

---

## Requirements

```
requests>=2.28.0      # HTTP requests
pandas>=1.5.0         # Data frames
python-dotenv>=0.20   # Load .env files
tqdm>=4.64.0          # Progress bars
matplotlib>=3.5.0     # Charts
numpy>=1.23.0         # Numerical computations
```

---

## Key Insights from Data Analysis

### Quiz Insights
- **Pass Rate:** % who scored ≥50% - indicates overall difficulty
- **Time vs Score Correlation:** Does spending more time help?
  - Positive correlation: More time = higher score (good time management needed)
  - No correlation: Time doesn't matter (focus on understanding, not rushing)
  - Negative correlation: More time = lower score (rushing = better performance?)

### Assignment Insights
- **Mean Grade:** Class average - is it sufficient?
- **On-Time Rate:** % submitted before deadline - time management indicator

### Forum Insights
- **Active vs Lurking:** Engagement levels
- **Posts per Student:** Participation indicator

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Missing configuration in .env" | Create .env file with MOODLE_BASE_URL, MOODLE_WSTOKEN, COURSE_ID |
| "Connection failed" | Check MOODLE_BASE_URL and MOODLE_WSTOKEN in .env |
| "No data in output/exports/" | Make sure QUIZ_CMIDS, ASSIGN_CMIDS are set in .env |
| "Charts not generating" | Check matplotlib is installed: `pip install matplotlib` |
| Empty CSV files | Moodle API might not have data for that activity (no students attempted it) |

---

Good luck with your interview! 🎓
