# AWS Resource Inventory

Audit date: 2026-09-19. Account `481665102347`; deployment region `us-east-2`. Business regions are application data (South India/Bangalore and West Coast/San Jose).

| Component | AWS Resource | Resource ID/ARN | Region | Status | Used By | Verified |
|---|---|---|---|---|---|---|
| CloudFormation | demand-intelligence-agent | stack/demand-intelligence-agent | us-east-2 | UPDATE_COMPLETE | SAM deployment | Yes |
| API Gateway | ServerlessRestApi / Prod | `fvlyc576k7`, stage `Prod` | us-east-2 | Deployed | Frontend-configurable API | Health/catalog endpoints verified |
| Lambda | ApiFunction | `demand-intelligence-agent-ApiFunction-Zf85kYzz6r3S` | us-east-2 | Deployed | API/EventBridge | Yes |
| DynamoDB | AnalysisTable | `arn:aws:dynamodb:us-east-2:481665102347:table/demand-intelligence-agent-AnalysisTable-1MN7ZAJV2R970` | us-east-2 | Deployed, empty for requests | Alert path | Yes |
| S3 | AnalysisBucket | `demand-intelligence-agent-analysisbucket-s8ehgtovbols` | us-east-2 | Deployed, no objects found | Analysis persistence path | Yes |
| EventBridge | RefreshSchedule | `demand-intelligence-agent-ApiFunctionRefreshSchedul-Ev3pz8k3tPoW` | us-east-2 | ENABLED, rate(1 day) | Lambda monitoring branch | Yes |
| CloudWatch | Lambda log group | `/aws/lambda/demand-intelligence-agent-ApiFunction-Zf85kYzz6r3S` | us-east-2 | Receiving logs | Lambda errors/invocations | Yes |
| IAM | ApiFunctionRole | `demand-intelligence-agent-ApiFunctionRole-F5DlBiMdpiKa` | us-east-2 | Deployed | Lambda execution | Yes |
| Cognito | None found | None | us-east-2 | Not deployed | Authentication | Yes |
| Amplify | None found | None | us-east-2 | Not deployed | Frontend hosting | Yes |
| Bedrock | Inference profiles available; Lambda configured with `openai.gpt-6-astra` | `us.openai.gpt-6-astra` profile exists | us-east-2 | Invocation denied: account verification | Lambda decision agent | Yes |
