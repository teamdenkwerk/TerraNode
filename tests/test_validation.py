"""
tests/test_validation.py

UNIT TESTS: REAL DATASET INGESTION VALIDATOR

Validates:
- Validation on real uploaded dataset
- Rejection of non-existent files
- Rejection of invalid file extensions
- Structure and completeness of the 20-check DatasetValidationReport
"""

import pytest
from pathlib import Path
from backend.validation.dataset_validator import DatasetValidator, DatasetValidationReport

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_validate_real_cadastral_dataset():
    fpath = PROJECT_ROOT / "data" / "uploads" / "d61deb54-ea55-4bbc-a888-2d57a018fee3.geojson"
    if not fpath.exists():
        pytest.skip("Dataset file not available")

    validator = DatasetValidator(fpath, "Cadastral Survey")
    report = validator.validate()

    assert isinstance(report, DatasetValidationReport)
    assert report.records == 37
    assert report.valid_records == 37
    assert report.invalid_records == 0
    assert report.processing_status in ("VALIDATED", "PASSED_WITH_WARNINGS")
    assert report.detected_crs == "EPSG:4326"
    assert "check_1_file_type" in report.check_results
    assert "check_20_coord_range" in report.check_results


def test_reject_invalid_extension(tmp_path):
    bad_file = tmp_path / "test.exe"
    bad_file.write_text("dummy")

    validator = DatasetValidator(bad_file)
    report = validator.validate()

    assert report.processing_status == "REJECTED"
    assert any("Unsupported extension" in err for err in report.errors)


def test_reject_empty_file(tmp_path):
    empty_file = tmp_path / "empty.geojson"
    empty_file.write_text("")

    validator = DatasetValidator(empty_file)
    report = validator.validate()

    assert report.processing_status == "REJECTED"
    assert any("empty (0 bytes)" in err for err in report.errors)
