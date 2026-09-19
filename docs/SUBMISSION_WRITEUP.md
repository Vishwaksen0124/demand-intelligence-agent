# DemandOps AI

## AI-powered demand intelligence with humans in control

DemandOps AI helps retail and operations teams make faster, safer inventory decisions. It combines backend-owned historical demand data, deterministic forecasting, inventory mathematics, and Bedrock Mantle reasoning into one auditable workflow.

> **AI recommends. Humans decide.**

## The problem

Inventory teams often work across disconnected spreadsheets, incomplete demand signals, and opaque recommendations. This creates two expensive failure modes:

- stockouts when demand rises faster than replenishment decisions;
- overstock when teams order without a reliable view of demand, lead time, and safety stock.

The operational challenge is not just producing a forecast. Teams need to understand why an action is recommended, verify the numbers, and retain a clear record of who made the final decision.

## Our solution

DemandOps AI creates a request-specific decision workspace:

1. A customer selects a business region and store, adds products, enters current inventory, and chooses a forecast horizon.
2. The backend loads and filters historical demand data automatically. Customers never upload or manually provide historical sales.
3. Deterministic Python services calculate trend, forecast demand, safety stock, reorder point, stockout timing, order quantity, and risk.
4. Bedrock Mantle receives structured facts and generates an explainable recommendation.
5. An employee reviews the recommendation, can modify the quantity or priority, and explicitly approves or rejects it.
6. Every important transition is persisted in an append-oriented audit trail.

The system separates three layers clearly:

| Layer | Responsibility |
| --- | --- |
| System calculation | Forecast and inventory mathematics |
| AI recommendation | Reasoning, explanation, risk interpretation |
| Employee decision | Modify, approve, or reject |

## Why this approach is trustworthy

The model is not asked to perform arithmetic. Forecast quantity, safety stock, reorder point, and recommended order quantity are calculated by deterministic backend code. Bedrock Mantle reasons over those supplied facts and cannot approve an order.

The original AI recommendation is preserved when an employee modifies it. For example:

```text
AI recommendation:       70 units
Employee decision:        60 units
Modification reason:      Supplier shipment arriving tomorrow.
Final decision:           APPROVED
```

This gives the team both explainability and accountability.

## Architecture

```text
Customer / Employee
        |
        v
Amplify-hosted React frontend
        |
        | Cognito JWT
        v
API Gateway
        |
        v
Lambda + FastAPI
   |       |        |          |
   |       |        |          +--> Bedrock Mantle / GPT-OSS-20B
   |       |        +-------------> S3
   |       +----------------------> DynamoDB
   +------------------------------> CloudWatch

EventBridge daily schedule
        |
        v
Inventory monitoring Lambda --> risk calculation --> persisted alerts
```

## AWS implementation

- **Amazon Cognito** authenticates customers and employees with JWTs and role groups.
- **Amazon API Gateway** exposes the protected production API.
- **AWS Lambda** runs the FastAPI application and the scheduled monitoring workflow.
- **Amazon DynamoDB** persists requests, forecasts, recommendations, audit events, alerts, and analysis records using the deployed single-table design.
- **Amazon S3** supports configured application artifacts and dataset/file storage.
- **Amazon Bedrock Mantle** provides the production AI reasoning path through the OpenAI-compatible API using AWS SigV4.
- **Amazon EventBridge** runs daily inventory monitoring without approving or placing orders.
- **Amazon CloudWatch** receives Lambda execution and error logs.
- **AWS SAM/CloudFormation** defines the backend infrastructure reproducibly.
- **AWS Amplify** hosts the React frontend.

Production region: `us-east-2`.

## Historical demand data

Historical sales are backend-owned. The current deployed dataset is `backend/data/synthetic_dataset.json`. The backend checks persisted store/product sales where available and falls back to product-level history when store-specific history is unavailable.

The frontend sends only customer-owned request information:

- country, state, city, and business region;
- store;
- products and current inventory;
- forecast horizon;
- optional budget.

It does not send historical rows, CSV contents, forecasts, risk values, or AI recommendations.

## Employee control loop

Employees receive a review queue filtered by region, store, status, and priority. The review view surfaces:

- current inventory;
- demand trend and forecast;
- safety stock and reorder point;
- days until stockout;
- calculated order quantity;
- risk classification;
- AI reasoning and confidence;
- complete audit history.

Approval and rejection are employee-only actions. Customers can view their own requests but cannot access employee analytics, modify recommendations, approve, or reject.

## Autonomous monitoring

The daily EventBridge workflow independently scans active inventory, calculates risk, and persists alerts for employee review. It never automatically approves a recommendation or places an order. This preserves human control even when monitoring is automated.

## Demonstration flow

### Customer

1. Sign in with Cognito.
2. Select Bangalore / South India / BLR-042.
3. Add multiple products with different current inventory values.
4. Choose a seven- or fourteen-day horizon.
5. Submit the request.
6. Review the deterministic forecast, inventory metrics, risk, and AI recommendation.

### Employee

1. Sign in with the employee Cognito account.
2. Open the review queue.
3. Inspect the request and calculations.
4. Change the recommended quantity from 70 to 60.
5. Add a business reason.
6. Approve or reject the final decision.
7. Verify the append-only audit timeline.

## Results

- 34 backend tests passing.
- Cognito JWT authentication and server-side role enforcement.
- Persistent request, forecast, recommendation, and audit workflow.
- Deterministic forecast and inventory calculations.
- Bedrock Mantle integration using `openai.gpt-oss-20b`.
- Employee modification, approval, and rejection workflow.
- Daily EventBridge monitoring and persisted alerts.
- Production frontend deployed through Amplify.

## What makes DemandOps AI different

DemandOps AI is designed around the operational decision, not just the prediction. It combines:

- quantitative calculations teams can inspect;
- AI reasoning teams can understand;
- employee control teams can trust;
- audit history teams can prove.

The result is an AI-assisted inventory system that is useful in the moment and accountable after the decision is made.

## Repository and demo

- Repository: https://github.com/Vishwaksen0124/demand-intelligence-agent
- Frontend: https://main.d2ywbbgebajkuj.amplifyapp.com
- API: https://fvlyc576k7.execute-api.us-east-2.amazonaws.com/Prod
- Architecture details: [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)
- Demo notes: [demo.md](demo.md)
