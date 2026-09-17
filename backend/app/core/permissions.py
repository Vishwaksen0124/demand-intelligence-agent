from __future__ import annotations

from .models import UserRole


def can_view_request(user_role: str, request_owner_id: str, user_id: str) -> bool:
    if user_role in {UserRole.EMPLOYEE, UserRole.ADMIN}:
        return True
    return request_owner_id == user_id


def can_modify_recommendation(user_role: str) -> bool:
    return user_role in {UserRole.EMPLOYEE, UserRole.ADMIN}


def can_approve_recommendation(user_role: str) -> bool:
    return user_role in {UserRole.EMPLOYEE, UserRole.ADMIN}
