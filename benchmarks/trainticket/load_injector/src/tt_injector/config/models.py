from __future__ import annotations

from pydantic import BaseModel, Field


class PhaseConfig(BaseModel):
    name: str
    duration_min: int = Field(gt=0)
    users: int | None = Field(default=None, ge=1)
    spawn_rate: float | None = Field(default=None, gt=0)
    arrival_rate: float | None = Field(default=None, gt=0)
    mix: dict[str, float]


class MixConfig(BaseModel):
    name: str
    description: str = ""
    phases: list[PhaseConfig]
