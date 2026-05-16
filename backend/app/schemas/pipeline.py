from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    ZERO_DCE = "zero_dce"
    OPENMVG = "openmvg"
    OPENMVS = "openmvs"


class PipelineJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolStatus(BaseModel):
    name: str
    configured: bool
    description: str


class PipelineJobResponse(BaseModel):
    job_id: str
    status: PipelineJobStatus
    stages: list[PipelineStage] = Field(
        default_factory=lambda: [
            PipelineStage.ZERO_DCE,
            PipelineStage.OPENMVG,
            PipelineStage.OPENMVS,
        ],
    )
    message: Optional[str] = None
