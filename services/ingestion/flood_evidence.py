"""Register historical flood-validation candidates without inventing observations."""

from __future__ import annotations

from pathlib import Path

from packages.contracts.datasets import HistoricalFloodEvidence


def register_flood_evidence(
    evidence: HistoricalFloodEvidence,
    destination: Path,
) -> Path:
    """Write a reviewable evidence record.

    A Sentinel-1 record is an event extent candidate only. It cannot be
    promoted to a depth measurement by this ingestion path.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")
    return destination


def read_flood_evidence(path: Path) -> HistoricalFloodEvidence:
    return HistoricalFloodEvidence.model_validate_json(Path(path).read_text(encoding="utf-8"))
