# Implementation milestones

## Current bootstrap

- Independent local repository and dependency-free Python CLI.
- Strict workload input parsing and tagged expected errors.
- Linux foreground execution with timeouts, bounded output excerpts, output
  digests, cancellation, and original-group cleanup before leader reaping.
- Selected-file and executable identities, explicit coverage, failed-run records.
- Baseline/candidate comparison and terminal workflow regressions.

This is infrastructure for optimization, not an autonomous optimizer yet. The
small search fixture exercises the pipeline; the first representative external
project and hardware lane have not been selected.

## Next: representative optimization experiment

Choose a source-available file-search application with reproducible builds and
useful correctness oracles. Define realistic datasets and preservation criteria.
Capture repeated baselines, investigate an observed bottleneck, prepare a bounded
candidate, and compare required behavior and resource use. Report variability,
regressions, unmeasured costs, and unsupported verification. No gain is assumed.

## Then: consequences and priorities

Represent behavioral reach, compatibility, security sensitivity, reversibility,
verification strength, and maintenance burden with reasons and evidence. Keep
these separate from optimization objectives. Add explicit preservation constraints
and regression limits before automatic acceptance; calibrate weighted decisions
using actual reviewed examples rather than arbitrary universal scores.

## Then: agent interface and coverage

Expose the established workflows through MCP using the same application layer
and named, validated contracts. Evaluate schemas and real client behavior.
Add profiling providers, richer behavioral oracles, stronger process/resource
containment, and host lanes as demonstrated workflows need them. Import REA
findings with version applicability and provenance preserved.

An in-process implementation may later change language if evidence justifies
the maintenance and integration costs. Philosophical alignment with REA does not
require copying its entire provider catalog or implementation stack.
