from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
import logging

from fastapi import Depends, Header, HTTPException, Request, status

from ..aws.cognito import load_cognito_config, verify_cognito_token
from ..core.models import UserRole

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentityContext:
    user_id: str
    role: UserRole
    email: str | None = None
    token_claims: dict | None = None


def get_current_identity(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_user_email: Annotated[str | None, Header(alias="X-User-Email")] = None,
) -> IdentityContext:
    config = load_cognito_config()
    if config:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer authentication required")
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token is empty")
        try:
            claims = verify_cognito_token(token)
        except Exception as exc:
            logger.warning("Cognito authentication failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc
        groups = claims.get("cognito:groups") or []
        token_role = claims.get("custom:role") or claims.get("role") or (groups[0] if groups else None)
        role = UserRole(token_role) if token_role in UserRole._value2member_map_ else UserRole.CUSTOMER
        user_id = str(claims.get("sub") or claims.get("username") or claims.get("email") or "")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has no user identity")
        return IdentityContext(user_id=user_id, role=role, email=claims.get("email"), token_claims=claims)

    # Header identity is a local test/development adapter only. It is never accepted when Cognito is configured.
    if x_user_id and x_user_role:
        if x_user_role not in UserRole._value2member_map_:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
        return IdentityContext(user_id=x_user_id, role=UserRole(x_user_role), email=x_user_email)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_roles(*allowed_roles: UserRole):
    def dependency(identity: IdentityContext = Depends(get_current_identity)) -> IdentityContext:
        if identity.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return identity

    return dependency
