# Ultra Optimize Anything: product proposal

Status: agreed product direction; proposed contracts and implementation scope.
This describes an independent optimization product inspired by REA. It does not
add capabilities to REA or authorize integration into REA distributions.

## Purpose

Ultra Optimize Anything (UOA, working name) helps an agent improve software's
resource efficiency while preserving required behavior, compatibility, and
security properties. Any runnable software is the long-term target; support is
declared per operation, environment, and verification capability.

The product aims for measurable improvement within explicit constraints. It
does not claim universal optimality or complete equivalence from passing tests.
An investigation that establishes no worthwhile improvement is a valid result.

## Relationship to REA

REA investigates how software works. UOA investigates resource use, prepares
improvements, and evaluates their consequences. Users may bring REA findings,
but UOA also works directly with source projects.

Imported findings retain target identity, provenance, coverage, limitations,
and their distinction between observations, derivations, and inferences. UOA
checks applicability to the supplied version and marks unresolved applicability
as unknown. Imported claims do not become UOA measurements.

Reverse-engineered understanding does not imply available, rebuildable source.
UOA reports when missing source, build inputs, workloads, or verification prevent
a proposed improvement. Reconstruction is not part of the initial workflow.

## Operating philosophy

- Operate locally through shared CLI and MCP workflows.
- Let the coding agent reason and edit using ordinary development tools; give it
  reliable inspection, profiling, experiment, and comparison capabilities.
- Preserve caller-selected inputs, originals, Evidence, and uncertainty.
- Profile representative work before claiming a bottleneck or improvement.
- Scale autonomy with consequences, reversibility, and verification strength.
- Count optimization overhead as well as the target's resource savings.
- Keep the optimizer's own dependencies and resource use deliberate.

## Optimization request

A request identifies the project or artifact, build inputs, execution environment,
representative workloads, preservation requirements, optimization priorities,
regression limits, and authorized actions. Initially, users supply ordinary
build, test, and workload commands rather than a new orchestration language.

Priorities can cover latency, throughput, CPU time, peak memory, distribution and
installed size, storage activity, network traffic, and energy. Units, workload,
and measurement method remain explicit. CPU time alone does not establish energy
savings. Unknown energy cost remains unknown.

Preservation requirements can include outputs, APIs, file formats, appearance,
accessibility, error behavior, supported platforms, and security controls.
Requirements are constraints, not terms a performance score can outweigh.

## Experiment workflow

1. Establish target identity, build reproducibility, requirements, authority,
   and available verification. Surface unresolved prerequisites.
2. Record baseline correctness and resource use for selected workloads.
3. Attribute observed costs and propose opportunities with supporting Evidence.
4. Assess expected benefit, consequences, verification gaps, and experiment cost.
5. Prepare an isolated candidate within authorized scope. Keep the original
   available and record the change and candidate identity.
6. Check behavior and relevant security properties; measure comparable workloads.
7. Accept, reject, or retain alternatives according to constraints and evidence.
   Recheck the combined candidate before presenting its aggregate improvement.
8. Deliver a reviewable patch or artifact, measurements, tradeoffs, and unknowns.

Measure representative completed tasks, distinguish cold and warm runs, retain
repeated samples and variability, and identify toolchain and environment changes.
Compare equivalent work; do not silently reduce features, data, quality, or
coverage. Report experiment time and resource cost, with estimated payback only
when savings and expected future usage support it.

## Weighted effects and autonomy

Keep optimization value separate from change consequences. Expected gains help
rank experiments; measured gains support acceptance. Avoid arbitrary universal
weights before representative use establishes useful calibration.

Assess consequences using behavioral reach, compatibility, security sensitivity,
reversibility, verification strength, and added maintenance burden. Preserve the
individual assessments and their reasons rather than exposing only a total.
Missing evidence raises uncertainty; it does not establish low consequence.

| Action class | Proposed behavior |
| --- | --- |
| Routine | Proceed within agreed authority for isolated, reversible changes with limited reach and strong verification. |
| Consequential | Prepare a bounded, reviewable candidate and evidence where authorized; bring the decision to the user before adoption. |
| Structural | Discuss the approach before substantial implementation of language/framework migrations, major rewrites, persistent data changes, or security-boundary changes. |

Evaluate actual effects rather than changed line count. Assess the cumulative
candidate as well as individual edits. Authorization to inspect does not imply
authorization to execute targets, mutate files, install dependencies, or deploy.
An isolated workspace does not itself contain subprocess filesystem or network
effects; report actual execution authority and containment.

## Initial capability boundaries

These are proposed operation boundaries, not finalized tool names or schemas.
Use named, typed contracts shared by CLI and MCP.

| Capability | Inputs | Result |
| --- | --- | --- |
| Baseline | Target, environment, workload commands, checks, resource scope | Identified run, check outcomes, measurements, samples, coverage, Evidence |
| Profile | Identified target/run, workload, available profiler and selected scope | Attributed costs, locations, profiler overhead and coverage limits |
| Evaluate candidate | Original and candidate identities, requirements, comparable workloads | Check outcomes, resource deltas, variability, consequences, unknowns |
| Compare candidates | Explicit candidate runs, priorities and constraints | Comparability assessment, supported tradeoffs, constraint outcomes |

Reuse existing REA contracts and process/resource ownership foundations where
their semantics match. Keep provider protocols out of domain and application
layers. A comparison must explain incompatible runs rather than invent a delta.
Cancellation, partial results, and failed cleanup retain meaningful outcomes and
resource ownership for retry. Measurements and complete Evidence remain
accessible even when the inline answer is compact.

## First vertical slice

Use an existing source-available local file-search application. Select the actual
project after checking that it builds, has meaningful workloads and correctness
oracles, and permits a reproducible baseline. No improvement is assumed.

Exercise small folders, large trees, repeated searches, and changing files.
Check required matching/ranking behavior, Unicode handling, permissions, and
error outcomes where supported by the selected application. Measure indexing
time, search latency, peak memory, startup, and distribution size where applicable.

The initial release supports source projects with user-supplied commands on one
declared host/toolchain lane. Broad adapters follow a working end-to-end workflow;
initial language and host support remain undecided. Binary rewriting, automatic
reconstruction, production deployment, and invasive instrumentation are outside
this first slice.

## Acceptance criteria

- One real project completes baseline, diagnosis, candidate, and comparison.
- Every improvement claim identifies the original, candidate, environment,
  workload, measurement method, and observed variability.
- Required behavior is checked with explicit coverage and limitations.
- A failing candidate is rejected or reported as unresolved, even if faster.
- The workflow can report no demonstrated gain without manufacturing changes.
- Consequential decisions include reasons and concrete supporting evidence.
- Original inputs remain available; cancellation and cleanup outcomes are clear.
- CLI and MCP preserve the same semantics, caller choices, and Evidence.

These are proposed checks; no application was selected, benchmarked, optimized,
or verified while preparing this proposal.

## Next design decisions

Select the independent product/repository location, first project and host lane,
then specify the smallest baseline and candidate-comparison contracts needed for
that workflow. Decide which REA foundations to reuse after inspecting their
actual consumers and costs. Do not assume a complete fork is necessary to
preserve philosophical alignment.
