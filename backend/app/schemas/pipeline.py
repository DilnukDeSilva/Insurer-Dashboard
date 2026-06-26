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


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class PipelineStep(BaseModel):
    key: str
    label: str
    status: StepStatus = StepStatus.PENDING


class JobStatusResponse(BaseModel):
    job_id: str
    overall: PipelineJobStatus
    steps: list[PipelineStep]
    error: Optional[str] = None
    model_url: Optional[str] = None


class ToolStatus(BaseModel):
    name: str
    configured: bool
    description: str


class PipelineJobCreateRequest(BaseModel):
    nic: str
    customer_name: str


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
    model_url: Optional[str] = None
