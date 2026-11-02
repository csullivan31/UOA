import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from uoa.application import baseline
from uoa.domain import compare
from uoa.manifest import read_json, parse_workload
from uoa.domain import BoundaryError
from uoa.runner import run_command

REPO = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "target.py").write_text("print('same result')\n")
        (self.root / "input.txt").write_text("fixed input\n")
        (self.root / "check.py").write_text("print('check passed')\n")
        self.manifest = {
            "id": "test", "command": [sys.executable, "target.py"],
            "checks": [[sys.executable, "check.py"]],
            "target_files": ["target.py"], "input_files": ["input.txt"],
            "verification_files": ["check.py"], "repetitions": 2, "warmups": 0,
            "timeout_seconds": 3, "environment_label": "test-host",
        }
        self.path = self.root / "workload.json"
        self.save_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def save_manifest(self):
        self.path.write_text(json.dumps(self.manifest))

    def capture(self):
        result = baseline(str(self.path), str(self.root))
        self.assertIsNone(result.error, result.error)
        return result.value

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "uoa", *args], cwd=REPO,
                              capture_output=True, text=True, timeout=10)

    def test_cli_baseline_and_comparison(self):
        files = [self.root / name for name in ("before.json", "after.json")]
        for path in files:
            result = self.cli("baseline", "--project", str(self.root), "--workload", str(self.path),
                              "--output", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("compare", *(str(path) for path in files))
        self.assertEqual(result.returncode, 0, result.stderr)
        comparison = json.loads(result.stdout)
        self.assertEqual(comparison["behavior"], "matched_observed_output")
        self.assertEqual(comparison["decision"], "review_candidate")
        self.assertIn("cpu_ms", comparison["metrics"])

    def test_changed_output_is_not_accepted(self):
        original = self.capture()
        (self.root / "target.py").write_text("print('wrong result')\n")
        result = compare(original, self.capture())
        self.assertEqual(result.value["decision"], "reject_or_investigate")

    def test_changed_stderr_is_not_accepted(self):
        original = self.capture()
        (self.root / "target.py").write_text("import sys; print('same result'); print('new warning', file=sys.stderr)\n")
        result = compare(original, self.capture())
        self.assertEqual(result.value["decision"], "reject_or_investigate")
        self.assertTrue(result.value["output_matches"]["stdout"])
        self.assertFalse(result.value["output_matches"]["stderr"])

    def test_selected_target_executable_can_change(self):
        script = self.root / "target.sh"
        script.write_text("#!/bin/sh\nprintf 'same result\\n'\n")
        script.chmod(0o700)
        self.manifest["target_files"] = ["target.sh"]
        self.manifest["command"] = ["./target.sh"]
        self.save_manifest()
        original = self.capture()
        script.write_text("#!/bin/sh\n# Equivalent implementation\nprintf '%s\\n' 'same result'\n")
        result = compare(original, self.capture())
        self.assertIsNone(result.error, result.error)
        self.assertEqual(result.value["decision"], "review_candidate")

    def test_failed_checks_stop_measurement(self):
        original = self.capture()
        (self.root / "check.py").write_text("raise SystemExit(3)\n")
        candidate = self.capture()
        self.assertEqual(candidate["status"], "failed")
        self.assertEqual(candidate["samples"], [])
        # Different oracle is independently incomparable.
        self.assertEqual(compare(original, candidate).error.code, "incomparable")
        self.assertEqual(compare(candidate, candidate).error.code, "failed_run")

    def test_input_and_oracle_changes_are_incomparable(self):
        original = self.capture()
        for field in ("inputs", "verification", "environment", "protocol"):
            candidate = copy.deepcopy(original)
            candidate[field]["changed"] = True
            self.assertEqual(compare(original, candidate).error.code, "incomparable")

    def test_malformed_records_fail_closed(self):
        original = self.capture()
        for malformed in (None, {}, {"schema_version": 1, "kind": "baseline"}):
            self.assertEqual(compare(original, malformed).error.code, "invalid_input")
        for mutate in (
            lambda r: r["samples"][0].update(cpu_ms=float("nan")),
            lambda r: r["samples"][0].update(status="nonzero_exit"),
            lambda r: r.update(selected_files_stable_at_end=False),
            lambda r: r["samples"].pop(),
        ):
            candidate = copy.deepcopy(original)
            mutate(candidate)
            self.assertEqual(compare(original, candidate).error.code, "invalid_input")

    def test_existing_evidence_prevents_execution(self):
        output = self.root / "existing.json"
        output.write_text("keep this evidence")
        (self.root / "check.py").write_text("open('executed', 'w').close()\n")
        result = self.cli("baseline", "--project", str(self.root), "--workload", str(self.path),
                          "--output", str(output))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "output_exists")
        self.assertEqual(output.read_text(), "keep this evidence")
        self.assertFalse((self.root / "executed").exists())

    def test_boundary_validation(self):
        for patch in ({"repetitions": True}, {"timeout_seconds": float("inf")},
                      {"target_files": ["../outside"]}, {"unknown": True},
                      {"repetitions": 10000000}):
            with self.assertRaises(BoundaryError):
                parse_workload(self.manifest | patch)
        self.path.write_text('{"id": 1, "id": 2}')
        with self.assertRaises(BoundaryError):
            read_json(self.path)

    def test_symlink_input_rejected(self):
        (self.root / "link.txt").symlink_to(self.root / "input.txt")
        self.manifest["input_files"] = ["link.txt"]
        self.save_manifest()
        self.assertEqual(baseline(self.path, self.root).error.code, "invalid_input")

    def test_source_mutation_invalidates_run(self):
        (self.root / "target.py").write_text("print('ok'); open('input.txt', 'w').write('changed')\n")
        result = self.capture()
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["selected_files_stable_at_end"])

    def test_missing_executable_has_actionable_error(self):
        self.manifest["command"] = ["uoa-certainly-missing-executable"]
        self.save_manifest()
        result = baseline(self.path, self.root)
        self.assertEqual(result.error.code, "missing_executable")
        self.assertIn("PATH", result.error.message)

    def test_timeout_retains_partial_output(self):
        result = run_command((sys.executable, "-c", "import time; print('partial', flush=True); time.sleep(30)"),
                             str(self.root), 0.15)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["stdout"]["excerpt"], "partial\n")

    def test_timeout_before_handshake_does_not_release_workload(self):
        result = run_command((sys.executable, "-c", "open('unexpected-launch', 'w').close()"),
                             str(self.root), 1e-9)
        self.assertEqual(result["status"], "timeout")
        self.assertFalse((self.root / "unexpected-launch").exists())

    def test_cancellation_during_final_reap_finishes_cleanup(self):
        wait4 = os.wait4
        reaped = []

        def cancel_while_reaping(pid, options):
            os.kill(os.getpid(), signal.SIGINT)
            outcome = wait4(pid, options)
            reaped.append(pid)
            return outcome

        with patch("uoa.runner.os.wait4", side_effect=cancel_while_reaping):
            with self.assertRaises(KeyboardInterrupt):
                run_command((sys.executable, "-c", "print('finished')"), str(self.root), 3)
        self.assertEqual(len(reaped), 1)
        with self.assertRaises(ChildProcessError):
            os.waitpid(reaped[0], os.WNOHANG)

    def test_large_output_keeps_full_digest_with_bounded_excerpt(self):
        result = run_command((sys.executable, "-c", "import sys; sys.stdout.write('x'*200000)"),
                             str(self.root), 3)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stdout"]["sha256"], hashlib.sha256(b"x" * 200000).hexdigest())
        self.assertEqual(len(result["stdout"]["excerpt"]), 4096)
        self.assertTrue(result["stdout"]["excerpt_truncated"])

    def test_leader_exit_stops_same_group_child_holding_pipes(self):
        code = "import os,time; child=os.fork(); time.sleep(30) if child == 0 else None"
        started = time.monotonic()
        result = run_command((sys.executable, "-c", code), str(self.root), 3)
        self.assertEqual(result["status"], "ok")
        self.assertLess(time.monotonic() - started, 2)
        self.assertTrue(result["stdout"]["complete"])

    def test_cli_cancellation_writes_failed_evidence(self):
        (self.root / "target.py").write_text("import time; open('started', 'w').close(); time.sleep(30)\n")
        output = self.root / "cancelled.json"
        process = subprocess.Popen(
            [sys.executable, "-m", "uoa", "baseline", "--project", str(self.root),
             "--workload", str(self.path), "--output", str(output)],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 3
            while not (self.root / "started").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.root / "started").exists())
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 1, stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["samples"][0]["status"], "cancelled")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
