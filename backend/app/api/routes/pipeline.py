from fastapi import APIRouter, BackgroundTasks, Query

from app.schemas.pipeline import PipelineJobResponse, PipelineJobStatus, PipelineStage
from app.services.pipeline import PipelineService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
pipeline_service = PipelineService()


@router.get("/stages")
def list_stages() -> list[PipelineStage]:
    return pipeline_service.list_stages()


@router.post("/jobs", response_model=PipelineJobResponse)
def create_job() -> PipelineJobResponse:
    return pipeline_service.create_job()


@router.post("/jobs/{job_id}/run", response_model=PipelineJobResponse)
async def run_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    skip_zero_dce: bool = Query(False, description="Skip Zero-DCE if images are already well lit"),
    background: bool = Query(True, description="Run pipeline in background"),
) -> PipelineJobResponse:
    if background:

        async def _run() -> None:
            await pipeline_service.run_job(job_id, skip_zero_dce=skip_zero_dce)

        background_tasks.add_task(_run)
        return PipelineJobResponse(
            job_id=job_id,
            status=PipelineJobStatus.RUNNING,
            message="Pipeline started in background",
        )

    return await pipeline_service.run_job(job_id, skip_zero_dce=skip_zero_dce)
