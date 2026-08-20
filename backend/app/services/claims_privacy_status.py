"""Flips a claim's status once this repo's 3D pipeline finishes (or an officer approves
it), so the driver's mobile app — which now reads captures.status directly from
Supabase (RLS-protected) — can show it. `captures` used to live in a separate Neon
Postgres DB owned by the claims-privacy service, reached here via a direct psycopg
connection; it has since been migrated into this project's own Supabase Postgres, so
this now reuses the generic REST client (sb_get/sb_patch) already used for
insurance_companies — see supabase_service.py.

Resolution still has no dedicated linking column to key off: this repo only knows a
pipeline job by the R2 folder it was given (name + NIC + optional timestamp), while
`captures` has claimant_name/claimant_nic/created_at. Those two are connected by one
fact: every capture's R2 folder name is a deterministic function of exactly those three
columns (see build_parent_folder_name() in
R26-SE-026/components/claims-privacy/app/r2_metadata.py, and its port in
R26-SE-026/apps/mobile/supabase/functions/sign-photo-upload/index.ts). Recomputing that
same string here and matching it against the folder this job was created with resolves
the one capture id to update.
"""

from __future__ import annotations

from typing import Optional

from app.services.captures_lookup import build_parent_folder_name
from app.services.supabase_service import sb_get, sb_patch

PENDING_REVIEW_STATUS = "pending_review"
APPROVED_STATUS = "approved"


async def _resolve_capture_id(nic: str, folder: str) -> Optional[str]:
    rows = await sb_get(
        "captures",
        {"claimant_nic": f"eq.{nic}", "select": "id,claimant_name,claimant_nic,created_at"},
    )
    match = next(
        (
            r
            for r in rows
            if build_parent_folder_name(r.get("claimant_name"), r.get("claimant_nic"), r.get("created_at")) == folder
        ),
        None,
    )
    return match["id"] if match else None


async def _set_capture_status(nic: str, folder: str, status: str) -> bool:
    """Best-effort: never raises. Returns whether a matching capture was found and
    updated, so callers can log it, but a failure here must not affect the caller's
    own success response — same non-fatal spirit as write_job_meta() in pipeline.py.
    Uses the service_role-equivalent Supabase key already configured for
    insurance_companies, which bypasses RLS — no special "insurer" policy needed."""
    try:
        capture_id = await _resolve_capture_id(nic, folder)
        if capture_id is None:
            print(f"[claims-privacy-status] no capture matched folder={folder!r} nic={nic!r}")
            return False
        await sb_patch("captures", "id", capture_id, {"status": status})
        print(f"[claims-privacy-status] capture {capture_id} -> {status}")
        return True
    except Exception as exc:
        print(f"[claims-privacy-status] failed to update capture status: {exc}")
        return False


async def mark_capture_pending_review(nic: str, customer_name: str, folder: str) -> bool:
    return await _set_capture_status(nic, folder, PENDING_REVIEW_STATUS)


async def mark_capture_approved(nic: str, customer_name: str, folder: str) -> bool:
    return await _set_capture_status(nic, folder, APPROVED_STATUS)
