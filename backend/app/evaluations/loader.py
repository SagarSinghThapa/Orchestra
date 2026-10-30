import hashlib
import json
import os
from pathlib import Path
from typing import Tuple

from app.evaluations.schemas import GoldenDataset

MAX_DATASET_FILE_BYTES = 2 * 1024 * 1024  # 2MB safety ceiling
DATASETS_DIR = Path(__file__).parent / "datasets"


class DatasetLoader:
    """
    Loads and validates versioned Golden Datasets with content hashing,
    path traversal prevention, and schema enforcement.
    """

    @staticmethod
    def get_datasets_dir() -> Path:
        return DATASETS_DIR.resolve()

    @classmethod
    def load_dataset(cls, filename_or_id: str) -> Tuple[GoldenDataset, str]:
        """
        Loads a golden dataset JSON by filename or dataset identifier.

        Returns:
            Tuple of (GoldenDataset, sha256_checksum)
        """
        # 1. Sanitize filename: forbid directory traversal
        if ".." in filename_or_id or "/" in filename_or_id or "\\" in filename_or_id:
            raise ValueError(f"Path traversal detected: {filename_or_id}")

        clean_name = filename_or_id.strip()
        if not clean_name.endswith(".json"):
            clean_name = f"{clean_name}.json"

        target_path = (cls.get_datasets_dir() / clean_name).resolve()

        # Strict containment check
        if not str(target_path).startswith(str(cls.get_datasets_dir())):
            raise ValueError(f"Path traversal detected: {filename_or_id}")

        if not target_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {clean_name}")

        # 2. File size bounding
        file_size = target_path.stat().st_size
        if file_size > MAX_DATASET_FILE_BYTES:
            raise ValueError(f"Dataset file exceeds maximum allowed size ({file_size} > {MAX_DATASET_FILE_BYTES} bytes)")

        # 3. Read exact raw bytes and compute SHA-256 checksum for content identity
        raw_bytes = target_path.read_bytes()
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        # 4. Parse UTF-8 JSON
        try:
            raw_text = raw_bytes.decode("utf-8")
            data = json.loads(raw_text)
        except UnicodeDecodeError as e:
            raise ValueError(f"Dataset file is not valid UTF-8: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Dataset file contains invalid JSON: {e}")

        # 5. Schema validation via Pydantic
        dataset = GoldenDataset.model_validate(data)

        # 6. Verify case ID uniqueness
        case_ids = [c.case_id for c in dataset.cases]
        if len(case_ids) != len(set(case_ids)):
            duplicates = [cid for cid in case_ids if case_ids.count(cid) > 1]
            raise ValueError(f"Duplicate case_ids detected in dataset: {set(duplicates)}")

        return dataset, sha256_hash
