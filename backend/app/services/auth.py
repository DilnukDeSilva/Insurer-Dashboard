from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


CLAIM_LINK_TOKEN_TYPE = "claim_link"


def decode_claim_link_token(token: str) -> dict:
    """Only for claim links sent before short codes (see services/claim_links.py)
    replaced JWTs — they stay valid until their own 48h expiry.

    Raises jose.JWTError (expired/bad signature) or ValueError (wrong token type)."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("typ") != CLAIM_LINK_TOKEN_TYPE:
        raise ValueError("Not a claim-link token.")
    return payload


async def verify_supabase_token(token: str) -> str | None:
    """Return the user's email if the token is a valid Supabase session token, else None."""
    if not settings.supabase_url or not settings.supabase_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_key},
            )
        if resp.status_code == 200:
            return resp.json().get("email")
    except httpx.HTTPError:
        pass
    return None
