from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi import Depends

from app.api.dependencies import get_current_identity, require_roles
from app.core.models import UserRole


def test_debug_header_identity_and_role_gate():
    app = FastAPI()

    def requires_employee():
        return require_roles(UserRole.EMPLOYEE)

    @app.get("/whoami")
    def whoami(identity=Depends(requires_employee())):
        return {"user_id": identity.user_id, "role": identity.role.value}

    client = TestClient(app)
    response = client.get(
        "/whoami",
        headers={"X-User-Id": "emp-1", "X-User-Role": "EMPLOYEE"},
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": "emp-1", "role": "EMPLOYEE"}


def test_customer_cannot_access_employee_only_route():
    app = FastAPI()

    def requires_employee():
        return require_roles(UserRole.EMPLOYEE)

    @app.get("/employee-only")
    def employee_only(identity=Depends(requires_employee())):
        return {"role": identity.role.value}

    client = TestClient(app)
    response = client.get(
        "/employee-only",
        headers={"X-User-Id": "cust-1", "X-User-Role": "CUSTOMER"},
    )
    assert response.status_code == 403


def test_configured_cognito_rejects_spoofable_debug_headers(monkeypatch):
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "client")
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    app = FastAPI()

    @app.get("/protected")
    def protected(identity=Depends(get_current_identity)):
        return identity.user_id

    client = TestClient(app)
    response = client.get("/protected", headers={"X-User-Id": "spoof", "X-User-Role": "EMPLOYEE"})
    assert response.status_code == 401
