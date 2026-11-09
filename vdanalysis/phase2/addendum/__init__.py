"""Code for ANALYSIS_ADDENDUM_plan-v2.1.md (sections S1-S9). Secondary, pre-specified analyses.

Nothing here changes P1-P7. Every function works on per-task arrays built from the same runs the
Phase 2 analysis reads, so it can be tested and dry-run in Phase 1 mode (on ``results_v2``) before it
is run once on Phase 2 data. S9 is not implemented: see ``s9_hierarchical.py`` for the open questions.
"""

DELTA = 0.05                 # gate threshold (PLAN.md section 4), also the TOST margin in S3
BOOT_REPS = 10_000           # addendum rule 4
BOOT_SEED = 1234
Z_ALPHA_2 = 1.959964         # two-sided alpha 0.05
Z_POWER_80 = 0.841621        # power 0.80
