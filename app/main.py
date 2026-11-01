from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from app.services.graph_service import SpatialGraphService
from app.services.reasoning_service import SpatialReasoningService


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ObjectUpdate(BaseModel):
    obj_id: str
    label: str
    position: list[float]
    dimensions: list[float]

    @field_validator("position", "dimensions")
    @classmethod
    def must_be_3d(cls, v: list[float]) -> list[float]:
        if len(v) != 3:
            raise ValueError("must have exactly 3 elements [x, y, z]")
        return v


class TelemetryPayload(BaseModel):
    robot_id: str
    position: list[float]
    query: str
    objects: list[ObjectUpdate] = []

    @field_validator("position")
    @classmethod
    def position_must_be_3d(cls, v: list[float]) -> list[float]:
        if len(v) != 3:
            raise ValueError("robot position must have exactly 3 elements [x, y, z]")
        return v


# ── App + lifespan ────────────────────────────────────────────────────────────

_graph: SpatialGraphService | None = None
_reasoning: SpatialReasoningService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _reasoning
    _graph = SpatialGraphService()
    _reasoning = SpatialReasoningService()
    yield
    if _graph:
        _graph.close()


app = FastAPI(title="SpatialSpark", lifespan=lifespan)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/reason")
def reason(payload: TelemetryPayload) -> dict[str, Any]:
    """Accept telemetry, update graph, run GraphRAG retrieval, return action."""
    if _graph is None or _reasoning is None:
        raise HTTPException(status_code=503, detail="Services not initialised")

    # Upsert all scene objects reported in this telemetry tick
    for obj in payload.objects:
        _graph.upsert_object(obj.obj_id, obj.label, obj.position, obj.dimensions)

    spatial_context = _graph.get_spatial_context(payload.position)
    action = _reasoning.plan_action(payload.query, spatial_context)
    return action
