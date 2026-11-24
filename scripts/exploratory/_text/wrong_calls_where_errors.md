## Where the errors come from

- **Reference verdicts (A/A arm):** D: 8 beneficial, 5 neutral, 5 harmful, **12 inconclusive**. R: 6 beneficial, 6 neutral, 3 harmful, **15 inconclusive**. The calibrated method's own verdicts on the main run are D: 7 beneficial, 9 neutral, 4 harmful, 10 inconclusive; R: 9 beneficial, 8 neutral, 3 harmful, 10 inconclusive.
- **The 4 serious naive errors under D** (a one-trial call that swapped harmful and beneficial) all come from two decisions: *mistral_v01 -> v02 on bfcl_multiple* (reference harmful; three single-trial calls said beneficial) and *mistral_v02 -> v03 on synthetic* (reference beneficial; one single-trial call said harmful).
- **The one calibrated error under R:** *mistral_v01 -> v02 on bfcl_simple*, where the reference says neutral and the main run's CI gate says beneficial. Under D the calibrated method made no definite call that differed from a definite reference.
- **Important selection effect:** the decisions whose reference is inconclusive (12 under D, 15 under R) cannot be scored, and they are the borderline decisions where a one-run test is most likely to be wrong. The naive error rates above are therefore measured on the easier decisions and are probably an underestimate of how often a one-run test is wrong on a typical borderline upgrade.

