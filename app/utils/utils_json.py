"""Utility helpers for loading, manipulating, and saving JSON data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

# Base directory of the project (repository root).
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_path(filepath: str | Path) -> Path:
    """Return an absolute path, resolving relative paths against the app root."""
    path = Path(filepath)
    return path if path.is_absolute() else BASE_DIR / path


def get_field_names(json_data: Any) -> list[str]:
    """Return the list of field names from JSON data (list or dict)."""
    if isinstance(json_data, list) and json_data:
        return list(json_data[0].keys())
    if isinstance(json_data, dict):
        return list(json_data.keys())
    raise ValueError("Expected a list of dicts or a JSON dict.")


def search_in_json(base: list[dict[str, Any]], field: str, value: Any) -> list[dict[str, Any]]:
    """Search JSON records by field value using a case-insensitive match."""
    if not isinstance(base, list):
        raise ValueError("Base must be a list of dictionaries.")

    results: list[dict[str, Any]] = []
    value_lower = str(value).lower()
    for entry in base:
        if field in entry and value_lower in str(entry[field]).lower():
            results.append(entry)
    return results


def add_record(base: list[dict[str, Any]], new_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Add a new record with an automatically generated INDEX field."""
    if not isinstance(base, list):
        raise ValueError("Base must be a list of dictionaries.")

    max_index = max((entry.get("INDEX", 0) for entry in base), default=0)
    new_index = max_index + 1
    new_record["INDEX"] = new_index
    base.append(new_record)
    return base


def load_json_file(filepath: str) -> Any:
    """Read a JSON file and return its content."""
    path = _resolve_path(filepath)
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        print(f"File loaded successfully: {path}")
        return data
    except FileNotFoundError:
        print(f"Error: file not found -> {path}")
        raise
    except json.JSONDecodeError as exc:
        print(f"JSON format error for {path}: {exc}")
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"Unexpected error while reading {path}: {exc}")
        raise


def save_json_file(filepath: str, data: Any) -> None:
    """Persist JSON data to the specified filepath."""
    path = _resolve_path(filepath)
    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        print(f"File saved successfully: {path}")
    except OSError as exc:
        print(f"Error while saving {path}: {exc}")
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"Unexpected error while saving {path}: {exc}")
        raise


def update_record(base: list[dict[str, Any]], index: int, updates: dict[str, Any]) -> list[dict[str, Any]]:
    """Update a JSON record matching the provided INDEX."""
    for record in base:
        if record.get("INDEX") == index:
            record.update(updates)
            print(f"Record with index {index} updated.")
            return base
    raise ValueError(f"No record found with index {index}.")


def sort_records(base: Iterable[dict[str, Any]], field: str, reverse: bool = False) -> list[dict[str, Any]]:
    """Return records sorted by the provided field."""
    try:
        return sorted(base, key=lambda value: value.get(field, ""), reverse=reverse)
    except Exception as exc:
        print(f"Error while sorting by field {field}: {exc}")
        raise


def filter_records(base: Iterable[dict[str, Any]], field: str, value: Any) -> list[dict[str, Any]]:
    """Filter records for which ``field`` equals ``value`` (case insensitive)."""
    return [record for record in base if str(record.get(field, "")).lower() == str(value).lower()]


def get_summary(base: list[dict[str, Any]], numeric_fields: Iterable[str]) -> dict[str, Any]:
    """Compute basic statistics for each numeric field provided."""
    summary: dict[str, Any] = {"Total Records": len(base)}
    for field in numeric_fields:
        values = [record.get(field) for record in base if isinstance(record.get(field), (int, float))]
        if values:
            summary[field] = {
                "Min": min(values),
                "Max": max(values),
                "Average": sum(values) / len(values),
            }
    return summary


def check_unique(base: Iterable[dict[str, Any]], field: str) -> bool:
    """Return True if the provided field contains only unique values."""
    values = [record.get(field) for record in base]
    return len(values) == len(set(values))


def get_next_index(filepath: str) -> int:
    """Return the next integer index available in the JSON file."""
    data = load_json_file(filepath)
    indices = [
        int(record.get("INDEX") or record.get("index"))
        for record in data
        if "INDEX" in record or "index" in record
    ]
    return max(indices, default=0) + 1


def get_unique_field_values(filepath: str, field: str) -> list[str]:
    """Return uppercase sorted unique values for the provided field."""
    data = load_json_file(filepath)
    values = {
        str(item.get(field, "")).strip().upper()
        for item in data
        if item.get(field)
    }
    return sorted(values)
