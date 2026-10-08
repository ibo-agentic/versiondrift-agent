<!-- DRAFT for the user to paste at the top of DEVIATIONS.md on main (newest first). Not applied. -->
## 2026-10-08 — Analysis conventions fixed before any verdict is computed

Set here, before any pair difference exists, so none is chosen after seeing results. All are implemented in `configs/analysis_official_folders.yaml` (branch `analysis-prep`).

- **Stress diff.** PLAN.md section 4 defines it only as "mean paired success difference (new − old) over the stress conditions, as in the existing pipeline"; it never lists them. The existing pipeline used schema_drift + runtime_fault, and runtime_fault is not rerun (PLAN.md section 3). **DECISION NEEDED:** the analysis currently uses schema_drift + fault_reporting; confirm or replace, and record it here.
- **F6.** Main number: only pairs where at least one model's sampling changed (qwen2, qwen25, qwen3, llama3, llama31, gemma3_4b). All pairs also reported.
- **F3.** Main flip count: only pairs where both models have a native tool template (F3 ran on llama31, qwen25, mistral_v03, granite30, granite31, granite32, qwen3, phi4_mini; both-native pairs: qwen25->qwen3, granite30->granite31, granite31->granite32). All pairs touching an F3 model also reported. Official data: granite30 from `results_v2/F3_rerun/`; phi4_mini from the rescored `results_v2/F3/`; `results_v2/F3/granite30/` is audit-only and the loader refuses it.
- **F4.** Generic JSON only. Qwen3 under F4 and under R is labeled "grammar + thinking blocked", excluded from the main F4 number, reported as its own variant, and compared with Qwen3 F2 (F2−D thinking only, F4−D both, F4−F2 grammar only).
- **H4.** For each nuisance factor (F3, F5, F6) separately, and pooled: the primary number uses only held-out pairs where that factor changed at least one model; the same test on all held-out pairs is also reported. For F3 a both-native variant is also reported. D is compared by the point gate, R by the CI gate.
- **Size-changing pairs** (qwen25->qwen3, gemma2_2b->gemma3_4b) are tagged and reported separately everywhere.
- **Controls.** A/A (R vs R_AA): mistral_v02, qwen25, llama31, phi35_mini, granite31, gemma3_4b (2 design + 4 held-out; PLAN.md section 6 asks for 3 + 3 — deviation). Positive controls (Q2_K and no-description): mistral_v03, qwen25, llama31, granite32 (2 design + 2 held-out).
- **Folder names** assumed for F5 and R: F5, R, R_F3, R_F5, R_F6, R_unconstrained, R_AA, R_PC_Q2K, R_PC_NODESC.
- **Parser.** The Granite-3.0 `"tool"`-key gap stays unfixed in strict parsing; F7 lenient parsing repairs invalid backslash escapes only.
