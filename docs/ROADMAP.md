# Roadmap (v2)

These items are documented for direction only — none are built in the current release.

## Cost/quality benchmarks vs. direct execution

Measure whether the orchestrated fan-out actually beats a single large model working directly, on both token cost and output quality, across a representative set of Salesforce task types. Without this data, the core value proposition of the plugin is asserted rather than demonstrated.

## Local opt-in telemetry

Optional, local-only logging of tokens used, retry counts, and fallback/degraded-capability usage per run, so a project can see its own orchestration overhead over time. Opt-in and local by design — no data leaves the machine.

## Worktree-backed parallel execution

Run concurrent work units in isolated git worktrees instead of a shared working tree, with a controlled merge step at the end of each wave. This would relax the current no-file-collision constraint within a wave and allow more aggressive parallelism.

## Expanded safe executor adapters

Grow `externalExecutors` beyond a single configured slot, with more adapters vetted under the same argv-safe, trust-confirmed, timeout-bound contract already defined for v1.

## Richer FLS analysis

Extend sf-mapper's field-level-security reporting beyond permission-set grants to cover profiles, permission set groups, and muting permission sets, so FLS answers can claim completeness instead of stating their current limits.
