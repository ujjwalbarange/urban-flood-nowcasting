"""Unit tests for Alert Lifecycle and Decision Support Engine (Phase 2F)."""

import pytest
from httpx import AsyncClient, ASGITransport

from services.api.main import app
from services.alerts.thresholds import (
    AlertThresholdConfig,
    AlertSeverity,
    DEFAULT_THRESHOLDS,
)
from services.alerts.engine import AlertEngine
from services.decision.engine import (
    determine_response_level,
    ResponseLevel,
    generate_decision_package,
    DecisionPackage,
)


@pytest.mark.asyncio
async def test_alert_threshold_evaluation():
    """Verify alert severity assignment for various flood depths and rainfall."""
    cfg = AlertThresholdConfig()

    # Minor ponding
    sev = cfg.evaluate_severity(max_depth_m=0.08)
    assert sev == AlertSeverity.INFO

    # Watch
    sev = cfg.evaluate_severity(max_depth_m=0.20)
    assert sev == AlertSeverity.WATCH

    # Warning
    sev = cfg.evaluate_severity(max_depth_m=0.35)
    assert sev == AlertSeverity.WARNING

    # Emergency from depth
    sev = cfg.evaluate_severity(max_depth_m=0.65)
    assert sev == AlertSeverity.EMERGENCY

    # Escalation from critical infrastructure
    sev = cfg.evaluate_severity(max_depth_m=0.35, critical_infra_count=3)
    assert sev == AlertSeverity.EMERGENCY


@pytest.mark.asyncio
async def test_alert_engine_lifecycle_and_deduplication():
    """Verify alert engine generates alerts, dedupes identical events, and supports escalation."""
    engine = AlertEngine()

    # 1. Generate warning alert
    alerts = await engine.evaluate_and_generate_alerts(
        city_id="mumbai",
        max_depth_m=0.35,
        rainfall_rate_mmh=40.0,
        exposed_population=5000,
    )
    assert len(alerts) >= 1
    a1 = alerts[0]
    alert_id = a1["alert_id"]
    dedup_key = a1["deduplication_key"]

    # 2. Re-evaluating same conditions should deduplicate
    alerts_dupe = await engine.evaluate_and_generate_alerts(
        city_id="mumbai",
        max_depth_m=0.35,
        rainfall_rate_mmh=40.0,
        exposed_population=5000,
    )
    assert len(alerts_dupe) >= 1
    assert alerts_dupe[0]["deduplication_key"] == dedup_key

    # 3. Test acknowledgement
    ack_ok = await engine.acknowledge_alert(alert_id, acknowledged_by="BMC_Control_Room_Officer")
    assert ack_ok is True

    # 4. Test resolution
    res_ok = await engine.resolve_alert(alert_id, resolution_notes="Waters drained; subways reopened.")
    assert res_ok is True


@pytest.mark.asyncio
async def test_decision_engine_and_packages():
    """Verify municipal decision engine computes correct response levels and action items."""
    # Emergency tier
    level = determine_response_level(max_depth_m=1.2, critical_wards=4)
    assert level == ResponseLevel.EMERGENCY

    # Warning tier
    level_warn = determine_response_level(max_depth_m=0.35, critical_wards=1)
    assert level_warn in (ResponseLevel.WARNING, ResponseLevel.ALERT)

    pkg = generate_decision_package(
        ward_risks=[],
        max_depth_m=0.45,
        rainfall_mmh=55.0,
    )

    assert pkg.response_level in (ResponseLevel.ALERT, ResponseLevel.WARNING, ResponseLevel.EMERGENCY)
    assert len(pkg.recommendations) > 0
    assert len(pkg.resource_allocation) > 0
    assert len(pkg.escalation_triggers) > 0


@pytest.mark.asyncio
async def test_decision_api_endpoints():
    """Verify /api/v1/decision endpoints return valid command center responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Response level
        r = await client.get("/api/v1/decision/response-level?max_depth_m=0.6&critical_wards=2")
        assert r.status_code == 200
        data = r.json()
        assert "response_level" in data
        assert data["response_level"] in ("WARNING", "EMERGENCY")

        # Full decision package
        r = await client.get("/api/v1/decision/package")
        assert r.status_code == 200
        pkg = r.json()
        assert "response_level" in pkg
        assert "recommendations" in pkg
        assert "resource_allocation" in pkg
