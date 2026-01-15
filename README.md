# job-search-backend
Backend für Aggregation, Scoring und KI-Anreicherung von Jobangeboten aus APIs und Karriereseiten.

## Setup
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

## Run
python3 -m uvicorn app.main:app --reload
