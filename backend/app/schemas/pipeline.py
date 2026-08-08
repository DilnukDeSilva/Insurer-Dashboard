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
    LOW_LIGHT = "low_light"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStep(BaseModel):
    key: str
    label: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[float] = None    # unix timestamp
    completed_at: Optional[float] = None  # unix timestamp


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
    # The claim's exact R2 folder (from GET /claims). Optional for backward
    # compatibility with any client still on the old customer+NIC-only request
    # shape; falls back to reconstructing the pre-timestamp folder name.
    folder: Optional[str] = None


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
