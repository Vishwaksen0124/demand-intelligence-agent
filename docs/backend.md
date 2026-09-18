# Backend data model and persistence

The backend uses validated Pydantic entities in `backend/app/core/models.py` and a repository interface in `backend/app/core/data.py`. The local adapter is in-memory for deterministic tests; production persistence is DynamoDB.

Entities are User, Region, Store, Product, Inventory, Sale, InventoryRequest, Forecast, Recommendation, and AuditEvent. Inventory is keyed by `(store_id, product_id)`, and each Sale stores `store_id`, `region_id`, and `product_id`, so quantities and history remain store-specific.

Recommendations retain immutable AI fields (`ai_status`, `ai_priority`, `ai_quantity`, `ai_reason`, `ai_risks`, `ai_confidence`). Manager review is separate (`manager_quantity`, `manager_priority`, `manager_decision`, `manager_comment`, `reviewed_by`, `reviewed_at`, and `modified`). Audit events record request state changes and review actions.

## DynamoDB design

`infra/template.yaml` provisions one PAY_PER_REQUEST single-table DynamoDB table. Items use `pk` and `sk`; `GSI1` supports alternate access patterns with `gsi1pk` and `gsi1sk`:

- `USER#<user_id>` / `PROFILE`
- `REGION#<region_id>` / `PROFILE`
- `STORE#<store_id>` / `PROFILE`
- `PRODUCT#<product_id>` / `PROFILE`
- `INVENTORY#<store_id>` / `PRODUCT#<product_id>`
- `SALE#<sales_id>` / `DATE#<timestamp>`
- `REQUEST#<request_id>` / `META`, with GSI keys for creator, region/store, and status
- `REQUEST#<request_id>` / `FORECAST#<forecast_id>`
- `REQUEST#<request_id>` / `RECOMMENDATION#<recommendation_id>`
- `REQUEST#<request_id>` / `AUDIT#<timestamp>#<event_id>`

GSI1 enables queries by request, creator, region, store, status, product, and timestamp without creating one table per entity. The current local repository mirrors the required create/get/list access patterns and rejects invalid foreign references and negative quantities.

The existing analysis snapshot table name and S3 analysis artifacts remain compatible with the current analytics pipeline; the workflow entities should be persisted through the same table adapter when production repository wiring is completed.


## Customer request workflow

`POST /requests` requires authenticated identity headers locally (or a Cognito bearer token in production). The server derives `created_by` from that identity, validates the supplied region/store relationship, validates every product and inventory quantity, requires at least one inventory row, records `REQUEST_CREATED`, and immediately transitions the request to `SUBMITTED` with `REQUEST_SUBMITTED`.

Customers can list and retrieve only their own requests. Employee/admin access is role-gated. Request responses retain the frontend contract: `GET /requests` returns `{requests: [...]}`, request detail returns an `InventoryRequest`, forecast returns `{request_id, forecasts: [...]}`, recommendations returns `{request_id, recommendations: [...]}`, and audit returns `{request_id, events: [...]}`.

Inventory used for request forecasts and recommendations comes from each submitted request row, not the global catalog quantity. Region and store catalogs are returned with the country/state/city/store fields required to build the frontend request payload.


## Forecast and inventory formulas

Request analysis uses the existing deterministic forecast engine. It takes the most recent 14 observations (or all available observations), computes the mean daily demand and endpoint slope, and projects each requested day as `max(0, mean + slope * step)`. Confidence is bounded between 0.40 and 0.95 from history length and volatility. Store-level sales are filtered by the exact `region_id + store_id + product_id` scope before conversion to forecast history; the bundled synthetic catalog is used only when no scoped sales have been ingested yet.

Inventory calculations use the request inventory snapshot and product supplier data:

- `average_daily_demand = mean(last 14 sales)`
- `lead_time_demand = average_daily_demand * supplier_lead_time_days`
- `demand_variability = population standard deviation(last 14 sales)`
- `safety_stock = ceil(demand_variability * sqrt(lead_time_days) * z)` where z is 0.84/1.28/1.65 by confidence
- `reorder_point = ceil(lead_time_demand + safety_stock)`
- `target_stock = ceil(max(average_daily_demand, forecast_quantity / horizon) * max(lead_time_days + horizon, 14))`
- `recommended_order = max(0, target_stock - current_inventory)`, rounded up to MOQ when positive but below MOQ
- `overstock_quantity = max(0, current_inventory - target_stock)`
- `days_until_stockout = current_inventory / average_daily_demand`, or infinity for zero demand

`stockout_risk` is true when inventory is at or below reorder point; `overstock_risk` is true when overstock quantity is positive. Risk classification is deterministic: OVERSTOCK takes precedence when there is no stockout risk, followed by URGENT, REORDER, WATCH, and NORMAL. Forecast and calculation snapshots are stored at analysis time and reused by the request forecast endpoint.

## Bedrock decision agent

Request analysis performs all forecast, inventory, and risk arithmetic in Python first. It then sends structured facts—including product, store/region, current stock, forecast, safety stock, reorder point, stockout days, deterministic quantity, supplier lead time, and confidence—to the configured `BEDROCK_MODEL_ID` through the existing Bedrock Converse client.

Bedrock must return JSON with `status`, `priority`, `recommended_quantity`, `reason`, `risks`, and `confidence`. `DecisionAgentResponse` validates the fields and bounds; the returned quantity must exactly match the deterministic backend quantity. Invalid JSON, missing fields, invalid enum values, invalid quantity, confidence, or changed quantity raises a controlled decision-agent error. No recommendation is stored on failure, an `AI_RECOMMENDATION_FAILED` audit event is recorded, and the request returns to `SUBMITTED` rather than being marked review-ready.

When Bedrock is not configured, local development uses the already calculated deterministic decision as a structured fallback. The agent never approves orders; successful analysis stores the AI recommendation and transitions the request to `REVIEW_REQUIRED` for employee review.

## Employee/manager review workflow

Employees and admins can use `GET /employee/requests` with `region`, `city`, `store`, `status`, and `priority` filters. The queue returns only reviewable states (`SUBMITTED`, `ANALYZING`, `REVIEW_REQUIRED`, and `MODIFIED`) and is role protected. The existing `/requests` endpoint remains compatible with the frontend and returns all employee-visible requests.

Approve, reject, and modify operations are restricted to employee/admin identities and require the recommendation’s request to be `REVIEW_REQUIRED` or `MODIFIED`. AI fields are never overwritten. Modification stores manager quantity/priority/comment and sets `MODIFIED`; approval records reviewer/timestamp and uses manager quantity when present. Rejection requires a comment and stores the manager decision, reviewer, timestamp, and comment. Audit metadata includes both AI and manager quantities so an approval such as AI 70 / manager 60 is explicit.

## Authentication and authorization

`get_current_identity` is the shared authentication dependency used by `require_roles`. When Cognito configuration is present, every protected route requires a valid `Authorization: Bearer <JWT>` token; `sub`/username and role claims (`custom:role`, `role`, or Cognito groups) are used for identity and role. Spoofable `X-User-*` headers are rejected in that mode. Header identity remains only as the local test/development adapter when Cognito is not configured.

Missing or invalid authentication returns 401. A valid identity without the required role returns 403. Customers are owner-scoped for request details, forecasts, recommendations, audits, and submissions; employees/admins can review authorized requests and use employee actions. Analytics is authenticated for customer/employee/admin access, while alerts and the employee queue are employee/admin-only. Request JSON never supplies or overrides the authenticated creator, user ID, or role.


## Employee analytics, alerts, and audit

`GET /analytics` is employee/admin-only and supports optional `region` and `store` filters. It retains the frontend’s catalog fields and adds `pending_approvals`, `approved_purchase_value`, `modified_recommendations`, and `regional_demand_trends`. These values aggregate persisted requests, forecasts, and recommendations; approved value uses manager quantity when present, otherwise the original AI quantity.

`GET /alerts` is employee/admin-only and returns backend-derived product risk alerts. `GET /requests/{request_id}/audit` is owner-visible to customers and employee-visible to authorized reviewers; events are sorted chronologically by timestamp and event ID.

## Autonomous monitoring schedule

The existing SAM `RefreshSchedule` EventBridge rule remains the single scheduled rule. It runs once per day with `{ "source": "aws.events" }` and invokes the existing Lambda handler. The scheduled branch is independent of customer request analysis: it scans the active configured stores and catalog products, runs the deterministic forecast/inventory/risk engines, creates `InventoryAlert` records for WATCH/REORDER/URGENT/OVERSTOCK conditions, and persists them in the existing DynamoDB table under `ALERT#<alert_id>` when configured. The employee-only `GET /alerts` endpoint reads the alert repository for the dashboard.

Monitoring never approves recommendations, places orders, or changes customer request state. CloudWatch-compatible Python logging records completion counts and failures are surfaced through the Lambda invocation. No duplicate EventBridge rule was added.
