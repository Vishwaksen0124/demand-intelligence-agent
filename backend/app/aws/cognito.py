from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient


@dataclass(frozen=True)
class CognitoConfig:
    user_pool_id: str
    app_client_id: str
    region: str

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"


def load_cognito_config() -> CognitoConfig | None:
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "").strip()
    app_client_id = os.getenv("COGNITO_APP_CLIENT_ID", "").strip()
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "")).strip()
    if not (user_pool_id and app_client_id and region):
        return None
    return CognitoConfig(user_pool_id=user_pool_id, app_client_id=app_client_id, region=region)


def verify_cognito_token(token: str) -> dict:
    config = load_cognito_config()
    if not config:
        raise ValueError("Cognito is not configured")

    client = PyJWKClient(config.jwks_url)
    signing_key = client.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=config.app_client_id,
        issuer=config.issuer,
    )
    return claims
