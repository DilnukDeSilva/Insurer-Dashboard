"""Cloudflare R2 download service for accident images."""

from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config

from app.config import settings


class R2Service:
    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.r2_bucket_name

    @property
    def is_configured(self) -> bool:
        return all([
            settings.r2_endpoint_url,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
        ])

    def download_accident_images(self, folder: str, dest_dir: Path) -> list[Path]:
        """
        Download accident images from R2 folder: {folder}/step-1-photos-uploaded/

        `folder` is the claim's exact top-level R2 prefix (as returned by
        GET /claims), not reconstructed from customer name + NIC — a claimant can
        have multiple claims, each in its own folder distinguished by a timestamp.
        """
        if not self.is_configured:
            raise RuntimeError("R2 credentials are not configured.")

        prefix = f"{folder}/step-1-photos-uploaded/"
        dest_dir.mkdir(parents=True, exist_ok=True)

        response = self.client.list_objects_v2(
            Bucket=self.bucket, Prefix=prefix
        )
        objects = response.get("Contents", [])

        if not objects:
            raise FileNotFoundError(
                f"No images found in R2 at prefix: {prefix}"
            )

        downloaded: list[Path] = []
        for obj in objects:
            key: str = obj["Key"]
            filename = Path(key).name
            if not filename:
                continue
            local_path = dest_dir / filename
            self.client.download_file(self.bucket, key, str(local_path))
            downloaded.append(local_path)

        return downloaded

    def upload_file(self, local_path: Path, r2_key: str) -> None:
        """Upload a local file to R2 at the given key."""
        self.client.upload_file(str(local_path), self.bucket, r2_key)

    def download_file(self, r2_key: str, local_path: Path) -> None:
        """Download a single R2 object to a local path."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, r2_key, str(local_path))

    def read_status_json(self, job_id: str) -> dict:
        """Read the step-progress JSON written by the Modal function."""
        response = self.client.get_object(
            Bucket=self.bucket,
            Key=f"jobs/{job_id}/status.json",
        )
        return __import__("json").loads(response["Body"].read())

    def write_job_meta(self, job_id: str, nic: str, customer: str, created_at: str, folder: Optional[str] = None) -> None:
        """Write meta.json so this job can later be looked up by folder or NIC."""
        import json as _json
        body = _json.dumps({"nic": nic, "customer": customer, "created_at": created_at, "folder": folder})
        self.client.put_object(
            Bucket=self.bucket,
            Key=f"jobs/{job_id}/meta.json",
            Body=body.encode(),
            ContentType="application/json",
        )

    def list_enhanced_jobs_for_nic(self, nic: str) -> list[dict]:
        """Return all jobs that have enhanced photos for a given NIC, newest first."""
        import json as _json

        resp = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix="jobs/",
            Delimiter="/",
        )

        results = []
        for prefix_obj in resp.get("CommonPrefixes", []):
            job_id = prefix_obj["Prefix"].rstrip("/").split("/")[-1]

            try:
                meta_resp = self.client.get_object(
                    Bucket=self.bucket, Key=f"jobs/{job_id}/meta.json"
                )
                meta = _json.loads(meta_resp["Body"].read())
            except Exception:
                continue

            if meta.get("nic") != nic:
                continue

            # Only include jobs that actually have enhanced photos
            check = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=f"jobs/{job_id}/enhanced/",
                MaxKeys=1,
            )
            if not check.get("Contents"):
                continue

            results.append({
                "job_id": job_id,
                "created_at": meta.get("created_at", ""),
            })

        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results

    def list_enhanced_photos(self, job_id: str) -> list[str]:
        """Return pre-signed URLs for all enhanced photos stored under jobs/{job_id}/enhanced/."""
        prefix = f"jobs/{job_id}/enhanced/"
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        urls = []
        for obj in resp.get("Contents", []):
            if obj["Key"].endswith("/"):
                continue
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": obj["Key"]},
                ExpiresIn=3600,
            )
            urls.append(url)
        return urls

    def list_models_for_nic(self, nic: str) -> list[dict]:
        """Return all completed jobs (have splat.ply) for a given NIC, newest first."""
        import json as _json

        resp = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix="jobs/",
            Delimiter="/",
        )

        results = []
        for prefix_obj in resp.get("CommonPrefixes", []):
            job_id = prefix_obj["Prefix"].rstrip("/").split("/")[-1]

            try:
                meta_resp = self.client.get_object(
                    Bucket=self.bucket, Key=f"jobs/{job_id}/meta.json"
                )
                meta = _json.loads(meta_resp["Body"].read())
            except Exception:
                continue

            if meta.get("nic") != nic:
                continue

            try:
                self.client.head_object(Bucket=self.bucket, Key=f"jobs/{job_id}/splat.ply")
            except Exception:
                continue

            results.append({
                "job_id": job_id,
                "created_at": meta.get("created_at", ""),
                "customer": meta.get("customer", ""),
            })

        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results

    def list_models_for_folder(self, folder: str, nic: str) -> list[dict]:
        """Return completed jobs for a specific claim folder.
        Matches on meta['folder'] when available (new jobs); falls back to
        meta['nic'] for older jobs that were created before folder was stored."""
        import json as _json

        resp = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix="jobs/",
            Delimiter="/",
        )

        results = []
        for prefix_obj in resp.get("CommonPrefixes", []):
            job_id = prefix_obj["Prefix"].rstrip("/").split("/")[-1]

            try:
                meta_resp = self.client.get_object(
                    Bucket=self.bucket, Key=f"jobs/{job_id}/meta.json"
                )
                meta = _json.loads(meta_resp["Body"].read())
            except Exception:
                continue

            # Prefer exact folder match; fall back to nic for pre-folder jobs
            if meta.get("folder") is not None:
                if meta["folder"] != folder:
                    continue
            elif meta.get("nic") != nic:
                continue

            try:
                self.client.head_object(Bucket=self.bucket, Key=f"jobs/{job_id}/splat.ply")
            except Exception:
                continue

            results.append({
                "job_id": job_id,
                "created_at": meta.get("created_at", ""),
                "customer": meta.get("customer", ""),
                "folder": meta.get("folder"),
            })

        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results
