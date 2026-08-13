"""
FastAPI entry point for the Crowd Flow Optimiser / Crowd Intelligence System.

Thin HTTP wrapper around existing simulation/prediction packages + Hugging Face vision.
Start with:

    cd backend
    uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load backend/.env for HF_TOKEN etc. without committing secrets.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from api import services
from vision.hf_detector import analyze_crowd_image, hf_config_status

app = FastAPI(
    title="Crowd Flow Optimiser API",
    description="Thin HTTP layer over simulation, prediction, routing, intervention, and Hugging Face vision.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventSchedule(BaseModel):
    start_time: Optional[str] = Field(None, examples=["18:00"])
    peak_window_minutes: int = Field(30, ge=5, le=240)
    event_duration_minutes: int = Field(120, ge=15, le=600)


class SimulationRequest(BaseModel):
    venue: str = Field(..., examples=["stadium"])
    scenario: str = Field(..., examples=["peak_traffic"])
    duration_seconds: int = Field(600, ge=60, le=3600)
    random_seed: int = Field(42, ge=0)
    arrival_rate: Optional[float] = Field(
        None, ge=0.0, description="Optional explicit override of base arrival rate"
    )
    expected_crowd_size: Optional[int] = Field(
        None, ge=0, description="PDF input: expected crowd size used to derive arrival pressure"
    )
    event_schedule: Optional[EventSchedule] = Field(
        None, description="PDF input: event timing influencing arrival intensity"
    )


class RouteRequest(BaseModel):
    venue: str
    source: str
    target: str
    max_alternates: int = Field(3, ge=1, le=5)


class InterventionRequest(BaseModel):
    redirect_percentage: Optional[int] = Field(None, ge=0, le=100)


class WhatIfRequest(BaseModel):
    test_arrival_rate: float = Field(..., ge=0.0, description="Alternate base arrival rate to simulate")


@app.on_event("startup")
def _startup() -> None:
    services.try_warm_model()


@app.get("/api/health")
def health():
    return services.health_payload()


@app.get("/api/venues")
def venues():
    return {"venues": services.list_venues()}


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": services.list_scenarios()}


@app.get("/api/venues/{venue_id}/graph")
def venue_graph(venue_id: str):
    try:
        return services.get_venue_graph(venue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/simulation")
def simulation(body: SimulationRequest):
    try:
        schedule = body.event_schedule.model_dump() if body.event_schedule else None
        return services.run_simulation(
            venue=body.venue,
            scenario=body.scenario,
            duration_seconds=body.duration_seconds,
            random_seed=body.random_seed,
            arrival_rate=body.arrival_rate,
            expected_crowd_size=body.expected_crowd_size,
            event_schedule=schedule,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/routing")
def routing(body: RouteRequest):
    try:
        return services.find_routes(
            venue=body.venue,
            source=body.source,
            target=body.target,
            max_alternates=body.max_alternates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/intervention/recommend")
def intervention_recommend():
    try:
        return services.recommend_intervention()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/intervention/simulate")
def intervention_simulate(body: InterventionRequest = InterventionRequest()):
    try:
        return services.simulate_intervention(redirect_percentage=body.redirect_percentage)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/what-if")
def what_if(body: WhatIfRequest):
    try:
        return services.run_what_if(test_arrival_rate=body.test_arrival_rate)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/vision/status")
def vision_status():
    return hf_config_status()


@app.post("/api/vision/analyze")
async def vision_analyze(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file (image/*).")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty image upload.")
    try:
        return analyze_crowd_image(raw)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
