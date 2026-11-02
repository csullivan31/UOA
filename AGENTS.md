# UOA repository guidance

UOA is an independent, local optimization product inspired by REA. Read
`docs/design.md` before changing product behavior. Preserve evidence provenance,
caller choices, originals, and explicit uncertainty. Do not silently redefine
functionality, workload quality, compatibility, or security to claim a gain.

Keep domain semantics, shared application workflows, provider adapters, and
CLI/MCP translation separate. Parse unknown boundary values once; model expected
failures with tagged Results. Reuse an owner's parsed facts instead of repeating
interpretations downstream.

Use Python 3.11+ and the standard library for this initial prototype. Introduce
dependencies only for a concrete capability that justifies their cost. Do not
install or upgrade unrelated tools. Runtime support is initially Linux; state
unsupported coverage explicitly.

Assess optimization value separately from consequences. Routine reversible work
may proceed within authorized scope. Present consequential decisions with
evidence. Discuss structural rewrites and security/data-boundary changes before
substantial implementation. Scores never override preservation constraints.

Execution is not sandboxed. Preserve process ownership proof through cleanup and
do not signal a PID or process group after its identity has been released. Do not
claim escaped-descendant containment or complete family memory measurements from
the current foreground adapter. Do not persist ambient environment values.

For bugs, inspect the producing boundary and sibling consumers, fix shared
ownership/representation problems, and remove superseded code. Keep malformed
input, output coverage, cancellation, finalization, cleanup, and failed-candidate
regressions where applicable. Bound resource use before allocation.

Run `python3 -m unittest discover -s tests -v` for behavior changes and
`python3 -m compileall -q uoa tests examples/search` for syntax verification.
Performance claims require equivalent workloads and reported measurement scope;
ordinary cleanup does not require synthetic benchmarks. Never claim unrun checks.

Use Conventional Commit subjects. Do not commit `.uoa/`, virtual environments,
bytecode, credentials, or captured target artifacts. Human review and ownership
cannot be attested by an agent. Do not publish, deploy, or push without authority.
