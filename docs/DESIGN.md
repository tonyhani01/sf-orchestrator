# sf-orchestrator — Open-Source Salesforce Orchestrator Plugin

**Date:** 2026-07-22 (rev 2 — external review adoptions)
**Status:** Approved design, pre-implementation
**Target:** Public GitHub repo, MIT license, installable as a Claude Code plugin

> sf-orchestrator is an independent open-source project. It is not affiliated with, endorsed by, or sponsored by Salesforce or Anthropic. "Salesforce" and related marks are trademarks of Salesforce, Inc.

## Purpose

An orchestration layer for Salesforce development in Claude Code: a large session model plans, routes, tracks, and reviews, while all mechanical implementation is delegated to cheaper worker subagents specialized per Salesforce discipline. Workers load the public `forcedotcom/sf-skills` Agent Skills at runtime for domain expertise. Goal: large-model quality on planning/verification at small-model token cost on execution.

Evolved from a private `orchestrator-mode` skill (same author; no third-party or internal-document content). Org-specific policy enters only via the runtime conventions hook (each user's own CLAUDE.md).

## Repo layout

```
sf-orchestrator/
├── .claude-plugin/
│   ├── plugin.json          # name, version, license, repository, keywords
│   └── marketplace.json
├── skills/
│   ├── orchestrate/SKILL.md
│   └── config/SKILL.md
├── agents/                  # 9 workers (see Workers)
├── hooks/hooks.json         # enforcement guards (PreToolUse)
├── scripts/
│   ├── guard.py             # hook implementation
│   └── validate.sh          # claude plugin validate --strict + contract checks
├── schemas/config.schema.json
├── .github/workflows/ci.yml # validate on push/PR
├── .github/ISSUE_TEMPLATE/  # bug + feature templates
├── README.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, CHANGELOG.md
├── docs/ROADMAP.md          # v2 items
└── LICENSE                  # MIT
```

## Upstream dependency: sf-skills (probe, don't assume)

The official skills live at `github.com/forcedotcom/sf-skills`, installed with `npx skills add forcedotcom/sf-skills` (a portable Agent Skills library, NOT a marketplace plugin). Upstream renames/removes skills without stability guarantees, so nothing hardcodes a single name. Instead, every capability has a **probe list** of candidate skill names (current upstream name first, legacy name second):

| Capability | Probe list |
|---|---|
| apex | `platform-apex-generate`, `generating-apex` |
| lwc | `experience-lwc-generate`, `generating-lwc-components` |
| apex-test-gen | `platform-apex-test-generate`, `generating-apex-test` |
| apex-test-run | `platform-apex-test-run`, `running-apex-tests` |
| soql | `platform-soql-query`, `querying-soql` |
| data | `platform-data-manage`, `handling-sf-data` |
| debug-logs | `platform-apex-logs-debug`, `debugging-apex-logs` |
| deploy | `platform-metadata-deploy`, `deploying-metadata` |
| object / field / validation-rule / permset / flexipage | `generating-custom-object`, `generating-custom-field`, `generating-validation-rule`, `generating-permission-set`, `generating-flexipage` + any `platform-metadata-*` successors found in the available list |
| flow | `automation-flow-generate`, `generating-flow` |

**Startup capability check** covers ALL capabilities above (including every metadata one) and, for `flow`, additionally verifies the Salesforce DX MCP server's metadata tools are available (the upstream Flow skill mandates an `execute_metadata_action`-style MCP tool and forbids hand-written Flow XML). Each capability resolves to **supported** (skill found), **degraded** (missing skill; cheat-sheet fallback exists), or **blocked** (missing skill AND no safe fallback — flow, deploy, complex metadata). The orchestrator reports the matrix to the user at startup and refuses to dispatch blocked capabilities.

**Skill-vs-contract precedence:** when a loaded skill's workflow conflicts with the worker's plan/contract (e.g. the upstream Apex skill generates tests itself), the plan/contract wins on scope and file boundaries — with one accommodation: if the Apex skill generates tests for the unit's code, the apex worker owns them, and the orchestrator must not schedule a separate test unit for the same code.

## Orchestrate skill

### Generic core

1. **Intake & restructure** — collect all tasks verbatim; group related tasks into work units; **split mixed-discipline units along ownership boundaries** (no "dominant worker" routing); split oversized units; order into dependency waves; no file collisions within a wave; user checkpoint before wave 1 unless autonomous.
2. **Track + run manifest** — task list in-session AND a persisted journal `.claude/sf-orchestrator-run.json`: per unit — id, worker, model, status, baseline SHA, owned files, attempt count, report digest. Written after every dispatch/completion; an interrupted run resumes from the manifest (completed units are not re-dispatched).
3. **Plan per unit** — exact files (the unit's **owned-file list**), exact interfaces, acceptance criteria, gotchas, do-not-touch. Mapper-first: sf-mapper verifies every schema/metadata assumption before a plan is final. Conventions hook: subagents receive the project's CLAUDE.md automatically, so do NOT re-paste it — inline only task-relevant gotchas that CLAUDE.md does not state (memory lessons, discovered traps).
4. **Dispatch** — HARD RULE: every Agent call sets `subagent_type` to the worker's agent name AND an explicit `model` from config (enforced by the plugin hook, which rejects `sf-*` dispatches without a model). Warn at startup if `CLAUDE_CODE_SUBAGENT_MODEL` is set (it outranks per-call models). Never fork. Concurrency: at most `limits.maxConcurrent` (default 4) workers in flight. **Serialize org-mutating units** (deploy, data mutations) — never two in flight against the same org. Re-anchor at every wave boundary: re-read config and restate the hard rules before dispatching the wave.
5. **Verify per unit + typed failures** — check the report against acceptance criteria. Classify failures before reacting: `plan-defect` (fix the plan, redispatch), `environment` (auth/org/CLI missing — surface to user, do not retry), `flaky` (one retry, same tier), `capability-gap` (skill/tool missing — mark blocked, report). Max `limits.maxAttempts` (default 2) per unit at base tier, then escalate to `models.escalation`; a failure at escalation blocks the unit and reports. Redispatch of org-mutating units must state what the prior attempt already changed (idempotency note).
6. **Final review** — per unit: dispatch sf-reviewer with the unit's plan, baseline SHA, and owned-file list; reviewers take an **adversarial refute stance** (try to disprove the worker's claims; uncertain = fail). Then a **completeness critic** pass: one reviewer asks "what did the original request ask for that no unit delivered?" The orchestrator personally adjudicates only the original-requirements diff and cross-unit integration, then reports: what was done, by which worker/tier, deviations, anything blocked.
7. **Capture lessons** — persist new gotchas to memory where available.

Context conservation: the orchestrator never reads implementation files itself; sf-mapper explores, reviewers verify, the orchestrator consumes summaries. Workers return compact reports only. If the whole request is one small unit, say orchestration is overhead and offer direct execution.

### Salesforce layer

- **Startup, in order:** capability check (matrix above) → config load + JSON Schema validation → `CLAUDE_CODE_SUBAGENT_MODEL` warning → **target-org resolution**: ask/confirm the target org alias once per session and record it in the manifest; support **repo-only mode** (no org available — mapper works from local metadata files only, org-dependent capabilities marked blocked).
- **Routing table** (task type → worker): Apex code → sf-apex-worker; LWC → sf-lwc-worker; Apex tests → sf-test-worker; data seeding/queries → sf-data-worker; log analysis → sf-debug-worker; objects/fields/VRs/permsets/flexipages/flows → sf-metadata-worker; retrieve/diff/deploy → sf-deploy-worker (gated); read-only exploration → sf-mapper; review → sf-reviewer. Mixed units are split, not merged.
- **Deploy gating:** sf-deploy-worker dispatches only if `deployWorker.enabled` is true AND the user confirmed org + component scope this session. Confirmation is recorded by writing `.claude/sf-orchestrator-approval.json` (`{"org": "<alias>", "scope": ["<components>"], "grantedAt": "<iso>"}`); the plugin hook blocks deploy/destructive commands unless a fresh approval file matches. Applies even in autonomous mode.

## Workers

Nine agents. Common structure: frontmatter (`name`, `description`, `tools` — never `model`); a role intro; a **fallback cheat-sheet** (original, generic best practices — used only when the capability is degraded, always flagged `fallback: true` in the report; blocked capabilities are refused, not faked); and the shared operating contract: skill probe-and-load FIRST (try each name in the capability's probe list), precedence rule, blocked-worker protocol (stop and report instead of improvising), compact report (`skills_loaded`, `files_changed`, `checks_run`, `deviations`).

| Agent | Capabilities (probe lists above) | Tools |
|---|---|---|
| sf-apex-worker | apex, soql | Read, Write, Edit, Grep, Glob, Bash, Skill |
| sf-lwc-worker | lwc | Read, Write, Edit, Grep, Glob, Bash, Skill |
| sf-test-worker | apex-test-gen, apex-test-run | Read, Write, Edit, Grep, Glob, Bash, Skill |
| sf-data-worker | data, soql | Read, Write, Grep, Glob, Bash, Skill |
| sf-debug-worker | debug-logs | Read, Grep, Glob, Bash, Skill |
| sf-metadata-worker | object, field, validation-rule, permset, flexipage, flow | Read, Write, Edit, Grep, Glob, Skill, ToolSearch + Salesforce DX MCP metadata tools (required by the Flow skill) |
| sf-deploy-worker | deploy | Read, Grep, Glob, Bash, Skill |
| sf-mapper | soql (read-only explorer) | Read, Grep, Glob, Bash, Skill |
| sf-reviewer | apex-test-run (+ domain checks) | Read, Grep, Glob, Bash, Skill |

- **sf-deploy-worker** adds a non-negotiable safety section: scoped deploys only, named org only, validate/preview first, stop on unexpected deletions, production only with explicit plan-stated user confirmation.
- **sf-mapper** is read-only by contract (Bash for `sf sobject describe` / `sf data query` / `sf org list metadata` only) — and its FLS answers must state their limits: permission-set grep shows permset grants only; profiles, permission set groups, and muting are not covered — say so rather than claiming completeness.
- **sf-reviewer** receives plan + baseline SHA + owned-file list; diffs `git diff <baseline> -- <owned files>`; refute stance; fails on unplanned file changes within its unit's scope; applies a **domain validation matrix**: Apex (loops/bulk/asserts), LWC (meta/wire/Jest), metadata (FLS entries for new fields), data (org + scope of mutations), deploy (scope match). Verdict report: `verdict`, `plan_conformance` (per requirement, with evidence), `checks_rerun`, `discrepancies`.

### Enforcement guards (hooks) — honest threat model

Prompt instructions alone are not enforcement. The plugin ships a `PreToolUse` hook (`hooks/hooks.json` → `scripts/guard.py`) that **hard-blocks**:

1. Any `Agent` call with `subagent_type` starting `sf-` and no `model` parameter.
2. Any `Bash` command matching deploy/destructive patterns (`sf project deploy`, `sfdx force:source:deploy`, `sf data delete`, `sf org delete`) unless `.claude/sf-orchestrator-approval.json` exists, is <60 minutes old, and names the target org in the command.

Everything else (mapper read-only-ness, file boundaries) remains prompt-level; the README states this plainly so users don't mistake conventions for sandboxing.

## Config

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

Loader rules (deterministic): missing file → defaults; malformed JSON → stop and tell the user (never guess); unknown keys → warn and ignore; invalid model values → error naming the key; defaults merge per-key. `effort` is reserved: per-dispatch reasoning-effort control, applied only where the harness supports it (documented as inert today in Claude Code's Agent tool).

**External executors** (e.g. a local Codex CLI as a mid-tier): shipped **disabled and empty** in v1. When configured, the contract is argv-safe (executable + fixed argument array from an allowlist — never a shell-interpolated string), requires a one-time user trust confirmation per project, and has a timeout. The orchestrate skill treats a configured executor as a tier between default and escalation; on any executor error it falls back to the escalation model.

## OSS readiness

- `plugin.json` includes `license`, `repository`, `homepage`, `keywords`, `displayName`; marketplace.json has a top-level description. Semver + CHANGELOG.md; version bumps on every release.
- README: independence disclaimer (top), what it does (token economics + workflow diagram), prerequisites with versions (Claude Code, Node/npx, Salesforce CLI + authenticated org, `forcedotcom/sf-skills` via `npx skills add`, Salesforce DX MCP server for Flow work), install, usage, worker table, config reference, capability matrix + fallback semantics, safety section (what is enforced by hooks vs prompt-level; deploy gating; token-cost warning — fan-out multiplies tokens), bring-your-own-conventions, supported platforms (macOS/Linux; Windows untested).
- CONTRIBUTING.md, CODE_OF_CONDUCT.md (Contributor Covenant), SECURITY.md (private disclosure path), issue/PR templates.
- CI: GitHub Actions running `scripts/validate.sh` (which wraps `claude plugin validate . --strict` when available plus contract checks) including **negative fixtures**: agent with `model` in frontmatter must fail; deploy command without approval file must be blocked by guard.py; malformed config must be rejected.
- Provenance: all content original to this repo's author; no Salesforce skill text, no internal documents. Public docs contain no local paths, machine names, or client project names.

## Migration (local, after smoke test)

Back up `~/.claude/skills/orchestrator-mode/` to `~/.claude/skills-backup/` (do not delete), install the plugin from the local clone, smoke test in a real project, and only then remove the backup if desired.

## Roadmap (v2 — documented in docs/ROADMAP.md, not built now)

Cost/quality benchmarks vs direct execution; local opt-in telemetry (tokens, retries, fallback usage); worktree-backed parallel execution with controlled merge; expanded safe executor adapters; richer FLS analysis (profiles, PSGs, effective access).

## Acceptance criteria

- `scripts/validate.sh` passes; CI green; negative fixtures fail as designed.
- Fresh-machine path works: `npx skills add forcedotcom/sf-skills` + plugin install → capability check reports all capabilities supported under CURRENT upstream names.
- With sf-skills absent, capabilities report degraded/blocked correctly; degraded workers flag `fallback: true`; blocked capabilities are refused with an explanation.
- Hook blocks: `sf-*` dispatch without model; deploy command without fresh matching approval file.
- Flow unit end-to-end: metadata worker loads the Flow skill and reaches the MCP metadata tools.
- Config loader behaves per the deterministic rules; `/sf-orchestrator:config` creates/edits the file against the schema.
- Interrupted run resumes from `.claude/sf-orchestrator-run.json` without re-dispatching completed units.
- Repo contains no internal-guideline content, no copied skill text, no local paths or client names in public docs.
