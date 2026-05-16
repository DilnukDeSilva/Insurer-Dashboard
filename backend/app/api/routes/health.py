from fastapi import APIRouter

from app.config import settings
from app.schemas.pipeline import ToolStatus
from app.services.openmvg import OpenMVGService
from app.services.openmvs import OpenMVSService
from app.services.zero_dce import ZeroDCEService

router = APIRouter()


@router.get("/health")
def health() -> dict:
    zero_dce = ZeroDCEService()
    openmvg = OpenMVGService()
    openmvs = OpenMVSService()

    tools = [
        ToolStatus(
            name="zero_dce",
            configured=zero_dce.is_configured,
            description="Low-light image enhancement before reconstruction",
        ),
        ToolStatus(
            name="openmvg",
            configured=openmvg.is_configured,
            description="Structure from motion and sparse reconstruction",
        ),
        ToolStatus(
            name="openmvs",
            configured=openmvs.is_configured,
            description="Dense point cloud and mesh generation",
        ),
    ]

    return {
        "status": "ok",
        "service": "insurer-dashboard-api",
        "environment": settings.environment,
        "pipeline": [t.model_dump() for t in tools],
    }
