"""Pure comparison semantics and tagged boundary outcomes."""

from dataclasses import dataclass
from math import isfinite
from statistics import median
import re
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Failure:
    code: str
    message: str


@dataclass(frozen=True)
class Result(Generic[T]):
    value: T | None = None
    error: Failure | None = None

    def __post_init__(self):
        if (self.value is None) == (self.error is None):
            raise ValueError("Result requires exactly one value or error")


class BoundaryError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def require(condition: bool, message: str):
    if not condition:
        raise BoundaryError("invalid_input", message)


def number(value):
    return (type(value) in (int, float) and 0 <= value <= 1.7976931348623157e308
            and (type(value) is int or isfinite(value)))


def summarize(values):
    return {"median": median(values), "min": min(values), "max": max(values),
            "samples": len(values)}


def _record(record):
    require(isinstance(record, dict) and type(record.get("schema_version")) is int
            and record.get("schema_version") == 1
            and record.get("kind") == "baseline", "Expected a UOA v1 baseline record")
    require(record.get("status") in ("complete", "failed"), "Invalid run status")
    for key in ("source", "inputs", "verification", "protocol", "environment"):
        require(isinstance(record.get(key), dict), f"Missing {key} evidence")
    require(isinstance(record.get("run_id"), str), "Missing run identity")
    for name in ("source", "inputs", "verification"):
        snapshot = record[name]
        require(snapshot.get("scope") == "explicitly_selected_files"
                and isinstance(snapshot.get("files"), list) and snapshot["files"],
                f"Missing selected-file identities in {name}")
        for item in snapshot["files"]:
            require(isinstance(item, dict) and isinstance(item.get("path"), str)
                    and digest(item.get("sha256")), f"Invalid file identity in {name}")
    protocol = record["protocol"]
    for key in ("workload_id", "metric_adapter", "cache_policy", "environment_label"):
        require(isinstance(protocol.get(key), str) and protocol[key], f"Missing protocol {key}")
    require(protocol["metric_adapter"] == "linux-wait4-pidfd-v1", "Unsupported measurement adapter")
    require(type(protocol.get("repetitions")) is int and protocol["repetitions"] > 0
            and type(protocol.get("warmups")) is int and protocol["warmups"] >= 0
            and number(protocol.get("timeout_seconds")) and protocol["timeout_seconds"] > 0,
            "Invalid protocol run counts or timeout")
    require(isinstance(protocol.get("checks"), list) and protocol["checks"], "Missing protocol checks")
    for command in [protocol.get("command"), *protocol["checks"]]:
        require(isinstance(command, list) and command and all(isinstance(v, str) for v in command),
                "Invalid recorded command")
    for key in ("system", "release", "machine", "hostname", "python"):
        require(isinstance(record["environment"].get(key), str), f"Missing environment {key}")
    require(isinstance(record["environment"].get("external_executables"), list),
            "Missing external executable evidence")
    require(isinstance(record.get("checks"), list) and record["checks"],
            "Verification checks are required")
    require(isinstance(record.get("samples"), list) and isinstance(record.get("warmups"), list),
            "Missing samples or warmups")
    for sample in record["checks"] + record["warmups"] + record["samples"]:
        require(isinstance(sample, dict) and sample.get("status") in
                ("ok", "nonzero_exit", "timeout", "cancelled", "launch_failed", "output_incomplete"),
                "Invalid command result")
        require(type(sample.get("exit_code")) is int, "Missing exit code")
        for stream_name in ("stdout", "stderr"):
            stream = sample.get(stream_name)
            require(isinstance(stream, dict) and digest(stream.get("sha256"))
                    and type(stream.get("complete")) is bool, "Missing output identity or coverage")
        for key in ("wall_ms", "cpu_ms", "wait4_max_rss_bytes"):
            require(number(sample.get(key)), f"Invalid {key}")
    return record


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def compare(original, candidate) -> Result[dict]:
    """Compare recorded facets; never claim whole-program equivalence."""
    try:
        original, candidate = _record(original), _record(candidate)
        for key in ("protocol", "inputs", "verification", "environment"):
            if original[key] != candidate[key]:
                return Result(error=Failure("incomparable", f"Recorded {key} differ"))
        if original["status"] != "complete" or candidate["status"] != "complete":
            return Result(error=Failure("failed_run", "Both runs must complete all checks and samples"))
        for record in (original, candidate):
            require(record.get("selected_files_stable_at_end") is True
                    and record.get("executables_stable_at_end") is True,
                    "Complete run must establish stable selected files and executables")
            require(record["samples"] and all(item["status"] == "ok" for item in
                    record["checks"] + record["warmups"] + record["samples"]),
                    "Complete run contains failed or missing samples")
            require(type(record["protocol"].get("repetitions")) is int
                    and len(record["samples"]) == record["protocol"]["repetitions"],
                    "Sample count does not match declared repetitions")
            require(len(record["warmups"]) == record["protocol"]["warmups"]
                    and len(record["checks"]) == len(record["protocol"]["checks"]),
                    "Check or warmup coverage does not match protocol")
            require(all(item["exit_code"] == 0 and item["stdout"]["complete"] is True
                        and item["stderr"]["complete"] is True for item in
                        record["checks"] + record["warmups"] + record["samples"]),
                    "Sample output coverage is incomplete")
        matches = {}
        for stream in ("stdout", "stderr"):
            expected = {s[stream]["sha256"] for s in original["samples"]}
            observed = {s[stream]["sha256"] for s in candidate["samples"]}
            matches[stream] = len(expected) == 1 and observed == expected
        metrics = {}
        for name in ("wall_ms", "cpu_ms", "wait4_max_rss_bytes"):
            before = summarize([s[name] for s in original["samples"]])
            after = summarize([s[name] for s in candidate["samples"]])
            metrics[name] = {
                "original": before, "candidate": after,
                "median_change_percent": None if before["median"] == 0 else
                100 * (after["median"] - before["median"]) / before["median"],
            }
        behavior = "matched_observed_output" if all(matches.values()) else "unresolved_or_changed"
        return Result(value={
            "schema_version": 1, "kind": "comparison",
            "original_run_id": original["run_id"], "candidate_run_id": candidate["run_id"],
            "behavior": behavior, "output_matches": matches, "metrics": metrics,
            "decision": "review_candidate" if all(matches.values()) else "reject_or_investigate",
            "limitations": [
                "Passing declared checks and matching stdout/stderr do not prove full equivalence or security.",
                "Environment comparison covers recorded facets; ambient environment and machine load are uncontrolled.",
                "Min/median/max describe samples, not statistical significance or causal improvement.",
                "wait4 max RSS is not simultaneous peak process-family memory; CPU covers the child and descendants it waited for.",
                "No automatic adoption, weighted ranking, or energy claim is performed.",
            ],
        })
    except BoundaryError as error:
        return Result(error=Failure(error.code, str(error)))
