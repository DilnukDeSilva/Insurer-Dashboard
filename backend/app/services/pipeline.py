from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from app.config import settings
from app.schemas.pipeline import (
    JobStatusResponse,
    PipelineJobResponse,
    PipelineJobStatus,
    PipelineStage,
    PipelineStep,
    StepStatus,
)
from app.services.claims_privacy_status import mark_capture_pending_review
from app.services.r2 import R2Service

STEPS = [
    ("download", "Downloading images"),
    ("enhance",  "Enhancing image brightness"),
    ("colmap",   "Mapping camera positions"),
    ("train",    "Reconstructing 3D model"),
    ("export",   "Exporting 3D model"),
]

# In-memory stores (reset on restart)
_job_status: dict[str, JobStatusResponse] = {}
_job_meta: dict[str, dict] = {}   # job_id → {r2_prefix, ...}


def get_job_status(job_id: str) -> JobStatusResponse | None:
    return _job_status.get(job_id)


def _make_steps() -> list[PipelineStep]:
    return [PipelineStep(key=k, label=l) for k, l in STEPS]


class PipelineService:
    def __init__(self) -> None:
        self.r2 = R2Service()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # create_job — download images locally to verify they exist in R2,
    # then store the R2 prefix so run_job can pass it to Modal.
    # ------------------------------------------------------------------
    def create_job(self, folder: str, customer_name: str, nic: str) -> PipelineJobResponse:
        job_id = str(uuid.uuid4())
        images_dir = settings.jobs_dir / job_id / "images"

        status = JobStatusResponse(
            job_id=job_id,
            overall=PipelineJobStatus.PENDING,
            steps=_make_steps(),
        )
        _job_status[job_id] = status

        r2_prefix = f"{folder}/step-1-photos-uploaded/"
        _job_meta[job_id] = {
            "r2_prefix": r2_prefix,
            "folder": folder,
            "customer_name": customer_name,
            "nic": nic,
        }

        status.steps[0].status = StepStatus.RUNNING
        status.steps[0].started_at = time.time()

        self.r2.download_accident_images(folder, images_dir)
        image_count = len(list(images_dir.glob("*")))

        status.steps[0].status = StepStatus.DONE
        status.steps[0].completed_at = time.time()

        # Tag this job with the NIC so it can be found later
        from datetime import datetime, timezone as _tz
        try:
            self.r2.write_job_meta(
                job_id,
                nic=nic,
                customer=customer_name,
                created_at=datetime.now(_tz.utc).isoformat(),
            )
        except Exception:
            pass  # non-fatal — pipeline still runs

        return PipelineJobResponse(
            job_id=job_id,
            status=PipelineJobStatus.PENDING,
            message=f"Downloaded {image_count} images. Ready to run.",
        )

    # ------------------------------------------------------------------
    # run_job — spawn Modal GPU function, poll R2 for live step updates.
    # ------------------------------------------------------------------
    async def run_job(self, job_id: str, skip_zero_dce: bool = False) -> PipelineJobResponse:
        status = _job_status.get(job_id)
        if not status:
            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.FAILED,
                message="Job not found",
            )

        meta = _job_meta.get(job_id, {})
        status.overall = PipelineJobStatus.RUNNING

        try:
            import modal as _modal
            print(f"[pipeline] Spawning Modal job for {job_id}")
            fn = _modal.Function.from_name("insurer-pipeline", "run_pipeline")

            print(f"[pipeline] Modal function found, spawning...")
            # Spawn the GPU function (returns immediately)
            call = fn.spawn(
                job_id=job_id,
                r2_endpoint=settings.r2_endpoint_url,
                r2_key_id=settings.r2_access_key_id,
                r2_secret=settings.r2_secret_access_key,
                r2_bucket=settings.r2_bucket_name,
                images_prefix=meta.get("r2_prefix", ""),
            )

            # Run call.get() in a thread so the event loop stays free
            modal_task = asyncio.create_task(asyncio.to_thread(call.get))

            # Poll R2 status.json every 5 s for live step updates
            while not modal_task.done():
                await asyncio.sleep(5)
                try:
                    r2_status = self.r2.read_status_json(job_id)
                    _merge_steps(status, r2_status)
                except Exception:
                    pass  # status.json not yet written — keep waiting

            # Task finished — check for errors
            try:
                modal_task.result()
            except Exception as exc:
                # Read final status from R2 (Modal wrote it before raising)
                try:
                    r2_status = self.r2.read_status_json(job_id)
                    _merge_steps(status, r2_status)
                except Exception:
                    pass
                status.overall = PipelineJobStatus.FAILED
                status.error = str(exc)
                return PipelineJobResponse(
                    job_id=job_id,
                    status=PipelineJobStatus.FAILED,
                    message=str(exc),
                )

            # Success — read final status
            try:
                r2_status = self.r2.read_status_json(job_id)
                _merge_steps(status, r2_status)
            except Exception:
                pass

            # Low-light: pipeline exited early, no splat to download
            if status.overall == PipelineJobStatus.LOW_LIGHT:
                return PipelineJobResponse(
                    job_id=job_id,
                    status=PipelineJobStatus.LOW_LIGHT,
                    message="Photos too dark for 3D — enhanced images available.",
                )

            splat_local = settings.jobs_dir / job_id / "gs" / "splat" / "splat.ply"
            self.r2.download_file(f"jobs/{job_id}/splat.ply", splat_local)

            status.overall = PipelineJobStatus.COMPLETED
            status.model_url = f"/api/pipeline/jobs/{job_id}/splat"

            # Best-effort — a failure here must not affect the pipeline's own success
            # response, see claims_privacy_status.py.
            try:
                await mark_capture_pending_review(
                    nic=meta.get("nic", ""),
                    customer_name=meta.get("customer_name", ""),
                    folder=meta.get("folder", ""),
                )
            except Exception as exc:
                print(f"[pipeline] mark_capture_pending_review failed: {exc}")

            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.COMPLETED,
                message="Pipeline finished.",
                model_url=f"/api/pipeline/jobs/{job_id}/splat",
            )

        except Exception as exc:
            print(f"[pipeline] ERROR: {exc}")
            status.overall = PipelineJobStatus.FAILED
            status.error = str(exc)
            for step in status.steps:
                if step.status == StepStatus.RUNNING:
                    step.status = StepStatus.FAILED
                    step.completed_at = time.time()
            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.FAILED,
                message=str(exc),
            )

    def list_stages(self) -> list[PipelineStage]:
        return [PipelineStage.ZERO_DCE, PipelineStage.OPENMVG, PipelineStage.OPENMVS]


def _merge_steps(status: JobStatusResponse, r2_status: dict) -> None:
    """Overwrite in-memory step states with whatever Modal wrote to R2."""
    overall = r2_status.get("overall", "")
    if overall == "low_light":
        status.overall = PipelineJobStatus.LOW_LIGHT
    elif overall == "completed":
        status.overall = PipelineJobStatus.COMPLETED
    elif overall == "failed":
        status.overall = PipelineJobStatus.FAILED

    r2_steps = {s["key"]: s for s in r2_status.get("steps", [])}
    for step in status.steps:
        if step.key not in r2_steps:
            continue
        rs = r2_steps[step.key]
        raw = rs.get("status", step.status.value)
        try:
            step.status = StepStatus(raw)
        except ValueError:
            pass
        if rs.get("started_at"):
            step.started_at = rs["started_at"]
        if rs.get("completed_at"):
            step.completed_at = rs["completed_at"]
