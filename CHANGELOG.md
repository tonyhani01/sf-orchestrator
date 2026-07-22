# Changelog

All notable changes to this project are documented in this file. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/); this project uses [Semantic Versioning](https://semver.org/).

## 0.1.0

Initial release.

- Nine worker agents (Apex, LWC, tests, data, debug, metadata, deploy, mapper, reviewer) dispatched by the `orchestrate` skill.
- Capability probe/check against the public `forcedotcom/sf-skills` library, with degraded fallback cheat-sheets and blocked-capability refusal.
- `config` skill and `schemas/config.schema.json` for `.claude/sf-orchestrator.json`.
- `PreToolUse` guard hook enforcing model-explicit worker dispatch and deploy/destructive-command approval.
- `scripts/validate.sh` CI check with negative-fixture coverage.
