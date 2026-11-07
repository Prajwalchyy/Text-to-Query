import math
import sys
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dialects.base import (
    EngineProtocol,
    normalize_doc_tree,
    resolve_dataset_file,
    sanitize_records_for_json,
    sanitize_scalar,
)


class MockObjectId:
    def __init__(self, val="654321abcdef123456789012"):
        self.val = val

    def __str__(self):
        return self.val


def test_sanitize_scalar_primitives():
    assert sanitize_scalar(None) is None
    assert sanitize_scalar("hello") == "hello"
    assert sanitize_scalar(100) == 100
    assert sanitize_scalar(True) is True
    assert sanitize_scalar(False) is False
    assert sanitize_scalar(float("nan")) is None
    assert sanitize_scalar(float("inf")) is None
    assert sanitize_scalar(float("-inf")) is None


def test_sanitize_scalar_complex_types():
    # Dates and times
    dt = datetime(2026, 3, 1, 14, 30, 0)
    d = date(2026, 3, 1)
    assert sanitize_scalar(dt) == "2026-03-01T14:30:00"
    assert sanitize_scalar(d) == "2026-03-01"

    # Pandas Timestamp
    ts = pd.Timestamp("2026-03-01 12:00:00")
    assert sanitize_scalar(ts) == "2026-03-01 12:00:00"

    # Decimal
    dec = Decimal("49.95")
    assert sanitize_scalar(dec) == 49.95

    # Bytes
    raw_b = b"simple_text"
    assert sanitize_scalar(raw_b) == "simple_text"

    # NumPy generics
    np_i = np.int64(99)
    np_f = np.float64(12.34)
    assert sanitize_scalar(np_i) == 99
    assert isinstance(sanitize_scalar(np_i), int)
    assert sanitize_scalar(np_f) == 12.34
    assert isinstance(sanitize_scalar(np_f), float)

    # ObjectId
    obj_id = MockObjectId("abcdef123456789012345678")
    assert sanitize_scalar(obj_id) == "abcdef123456789012345678"


def test_sanitize_scalar_recursive():
    payload = {
        "id": MockObjectId(),
        "date": date(2026, 1, 1),
        "nums": [np.int64(1), float("nan"), Decimal("10.5")],
        "nested": {
            "ts": pd.Timestamp("2026-01-01 00:00:00"),
            "val": "ok",
        }
    }
    sanitized = sanitize_scalar(payload)
    assert sanitized["id"] == "654321abcdef123456789012"
    assert sanitized["date"] == "2026-01-01"
    assert sanitized["nums"] == [1, None, 10.5]
    assert sanitized["nested"]["ts"] == "2026-01-01 00:00:00"
    assert sanitized["nested"]["val"] == "ok"


def test_sanitize_records_for_json():
    records = [
        {"name": "Item A", "price": Decimal("15.50"), "missing": float("nan")},
        {"name": "Item B", "price": Decimal("25.00"), "missing": 42},
    ]
    cleaned = sanitize_records_for_json(records)
    assert len(cleaned) == 2
    assert cleaned[0]["price"] == 15.50
    assert cleaned[0]["missing"] is None
    assert cleaned[1]["price"] == 25.00
    assert cleaned[1]["missing"] == 42


def test_normalize_doc_tree():
    doc = {
        "_id": MockObjectId(),
        "created_at": datetime(2026, 1, 15, 10, 0, 0),
        "items": [
            {"product_id": MockObjectId("111122223333444455556666"), "qty": np.int32(3)}
        ]
    }
    normalized = normalize_doc_tree(doc)
    assert normalized["_id"] == "654321abcdef123456789012"
    assert normalized["created_at"] == "2026-01-15T10:00:00"
    assert normalized["items"][0]["product_id"] == "111122223333444455556666"
    assert normalized["items"][0]["qty"] == 3


def test_resolve_dataset_file_scenarios():
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        sub1 = base_dir / "folder1"
        sub2 = base_dir / "folder2"
        sub1.mkdir()
        sub2.mkdir()

        default_file = base_dir / "default.db"
        default_file.touch()

        target_file = sub2 / "my_custom.db"
        target_file.touch()

        # 1. Fallback to default when None or empty
        res1 = resolve_dataset_file(None, default_file, [sub1, sub2])
        assert res1 == default_file.resolve()

        res2 = resolve_dataset_file("", default_file, [sub1, sub2])
        assert res2 == default_file.resolve()

        # 2. Alias resolution
        res3 = resolve_dataset_file("my_alias", default_file, [sub1, sub2], default_alias_names=["my_alias"])
        assert res3 == default_file.resolve()

        # 3. Direct filename match across search directories
        res4 = resolve_dataset_file("my_custom.db", default_file, [sub1, sub2])
        assert res4 == target_file.resolve()

        # 4. sqlite:/// URI prefix handling
        res5 = resolve_dataset_file(f"sqlite:///{target_file.as_posix()}", default_file, [sub1, sub2])
        assert res5 == target_file.resolve()

