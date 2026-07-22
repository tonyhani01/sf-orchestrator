# sf-orchestrator

> sf-orchestrator is an independent open-source project. It is not affiliated with, endorsed by, or sponsored by Salesforce or Anthropic. "Salesforce" and related marks are trademarks of Salesforce, Inc.

An orchestration layer for Salesforce development in Claude Code. A large session model does the high-value thinking — planning, routing, tracking, and reviewing — while cheap, specialized worker subagents do the mechanical implementation. Workers load the public [`forcedotcom/sf-skills`](https://github.com/forcedotcom/sf-skills) Agent Skills at runtime for domain expertise.

## What it is

The goal is large-model quality on planning and verification, at small-model token cost on execution. Instead of one expensive model doing everything, the orchestrator breaks a request into work units, dispatches each to a purpose-built worker on a cheaper model tier, and only escalates or intervenes when a worker's report doesn't hold up under review.

```
            you
             │
             ▼
     ┌───────────────┐
     │  orchestrator │   plans, tracks, reviews (large model)
     └───────┬───────┘
             │  intake → mapper-verified plan → dependency waves
             ▼
     ┌───────────────┐
     │   sf-mapper   │   read-only: verifies schema/metadata before planning
     └───────┬───────┘
             ▼
   ┌─────────────────────┐
   │   dispatch waves     │  bounded concurrency, no file collisions
   └──────────┬────────────┘
              ▼
  ┌─────┬─────┬─────┬─────┬─────┬─────┐
  │apex │ lwc │test │data │debug│meta │  ...worker agents (cheap model tier)
  └─────┴─────┴─────┴─────┴─────┴─────┘
              │
              ▼
     ┌───────────────┐
     │  sf-reviewer  │   adversarial verification against plan + baseline SHA
     └───────┬───────┘
             ▼
        final report to you
```

This fan-out is real token spend, not free — see [Safety](#safety) below.

## Prerequisites

- Claude Code, current major version
- Node.js with `npx`
- Salesforce CLI, with an authenticated org (or run in repo-only mode with no org)
- `npx skills add forcedotcom/sf-skills` — the official Agent Skills library workers load at runtime
- Salesforce DX MCP server — required for any Flow work (the metadata worker's Flow capability is blocked without it)
- macOS/Linux. Windows is untested.

## Install

```
/plugin marketplace add <marketplace-source>
/plugin install sf-orchestrator
```

## Usage

```
/sf-orchestrator:orchestrate <describe the work>
/sf-orchestrator:config
```

`orchestrate` runs the capability check, loads config, resolves the target org, and walks the intake → plan → dispatch → verify → review cycle. `config` creates or edits `.claude/sf-orchestrator.json` against the plugin's schema.

## Workers

Nine agents, each with `tools` set explicitly in frontmatter and no hardcoded `model` (model is always passed per-dispatch):

| Agent | Purpose | Capabilities | Default model |
|---|---|---|---|
| sf-apex-worker | Apex classes, triggers, services, batch/queueable jobs, REST resources | apex, soql | `models.default` (sonnet) |
| sf-lwc-worker | LWC components, templates, CSS, js-meta.xml, wire adapters, Jest tests | lwc | `models.default` (sonnet) |
| sf-test-worker | Apex test classes, coverage/test-run cycles | apex-test-gen, apex-test-run | `models.default` (sonnet) |
| sf-data-worker | Test data seeding, bulk import/export, SOQL authoring, cleanup | data, soql | `models.default` (sonnet) |
| sf-debug-worker | Debug log / governor-limit / stack-trace root-cause analysis | debug-logs | `models.default` (sonnet) |
| sf-metadata-worker | Objects, fields, validation rules, permission sets, flexipages, Flows (via Salesforce DX MCP metadata tools) | object, field, validation-rule, permset, flexipage, flow | `models.default` (sonnet) |
| sf-deploy-worker | Retrieve/diff/deploy metadata; gated | deploy | `models.default` (sonnet) |
| sf-mapper | Read-only schema/metadata explorer used before planning | soql (read-only) | `models.workers["sf-mapper"]` (haiku) |
| sf-reviewer | Adversarial final review of a completed unit against its plan | apex-test-run + domain checks | `models.workers["sf-reviewer"]` (sonnet) |

Model column shows the shipped config defaults; every value is overridable per-worker in `.claude/sf-orchestrator.json`.

## Capability matrix semantics

At startup the orchestrator probes each capability against a list of candidate skill names (current upstream `sf-skills` name first, legacy/local fallback second) and reports one of:

- **supported** — a skill loaded from the probe list.
- **degraded** — no skill loaded, but the dispatched worker has a built-in fallback cheat-sheet; the worker's report always sets `fallback: true` when it used it.
- **blocked** — no skill loaded and no safe fallback exists. This always applies to `flow`, `deploy`, and complex metadata work when nothing is loaded. Blocked capabilities are refused, never faked or improvised around.

Flow work has an additional hard requirement: the Salesforce DX MCP server's metadata tools must be available, independent of skill availability. If they aren't, `flow` is blocked and never falls back to hand-written Flow XML — this is the one capability that never degrades.

## Configuration

`.claude/sf-orchestrator.json`, validated against `schemas/config.schema.json`:

```json
{
  "models": {
    "default": "sonnet",
    "escalation": "opus",
    "workers": { "sf-mapper": "haiku", "sf-reviewer": "sonnet" }
  },
  "limits": { "maxConcurrent": 4, "maxAttempts": 2 },
  "deployWorker": { "enabled": false },
  "effort": null,
  "externalExecutors": {}
}
```

Loader rules (deterministic, shared by the `orchestrate` and `config` skills):

- Missing file → use defaults silently.
- Malformed JSON → stop and tell the user; never guess or overwrite.
- Unknown keys → warn and ignore.
- Invalid model value → error naming the offending key.
- Defaults merge per-key — a partial file is fine.

Notes on individual keys:

- `limits.maxConcurrent` bounds in-flight workers (default 4); org-mutating units (deploy, data mutations) are always serialized regardless of this limit.
- `limits.maxAttempts` bounds retries at the base model tier (default 2) before escalating to `models.escalation`; a failure at escalation blocks the unit.
- `deployWorker.enabled` defaults to `false`. Setting it `true` only permits dispatch — the guard hook still requires a fresh, matching approval file every run (see Safety).
- `effort` is reserved for per-dispatch reasoning-effort control. It is currently inert — Claude Code's Agent tool does not act on it yet — and is documented as such rather than silently ignored.
- `externalExecutors` ships disabled and empty. When configured, it must use an argv-safe contract (fixed executable + fixed argument array — never a shell-interpolated string), requires a one-time user trust confirmation per project, and has a timeout. A configured executor is treated as a tier between the default and escalation models; any executor error falls back to the escalation model.

Config validation (malformed JSON, unknown keys, invalid models/limits/executors) is covered by CI via `scripts/check_config.py` and the negative fixtures under `tests/fixtures/`.

## Safety

Be precise about what is actually enforced versus what is a convention the model is asked to follow:

**Hook-enforced** (`hooks/hooks.json` → `scripts/guard.py`, a `PreToolUse` hook that hard-blocks at the tool-call level, independent of what the model intends to do):

1. Any `Agent` call whose `subagent_type` starts with `sf-` and has no `model` parameter.
2. Any `Bash` command matching a deploy/destructive pattern (`sf project deploy`, `sfdx force:source:deploy`, `sf data delete`, `sf org delete`) unless `.claude/sf-orchestrator-approval.json` exists, is under 60 minutes old, and names the target org present in the command.

**Prompt-level only** (stated plainly so it isn't mistaken for sandboxing): sf-mapper's read-only behavior, worker file-boundary discipline (owned-file lists), the reviewer's adversarial stance, and every fallback cheat-sheet. Nothing prevents a worker from writing outside its plan except the plan itself and the reviewer catching it after the fact.

**Token-cost warning:** fan-out multiplies usage. Every dispatched work unit is a full subagent call, and mapper/reviewer passes run in addition to the workers doing the implementation. For a single small change, orchestration is pure overhead — the skill says so explicitly and offers to execute directly instead.

**Measured, honestly:** in our own benchmarks ([docs/BENCHMARKS.md](docs/BENCHMARKS.md)), self-contained headless tasks cost 2–3.6× MORE orchestrated than inline on the expensive model — worker execution is cheap, but coordination on the expensive model dominates small tasks. Orchestration pays off for large batches, context-heavy or verbose-tool-output work (test loops, log analysis), beyond-one-context jobs, and when independent adversarial review matters — not as a blanket cost optimization.

## Bring your own conventions

Claude Code passes each project's `CLAUDE.md` to subagents automatically. Org-specific policy (naming conventions, layered architecture rules, logging patterns, deploy restrictions) enters entirely through your own `CLAUDE.md` — the orchestrator does not re-paste it into worker prompts, and this plugin ships with no org-specific policy baked in.

## Versioning

Semantic versioning; every release bumps `.claude-plugin/plugin.json`'s `version` and adds an entry to `CHANGELOG.md`.

## License

MIT — see [LICENSE](./LICENSE).
