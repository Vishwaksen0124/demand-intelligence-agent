# DemandOps AI Upgrade Plan

## Current State

The repository is a fresh scaffold with no git commits yet. The current implementation already contains a minimal working demand-analysis stack, but it is not yet the role-based, human-in-the-loop platform requested in the upgrade brief.

### Existing Architecture

- Frontend: React + Vite SPA in `frontend/`
- Backend: FastAPI in `backend/app/`
- Forecasting: deterministic Python engine in `backend/app/core/forecast.py`
- Inventory math: deterministic Python engine in `backend/app/core/inventory.py`
- Decision logic: deterministic rule engine in `backend/app/core/decision.py`
- Bedrock: optional narration wrapper in `backend/app/aws/bedrock.py`
- Storage: optional DynamoDB and S3 adapter in `backend/app/aws/storage.py`
- Infra: AWS SAM template in `infra/template.yaml`
- Tests: Pytest API and engine tests in `tests/`
- Dataset: synthetic product history in `data/synthetic_dataset.json`

### Existing Functionality

- `GET /health`
- `GET /products`
- `GET /products/{product_id}`
- `POST /forecast`
- `POST /inventory/analyze`
- `POST /decision`
- `POST /analyze`
- `GET /alerts`
- Deterministic forecast generation
- Deterministic inventory calculations
- Deterministic decision classification
- Optional Bedrock explanation fallback
- Optional DynamoDB and S3 persistence
- Basic React dashboard with product list and detail panels

### Current AWS State

Read-only AWS inspection in `us-east-2` found no existing app resources to preserve in this account.

- Amplify apps: none
- Lambda functions: none
- DynamoDB tables: none
- S3 buckets: none
- Cognito user pools: none

The active AWS identity is the account root principal in account `481665102347`, and the configured AWS region is `us-east-2`.

## Proposed Target Architecture

Upgrade the current application into a role-based DemandOps AI platform with a human approval gate:

Customer
→ React Dashboard
→ Amazon Cognito
→ API Gateway
→ Lambda backend
→ Request Orchestrator
→ Forecast Engine
→ Inventory Calculation Engine
→ Risk Engine
→ Amazon Bedrock Decision Agent
→ Employee Review Dashboard
→ Approve / Modify / Reject
→ Final Approved Order
→ Audit Trail

### Services to Use

- Amazon Cognito for auth and role claims
- AWS Amplify Hosting for frontend deployment
- Amazon API Gateway for API access
- AWS Lambda for backend handlers
- Amazon Bedrock for explanation and reasoning only
- Amazon DynamoDB for requests, recommendations, audits, stores, products, and analytics
- Amazon S3 for uploads and report artifacts
- Amazon EventBridge for optional scheduled analysis
- Amazon CloudWatch for logs and metrics
- AWS IAM for least-privilege access
- AWS SAM / CloudFormation for backend infrastructure

## Files To Modify

- `README.md`
- `SPEC.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/demo.md`
- `backend/app/main.py`
- `backend/app/api/routes.py`
- `backend/app/services/pipeline.py`
- `backend/app/core/models.py`
- `backend/app/core/catalog.py`
- `backend/app/core/forecast.py`
- `backend/app/core/inventory.py`
- `backend/app/core/decision.py`
- `backend/app/aws/bedrock.py`
- `backend/app/aws/storage.py`
- `frontend/src/App.jsx`
- `frontend/src/styles.css`
- `infra/template.yaml`
- `backend/requirements.txt`
- `tests/test_api.py`
- `tests/test_engines.py`

## Files To Add

- `docs/UPGRADE_PLAN.md`
- `docs/api.md`
- `docs/security.md`
- `backend/app/api/auth.py`
- `backend/app/api/dependencies.py`
- `backend/app/core/requests.py`
- `backend/app/core/recommendations.py`
- `backend/app/core/audit.py`
- `backend/app/core/regions.py`
- `backend/app/core/stores.py`
- `backend/app/core/permissions.py`
- `backend/app/services/orchestrator.py`
- `backend/app/services/review_service.py`
- `backend/app/services/audit_service.py`
- `backend/app/services/analytics_service.py`
- `backend/app/aws/cognito.py`
- `backend/app/aws/dynamodb.py`
- `backend/app/aws/events.py`
- `backend/app/aws/s3.py`
- `frontend/src/components/` and dashboard screen components as needed
- `frontend/src/auth/` helpers for Cognito login state
- `tests/test_auth.py`
- `tests/test_requests.py`
- `tests/test_recommendations.py`
- `tests/test_audit.py`
- `tests/test_e2e.py`

## AWS Resources To Add

New resources will be added only where the account does not already contain them.

- Cognito user pool and app client
- API Gateway auth integration or Lambda authorizer support
- DynamoDB tables for requests, recommendations, audit events, products, stores, regions, and sales
- S3 bucket for sales uploads and generated reports
- EventBridge rule for scheduled monitoring if implemented
- CloudWatch log groups/permissions through Lambda and API integrations
- Amplify Hosting app for the frontend

## Migration Strategy

1. Preserve the current deterministic forecast and calculation engines.
2. Expand the data model to make region and store first-class entities.
3. Replace static inventory assumptions with request-scoped inventory inputs.
4. Add Cognito-based CUSTOMER and EMPLOYEE roles.
5. Add request creation, analysis, review, approval, modification, and rejection workflows.
6. Add immutable-style audit logging.
7. Upgrade Bedrock to generate explanations from structured facts only.
8. Upgrade the frontend into separate customer and employee dashboards.
9. Add analytics and optional scheduled monitoring.
10. Deploy incrementally and validate each phase.

## Migration Risks

- The current codebase has no persisted multi-tenant data model, so role and ownership boundaries must be introduced carefully.
- The current backend stores only minimal synthetic product history and does not yet model request lifecycles.
- Bedrock outputs must be validated because the current integration is only a best-effort text wrapper.
- The current frontend is a single dashboard and must be split into customer and employee experiences without breaking the existing data flow.
- There are no live AWS resources in this account today, so the first deployment must establish new infrastructure cleanly without assuming prior state.
- The repo has no git history, so there is no release baseline to diff against.

## Testing Strategy

### Preserve Existing Tests

- Keep the current deterministic engine and API tests.
- Add new tests rather than replacing the existing ones.

### New Coverage

- Forecasting by region and store
- Inventory calculations with variable request inputs
- Risk classification for NORMAL, WATCH, REORDER, URGENT, and OVERSTOCK
- Bedrock response validation and fallback behavior
- Customer-only authorization rules
- Employee-only authorization rules
- Request creation and request ownership
- Review workflow: approve, modify, reject
- Audit trail integrity
- S3 upload validation
- DynamoDB read/write adapters
- Regional filtering and store filtering
- End-to-end customer → employee approval flow

### Validation Order

1. Unit tests for deterministic engines
2. API tests for role-protected endpoints
3. Integration tests for request workflow and audit persistence
4. Frontend build and smoke tests
5. Local SAM build/package validation
6. Deployed smoke tests after infrastructure is created

## Notes

- The AWS deployment region is `us-east-2` unless explicitly changed by configuration.
- Business regions such as Bangalore, Hyderabad, Chennai, Mumbai, and Delhi are application data and must not be confused with the AWS deployment region.
- No destructive AWS action should be performed without explicit confirmation.
- Existing functionality must remain working during the upgrade.
