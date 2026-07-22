# Changelog

All notable changes to this project are documented in this file. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/); this project uses [Semantic Versioning](https://semver.org/).

## 0.1.1

Skill-audit hardening (no new features; no config or schema changes).

- Orchestrate skill: capability check reads the available-skills listing instead of load-probing via the Skill tool; corrected the "conventions hook" claim to Claude Code's built-in CLAUDE.md delivery with a per-session verification fallback; documented the guard's exact enforcement contract (explicit `--target-org` required, scope not machine-checked, type-less dispatches uninspected).
- Guard: approval files must name a non-empty org; org is matched as the `--target-org`/`-o` (or `--targetusername`/`-u`) value instead of a command substring; `sf project delete source` and `sfdx force:source:push` are now gated; `Z`-suffixed `grantedAt` timestamps parse on Python < 3.11.
- Tests: new fixtures and guard cases for delete-source gating, wrong-org and missing-flag blocks, empty-org rejection, and `Z` timestamp parsing.

## 0.1.0

Initial release.

- Nine worker agents (Apex, LWC, tests, data, debug, metadata, deploy, mapper, reviewer) dispatched by the `orchestrate` skill.
- Capability probe/check against the public `forcedotcom/sf-skills` library, with degraded fallback cheat-sheets and blocked-capability refusal.
- `config` skill and `schemas/config.schema.json` for `.claude/sf-orchestrator.json`.
- `PreToolUse` guard hook enforcing model-explicit worker dispatch and deploy/destructive-command approval.
- `scripts/validate.sh` CI check with negative-fixture coverage.
