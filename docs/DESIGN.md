# sf-orchestrator — Open-Source Salesforce Orchestrator Plugin

**Date:** 2026-07-22
**Status:** Approved design, pre-implementation
**Target:** Public GitHub repo, MIT license, installable as a Claude Code plugin

## Purpose

An orchestration layer for Salesforce development in Claude Code: a large session model plans, routes, tracks, and reviews, while all mechanical implementation is delegated to cheaper worker subagents specialized per Salesforce discipline. Workers load the official public Salesforce skills at runtime for domain expertise. Goal: large-model quality on planning/verification at small-model token cost on execution.

Evolved from a private `orchestrator-mode` skill; this plugin replaces it (single source of truth, dogfooded locally). No content from any internal/proprietary guideline document is included — org-specific policy enters only via the runtime conventions hook (each user's own CLAUDE.md).

## Repo layout

```
sf-orchestrator/
├── .claude-plugin/
│   ├── plugin.json          # name: sf-orchestrator, version, description
│   └── marketplace.json     # enables /plugin marketplace add <owner>/sf-orchestrator
├── skills/
│   ├── orchestrate/SKILL.md # main skill
│   └── config/SKILL.md      # interactive config editor
├── agents/
│   ├── sf-apex-worker.md
│   ├── sf-lwc-worker.md
│   ├── sf-test-worker.md
│   ├── sf-data-worker.md
│   ├── sf-debug-worker.md
│   ├── sf-metadata-worker.md
│   ├── sf-deploy-worker.md
│   ├── sf-mapper.md         # read-only
│   └── sf-reviewer.md       # read-only
├── README.md
└── LICENSE                  # MIT
```

**Dependency, not vendored:** the official Salesforce skills plugin is a documented prerequisite. No Salesforce skill content is copied into this repo. The orchestrator verifies at startup that the required skills appear in the available-skills list; if absent it warns with install instructions and workers fall back to their embedded cheat-sheets (see Workers).

## Orchestrator skill (`skills/orchestrate/SKILL.md`)

Carries over the proven generic workflow unchanged, plus a Salesforce layer.

### Generic core (retained)

1. **Intake & restructure** — collect all tasks verbatim; group related tasks into work units; split oversized ones; order into dependency waves; no file collisions within a wave; user checkpoint before wave 1 unless running autonomous.
2. **Track** — task list with unit, grouping, worker, tier, status, wave; every original task must map to a unit.
3. **Plan per unit** — mechanical plans: exact files, exact interfaces, acceptance criteria, gotchas section, do-not-touch list.
4. **Dispatch** — **HARD RULE: every Agent call carries an explicit `model` parameter** (from config); never fork (forks inherit the expensive session model). Independent units dispatch in parallel.
5. **Verify per unit** — check reports against acceptance criteria; on failure fix the plan and redispatch; escalate one model tier after a second failure.
6. **Final review (mandatory)** — sf-reviewer agents check diffs/tests per unit; orchestrator personally adjudicates the requirements diff and cross-unit integration.
7. **Capture lessons** — persist newly discovered gotchas to memory.

Context conservation: the orchestrator never reads whole files itself — sf-mapper explores and the orchestrator consumes summaries. Workers return compact structured reports only (files changed, checks run + output, deviations, skill-load confirmation — no code dumps). If the whole request is one small unit, say so and offer to skip orchestration.

### Salesforce layer (new)

- **Startup check:** confirm official Salesforce skills are available; warn + point to install if not (workers then rely on cheat-sheet fallback).
- **Config load:** read `.claude/sf-orchestrator.json` (defaults if absent) to resolve model per worker.
- **Routing table:**

| Task type                                                                   | Worker                   |
| --------------------------------------------------------------------------- | ------------------------ |
| Apex classes, triggers, services, batch/queueable, REST                     | sf-apex-worker           |
| LWC components, Jest tests, SLDS                                            | sf-lwc-worker            |
| Apex test classes, coverage, test-fix loops                                 | sf-test-worker           |
| Test data seeding, bulk import/export, SOQL authoring                       | sf-data-worker           |
| Debug log analysis, governor limits, stack traces                           | sf-debug-worker          |
| Custom objects/fields, validation rules, permission sets, flows, flexipages | sf-metadata-worker       |
| Org retrieve, diff, deploy                                                  | sf-deploy-worker (gated) |
| Read-only exploration: schema, FLS, permsets, existing code, dependencies   | sf-mapper                |
| Final review: diffs vs plans, test runs                                     | sf-reviewer              |

Mixed units route to the dominant worker with instructions to load the additional skill(s).

- **Mapper-first planning (mandatory):** before writing plans, dispatch sf-mapper to verify assumed metadata — object/field existence and types, FLS, existing classes/triggers, picklist values. Salesforce plans fail on assumed schema; verification is a required step.
- **Conventions hook:** the orchestrator reads the project's CLAUDE.md (and any conventions file it references) and inlines the relevant rules into every worker prompt. This is how org-specific policy (naming, trigger frameworks, logging, deploy rules) reaches workers without living in the plugin.
- **Deploy gating:** sf-deploy-worker dispatches only if `deployWorker.enabled` is true in config, and the orchestrator confirms target org and scope with the user before every deploy dispatch, even in autonomous mode.

## Worker agents

Thin orchestration wrappers; domain expertise loads at runtime from the official Salesforce skills. Each agent file contains:

1. **Frontmatter:** `name`, `description` (routing hints for the orchestrator), `tools` restricted per role. **No `model:` in frontmatter** — the model always comes from the orchestrator's dispatch call driven by config (single source of truth; preserves the hard rule).
2. **Skill-load mandate (first instruction):** invoke the named skills via the Skill tool before any work; confirm the load in the final report. If a named skill is unavailable, use the embedded cheat-sheet and flag "ran on fallback" in the report.
3. **Cheat-sheet fallback:** a short, original, generic Salesforce best-practices section embedded in the agent prompt (bulkification, no SOQL/DML in loops, governor limits, trigger-handler delegation, test patterns, LWC wire/imperative patterns — per discipline). Original content only: not copied from Salesforce's skills nor from any internal document. Used only when the official skill fails to load; the report must say so.
4. **Compact-report contract:** files changed, checks run + their output, deviations/assumptions, skill-load or fallback confirmation. No code dumps or diffs.
5. **Blocked-worker protocol:** if the plan is wrong, impossible, or requires an assumption — stop and report; never improvise.

### Skill assignments and tool restrictions

| Agent              | Loads skills                                                                                                                                    | Tools                                                             |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| sf-apex-worker     | generating-apex, querying-soql                                                                                                                  | full edit + Bash                                                  |
| sf-lwc-worker      | generating-lwc-components                                                                                                                       | full edit + Bash (Jest)                                           |
| sf-test-worker     | generating-apex-test, running-apex-tests                                                                                                        | full edit + Bash                                                  |
| sf-data-worker     | handling-sf-data, querying-soql                                                                                                                 | Bash + Read (+ Write for data files)                              |
| sf-debug-worker    | debugging-apex-logs                                                                                                                             | Read + Bash (log retrieval)                                       |
| sf-metadata-worker | generating-custom-object, generating-custom-field, generating-validation-rule, generating-permission-set, generating-flow, generating-flexipage | full edit                                                         |
| sf-deploy-worker   | deploying-metadata                                                                                                                              | Bash + Read                                                       |
| sf-mapper          | querying-soql                                                                                                                                   | **read-only:** Read, Grep, Glob, Bash (sf describes/queries only) |
| sf-reviewer        | running-apex-tests                                                                                                                              | **read-only:** Read, Grep, Glob, Bash (tests only)                |

## Config

`.claude/sf-orchestrator.json` in the user's project (orchestrator falls back to safe defaults if absent):

```json
{
  "models": {
    "default": "sonnet",
    "escalation": "opus",
    "workers": {
      "sf-mapper": "haiku",
      "sf-reviewer": "sonnet"
    }
  },
  "deployWorker": { "enabled": false },
  "externalExecutors": {
    "codex": { "enabled": false, "command": "codex exec" }
  }
}
```

- `models.workers` overrides `models.default` per agent; `models.escalation` is the tier used after a second failure on a unit.
- `externalExecutors` lets power users add a mid-tier CLI executor (e.g. Codex) invoked via Bash for tasks between the default and escalation tiers; disabled by default and clearly documented as optional/machine-specific.
- The `config` skill (`/sf-orchestrator:config`) walks through these settings with interactive questions and writes the file; it also creates the file with defaults on first run.

## README contents

- What it does and why (token economics of orchestration: expensive model plans/reviews, cheap models execute).
- Install: 2 commands (marketplace add + plugin install), plus the Salesforce skills plugin prerequisite.
- Worker table (as above) and the workflow diagram.
- Config reference.
- "Bring your own conventions" section: how CLAUDE.md rules reach workers via the conventions hook.
- Fallback behavior when the official skills aren't installed.

## Explicit exclusions

- No content from internal developer-guideline documents.
- No bundled copies of Salesforce's skills.
- No CI in v1 (later nicety: smoke-test script validating agent/skill frontmatter).

## Migration (local)

1. Build the repo in a new directory (separate from any client project).
2. Install the plugin locally from the repo clone.
3. Delete `~/.claude/skills/orchestrator-mode`.
4. Personal extras (Codex tier, org gotchas) live in local project config/memory, not the repo.

## Acceptance criteria

- Plugin installs cleanly via marketplace add on a machine with the Salesforce skills plugin present.
- `/sf-orchestrator:orchestrate` runs the startup check, loads config, and routes a mixed Apex+LWC+test request to the correct workers with explicit models on every dispatch.
- With the Salesforce skills plugin absent, workers complete on cheat-sheet fallback and reports flag it.
- `/sf-orchestrator:config` creates and edits the config file interactively.
- sf-deploy-worker never dispatches with `deployWorker.enabled: false` or without user confirmation of org + scope.
- Repo contains no internal-guideline content and no copied Salesforce skill text.
