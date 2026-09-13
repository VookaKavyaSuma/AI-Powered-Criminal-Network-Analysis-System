"""
jwt_handler.py — JWT authentication and bcrypt password verification.

Handles:
- Password verification via bcrypt (compatible with Python 3.14)
- JWT generation and payload validation using python-jose
- User authentication against PostgreSQL 'users' table
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

from backend.db.connections import get_pg_connection

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET")
if not SECRET_KEY or "change_me" in SECRET_KEY:
    raise RuntimeError("CRITICAL: JWT_SECRET_KEY environment variable is not properly set. Refusing to start for security reasons.")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "480"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate user against PostgreSQL users table.
    Returns user dict with username and role, or None if authentication fails.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, password_hash, role
                FROM users
                WHERE username = %s;
            """, (username,))
            row = cur.fetchone()
            if not row:
                return None

            user_id, uname, pwhash, role = row
            if verify_password(password, pwhash):
                return {
                    "user_id": str(user_id),
                    "username": uname,
                    "role": role,
                }
            return None
