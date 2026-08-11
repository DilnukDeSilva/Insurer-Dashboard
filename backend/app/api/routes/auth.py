from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.db.mongo import get_db
from app.services.auth import create_access_token, verify_password
from app.services.supabase_service import sb_get

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    role: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    db = get_db()
    user = await db["users"].find_one({"email": body.email, "is_active": True})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    company_name = None
    if user.get("company_id"):
        try:
            rows = await sb_get(
                "insurance_companies",
                {"id": f"eq.{user['company_id']}", "select": "company_name"},
            )
            if rows:
                company_name = rows[0]["company_name"]
        except Exception:
            pass

    token = create_access_token({
        "sub": user["email"],
        "role": user["role"],
        "name": user["name"],
        "company_id": str(user.get("company_id") or ""),
    })
    return TokenResponse(
        access_token=token,
        name=user["name"],
        role=user["role"],
        company_id=str(user["company_id"]) if user.get("company_id") else None,
        company_name=company_name,
    )


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)) -> dict:
    return {
        "email": current_user["email"],
        "name": current_user["name"],
        "role": current_user["role"],
        "company_id": current_user.get("company_id"),
    }
