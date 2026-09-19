# Bedrock Blocker

Status: BLOCKED BY AWS ACCOUNT VERIFICATION

- AWS region: `us-east-2`
- Lambda environment: `BEDROCK_MODEL_ID=openai.gpt-6-astra`
- The configured identifier is available in the account as an active Bedrock inference profile.
- Invocation path: deployed Lambda `ApiFunction` → `boto3.client("bedrock-runtime").converse(modelId=...)`.
- IAM: Lambda role includes `bedrock:Converse`, `bedrock:InvokeModel`, and `bedrock:InvokeModelWithResponseStream` on the existing policy.
- CloudWatch error category: `AccessDeniedException`. AWS message states the account is currently being verified and cannot access the operation yet.
- Application behavior: analysis returns controlled HTTP 502, records `AI_RECOMMENDATION_FAILED`, and does not create a fake recommendation.

Required external action: AWS account verification must complete. Then rerun the authenticated analysis test; no code or infrastructure bypass is appropriate.
