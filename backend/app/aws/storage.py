from __future__ import annotations

import json
import os
from decimal import Decimal

try:
    import boto3
except ImportError:
    boto3 = None


def _serialize(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


class AnalysisStore:
    def __init__(self) -> None:
        self.table_name = os.getenv("APP_TABLE_NAME", "")
        self.bucket_name = os.getenv("APP_BUCKET_NAME", "")
        self.region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-2"))
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region) if self.table_name and boto3 else None
        self.s3 = boto3.client("s3", region_name=self.region) if self.bucket_name and boto3 else None

    def read_object(self, key: str) -> bytes:
        if not self.s3:
            raise RuntimeError("S3 is not configured")
        return self.s3.get_object(Bucket=self.bucket_name, Key=key)["Body"].read()

    def upload_historical_sales(self, key: str, content: bytes, content_type: str = "text/csv") -> str:
        if not self.s3:
            raise RuntimeError("S3 is not configured")
        self.s3.put_object(Bucket=self.bucket_name, Key=key, Body=content, ContentType=content_type)
        return key

    def save(self, analysis: dict) -> None:
        if self.dynamodb:
            table = self.dynamodb.Table(self.table_name)
            product_id = analysis.get("product", {}).get("id", "unknown")
            item = {
                "pk": f"ANALYSIS#{product_id}",
                "sk": str(analysis.get("forecast", {}).get("created_at", "LATEST")),
                "entity": "ANALYSIS",
                **analysis,
            }
            table.put_item(Item=_serialize(item))
        if self.s3:
            key = f"analysis/{analysis['product']['id']}.json"
            self.s3.put_object(Bucket=self.bucket_name, Key=key, Body=json.dumps(analysis, default=str).encode("utf-8"), ContentType="application/json")

    def list_alerts(self) -> list[dict]:
        if not self.dynamodb:
            return []
        table = self.dynamodb.Table(self.table_name)
        response = table.scan()
        items = response.get("Items", [])
        return [item for item in items if item.get("decision", {}).get("status") in {"WATCH", "REORDER", "URGENT"}]


    def save_alert(self, alert: dict) -> None:
        if self.dynamodb:
            item = {"pk": f"ALERT#{alert['alert_id']}", "sk": "META", "gsi1pk": f"ALERT_STATUS#{alert['status']}", "gsi1sk": alert["created_at"], **_serialize(alert)}
            self.dynamodb.Table(self.table_name).put_item(Item=item)

    def list_persisted_alerts(self) -> list[dict]:
        if not self.dynamodb:
            return []
        response = self.dynamodb.Table(self.table_name).scan()
        return [item for item in response.get("Items", []) if str(item.get("pk", "")).startswith("ALERT#")]


class RequestStore(AnalysisStore):
    """Single-table persistence for request workflow entities."""
    def _put(self, item: dict) -> None:
        if self.dynamodb:
            self.dynamodb.Table(self.table_name).put_item(Item=_serialize(item))

    def save_request(self, value: dict) -> None:
        self._put({"pk": f"REQUEST#{value['request_id']}", "sk": "META", "gsi1pk": f"USER#{value['created_by']}", "gsi1sk": value.get("created_at", ""), "entity": "REQUEST", **value})

    def get_request(self, request_id: str) -> dict | None:
        if not self.dynamodb: return None
        item = self.dynamodb.Table(self.table_name).get_item(Key={"pk": f"REQUEST#{request_id}", "sk": "META"}).get("Item")
        return item

    def list_requests(self) -> list[dict]:
        if not self.dynamodb: return []
        return [i for i in self.dynamodb.Table(self.table_name).scan().get("Items", []) if i.get("entity") == "REQUEST"]

    def save_forecast(self, value: dict) -> None:
        self._put({"pk": f"REQUEST#{value['request_id']}", "sk": f"FORECAST#{value['forecast_id']}", "gsi1pk": f"REQUEST#{value['request_id']}", "gsi1sk": f"FORECAST#{value['product_id']}", "entity": "FORECAST", **value})

    def list_forecasts(self, request_id: str) -> list[dict]:
        if not self.dynamodb: return []
        return [i for i in self.dynamodb.Table(self.table_name).query(KeyConditionExpression=__import__('boto3').dynamodb.conditions.Key('pk').eq(f'REQUEST#{request_id}')).get('Items', []) if i.get('entity') == 'FORECAST']

    def save_recommendation(self, value: dict) -> None:
        self._put({"pk": f"REQUEST#{value['request_id']}", "sk": f"RECOMMENDATION#{value['recommendation_id']}", "gsi1pk": f"REQUEST#{value['request_id']}", "gsi1sk": f"RECOMMENDATION#{value['product_id']}", "entity": "RECOMMENDATION", **value})

    def list_recommendations(self, request_id: str) -> list[dict]:
        if not self.dynamodb: return []
        return [i for i in self.dynamodb.Table(self.table_name).query(KeyConditionExpression=__import__('boto3').dynamodb.conditions.Key('pk').eq(f'REQUEST#{request_id}')).get('Items', []) if i.get('entity') == 'RECOMMENDATION']

    def list_all_recommendations(self) -> list[dict]:
        if not self.dynamodb: return []
        return [i for i in self.dynamodb.Table(self.table_name).scan().get('Items', []) if i.get('entity') == 'RECOMMENDATION']

    def save_event(self, value: dict) -> None:
        self._put({"pk": f"REQUEST#{value['request_id']}", "sk": f"EVENT#{value['timestamp']}#{value['event_id']}", "gsi1pk": f"REQUEST#{value['request_id']}", "gsi1sk": f"EVENT#{value['timestamp']}", "entity": "AUDIT", **value})

    def list_events(self, request_id: str) -> list[dict]:
        if not self.dynamodb: return []
        return [i for i in self.dynamodb.Table(self.table_name).query(KeyConditionExpression=__import__('boto3').dynamodb.conditions.Key('pk').eq(f'REQUEST#{request_id}')).get('Items', []) if i.get('entity') == 'AUDIT']

    def delete_keys(self, item: dict) -> dict:
        return {k: v for k, v in item.items() if k not in {'pk','sk','gsi1pk','gsi1sk','entity'}}
