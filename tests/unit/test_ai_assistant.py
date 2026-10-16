"""Unit tests for Grounded AI Assistant (Phase 2G)."""

import pytest
from httpx import AsyncClient, ASGITransport

from services.api.main import app
from services.ai.operator import AIOperator, get_ai_operator


@pytest.mark.asyncio
async def test_ai_operator_tool_registry():
    """Verify AIOperator registers all 11 deterministic tools."""
    op = get_ai_operator()
    assert len(op.tools) >= 11
    expected_tools = [
        "get_ward_risk",
        "get_latest_nowcast",
        "get_active_alerts",
        "get_tide_status",
        "get_drainage_status",
        "get_impact_summary",
        "get_decision_package",
        "get_nearest_shelter",
        "get_chronic_hotspots",
        "get_current_rainfall",
        "get_rainfall_forecast",
    ]
    for t in expected_tools:
        assert t in op.tools
        assert op.tools[t].name == t
        assert len(op.tools[t].description) > 5


@pytest.mark.asyncio
async def test_tool_get_ward_risk():
    """Verify ward risk deterministic tool execution."""
    op = get_ai_operator()
    res = await op._get_ward_risk(ward_id="FN")
    assert res["status"] in ("ok", "fallback")
    wr = res.get("ward_risk") or res.get("highest_risk_ward")
    assert wr is not None
    assert "risk_level" in wr
    assert "risk_score" in wr


@pytest.mark.asyncio
async def test_tool_get_tide_status():
    """Verify tide status deterministic tool execution."""
    op = get_ai_operator()
    res = await op._get_tide_status()
    assert res["status"] == "ok"
    assert "current_tide_level_m" in res
    assert "compound_risk_factor" in res
    assert "coastal_outfall_status" in res


@pytest.mark.asyncio
async def test_tool_get_drainage_status():
    """Verify drainage status tool returns SWPS pumping stations."""
    op = get_ai_operator()
    res = await op._get_drainage_status()
    assert res["status"] == "ok"
    assert res["total_stations"] == 8
    assert res["total_capacity_m3s"] > 300
    assert len(res["stations"]) == 8


@pytest.mark.asyncio
async def test_tool_get_nearest_shelter():
    """Verify nearest shelter query returns valid facilities."""
    op = get_ai_operator()
    res = await op._get_nearest_shelter(latitude=19.0125, longitude=72.8428, limit=3)
    assert res["status"] == "ok"
    assert res["shelters_count"] >= 1
    assert len(res["shelters"]) >= 1
    for s in res["shelters"]:
        assert "name" in s
        assert "capacity" in s


@pytest.mark.asyncio
async def test_tool_get_chronic_hotspots():
    """Verify chronic hotspots query returns known hotspots."""
    op = get_ai_operator()
    res = await op._get_chronic_hotspots(location_name="Hindmata")
    assert res["status"] == "ok"
    assert "hotspots" in res
    assert len(res["hotspots"]) >= 1


@pytest.mark.asyncio
async def test_tool_get_decision_package():
    """Verify command center decision package tool."""
    op = get_ai_operator()
    res = await op._get_decision_package()
    assert res["status"] in ("ok", "fallback")
    pkg = res["decision_package"]
    assert "response_level" in pkg


@pytest.mark.asyncio
async def test_ai_chat_shelter_query():
    """Verify conversational query for shelter returns grounded municipal shelters."""
    op = get_ai_operator()
    res = await op.process_query("Where is the nearest shelter in Dadar?", latitude=19.0178, longitude=72.8478)
    assert "shelter" in res["intent"]
    assert "1916" in res["reply"]
    assert "get_nearest_shelter" in res["tools_called"]
    assert "REAL GIS DATA" in res["data_provenance"]


@pytest.mark.asyncio
async def test_ai_chat_tide_query():
    """Verify conversational query for tide returns Apollo Bunder data."""
    op = get_ai_operator()
    res = await op.process_query("What is the sea tide level right now at Apollo Bunder?")
    assert "tide" in res["intent"]
    assert "Apollo Bunder" in res["reply"]
    assert "get_tide_status" in res["tools_called"]


@pytest.mark.asyncio
async def test_ai_chat_drainage_query():
    """Verify conversational query for pumping stations."""
    op = get_ai_operator()
    res = await op.process_query("How many pumps are operational at Britannia?")
    assert "drainage" in res["intent"]
    assert "Britannia" in res["reply"]
    assert "get_drainage_status" in res["tools_called"]


@pytest.mark.asyncio
async def test_ai_chat_hotspot_query():
    """Verify conversational query for chronic subways."""
    op = get_ai_operator()
    res = await op.process_query("What is the flood depth at Milan Subway?")
    assert "chronic_hotspot" in res["intent"]
    assert "Milan" in res["reply"] or "Subway" in res["reply"]
    assert "get_chronic_hotspots" in res["tools_called"]


@pytest.mark.asyncio
async def test_ai_chat_nowcast_query():
    """Verify general nowcast query returns depth and action guidance."""
    op = get_ai_operator()
    res = await op.process_query("Is Kurla going to flood today?")
    assert "ward_risk_nowcast" in res["intent"]
    assert "Risk Level" in res["reply"]
    assert "Citizen Advisories" in res["reply"]
    assert "get_ward_risk" in res["tools_called"]


@pytest.mark.asyncio
async def test_ai_api_endpoints():
    """Verify FastAPI endpoints /api/v1/ai/status, /api/v1/ai/tools, /api/v1/ai/chat."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Status
        r = await client.get("/api/v1/ai/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"
        assert data["assistant_name"] == "JalDrishti"
        assert data["tools_registered"] >= 11
        assert data["grounding_enforced"] is True

        # Tools
        r = await client.get("/api/v1/ai/tools")
        assert r.status_code == 200
        data = r.json()
        assert data["total_tools"] >= 11
        assert len(data["tools"]) >= 11

        # Chat
        r = await client.post(
            "/api/v1/ai/chat",
            json={"message": "Where can I find emergency shelter near Hindmata?"},
        )
        assert r.status_code == 200
        chat_data = r.json()
        assert "reply" in chat_data
        assert "data_provenance" in chat_data
        assert "1916" in chat_data["reply"]
