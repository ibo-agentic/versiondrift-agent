# CLAUDE.md

## Phase 2 rules

- Never modify `results/`, `results_smoke/`, or any `results_v2/` folder. Phase 2 outputs go to `results_v3/`.
- Never change hypotheses, thresholds, gate rules, or control definitions. Any change goes in `DEVIATIONS.md` with a reason BEFORE acting on it.
- If you hit a decision not covered by `PLAN_PHASE2.md`, stop and write a report. Do not guess.
- Keep all tests passing. One commit per change. No Claude attribution in commits.
- After any batch of runs, back up new results to `C:\Users\Ibo\OneDrive\upgradecanary_backups\` (stage zips outside results folders).
- Never print, log, or commit API keys.
