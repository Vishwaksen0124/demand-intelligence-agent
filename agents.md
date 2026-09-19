# DemandOps AI — AGENTS.md

## Project

Build a complete production-style hackathon application called:

**DemandOps AI — AI-Powered Demand & Inventory Decision Agent**

The system helps businesses forecast regional product demand, calculate inventory requirements, identify stockout/overstock risks, and generate explainable replenishment recommendations.

The system MUST use a human-in-the-loop workflow.

The AI recommends actions.

A human employee reviews, modifies, approves, or rejects those recommendations.

---

# Core Workflow

Customer:

Region + Store + Inventory + Historical Sales
↓
Create Inventory Request
↓
AI Analysis
↓
Demand Forecast
↓
Inventory Calculation
↓
Risk Analysis
↓
Bedrock Decision Agent
↓
AI Recommendation
↓
Employee Review
↓
Approve / Modify / Reject
↓
Final Approved Order

---

# User Roles

## Customer

Can:

* authenticate
* select region
* select city
* select store
* enter current inventory
* upload historical sales
* select forecast horizon
* submit inventory analysis request
* view own requests
* view AI recommendations
* view request status

Cannot:

* approve orders
* reject orders
* modify employee decisions
* access other customers' requests

## Employee / Manager

Can:

* authenticate
* view pending requests
* view requests for permitted regions
* inspect AI recommendations
* inspect forecast
* inspect calculations
* inspect AI reasoning
* modify quantities
* modify priority
* add/remove products
* add comments
* approve
* reject
* view audit history
* view regional inventory analytics

## Admin

Optional if time permits.

Can:

* manage users
* manage products
* manage stores
* manage regions
* view all requests

---

# Authentication

Use Amazon Cognito.

Frontend authenticates users through Cognito.

API Gateway passes authenticated identity to Lambda.

Lambda MUST enforce authorization.

Do not rely only on hiding frontend buttons.

Roles must be enforced server-side.

---

# Regional Model

Region is a first-class business attribute.

Every inventory request must contain:

* country
* state
* city
* store_id

Example:

{
"country": "India",
"state": "Karnataka",
"city": "Bangalore",
"store_id": "BLR-042"
}

Historical sales must also contain regional/store information.

Forecasting must use the relevant regional/store dataset.

---

# Customer Request

Request schema:

{
"request_id": "REQ-10291",

"region": {
"country": "India",
"state": "Karnataka",
"city": "Bangalore",
"store_id": "BLR-042"
},

"forecast_horizon_days": 7,

"inventory": [
{
"product_id": "P001",
"product_name": "Milk",
"current_stock": 32,
"unit_cost": 40,
"supplier_lead_time_days": 2,
"minimum_order_quantity": 10
}
],

"historical_sales_source": "S3",

"constraints": {
"max_purchase_budget": 50000
}
}

Inventory MUST be request-specific.

Do not hardcode inventory values.

---

# Historical Sales

Create a realistic synthetic dataset.

At minimum:

* 20 products
* 90 days
* multiple regions
* multiple stores
* different demand patterns

Include:

* stable products
* increasing products
* decreasing products
* seasonal products
* weekend effects
* demand spikes

Dataset must be clearly documented as synthetic.

---

# Forecasting

Create a deterministic Python forecasting engine.

The LLM must NOT invent numerical forecasts.

Forecast engine should consider where supported:

* historical demand
* recent trend
* moving averages
* weighted recent demand
* weekly seasonality
* demand variability
* regional/store patterns

Output:

{
"forecast_7_day": 95,
"forecast_14_day": 190,
"trend": "increasing",
"confidence": 0.87
}

Keep the implementation transparent and testable.

---

# Inventory Calculation Engine

Implement deterministic Python calculations.

Calculate:

* average daily demand
* demand during lead time
* demand variability
* safety stock
* reorder point
* days until stockout
* recommended order quantity
* overstock quantity
* stockout risk

Do not use the LLM for arithmetic.

Every recommendation must be reproducible.

---

# Decision Agent

Use Amazon Bedrock for reasoning and explanation.

The Decision Agent receives structured calculated facts.

Example:

{
"product": "Eggs",
"region": "Bangalore",
"current_stock": 40,
"forecast_7_day": 95,
"reorder_point": 43,
"safety_stock": 15,
"days_until_stockout": 2.8,
"recommended_order": 70,
"forecast_confidence": 0.87
}

Return structured JSON:

{
"status": "URGENT",
"priority": "HIGH",
"recommended_quantity": 70,
"reason": "...",
"risks": [],
"confidence": 0.87
}

Validate all Bedrock outputs.

The LLM must explain calculated facts rather than inventing numerical values.

---

# Risk Classification

Support:

* NORMAL
* WATCH
* REORDER
* URGENT
* OVERSTOCK

Stockout and overstock calculations must be deterministic.

---

# Human Review

Every AI recommendation MUST enter:

REVIEW_REQUIRED

The AI MUST NOT directly finalize an order.

Employee can:

* approve
* reject
* modify quantity
* modify priority
* remove products
* add products
* add comments

When modified, preserve both:

AI recommendation
Manager decision

Example:

AI quantity: 71
Manager quantity: 60
Modified: true
Modification reason: "Supplier shipment arriving tomorrow"

---

# Audit Trail

Record:

* request creator
* AI recommendation
* AI reasoning
* AI confidence
* manager
* manager decision
* original quantity
* final quantity
* modification
* modification reason
* timestamp

Never overwrite the original AI recommendation.

---

# Request State Machine

Support:

DRAFT
SUBMITTED
ANALYZING
AI_RECOMMENDED
REVIEW_REQUIRED
MODIFIED
APPROVED
REJECTED
ORDER_READY
FULFILLED

---

# AWS Architecture

Use:

* Amazon Cognito
* AWS Amplify Hosting
* Amazon API Gateway
* AWS Lambda
* Amazon Bedrock
* Amazon DynamoDB
* Amazon S3
* Amazon EventBridge
* Amazon CloudWatch
* AWS IAM
* AWS SAM / CloudFormation

Do not add unnecessary AWS services.

Infrastructure MUST be defined as code.

---

# DynamoDB Entities

Create logical data models for:

Users
Products
Stores
Inventory
Sales
Requests
Forecasts
Recommendations
AuditEvents

Ensure requests and recommendations can be queried efficiently by region/store/status.

---

# S3

Use S3 for:

* historical sales CSV
* uploaded datasets
* generated reports if required

Never store AWS credentials in S3 or source code.

---

# API

Implement:

POST /requests
GET /requests
GET /requests/{id}

POST /requests/{id}/analyze

GET /requests/{id}/forecast

GET /requests/{id}/recommendations

POST /recommendations/{id}/approve

POST /recommendations/{id}/reject

POST /recommendations/{id}/modify

GET /requests/{id}/audit

GET /products

GET /stores

GET /regions

GET /alerts

GET /analytics

GET /health

Enforce authorization for every endpoint.

---

# Customer Dashboard

Create:

## Overview

* requests created
* requests processing
* requests awaiting approval
* approved requests

## Create Request

Fields:

* country
* state
* city
* store
* forecast period
* historical sales upload
* inventory table
* budget constraint

## Request Details

Show:

* AI status
* forecast
* inventory
* recommendations
* request status

---

# Employee Dashboard

Create:

## Review Queue

Show:

* pending requests
* urgent requests
* region
* store
* requester
* estimated purchase value

## Review Request

Show:

* region
* store
* all products
* forecast
* inventory
* risk
* AI recommendation
* reasoning
* confidence

Employee actions:

APPROVE
MODIFY
REJECT

---

# Product Review

For each product show:

Current stock
Forecast
Average daily demand
Safety stock
Reorder point
Days until stockout
AI recommended quantity
AI reasoning
Risk
Confidence

Allow employee to modify:

quantity
priority
status

Allow comments.

---

# Manager Analytics

Display:

* stockout risks
* overstock risks
* pending approvals
* total recommended purchase value
* approved purchase value
* modified recommendations
* regional demand trends

---

# Frontend

Use React.

Keep UI professional and demo-ready.

Important screens:

1. Login
2. Customer dashboard
3. Create request
4. Request details
5. Employee review dashboard
6. Employee request review
7. Analytics
8. Product details

Use charts for historical demand and forecasts.

---

# EventBridge

If time permits, implement scheduled monitoring.

Example:

Daily:

EventBridge
↓
Lambda
↓
Analyze active inventory
↓
Detect risks
↓
Create alerts
↓
Employee dashboard

This should not block the core MVP.

---

# Testing

Create tests for:

* forecasting
* regional filtering
* safety stock
* reorder point
* order quantity
* stockout risk
* overstock risk
* decision classification
* authentication
* authorization
* customer permissions
* employee permissions
* approval
* modification
* rejection
* audit trail

Create an end-to-end test covering:

Customer → Request → AI → Recommendation → Employee → Approval

---

# Security

Never hardcode:

* AWS credentials
* API keys
* secrets

Use Cognito/IAM/environment configuration.

Do not commit .env.

Use least-privilege IAM policies.

Validate all user inputs.

Validate all AI outputs.

---

# Deployment

Use AWS SAM / CloudFormation for backend infrastructure.

Use Amplify Hosting for frontend deployment.

Deployment must be reproducible.

The coding agent may use AWS CLI.

Before creating resources, inspect:

aws sts get-caller-identity
aws configure list
aws configure get region

Never delete unrelated AWS resources.

Never use destructive commands unless explicitly required.

---

# Development Strategy

Build in this order:

1. Repository structure
2. Data models
3. Synthetic data
4. Forecast engine
5. Inventory calculation engine
6. Risk engine
7. Backend APIs
8. DynamoDB
9. S3
10. Cognito
11. Bedrock Decision Agent
12. Human approval workflow
13. React customer dashboard
14. React employee dashboard
15. AWS infrastructure
16. Deployment
17. End-to-end testing
18. Documentation
19. Demo preparation

Do not build the UI before the core backend workflow works.

Do not stop after creating boilerplate.

---

# Completion Criteria

The project is complete only when:

[ ] Customer can log in
[ ] Employee can log in
[ ] Roles are enforced
[ ] Region can be selected
[ ] Store can be selected
[ ] Customer can enter different inventory
[ ] Historical sales can be uploaded
[ ] Forecast works
[ ] Inventory calculation works
[ ] Stockout detection works
[ ] Overstock detection works
[ ] Bedrock reasoning works
[ ] AI recommendation works
[ ] Employee review dashboard works
[ ] Employee can inspect reasoning
[ ] Employee can modify quantity
[ ] Employee can approve
[ ] Employee can reject
[ ] Audit trail works
[ ] DynamoDB works
[ ] S3 works
[ ] Cognito works
[ ] API Gateway works
[ ] Lambda works
[ ] Amplify deployment works
[ ] Tests pass
[ ] AWS deployment works
[ ] README is complete
[ ] Architecture documentation is complete
[ ] Demo script is complete

---

# Demo Story

The final 3-minute demo should show:

1. Customer logs in
2. Customer selects Bangalore
3. Customer selects a store
4. Customer enters/upload inventory
5. Customer submits request
6. AI analyzes demand
7. Forecast appears
8. AI calculates inventory requirement
9. AI identifies stockout risk
10. AI recommends an order
11. Employee logs in
12. Employee opens review queue
13. Employee opens the AI recommendation
14. Employee inspects reasoning and calculations
15. Employee changes one quantity
16. Employee approves the request
17. Audit trail shows AI quantity vs approved quantity
18. Show AWS architecture
19. Explain that AI recommends while humans remain in control

Final message:

**"DemandOps AI turns demand forecasts into explainable inventory decisions — with humans always in control."**
