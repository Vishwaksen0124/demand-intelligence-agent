import json
import pytest
from app.aws import bedrock
from app.core.models import DecisionAgentResponse

def facts():
    return {"deterministic_recommended_quantity": 70, "forecast_7_day": 95, "current_stock": 40}

def response_for(value):
    return {"choices": [{"message": {"content": value}}]}

def test_valid_bedrock_response(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(bedrock, "_mantle_request", lambda *args: response_for(json.dumps({"status":"REORDER","priority":"HIGH","recommended_quantity":70,"reason":"Stock is below the reorder point.","risks":["Stockout risk"],"confidence":0.87})))
    result = bedrock.decide_with_bedrock(facts(), DecisionAgentResponse(status="NORMAL", priority="LOW", recommended_quantity=70, reason="fallback", confidence=.5))
    assert result.status == "REORDER" and result.recommended_quantity == 70

@pytest.mark.parametrize("payload", ["not json", {"status":"REORDER"}, {"status":"INVALID","priority":"HIGH","recommended_quantity":70,"reason":"x","risks":[],"confidence":.8}, {"status":"REORDER","priority":"HIGH","recommended_quantity":-1,"reason":"x","risks":[],"confidence":.8}, {"status":"REORDER","priority":"HIGH","recommended_quantity":71,"reason":"x","risks":[],"confidence":.8}, {"status":"REORDER","priority":"HIGH","recommended_quantity":70,"reason":"x","risks":[],"confidence":1.5}])
def test_malformed_or_unsafe_bedrock_response(payload, monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(bedrock, "_mantle_request", lambda *args: response_for(payload if isinstance(payload, str) else json.dumps(payload)))
    fallback = DecisionAgentResponse(status="NORMAL", priority="LOW", recommended_quantity=70, reason="fallback", confidence=.5)
    with pytest.raises(bedrock.BedrockDecisionError): bedrock.decide_with_bedrock(facts(), fallback)

def test_mantle_http_failure(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(bedrock, "_mantle_request", lambda *args: (_ for _ in ()).throw(RuntimeError("HTTP 500")))
    with pytest.raises(bedrock.BedrockDecisionError): bedrock.decide_with_bedrock(facts(), DecisionAgentResponse(status="NORMAL", priority="LOW", recommended_quantity=70, reason="fallback", confidence=.5))
