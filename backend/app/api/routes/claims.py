from __future__ import annotations

import asyncio
import concurrent.futures
import json as _json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.client import Config
from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError
from pydantic import BaseModel
from app.core.dependencies import get_current_user

from app.config import Settings, settings
from app.services.auth import create_claim_link_token, decode_claim_link_token
from app.services.captures_lookup import get_insurance_expire_month
from app.services.claims_privacy_status import mark_capture_approved
from app.services.sms import send_sms
from app.services.supabase_service import sb_get

router = APIRouter(prefix="/claims", tags=["claims"])

PRESIGN_EXPIRES = 3600  # 1 hour


def _s3_client(s: Settings):
    if not all([s.r2_endpoint_url, s.r2_access_key_id, s.r2_secret_access_key, s.r2_bucket_name]):
        raise HTTPException(status_code=503, detail="R2 is not configured.")
    return boto3.client("s3", **_s3_kwargs(s))


def _s3_kwargs(s: Settings) -> dict:
    return dict(
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 1},
        ),
        region_name="auto",
    )


def _parse_timestamp(ts_iso: Optional[str]) -> tuple:
    if not ts_iso:
        return ("", "")
    try:
        normalized = ts_iso.replace("Z", "+00:00")
        # datetime.fromisoformat() only accepts exactly 3 or 6 fractional-second
        # digits — pad/truncate any other precision (e.g. ".54") to 6 so a
        # otherwise-valid timestamp doesn't fall through to the raw-string
        # fallback below and show up unformatted in the dashboard.
        normalized = re.sub(
            r"\.(\d+)",
            lambda m: "." + (m.group(1) + "000000")[:6],
            normalized,
        )
        dt = datetime.fromisoformat(normalized).astimezone(timezone.utc)
        return (dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"))
    except Exception:
        return (ts_iso, "")


def _presign(s3, bucket: str, key: str) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=PRESIGN_EXPIRES,
    )


def _process_folder(kwargs: dict, bucket: str, prefix: str) -> Optional[Dict[str, Any]]:
    """Process a single claim folder. Runs in a thread pool — no await."""
    folder = prefix.rstrip("/")
    if " - " not in folder:
        return None
    try:
        return _process_folder_inner(kwargs, bucket, folder)
    except Exception:
        return None


def _process_folder_inner(kwargs: dict, bucket: str, folder: str) -> Optional[Dict[str, Any]]:
    parts = folder.split(" - ", 2)
    customer = parts[0].strip()
    nic = parts[1].strip()

    s3 = boto3.client("s3", **kwargs)

    metadata: Dict[str, str] = {}
    step1_first = s3.list_objects_v2(Bucket=bucket, Prefix=f"{folder}/step-1-photos-uploaded/", MaxKeys=1)
    if step1_first.get("Contents"):
        try:
            head = s3.head_object(Bucket=bucket, Key=step1_first["Contents"][0]["Key"])
            metadata = head.get("Metadata", {})
        except Exception:
            metadata = {}

    uv = s3.list_objects_v2(Bucket=bucket, Prefix=f"{folder}/step-2-fraud-validation/user-verification/", MaxKeys=1)
    tp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{folder}/step-2-fraud-validation/third-party/", MaxKeys=1)

    locations: Dict[str, Any] = {}
    try:
        loc_obj = s3.get_object(Bucket=bucket, Key=f"{folder}/locations/locations.json")
        locations = _json.loads(loc_obj["Body"].read())
    except Exception:
        pass

    report_submitted = locations.get("report_submitted", {})
    submitted_date, submitted_time = _parse_timestamp(
        report_submitted.get("captured_at") or metadata.get("report-timestamp")
    )
    report_location = report_submitted.get("location_label") or metadata.get("report-location", "")
    gps_matched = bool(report_submitted.get("gps_lat") or metadata.get("report-gps-lat"))

    entry: Dict[str, Any] = {
        "nic": nic,
        "customer": customer,
        "folder": folder,
        "policyId": metadata.get("policy-number") or "AL-VIP-00001",
        "vehicleModel": metadata.get("vehicle-model") or "Toyota Raize",
        "submittedDate": submitted_date,
        "submittedTime": submitted_time,
        "location": report_location,
        "gpsMatched": gps_matched,
        "timestampSigned": bool(submitted_date),
        "userVerificationAvailable": bool(uv.get("Contents")),
        "thirdPartyApplicable": bool(tp.get("Contents")),
        # Photos are fetched lazily via GET /claims/{folder}/photos
        "accidentImages": [],
        "userVerificationPhotos": [],
        "thirdPartyPhotos": [],
        "locations": locations,
    }
    if metadata.get("vehicle-reg-no"):
        entry["vehicleRegNo"] = metadata["vehicle-reg-no"]
    return entry


@router.get("")
async def list_claims(_: dict = Depends(get_current_user)) -> List[Dict[str, Any]]:
    s = settings
    if not all([s.r2_endpoint_url, s.r2_access_key_id, s.r2_secret_access_key, s.r2_bucket_name]):
        raise HTTPException(status_code=503, detail="R2 is not configured.")

    kwargs = _s3_kwargs(s)
    s3 = boto3.client("s3", **kwargs)
    bucket = s.r2_bucket_name

    resp = s3.list_objects_v2(Bucket=bucket, Delimiter="/")
    prefixes = [p["Prefix"] for p in resp.get("CommonPrefixes", [])]

    if not prefixes:
        return []

    loop = asyncio.get_event_loop()
    max_workers = min(len(prefixes), 20)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        tasks = [
            loop.run_in_executor(pool, _process_folder, kwargs, bucket, prefix)
            for prefix in prefixes
        ]
        results = await asyncio.gather(*tasks)

    claims = [r for r in results if r is not None]
    claims.sort(key=lambda c: (c.get("submittedDate") or ""), reverse=True)
    return claims


class ApproveClaimRequest(BaseModel):
    nic: str
    customer_name: str
    folder: str


@router.post("/approve")
async def approve_claim(body: ApproveClaimRequest, _: dict = Depends(get_current_user)) -> Dict[str, bool]:
    ok = await mark_capture_approved(nic=body.nic, customer_name=body.customer_name, folder=body.folder)
    if not ok:
        raise HTTPException(status_code=404, detail="Could not find a matching claim to approve.")
    return {"approved": True}


class CreateClaimLinkRequest(BaseModel):
    nic: str
    plate_number: str
    phone: Optional[str] = None


CLAIM_LINK_EXPIRE_HOURS = 48


@router.post("/claim-links")
async def create_claim_link(
    body: CreateClaimLinkRequest, current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Mints a shareable, no-app-required link an insurer sends a claimant so
    they can report an accident from a plain mobile browser. Stateless — the
    token itself carries everything the claimant page needs, so there's
    nothing here to store or clean up later."""
    token = create_claim_link_token(
        {
            "nic": body.nic.strip(),
            "plateNumber": body.plate_number.strip().upper(),
            "insurerId": current_user["id"],
            # Not sent anywhere yet (no SMS/WhatsApp integration in v1 — see
            # the plan) — carried through so it isn't silently dropped, and
            # is already threaded for whenever that's added.
            "phone": body.phone.strip() if body.phone else None,
        },
        expire_hours=CLAIM_LINK_EXPIRE_HOURS,
    )
    return {
        "token": token,
        # kaduna-web is a static export (no dynamic path segments at runtime) —
        # the token is a query param the client page reads itself, not a route param.
        "url": f"{settings.claimant_web_base_url}/claim?token={token}",
        "expiresInHours": CLAIM_LINK_EXPIRE_HOURS,
    }


@router.get("/claim-links/{token}")
def verify_claim_link(token: str) -> Dict[str, Any]:
    """Public (no auth) — the claimant page calls this itself to recover the
    NIC/plate to pre-fill, since the token is HS256-signed with a
    server-only secret the browser can't verify on its own."""
    try:
        payload = decode_claim_link_token(token)
    except (JWTError, ValueError):
        raise HTTPException(status_code=404, detail="This link is invalid or has expired.")
    return {"nic": payload["nic"], "plateNumber": payload["plateNumber"]}


class SendClaimLinkSmsRequest(BaseModel):
    phone: str
    url: str


@router.post("/claim-links/send-sms")
async def send_claim_link_sms(
    body: SendClaimLinkSmsRequest, _: dict = Depends(get_current_user)
) -> Dict[str, bool]:
    """Texts an already-generated claim link to the claimant via Notify.lk.
    Kept separate from create_claim_link so staff can fix up the phone number
    (or type one in when it wasn't auto-filled from the vehicle search) after
    seeing the generated link, without having to regenerate it."""
    try:
        await send_sms(body.phone, f"Report your accident here: {body.url}")
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"sent": True}


_PLATE_QUERY_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9\- ]")


class VehicleSearchResult(BaseModel):
    plate_number: str
    vehicle_model: Optional[str] = None
    nic: Optional[str] = None
    phone: Optional[str] = None


@router.get("/vehicle-search")
async def search_vehicles(q: str, _: dict = Depends(get_current_user)) -> List[VehicleSearchResult]:
    """Insurer-side typeahead for the claim-link form's Vehicle Reg No field —
    looks up vehicles across ALL drivers (not just the insurer's own data,
    which an insurer session has none of) via the service-role key, same
    bypass-RLS pattern as the verify-claimant edge function. `q` is stripped
    to plate-number-safe characters before being used in an ilike pattern, so
    there's no LIKE-wildcard-injection path from arbitrary user input."""
    sanitized = _PLATE_QUERY_UNSAFE_CHARS.sub("", q).strip().upper()
    if len(sanitized) < 2:
        return []

    vehicles = await sb_get(
        "vehicles",
        {
            "plate_number": f"ilike.*{sanitized}*",
            "select": "user_id,model,plate_number",
            "order": "plate_number.asc",
            "limit": "8",
        },
    )
    if not vehicles:
        return []

    user_ids = {v["user_id"] for v in vehicles}
    profiles = await sb_get(
        "profiles",
        {
            "id": f"in.({','.join(user_ids)})",
            "select": "id,nic_number,phone",
        },
    )
    profile_by_id = {p["id"]: p for p in profiles}

    return [
        VehicleSearchResult(
            plate_number=v["plate_number"],
            vehicle_model=v.get("model"),
            nic=profile_by_id.get(v["user_id"], {}).get("nic_number"),
            phone=profile_by_id.get(v["user_id"], {}).get("phone"),
        )
        for v in vehicles
    ]


@router.get("/{folder_name}/enhanced-jobs")
def list_enhanced_jobs_for_claim(folder_name: str) -> List[Dict[str, Any]]:
    from app.services.r2 import R2Service
    r2 = R2Service()
    if not r2.is_configured:
        return []
    parts = folder_name.split(" - ", 2)
    nic = parts[1].strip() if len(parts) > 1 else folder_name
    try:
        return r2.list_enhanced_jobs_for_folder(folder=folder_name, nic=nic)
    except Exception:
        return []


@router.get("/{folder_name}/models")
def list_models_for_claim(folder_name: str) -> List[Dict[str, Any]]:
    from app.services.r2 import R2Service
    r2 = R2Service()
    if not r2.is_configured:
        return []
    # Extract NIC from folder for backward-compat fallback (folder = "Name - NIC" or "Name - NIC - ts")
    parts = folder_name.split(" - ", 2)
    nic = parts[1].strip() if len(parts) > 1 else folder_name
    try:
        return r2.list_models_for_folder(folder=folder_name, nic=nic)
    except Exception:
        return []


@router.get("/{folder_name}/expiry")
def get_claim_expiry(folder_name: str) -> Dict[str, Any]:
    parts = folder_name.split(" - ", 2)
    nic = parts[1].strip() if len(parts) > 1 else folder_name
    expire = get_insurance_expire_month(nic, folder_name)
    return {"insuranceExpireMonth": expire}


@router.get("/{folder_name}/photos")
def get_claim_photos(folder_name: str) -> Dict[str, List[Any]]:
    """Fetch photo URLs + per-photo metadata for one claim folder.
    Called lazily when the user opens an image panel — never on initial load."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    s = settings
    s3 = _s3_client(s)
    bucket = s.r2_bucket_name

    def _fetch_one(key: str) -> Dict[str, Any]:
        url = _presign(s3, bucket, key)
        try:
            pmeta = s3.head_object(Bucket=bucket, Key=key).get("Metadata", {})
        except Exception:
            pmeta = {}
        return {
            "url": url,
            "gps_lat": float(pmeta["photo-gps-lat"]) if pmeta.get("photo-gps-lat") else None,
            "gps_lng": float(pmeta["photo-gps-lng"]) if pmeta.get("photo-gps-lng") else None,
            "captured_at": pmeta.get("photo-captured-at") or None,
        }

    def list_with_meta(prefix: str) -> List[Dict[str, Any]]:
        keys = sorted(
            obj["Key"] for obj in
            s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])
            if not obj["Key"].endswith("/")
        )
        if not keys:
            return []
        with ThreadPoolExecutor(max_workers=min(len(keys), 20)) as pool:
            # Submit in sorted key order and collect in that same order so the
            # frontend sees photos in capture sequence (lexicographic filename order
            # matches sequential camera naming from phone cameras).
            futures = [pool.submit(_fetch_one, k) for k in keys]
            return [f.result() for f in futures if f.result()]

    # All three categories fetched in parallel
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_walk = pool.submit(list_with_meta, f"{folder_name}/step-1-photos-uploaded/")
        f_uv   = pool.submit(list_with_meta, f"{folder_name}/step-2-fraud-validation/user-verification/")
        f_tp   = pool.submit(list_with_meta, f"{folder_name}/step-2-fraud-validation/third-party/")

    return {
        "walkaround":        f_walk.result(),
        "user_verification": f_uv.result(),
        "third_party":       f_tp.result(),
    }
