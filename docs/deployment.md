# Deployment

## Backend

1. Build the SAM application from `infra/template.yaml`.
2. Deploy the Lambda, API Gateway, DynamoDB table, S3 bucket, and EventBridge rule.
3. Configure environment variables for the Bedrock model id and optional storage targets.

## Frontend

1. Build the React app with Vite.
2. Deploy to Amplify hosting or a static host that points at the backend API URL.
3. Set `VITE_API_BASE_URL`, `VITE_COGNITO_REGION`, `VITE_COGNITO_USER_POOL_ID`, and `VITE_COGNITO_APP_CLIENT_ID` at build time so the static bundle targets the deployed API and Cognito pool. Do not commit `.env` files.

## Environment variables

- `BEDROCK_MODEL_ID`
- `APP_TABLE_NAME`
- `APP_BUCKET_NAME`
- `AWS_REGION`
- `VITE_API_BASE_URL`

## Notes

- The backend keeps working if Bedrock, DynamoDB, or S3 are unavailable.
- The EventBridge rule is only for periodic refresh. The main API remains the source of truth.
