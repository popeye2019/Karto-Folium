import json

import pytest

from app.utils import utils_json as uj


def test_get_field_names_from_list():
    data = [{"a": 1, "b": 2}]
    assert uj.get_field_names(data) == ["a", "b"]


def test_search_in_json_case_insensitive():
    base = [
        {"name": "Alpha"},
        {"name": "Beta"},
        {"name": "alphabet"},
    ]
    result = uj.search_in_json(base, "name", "ALP")
    assert len(result) == 2


def test_add_record_assigns_incremental_index():
    base = [{"INDEX": 1}]
    uj.add_record(base, {"value": "new"})
    assert base[-1]["INDEX"] == 2


def test_update_record_updates_value():
    base = [{"INDEX": 1, "value": "old"}]
    updated = uj.update_record(base, 1, {"value": "new"})
    assert updated[0]["value"] == "new"

    with pytest.raises(ValueError):
        uj.update_record(base, 99, {"value": "missing"})


def test_sort_and_filter_records():
    base = [
        {"name": "alice", "role": "user"},
        {"name": "bob", "role": "admin"},
    ]
    sorted_records = uj.sort_records(base, "name", reverse=True)
    assert [item["name"] for item in sorted_records] == ["bob", "alice"]

    filtered = uj.filter_records(base, "role", "admin")
    assert filtered == [{"name": "bob", "role": "admin"}]


def test_get_summary_and_check_unique():
    base = [
        {"INDEX": 1, "value": 10},
        {"INDEX": 2, "value": 20},
    ]
    summary = uj.get_summary(base, ["value"])
    assert summary["Total Records"] == 2
    assert summary["value"]["Average"] == 15

    assert uj.check_unique(base, "INDEX") is True
    assert uj.check_unique(base + [{"INDEX": 1}], "INDEX") is False


def test_get_next_index_and_unique_values(tmp_path):
    data = [
        {"INDEX": 2, "status": "open"},
        {"index": 3, "status": "Closed"},
    ]
    filepath = tmp_path / "data.json"
    filepath.write_text(json.dumps(data), encoding="utf-8")

    assert uj.get_next_index(str(filepath)) == 4

    values = uj.get_unique_field_values(str(filepath), "status")
    assert values == ["CLOSED", "OPEN"]
