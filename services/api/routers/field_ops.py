"""Field Operations & Dispatch API Router.

Provides endpoints for municipal dispatchers and field workers:
- Task dispatch, assignment, tracking, and resolution
- Crew operational statistics
- Integration with citizen report verification pipeline

Phase 2H-2: Field worker backend API.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.connection import _db_online, get_db
from services.database.models import CitizenReport, FieldTask
from services.data.report_verification import get_verification_pipeline

logger = structlog.get_logger()
router = APIRouter(prefix="/field-ops", tags=["Field Operations"])

# In-memory storage for standalone / development mode
_memory_tasks: Dict[str, Dict[str, Any]] = {}


def _seed_sample_tasks():
    """Seed initial operational tasks if memory is empty."""
    if not _memory_tasks:
        samples = [
            {
                "task_id": "FT-001",
                "title": "Stage dewatering pump at Hindmata Junction",
                "task_type": "dewatering",
                "ward_id": "FN",
                "latitude": 19.0125,
                "longitude": 72.8428,
                "priority": "HIGH",
                "status": "IN_PROGRESS",
                "description": "Deploy 1500 GPM high-discharge pump before high tide window.",
                "assigned_to": "Crew Alpha (Ward FN)",
                "assigned_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "notes": "Pump operating at 70% capacity.",
                "evidence_photo_url": None,
            },
            {
                "task_id": "FT-002",
                "title": "Inspect Mithi River sluice gate at Kurla",
                "task_type": "gate_inspection",
                "ward_id": "L",
                "latitude": 19.0688,
                "longitude": 72.8797,
                "priority": "CRITICAL",
                "status": "PENDING",
                "description": "Check backflow prevention flap gate for silt blockage.",
                "assigned_to": "Inspection Unit 3",
                "assigned_at": None,
                "completed_at": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "notes": None,
                "evidence_photo_url": None,
            },
            {
                "task_id": "FT-003",
                "title": "Barricade flooded underpass at Milan Subway",
                "task_type": "barricading",
                "ward_id": "KW",
                "latitude": 19.0912,
                "longitude": 72.8423,
                "priority": "HIGH",
                "status": "COMPLETED",
                "description": "Close vehicular access as water exceeds 0.45m.",
                "assigned_to": "Traffic Police / BMC Beat 7",
                "assigned_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "notes": "Diversion via SV Road active.",
                "evidence_photo_url": None,
            },
        ]
        for s in samples:
            _memory_tasks[s["task_id"]] = s


_seed_sample_tasks()


class CreateFieldTaskRequest(BaseModel):
    title: str = Field(..., description="Short title of the task")
    task_type: str = Field(..., description="dewatering, gate_inspection, debris_clearance, rescue_boat, barricading, citizen_check")
    ward_id: str = Field(..., description="Municipal Ward ID (e.g. 'FN', 'L')")
    latitude: float = Field(..., description="WGS84 latitude")
    longitude: float = Field(..., description="WGS84 longitude")
    priority: str = Field("HIGH", description="CRITICAL, HIGH, MEDIUM, LOW")
    description: Optional[str] = Field(None, description="Detailed task instructions")
    assigned_to: Optional[str] = Field(None, description="Assigned field crew / officer")
    citizen_report_id: Optional[str] = Field(None, description="Linked citizen report ID")


class UpdateFieldTaskRequest(BaseModel):
    status: Optional[str] = Field(None, description="PENDING, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED")
    assigned_to: Optional[str] = Field(None, description="Crew ID or leader name")
    notes: Optional[str] = Field(None, description="Field operational notes")
    evidence_photo_url: Optional[str] = Field(None, description="URL or data reference of evidence photo")


@router.get("/tasks")
async def list_field_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    ward_id: Optional[str] = Query(None, description="Filter by ward ID"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=200),
    db: Optional[AsyncSession] = Depends(get_db),
):
    """List operational field tasks with optional filtering."""
    if _db_online and db is not None:
        try:
            q = select(
                FieldTask.task_id,
                FieldTask.title,
                FieldTask.task_type,
                FieldTask.ward_id,
                func.ST_Y(FieldTask.location).label("lat"),
                func.ST_X(FieldTask.location).label("lon"),
                FieldTask.priority,
                FieldTask.status,
                FieldTask.description,
                FieldTask.assigned_to,
                FieldTask.assigned_at,
                FieldTask.completed_at,
                FieldTask.created_at,
                FieldTask.notes,
                FieldTask.evidence_photo_url,
            ).order_by(desc(FieldTask.created_at)).limit(limit)

            if status:
                q = q.where(FieldTask.status == status.upper())
            if ward_id:
                q = q.where(FieldTask.ward_id == ward_id.upper())
            if priority:
                q = q.where(FieldTask.priority == priority.upper())

            res = await db.execute(q)
            tasks = []
            for r in res.fetchall():
                tasks.append({
                    "task_id": str(r.task_id),
                    "title": r.title,
                    "task_type": r.task_type,
                    "ward_id": r.ward_id,
                    "latitude": float(r.lat) if r.lat else 19.076,
                    "longitude": float(r.lon) if r.lon else 72.877,
                    "priority": r.priority,
                    "status": r.status,
                    "description": r.description,
                    "assigned_to": r.assigned_to,
                    "assigned_at": r.assigned_at.isoformat() if r.assigned_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "notes": r.notes,
                    "evidence_photo_url": r.evidence_photo_url,
                })
            return {"total_tasks": len(tasks), "tasks": tasks, "data_source": "PostGIS field_tasks"}
        except Exception as e:
            logger.warning("DB query for field_tasks failed, falling back to memory", error=str(e))

    # Memory fallback
    tasks = list(_memory_tasks.values())
    if status:
        tasks = [t for t in tasks if t.get("status") == status.upper()]
    if ward_id:
        tasks = [t for t in tasks if t.get("ward_id") == ward_id.upper()]
    if priority:
        tasks = [t for t in tasks if t.get("priority") == priority.upper()]

    return {"total_tasks": len(tasks[:limit]), "tasks": tasks[:limit], "data_source": "In-memory operational dispatch"}


@router.post("/tasks")
async def create_field_task(
    payload: CreateFieldTaskRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Dispatch a new operational task to field crew."""
    now_iso = datetime.now(timezone.utc).isoformat()
    new_id = f"FT-{uuid.uuid4().hex[:8].upper()}"

    task_dict = {
        "task_id": new_id,
        "title": payload.title,
        "task_type": payload.task_type,
        "ward_id": payload.ward_id.upper(),
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "priority": payload.priority.upper(),
        "status": "ASSIGNED" if payload.assigned_to else "PENDING",
        "description": payload.description,
        "assigned_to": payload.assigned_to,
        "assigned_at": now_iso if payload.assigned_to else None,
        "completed_at": None,
        "created_at": now_iso,
        "notes": None,
        "evidence_photo_url": None,
        "citizen_report_id": payload.citizen_report_id,
    }

    if _db_online and db is not None:
        try:
            new_task = FieldTask(
                city_id="mumbai",
                title=payload.title,
                task_type=payload.task_type,
                ward_id=payload.ward_id.upper(),
                location=func.ST_SetSRID(func.ST_MakePoint(payload.longitude, payload.latitude), 4326),
                priority=payload.priority.upper(),
                status="ASSIGNED" if payload.assigned_to else "PENDING",
                description=payload.description,
                assigned_to=payload.assigned_to,
                assigned_at=datetime.now(timezone.utc) if payload.assigned_to else None,
                citizen_report_id=uuid.UUID(payload.citizen_report_id) if payload.citizen_report_id else None,
            )
            db.add(new_task)
            await db.commit()
            await db.refresh(new_task)
            task_dict["task_id"] = str(new_task.task_id)
            logger.info("Field task persisted to DB", task_id=str(new_task.task_id))
        except Exception as e:
            logger.warning("DB persist for field task failed", error=str(e))

    _memory_tasks[task_dict["task_id"]] = task_dict
    return {"message": "Field task dispatched successfully", "task": task_dict}


@router.patch("/tasks/{task_id}")
async def update_field_task(
    task_id: str,
    payload: UpdateFieldTaskRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Update status, assignment, or completion details of a field task."""
    now_dt = datetime.now(timezone.utc)
    updated = False

    if _db_online and db is not None:
        try:
            uid = uuid.UUID(task_id)
            task = await db.get(FieldTask, uid)
            if task:
                if payload.status:
                    task.status = payload.status.upper()
                    if task.status == "COMPLETED" and not task.completed_at:
                        task.completed_at = now_dt
                if payload.assigned_to:
                    task.assigned_to = payload.assigned_to
                    if not task.assigned_at:
                        task.assigned_at = now_dt
                if payload.notes:
                    task.notes = payload.notes
                if payload.evidence_photo_url:
                    task.evidence_photo_url = payload.evidence_photo_url
                await db.commit()
                updated = True
        except Exception as e:
            logger.warning("DB update for field task failed", error=str(e))

    # Also update in-memory
    if task_id in _memory_tasks:
        t = _memory_tasks[task_id]
        if payload.status:
            t["status"] = payload.status.upper()
            if t["status"] == "COMPLETED" and not t["completed_at"]:
                t["completed_at"] = now_dt.isoformat()
        if payload.assigned_to:
            t["assigned_to"] = payload.assigned_to
            if not t["assigned_at"]:
                t["assigned_at"] = now_dt.isoformat()
        if payload.notes:
            t["notes"] = payload.notes
        if payload.evidence_photo_url:
            t["evidence_photo_url"] = payload.evidence_photo_url
        updated = True

    if not updated and task_id not in _memory_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {
        "message": f"Task {task_id} updated successfully",
        "task": _memory_tasks.get(task_id, {"task_id": task_id, "status": payload.status}),
    }


@router.get("/stats")
async def get_field_ops_stats(
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Get operational summary statistics of field tasks."""
    total = len(_memory_tasks)
    pending = sum(1 for t in _memory_tasks.values() if t.get("status") == "PENDING")
    in_progress = sum(1 for t in _memory_tasks.values() if t.get("status") == "IN_PROGRESS")
    completed = sum(1 for t in _memory_tasks.values() if t.get("status") == "COMPLETED")
    critical = sum(1 for t in _memory_tasks.values() if t.get("priority") == "CRITICAL")
    crews = len(set(t.get("assigned_to") for t in _memory_tasks.values() if t.get("assigned_to")))

    return {
        "total_tasks": total,
        "pending_tasks": pending,
        "in_progress_tasks": in_progress,
        "completed_tasks": completed,
        "critical_priority_tasks": critical,
        "active_crews": max(1, crews),
        "system_status": "OPERATIONAL",
    }


class VerifyReportPayload(BaseModel):
    water_depth_cm: float = Field(25.0, description="Reported flood depth in cm")
    latitude: float = Field(19.0125, description="Report latitude")
    longitude: float = Field(72.8428, description="Report longitude")
    photo_url: Optional[str] = Field(None, description="Photo proof URL")
    description: Optional[str] = Field(None, description="Report narrative")
    rainfall_rate_mmh: Optional[float] = Field(None, description="Local rainfall rate if available")
    auto_dispatch_task: bool = Field(True, description="Auto-create a field task if verified as critical")


@router.post("/verify-report/{report_id}")
async def verify_citizen_report(
    report_id: str,
    payload: VerifyReportPayload = Body(...),
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Run multi-factor automated verification on a citizen report and optionally dispatch crew."""
    pipeline = get_verification_pipeline()
    result = await pipeline.verify_report(
        report_id=report_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        water_depth_cm=payload.water_depth_cm,
        photo_url=payload.photo_url,
        description=payload.description,
        rainfall_rate_mmh=payload.rainfall_rate_mmh,
    )

    # If DB available, update citizen report record
    if _db_online and db is not None:
        try:
            uid = uuid.UUID(report_id)
            report = await db.get(CitizenReport, uid)
            if report:
                report.verification_status = result.verification_status.lower()
                meta = report.metadata_ or {}
                meta["verification_score"] = result.confidence_score
                meta["verification_factors"] = result.factors
                report.metadata_ = meta
                await db.commit()
        except Exception as e:
            logger.warning("DB update for citizen report verification failed", error=str(e))

    # Auto-dispatch task if requested and verified as high/critical
    dispatched_task = None
    if payload.auto_dispatch_task and result.verification_status == "VERIFIED" and result.dispatch_priority in ("CRITICAL", "HIGH"):
        task_id = f"FT-AUTO-{uuid.uuid4().hex[:6].upper()}"
        dispatched_task = {
            "task_id": task_id,
            "title": f"Urgent Response: {result.recommended_action[:50]}...",
            "task_type": "dewatering" if payload.water_depth_cm >= 30 else "barricading",
            "ward_id": "FN",
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "priority": result.dispatch_priority,
            "status": "PENDING",
            "description": f"Auto-generated from Verified Citizen Report {report_id}. Depth: {payload.water_depth_cm}cm. Action: {result.recommended_action}",
            "assigned_to": None,
            "assigned_at": None,
            "completed_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "citizen_report_id": report_id,
        }
        _memory_tasks[task_id] = dispatched_task
        logger.info("Auto-dispatched field task from verified report", task_id=task_id, report_id=report_id)

    return {
        "report_id": report_id,
        "verification": result.to_dict(),
        "dispatched_task": dispatched_task,
    }
