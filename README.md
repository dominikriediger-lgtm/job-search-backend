# job-search-backend

Backend für Aggregation, Scoring und KI-Anreicherung von Jobangeboten aus APIs und Karriereseiten.

## Setup

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Projektstruktur

```
app/
├── api/routes.py          # FastAPI endpoints
├── core/config.py         # App configuration & scoring weights
├── data/profile_seed.py   # Candidate profile & job clusters
├── models/schemas.py      # Pydantic models (Job, Score, Profile)
├── services/
│   ├── scoring.py         # Weighted scoring engine
│   ├── job_store.py       # Job persistence (in-memory, DB later)
│   └── search.py          # Search query generation
└── main.py                # FastAPI app entry point
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/profile` | Candidate profile |
| GET | `/api/v1/profile/titles` | Target titles by cluster |
| GET | `/api/v1/search/queries` | Generated search queries |
| GET | `/api/v1/search/sources` | Supported job sources |
| POST | `/api/v1/jobs` | Add a job listing |
| POST | `/api/v1/jobs/batch` | Add multiple jobs |
| GET | `/api/v1/jobs` | List all jobs |
| POST | `/api/v1/jobs/score` | Score a single job |
| GET | `/api/v1/jobs/scored/all` | Score & rank all jobs |
| GET | `/api/v1/stats` | Dashboard stats |

## Scoring System

Gewichtung (konfigurierbar via `.env`):
- **Title Match (25%)** – Cluster A > B > C Priorität
- **Company Fit (20%)** – Größe, Sektor, True-Tech Score
- **Location (15%)** – München + Hybrid bevorzugt
- **Tech Depth (15%)** – True Tech vs. GPT-Wrapper Erkennung
- **AI Resilience (15%)** – Zukunftssicherheit der Rolle
- **Salary (10%)** – ≥100k + Equity Bonus
