---
name: config
description: Use when the user wants to configure sf-orchestrator - worker models, escalation tier, concurrency/retry limits, deploy worker enablement, or external executors. Creates or edits .claude/sf-orchestrator.json in the current project.
---

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

Implementations can consult `scripts/check_config.py` in this plugin as the reference for these rules.

## Workflow

1. Read the existing file if present; else start from defaults.
2. Ask one question at a time (AskUserQuestion where available): default model → escalation model → per-worker overrides (recommend sf-mapper: haiku) → limits → enable deploy worker? (default NO — explain it permits org deploys, still gated per-run by approval) → external executor? (default no; if yes, capture executable + fixed args array + timeout, warn it runs a local CLI and requires trust).
3. Validate the result against the schema (mentally; keys and enums above). Write the file, creating `.claude/` if needed.
4. Show the final JSON; note that `effort` is reserved and currently inert in Claude Code dispatches.

Never write keys outside the schema.
