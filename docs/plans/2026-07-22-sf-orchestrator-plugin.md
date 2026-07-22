# sf-orchestrator Plugin Implementation Plan (rev 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the open-source `sf-orchestrator` Claude Code plugin per `docs/DESIGN.md` (rev 2): 2 skills, 9 agents, enforcement hooks, config schema, validation + CI, community files.

**Architecture:** Plugin repo (`.claude-plugin/` manifest, `skills/`, `agents/`, `hooks/`). Workers probe-and-load `forcedotcom/sf-skills` capabilities at runtime with per-capability fallback (supported/degraded/blocked). A PreToolUse hook hard-blocks model-less `sf-*` dispatches and unapproved deploy commands. Orchestrate skill routes split-by-discipline units with config-driven models, run manifest, typed failures, refute-stance review.

**Tech Stack:** Markdown skills/agents, JSON manifests + JSON Schema, python3 (stdlib) hook + validator, bash, GitHub Actions.

## Global Constraints

- Repo root: the `sf-orchestrator` repo (all paths relative to it). Public docs (README, community files, skill/agent bodies) must contain NO local machine paths, client project names, or internal document references.
- License MIT; plugin name `sf-orchestrator`; independence disclaimer required in README (verbatim from DESIGN.md header note).
- NO content copied from Salesforce's skills or any internal guideline document. Cheat-sheets are original generic best practices.
- Agent frontmatter: `name`, `description`, `tools` only — **never `model`**.
- Every agent carries: probe-and-load mandate, precedence rule, blocked-worker protocol, compact-report contract, fallback cheat-sheet.
- Capability probe lists are those in DESIGN.md "Upstream dependency" table — use them exactly wherever `<PROBE:x>` appears below.
- Commit after every task, conventional-commit style.

---

### Task 1: Scaffold + validator

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `LICENSE`, `scripts/validate.sh`, `scripts/contract_check.py`

**Interfaces:**
- Produces: `bash scripts/validate.sh` → `PASS`/`FAIL`; runs `claude plugin validate . --strict` when the `claude` CLI is available, then `python3 scripts/contract_check.py`. Later tasks use this as their test.

- [ ] **Step 1: Write `scripts/contract_check.py`**

```python
#!/usr/bin/env python3
"""Contract checks beyond `claude plugin validate`. Exit 0 = ok."""
import glob, json, re, sys

errors = []

def frontmatter(path):
    text = open(path).read()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None
    return dict(re.findall(r'^([A-Za-z_-]+):\s*(.*)$', m.group(1), re.M))

for j in ('.claude-plugin/plugin.json', '.claude-plugin/marketplace.json',
          'schemas/config.schema.json', 'hooks/hooks.json'):
    try:
        json.load(open(j))
    except FileNotFoundError:
        errors.append(f'missing {j}')
    except json.JSONDecodeError as e:
        errors.append(f'invalid JSON {j}: {e}')

agents = sorted(glob.glob('agents/*.md'))
skills = sorted(glob.glob('skills/*/SKILL.md'))
if len(agents) != 9:
    errors.append(f'expected 9 agents, found {len(agents)}')
if len(skills) != 2:
    errors.append(f'expected 2 skills, found {len(skills)}')

REQUIRED_AGENT_PHRASES = ['fallback: true', 'STOP', 'skills_loaded']
for p in agents:
    fm = frontmatter(p)
    body = open(p).read()
    if not fm or not fm.get('name') or not fm.get('description') or not fm.get('tools'):
        errors.append(f'{p}: frontmatter must have name/description/tools')
        continue
    if 'model' in fm:
        errors.append(f'{p}: model is forbidden in frontmatter')
    if fm['name'] != p.split('/')[-1][:-3]:
        errors.append(f'{p}: frontmatter name must match filename')
    for phrase in REQUIRED_AGENT_PHRASES:
        if phrase not in body:
            errors.append(f'{p}: missing contract phrase {phrase!r}')

for p in skills:
    fm = frontmatter(p)
    if not fm or not fm.get('name') or not fm.get('description'):
        errors.append(f'{p}: frontmatter must have name/description')

for e in errors:
    print(f'FAIL: {e}')
sys.exit(1 if errors else 0)
```

- [ ] **Step 2: Write `scripts/validate.sh`**

```bash
#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
if command -v claude >/dev/null 2>&1; then
  claude plugin validate . --strict || fail=1
else
  echo "note: claude CLI not found, skipping plugin validate"
fi
python3 scripts/contract_check.py || fail=1
[ "$fail" -eq 0 ] && echo PASS || { echo FAIL; exit 1; }
```

- [ ] **Step 3: Run `bash scripts/validate.sh`** — Expected: `FAIL` (missing manifests, 0 agents/skills).

- [ ] **Step 4: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "sf-orchestrator",
  "displayName": "SF Orchestrator",
  "version": "0.1.0",
  "description": "Independent Salesforce development orchestrator for Claude Code: a large model plans, routes, and reviews while cheap specialized workers (Apex, LWC, tests, data, debug, metadata, deploy) execute using the public forcedotcom/sf-skills library. Not affiliated with Salesforce or Anthropic.",
  "author": { "name": "Antony Hani" },
  "license": "MIT",
  "repository": "https://github.com/OWNER/sf-orchestrator",
  "homepage": "https://github.com/OWNER/sf-orchestrator#readme",
  "keywords": ["salesforce", "orchestrator", "agents", "apex", "lwc", "claude-code"]
}
```

(`OWNER` is replaced at publish time — Task 9 confirms the GitHub owner with the user; grep for `OWNER` must return nothing after that task.)

- [ ] **Step 5: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "sf-orchestrator-marketplace",
  "owner": { "name": "Antony Hani" },
  "metadata": { "description": "Marketplace for the sf-orchestrator plugin — an independent Salesforce development orchestrator for Claude Code." },
  "plugins": [
    { "name": "sf-orchestrator", "source": "./", "description": "Salesforce development orchestrator with specialized worker agents, enforcement hooks, and per-worker model config." }
  ]
}
```

- [ ] **Step 6: Write `LICENSE`** — standard MIT text, copyright `2026 Antony Hani`.

- [ ] **Step 7: Run `bash scripts/validate.sh`** — still FAIL (agents/skills/schema/hooks missing) but no manifest-JSON errors.

- [ ] **Step 8: Commit** — `chore: scaffold, manifests, validator`

---

### Task 2: Enforcement hooks + negative fixtures

**Files:**
- Create: `hooks/hooks.json`, `scripts/guard.py`, `tests/fixtures/agent_missing_model.json`, `tests/fixtures/bash_deploy_unapproved.json`, `tests/fixtures/bash_ok.json`, `tests/test_guard.sh`

**Interfaces:**
- Produces: PreToolUse guard. Blocks (exit 2 + stderr): `Agent` calls with `subagent_type` starting `sf-` and no `model`; Bash deploy/destructive commands without a fresh matching `.claude/sf-orchestrator-approval.json`. Approval file schema: `{"org": "<alias>", "scope": ["..."], "grantedAt": "<ISO-8601>"}` — written by the orchestrate skill after user confirmation (Task 7).

- [ ] **Step 1: Write `tests/test_guard.sh` (failing test)**

```bash
#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
expect() { # expect <exit-code> <fixture>
  python3 scripts/guard.py < "tests/fixtures/$2" >/dev/null 2>&1
  actual=$?
  [ "$actual" -eq "$1" ] || { echo "FAIL: $2 expected exit $1 got $actual"; fail=1; }
}
rm -f .claude/sf-orchestrator-approval.json
expect 2 agent_missing_model.json
expect 2 bash_deploy_unapproved.json
expect 0 bash_ok.json
mkdir -p .claude
python3 - <<'EOF'
import json, datetime
json.dump({"org": "my-sandbox", "scope": ["classes/Foo.cls"],
           "grantedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()},
          open('.claude/sf-orchestrator-approval.json', 'w'))
EOF
expect 0 bash_deploy_unapproved.json   # now approved: same org appears in command
python3 - <<'EOF'
import json
json.dump({"org": "my-sandbox", "scope": ["classes/Foo.cls"],
           "grantedAt": "2026-07-21T09:00:00"},
          open('.claude/sf-orchestrator-approval.json', 'w'))
EOF
expect 2 bash_deploy_unapproved.json   # naive+stale timestamp: clean block, not a crash
rm -f .claude/sf-orchestrator-approval.json
[ "$fail" -eq 0 ] && echo GUARD-PASS || { echo GUARD-FAIL; exit 1; }
```

- [ ] **Step 2: Write the fixtures**

`tests/fixtures/agent_missing_model.json`:
```json
{"tool_name": "Agent", "tool_input": {"subagent_type": "sf-apex-worker", "prompt": "x", "description": "x"}}
```
`tests/fixtures/bash_deploy_unapproved.json`:
```json
{"tool_name": "Bash", "tool_input": {"command": "sf project deploy start --source-dir force-app --target-org my-sandbox"}}
```
`tests/fixtures/bash_ok.json`:
```json
{"tool_name": "Bash", "tool_input": {"command": "sf sobject describe --sobject Account --target-org my-sandbox"}}
```

- [ ] **Step 3: Run `bash tests/test_guard.sh`** — Expected: FAIL (guard.py missing).

- [ ] **Step 4: Write `scripts/guard.py`**

```python
#!/usr/bin/env python3
"""PreToolUse guard for sf-orchestrator. Exit 0 allows; exit 2 blocks (stderr shown to the model)."""
import datetime, json, os, re, sys

APPROVAL = os.path.join('.claude', 'sf-orchestrator-approval.json')
APPROVAL_TTL_MIN = 60
DESTRUCTIVE = re.compile(
    r'\bsf\s+project\s+deploy\b|\bsfdx\s+force:source:deploy\b|'
    r'\bsf\s+data\s+delete\b|\bsf\s+org\s+delete\b')

def block(msg):
    print(f'sf-orchestrator guard: {msg}', file=sys.stderr)
    sys.exit(2)

def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # not our concern; never break unrelated tooling
    tool = event.get('tool_name', '')
    tin = event.get('tool_input', {}) or {}

    if tool == 'Agent':
        sub = str(tin.get('subagent_type', ''))
        if sub.startswith('sf-') and not tin.get('model'):
            block(f'dispatch of {sub} without an explicit model parameter. '
                  'Set model from .claude/sf-orchestrator.json and retry.')

    if tool == 'Bash':
        cmd = str(tin.get('command', ''))
        if DESTRUCTIVE.search(cmd):
            if not os.path.exists(APPROVAL):
                block('deploy/destructive command without approval. Confirm org and '
                      'scope with the user, write .claude/sf-orchestrator-approval.json, retry.')
            try:
                approval = json.load(open(APPROVAL))
                granted = datetime.datetime.fromisoformat(approval['grantedAt'])
                if granted.tzinfo is None:
                    granted = granted.replace(tzinfo=datetime.timezone.utc)
                age_min = (datetime.datetime.now(datetime.timezone.utc) - granted).total_seconds() / 60
                org = approval.get('org', '')
            except (KeyError, ValueError, TypeError, json.JSONDecodeError):
                block('approval file malformed; re-confirm with the user and rewrite it.')
            if age_min > APPROVAL_TTL_MIN:
                block(f'approval expired ({int(age_min)} min old, TTL {APPROVAL_TTL_MIN}). Re-confirm with the user.')
            if org and org not in cmd:
                block(f'command does not target the approved org "{org}".')
    sys.exit(0)

main()
```

- [ ] **Step 5: Write `hooks/hooks.json`**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Agent|Bash",
        "hooks": [
          { "type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/guard.py\"" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 6: Run `bash tests/test_guard.sh`** — Expected: `GUARD-PASS`.

- [ ] **Step 7: Append the guard test to `scripts/validate.sh`** — add `bash tests/test_guard.sh || fail=1` before the final PASS/FAIL line.

- [ ] **Step 8: Commit** — `feat: PreToolUse guard (model-less dispatch, unapproved deploys) with fixtures`

---

### Task 3: Config schema + config skill

**Files:**
- Create: `schemas/config.schema.json`, `skills/config/SKILL.md`

**Interfaces:**
- Produces: canonical config contract at `.claude/sf-orchestrator.json` (user's project), schema below; loader rules consumed verbatim by Task 7.

- [ ] **Step 1: Write `schemas/config.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "sf-orchestrator config",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "models": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "default": { "enum": ["haiku", "sonnet", "opus"] },
        "escalation": { "enum": ["haiku", "sonnet", "opus"] },
        "workers": {
          "type": "object",
          "propertyNames": {
            "enum": ["sf-apex-worker", "sf-lwc-worker", "sf-test-worker", "sf-data-worker",
                     "sf-debug-worker", "sf-metadata-worker", "sf-deploy-worker",
                     "sf-mapper", "sf-reviewer"]
          },
          "additionalProperties": { "enum": ["haiku", "sonnet", "opus"] }
        }
      }
    },
    "limits": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "maxConcurrent": { "type": "integer", "minimum": 1, "maximum": 10 },
        "maxAttempts": { "type": "integer", "minimum": 1, "maximum": 3 }
      }
    },
    "deployWorker": {
      "type": "object",
      "additionalProperties": false,
      "properties": { "enabled": { "type": "boolean" } }
    },
    "effort": { "enum": ["low", "medium", "high", null] },
    "externalExecutors": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "additionalProperties": false,
        "required": ["enabled", "executable", "args"],
        "properties": {
          "enabled": { "type": "boolean" },
          "executable": { "type": "string" },
          "args": { "type": "array", "items": { "type": "string" } },
          "timeoutSeconds": { "type": "integer", "minimum": 30, "maximum": 3600 }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write `skills/config/SKILL.md`** — frontmatter `name: config`, `description: Use when the user wants to configure sf-orchestrator - worker models, escalation tier, concurrency/retry limits, deploy worker enablement, or external executors. Creates or edits .claude/sf-orchestrator.json in the current project.` Body:

````markdown
# sf-orchestrator: config

Create or edit `.claude/sf-orchestrator.json`, always conforming to `schemas/config.schema.json` in this plugin.

## Defaults

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

## Loader rules (shared with the orchestrate skill)

- Missing file → use defaults silently.
- Malformed JSON → STOP and tell the user; never guess or overwrite.
- Unknown keys → warn, ignore.
- Invalid model value → error naming the key.
- Defaults merge per-key (a partial file is fine).

## Workflow

1. Read the existing file if present; else start from defaults.
2. Ask one question at a time (AskUserQuestion where available): default model → escalation model → per-worker overrides (recommend sf-mapper: haiku) → limits → enable deploy worker? (default NO — explain it permits org deploys, still gated per-run by approval) → external executor? (default no; if yes, capture executable + fixed args array + timeout, warn it runs a local CLI and requires trust).
3. Validate the result against the schema (mentally; keys and enums above). Write the file, creating `.claude/` if needed.
4. Show the final JSON; note that `effort` is reserved and currently inert in Claude Code dispatches.

Never write keys outside the schema.
````

- [ ] **Step 3: Run `bash scripts/validate.sh`** — schema JSON valid; skill count failure now `found 1`.

- [ ] **Step 4: Commit** — `feat: config schema and config skill`

---

### Task 4: Code workers (apex, lwc, test)

**Files:**
- Create: `agents/sf-apex-worker.md`, `agents/sf-lwc-worker.md`, `agents/sf-test-worker.md`

**Interfaces:**
- Produces: the **shared contract block** below, reused verbatim in every agent (Tasks 4–6), `<CAPS>` replaced by that agent's capability probe lists.

**Shared contract block:**

```markdown
## Operating contract

**Skill loading (FIRST action):** For each capability you need, try the probe list in order via the Skill tool and use the first that loads: <CAPS>. If none loads for a capability, check your Fallback cheat-sheet: if it covers the operation, proceed with it and set `fallback: true` in your report; if it does not (or the operation is marked blocked), STOP and report a capability-gap.

**Precedence:** Your dispatched plan defines scope and file boundaries. If a loaded skill's workflow wants to exceed them (extra files, extra steps), follow the plan — except tests the skill generates for this unit's own code, which you own and report.

**Blocked-worker protocol:** If the plan is wrong, impossible, contradicts the codebase, or requires an assumption — STOP. Do not improvise. Report the problem and wait for a corrected plan.

**Final report (compact — no code dumps, no diffs):**
- `skills_loaded`: skill names that loaded, or `fallback: true`, or the capability-gap
- `files_changed`: paths + one-line summary each
- `checks_run`: each acceptance check from the plan + actual output/result
- `deviations`: anything done differently than planned, or `none`
```

- [ ] **Step 1: Write `agents/sf-apex-worker.md`**

Frontmatter: `name: sf-apex-worker`; `description: Implements Apex work units dispatched by the sf-orchestrator - classes, triggers, services, batch/queueable jobs, REST resources, SOQL in Apex. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Edit, Grep, Glob, Bash, Skill`.

Body: one-paragraph role intro ("You execute exactly one work unit from an orchestrator's plan — exact files, exact interfaces, acceptance criteria; follow it literally."), then fallback cheat-sheet, then the shared contract block with `<CAPS>` = "apex: `platform-apex-generate` then `generating-apex`; soql (if the unit designs queries): `platform-soql-query` then `querying-soql`".

Cheat-sheet:
```markdown
## Fallback cheat-sheet (degraded mode only)
- Bulkify: methods take collections; never assume one record.
- No SOQL/DML in loops — query into Maps keyed by Id before, collect and DML once after.
- One trigger per object, zero logic in the trigger body; delegate to a handler class.
- Governor limits: 100 SOQL / 150 DML / 50k rows per transaction.
- DML in try/catch; never swallow exceptions.
- `with sharing` unless the plan says otherwise; bind variables in all SOQL.
```

- [ ] **Step 2: Write `agents/sf-lwc-worker.md`** — same shape. `description: Implements Lightning Web Component work units dispatched by the sf-orchestrator - components, templates, CSS, js-meta.xml, wire adapters, Jest tests. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Edit, Grep, Glob, Bash, Skill`. `<CAPS>` = "lwc: `experience-lwc-generate` then `generating-lwc-components`". Cheat-sheet:

```markdown
## Fallback cheat-sheet (degraded mode only)
- One component per folder: name.js/.html/.css/.js-meta.xml (meta sets apiVersion, isExposed, targets).
- `@wire` for reactive reads; imperative Apex for user-action writes.
- `@api` props are set after construction — never read them in the constructor.
- DOM access only via `this.template.querySelector`.
- Surface Apex errors (extract error.body.message → toast/inline); never fail silently.
- Jest: mock all `@salesforce/*` imports; flush promises before DOM asserts; one behavior per test.
```

- [ ] **Step 3: Write `agents/sf-test-worker.md`** — `description: Writes and fixes Apex test classes and runs test/coverage cycles for work units dispatched by the sf-orchestrator. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Edit, Grep, Glob, Bash, Skill`. `<CAPS>` = "apex-test-gen: `platform-apex-test-generate` then `generating-apex-test`; apex-test-run: `platform-apex-test-run` then `running-apex-tests`". Cheat-sheet:

```markdown
## Fallback cheat-sheet (degraded mode only)
- `@isTest`; create ALL data in-test (factory pattern); never `seeAllData=true`.
- Test bulk paths (200+ records), not just singles.
- `Test.startTest()/stopTest()` around the action under test.
- Assert outcomes with messages; a test without asserts is not a test.
- Cover positive, negative (expected exception), and `System.runAs` permission paths.
- Run: `sf apex run test --tests <Class> --result-format human --synchronous --target-org <alias>`; read real failures before editing.
```

- [ ] **Step 4: Run `bash scripts/validate.sh`** — agent count `found 3`, no contract-phrase failures for these three.

- [ ] **Step 5: Commit** — `feat: apex, lwc, test workers`

---

### Task 5: data, debug, metadata workers

**Files:**
- Create: `agents/sf-data-worker.md`, `agents/sf-debug-worker.md`, `agents/sf-metadata-worker.md`

Same shape + shared contract block per agent.

- [ ] **Step 1: `agents/sf-data-worker.md`** — `description: Seeds, imports, exports, and queries Salesforce org data for work units dispatched by the sf-orchestrator - test data, bulk loads, SOQL authoring, record cleanup. Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Grep, Glob, Bash, Skill`. `<CAPS>` = "data: `platform-data-manage` then `handling-sf-data`; soql: `platform-soql-query` then `querying-soql`". Extra rule after the intro: "Data mutations are org mutations: your plan must name the target org and record scope; if it does not, invoke the blocked-worker protocol. On redispatch after a failure, first query what the prior attempt created before inserting again (idempotency)." Cheat-sheet:

```markdown
## Fallback cheat-sheet (degraded mode only)
- Explicit `--target-org` on every sf command; never the default org.
- Prefer `sf data` commands (bulk upsert >200 rows); anonymous Apex only when relationships require it.
- Query before mutating: verify shape, record types, required fields.
- Upsert on external IDs; never hardcode cross-org record Ids.
- LIMIT exploratory queries; bind/escape all values.
- Delete only records you created (tag field or captured Ids) — never blanket-delete.
```

- [ ] **Step 2: `agents/sf-debug-worker.md`** — `description: Analyzes Salesforce debug logs, governor-limit failures, and stack traces for work units dispatched by the sf-orchestrator; reports root cause with evidence. Read-mostly; fixes code only if the plan says so.`; `tools: Read, Grep, Glob, Bash, Skill`. `<CAPS>` = "debug-logs: `platform-apex-logs-debug` then `debugging-apex-logs`". Cheat-sheet:

```markdown
## Fallback cheat-sheet (degraded mode only)
- `sf apex list log` / `sf apex get log -i <id>` against the explicit target org.
- Read LIMIT_USAGE and EXCEPTION_THROWN lines first; last user-namespace stack frame is usually the culprit.
- SOQL 101/DML 151: count QUERY/DML entries per frame to find the loop; fix is bulkification there.
- Distinguish trigger recursion (same handler repeating) from batch/queueable chaining before blaming volume.
- Every root-cause claim quotes the exact log lines as evidence.
```

- [ ] **Step 3: `agents/sf-metadata-worker.md`** — `description: Creates and edits declarative Salesforce metadata for work units dispatched by the sf-orchestrator - custom objects, fields, validation rules, permission sets, flexipages, and Flows (via the Salesforce DX MCP metadata tools). Executes an explicit plan; does not design solutions.`; `tools: Read, Write, Edit, Grep, Glob, Skill, ToolSearch, mcp__salesforce__deploy_metadata, mcp__salesforce__retrieve_metadata`. `<CAPS>` = "object/field/validation-rule/permset/flexipage: `generating-custom-object`, `generating-custom-field`, `generating-validation-rule`, `generating-permission-set`, `generating-flexipage` (or `platform-metadata-*` successors); flow: `automation-flow-generate` then `generating-flow`". Extra rule: "Flow work REQUIRES the Flow skill plus its MCP metadata tool (load via ToolSearch if deferred); never hand-write Flow XML. If either is unavailable, Flow work is BLOCKED — report a capability-gap, do not fall back." Cheat-sheet (explicitly excludes Flows):

```markdown
## Fallback cheat-sheet (degraded mode only — never for Flows)
- One component per file, exact suffixes (.object-meta.xml, .field-meta.xml, ...) under force-app/main/default/.
- New custom fields deploy with ZERO field-level security — pair every new field with permission-set fieldPermissions.
- Required fields must NOT appear in fieldPermissions (implicit access; listing them breaks deploys).
- Check existing picklist values and naming patterns in the repo before adding.
- Prefer Lookup over Master-Detail unless rollups/ownership inheritance are required.
- Validation rules fire when the formula is TRUE — test the error condition.
```

- [ ] **Step 4: Run `bash scripts/validate.sh`** — `found 6`.

- [ ] **Step 5: Commit** — `feat: data, debug, metadata workers (Flow via MCP, blocked on fallback)`

---

### Task 6: deploy, mapper, reviewer

**Files:**
- Create: `agents/sf-deploy-worker.md`, `agents/sf-mapper.md`, `agents/sf-reviewer.md`

- [ ] **Step 1: `agents/sf-deploy-worker.md`** — `description: Retrieves, diffs, and deploys Salesforce metadata for work units dispatched by the sf-orchestrator. Only dispatched when enabled in config and the user has confirmed org and scope (guard-enforced).`; `tools: Read, Grep, Glob, Bash, Skill`. `<CAPS>` = "deploy: `platform-metadata-deploy` then `deploying-metadata`". Before the contract, add:

```markdown
## Deploy safety (non-negotiable)
- Deploy ONLY the components in your plan, to the org in your plan; missing either → blocked-worker protocol.
- Validate/preview first; report unexpected deletions or conflicts and STOP before the real deploy.
- A plugin guard blocks deploy commands without a fresh user approval file — if blocked, report it; never work around the guard.
- Production deploys only when the plan explicitly states production AND user confirmation.
- On test-gate failures, report failing tests verbatim; never downgrade test levels to force a deploy.
```

Cheat-sheet:
```markdown
## Fallback cheat-sheet (degraded mode only)
- `sf project deploy start --source-dir <paths> --target-org <alias>` — scoped, never whole-repo, unless the plan says otherwise.
- Retrieve-and-diff before deploying: a deploy is a full-file replace and the org may hold newer work.
- Preview (`--dry-run` / validate) before the real deploy; report deltas.
```

- [ ] **Step 2: `agents/sf-mapper.md`** — `description: Read-only Salesforce explorer for the sf-orchestrator. Verifies schema (objects, fields, types, picklists), permission-set grants, existing classes/triggers/components, and dependencies; returns compact facts for planning. Never edits anything.`; `tools: Read, Grep, Glob, Bash, Skill`. `<CAPS>` = "soql (live-org queries): `platform-soql-query` then `querying-soql`". Intro: READ-ONLY; Bash restricted to `sf sobject describe`, `sf data query`, `sf org list metadata`, `sf apex list log` and similar reads; in repo-only mode answer purely from local `*-meta.xml` files and say the org was not consulted. Cheat-sheet:

```markdown
## Fallback cheat-sheet (degraded mode only)
- Verify, never assume: exact API names via `sf sobject describe --sobject <X> --target-org <alias>` or the repo's *-meta.xml.
- Report field TYPES and picklist values exactly — plans fail on assumed types.
- FLS answers from permission-set XML cover permset grants ONLY — state that profiles, permission set groups, and muting are not covered.
- Answer only what was asked, as structured facts (name -> value); say "not found" explicitly; no file dumps, no speculation.
```

- [ ] **Step 3: `agents/sf-reviewer.md`** — `description: Read-only adversarial reviewer for the sf-orchestrator final-review step. Tries to refute a completed unit's claims against its plan, baseline SHA, and owned-file list; runs the acceptance checks; returns a verdict with evidence. Never edits anything.`; `tools: Read, Grep, Glob, Bash, Skill`. `<CAPS>` = "apex-test-run (when the unit has Apex tests): `platform-apex-test-run` then `running-apex-tests`". Intro:

```markdown
You receive: the unit's plan, its baseline commit SHA, its owned-file list, and the worker's report. The report is a CLAIM. Your stance is adversarial: try to REFUTE it — re-derive every claim yourself (`git diff <baseline> -- <owned files>`, run the actual checks). If you cannot confirm a claim, it fails; uncertainty = fail, with what you'd need to confirm.

## Domain validation matrix (apply the rows matching the unit)
- Apex: no SOQL/DML in loops; bulk-safe; asserts present in tests.
- LWC: js-meta targets/apiVersion sane; wires/imperative used per plan; Jest passing.
- Metadata: every new field has permission-set fieldPermissions; no required-field FLS entries.
- Data: mutations match the planned org and record scope exactly.
- Deploy: deployed component list == plan's list; org matches.
```

Replace the standard report block with:

```markdown
**Final report:**
- `verdict`: pass | fail
- `plan_conformance`: each plan requirement -> met / not met, with file:line or command-output evidence
- `checks_rerun`: each acceptance check + actual output
- `discrepancies`: claims in the worker report you could not reproduce (or refuted)
- `skills_loaded`: skills used, or `fallback: true`
```

Cheat-sheet:
```markdown
## Fallback cheat-sheet (degraded mode only)
- Diff first, scoped to owned files; a green test suite does not prove the plan was followed.
- Fail on any changed file outside the owned-file list.
- Deviations the worker did not declare are automatic fails.
```

- [ ] **Step 4: Run `bash scripts/validate.sh`** — `found 9`; only the orchestrate-skill count failing.

- [ ] **Step 5: Commit** — `feat: deploy, mapper, reviewer agents`

---

### Task 7: Orchestrate skill

**Files:**
- Create: `skills/orchestrate/SKILL.md`

**Interfaces:**
- Consumes: agent names (Tasks 4–6), config contract + loader rules (Task 3), approval-file schema (Task 2), capability probe lists (DESIGN.md).

- [ ] **Step 1: Write `skills/orchestrate/SKILL.md`** — frontmatter `name: orchestrate`, `description: Use when the user says "orchestrator", "orchestrate", or asks to delegate a batch of Salesforce tasks (Apex, LWC, tests, data, metadata, Flows, debugging, deploys) to specialized worker agents while a larger model plans, tracks, and reviews.` Body sections in order, content per DESIGN.md rev 2 (this is the authoritative checklist; write each as full prose/tables, no summaries):

  1. **Overview** — orchestrator does only high-value thinking; single-small-unit escape hatch.
  2. **Startup (ordered)** — capability check over ALL probe lists (report supported/degraded/blocked matrix; refuse blocked); config load with the Task 3 loader rules; warn if `CLAUDE_CODE_SUBAGENT_MODEL` is set (it outranks per-call models); target-org resolution (confirm alias once per session, record in manifest) or repo-only mode (org capabilities blocked, mapper local-only).
  3. **Run manifest** — `.claude/sf-orchestrator-run.json`: per unit {id, worker, model, status, baselineSha, ownedFiles, attempts, failureType, reportDigest}; write after every dispatch/completion; on invocation with an existing manifest, offer resume (skip completed units).
  4. **Routing table** — 9 rows as in DESIGN.md; mixed units are SPLIT along ownership boundaries, never merged into a dominant worker.
  5. **Workflow 1–7** — intake/grouping/waves (+ no file collisions, user checkpoint); track (+ manifest); plan (mapper-first mandatory; owned-file list per unit; gotchas = memory lessons only, CLAUDE.md reaches subagents natively — do not re-paste it); dispatch (**HARD RULE: explicit `subagent_type` + `model` on every Agent call — guard-enforced; never fork; ≤ `limits.maxConcurrent` in flight; serialize org-mutating units per org; record baseline SHA before each wave; re-anchor: re-read config + these rules at every wave boundary**); verify (typed failures: plan-defect → fix plan + redispatch; environment → surface, no retry; flaky → one same-tier retry; capability-gap → block + report; `limits.maxAttempts` then escalation model, then block; org-mutating redispatches carry an idempotency note); final review (sf-reviewer per unit with plan + baselineSha + ownedFiles, refute stance; then one completeness-critic reviewer over the original request; orchestrator adjudicates requirements diff + cross-unit integration; user report includes per-unit worker/tier/deviations/blocked); capture lessons.
  6. **Deploy approval** — before dispatching sf-deploy-worker (or any data-deletion unit): config must enable it, user must confirm org + component scope THIS session, then write `.claude/sf-orchestrator-approval.json` {org, scope, grantedAt ISO-8601}; the guard enforces freshness (60 min) and org match; delete the file after the unit completes.
  7. **External executors** — only if configured AND enabled: run via Bash as executable + fixed args array exactly as configured (never build a shell string from the prompt — pass the prompt via stdin), enforce timeoutSeconds, one-time per-project user trust confirmation before first use; any error → escalation model.
  8. **Common mistakes table** — all rows from the original list plus: model-less/fork dispatch; dominant-worker merging; re-pasting CLAUDE.md into prompts; retrying environment failures; deploy without fresh approval; treating a degraded capability as supported; losing the manifest.

- [ ] **Step 2: Run `bash scripts/validate.sh`** — Expected: `PASS` (with `claude` CLI present, plugin validate also green).

- [ ] **Step 3: Commit** — `feat: orchestrate skill (capability matrix, manifest, typed failures, guarded deploys)`

---

### Task 8: README, community files, CI, roadmap

**Files:**
- Create: `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml`, `.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`

- [ ] **Step 1: `README.md`** — sections: independence disclaimer (verbatim from DESIGN.md, at the very top); What it is (token economics + ASCII workflow diagram orchestrator→mapper→waves→workers→reviewers); Prerequisites (Claude Code ≥ current major, Node/npx, Salesforce CLI + authenticated org, `npx skills add forcedotcom/sf-skills`, Salesforce DX MCP server required for Flow work; macOS/Linux, Windows untested); Install (marketplace add + plugin install commands); Usage (`/sf-orchestrator:orchestrate ...`, `/sf-orchestrator:config`); Workers table (9 rows: agent, purpose, capabilities, default model); Capability matrix semantics (supported/degraded/blocked; fallback always flagged; Flows never fall back); Configuration (schema walkthrough incl. loader rules, limits, reserved `effort`, externalExecutors trust model); Safety (hook-enforced: model-less dispatch block + deploy approval; prompt-level everything else — stated plainly; token-cost warning: fan-out multiplies usage); Bring your own conventions (CLAUDE.md flows to workers natively); Versioning (semver, CHANGELOG); License.
- [ ] **Step 2: Community files** — `CONTRIBUTING.md` (dev setup = run `bash scripts/validate.sh`; PR expectations; no vendored Salesforce content rule); `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 standard text); `SECURITY.md` (private disclosure via GitHub security advisories; scope: guard bypasses are vulnerabilities); `CHANGELOG.md` (`## 0.1.0` initial); `docs/ROADMAP.md` (v2 items from DESIGN.md Roadmap verbatim); issue templates (bug: repro + capability matrix output + config; feature: problem/proposal).
- [ ] **Step 3: `.github/workflows/ci.yml`**

```yaml
name: ci
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: bash scripts/validate.sh
```

- [ ] **Step 4: Leak scan** — run `grep -rniE "nos local|sfdc-dev|tonyhani|/Users/" README.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md CHANGELOG.md skills agents docs/ROADMAP.md` → Expected: no matches (DESIGN.md and plans/ are working docs and exempt, but must still not quote internal guideline content).
- [ ] **Step 5: Run `bash scripts/validate.sh`** — `PASS`.
- [ ] **Step 6: Commit** — `docs: README, community files, CI, roadmap`

---

### Task 9: Install, smoke test, migration, publish

- [ ] **Step 1: Local install** — ask the user to run `/plugin marketplace add <local repo path>` then `/plugin install sf-orchestrator@sf-orchestrator-marketplace` (interactive commands).
- [ ] **Step 2: Smoke test (real project)** — in a Salesforce project session: `/sf-orchestrator:config` (verify file + schema conformance); `/sf-orchestrator:orchestrate` with a trivial 2-unit request; verify: capability matrix reported (note which names resolved — current vs legacy), routing correct, every dispatch has explicit model (try one without → guard must block), manifest file written, reviewer ran with refute stance. Test deploy gating: with `deployWorker.enabled: false`, a deploy request must be refused.
- [ ] **Step 3: Negative smoke** — temporarily rename the sf-skills directory (or run in a project without them): degraded capabilities flagged, Flow request blocked with explanation. Restore afterwards.
- [ ] **Step 4: Migration (backup, not delete)** — `mkdir -p ~/.claude/skills-backup && mv ~/.claude/skills/orchestrator-mode ~/.claude/skills-backup/` after the smoke test passes.
- [ ] **Step 5: Publish** — confirm GitHub owner/repo name with the user; replace `OWNER` in plugin.json (grep to confirm none left); create the public repo; push `main`; tag `v0.1.0`; verify CI green.
- [ ] **Step 6: Commit fixes** — `fix: smoke-test findings` (if any).
