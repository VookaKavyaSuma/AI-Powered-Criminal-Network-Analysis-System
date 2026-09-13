"""
auth.py — Authentication router for login and token verification.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.auth.jwt_handler import authenticate_user, create_access_token
from backend.auth.rbac import get_current_user
from security.audit_chain import audit_chain

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """
    Authenticate with username and password.
    Returns JWT access token with role claims.
    """
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": user["username"], "role": user["role"]})

    # Log to cryptographic audit chain
    audit_chain.append_block(
        action="USER_LOGIN",
        actor=user["username"],
        entity_id=user["user_id"],
        details={"role": user["role"]},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"],
        },
    }


@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Return the profile and role of the currently authenticated user."""
    return current_user
