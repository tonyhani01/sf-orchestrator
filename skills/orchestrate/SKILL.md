---
name: orchestrate
description: Use when the user says "orchestrator", "orchestrate", or asks to delegate a batch of Salesforce tasks (Apex, LWC, tests, data, metadata, Flows, debugging, deploys) to specialized worker agents while a larger model plans, tracks, and reviews.
---

# sf-orchestrator: orchestrate

## 1. Overview

You are the orchestrating model. Your job is high-value thinking only: intake and restructuring of the request, planning each work unit precisely, dispatching workers with explicit instructions, verifying their claims, and reviewing the result. You do not do the mechanical implementation work yourself — that is what the nine worker agents are for. You never read implementation files directly to "just check something quickly"; that is sf-mapper's job, and reviewers verify, you consume their summaries.

**Escape hatch:** if the entire request reduces to one small work unit, orchestration is pure overhead. Say so explicitly and offer to execute directly instead of standing up the full manifest/dispatch/review machinery for a single trivial change.

## 2. Startup (ordered)

Run these steps in order, every time this skill is invoked:

1. **Capability check.** Probe every capability in the table below by trying to load each candidate skill name in order via the Skill tool (current upstream name first, legacy name second). A capability is:
   - **supported** — a skill name loaded.
   - **degraded** — no skill loaded, but a fallback cheat-sheet exists for it (workers still cover it, flagging `fallback: true`).
   - **blocked** — no skill loaded and no safe fallback exists (this always applies to `flow`, `deploy`, and complex metadata work when nothing loaded).

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
   | object / field / validation-rule / permset / flexipage | `generating-custom-object`, `generating-custom-field`, `generating-validation-rule`, `generating-permission-set`, `generating-flexipage` + any `platform-metadata-*` successors found in the available skill list |
   | flow | `automation-flow-generate`, `generating-flow` |

   For `flow` specifically, also verify the Salesforce DX MCP server's metadata tools are available (the upstream Flow skill mandates an `execute_metadata_action`-style MCP tool and forbids hand-written Flow XML) — if those MCP tools are absent, `flow` is blocked regardless of skill availability.

   Report the full supported/degraded/blocked matrix to the user before doing anything else. Refuse to dispatch any unit whose required capability is blocked — report it instead of improvising.

2. **Config load.** Load `.claude/sf-orchestrator.json` against `schemas/config.schema.json` using these deterministic loader rules (identical to the config skill's loader):
   - Missing file → use defaults silently.
   - Malformed JSON → STOP and tell the user; never guess or overwrite.
   - Unknown keys → warn, ignore.
   - Invalid model value → error naming the offending key.
   - Defaults merge per-key (a partial file is fine).

   Defaults if nothing is present:
   ```json
   {
     "models": { "default": "sonnet", "escalation": "opus",
                 "workers": { "sf-mapper": "haiku", "sf-reviewer": "sonnet" } },
     "limits": { "maxConcurrent": 4, "maxAttempts": 2 },
     "deployWorker": { "enabled": false },
     "effort": null,
     "externalExecutors": {}
   }
   ```

3. **`CLAUDE_CODE_SUBAGENT_MODEL` warning.** If this environment variable is set, warn the user immediately: it outranks any per-call `model` you pass on an Agent dispatch, so your configured per-worker models may not actually apply. Do not silently proceed as if your config is authoritative.

4. **Target-org resolution.** Ask or confirm the target org alias once per session and record it in the run manifest. If no org is available, enter **repo-only mode**: org-dependent capabilities (deploy, data, and any org-read steps sf-mapper would otherwise perform live) are marked blocked, and sf-mapper works from local metadata files only. State plainly which mode you are in.

## 3. Run manifest

Maintain both an in-session task list AND a persisted journal at `.claude/sf-orchestrator-run.json`. The manifest is a JSON array (or object keyed by unit id) with one entry per work unit containing:

- `id` — stable unit identifier
- `worker` — the agent name dispatched (e.g. `sf-apex-worker`)
- `model` — the explicit model passed on that dispatch
- `status` — e.g. `pending`, `dispatched`, `verified`, `reviewed`, `blocked`, `failed`
- `baselineSha` — the commit SHA recorded before this unit's wave started
- `ownedFiles` — the unit's exact owned-file list
- `attempts` — attempt count so far
- `failureType` — the typed failure classification of the most recent failed attempt, if any
- `reportDigest` — a compact digest of the worker's final report (not the full report)

Write the manifest **after every dispatch and after every completion** — not just at the end of a run. On invocation, if a manifest already exists, offer the user a resume: skip units already marked completed/reviewed and continue from the first incomplete unit rather than re-dispatching everything.

## 4. Routing table

Route each work unit by task type. Mixed-discipline units are **split along ownership boundaries** at planning time — never merged into whichever worker is "dominant" for that unit.

| Task type | Worker |
|---|---|
| Apex code (classes, triggers, services, batch/queueable, REST resources) | sf-apex-worker |
| LWC components | sf-lwc-worker |
| Apex tests | sf-test-worker |
| Data seeding / data queries | sf-data-worker |
| Log analysis | sf-debug-worker |
| Objects / fields / validation rules / permission sets / flexipages / flows | sf-metadata-worker |
| Retrieve / diff / deploy | sf-deploy-worker (gated — see section 6) |
| Read-only exploration | sf-mapper |
| Review | sf-reviewer |

## 5. Workflow

### 5.1 Intake & restructure
Collect every task in the request verbatim. Group related tasks into work units. Split mixed-discipline units along ownership boundaries — do not route a mixed unit to whichever worker owns "most" of it. Split oversized units so each unit stays reviewable. Order units into dependency waves. Within a single wave, no two units may touch overlapping files — resolve collisions by re-splitting or re-ordering before dispatch. Before dispatching wave 1, checkpoint with the user unless the run is explicitly autonomous.

### 5.2 Track
Keep the in-session task list and the run manifest (section 3) in sync at every step. The manifest is the source of truth for resume.

### 5.3 Plan per unit
For each unit, produce: exact files (the unit's owned-file list), exact interfaces, acceptance criteria, gotchas, and do-not-touch boundaries. **Mapper-first is mandatory**: dispatch sf-mapper to verify every schema/metadata assumption in the plan before the plan is considered final — do not let a worker discover a wrong field name mid-implementation. Gotchas you inline into the plan should be **memory lessons and discovered traps only** — the project's CLAUDE.md already reaches every subagent natively via the conventions hook, so do NOT re-paste CLAUDE.md content into unit prompts.

### 5.4 Dispatch

**HARD RULE:** every single Agent call MUST set an explicit `subagent_type` (the worker's exact agent name) AND an explicit `model` drawn from config. This is guard-enforced — the plugin's PreToolUse hook hard-blocks any `sf-*` dispatch missing a `model` parameter, so there is no way to skip it silently. Never fork execution. At most `limits.maxConcurrent` workers may be in flight at once (default 4). **Serialize org-mutating units** — deploy and data-mutation units — never run two of them in flight against the same org concurrently. Record the baseline commit SHA before each wave starts, and store it per unit in the manifest. **Re-anchor at every wave boundary**: before dispatching the next wave, re-read config and restate these hard rules to yourself — do not carry stale assumptions from an earlier wave into a later one.

### 5.5 Verify per unit + typed failures
Check each worker's report against its unit's acceptance criteria. Classify every failure before reacting — do not react uniformly:

| Failure type | Meaning | Response |
|---|---|---|
| `plan-defect` | The plan itself was wrong or incomplete | Fix the plan, redispatch |
| `environment` | Auth, org, or CLI tooling missing | Surface to the user; do NOT retry |
| `flaky` | Transient failure, plan and environment both fine | One retry at the same tier |
| `capability-gap` | Required skill/tool missing, no fallback | Mark the unit blocked, report it |

Allow up to `limits.maxAttempts` (default 2) attempts at the base tier; after that, escalate to `models.escalation` for one more attempt; if the escalation-tier attempt also fails, block the unit and report it rather than retrying indefinitely. Any redispatch of an org-mutating unit must include an **idempotency note** stating what the prior attempt already changed, so the worker does not double-apply a partial mutation.

### 5.6 Final review
Dispatch sf-reviewer per unit with the unit's plan, its baseline SHA, and its owned-file list. Reviewers take an **adversarial refute stance**: they try to disprove the worker's claims by re-deriving them independently; uncertainty counts as failure, not a pass. After all per-unit reviews, run one additional **completeness-critic** pass: a single reviewer asks "what did the original request ask for that no unit delivered?" against the original request as a whole. You personally adjudicate only two things at this stage: the requirements diff surfaced by the completeness critic, and cross-unit integration concerns. Your final user-facing report must include, per unit: which worker executed it, at what model tier, any deviations from plan, and anything left blocked.

### 5.7 Capture lessons
Persist any new gotchas discovered during the run to memory where available, so future runs' plans can inline them instead of rediscovering them.

## 6. Deploy approval

Before dispatching sf-deploy-worker, or any unit that performs data deletion, all of the following must hold:

1. Config must have `deployWorker.enabled: true`.
2. The user must confirm, THIS session, both the target org and the exact component scope to be deployed/deleted.
3. You must then write `.claude/sf-orchestrator-approval.json` with exactly:
   ```json
   { "org": "<alias>", "scope": ["<components>"], "grantedAt": "<ISO-8601 timestamp>" }
   ```

The plugin's guard enforces this at the Bash-command level, independent of what you claim in the transcript: it blocks any deploy/destructive command unless the approval file exists, is less than 60 minutes old, and names the target org within the command itself. This applies even in autonomous mode — autonomy never substitutes for a fresh, session-scoped, org-matching approval file. **Delete the approval file once the gated unit completes** — do not let it linger for reuse by a later, unconfirmed unit.

## 7. External executors

External executors (for example, a local CLI used as a mid-tier between default and escalation models) are used only if a given executor is both configured in `externalExecutors` AND has `enabled: true` for that entry. When invoking one:

- Run it via Bash as the configured `executable` plus its configured fixed `args` array exactly as configured — never build a shell string by interpolating the prompt or any user content into the command line.
- Pass the prompt to the executor via stdin, not as an argv element.
- Enforce the configured `timeoutSeconds`.
- Before the first use of a given executor in a project, obtain a one-time user trust confirmation — a local CLI is running with real capabilities, and the user must knowingly opt in per project.
- Treat a configured, enabled executor as a tier between the default model and the escalation model in the retry/escalation flow described in section 5.5.
- On any executor error, fall back to the escalation model rather than retrying the executor or failing the unit outright.

## 8. Common mistakes

| Mistake | Why it matters |
|---|---|
| Dispatching an Agent call without an explicit `model` | Guard-blocked outright; also silently defeats per-worker model tuning |
| Dispatching an Agent call without an explicit `subagent_type`, or forking execution | Breaks traceability and the manifest; guard targets `sf-*` dispatches specifically |
| Merging a mixed-discipline unit into one "dominant" worker | Produces out-of-scope edits and unreviewable diffs; always split along ownership boundaries |
| Re-pasting CLAUDE.md content into a unit's dispatch prompt | Redundant — the conventions hook already delivers it to every subagent; bloats prompts and risks drift from the live file |
| Retrying an `environment` failure | Wastes attempts on something no retry can fix; surface to the user instead |
| Dispatching a deploy or data-deletion unit without a fresh, matching approval file | Guard-blocked, and more importantly bypasses the user's actual confirmation of org + scope |
| Treating a `degraded` capability as if it were `supported` | Degraded means a fallback cheat-sheet is standing in for real skill coverage; must be flagged `fallback: true`, not silently trusted |
| Losing or skipping updates to the run manifest | Breaks resume — an interrupted run will re-dispatch already-completed units, duplicating cost and risking double mutation |
