# DemandOps AI

## Problem

Inventory teams often make purchasing decisions using fragmented historical sales data, changing demand, and limited visibility into future stockout risks. This can lead to overstocking, stockouts, and purchasing decisions that are difficult to explain.

## Solution

DemandOps AI is an AI-powered demand and inventory decision platform that analyzes historical demand, identifies trends, forecasts future requirements, calculates inventory risk, and provides explainable AI recommendations.

The key principle is:

> **AI recommends. Humans decide.**

The system never allows AI to automatically approve or place an order. An employee reviews each recommendation and can modify, approve, or reject it.

## How It Works

```text
Historical Sales Dataset
        ↓
Demand & Trend Analysis
        ↓
Deterministic Forecast
        ↓
Inventory Calculations
        ↓
Risk Analysis
        ↓
Amazon Bedrock Mantle
        ↓
AI Recommendation
        ↓
Employee Review
        ↓
Modify / Approve / Reject
        ↓
Audit Trail
```

Historical sales are maintained by the backend. Customers do not upload historical data.

For each customer request, the backend automatically loads relevant demand history for the requested products and store/region, analyzes trends, and generates a deterministic forecast.

The system calculates:

- average daily demand;
- safety stock;
- reorder point;
- days until stockout;
- recommended order quantity;
- stockout risk;
- overstock risk.

These deterministic results are provided to Amazon Bedrock Mantle, which generates an explainable recommendation containing priority, reasoning, confidence, and recommended quantity.

## Human-in-the-Loop

DemandOps separates three layers:

### System Calculation

```text
Calculated Order Quantity: 110
```

### AI Recommendation

```text
Recommended Quantity: 110
Priority: HIGH
Confidence: 89.9%
```

### Employee Decision

```text
Final Quantity: 60
Decision: APPROVED
```

The original AI recommendation is preserved even when an employee modifies it. Every important action is recorded in an append-oriented audit trail.

## AWS Architecture

```text
Amplify-hosted React frontend
        |
        | Cognito JWT
        v
API Gateway
        |
        v
AWS Lambda / FastAPI
   |       |        |          |
   |       |        |          +--> Bedrock Mantle / GPT-OSS-20B
   |       |        +-------------> S3
   |       +----------------------> DynamoDB
   +------------------------------> CloudWatch

EventBridge daily schedule
        |
        v
Monitoring Lambda → risk calculation → persisted alerts
```

DemandOps uses:

- **Amazon Bedrock Mantle** for AI reasoning and recommendations;
- **AWS Lambda** for backend processing;
- **Amazon API Gateway** for APIs;
- **Amazon DynamoDB** for persistent application state;
- **Amazon Cognito** for authentication and authorization;
- **Amazon S3** for application/data storage where applicable;
- **Amazon EventBridge** for scheduled inventory monitoring;
- **AWS Amplify** for frontend deployment;
- **Amazon CloudWatch** for logging and observability;
- **AWS IAM** for access control.

Production region: `us-east-2`.

## Why AI?

Traditional forecasting and inventory calculations remain deterministic and explainable.

AI is used where it provides additional value: interpreting operational facts, prioritizing risks, explaining recommendations, and providing context for the employee.

This prevents the AI from inventing inventory numbers or silently making purchasing decisions.

## Key Features

### Customer

- secure Cognito authentication;
- region and store selection;
- dynamic product inventory;
- forecast horizon selection;
- request creation and tracking;
- forecast and risk visibility;
- AI recommendation visibility.

Historical sales are backend-owned. The customer request contains only location, products, current inventory, forecast horizon, and optional budget.

### Employee

- review queue;
- risk prioritization;
- demand and forecast analysis;
- AI recommendation reasoning;
- recommendation modification;
- approval and rejection;
- alerts and analytics;
- complete audit history.

## Security and Trust

Amazon Cognito issues JWTs. The backend derives user identity and role from validated claims rather than trusting frontend-supplied identity fields.

Customers can access only their own requests. Employee actions are protected server-side. Customers cannot modify, approve, reject, or access employee-only workflows.

## Impact

DemandOps AI turns historical demand data into actionable inventory intelligence while keeping the final decision with a human operator.

It provides a transparent chain:

**Historical Data → Forecast → Inventory Math → Risk → AI Reasoning → Human Decision**

rather than treating AI as a black-box autonomous ordering system.

## Deployment and Demo

- Repository: https://github.com/Vishwaksen0124/demand-intelligence-agent
- Frontend: https://main.d2ywbbgebajkuj.amplifyapp.com
- API: `https://fvlyc576k7.execute-api.us-east-2.amazonaws.com/Prod`
- Dataset: `backend/data/synthetic_dataset.json`
- AI model: `openai.gpt-oss-20b` through Bedrock Mantle
- Tests: 34 backend tests passing

The complete demo is:

```text
Customer login
→ Create request
→ Deterministic forecast and inventory analysis
→ Bedrock Mantle recommendation
→ Employee review
→ Modification or approval/rejection
→ Persisted audit trail
```
