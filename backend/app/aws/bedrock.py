from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from pydantic import ValidationError

from ..core.models import DecisionAgentResponse


def _mantle_request(model_id: str, messages: list[dict], max_tokens: int, temperature: float) -> dict:
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-2"))
    endpoint = os.getenv("BEDROCK_MANTLE_ENDPOINT", f"https://bedrock-mantle.{region}.api.aws/v1").rstrip("/")
    url = f"{endpoint}/chat/completions"
    body = json.dumps({"model": model_id, "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "reasoning_effort": "low"}).encode("utf-8")
    session = boto3.Session(region_name=region)
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("AWS credentials are unavailable for Bedrock Mantle")
    frozen = credentials.get_frozen_credentials()
    signed = AWSRequest(method="POST", url=url, data=body, headers={"Host": url.split('/')[2], "Content-Type": "application/json", "Accept": "application/json"})
    SigV4Auth(frozen, "bedrock-mantle", region).add_auth(signed)
    request = Request(url, data=body, headers=dict(signed.headers), method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Bedrock Mantle request failed: {exc}") from exc


def explain_with_bedrock(payload: dict) -> str:
    model_id = os.getenv("BEDROCK_MODEL_ID", "")
    if not model_id:
        return payload["fallback"]
    try:
        response = _mantle_request(model_id, [{"role": "user", "content": "Explain this inventory decision in 3 sentences without inventing numeric values: " + json.dumps(payload["context"], sort_keys=True)}], 180, 0.2)
        return response["choices"][0]["message"].get("content") or payload["fallback"]
    except Exception:
        return payload["fallback"]


def decide_with_bedrock(facts: dict, fallback: DecisionAgentResponse) -> DecisionAgentResponse:
    model_id = os.getenv("BEDROCK_MODEL_ID", "")
    if not model_id:
        return fallback
    prompt = (
        "Return ONLY one valid JSON object with exactly these fields: status, priority, recommended_quantity, reason, risks, confidence. "
        "status MUST be uppercase and one of NORMAL, WATCH, REORDER, URGENT, OVERSTOCK. "
        "priority MUST be uppercase and one of LOW, MEDIUM, HIGH. "
        "recommended_quantity MUST be an integer equal to deterministic_recommended_quantity. "
        "risks MUST be a JSON array of strings, never a single string. "
        "confidence MUST be a number from 0 to 1. "
        "Use only supplied facts. Do not perform arithmetic or invent facts. "
        f"FACTS\n{json.dumps(facts, sort_keys=True)}"
    )
    try:
        response = _mantle_request(model_id, [{"role": "user", "content": prompt}], 500, 0.0)
        text = response["choices"][0]["message"].get("content") or ""
        if text.startswith("```"):
            text = text.strip("`").removeprefix("json").strip()
        result = DecisionAgentResponse.model_validate(json.loads(text))
        if result.recommended_quantity != facts["deterministic_recommended_quantity"]:
            raise ValueError("Bedrock changed the deterministic recommended quantity")
        return result
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise BedrockDecisionError(f"Invalid Bedrock decision response: {exc}") from exc
    except Exception as exc:
        raise BedrockDecisionError(f"Bedrock decision failed: {exc}") from exc


class BedrockDecisionError(RuntimeError):
    pass
