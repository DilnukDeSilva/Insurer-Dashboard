from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.db.mongo import get_db
from app.services.auth import decode_access_token, verify_supabase_token

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    token = credentials.credentials
    email: str | None = None

    # Try internal JWT first.
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
    except JWTError:
        pass

    # Fall back to Supabase session token (used by kaduna-web SSO).
    if not email:
        email = await verify_supabase_token(token)

    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    db = get_db()
    user = await db["users"].find_one({"email": email, "is_active": True})
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    user["id"] = str(user["_id"])
    user["_id"] = str(user["_id"])
    return user


def require_role(*roles: str):
    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check
