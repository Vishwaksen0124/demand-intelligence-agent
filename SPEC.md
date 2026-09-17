# Technical Specification

## Objective

Build a hackathon-friendly demand intelligence system that predicts demand, calculates inventory actions, and explains recommendations without depending on an LLM for numeric results.

## Architecture

- Frontend: React + Vite
- Backend: FastAPI running locally and behind AWS Lambda via Mangum
- AI narration: Amazon Bedrock, with deterministic fallback
- Storage: DynamoDB for analysis snapshots, S3 for exports
- Infra: AWS SAM / CloudFormation
- Scheduled refresh: EventBridge rule invoking the same Lambda

## Core pipeline

1. Load a selected product and its 90-day synthetic sales history.
2. Compute trend, forecast, and confidence with deterministic math.
3. Compute inventory metrics: average demand, safety stock, reorder point, recommended order, and days until stockout.
4. Classify the decision as NORMAL, WATCH, REORDER, or URGENT.
5. Generate an explanation with Bedrock when available, otherwise use a deterministic summary.

## Data model

Each product has:

- id
- name
- category
- current inventory
- supplier lead time in days
- minimum order quantity
- unit cost

Each history record has:

- date
- units sold

## API surface

- GET /health
- GET /products
- GET /products/{id}
- POST /forecast
- POST /inventory/analyze
- POST /decision
- POST /analyze
- GET /alerts

## Guardrails

- No numeric forecast values from the LLM.
- Validation on all request and response models.
- Optional AWS integration must fail closed to deterministic local behavior.
