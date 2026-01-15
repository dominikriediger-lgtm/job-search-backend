# job-search-backend

Backend für Aggregation, Scoring und KI-Anreicherung von Jobangeboten aus APIs und Karriereseiten.

## Setup

### Requirements

- Python 3.10+

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /hello` - Hello endpoint with basic info
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Development

The server runs on `http://localhost:8000` by default.

CORS is currently configured to allow all origins (`*`) for development. This should be restricted in production.
