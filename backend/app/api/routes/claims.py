from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.client import Config
from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, settings

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


def _parse_timestamp(ts_iso: Optional[str]) -> tuple[str, str]:
    """Return (date_str, time_str) from an ISO-8601 UTC string."""
    if not ts_iso:
        return ("", "")
    try:
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        return (dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"))
    except Exception:
        return (ts_iso, "")


def _presign(s3, bucket: str, key: str) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=PRESIGN_EXPIRES,
    )


@router.get("")
def list_claims() -> List[Dict[str, Any]]:
    s = settings
    s3 = _s3_client(s)
    bucket = s.r2_bucket_name

    # Top-level folders — each is one accident claim
    resp = s3.list_objects_v2(Bucket=bucket, Delimiter="/")
    prefixes = [p["Prefix"] for p in resp.get("CommonPrefixes", [])]

    claims: List[Dict[str, Any]] = []
    for prefix in prefixes:
        folder = prefix.rstrip("/")

        # Only process claim folders in "Name - NIC" format; skip internal folders like captures/
        if " - " not in folder:
            continue

        # Parse "Name - NIC" from folder name
        parts = folder.split(" - ", 1)
        customer = parts[0].strip()
        nic = parts[1].strip()

        # Read metadata from the first photo in step-1
        metadata: Dict[str, str] = {}
        step1 = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=f"{folder}/step-1-photos-uploaded/",
            MaxKeys=1,
        )
        if step1.get("Contents"):
            head = s3.head_object(Bucket=bucket, Key=step1["Contents"][0]["Key"])
            metadata = head.get("Metadata", {})

        # Collect step-1 walkaround photos with per-photo metadata
        all_step1 = s3.list_objects_v2(Bucket=bucket, Prefix=f"{folder}/step-1-photos-uploaded/")
        accident_images = []
        for obj in all_step1.get("Contents", []):
            if obj["Key"].endswith("/"):
                continue
            url = _presign(s3, bucket, obj["Key"])
            try:
                ph = s3.head_object(Bucket=bucket, Key=obj["Key"])
                pmeta = ph.get("Metadata", {})
            except Exception:
                pmeta = {}
            accident_images.append({
                "url": url,
                "gps_lat": float(pmeta["photo-gps-lat"]) if pmeta.get("photo-gps-lat") else None,
                "gps_lng": float(pmeta["photo-gps-lng"]) if pmeta.get("photo-gps-lng") else None,
                "captured_at": pmeta.get("photo-captured-at") or None,
            })

        # User-verification subfolder: driving licence + drunk test
        uv = s3.list_objects_v2(Bucket=bucket, Prefix=f"{folder}/step-2-fraud-validation/user-verification/")
        user_verification_photos = []
        for obj in uv.get("Contents", []):
            if obj["Key"].endswith("/"):
                continue
            url = _presign(s3, bucket, obj["Key"])
            try:
                ph = s3.head_object(Bucket=bucket, Key=obj["Key"])
                pmeta = ph.get("Metadata", {})
            except Exception:
                pmeta = {}
            user_verification_photos.append({
                "url": url,
                "gps_lat": float(pmeta["photo-gps-lat"]) if pmeta.get("photo-gps-lat") else None,
                "gps_lng": float(pmeta["photo-gps-lng"]) if pmeta.get("photo-gps-lng") else None,
                "captured_at": pmeta.get("photo-captured-at") or None,
            })

        # Third-party subfolder
        tp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{folder}/step-2-fraud-validation/third-party/")
        third_party_photos = []
        for obj in tp.get("Contents", []):
            if obj["Key"].endswith("/"):
                continue
            url = _presign(s3, bucket, obj["Key"])
            try:
                ph = s3.head_object(Bucket=bucket, Key=obj["Key"])
                pmeta = ph.get("Metadata", {})
            except Exception:
                pmeta = {}
            third_party_photos.append({
                "url": url,
                "gps_lat": float(pmeta["photo-gps-lat"]) if pmeta.get("photo-gps-lat") else None,
                "gps_lng": float(pmeta["photo-gps-lng"]) if pmeta.get("photo-gps-lng") else None,
                "captured_at": pmeta.get("photo-captured-at") or None,
            })

        # Read locations.json written by POST /complete
        locations: Dict[str, Any] = {}
        try:
            import json as _json
            loc_obj = s3.get_object(Bucket=bucket, Key=f"{folder}/locations/locations.json")
            locations = _json.loads(loc_obj["Body"].read())
        except Exception:
            pass

        # Report-level data: prefer locations.json (written at submit time), fall back to old R2 metadata
        report_submitted = locations.get("report_submitted", {})
        submitted_date, submitted_time = _parse_timestamp(
            report_submitted.get("captured_at") or metadata.get("report-timestamp")
        )
        report_location = report_submitted.get("location_label") or metadata.get("report-location", "")
        gps_matched = bool(report_submitted.get("gps_lat") or metadata.get("report-gps-lat"))

        entry: Dict[str, Any] = {
            "nic": nic,
            "customer": customer,
            "policyId": metadata.get("policy-number") or "AL-VIP-00001",
            "vehicleModel": metadata.get("vehicle-model") or "Toyota Raize",
            "submittedDate": submitted_date,
            "submittedTime": submitted_time,
            "location": report_location,
            "gpsMatched": gps_matched,
            "timestampSigned": bool(submitted_date),
            "userVerificationAvailable": len(user_verification_photos) > 0,
            "thirdPartyApplicable": len(third_party_photos) > 0,
            "accidentImages": accident_images,
            "userVerificationPhotos": user_verification_photos,
            "thirdPartyPhotos": third_party_photos,
            "locations": locations,
        }
        if metadata.get("vehicle-reg-no"):
            entry["vehicleRegNo"] = metadata["vehicle-reg-no"]
        claims.append(entry)

    return claims


@router.get("/{nic}/enhanced-jobs")
def list_enhanced_jobs_for_claim(nic: str) -> List[Dict[str, Any]]:
    """Return all low-light enhanced photo jobs for a given NIC, newest first."""
    from app.services.r2 import R2Service
    r2 = R2Service()
    if not r2.is_configured:
        return []
    try:
        return r2.list_enhanced_jobs_for_nic(nic)
    except Exception:
        return []


@router.get("/{nic}/models")
def list_models_for_claim(nic: str) -> List[Dict[str, Any]]:
    """Return all completed 3D models for a given NIC, newest first."""
    from app.services.r2 import R2Service
    r2 = R2Service()
    if not r2.is_configured:
        return []
    try:
        return r2.list_models_for_nic(nic)
    except Exception:
        return []


@router.get("/{folder_name}/photos")
def get_claim_photos(folder_name: str) -> Dict[str, List[str]]:
    s = settings
    s3 = _s3_client(s)
    bucket = s.r2_bucket_name

    def list_signed(prefix: str) -> List[str]:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [
            _presign(s3, bucket, obj["Key"])
            for obj in resp.get("Contents", [])
            if not obj["Key"].endswith("/")
        ]

    return {
        "walkaround": list_signed(f"{folder_name}/step-1-photos-uploaded/"),
        "fraud": list_signed(f"{folder_name}/step-2-fraud-validation/"),
    }
