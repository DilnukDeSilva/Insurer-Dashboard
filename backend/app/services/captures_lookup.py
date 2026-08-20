"""Direct Supabase lookups against the mobile app's `captures` table, for fields that
live there but were never baked into R2 object metadata (unlike policy-number,
vehicle-model, etc., which claims.py still reads from R2 metadata at upload time).

There's no dedicated linking column to key off: this repo only knows a claim by the R2
folder it's stored under (name + NIC + optional timestamp), while `captures` has
claimant_name/claimant_nic/created_at. Those are connected by one fact: every capture's
R2 folder name is a deterministic function of exactly those three columns (see
build_parent_folder_name() below, kept in sync by hand with
R26-SE-026/apps/mobile/supabase/functions/sign-photo-upload/index.ts's port of the same
logic — the two repos share no code). Recomputing that same string and matching it
against the folder resolves the one capture row.

Sync (not async httpx like supabase_service.py's sb_get/sb_patch) since this is called
from claims.py's _process_folder, which itself runs inside a thread pool, not the
asyncio event loop — see list_claims().
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings


def _headers() -> Dict[str, str]:
    return {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
    }


def build_parent_folder_name(name: Optional[str], nic: Optional[str], created_at: Any) -> str:
    """Direct port of claims-privacy's r2_metadata.build_parent_folder_name()."""
    resolved_name = (name or "UNKNOWN").strip() or "UNKNOWN"
    resolved_nic = (nic or "000000000000").strip() or "000000000000"
    safe_name = re.sub(r"[/\\]", "-", resolved_name)
    safe_nic = re.sub(r"[/\\]", "-", resolved_nic)
    folder = f"{safe_name} - {safe_nic}"

    dt: Optional[datetime] = None
    if isinstance(created_at, datetime):
        dt = created_at
    elif isinstance(created_at, str) and created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            dt = None
    if dt is not None:
        folder += f" - {dt.strftime('%Y-%m-%dT%H-%M-%SZ')}"
    return folder


def get_insurance_expire_month(nic: str, folder: str) -> Optional[str]:
    """Best-effort: returns the matching capture's insurance_expire_month, or None on
    no match / any failure — a lookup failure here must not break the claims list."""
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(
                f"{settings.supabase_url}/rest/v1/captures",
                headers=_headers(),
                params={
                    "claimant_nic": f"eq.{nic}",
                    "select": "claimant_name,claimant_nic,created_at,insurance_expire_month",
                },
            )
            r.raise_for_status()
            rows: List[Dict[str, Any]] = r.json()
        match = next(
            (
                row
                for row in rows
                if build_parent_folder_name(row.get("claimant_name"), row.get("claimant_nic"), row.get("created_at"))
                == folder
            ),
            None,
        )
        return match.get("insurance_expire_month") if match else None
    except Exception:
        return None
