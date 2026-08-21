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
from pydantic import BaseModel
from app.core.dependencies import get_current_user

from app.config import Settings, settings
from app.services.captures_lookup import get_insurance_expire_month
from app.services.claims_privacy_status import mark_capture_approved

router = APIRouter(prefix="/claims", tags=["claims"])

PRESIGN_EXPIRES = 3600  # 1 hour


def _s3_client(s: Settings):
    if not all([s.r2_endpoint_url, s.r2_access_key_id, s.r2_secret_access_key, s.r2_bucket_name]):
        raise HTTPException(status_code=503, detail="R2 is not configured.")
    return boto3.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _s3_kwargs(s: Settings) -> dict:
    return dict(
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
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

    parts = folder.split(" - ", 2)
    customer = parts[0].strip()
    nic = parts[1].strip()

    s3 = boto3.client("s3", **kwargs)

    # Metadata from the first step-1 photo only (one head_object, not one per photo)
    metadata: Dict[str, str] = {}
    step1_first = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=f"{folder}/step-1-photos-uploaded/",
        MaxKeys=1,
    )
    if step1_first.get("Contents"):
        head = s3.head_object(Bucket=bucket, Key=step1_first["Contents"][0]["Key"])
        metadata = head.get("Metadata", {})

    # Existence checks only — no listing all objects, no head_object per photo
    uv = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=f"{folder}/step-2-fraud-validation/user-verification/",
        MaxKeys=1,
    )
    tp = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=f"{folder}/step-2-fraud-validation/third-party/",
        MaxKeys=1,
    )

    # locations.json
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
    # Read directly from captures (via Supabase), not R2 object metadata like the fields
    # above — unlike those, this doesn't need the sign-photo-upload Edge Function to be
    # redeployed for changes to take effect, and it isn't frozen at upload time.
    expire_month = get_insurance_expire_month(nic, folder)
    if expire_month:
        entry["insuranceExpireMonth"] = expire_month
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

    # Process all claim folders in parallel — eliminates the sequential bottleneck
    loop = asyncio.get_event_loop()
    max_workers = min(len(prefixes), 20)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        tasks = [
            loop.run_in_executor(pool, _process_folder, kwargs, bucket, prefix)
            for prefix in prefixes
        ]
        results = await asyncio.gather(*tasks)

    claims = [r for r in results if r is not None]

    # Sort newest first: folders with a timestamp suffix sort naturally;
    # fall back to submittedDate desc
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


@router.get("/{nic}/enhanced-jobs")
def list_enhanced_jobs_for_claim(nic: str) -> List[Dict[str, Any]]:
    from app.services.r2 import R2Service
    r2 = R2Service()
    if not r2.is_configured:
        return []
    try:
        return r2.list_enhanced_jobs_for_nic(nic)
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


@router.get("/{folder_name}/photos")
def get_claim_photos(folder_name: str) -> Dict[str, List[Any]]:
    """Fetch photo URLs + per-photo metadata for one claim folder.
    Called lazily when the user opens an image panel — never on initial load."""
    s = settings
    s3 = _s3_client(s)
    bucket = s.r2_bucket_name

    def list_with_meta(prefix: str) -> List[Dict[str, Any]]:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        result = []
        for obj in resp.get("Contents", []):
            if obj["Key"].endswith("/"):
                continue
            url = _presign(s3, bucket, obj["Key"])
            try:
                ph = s3.head_object(Bucket=bucket, Key=obj["Key"])
                pmeta = ph.get("Metadata", {})
            except Exception:
                pmeta = {}
            result.append({
                "url": url,
                "gps_lat": float(pmeta["photo-gps-lat"]) if pmeta.get("photo-gps-lat") else None,
                "gps_lng": float(pmeta["photo-gps-lng"]) if pmeta.get("photo-gps-lng") else None,
                "captured_at": pmeta.get("photo-captured-at") or None,
            })
        return result

    return {
        "walkaround": list_with_meta(f"{folder_name}/step-1-photos-uploaded/"),
        "user_verification": list_with_meta(f"{folder_name}/step-2-fraud-validation/user-verification/"),
        "third_party": list_with_meta(f"{folder_name}/step-2-fraud-validation/third-party/"),
    }
