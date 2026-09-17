# Architecture

The system uses a single deterministic analysis pipeline with a thin AI narration layer.

```mermaid
flowchart LR
  UI[React Dashboard] --> API[FastAPI API]
  API --> DATA[Synthetic Dataset]
  API --> F[Forecast Engine]
  F --> I[Inventory Engine]
  I --> D[Decision Engine]
  D --> B[Bedrock Narration]
  D --> S3[S3 Snapshot Export]
  D --> DDB[DynamoDB Analysis Store]
  EVT[EventBridge] --> API
```

### Design choices

- Keep all numeric outputs deterministic for testability.
- Use Bedrock only for explanation text.
- Keep the backend Lambda-compatible with a shared ASGI entry point.
- Keep the frontend lightweight and dependency-minimal.
