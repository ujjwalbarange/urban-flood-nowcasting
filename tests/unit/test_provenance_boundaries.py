"""Regression tests for public claims made about current prototype data."""

import pytest

from services.api.routers.geodata import get_geodata_audit_status
from services.api.routers.simulations import (
    _build_rainfall_schedule_from_event,
    _build_rainfall_schedule_from_scenario,
    get_physics_capabilities,
)


@pytest.mark.asyncio
async def test_geodata_status_does_not_claim_operational_verification():
    status = await get_geodata_audit_status()

    assert status["verification_status"] == "audit_incomplete"
    assert status["operational_use"] is False
    assert status["inventory"]["drainage_nodes"]["origin"] == "unverified_partial"
    assert status["inventory"]["flood_polygons"]["origin"] == "unverified_not_event_truth"


def test_unknown_rainfall_scenario_is_not_replaced_by_a_default_storm():
    with pytest.raises(ValueError, match="Unknown synthetic rainfall scenario"):
        _build_rainfall_schedule_from_scenario("not-a-real-scenario")


def test_unknown_historical_event_is_not_replaced_by_a_zero_rain_series():
    with pytest.raises(ValueError, match="Unknown historical rainfall file"):
        _build_rainfall_schedule_from_event("event_that_does_not_exist")


@pytest.mark.asyncio
async def test_simulation_capabilities_disclose_data_and_model_limits():
    status = await get_physics_capabilities()

    assert status["simulation_api_status"] == "synthetic_non_georeferenced_experiment_only"
    assert status["validated_for_municipal_decisions"] is False
    assert status["drainage_network"]["status"] == "not connected to the simulation API"
