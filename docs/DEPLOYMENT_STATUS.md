# Deployment Status

Inspection date: 2026-09-19

## Status

**Backend deployed; full production workflow not verified.** The SAM stack is deployed in `us-east-2`. Cognito and Amplify resources were not present, so authenticated browser workflow verification remains pending.

## AWS region

- Configured deployment region: `us-east-2`
- Verification: `aws configure get region`
- AWS account: `481665102347`
- Business regions are application data and are separate from the AWS region: `South India`/`Bangalore` and `West Coast`/`San Jose`.

## Existing resource inspection

Read-only AWS inventory commands for Lambda, API Gateway, DynamoDB, S3, Cognito, Bedrock, EventBridge, CloudWatch, CloudFormation, and IAM were attempted in `us-east-2`, but all authenticated calls were blocked by the expired session. Existing resource reuse and duplicate detection therefore remain unverified.

Local IaC contains one SAM backend definition with:

- Lambda-compatible FastAPI handler (`app.main.lambda_handler`)
- API Gateway proxy event
- One DynamoDB table (`AnalysisTable`)
- One S3 bucket (`AnalysisBucket`)
- One existing EventBridge schedule (`RefreshSchedule`, `rate(1 day)`) invoking the same Lambda with `{"source":"aws.events"}`
- Bedrock IAM permissions
- DynamoDB/S3 IAM policies
- CloudWatch logging through the Lambda execution role defaults

No Cognito or Amplify resources/configuration are represented in the repository’s SAM/IaC files. Cognito verification exists in application code and requires deployed environment variables.

## URLs and resources

- API URL: `https://fvlyc576k7.execute-api.us-east-2.amazonaws.com/Prod`
- Frontend URL: not available; no Amplify configuration or deployed Amplify app exists in this account.
- DynamoDB: SAM logical resource `AnalysisTable`; physical table name unverified.
- S3: SAM logical resource `AnalysisBucket`; physical bucket name unverified.
- Lambda/API: SAM logical resource `ApiFunction`; physical identifiers unverified.
- EventBridge: SAM logical event `RefreshSchedule`; deployed rule unverified.
- CloudWatch: Lambda log groups/metrics unverified.
- Cognito: user pool/app client unverified.
- Bedrock: application uses `BEDROCK_MODEL_ID`; SAM currently supplies `openai.gpt-6-astra`, which must be validated against available models in the deployment region before production use.

## Required environment variables

- `AWS_REGION` or `AWS_DEFAULT_REGION` — configured deployment region, currently `us-east-2`
- `APP_TABLE_NAME` — deployed DynamoDB table name
- `APP_BUCKET_NAME` — deployed S3 bucket name
- `BEDROCK_MODEL_ID` — approved Bedrock model ID available in the deployment region
- `COGNITO_USER_POOL_ID` — required for production JWT validation
- `COGNITO_APP_CLIENT_ID` — required for production JWT validation
- `VITE_API_BASE_URL` — deployed API base URL for the frontend build

No credentials or secrets are stored in the repository.

## Validation completed

- Backend suite: `33 passed`
- Frontend build: `npm run build` succeeded
- SAM validation/build: succeeded
- Deployment: succeeded; `/health`, `/regions`, `/stores`, and `/products` returned HTTP 200
- Production customer/employee workflow: not verified because no deployed API/auth/frontend URLs were available

## Deployment commands after reauthentication

```bash
aws login
aws configure set region us-east-2
aws sts get-caller-identity
sam validate --template-file infra/template.yaml
sam build --template-file infra/template.yaml
sam deploy --template-file .aws-sam/build/template.yaml --guided
npm --prefix frontend run build
```

Use an existing approved Amplify app/configuration if discovered after authentication. Do not create a second EventBridge schedule; reuse the existing `RefreshSchedule` resource or existing deployed rule after verifying its CloudFormation ownership.

## Production verification checklist

After deployment, verify the stack outputs and then test: customer authentication, request creation/submission, store-specific inventory, employee analysis, forecast/calculation persistence, Bedrock response, employee review/modify/approve/reject, audit history, customer ownership denial, and customer approval denial. Also invoke the scheduled Lambda path with an EventBridge-shaped event and verify persisted alerts through the employee endpoint.

## Rollback notes

No rollback was performed. After a successful deployment, use the same named SAM/CloudFormation stack for rollback or a CloudFormation stack rollback operation. Do not delete shared buckets, tables, Cognito pools, or unrelated resources; preserve data and use a reviewed stack change set.
