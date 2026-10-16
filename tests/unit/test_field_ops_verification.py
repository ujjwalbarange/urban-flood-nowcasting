"""Unit tests for Field Operations & Citizen Report Verification (Phase 2H)."""

import pytest
from httpx import AsyncClient, ASGITransport

from services.api.main import app
from services.data.report_verification import get_verification_pipeline


@pytest.mark.asyncio
async def test_verification_pipeline_verified():
    """Verify report with strong spatial and meteorological concordance is marked VERIFIED."""
    pipeline = get_verification_pipeline()
    # Location near Hindmata with 45 mm/h rainfall and photo proof
    res = await pipeline.verify_report(
        report_id="REP-TEST-001",
        latitude=19.0125,
        longitude=72.8428,
        water_depth_cm=45.0,
        photo_url="https://storage.mumbai.gov.in/evidence/fl_001.jpg",
        description="Water 45cm deep at Hindmata Cinema junction, buses diverted",
        rainfall_rate_mmh=45.0,
        simulated_depth_m=0.40,
    )

    assert res.verification_status == "VERIFIED"
    assert res.confidence_score >= 0.70
    assert res.dispatch_priority in ("HIGH", "CRITICAL")
    assert "dewatering" in res.recommended_action.lower() or "pump" in res.recommended_action.lower()
    assert len(res.factors) == 4


@pytest.mark.asyncio
async def test_verification_pipeline_suspect():
    """Verify report with no rainfall, isolated location, and no evidence is marked SUSPECT or REJECTED."""
    pipeline = get_verification_pipeline()
    res = await pipeline.verify_report(
        report_id="REP-TEST-002",
        latitude=19.3000,
        longitude=72.9500,
        water_depth_cm=10.0,
        photo_url=None,
        description="Wet road",
        rainfall_rate_mmh=0.0,
        simulated_depth_m=0.0,
    )

    assert res.verification_status in ("SUSPECT", "REJECTED")
    assert res.confidence_score < 0.40
    assert res.dispatch_priority in ("LOW", "NONE")


@pytest.mark.asyncio
async def test_verification_pipeline_depth_penalty():
    """Verify report claiming physically implausible 5-meter flood in city gets penalty."""
    pipeline = get_verification_pipeline()
    res = await pipeline.verify_report(
        report_id="REP-TEST-003",
        latitude=19.0125,
        longitude=72.8428,
        water_depth_cm=500.0,  # 5 meters!
        photo_url=None,
        rainfall_rate_mmh=15.0,
    )

    assert res.evidence_score <= 0.05
    assert any("Unusually high depth" in f.get("detail", "") for f in res.factors)


@pytest.mark.asyncio
async def test_field_ops_api_endpoints():
    """Verify FastAPI endpoints for /api/v1/field-ops."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List tasks
        r = await client.get("/api/v1/field-ops/tasks")
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data
        assert data["total_tasks"] >= 1

        # 2. Stats
        r = await client.get("/api/v1/field-ops/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["total_tasks"] >= 1
        assert "system_status" in stats

        # 3. Create task
        new_task_payload = {
            "title": "Clear blocked culvert near Gandhi Market",
            "task_type": "debris_clearance",
            "ward_id": "FN",
            "latitude": 19.0402,
            "longitude": 72.8624,
            "priority": "HIGH",
            "description": "Clear plastic trash obstructing intake grate.",
            "assigned_to": "Ward FN Rapid Response Crew",
        }
        r = await client.post("/api/v1/field-ops/tasks", json=new_task_payload)
        assert r.status_code == 200
        created = r.json()["task"]
        task_id = created["task_id"]
        assert created["title"] == new_task_payload["title"]
        assert created["status"] == "ASSIGNED"

        # 4. Update task
        update_payload = {
            "status": "COMPLETED",
            "notes": "Culvert cleared. Drainage free flowing.",
        }
        r = await client.patch(f"/api/v1/field-ops/tasks/{task_id}", json=update_payload)
        assert r.status_code == 200
        updated = r.json()["task"]
        assert updated["status"] == "COMPLETED"

        # 5. Verify citizen report endpoint
        verify_payload = {
            "water_depth_cm": 50.0,
            "latitude": 19.0125,
            "longitude": 72.8428,
            "photo_url": "https://bmc.gov.in/photo1.jpg",
            "description": "Water logging near Hindmata junction",
            "rainfall_rate_mmh": 40.0,
            "auto_dispatch_task": True,
        }
        r = await client.post("/api/v1/field-ops/verify-report/REP-API-101", json=verify_payload)
        assert r.status_code == 200
        ver_res = r.json()
        assert ver_res["report_id"] == "REP-API-101"
        assert ver_res["verification"]["verification_status"] == "VERIFIED"
        assert ver_res["dispatched_task"] is not None
        assert "FT-AUTO" in ver_res["dispatched_task"]["task_id"]
