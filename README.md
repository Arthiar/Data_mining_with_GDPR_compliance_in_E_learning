# Moodle Learning Analytics Pipeline

A Python tool that connects to a Moodle course, downloads student activity data, anonymises identities for GDPR compliance, and generates charts and statistics for analysis.

## Structure

```
code/main/     ← Python scripts (export.py, analyse.py, and helpers)
output/        ← Generated CSV files and charts
```

## How To Run

```bash
# 1. Install dependencies
pip install -r code/main/requirements.txt

# 2. Create your credentials file
cp code/main/.env.example code/main/.env
# Edit .env with your Moodle URL, token, course ID, and activity CMIDs

# 3. Download data from Moodle
python code/main/export.py

# 4. Generate charts and statistics
python code/main/analyse.py
```

## Privacy

Student IDs are anonymised using one-way SHA-256 hashing before any data is saved. The `.env` file containing credentials is never committed to this repository.

See [code/main/README.md](code/main/README.md) for full documentation.
