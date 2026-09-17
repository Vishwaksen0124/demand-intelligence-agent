# DemandOps AI — Architecture and End-to-End Flow

## Product principle

DemandOps AI combines backend-owned historical demand data, deterministic forecasting and inventory mathematics, Bedrock Mantle reasoning, and human approval. **AI recommends. Humans decide.**

## Runtime architecture

```text
Amplify-hosted React frontend
        |
        | Cognito JWT / HTTPS JSON
        v
API Gateway (Prod)
        |
        v
AWS Lambda / FastAPI
   |          |             |              |
   |          |             |              +--> Bedrock Mantle / GPT-OSS-20B
   |          |             +-----------------> S3 dataset/files
   |          +-------------------------------> DynamoDB single table
   +------------------------------------------> CloudWatch

EventBridge rate(1 day) --> monitoring Lambda --> risk calculation --> alerts
```

## Authentication and authorization

The frontend authenticates with Amazon Cognito and sends a bearer JWT. The backend derives `user_id`, email, and role from validated Cognito claims. Customer access is ownership-scoped; employee and admin operations are protected by reusable authorization dependencies. Frontend role visibility is only a usability feature; backend authorization remains authoritative.

## Customer workflow

1. Customer selects business region, city/store, products, current inventory, forecast horizon, and optional budget.
2. The browser sends only customer-owned request data. It never sends historical sales, forecast values, inventory calculations, risk, or AI output.
3. Lambda validates the region/store/product relationship, creates the request, persists it, and records audit events.
4. Analysis loads backend-owned history from persisted store/product sales where available, falling back to `backend/data/synthetic_dataset.json` product history.
5. History is filtered and processed deterministically into trend, forecast, confidence, inventory metrics, and risk.
6. Structured deterministic facts are sent to Bedrock Mantle. The validated response is stored as an advisory AI recommendation.
7. The request enters `REVIEW_REQUIRED`.

## Employee workflow

Employees retrieve the review queue, inspect calculations and AI reasoning, then modify, approve, or reject. Manager fields are separate from AI fields, so an employee quantity never overwrites the original AI recommendation. Every transition is append-recorded in the audit trail.

## Persistence model

The deployed DynamoDB table uses a single-table layout with `pk`/`sk` plus `GSI1`. Logical entities include requests, forecasts, recommendations, audit events, alerts, and persisted analyses. S3 stores configured files and analysis artifacts. The frontend has no production in-memory state dependency.

## Deterministic analysis

Forecasting, average demand, variability, safety stock, reorder point, stockout days, recommended order, overstock, and risk classification are calculated in Python. Mantle receives derived facts for explanation and classification; it does not perform arithmetic or approve orders.

## AWS deployment

- Region: `us-east-2`
- CloudFormation/SAM stack: `demand-intelligence-agent`
- API: `https://fvlyc576k7.execute-api.us-east-2.amazonaws.com/Prod`
- Amplify app: `d2ywbbgebajkuj`, branch `main`
- Cognito pool: `us-east-2_4Zn2PGaw6`
- Mantle endpoint: `https://bedrock-mantle.us-east-2.api.aws/v1`
- Mantle model: `openai.gpt-oss-20b`

## Local development

Copy `.env.example` to `.env` and fill only local values. Real credentials must come from the AWS CLI environment, IAM roles, or deployment configuration; they must never be committed. Build the frontend with the appropriate `VITE_*` values and deploy the backend through `infra/template.yaml`.
