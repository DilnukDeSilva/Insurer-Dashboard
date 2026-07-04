"""Cloudflare R2 download service for accident images."""

from pathlib import Path

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

    def download_accident_images(
        self, customer_name: str, nic: str, dest_dir: Path
    ) -> list[Path]:
        """
        Download accident images from R2 folder:
        {customer_name} - {nic}/step-1-photos-uploaded/
        """
        if not self.is_configured:
            raise RuntimeError("R2 credentials are not configured.")

        prefix = f"{customer_name} - {nic}/step-1-photos-uploaded/"
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
