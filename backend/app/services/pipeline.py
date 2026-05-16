from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from app.config import settings
from app.schemas.pipeline import PipelineJobResponse, PipelineJobStatus, PipelineStage
from app.services.openmvg import OpenMVGService
from app.services.openmvs import OpenMVSService
from app.services.zero_dce import ZeroDCEService


class PipelineService:
    """
    Photogrammetry pipeline for insurer property capture:

    1. Zero-DCE — enhance low-light photos
    2. OpenMVG — sparse SfM / camera poses
    3. OpenMVS — dense point cloud and mesh
    """

    def __init__(self) -> None:
        self.zero_dce = ZeroDCEService()
        self.openmvg = OpenMVGService()
        self.openmvs = OpenMVSService()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create_job(self, image_dir: Optional[Path] = None) -> PipelineJobResponse:
        job_id = str(uuid.uuid4())
        job_dir = settings.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        if image_dir is None:
            image_dir = settings.uploads_dir / job_id
            image_dir.mkdir(parents=True, exist_ok=True)

        return PipelineJobResponse(
            job_id=job_id,
            status=PipelineJobStatus.PENDING,
            message=f"Job workspace: {job_dir}. Place images in {image_dir}, then run the pipeline.",
        )

    async def run_job(self, job_id: str, skip_zero_dce: bool = False) -> PipelineJobResponse:
        job_dir = settings.jobs_dir / job_id
        if not job_dir.exists():
            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.FAILED,
                message="Job not found",
            )

        images_dir = job_dir / "images"
        enhanced_dir = job_dir / "enhanced"
        sfm_dir = job_dir / "sfm"
        mvs_dir = job_dir / "mvs"

        try:
            source_images = enhanced_dir if skip_zero_dce else images_dir

            if not skip_zero_dce:
                self.zero_dce.enhance_images(images_dir, enhanced_dir)
                source_images = enhanced_dir

            self.openmvg.run_sfm(source_images, sfm_dir)
            self.openmvs.run_dense_reconstruction(sfm_dir, mvs_dir)

            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.COMPLETED,
                message=f"Pipeline finished. Outputs in {job_dir}",
            )
        except NotImplementedError as exc:
            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.PENDING,
                message=str(exc),
            )
        except Exception as exc:
            return PipelineJobResponse(
                job_id=job_id,
                status=PipelineJobStatus.FAILED,
                message=str(exc),
            )

    def list_stages(self) -> list[PipelineStage]:
        return [PipelineStage.ZERO_DCE, PipelineStage.OPENMVG, PipelineStage.OPENMVS]
