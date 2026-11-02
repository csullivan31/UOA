"""Parse workload declarations once at the input boundary."""

import json
from dataclasses import dataclass
from pathlib import Path

from .domain import BoundaryError, require, number

MANIFEST_BYTES = 1024 * 1024
JSON_BYTES = 16 * 1024 * 1024
# Retained excerpts expand by up to six bytes per byte in JSON. Reserve space
# for metadata and declarations before accepting a requested run count.
MAX_RUNS = (JSON_BYTES - 2 * MANIFEST_BYTES) // (2 * 4096 * 6 + 8192)


def read_json(path, limit=JSON_BYTES):
    with open(path, "rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, f"JSON exceeds the {limit}-byte admission budget")
    try:
        return json.loads(data, object_pairs_hook=_unique, parse_constant=_constant)
    except (ValueError, UnicodeError) as error:
        raise BoundaryError("invalid_input", f"Invalid JSON: {error}") from error


def _unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def command(value):
    require(isinstance(value, list) and value and all(
        isinstance(item, str) and "\0" not in item for item in value)
        and bool(value[0]), "Commands must be nonempty argv arrays without NUL")
    return tuple(value)


def files(value, field):
    require(isinstance(value, list) and value and all(isinstance(item, str) and item
            and "\0" not in item and not Path(item).is_absolute()
            and ".." not in Path(item).parts for item in value),
            f"{field} must declare nonempty relative file paths inside the project")
    require(len(set(value)) == len(value), f"Duplicate {field}")
    return tuple(value)


@dataclass(frozen=True)
class Workload:
    id: str
    command: tuple[str, ...]
    checks: tuple[tuple[str, ...], ...]
    target_files: tuple[str, ...]
    input_files: tuple[str, ...]
    verification_files: tuple[str, ...]
    repetitions: int
    warmups: int
    timeout_seconds: float
    environment_label: str


def parse_workload(value):
    keys = {"id", "command", "checks", "target_files", "input_files",
            "verification_files", "repetitions", "warmups", "timeout_seconds", "environment_label"}
    require(isinstance(value, dict) and set(value) == keys,
            "Workload must contain exactly: " + ", ".join(sorted(keys)))
    for key in ("id", "environment_label"):
        require(isinstance(value[key], str) and bool(value[key].strip()), f"{key} is required")
    require(type(value["repetitions"]) is int and value["repetitions"] > 0,
            "repetitions must be a positive integer")
    require(type(value["warmups"]) is int and value["warmups"] >= 0,
            "warmups must be a nonnegative integer")
    require(number(value["timeout_seconds"]) and value["timeout_seconds"] > 0,
            "timeout_seconds must be finite and positive")
    require(isinstance(value["checks"], list) and value["checks"], "At least one check is required")
    require(value["repetitions"] + value["warmups"] + len(value["checks"]) <= MAX_RUNS,
            f"Run count exceeds the retained-evidence budget ({MAX_RUNS} commands per record)")
    return Workload(
        value["id"], command(value["command"]), tuple(command(c) for c in value["checks"]),
        files(value["target_files"], "target_files"), files(value["input_files"], "input_files"),
        files(value["verification_files"], "verification_files"), value["repetitions"],
        value["warmups"], value["timeout_seconds"], value["environment_label"],
    )
