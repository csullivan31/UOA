# UOA — Ultra Optimize Anything

Local, evidence-driven software optimization. Understand resource use, prepare
improvements, and verify measured results while preserving required behavior.

Inspired by [REA](https://github.com/morluto/rea). REA findings can inform an
optimization investigation; UOA also works directly with source projects.

**Status:** initial executable prototype. It captures baselines and compares
candidates. It does not yet profile bottlenecks, edit code, calculate weighted
consequences, import REA records, or expose MCP tools.

## Run locally

Requires Python 3.11+ and Linux with `pidfd_open` support. No runtime packages,
installation, account, or network service are required. From this repository:

```bash
python3 -m uoa --help
mkdir -p .uoa
python3 -m uoa baseline \
  --project examples/search \
  --workload examples/search/workload.json \
  --output .uoa/original.json

# After preparing a candidate, capture it with the same workload declaration.
# Running the unchanged example again is a workflow smoke test, not an optimization.
python3 -m uoa baseline \
  --project examples/search \
  --workload examples/search/workload.json \
  --output .uoa/candidate.json

python3 -m uoa compare .uoa/original.json .uoa/candidate.json
```

Baseline prints a compact summary and stores complete evidence at `--output`.
Use `--full` to print the complete record. Existing output files are preserved;
choose a new path for each experiment. An optional `compare --output PATH` also
preserves a comparison record.

The included search program is a small workflow fixture, not a representative
application benchmark or evidence of an optimization gain. Its declared checks
exercise matching, no results, and Unicode case folding.

## Declare a workload

Use `examples/search/workload.json` as a starting point. Declare argv arrays
for the workload and at least one check, selected target files, workload input
files, verification files, repetitions, warmups, per-command timeout, and a
caller-chosen environment label. Paths to selected files are relative to the
project directory. Symlink traversal and parent traversal are not admitted.

Commands execute directly, without an implicit shell, from the selected project.
An explicitly requested shell still executes shell code. Commands inherit user
permissions and environment; execution is **not sandboxed**. This initial
adapter supports trusted foreground workloads, not daemons or workloads that
change their own session/process group. No changes are deployed or adopted.

## Evidence and interpretation

- Every run identifies selected source, input, verification, and executable files
  with SHA-256 digests. Inputs and executables are checked again at the end.
- Declared checks run first; a failing check stops measurement. Failed, timed-out,
  and cancelled commands retain the evidence collected when a record can finish.
- Complete stdout/stderr are hashed while only the first 4 KiB per stream is
  retained as an excerpt. Excerpt truncation and output coverage are explicit.
- Measurements include launch-to-observed-exit wall time, `wait4` CPU time, and
  Linux `wait4` maximum RSS. RSS is **not simultaneous peak process-family memory**;
  CPU includes descendants only when accounted through the child's waits.
- Comparison requires matching recorded protocols, workload inputs, verification
  files, and environment facets. Both runs must complete all declared commands.
  Changed or nondeterministic stdout/stderr require investigation.
- Passing checks and output matching do not prove full functional or security
  equivalence. A matching candidate is offered for review, never auto-adopted.
- Min/median/max describe observed samples. They do not establish statistical
  significance, controlled cold-cache performance, or causation. Energy is unknown.

Only explicitly selected files are fingerprinted. Undeclared dependencies and
changes restored between observations can escape detection. Ambient environment
values are inherited but not serialized; machine load and environment equivalence
remain uncontrolled. The environment label is a caller declaration, not proof.

The supervisor uses a launch gate, pidfd exit notification, and an unreaped leader
to signal its original process group before releasing that identity. Group
signalling does not prove descendant completion, and escaped descendants are not
tracked. Resource/process containment needs a stronger future adapter.

Workload declarations have a 1 MiB input budget and evidence records a 16 MiB
budget. Command count is bounded using retained-excerpt JSON expansion; ordinary
output is streamed through bounded buffers. These are resource admission limits.

Exit codes: `0` completed baseline/reviewable comparison; `1` failed baseline or
changed/unresolved output; `2` malformed input, incomparable runs, or I/O failure.

## Develop

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q uoa tests examples/search
```

Shared workflows live in `uoa/application.py`, pure comparison semantics in
`uoa/domain.py`, input parsing in `uoa/manifest.py`, Linux execution in
`uoa/runner.py`, and terminal presentation in `uoa/cli.py`. The initial adapter
uses the Python standard library; REA runtime code has not been copied.

See [the product design](docs/design.md) and [implementation milestones](docs/roadmap.md).

## License

UOA is licensed under GPL-3.0-only; see [LICENSE](LICENSE). REA attribution
and its MIT notice are retained in [NOTICE.md](NOTICE.md) and
[licenses/REA-MIT.txt](licenses/REA-MIT.txt).
