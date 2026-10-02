# Gate vs baseline: baseline-only gate vs stress-based gate; selected vs random canary

Read-only. Gate threshold = 0.05 (same as `docs/protocol.md`). 'stress-based gate' = full-suite truth as published (`tables/upgrade_decisions.csv`, mean(schema_drift, runtime_fault) diff). 'baseline-only gate' = the same threshold rule applied to the `baseline` condition diff alone. 'selected' canary = k=30, cross-pair leave-one-out informativeness with category coverage (same method as `scripts/analyze_gate_threshold_sensitivity.py`, trained only on the other 3 decisions within the same suite -- never on the decision being evaluated). 'random' = 1000 uniform 30-task subsets, match rate against the stress-based truth.


## synthetic

| pair | stress truth | baseline-only verdict | agree with stress truth? | selected-canary (k=30) verdict | selected correct? | random-canary match rate (1000x, k=30) |
|---|---|---|---|---|---|---|
| Mistral v0.1 -> Mistral v0.2 | harmful (-0.168) | neutral (+0.000) | no | harmful (-0.450) | YES | 1.000 |
| Mistral v0.2 -> Mistral v0.3 | beneficial (+0.123) | neutral (-0.030) | no | beneficial (+0.306) | YES | 0.929 |
| Mistral v0.1 -> Mistral v0.3 | neutral (-0.045) | neutral (-0.030) | YES | harmful (-0.111) | no | 0.648 |
| Qwen2.5 -> Qwen3 | neutral (-0.042) | neutral (-0.003) | YES | harmful (-0.067) | no | 0.663 |

## BFCL

| pair | stress truth | baseline-only verdict | agree with stress truth? | selected-canary (k=30) verdict | selected correct? | random-canary match rate (1000x, k=30) |
|---|---|---|---|---|---|---|
| Mistral v0.1 -> Mistral v0.2 | harmful (-0.115) | harmful (-0.083) | YES | harmful (-0.300) | YES | 0.887 |
| Mistral v0.2 -> Mistral v0.3 | beneficial (+0.187) | beneficial (+0.137) | YES | beneficial (+0.344) | YES | 1.000 |
| Mistral v0.1 -> Mistral v0.3 | beneficial (+0.072) | beneficial (+0.053) | YES | beneficial (+0.072) | YES | 0.747 |
| Qwen2.5 -> Qwen3 | harmful (-0.230) | harmful (-0.100) | YES | harmful (-0.222) | YES | 1.000 |

## Interpretation

A baseline-only gate agreeing with the stress-based gate on a given pair means that, for that specific decision, running the clean condition alone would already have produced the correct accept/reject/inspect verdict -- i.e. the stress conditions were not *necessary* to reach that verdict (though they may still be necessary to size the effect, or to catch the category-level swaps AUDIT.md's H2 discusses). See AUDIT.md section K24 for the per-condition significance test this table complements: K24 shows BFCL's baseline gap is statistically significant and same-signed for all four pairs, and the baseline-only verdicts below confirm whether that significant gap is also large enough to cross the 0.05 gate threshold on its own.
