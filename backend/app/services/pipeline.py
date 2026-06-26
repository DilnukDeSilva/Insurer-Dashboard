from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

from app.config import settings
from app.schemas.pipeline import (
    JobStatusResponse,
    PipelineJobResponse,
    PipelineJobStatus,
    PipelineStage,
    PipelineStep,
    StepStatus,
)
from app.services.openmvg import OpenMVGService
from app.services.openmvs import OpenMVSService
from app.services.r2 import R2Service
from app.services.zero_dce import ZeroDCEService

STEPS = [
    ("download",  "Downloading images"),
    ("features",  "Computing features"),
    ("matching",  "Matching features"),
    ("sfm",       "Structure from Motion"),
    ("export",    "Exporting scene"),
    ("densify",   "Dense point cloud"),
    ("mesh",      "Reconstructing mesh"),
    ("texture",   "Texturing mesh"),
    ("convert",   "Converting to 3D"),
]

# In-memory status store: job_id → JobStatusResponse
_job_status: dict[str, JobStatusResponse] = {}


def get_job_status(job_id: str) -> JobStatusResponse | None:
    return _job_status.get(job_id)


def _make_steps() -> list[PipelineStep]:
    return [PipelineStep(key=k, label=l) for k, l in STEPS]


class PipelineService:
    def __init__(self) -> None:
        self.zero_dce = ZeroDCEService()
        self.openmvg = OpenMVGService()
        self.openmvs = OpenMVSService()
        self.r2 = R2Service()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create_job(self, customer_name: str, nic: str) -> PipelineJobResponse:
        job_id = str(uuid.uuid4())
        job_dir = settings.jobs_dir / job_id
        images_dir = job_dir / "images"

        _job_status[job_id] = JobStatusResponse(
            job_id=job_id,
            overall=PipelineJobStatus.PENDING,
            steps=_make_steps(),
        )

        self.r2.download_accident_images(customer_name, nic, images_dir)

        image_count = len(list(images_dir.glob("*")))
        _job_status[job_id].steps[0].status = StepStatus.DONE

        return PipelineJobResponse(
            job_id=job_id,
            status=PipelineJobStatus.PENDING,
            message=f"Downloaded {image_count} images. Ready to run.",
        )

    async def run_job(self, job_id: str, skip_zero_dce: bool = False) -> PipelineJobResponse:
        job_dir = settings.jobs_dir / job_id
        if not job_dir.exists():
            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.FAILED,
                message="Job not found",
            )

        status = _job_status.setdefault(job_id, JobStatusResponse(
            job_id=job_id,
            overall=PipelineJobStatus.RUNNING,
            steps=_make_steps(),
        ))
        status.overall = PipelineJobStatus.RUNNING

        def mark(key: str, s: StepStatus) -> None:
            for step in status.steps:
                if step.key == key:
                    step.status = s
                    return

        images_dir = job_dir / "images"
        sfm_dir = job_dir / "sfm"
        mvs_dir = job_dir / "mvs"

        try:
            self.openmvg.run_sfm(
                images_dir, sfm_dir,
                on_step=mark,
            )
            self.openmvs.run_dense_reconstruction(
                sfm_dir, mvs_dir,
                on_step=mark,
            )

            status.overall = PipelineJobStatus.COMPLETED
            status.model_url = f"/api/pipeline/jobs/{job_id}/model"

            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.COMPLETED,
                message="Pipeline finished.",
                model_url=f"/api/pipeline/jobs/{job_id}/model",
            )
        except Exception as exc:
            status.overall = PipelineJobStatus.FAILED
            status.error = str(exc)
            for step in status.steps:
                if step.status == StepStatus.RUNNING:
                    step.status = StepStatus.FAILED
            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.FAILED,
                message=str(exc),
            )

    def list_stages(self) -> list[PipelineStage]:
        return [PipelineStage.ZERO_DCE, PipelineStage.OPENMVG, PipelineStage.OPENMVS]
