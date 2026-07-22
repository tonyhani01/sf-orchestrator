# Security Policy

## Reporting a vulnerability

Please report security issues privately via [GitHub Security Advisories](../../security/advisories/new) for this repository rather than opening a public issue. Do not post exploit details in issues, discussions, or pull requests.

Include, where possible: the affected file(s) or hook, reproduction steps, and the impact you believe it has.

## Scope

This project's threat model centers on the `PreToolUse` guard hook (`hooks/hooks.json` → `scripts/guard.py`), which is the only part of the repo that is actually enforced rather than prompt-level convention. In scope:

- Any way to dispatch an `sf-` worker without an explicit `model` parameter despite the guard.
- Any way to execute a deploy/destructive Bash command (`sf project deploy`, `sfdx force:source:deploy`, `sf data delete`, `sf org delete`, or equivalents) without a fresh, matching `.claude/sf-orchestrator-approval.json`, or with an expired/mismatched approval accepted incorrectly.
- Any way to make the guard silently no-op (e.g. malformed input it should block on but instead allows).

Guard bypasses of this kind are treated as security vulnerabilities, not ordinary bugs, and will be prioritized accordingly.

Everything else in this plugin (mapper read-only-ness, worker file-boundary discipline, reviewer behavior) is explicitly prompt-level, not sandboxed — see the Safety section of `README.md`. Reports about a worker not perfectly following its plan are welcome as regular issues but are not security reports.
