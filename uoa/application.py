"""Shared baseline workflow; no CLI formatting or provider protocols."""

import hashlib
import json
import os
import platform
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .domain import BoundaryError, Failure, Result, require
from .manifest import JSON_BYTES, MANIFEST_BYTES, parse_workload, read_json
from .runner import run_command


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def snapshot(root, names):
    evidence = []
    for name in sorted(names):
        path = root / name
        # Selected files are ordinary files, not traversals through symlinks.
        relative = Path(name)
        for parent in (relative, *relative.parents):
            require(not (root / parent).is_symlink(), f"Symlink not admitted in selected path: {name}")
        require(path.is_file(), f"Selected input is not an ordinary file: {name}")
        evidence.append({"path": name, "sha256": file_digest(path)})
    return {"scope": "explicitly_selected_files", "files": evidence}


def executable_identity(command, root):
    executable = command[0]
    if "/" in executable:
        path = Path(executable)
        path = path if path.is_absolute() else root / path
    else:
        found = shutil.which(executable)
        if found is None:
            raise BoundaryError("missing_executable", f"Executable not found on PATH: {executable}")
        path = Path(found)
    path = path.resolve(strict=True)
    require(path.is_file() and os.access(path, os.X_OK), f"Not an executable file: {path}")
    return {"caller_executable": executable, "resolved_path": str(path), "sha256": file_digest(path)}


def baseline(manifest_path, project_path) -> Result[dict]:
    try:
        workload = parse_workload(read_json(manifest_path, MANIFEST_BYTES))
        root = Path(project_path).resolve(strict=True)
        require(root.is_dir(), "Project must be a directory")
        source = snapshot(root, workload.target_files)
        inputs = snapshot(root, workload.input_files)
        verification = snapshot(root, workload.verification_files)
        commands = (workload.command, *workload.checks)
        executables = [executable_identity(command, root) for command in commands]
        target_paths = {(root / name).resolve() for name in workload.target_files}
        external_executables = [identity for identity in executables
                                if Path(identity["resolved_path"]) not in target_paths]
        record = {
            "schema_version": 1, "kind": "baseline", "run_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "complete",
            "caller_input": {"project": str(project_path), "manifest": str(manifest_path)},
            "project_path": str(root), "source": source, "inputs": inputs, "verification": verification,
            "protocol": {
                "workload_id": workload.id, "command": list(workload.command),
                "checks": [list(check) for check in workload.checks],
                "repetitions": workload.repetitions, "warmups": workload.warmups,
                "timeout_seconds": workload.timeout_seconds,
                "metric_adapter": "linux-wait4-pidfd-v1",
                "cache_policy": "no cache reset; warmups explicit; cold/warm state otherwise uncontrolled",
                "environment_label": workload.environment_label,
            },
            "executable_evidence": executables,
            "environment": {"system": platform.system(), "release": platform.release(),
                            "machine": platform.machine(), "hostname": platform.node(),
                            "python": sys.version, "external_executables": external_executables},
            "checks": [], "warmups": [], "samples": [],
            "limitations": [
                "Execution inherits user permissions and ambient environment; neither is sandboxed or persisted as an environment snapshot.",
                "Only selected files are fingerprinted; undeclared inputs and mid-run changes restored before the final snapshot may escape detection.",
                "Foreground workloads only: original process group is signalled on completion; escaped descendants and descendant exit completion are not verified.",
                "CPU includes child and descendants it waited for; wait4 max RSS is not simultaneous peak family memory.",
                "Energy, security equivalence, machine load, and cold-cache state are not measured.",
            ],
        }
        for group, command_list in (
            ("checks", workload.checks),
            ("warmups", (workload.command for _ in range(workload.warmups))),
            ("samples", (workload.command for _ in range(workload.repetitions))),
        ):
            if record["status"] != "complete":
                break
            for command in command_list:
                # Execute the exact resolved executable whose identity was recorded.
                identity = executables[commands.index(command)]
                actual = (identity["resolved_path"], *command[1:])
                sample = run_command(actual, str(root), workload.timeout_seconds)
                record[group].append(sample)
                if sample["status"] != "ok":
                    record["status"] = "failed"
                    break
        snapshots_after = (snapshot(root, workload.target_files), snapshot(root, workload.input_files),
                           snapshot(root, workload.verification_files))
        record["selected_files_stable_at_end"] = snapshots_after == (source, inputs, verification)
        executables_after = [executable_identity(command, root) for command in commands]
        record["executables_stable_at_end"] = executables_after == executables
        if not record["selected_files_stable_at_end"] or not record["executables_stable_at_end"]:
            record["status"] = "failed"
        return Result(value=record)
    except BoundaryError as error:
        return Result(error=Failure(error.code, str(error)))
    except (OSError, ValueError) as error:
        return Result(error=Failure("io_error", str(error)))


def write_record(path, record):
    """Exclusive create preserves existing evidence; remove our own partial file on failure."""
    content = json.dumps(record, indent=2, allow_nan=False) + "\n"
    require(len(content.encode("utf-8")) <= JSON_BYTES, "Evidence exceeds the 16 MiB record budget")
    try:
        with open(path, "x", encoding="utf-8") as stream:
            try:
                stream.write(content)
            except BaseException:
                Path(path).unlink()
                raise
    except FileExistsError as error:
        raise BoundaryError("output_exists", f"Refusing to overwrite evidence: {path}") from error
