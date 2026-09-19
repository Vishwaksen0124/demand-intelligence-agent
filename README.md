# Demand Intelligence Agent

Hackathon project for forecasting product demand, calculating inventory actions, and explaining reorder decisions with deterministic logic plus optional Amazon Bedrock narration.

## What it includes

- Synthetic dataset for 20 products and 90 days of sales history
- Deterministic demand forecasting, inventory math, and decision logic
- FastAPI backend with Lambda-ready handler
- React dashboard for analysis and product drill-down
- Optional DynamoDB, S3, and Bedrock integration
- AWS SAM infrastructure for backend deployment

## Local setup

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

Frontend:

```bash
cd frontend
npm install
npm run build
npm run dev
```

Set `VITE_API_BASE_URL` before building the frontend for a deployed API.

## Key docs

- [SPEC.md](SPEC.md)
- [Submission write-up](docs/SUBMISSION_WRITEUP.md)
- [Project architecture](docs/PROJECT_ARCHITECTURE.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/deployment.md](docs/deployment.md)
- [docs/demo.md](docs/demo.md)
- [DEMO.md](DEMO.md)
