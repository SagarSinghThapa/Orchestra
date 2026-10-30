import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.evaluations.loader import DatasetLoader
from app.evaluations.schemas import GoldenDataset, GoldenCase
from app.models import EvaluationRun, EvaluationCaseResult, User, Project


def test_load_all_golden_datasets():
    """Verify that all 4 canonical golden datasets load cleanly with valid checksums."""
    datasets = [
        "retrieval_golden_v1.json",
        "research_grounding_v1.json",
        "developer_ast_v1.json",
        "orchestrator_routing_v1.json",
    ]
    total_cases = 0
    for filename in datasets:
        ds, sha256_hash = DatasetLoader.load_dataset(filename)
        assert isinstance(ds, GoldenDataset)
        assert len(ds.cases) >= 1
        assert len(sha256_hash) == 64
        total_cases += len(ds.cases)

    # Concurred total: exactly 25 cases across the 4 suites
    assert total_cases == 25


def test_path_traversal_prevention():
    """Verify that path traversal attempts are strictly rejected."""
    with pytest.raises(ValueError, match="Path traversal detected|not found"):
        DatasetLoader.load_dataset("../../secret.json")


def test_missing_dataset_raises_file_not_found():
    """Verify that missing dataset raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        DatasetLoader.load_dataset("non_existent_dataset_v999.json")


def test_duplicate_case_id_rejected(tmp_path, monkeypatch):
    """Verify duplicate case IDs within a dataset trigger validation error."""
    bad_data = {
        "dataset_id": "duplicate_test",
        "dataset_version": "1.0.0",
        "description": "Dataset with duplicates",
        "cases": [
            {
                "case_id": "dup_01",
                "category": "developer",
                "description": "First instance",
                "input_data": {"prompt": "foo"},
                "ground_truth": {"expected": "bar"},
            },
            {
                "case_id": "dup_01",
                "category": "developer",
                "description": "Second instance with same ID",
                "input_data": {"prompt": "baz"},
                "ground_truth": {"expected": "qux"},
            },
        ],
    }
    test_file = tmp_path / "dup_test.json"
    test_file.write_text(json.dumps(bad_data), encoding="utf-8")

    monkeypatch.setattr(DatasetLoader, "get_datasets_dir", staticmethod(lambda: tmp_path))

    with pytest.raises(ValueError, match="Duplicate case_ids detected"):
        DatasetLoader.load_dataset("dup_test.json")


def test_evaluation_models_sqlite_compatibility():
    """Verify EvaluationRun and EvaluationCaseResult create cleanly and link in SQLite."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    run = EvaluationRun(
        id="test-run-uuid-1234",
        project_id=None,
        created_by_user_id=None,
        suite_id="coding_ast",
        dataset_id="orchestra_developer_ast",
        dataset_version="1.0.0",
        dataset_sha256="dummy_sha256",
        execution_mode="regression",
        model_name="deterministic-test-provider",
        metric_schema_version="1.0.0",
        target_type="developer",
        status="completed",
        is_baseline=True,
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        duration_ms=120.5,
        summary_metrics={"ast_syntax_validity": 1.0},
    )
    db.add(run)
    db.commit()

    case_res = EvaluationCaseResult(
        run_id=run.id,
        case_id="dev_001",
        status="passed",
        duration_ms=45.2,
        metrics={"ast_syntax_validity": 1.0},
        failure_reason=None,
        details={"syntax_valid": True},
    )
    db.add(case_res)
    db.commit()

    fetched = db.query(EvaluationRun).filter(EvaluationRun.id == "test-run-uuid-1234").first()
    assert fetched is not None
    assert fetched.is_baseline is True
    assert len(fetched.case_results) == 1
    assert fetched.case_results[0].case_id == "dev_001"
    assert fetched.case_results[0].status == "passed"
    db.close()
