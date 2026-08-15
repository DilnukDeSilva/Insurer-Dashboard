"""Direct write into claims-privacy's Neon Postgres — a separate service/repo with no
HTTP API of its own for this. Flips a claim's status once this repo's 3D pipeline
finishes, so the driver's mobile app (which reads captures.status) can show it.

Resolution has no dedicated linking column to key off: this repo only knows a pipeline
job by the R2 folder it was given (name + NIC + optional timestamp), while
claims-privacy's `captures` table has claimant_name/claimant_nic/created_at. Those two
are connected by one fact: claims-privacy derives every capture's R2 folder name from
exactly those three columns (see build_parent_folder_name() in
R26-SE-026/components/claims-privacy/app/r2_metadata.py). Recomputing that same
deterministic string here and matching it against the folder this job was created with
resolves the one capture_id to update, without needing a new column or a new endpoint
on claims-privacy.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

import psycopg
from psycopg.rows import dict_row

from app.config import settings

PENDING_REVIEW_STATUS = "pending_review"
APPROVED_STATUS = "approved"


@contextmanager
def _connect() -> Generator[psycopg.Connection[Any], None, None]:
    with psycopg.connect(settings.claims_privacy_database_url, row_factory=dict_row) as conn:
        yield conn


def _build_parent_folder_name(name: Optional[str], nic: Optional[str], created_at: Any) -> str:
    """Direct port of claims-privacy's r2_metadata.build_parent_folder_name() — the two
    repos share no code, so this must be kept in sync with that function by hand."""
    resolved_name = (name or "UNKNOWN").strip() or "UNKNOWN"
    resolved_nic = (nic or "000000000000").strip() or "000000000000"
    safe_name = re.sub(r"[/\\]", "-", resolved_name)
    safe_nic = re.sub(r"[/\\]", "-", resolved_nic)
    folder = f"{safe_name} - {safe_nic}"
    if isinstance(created_at, datetime):
        folder += f" - {created_at.strftime('%Y-%m-%dT%H-%M-%SZ')}"
    return folder


def _resolve_capture_id(cur: Any, nic: str, folder: str) -> Optional[str]:
    cur.execute(
        "SELECT id, claimant_name, claimant_nic, created_at FROM captures WHERE claimant_nic = %s",
        (nic,),
    )
    rows = cur.fetchall()
    match = next(
        (
            r
            for r in rows
            if _build_parent_folder_name(r["claimant_name"], r["claimant_nic"], r["created_at"]) == folder
        ),
        None,
    )
    return match["id"] if match else None


def _set_capture_status(nic: str, folder: str, status: str) -> bool:
    """Best-effort: never raises. Returns whether a matching capture was found and
    updated, so callers can log it, but a failure here must not affect the caller's
    own success response — same non-fatal spirit as write_job_meta() in pipeline.py."""
    if not settings.claims_privacy_database_url:
        print("[claims-privacy-status] CLAIMS_PRIVACY_DATABASE_URL not configured — skipping")
        return False
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                capture_id = _resolve_capture_id(cur, nic, folder)
                if capture_id is None:
                    print(f"[claims-privacy-status] no capture matched folder={folder!r} nic={nic!r}")
                    return False
                cur.execute("UPDATE captures SET status = %s WHERE id = %s", (status, capture_id))
                conn.commit()
                print(f"[claims-privacy-status] capture {capture_id} -> {status}")
                return True
    except Exception as exc:
        print(f"[claims-privacy-status] failed to update capture status: {exc}")
        return False


def mark_capture_pending_review(nic: str, customer_name: str, folder: str) -> bool:
    return _set_capture_status(nic, folder, PENDING_REVIEW_STATUS)


def mark_capture_approved(nic: str, customer_name: str, folder: str) -> bool:
    return _set_capture_status(nic, folder, APPROVED_STATUS)
