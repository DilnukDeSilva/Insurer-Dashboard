from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import require_role
from app.db.mongo import get_db
from app.services.auth import hash_password
from app.services.supabase_service import sb_get, sb_patch, sb_post

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = require_role("admin")
admin_or_agent = require_role("admin", "agent")


# ── Schemas ────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    app_name: str
    phone_tel: Optional[str] = None
    contact_email: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: str
    app_name: str
    phone_tel: Optional[str] = None
    contact_email: Optional[str] = None


class CompanyOut(BaseModel):
    id: str
    name: str
    app_name: str
    phone_tel: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: bool


class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str  # "admin" | "agent" | "staff"
    company_id: Optional[str] = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool


# ── Companies ──────────────────────────────────────────────────

def _row_to_company(r: Dict[str, Any]) -> CompanyOut:
    return CompanyOut(
        id=r["id"],
        name=r["company_name"],
        app_name=r.get("app_name") or "",
        phone_tel=r.get("phone_tel"),
        contact_email=r.get("contact_email"),
        is_active=r.get("is_active", True),
    )


@router.get("/companies", response_model=List[CompanyOut])
async def list_companies(_: dict = Depends(admin_only)) -> List[CompanyOut]:
    rows = await sb_get("insurance_companies", {"select": "*", "order": "company_name.asc"})
    return [_row_to_company(r) for r in rows]


@router.post("/companies", response_model=CompanyOut)
async def create_company(body: CompanyCreate, _: dict = Depends(admin_only)) -> CompanyOut:
    row = await sb_post("insurance_companies", {
        "company_name": body.name,
        "app_name": body.app_name,
        "phone_tel": body.phone_tel,
        "contact_email": body.contact_email,
        "is_active": True,
    })
    return _row_to_company(row)


@router.put("/companies/{company_id}", response_model=CompanyOut)
async def update_company(company_id: str, body: CompanyUpdate, _: dict = Depends(admin_only)) -> CompanyOut:
    await sb_patch("insurance_companies", "id", company_id, {
        "company_name": body.name,
        "app_name": body.app_name,
        "phone_tel": body.phone_tel,
        "contact_email": body.contact_email,
    })
    rows = await sb_get("insurance_companies", {"id": f"eq.{company_id}", "select": "*"})
    if not rows:
        raise HTTPException(status_code=404, detail="Company not found")
    return _row_to_company(rows[0])


@router.patch("/companies/{company_id}")
async def toggle_company(company_id: str, _: dict = Depends(admin_only)) -> Dict[str, Any]:
    rows = await sb_get("insurance_companies", {"id": f"eq.{company_id}", "select": "is_active"})
    if not rows:
        raise HTTPException(status_code=404, detail="Company not found")
    new_state = not rows[0].get("is_active", True)
    await sb_patch("insurance_companies", "id", company_id, {"is_active": new_state})
    return {"id": company_id, "is_active": new_state}


# ── Users (admin manages all roles) ───────────────────────────

@router.get("/users", response_model=List[UserOut])
async def list_users(_: dict = Depends(admin_only)) -> List[UserOut]:
    db = get_db()
    users = await db["users"].find().to_list(length=500)

    company_ids = [u["company_id"] for u in users if u.get("company_id")]
    companies: Dict[str, str] = {}
    if company_ids:
        docs = await db["companies"].find(
            {"_id": {"$in": [ObjectId(c) for c in company_ids]}}
        ).to_list(length=200)
        companies = {str(d["_id"]): d["name"] for d in docs}

    return [
        UserOut(
            id=str(u["_id"]),
            email=u["email"],
            name=u["name"],
            role=u["role"],
            company_id=str(u["company_id"]) if u.get("company_id") else None,
            company_name=companies.get(str(u.get("company_id", ""))) if u.get("company_id") else None,
            is_active=u.get("is_active", True),
        )
        for u in users
    ]


@router.post("/users", response_model=UserOut)
async def create_user(body: UserCreate, _: dict = Depends(admin_only)) -> UserOut:
    db = get_db()
    if await db["users"].find_one({"email": body.email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    company_oid = ObjectId(body.company_id) if body.company_id else None
    doc: Dict[str, Any] = {
        "email": body.email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "role": body.role,
        "company_id": company_oid,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db["users"].insert_one(doc)
    return UserOut(
        id=str(result.inserted_id),
        email=body.email,
        name=body.name,
        role=body.role,
        company_id=body.company_id,
        is_active=True,
    )


@router.patch("/users/{user_id}")
async def toggle_user(user_id: str, _: dict = Depends(admin_only)) -> Dict[str, Any]:
    db = get_db()
    doc = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    new_state = not doc.get("is_active", True)
    await db["users"].update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"is_active": new_state}}
    )
    return {"id": user_id, "is_active": new_state}


# ── Agent: create Staff accounts for their own company ─────────

@router.post("/agent/users", response_model=UserOut)
async def agent_create_staff(
    body: UserCreate,
    current_user: dict = Depends(admin_or_agent),
) -> UserOut:
    if current_user["role"] == "agent" and body.role != "staff":
        raise HTTPException(status_code=403, detail="Agents can only create Staff accounts")

    db = get_db()
    if await db["users"].find_one({"email": body.email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    company_id = body.company_id or current_user.get("company_id")
    doc: Dict[str, Any] = {
        "email": body.email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "role": "staff",
        "company_id": company_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db["users"].insert_one(doc)
    return UserOut(
        id=str(result.inserted_id),
        email=body.email,
        name=body.name,
        role="staff",
        company_id=company_id,
        is_active=True,
    )
