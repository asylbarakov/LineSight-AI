import pytest

from pydantic import ValidationError

from app.schemas import (
    FindingInput,
    JobOut,
    ProcessingResult,
)


def test_valid_finding():
    finding = FindingInput(
        category="insulator_damage",
        confidence=0.94,
        timecode_s=12.5,
        frame_index=375,
        bbox=[0.2, 0.3, 0.47, 0.61],
    )

    assert finding.category == "insulator_damage"
    assert finding.frame_index == 375


def test_finding_without_bbox():
    finding = FindingInput(
        category="equipment_present",
        timecode_s=3.0,
    )

    assert finding.bbox is None
    assert finding.confidence is None


@pytest.mark.parametrize(
    "bbox",
    [
        [0.8, 0.2, 0.3, 0.6],
        [0.1, 0.8, 0.4, 0.2],
        [-0.1, 0.2, 0.4, 0.6],
        [0.1, 0.2, 1.2, 0.6],
        [0.1, 0.2, 0.4],
        [0.1, 0.2, 0.4, float("nan")],
    ],
)
def test_invalid_bbox(bbox):
    with pytest.raises(ValidationError):
        FindingInput(
            category="test",
            timecode_s=1.0,
            bbox=bbox,
        )


@pytest.mark.parametrize(
    "field, value",
    [
        ("confidence", 1.5),
        ("confidence", float("nan")),
        ("timecode_s", -1.0),
        ("frame_index", -5),
    ],
)
def test_invalid_numeric_fields(field, value):
    data = {
        "category": "test",
        "timecode_s": 1.0,
        field: value,
    }

    with pytest.raises(ValidationError):
        FindingInput(**data)


def test_empty_processing_result():
    result = ProcessingResult(
        model_name="test-detector",
        model_version="v1",
        findings=[],
    )

    assert result.findings == []


def test_lease_token_not_exposed():
    assert "lease_token" not in JobOut.model_fields
