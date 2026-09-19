# Backend Gap Analysis

Inspection date: 2026-09-19

Scope: existing frontend in `frontend/src/App.jsx`, backend in `backend/app`, tests, and `infra/template.yaml`. No frontend redesign or implementation changes were made.

## 1. Frontend screens and responsibilities

The frontend is a single React application with client-side view switching; there is no router package.

| Screen/view | Current behavior | Backend data required |
|---|---|---|
| Login | Collects `userId`, `email`, and `role` locally; persists identity in `localStorage`. No login API call. | Production Cognito sign-in/token flow, or an explicitly retained demo mode. |
| Customer Dashboard | Select region/store, forecast horizon, budget, upload metadata, edit inventory rows, save/submit requests, list own requests, inspect request forecast/recommendations/audit. | Regions, stores, products, request CRUD/status transitions, request-scoped forecast, recommendations, audit. |
| Employee Review | Lists review queue, selects request, analyzes it, selects recommendation, edits quantity/status/priority/reason, approves or rejects. | Employee-scoped request list, analysis/recommendation generation, modification, approval, rejection, audit. |
| Analytics | Portfolio metrics, product table, product detail/history, request/review counts. | Analytics dashboard, products, product detail/history, request list. |
| Shared shell | Refresh, sign out, status/error banners, identity chip. | Reliable authenticated refresh and sign-out/token lifecycle. |

There are no separate frontend files for forms, services, types, or auth; the API client, interfaces, form state, role handling, and screen components are all embedded in `App.jsx`.

## 2. Exact frontend API contract

`apiJson()` calls `VITE_API_BASE_URL || '/api'`, sends JSON, and for an identity sends these debug headers:

```text
X-User-Id: identity.userId
X-User-Role: identity.role
X-User-Email: identity.email
```

Errors are expected as JSON with `detail` or `message`.

### Public bootstrap/catalog calls

| Method/path | Expected response | Used by |
|---|---|---|
| GET `/products` | `Product[]` with `id`, `name`, `category`, `current_inventory`, `supplier_lead_time_days`, `minimum_order_quantity`, `unit_cost` | Bootstrap, inventory selectors, analytics |
| GET `/products/{productId}` | `{ product: Product, history: SalesPoint[] }`; history points have `date`, `units` | Product detail and sparkline |
| GET `/regions` | `{ regions: Region[] }`; region fields: `country`, `state`, `city`, `region`, `store_id` | Request form |
| GET `/stores` | `{ stores: Store[] }`; frontend uses `store_id`, `name`, `region`, and request creation also needs `country`, `state`, `city` | Request form and payload construction |

### Authenticated workspace calls

| Method/path | Request body | Expected response | Role |
|---|---|---|---|
| GET `/requests` | none | `{ requests: InventoryRequest[] }` | Customer sees own; employee/admin sees queue/all |
| GET `/analytics` | none | `DashboardResponse` with portfolio counters and `products[]` summaries | Customer/employee in practice; backend currently does not require auth |
| GET `/requests/{requestId}` | none | `InventoryRequest` | Owner, employee, admin |
| GET `/requests/{requestId}/forecast` | none | `{ request_id, forecasts: [{ product_id, forecast: ForecastResult, inventory: InventoryResult }] }` | Request viewer |
| GET `/requests/{requestId}/recommendations` | none | `{ request_id, recommendations: Recommendation[] }` | Request viewer |
| GET `/requests/{requestId}/audit` | none | `{ request_id, events: AuditEvent[] }` | Request viewer |
| POST `/requests` | `CreateRequestBody` below | Created `InventoryRequest` | Customer/employee/admin |
| POST `/requests/{requestId}/submit` | none | Updated `InventoryRequest` | Customer/employee/admin |
| POST `/requests/{requestId}/analyze` | none | `{ request: InventoryRequest, recommendations: Recommendation[] }` | Employee/admin |
| POST `/recommendations/{recommendationId}/modify` | `ModifyRecommendationBody` below | Updated `Recommendation` | Employee/admin |
| POST `/recommendations/{recommendationId}/approve` | none | Updated `Recommendation` | Employee/admin |
| POST `/recommendations/{recommendationId}/reject` | none | Updated `Recommendation` | Employee/admin |

### Frontend request schemas

`POST /requests` body:

```json
{
  "region": {"country":"...","state":"...","city":"...","region":"...","store_id":"..."},
  "forecast_horizon_days": 7,
  "inventory": [{
    "product_id":"...", "product_name":"...", "current_stock":0,
    "unit_cost":1.0, "supplier_lead_time_days":1, "minimum_order_quantity":1
  }],
  "historical_sales_source":"S3",
  "historical_sales_upload": {"file_name":"...","content_type":"...","row_count":90},
  "constraints": {"max_purchase_budget":50000}
}
```

`historical_sales_upload` is metadata only; the browser never uploads file bytes or obtains an S3 key.

`POST /recommendations/{id}/modify` body:

```json
{"quantity": 0, "status":"REVIEW_REQUIRED", "priority":"HIGH", "reason":"..."}
```

Recommendation fields consumed by the UI include `recommendation_id`, `product_id`, `ai_quantity`, `manager_quantity`, `modified`, `modification_reason`, `ai_status`, `ai_priority`, `ai_reason`, `ai_risks`, `ai_confidence`, `final_status`, `final_priority`, and `approval_status`. Audit events need `event_id`, `action`, `user_id`, `user_role`, `timestamp` and may expose `metadata`.

## 3. Existing backend endpoints

Implemented in `backend/app/api/routes.py`:

```text
GET  /health
GET  /regions
GET  /stores
GET  /products
GET  /products/{product_id}
POST /forecast
POST /inventory/analyze
POST /decision
POST /analyze
POST /requests
POST /requests/{request_id}/submit
GET  /requests
GET  /requests/{request_id}
POST /requests/{request_id}/analyze
GET  /requests/{request_id}/forecast
GET  /requests/{request_id}/recommendations
POST /recommendations/{recommendation_id}/approve
POST /recommendations/{recommendation_id}/reject
POST /recommendations/{recommendation_id}/modify
GET  /requests/{request_id}/audit
GET  /alerts
GET  /analytics
```

The frontend calls all of these except the legacy/direct analysis endpoints (`/forecast`, `/inventory/analyze`, `/decision`, `/analyze`, `/alerts`) and `/health`. No frontend API endpoint is wholly absent by path.

## 4. Mocked, hardcoded, or local-only data

- Login is fake/local: role and identity are entered freely and persisted only in `localStorage` under `demand-intelligence-agent.identity`.
- The frontend sends identity debug headers, not a bearer token.
- File selection records name, MIME type, and hardcoded `row_count: 90`; bytes are discarded and no S3 upload occurs.
- `historical_sales_source` defaults to `S3`, but the request flow does not create or use an S3 object.
- Region and store responses are hardcoded Python lists containing only South India/Bangalore and West Coast/San Jose.
- Product and sales history come from `data/synthetic_dataset.json` (20 products, 90-day history), loaded by an in-process cache.
- The repository for requests, recommendations, and audit events is process-local memory. Data disappears on Lambda cold start/redeploy and is not shared across workers.
- Analytics fallback values in `App.jsx` are placeholders used if `/analytics` fails; the UI can display zeros rather than an error.
- `clampInventoryRows()` limits the initial draft to three products, which is frontend behavior rather than catalog persistence.
- Bedrock is optional and falls back to deterministic text; numeric decisions are deterministic.

Search findings: no separate frontend API client/service module, TypeScript interfaces, frontend TODO/FIXME markers, or frontend mock API module were found. Existing backend docs mention future modules that do not exist yet (for example dedicated recommendation/audit/region/store services).

## 5. Database entities required

The current model requires these durable entities:

1. `User`: Cognito subject, email, role, status, and optional profile metadata.
2. `Region`: country/state/city/business region identifier.
3. `Store`: store identifier, name, region, and geographic fields.
4. `Product`: catalog fields and current inventory defaults.
5. `SalesPoint`: product/store/date/units; supports uploaded and synthetic history.
6. `InventoryRequest`: creator, role, region/store, horizon, inventory snapshot, source/upload reference, constraints, status, timestamps.
7. `Recommendation`: request/product, AI values, manager overrides, final values, explanation, risks, confidence, calculation snapshot, status, timestamps.
8. `AuditEvent`: immutable request event, actor, role, action, timestamp, metadata.
9. `AnalysisSnapshot`/analytics materialization: product analysis and dashboard refresh results if the existing `AnalysisStore` is retained.

The request inventory row must be a snapshot: analysis currently calls `service.analyze_product(item.product_id)`, which uses catalog inventory/history and ignores request-specific `current_stock`, cost, lead time, MOQ, region, store, and forecast horizon.

## 6. AWS configured versus still required

### Currently configured in code/templates

- AWS Lambda-compatible FastAPI handler via Mangum.
- API Gateway proxy event in SAM.
- DynamoDB and S3 adapters in `backend/app/aws/storage.py`, activated only when `APP_TABLE_NAME`/`APP_BUCKET_NAME` exist.
- Amazon Bedrock Converse wrapper controlled by `BEDROCK_MODEL_ID`, with deterministic fallback.
- EventBridge daily schedule invokes the Lambda with `source: aws.events`.
- SAM creates one DynamoDB `AnalysisTable` keyed only by `product_id` and one S3 `AnalysisBucket`.
- Cognito JWT verification code exists and reads `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, and AWS region.
- CORS is currently wildcard with credentials enabled.

### Still required for the frontend/backend contract

- Cognito user pool/app client, role claims/groups, frontend token acquisition, refresh, logout, and bearer-token API calls.
- API Gateway/Cognito authorizer or equivalent enforcement; debug headers must not be accepted as production authentication.
- Durable DynamoDB design for requests, recommendations, audit events, catalog, regions/stores, and sales history. The current single-product analysis table cannot represent the request workflow safely.
- Correct keys/indexes for request owner, status/review queue, region/store, recommendation lookup, and audit ordering.
- S3 upload/presigned URL flow, content validation, parsing, object ownership/key policy, and request linkage.
- Lambda IAM least privilege for Cognito-related integration if needed, DynamoDB entities, S3 prefixes, Bedrock model access, and CloudWatch logs.
- CloudWatch structured logs/metrics/alarms and tracing for request lifecycle failures.
- Scheduled analytics refresh that persists/reads durable state rather than recomputing only in process.
- A deployment path for the frontend (the docs mention Amplify, but no Amplify configuration is present).
- A valid deployed Bedrock model ID/region; `openai.gpt-6-astra` in the SAM template is not validated here as an available Bedrock model identifier.

## 7. Mismatches and backend gaps

| Area | Current mismatch/gap | Impact |
|---|---|---|
| Authentication | UI accepts arbitrary local identity; backend allows spoofable `X-User-*` headers whenever Cognito is not configured. | No real identity or secure authorization in the default deployment. |
| Analytics authorization | Frontend sends identity, but `GET /analytics` has no dependency and is public. | Unauthenticated portfolio data exposure and inconsistent role contract. |
| Request ownership | `submit_request`, modify, approve, and reject do not verify the acting user owns or can act on the target object beyond route role gates. | Any accepted customer identity can submit any request ID; employee actions lack object/state checks. |
| State machine | Status transitions are not validated; repeated analysis appends duplicate recommendations; rejection/approval can be applied in arbitrary states. | Invalid lifecycle and duplicate data. |
| Request-scoped analysis | Analysis ignores request inventory values, store/region, horizon, budget, and uploaded data. | UI inputs do not affect results. |
| Persistence | Requests/recommendations/audits are in-memory; analysis persistence is a separate optional snapshot path. | Data loss and Lambda multi-instance inconsistency. |
| Uploads | UI only submits fabricated metadata and no `s3_key`. | Historical sales upload feature is not functional. |
| Catalog/location | Regions and stores are hardcoded and `Store` schema contains fields the route does not return. | Not extensible and can produce incomplete data. |
| Forecast horizon | Frontend sends arbitrary horizon, but request forecast and analysis use the fixed 7-day calculation/`forecast_7_day`. | Horizon control is cosmetic. |
| Recommendation response | Employee UI can edit fields, but backend accepts arbitrary status/priority strings and does not validate quantity against budget/MOQ/business rules. | Invalid approvals can be persisted. |
| Error handling | Cognito JWT verification exceptions are not normalized to a controlled 401; frontend assumes JSON error payloads. | Authentication failures may surface as server errors. |
| CORS/infra | Wildcard CORS plus credentials; SAM lacks Cognito authorizer, explicit table design for workflow entities, and frontend deployment config. | Unsafe or incomplete production deployment. |
| API documentation | `SPEC.md` documents only the original product-analysis API, not the role-based request workflow now used by the frontend. | Contract drift and difficult implementation handoff. |

## 8. Dependency-ordered implementation plan

1. Freeze this contract and add request/recommendation/audit integration tests covering every frontend call, role, ownership rule, and valid state transition.
2. Define durable DynamoDB entities, keys, indexes, serialization, and repository interfaces; migrate the in-memory `RequestRepository` behind that interface.
3. Implement authoritative catalog, region, store, and sales-history repositories, preserving the current response shapes.
4. Implement request-scoped forecast/inventory/decision calculation using the submitted inventory snapshot, store/region, horizon, constraints, and validated sales source.
5. Implement Cognito provisioning/claims and secure bearer-token enforcement; keep debug headers only behind an explicit local-development switch.
6. Implement S3 presigned upload and ingestion metadata, then connect uploaded sales data to request analysis.
7. Harden recommendation workflow: idempotent analysis, state/role/ownership checks, validation, budget/MOQ rules, and immutable audit persistence.
8. Add authenticated analytics and durable materializations/refresh behavior; ensure the scheduled Lambda does not erase or duplicate workflow data.
9. Update SAM/IAM/API authorizer/CORS/CloudWatch configuration and validate the Bedrock model configuration.
10. Run backend tests, end-to-end API tests, a frontend build, and a deployed smoke test without redesigning the frontend.
