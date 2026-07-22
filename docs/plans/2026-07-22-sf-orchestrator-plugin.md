# sf-orchestrator Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the open-source `sf-orchestrator` Claude Code plugin: 2 skills (orchestrate, config) + 9 Salesforce worker agents + config schema + README, per `docs/DESIGN.md`.

**Architecture:** A plugin repo (`.claude-plugin/` manifest, `skills/`, `agents/`). Worker agents are thin wrappers that load official Salesforce skills at runtime and carry an original cheat-sheet fallback. The orchestrate skill routes work units to workers with explicit models from `.claude/sf-orchestrator.json`. Validation is a shell script checking JSON validity and agent/skill frontmatter.

**Tech Stack:** Markdown skills/agents, JSON manifests, bash + python3 (stdlib) validation script. No runtime dependencies.

## Global Constraints

- Repo root: `/Users/tonyhani/Desktop/VS Code Projects/sf-orchestrator` (all paths below relative to it).
- License: MIT. Plugin name: `sf-orchestrator`.
- NO content copied from Salesforce's skills, and NOTHING from any internal guideline document (e.g. sfdc-dev). Cheat-sheets must be original generic best practices.
- Agent frontmatter: `name`, `description`, `tools` only — **never `model`** (models come from orchestrator dispatch).
- Every agent prompt must include, verbatim in spirit: skill-load mandate (first instruction), cheat-sheet fallback rule, compact-report contract, blocked-worker protocol.
- Commit after every task with a conventional-commit message ending in `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Scaffold + validation script

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `LICENSE`, `scripts/validate.sh`

**Interfaces:**
- Produces: `bash scripts/validate.sh` → exits 0 printing `PASS` when all JSON parses and every `agents/*.md` + `skills/*/SKILL.md` has valid frontmatter (`name`, `description`; agents additionally `tools` and NO `model`). Later tasks run this as their test.

- [ ] **Step 1: Write `scripts/validate.sh` (the failing test)**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
fail=0

for j in .claude-plugin/plugin.json .claude-plugin/marketplace.json; do
  python3 -m json.tool "$j" >/dev/null 2>&1 || { echo "FAIL: invalid JSON $j"; fail=1; }
done

python3 - <<'EOF' || fail=1
import glob, re, sys
def fm(path):
    text = open(path).read()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return dict(re.findall(r'^([a-zA-Z-]+):\s*(.*)$', m.group(1), re.M)) if m else None

ok = True
agents = glob.glob('agents/*.md')
skills = glob.glob('skills/*/SKILL.md')
if len(agents) != 9: print(f'FAIL: expected 9 agents, found {len(agents)}'); ok = False
if len(skills) != 2: print(f'FAIL: expected 2 skills, found {len(skills)}'); ok = False
for p in agents:
    f = fm(p)
    if not f or not f.get('name') or not f.get('description') or not f.get('tools'):
        print(f'FAIL: {p} missing frontmatter name/description/tools'); ok = False
    if f and 'model' in f:
        print(f'FAIL: {p} must not set model in frontmatter'); ok = False
for p in skills:
    f = fm(p)
    if not f or not f.get('name') or not f.get('description'):
        print(f'FAIL: {p} missing frontmatter name/description'); ok = False
sys.exit(0 if ok else 1)
EOF

[ "$fail" -eq 0 ] && echo PASS || { echo FAIL; exit 1; }
```

- [ ] **Step 2: Run it to verify it fails** — `bash scripts/validate.sh` → Expected: `FAIL` (no JSON files, 0 agents, 0 skills).

- [ ] **Step 3: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "sf-orchestrator",
  "version": "0.1.0",
  "description": "Salesforce development orchestrator: a large model plans, routes, and reviews while cheap specialized workers (Apex, LWC, tests, data, debug, metadata, deploy) execute using the official Salesforce skills.",
  "author": { "name": "Antony Hani" }
}
```

- [ ] **Step 4: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "sf-orchestrator-marketplace",
  "owner": { "name": "Antony Hani" },
  "plugins": [
    {
      "name": "sf-orchestrator",
      "source": "./",
      "description": "Salesforce development orchestrator with specialized worker agents."
    }
  ]
}
```

- [ ] **Step 5: Write `LICENSE`** — standard MIT text, copyright `2026 Antony Hani`.

- [ ] **Step 6: Run `bash scripts/validate.sh`** — still `FAIL` (agents/skills missing) but JSON checks must produce no `invalid JSON` lines.

- [ ] **Step 7: Commit** — `chore: plugin scaffold, manifests, validation script`

---

### Task 2: Config skill + config schema

**Files:**
- Create: `skills/config/SKILL.md`

**Interfaces:**
- Produces: the canonical config file contract used by the orchestrate skill and README: path `.claude/sf-orchestrator.json` in the USER'S project, schema exactly as in the code block below.

- [ ] **Step 1: Write `skills/config/SKILL.md`**

````markdown
---
name: config
description: Use when the user wants to configure sf-orchestrator - set worker models, escalation tier, enable/disable the deploy worker, or add an external executor. Creates or edits .claude/sf-orchestrator.json in the current project.
---

# sf-orchestrator: config

Interactively create or edit `.claude/sf-orchestrator.json` in the current project root.

## Schema (canonical)

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

- `models.default` — model for any worker without an override. Allowed: `haiku`, `sonnet`, `opus`.
- `models.escalation` — tier used after a unit fails twice.
- `models.workers` — per-agent overrides keyed by agent name (`sf-apex-worker`, `sf-lwc-worker`, `sf-test-worker`, `sf-data-worker`, `sf-debug-worker`, `sf-metadata-worker`, `sf-deploy-worker`, `sf-mapper`, `sf-reviewer`).
- `deployWorker.enabled` — when false the orchestrator must never dispatch sf-deploy-worker.
- `externalExecutors` — optional CLI executors (run via Bash) usable as a tier between default and escalation. Disabled by default; machine-specific.

## Workflow

1. Read `.claude/sf-orchestrator.json` if it exists; otherwise start from the schema above.
2. Ask the user, one question at a time (AskUserQuestion where available):
   - Default worker model? (sonnet recommended)
   - Escalation model? (opus recommended)
   - Any per-worker overrides? (recommend sf-mapper: haiku)
   - Enable the deploy worker? (default NO; explain it lets an agent deploy to a Salesforce org)
   - Add an external executor CLI? (default no)
3. Write the merged result to `.claude/sf-orchestrator.json` (create `.claude/` if needed).
4. Show the final JSON and remind the user the orchestrator reads it at the start of every run.

Never write any key not in the schema. Never set a model value other than haiku/sonnet/opus.
````

- [ ] **Step 2: Run `bash scripts/validate.sh`** — Expected: still FAIL overall (agents missing) but no `skills/` frontmatter failures and skill count failure now says `found 1`.

- [ ] **Step 3: Commit** — `feat: config skill with canonical config schema`

---

### Task 3: Shared agent contract + code workers (apex, lwc, test)

**Files:**
- Create: `agents/sf-apex-worker.md`, `agents/sf-lwc-worker.md`, `agents/sf-test-worker.md`

**Interfaces:**
- Produces: the **shared contract block** (below) reused verbatim in every agent; agent names as listed (orchestrate skill routes by these names).

**Shared contract block** — include at the end of EVERY agent prompt in Tasks 3–5, replacing `<SKILLS>` with that agent's skill list:

```markdown
## Operating contract

**Skill loading (do this FIRST):** Before any other action, invoke via the Skill tool: <SKILLS>. If a skill is unavailable, proceed using the Fallback cheat-sheet below and flag `fallback: true` in your report.

**Blocked-worker protocol:** If the plan you were given is wrong, impossible, contradicts the codebase, or requires you to make an assumption — STOP. Do not improvise. Report the problem and wait for a corrected plan.

**Final report (compact, structured — no code dumps, no diffs):**
- `skills_loaded`: which skills loaded, or `fallback: true`
- `files_changed`: paths + one-line summary each
- `checks_run`: each acceptance check from the plan + its actual output/result
- `deviations`: anything done differently than planned, or `none`
```

- [ ] **Step 1: Write `agents/sf-apex-worker.md`**

````markdown
---
name: sf-apex-worker
description: Implements Apex work units dispatched by the sf-orchestrator - classes, triggers, services, selectors, batch/queueable/schedulable jobs, REST resources, and SOQL inside Apex. Executes an explicit plan; does not design solutions.
tools: Read, Write, Edit, Grep, Glob, Bash, Skill
---

You are a Salesforce Apex implementation worker. You execute exactly one work unit from a plan written by an orchestrator. The plan lists exact files, exact interfaces, and acceptance criteria — follow it literally.

## Fallback cheat-sheet (only if skills fail to load)

- Bulkify everything: methods take collections; never assume one record.
- No SOQL and no DML inside loops; query into Maps keyed by Id first, collect records and do one DML after the loop.
- One trigger per object, no logic in the trigger body — delegate to a handler class.
- Respect governor limits (100 SOQL / 150 DML / 50k rows per transaction).
- Wrap DML in try/catch; never swallow exceptions silently.
- Prefer `with sharing` unless the plan states otherwise; use bind variables in all SOQL (no string-concatenated queries).

## Operating contract

**Skill loading (do this FIRST):** Before any other action, invoke via the Skill tool: `generating-apex`, and `querying-soql` if the unit involves query design. If a skill is unavailable, proceed using the Fallback cheat-sheet above and flag `fallback: true` in your report.

**Blocked-worker protocol:** If the plan you were given is wrong, impossible, contradicts the codebase, or requires you to make an assumption — STOP. Do not improvise. Report the problem and wait for a corrected plan.

**Final report (compact, structured — no code dumps, no diffs):**
- `skills_loaded`: which skills loaded, or `fallback: true`
- `files_changed`: paths + one-line summary each
- `checks_run`: each acceptance check from the plan + its actual output/result
- `deviations`: anything done differently than planned, or `none`
````

- [ ] **Step 2: Write `agents/sf-lwc-worker.md`** — same structure. Frontmatter: `name: sf-lwc-worker`; `description: Implements Lightning Web Component work units dispatched by the sf-orchestrator - components, templates, CSS, js-meta.xml, wire adapters, and Jest tests. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Edit, Grep, Glob, Bash, Skill`. Intro sentence adapted to LWC. Skills in contract: `generating-lwc-components`. Fallback cheat-sheet:

```markdown
- One component per folder: `name.js`, `name.html`, `name.css`, `name.js-meta.xml` (meta must set apiVersion and isExposed/targets).
- Use `@wire` for reactive reads, imperative Apex for user-action writes; never mix cached wire reads with post-DML re-reads.
- `@api` properties are set by parents AFTER construction — never read them in the constructor.
- No direct DOM manipulation outside the component's own template; query with `this.template.querySelector`.
- Handle Apex errors: catch, extract `error.body.message`, surface via toast or inline text — never fail silently.
- Jest: mock all `@salesforce/*` imports; flush promises before asserting DOM; one behavior per test.
```

- [ ] **Step 3: Write `agents/sf-test-worker.md`** — Frontmatter: `name: sf-test-worker`; `description: Writes and fixes Apex test classes and runs test/coverage cycles for work units dispatched by the sf-orchestrator. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Edit, Grep, Glob, Bash, Skill`. Skills in contract: `generating-apex-test`, `running-apex-tests`. Fallback cheat-sheet:

```markdown
- `@isTest` classes; create ALL data in the test (factory pattern); never `seeAllData=true`.
- Test bulk paths with 200+ records, not just single records.
- `Test.startTest()/stopTest()` around the action under test to reset limits and flush async.
- Assert outcomes with messages (`Assert.areEqual(expected, actual, 'why')`) — a test without asserts is not a test.
- Cover positive, negative (expected exception), and permission paths (`System.runAs`).
- Run tests via `sf apex run test --tests <Class> --result-format human --synchronous` and read actual failures before editing.
```

- [ ] **Step 4: Run `bash scripts/validate.sh`** — Expected: agent count failure now `found 3`, no frontmatter failures.

- [ ] **Step 5: Commit** — `feat: apex, lwc, and test worker agents with shared contract`

---

### Task 4: data, debug, metadata workers

**Files:**
- Create: `agents/sf-data-worker.md`, `agents/sf-debug-worker.md`, `agents/sf-metadata-worker.md`

Same structure and shared contract block as Task 3 (repeat it verbatim per agent with that agent's skills).

- [ ] **Step 1: Write `agents/sf-data-worker.md`** — Frontmatter: `name: sf-data-worker`; `description: Seeds, imports, exports, and queries Salesforce org data for work units dispatched by the sf-orchestrator - test data generation, bulk loads, SOQL authoring, record cleanup. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Grep, Glob, Bash, Skill`. Skills: `handling-sf-data`, `querying-soql`. Fallback cheat-sheet:

```markdown
- Always name the target org explicitly (`--target-org`) on every `sf` command; never rely on the default org.
- Prefer `sf data` commands (query/create/upsert/delete, bulk upsert for >200 rows) over anonymous Apex; use anonymous Apex only when relationships require it.
- Query before you mutate: verify record shape, record types, and required fields first.
- Use external IDs for upserts where available; never hardcode record Ids across orgs.
- Bind/escape user-provided values in SOQL; add LIMIT to exploratory queries.
- Clean up only records you created, identified by a tag field or captured Ids — never blanket-delete.
```

- [ ] **Step 2: Write `agents/sf-debug-worker.md`** — Frontmatter: `name: sf-debug-worker`; `description: Analyzes Salesforce debug logs, governor-limit failures, and stack traces for work units dispatched by the sf-orchestrator, and reports root cause with evidence. Read-mostly; does not fix code unless the plan says so.`; `tools: Read, Grep, Glob, Bash, Skill`. Skills: `debugging-apex-logs`. Fallback cheat-sheet:

```markdown
- Retrieve logs with `sf apex list log` / `sf apex get log -i <id>` against the explicit target org.
- Read the LIMIT_USAGE and EXCEPTION_THROWN lines first; the last stack frame in the user's namespace is usually the culprit.
- SOQL 101 / DML 151: count QUERY/DML entries per stack frame to find the loop; the fix is bulkification at that frame, not raising limits.
- Distinguish trigger recursion (same handler repeating) from batch/queueable chaining before blaming volume.
- Root-cause claims need evidence: quote the exact log lines in your report.
```

- [ ] **Step 3: Write `agents/sf-metadata-worker.md`** — Frontmatter: `name: sf-metadata-worker`; `description: Creates and edits declarative Salesforce metadata for work units dispatched by the sf-orchestrator - custom objects, fields, validation rules, permission sets, flows, flexipages. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Edit, Grep, Glob, Skill`. Skills: `generating-custom-object`, `generating-custom-field`, `generating-validation-rule`, `generating-permission-set`, `generating-flow`, `generating-flexipage` (load only those relevant to the unit). Fallback cheat-sheet:

```markdown
- One metadata component per file, exact suffix conventions (`.object-meta.xml`, `.field-meta.xml`, etc.) under `force-app/main/default/`.
- New custom fields ship with ZERO field-level security — every new field needs matching permission-set `fieldPermissions` entries.
- Required fields must NOT appear in permission-set fieldPermissions (access is implicit; listing them breaks deploys).
- Check existing picklist values and naming patterns in the repo before adding values or objects.
- Master-Detail requires the child to be deployable without existing data conflicts; prefer Lookup unless rollups/ownership inheritance are required.
- Validation rule formulas: test the error condition logic (rule fires when formula is TRUE).
```

- [ ] **Step 4: Run `bash scripts/validate.sh`** — Expected: `found 6` agents, no frontmatter failures.

- [ ] **Step 5: Commit** — `feat: data, debug, and metadata worker agents`

---

### Task 5: deploy worker + mapper + reviewer

**Files:**
- Create: `agents/sf-deploy-worker.md`, `agents/sf-mapper.md`, `agents/sf-reviewer.md`

Same structure and shared contract block (with agent-specific skills).

- [ ] **Step 1: Write `agents/sf-deploy-worker.md`** — Frontmatter: `name: sf-deploy-worker`; `description: Retrieves, diffs, and deploys Salesforce metadata for work units dispatched by the sf-orchestrator. Only dispatched when the deploy worker is enabled in config and the user has confirmed org and scope.`; `tools: Read, Grep, Glob, Bash, Skill`. Skills: `deploying-metadata`. Add this extra section before the contract:

```markdown
## Deploy safety (non-negotiable)

- Deploy ONLY the components named in your plan, to the org named in your plan. If either is missing, invoke the blocked-worker protocol.
- Always run a preview/validate first and report unexpected deletions or conflicts BEFORE the real deploy; if any appear, STOP and report.
- Never deploy to an org whose alias suggests production unless the plan explicitly says production and states that the user confirmed it.
```

Fallback cheat-sheet:

```markdown
- Use `sf project deploy start --source-dir <paths> --target-org <alias>`; scoped, never whole-repo, unless the plan says otherwise.
- Retrieve-and-diff before deploy: the org may have newer work; deploying a file is a full-file replace.
- On test-gate failures, report the failing tests verbatim; do not switch test levels to force a deploy through.
```

- [ ] **Step 2: Write `agents/sf-mapper.md`** — Frontmatter: `name: sf-mapper`; `description: Read-only Salesforce explorer for the sf-orchestrator. Verifies schema (objects, fields, types, picklists), FLS/permission sets, existing classes/triggers/components, and dependencies, and returns a compact factual summary for planning. Never edits anything.`; `tools: Read, Grep, Glob, Bash, Skill`. Skills: `querying-soql` (when live-org queries needed). Intro states: you are READ-ONLY; Bash is for `sf sobject describe`, `sf data query`, `sf org list metadata` and similar read commands only — never any command that mutates files or org state. Fallback cheat-sheet:

```markdown
- Verify, don't assume: confirm object/field existence and exact API names via `sf sobject describe --sobject <X> --target-org <alias>` or the repo's `*-meta.xml` files.
- Report field TYPES and picklist values exactly - plans fail on assumed types.
- For FLS questions, grep permission-set XML for the field; absence of a fieldPermissions entry means no access.
- Answer ONLY what was asked, as structured facts (name -> value); no file dumps, no speculation, and say "not found" explicitly when something does not exist.
```

- [ ] **Step 3: Write `agents/sf-reviewer.md`** — Frontmatter: `name: sf-reviewer`; `description: Read-only reviewer for the sf-orchestrator final-review step. Checks a completed work unit's diff against its plan, runs the unit's acceptance checks and tests, and returns a verdict with evidence. Never edits anything.`; `tools: Read, Grep, Glob, Bash, Skill`. Skills: `running-apex-tests` (when the unit has Apex tests). Intro: you receive a plan + a claimed-complete report; verify claims independently — read the actual diff (`git diff`), run the actual checks; workers' reports are claims, not evidence. Report format (replaces the standard files_changed report):

```markdown
**Final report:**
- `verdict`: pass | fail
- `plan_conformance`: each plan requirement -> met / not met (with file:line evidence)
- `checks_rerun`: each acceptance check + actual output
- `discrepancies`: anything the worker's report claimed that you could not reproduce
```

Fallback cheat-sheet:

```markdown
- Diff first (`git diff <base>` scoped to the unit's files), then tests; a green suite does not prove the plan was followed.
- Watch for: SOQL/DML in loops, missing FLS for new fields, tests without asserts, files touched outside the plan's list.
- Fail the unit on any unplanned file change - even a harmless-looking one.
```

- [ ] **Step 4: Run `bash scripts/validate.sh`** — Expected: `found 9` agents, both skills… still FAIL only if orchestrate skill absent (`skills found 1`).

- [ ] **Step 5: Commit** — `feat: deploy, mapper, and reviewer agents`

---

### Task 6: Orchestrate skill

**Files:**
- Create: `skills/orchestrate/SKILL.md`

**Interfaces:**
- Consumes: agent names from Tasks 3–5; config schema from Task 2.

- [ ] **Step 1: Write `skills/orchestrate/SKILL.md`** with frontmatter `name: orchestrate`, `description: Use when the user says "orchestrator", "orchestrate", or asks to delegate a batch of Salesforce tasks (Apex, LWC, tests, data, metadata, debugging, deploys) to specialized worker agents while a larger model plans, tracks, and reviews.` Body sections, in order:

  1. **Overview** — orchestrator does ONLY high-value thinking (analysis, grouping, planning, tracking, review); all implementation is delegated; if a plan isn't executable without assumptions it isn't done; if the request is one small unit, say orchestration is overhead and offer to do it directly.
  2. **Startup (mandatory, in order)** — (a) check the available-skills list for `generating-apex`, `generating-lwc-components`, `generating-apex-test`, `running-apex-tests`, `handling-sf-data`, `querying-soql`, `debugging-apex-logs`, `deploying-metadata`; if missing, warn the user that workers will run on fallback cheat-sheets and point to installing the official Salesforce skills plugin. (b) Read `.claude/sf-orchestrator.json`; if absent use defaults (default sonnet, escalation opus, sf-mapper haiku, deployWorker disabled). (c) Read the project's CLAUDE.md and note conventions to inline into worker prompts (the conventions hook).
  3. **Context conservation** — never Read whole files; dispatch sf-mapper and consume summaries; workers return compact reports only.
  4. **Routing table** — the 9-row table exactly as in `docs/DESIGN.md` (task type → agent name). Mixed units → dominant worker + instruction to load the extra skill.
  5. **Workflow steps 1–7** — Intake & restructure (group/split/waves/no file collisions/user checkpoint before wave 1 unless autonomous); Track (task list; every original task maps to a unit); Plan per unit (exact files, exact interfaces, acceptance criteria, gotchas incl. CLAUDE.md conventions, do-not-touch; mapper-first: dispatch sf-mapper to verify every schema/metadata assumption BEFORE finalizing a plan); Dispatch (**HARD RULE: every Agent call MUST set `subagent_type` to the worker's agent name AND an explicit `model` from config — an omitted model silently inherits the expensive session model; never use fork; if a dispatch went out without a model, tell the user**; parallel dispatch for independent units; deploy gating: sf-deploy-worker only if config enables it AND the user confirmed org + scope this session, even in autonomous mode); Verify per unit (check report vs acceptance criteria; on failure fix the PLAN and redispatch; after a second failure escalate to `models.escalation` or an enabled external executor); Final review (dispatch sf-reviewer per unit/wave; orchestrator personally adjudicates only the original-requirements diff and cross-unit integration; report to user: what was done, by which worker/tier, deviations); Capture lessons (write new gotchas to persistent memory where available).
  6. **External executors** — if config enables one (e.g. codex), it may be used as a mid-tier via Bash (`<command> "<prompt>"` in the target dir); on CLI error fall back to escalation model; never required.
  7. **Common mistakes table** — port all rows from the original skill: orchestrator edits files itself; vague plans; missing gotchas; skipping final review; everything to opus; task lost in regroup; orchestrator reads files; worker improvises; two workers same file same wave; lessons evaporate; **Agent call without explicit model / via fork**; dispatching sf-deploy-worker while disabled or unconfirmed.

- [ ] **Step 2: Run `bash scripts/validate.sh`** — Expected: `PASS`.

- [ ] **Step 3: Commit** — `feat: orchestrate skill with SF routing, config-driven models, deploy gating`

---

### Task 7: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`** with sections: **What it is** (token economics: expensive model plans/reviews, cheap workers execute; diagram of orchestrator → waves → workers → reviewer); **Prerequisites** (Claude Code + the official Salesforce skills plugin, with the note that without it workers degrade to built-in cheat-sheets and flag it); **Install** (`/plugin marketplace add <owner>/sf-orchestrator` then `/plugin install sf-orchestrator@sf-orchestrator-marketplace`); **Usage** (`/sf-orchestrator:orchestrate <batch of tasks>`, `/sf-orchestrator:config`); **Workers** (the 9-row table: agent, purpose, skills loaded, default model); **Configuration** (full schema from Task 2 with field docs); **Bring your own conventions** (orchestrator reads your project's CLAUDE.md and inlines relevant rules into every worker prompt); **Safety** (deploy worker disabled by default + org/scope confirmation; workers stop instead of improvising); **License** (MIT).

- [ ] **Step 2: Run `bash scripts/validate.sh`** — Expected: `PASS`.

- [ ] **Step 3: Commit** — `docs: README with install, usage, config reference`

---

### Task 8: Local install + smoke test + migration

- [ ] **Step 1: Install locally** — add the repo as a local marketplace and install the plugin (user runs `/plugin marketplace add "/Users/tonyhani/Desktop/VS Code Projects/sf-orchestrator"` then `/plugin install sf-orchestrator@sf-orchestrator-marketplace`; these are interactive CLI commands — ask the user to run them).
- [ ] **Step 2: Smoke test** — in a fresh session in the NOS Local project, run `/sf-orchestrator:config` (verify it writes `.claude/sf-orchestrator.json`), then `/sf-orchestrator:orchestrate` with a trivial 2-task request; verify: startup check runs, routing picks correct workers, every dispatch has explicit model, workers' reports include `skills_loaded`.
- [ ] **Step 3: Migration** — after a successful smoke test, delete `~/.claude/skills/orchestrator-mode/` (the plugin replaces it).
- [ ] **Step 4: Publish** — create the GitHub repo (public, MIT), push `main`. User confirms repo name/owner first.
- [ ] **Step 5: Commit any smoke-test fixes** — `fix: smoke-test findings`
