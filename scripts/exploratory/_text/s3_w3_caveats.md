## Caveats

- 40 decisions, and decisions are not independent (pairs share models, and D and R use the same tasks). The shares
  carry no confidence interval and should not be read as precise rates.
- The full-set classes describe these particular W3 tasks, not tasks in general.
- bfcl_multiple adds only 9 tasks (100 -> 109), so almost nothing changes there; the gain comes from bfcl_simple
  (100 -> 191).
- The class rules (delta, 90% TOST, the CI gate) are unchanged; nothing here alters any pre-registered result.
