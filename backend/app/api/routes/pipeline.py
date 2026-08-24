from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas.pipeline import (
    JobStatusResponse,
    PipelineJobCreateRequest,
    PipelineJobResponse,
    PipelineJobStatus,
    PipelineStage,
)
from app.services.pipeline import PipelineService, get_job_status

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
pipeline_service = PipelineService()


@router.get("/stages")
def list_stages() -> list[PipelineStage]:
    return pipeline_service.list_stages()


@router.post("/jobs", response_model=PipelineJobResponse)
def create_job(body: PipelineJobCreateRequest) -> PipelineJobResponse:
    return pipeline_service.create_job(
        folder=body.folder or f"{body.customer_name} - {body.nic}",
        customer_name=body.customer_name,
        nic=body.nic,
    )


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


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@router.get("/jobs/{job_id}/splat")
def get_splat(job_id: str):
    """Stream PLY from R2 to the browser without buffering to disk."""
    from fastapi.responses import StreamingResponse
    r2 = pipeline_service.r2
    if not r2.is_configured:
        raise HTTPException(status_code=503, detail="R2 not configured")
    try:
        obj = r2.client.get_object(Bucket=r2.bucket, Key=f"jobs/{job_id}/splat.ply")
    except Exception:
        raise HTTPException(status_code=404, detail="Splat model not ready yet")
    headers = {"Content-Length": str(obj["ContentLength"])} if obj.get("ContentLength") else {}
    return StreamingResponse(
        obj["Body"].iter_chunks(chunk_size=65536),
        media_type="application/octet-stream",
        headers=headers,
    )


@router.get("/jobs/{job_id}/enhanced-photos")
def get_enhanced_photos(job_id: str) -> list[str]:
    """Return pre-signed URLs for Zero-DCE enhanced photos (low-light jobs)."""
    try:
        return pipeline_service.r2.list_enhanced_photos(job_id)
    except Exception:
        raise HTTPException(status_code=404, detail="No enhanced photos found for this job")


@router.get("/jobs/{job_id}/model")
def get_model(job_id: str) -> FileResponse:
    """Serve the GLB model (legacy) or redirect to splat."""
    glb_path = settings.jobs_dir / job_id / "mvs" / "scene.glb"
    if not glb_path.exists():
        raise HTTPException(status_code=404, detail="Model not ready yet")
    return FileResponse(
        path=str(glb_path),
        media_type="model/gltf-binary",
        filename="scene.glb",
    )
