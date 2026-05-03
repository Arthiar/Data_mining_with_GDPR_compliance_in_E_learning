# Data Mining with GDPR Compliance in E-Learning

This repository contains the Python code for a project about privacy-aware data mining in Moodle e-learning courses.

The project collects learning activity data from Moodle, removes direct user identity by replacing user IDs with salted SHA-256 hash values, and creates CSV summaries and charts for learning analytics.

Author and contributor: Arthiar

## What This Code Does

The code has two main steps:

1. `export.py` connects to Moodle through the Moodle REST API and exports selected course activity data to CSV files.
2. `analyse.py` reads those CSV files, creates anonymised statistics, generates charts, and writes summary CSV files.

There is also a demo script:

3. `generate_demo_data.py` creates fake sample data so the analysis can be tested without connecting to a real Moodle server.

## Main Features

- Exports Moodle activity data for quizzes, assignments, H5P activities, forums, and database activities.
- Uses a local secret salt to pseudonymise user IDs.
- Does not export names, email addresses, or direct personal identifiers.
- Creates CSV files and visual charts for analysis.
- Keeps secret configuration files out of Git.

## Project Files

```text
Course_1516_Python_Script/
  export.py              Export selected data from Moodle
  analyse.py             Analyse exported CSV files and create charts
  generate_demo_data.py  Create fake demo data for testing
  requirements.txt       Python packages needed by the project
  .env.example           Example configuration file
  .gitignore             Prevents secrets and generated files from being committed
  README.md              Project explanation and setup guide
```

Generated CSV files and charts are written to the `output/` folder. The repository includes the current anonymised output results as evidence of the analysis. Runtime logs and temporary export files are still ignored.

## Important Security Note

Do not commit the real `.env` file.

The `.env` file contains private Moodle settings such as:

- Moodle URL
- Moodle web service token
- course ID
- activity IDs
- hash salt used for pseudonymisation

Only `.env.example` is included in Git. It is a template and does not contain real secrets.

## Requirements

- Python 3.9 or newer
- A Moodle site with Web Services enabled
- A Moodle web service token with access to the needed course functions

Install the Python packages from `requirements.txt`.

## Step-by-Step Setup

### 1. Clone the repository

```bash
git clone https://github.com/Arthiar/Data_mining_with_GDPR_compliance_in_E_learning.git
cd Data_mining_with_GDPR_compliance_in_E_learning
```

### 2. Create a virtual environment

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

On macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your private `.env` file

Copy the example file:

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

Then open `.env` and fill in your real Moodle details:

```text
MOODLE_BASE_URL=https://your-moodle-instance.example.com
MOODLE_WSTOKEN=your_real_moodle_token
COURSE_ID=1234
QUIZ_CMIDS=111,222
ASSIGN_CMIDS=333,444
FORUM_CMIDS=
HVP_CMIDS=555
DATA_CMIDS=666
HASH_SALT=use_a_long_private_random_string_here
```

Keep `HASH_SALT` secret. It is used to create the same anonymous user code every time, without storing the original user ID.

## How to Run with a Real Moodle Course

Run the export first:

```bash
python export.py
```

This creates temporary exported CSV files in:

```text
output/exports/
```

Then run the analysis:

```bash
python analyse.py
```

This creates organised results and charts in:

```text
output/quizzes/
output/assignments/
output/h5p/
output/forums/
output/databases/
output/summary/
```

## How to Run Without Moodle

If you only want to test the analysis part, use the demo data script:

```bash
python generate_demo_data.py
python analyse.py
```

This creates fake learning activity data and then generates the same kind of charts and summaries.

## Output Examples

The analysis can create outputs such as:

- score distribution charts
- pass/fail charts
- time spent vs score charts
- assignment grade charts
- on-time vs late submission charts
- forum participation charts
- summary CSV files for all activity types

The current anonymised generated output is included in Git. Runtime logs and temporary export files are not included.

## GDPR and Privacy Approach

This project follows basic GDPR-aware design ideas:

- Data minimisation: only data needed for analysis is collected.
- Pseudonymisation: Moodle user IDs are converted into salted SHA-256 hash values.
- No direct identifiers: names and emails are not saved in the output.
- Local secrets: Moodle token and hash salt stay only in the local `.env` file.
- Reproducible outputs: generated CSV files and charts can be recreated by running the scripts.

This code is for academic and demonstration use. It should be reviewed carefully before being used in a real production environment.
