# Benchmarks — orchestrated vs inline cost

Honest, reproducible measurements of the plugin's core economic claim. **Summary: on self-contained, headless tasks, orchestration cost 2–3.6× MORE than doing the work inline on the expensive model.** The per-token worker savings are real, but coordination overhead on the expensive model dominated at both scales tested. Read the analysis before drawing conclusions — the result is narrower than it looks.

## Method

Same task, two arms, fresh scratch Salesforce projects (repo-only mode, no org), run headless via `claude -p --output-format json`; costs are the CLI's reported `total_cost_usd` (actual billed usage, all models, cache-aware). Both arms were held to the same acceptance bar: the inline arm was required to re-read and verify every requirement; the orchestrated arm used its normal refute-stance reviewers + completeness critic. Artifacts from both arms were checked for correctness — all runs produced correct output.

- Expensive model (inline arm / orchestrator): Claude Fable 5 ($10/$50 per MTok)
- Workers (orchestrated arm): Sonnet ($3/$15) default, Haiku ($1/$5) mapper — the plugin's default config
- Date: 2026-07-22, plugin v0.1.0, n=1 per cell

## Results

| Metric | Bench 1: 2 units (object+field, Apex service) | Bench 2: 5 units (2 objects, service, trigger+handler, permset) |
|---|---|---|
| Inline total | **$1.30** — 44 s, 15 turns | **$1.45** — 93 s, 19 turns |
| Orchestrated total | **$2.66** — 4.4 min, 15 turns | **$5.15** — 7.2 min, 27 turns |
| … orchestrator (Fable) share | $1.90 | $3.60 |
| … workers (Sonnet+Haiku) share | $0.76 | $1.55 |
| Correctness | both ✅ | both ✅ |

## Analysis

1. **Worker execution is genuinely cheap.** In bench 2 the workers implemented all 5 units *and* ran 5 adversarial reviews plus a completeness critic for $1.55. The same volume on the expensive model would have been roughly $7–10. The per-token thesis holds.
2. **Coordination on the expensive model swamps it.** Planning, dispatch prompts, report-reading, and adjudication cost $1.90–3.60 — more than the entire inline run in both benches. Overhead also *grew* with unit count (more plans, more reports, more verdicts to read), so simply scaling the task did not reach a crossover.
3. **The expensive model is extremely token-efficient inline.** Fable produced the whole 5-unit build in ~9k output tokens with heavy prompt-cache reuse. When the strong model needs so few tokens, there is little execution cost to save.
4. **Conditions that favor orchestration were absent by design.** Both arms started with a cold, empty context. The benches had no bulky tool output (no test runs, logs, or org describes), nothing exceeding one context window, and no need for wall-clock parallelism. Orchestration's advantages live exactly there:
   - **Main-session context protection** — inline work floods an interactive session's context; every later turn re-reads it at expensive-model rates, and quality degrades. Workers absorb that bloat in disposable contexts.
   - **Verbose-tool-output tasks** — a test-fix loop or debug-log analysis pushes megabytes through context; at $10/MTok input that flips the math.
   - **Beyond-one-context work** — large migrations/audits can't be done inline at any price.
   - **Quality gates** — the refute-reviewers caught real issues in these runs (including workers writing to wrong directories, corrected mid-run). The inline arm's self-verification also passed here, but self-review and independent review are not equivalent under load.
5. **Practical guidance encoded from this data:** use `/sf-orchestrator:orchestrate` for large batches, context-heavy work, org-interactive loops, and when independent review matters; do small self-contained tasks directly (the skill's own "single small unit → skip orchestration" escape hatch, now empirically supported).

## Threats to validity

n=1 per cell; single task family (declarative metadata + small Apex); repo-only (no org round-trips); headless cold-context sessions (understates inline's context-pollution cost in real interactive use); intro Sonnet pricing not assumed. Rerunning with org-interactive units (test execution, deploys, log retrieval) is the most valuable follow-up.

## Reproduction

Two scratch projects with identical `sfdx-project.json` + default `.claude/sf-orchestrator.json`; arm A prompt = task + "verify your own work" clause on the expensive model; arm B prompt = `/sf-orchestrator:orchestrate — FULLY AUTONOMOUS, REPO-ONLY` + the same task; extract `total_cost_usd` and `modelUsage` from each JSON result.
