# Contributing to sf-orchestrator

## Dev setup

There's no build step. Clone the repo and run the validation suite:

```
bash scripts/validate.sh
```

This wraps `claude plugin validate . --strict` (when the `claude` CLI is available) plus repo contract checks (agent frontmatter shape, guard negative fixtures, config schema conformance). It must print `PASS` before you open a PR.

## PR expectations

- One logical change per PR; keep unrelated cleanups separate.
- If you touch `agents/*.md`, keep frontmatter (`name`, `description`, `tools`) intact and never add a hardcoded `model` — models are always supplied per-dispatch by the orchestrator, and the guard hook enforces this.
- If you touch `schemas/config.schema.json`, update `skills/config/SKILL.md`'s loader rules and `README.md`'s config reference in the same PR so they stay in sync.
- Run `bash scripts/validate.sh` locally before pushing; CI runs the same script.
- Describe what changed and why in the PR body; link any related issue.

## No vendored Salesforce content

This repo contains no copied text from Salesforce's official skills, documentation, or any other third-party or internal source. Workers *load* the public `forcedotcom/sf-skills` library at runtime — they don't ship a copy of it. Fallback cheat-sheets in `agents/*.md` are original, generic best-practice notes, not excerpts from anywhere. Do not add content copied from Salesforce docs, internal company guidelines, or another project's skill files. If you're unsure whether something counts as vendored content, ask in the PR before merging.
