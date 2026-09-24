"""Tests for data-provider readiness and non-fabricated geospatial evidence."""

from datetime import datetime, timezone

import pytest

from packages.contracts.datasets import EvidenceMethod, HistoricalFloodEvidence
from packages.contracts.provenance import DataOrigin, DataSource, VerificationStatus
from services.config.providers import ProviderReadiness, ProviderSettings


def test_provider_status_does_not_serialize_secret_values():
    settings = ProviderSettings(opentopography_api_key="not-for-output")
    status = settings.status_catalog()["opentopography_cop30"]

    assert status.readiness == ProviderReadiness.READY
    assert "not-for-output" not in status.model_dump_json()


def test_sentinel_evidence_requires_scene_and_forbids_depth_claim():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="water depth"):
        HistoricalFloodEvidence(
            evidence_id="mumbai-2019-s1",
            method=EvidenceMethod.SENTINEL_1_CHANGE_DETECTION,
            event_start=now,
            event_end=now,
            source=DataSource.MANUAL,
            origin=DataOrigin.PUBLIC_DATA,
            verification_status=VerificationStatus.UNVERIFIED,
            scene_or_record_id="S1A_IW_GRDH_1SDV_example",
            has_depth_observations=True,
        )


def test_sentinel_evidence_records_extent_as_unverified_candidate():
    now = datetime.now(timezone.utc)
    evidence = HistoricalFloodEvidence(
        evidence_id="mumbai-2019-s1",
        method=EvidenceMethod.SENTINEL_1_CHANGE_DETECTION,
        event_start=now,
        event_end=now,
        source=DataSource.MANUAL,
        origin=DataOrigin.PUBLIC_DATA,
        verification_status=VerificationStatus.UNVERIFIED,
        scene_or_record_id="S1A_IW_GRDH_1SDV_example",
        extent_uri="data/storage/evidence/mumbai-2019.geojson",
        limitations=["No depth information"],
    )

    assert evidence.has_depth_observations is False
