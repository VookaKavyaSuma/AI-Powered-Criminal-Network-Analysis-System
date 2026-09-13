"""
rbac.py — Role-Based Access Control (RBAC) and current user authentication dependencies.

Supported Roles:
- investigator (Level 1): View entities, subgraphs, ingest FIR documents
- analyst      (Level 2): View analytics, communities, link predictions, alerts, ingest CDR/transactions
- admin        (Level 3): Verify audit chain, view audit logs, manage system users
"""

from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt_handler import decode_access_token

security = HTTPBearer()

ROLE_HIERARCHY = {
    "investigator": 1,
    "analyst": 2,
    "admin": 3,
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency to extract and authenticate current user from Bearer token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing required identity claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "username": username,
        "role": role,
    }


def require_role(min_role: str):
    """
    Dependency factory checking that the authenticated user meets the minimum role rank.
    """
    min_rank = ROLE_HIERARCHY.get(min_role.lower(), 1)

    def role_checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "").lower()
        user_rank = ROLE_HIERARCHY.get(user_role, 0)
        if user_rank < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires role '{min_role}' or higher (current role: '{user_role}')",
            )
        return user

    return role_checker
