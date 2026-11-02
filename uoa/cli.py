import argparse
import json
import signal
import sys

from .application import baseline, write_record
from .domain import BoundaryError
from .domain import compare, summarize
from .manifest import read_json


def main(argv=None):
    parser = argparse.ArgumentParser(prog="uoa", description="Local evidence-driven optimization experiments")
    sub = parser.add_subparsers(dest="action", required=True)
    capture = sub.add_parser("baseline", help="Execute declared checks and foreground workloads (not sandboxed)")
    capture.add_argument("--project", required=True)
    capture.add_argument("--workload", required=True)
    capture.add_argument("--output", required=True, help="New evidence file; existing files are preserved")
    capture.add_argument("--full", action="store_true", help="Print complete evidence instead of the default summary")
    comparison = sub.add_parser("compare", help="Compare two baseline records without executing software")
    comparison.add_argument("original")
    comparison.add_argument("candidate")
    comparison.add_argument("--output")
    args = parser.parse_args(argv)
    old_handler = signal.signal(signal.SIGTERM, _cancel)
    try:
        if args.action == "baseline":
            # Do not execute a workload only to discover an existing destination.
            from pathlib import Path
            if Path(args.output).exists() or Path(args.output).is_symlink():
                raise BoundaryError("output_exists", f"Refusing to overwrite evidence: {args.output}")
            result = baseline(args.workload, args.project)
        else:
            result = compare(read_json(args.original), read_json(args.candidate))
        if result.error:
            return _error(result.error.code, result.error.message)
        if args.output:
            write_record(args.output, result.value)
        visible = result.value
        if args.action == "baseline" and not args.full:
            visible = _summary(result.value, args.output)
        print(json.dumps(visible, indent=2, allow_nan=False))
        if result.value.get("status") == "failed" or result.value.get("decision") == "reject_or_investigate":
            return 1
        return 0
    except BoundaryError as error:
        return _error(error.code, str(error))
    except (OSError, ValueError) as error:
        return _error("io_error", str(error))
    except KeyboardInterrupt:
        return _error("cancelled", "Cancelled; no completed evidence record was written")
    finally:
        signal.signal(signal.SIGTERM, old_handler)


def _cancel(_signal, _frame):
    raise KeyboardInterrupt


def _error(code, message):
    print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
    return 2


def _summary(record, output):
    from pathlib import Path
    samples = record["samples"]
    return {
        "schema_version": 1, "kind": "baseline_summary", "run_id": record["run_id"],
        "status": record["status"], "evidence_path": str(Path(output).resolve()),
        "source": record["source"], "workload_id": record["protocol"]["workload_id"],
        "completed_checks": len(record["checks"]), "recorded_samples": len(samples),
        "metrics": {name: summarize([s[name] for s in samples]) for name in
                    ("wall_ms", "cpu_ms", "wait4_max_rss_bytes")} if samples else {},
        "failures": [sample for group in ("checks", "warmups", "samples")
                     for sample in record[group] if sample["status"] != "ok"],
        "selected_files_stable_at_end": record["selected_files_stable_at_end"],
        "executables_stable_at_end": record["executables_stable_at_end"],
        "limitations": record["limitations"],
    }
