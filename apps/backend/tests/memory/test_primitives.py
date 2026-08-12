"""持久化基础值的行为测试。"""

from dataclasses import FrozenInstanceError
from datetime import timezone

import pytest

from super_ai.memory.primitives import dump_json, load_json, new_id, utc_now
from super_ai.memory.records import Record


def test_record_has_unique_id_and_utc_timestamps() -> None:
    first = Record()
    second = Record()

    assert first.id
    assert first.id != second.id
    assert first.created_at.tzinfo is timezone.utc
    assert first.updated_at.tzinfo is timezone.utc


def test_record_is_immutable() -> None:
    record = Record()

    with pytest.raises(FrozenInstanceError):
        record.id = new_id()  # type: ignore[misc]


def test_json_codec_is_stable_and_round_trips_unicode() -> None:
    first = {"名称": "值", "nested": {"b": 2, "a": 1}}
    second = {"nested": {"a": 1, "b": 2}, "名称": "值"}

    first_dump = dump_json(first)

    assert first_dump == dump_json(second)
    assert load_json(first_dump) == first
    assert "名称" in first_dump


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_json_codec_rejects_non_finite_numbers(invalid: float) -> None:
    with pytest.raises(ValueError):
        dump_json({"invalid": invalid})


def test_utc_now_returns_aware_utc_time() -> None:
    assert utc_now().tzinfo is timezone.utc
