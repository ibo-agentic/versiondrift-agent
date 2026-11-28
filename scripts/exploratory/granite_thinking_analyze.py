"""Exploratory add-on (not pre-registered): analyse the granite32 thinking-ON arm by the decision rule of
analysis/exploratory/EXPLORATORY_PLAN_granite_thinking.md (tag plan-granite-thinking). Read only.

    python -m scripts.exploratory.granite_thinking_analyze --arm think256 --out analysis/exploratory

Writes EXPLORATORY_granite_thinking.md and EXPLORATORY_granite_thinking_records.csv into --out.
- Cut-off share (criterion a, c): output hit the token limit OR contains "Here is my thought process:" without "Here is my response:".
- Unparsed share (secondary): the scorer's parse_ok is false (strict thinking policy, as stored).
- Verdict: granite31 (D main run) -> granite32 thinking ON with the study's own compare() (stress conditions, point gate +/-0.05,
  task-cluster bootstrap CI gate, 10,000 reps, seed 1234) and the S3 four-class verdict, on the trials both runs share. Compared with the
  existing thinking-off decision (10 trials, from analysis_out_v3_p7 and the S3 classes) and, as a like-for-like check, the thinking-off
  granite32 run on the same trials. Sensitivity: the same verdicts with the main study's parsing rule (first JSON anywhere), rescored
  from the stored raw outputs.
- qwen3 under the strict rule (plan section 4): both sides of qwen25 -> qwen3 (stored D outputs, 10 trials) rescored with the main
  rule and with thinking_policy="strict"; cut-off / unparsed shares and verdicts per suite; a qwen3 vs granite32 token-length table.
  Also writes EXPLORATORY_granite_thinking_qwen3_records.csv. Needs models/qwen/Qwen3-8B-Q4_K_M.gguf (vocab only, for token counts).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

import numpy as np

from ._common import ADDENDUM_DIR, CONFIG, P7_DIR, REPO_ROOT, check_out_dir

THOUGHT, RESPONSE = "Here is my thought process:", "Here is my response:"
ORDER = {"harmful": 0, "neutral": 1, "beneficial": 2}


class Sub:
    """A run restricted to some trials (only .keys is used by compare / make_arrays)."""
    def __init__(self, run, trials):
        self.keys = {k: v for k, v in run.keys.items() if k[4] in trials}
        self.protocol, self.model, self.suite = run.protocol, run.model, run.suite

    def __len__(self):
        return len(self.keys)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", default="think256")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = check_out_dir(args.out)
    sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))
    import _dll_preload                                            # this machine's llama.dll workaround (vocab only: token counts)
    _dll_preload.preload()
    from llama_cpp import Llama
    from upgradecanary.evaluator import evaluate, evaluate_fault_reporting
    from upgradecanary.parsing import extract_fault_report, extract_tool_call_with_format
    from upgradecanary.perturbations.runtime_faults import Fault
    from upgradecanary.perturbations.schema_drift import Drift, drifted_schema
    from upgradecanary.runner import _safe_execute, task_base_schema
    from upgradecanary.tasks import load_tasks
    from vdanalysis.loader import Run, failure_bucket, record_key, record_score
    from vdanalysis.phase2.addendum.data import make_arrays
    from vdanalysis.phase2.addendum.s3_fourclass import interval
    from vdanalysis.phase2.analysis import Phase2Analysis
    from vdanalysis.phase2.config import load_phase2_config
    from vdanalysis.stats import compare
    import yaml
    from ._common import classify

    def rescore(p, outp, tasks, policy):
        """Score a stored stress record again from its raw output under a thinking policy (None = the main study's rule)."""
        fault = Fault(**p["fault"]) if p.get("fault") else None
        if p["condition"] == "fault_reporting":
            m = evaluate_fault_reporting(extract_fault_report(outp, thinking_policy=policy), fault)
        else:
            task = tasks[p["task_id"]]
            drift = Drift(**p["drift"]) if p.get("drift") else None
            base = task_base_schema(task)
            schema = drifted_schema(base, drift)
            call, _f = extract_tool_call_with_format(outp, thinking_policy=policy)
            ex = _safe_execute(call, schema, drift, fault, False, canonical_schema=base)
            m = evaluate(p["condition"], task.expected_call, call, ex, drift, fault, None, schema, False, acceptable=task.acceptable)
        return {"condition": p["condition"], "metrics": m}

    cfg = load_phase2_config(str(CONFIG))
    an = Phase2Analysis(cfg, with_ci=True, allow_missing=True)
    tok = Llama(str(REPO_ROOT / "models/granite/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf"), vocab_only=True, verbose=False)
    arm_dir = REPO_ROOT / "results_exploratory" / "granite_thinking" / args.arm
    rows, think_strict, think_main = [], {}, {}
    for suite in cfg.suites:
        run_dirs = [d for d in (arm_dir / suite).iterdir() if d.is_dir() and (d / "parsed_results.jsonl").exists()]
        assert len(run_dirs) == 1, f"{suite}: expected one run folder, found {len(run_dirs)}"
        rd = run_dirs[0]
        rcfg = yaml.safe_load(Path(json.loads((rd / "run_manifest.json").read_text(encoding="utf-8"))["config_path"]).read_text(encoding="utf-8"))
        tasks = {t.task_id: t for t in load_tasks(str(REPO_ROOT / rcfg["data"]))}
        rs, rm = Run("G32think", "granite32", suite, rd), Run("G32think_mainrule", "granite32", suite, rd)
        for lp, lr in zip(open(rd / "parsed_results.jsonl", encoding="utf-8"), open(rd / "raw_outputs.jsonl", encoding="utf-8")):
            p, r = json.loads(lp), json.loads(lr)
            assert (p["task_id"], p["condition"], p["trial_index"]) == (r["task_id"], r["condition"], r["trial_index"])
            outp = r["raw_output"] or ""
            k = record_key(p)
            s = record_score(p)
            rs.keys[k] = (s, failure_bucket(p, s))
            # the main study's rule (no thinking policy): rescore from the stored raw output
            pm = rescore(p, outp, tasks, None)
            sm = record_score(pm)
            rm.keys[k] = (sm, failure_bucket(pm, sm))
            thought, resp, trunc = THOUGHT in outp, RESPONSE in outp, bool(r.get("truncated"))
            rows.append({"suite": suite, "task_id": p["task_id"], "condition": p["condition"], "trial": p["trial_index"],
                         "tokens": len(tok.tokenize(outp.encode("utf-8"), add_bos=False, special=True)), "truncated": int(trunc),
                         "thought_marker": int(thought), "response_marker": int(resp), "cut_off": int(trunc or (thought and not resp)),
                         "parse_ok_strict": int(bool(p["metrics"].get("parse_ok"))), "score_strict": s, "score_main_rule": sm})
        think_strict[suite], think_main[suite] = rs, rm
    trials = sorted({r["trial"] for r in rows})

    # ---- verdicts
    existing = {(r["pair"], r["suite"]): r for r in csv.DictReader(open(P7_DIR / "decisions_D.csv"))}
    s3 = {(r["protocol"], r["pair"], r["suite"]): r["class4"] for r in csv.DictReader(open(ADDENDUM_DIR / "s3_classes.csv"))}
    pair = "granite31->granite32"

    def verdict(old, new):
        c = compare(old, new, cfg.stress, cfg.threshold, cfg.reps, cfg.seed, with_ci=True)
        a = make_arrays(old, new, cfg.stress)
        lo90, hi90 = interval(a, 0.90, 10000, 1234)
        return {"n": c.n_records, "diff": c.diff, "lo": c.ci_lo, "hi": c.ci_hi, "point": c.label_point, "ci": c.label_ci,
                "class4": classify(c.diff, lo90, hi90, c.label_ci)}

    V = {}
    for suite in cfg.suites:
        g31 = Sub(an.run_for("D", "granite31", suite), set(trials))
        g32off = Sub(an.run_for("D", "granite32", suite), set(trials))
        V[suite] = {"think": verdict(g31, think_strict[suite]), "think_mainrule": verdict(g31, think_main[suite]),
                    "off_same_trials": verdict(g31, g32off),
                    "off_existing": {"diff": float(existing[(pair, suite)]["stress_diff"]), "lo": float(existing[(pair, suite)]["ci_lo"]),
                                     "hi": float(existing[(pair, suite)]["ci_hi"]), "point": existing[(pair, suite)]["label_point"],
                                     "ci": existing[(pair, suite)]["label_ci"], "class4": s3[("D", pair, suite)], "n": None}}

    # ---- decision rule
    n = len(rows)
    cut = sum(r["cut_off"] for r in rows)
    unp = sum(1 - r["parse_ok_strict"] for r in rows)
    a_holds = cut / n > 0.10
    mean_drop = np.mean([V[s]["think"]["diff"] - V[s]["off_existing"]["diff"] for s in cfg.suites])
    toward_harm = [s for s in cfg.suites if ORDER[V[s]["think"]["point"]] < ORDER[V[s]["off_existing"]["point"]]]
    b_holds = mean_drop <= -0.05 and len(toward_harm) >= 1
    toks = [r["tokens"] for r in rows]

    def pc(k, m):
        return f"{100 * k / m:.1f}%" if m else "n/a"

    md = ["**EXPLORATORY add-on, not pre-registered.** Analysis of the granite32 thinking-ON arm by the decision rule fixed in "
          "`EXPLORATORY_PLAN_granite_thinking.md` (tag plan-granite-thinking). Existing data plus this arm only; read-only script "
          "`scripts/exploratory/granite_thinking_analyze.py`.\n",
          f"# granite32 with thinking ON: arm {args.arm}, trials {', '.join(map(str, trials))}\n",
          f"Run: 3 suites x 100 tasks x 2 stress conditions x {len(trials)} trials = {n} outputs (granite32, thinking ON via the chat template's "
          "`thinking` variable, 256 tokens, strict thinking policy). Seeds and temperatures as the D main run's trials "
          f"{trials[0]}-{trials[-1]}.\n",
          "## Criterion (a): cut-off share, and the secondary unparsed share\n",
          "| Suite | Outputs | Cut-off (limit hit, or thinking without a response) | of which hit the token limit | Unparsed (secondary) |\n|---|---|---|---|---|"]
    for suite in list(cfg.suites) + ["all"]:
        sel = [r for r in rows if suite == "all" or r["suite"] == suite]
        md.append(f"| {suite} | {len(sel)} | **{pc(sum(r['cut_off'] for r in sel), len(sel))}** ({sum(r['cut_off'] for r in sel)}) | "
                  f"{pc(sum(r['truncated'] for r in sel), len(sel))} | {pc(sum(1 - r['parse_ok_strict'] for r in sel), len(sel))} ({sum(1 - r['parse_ok_strict'] for r in sel)}) |")
    md.append(f"\nThinking visibly on: {sum(r['thought_marker'] for r in rows)} of {n} outputs contain \"{THOUGHT}\"; "
              f"{sum(r['response_marker'] for r in rows)} contain \"{RESPONSE}\".\n")
    md.append(f"**Output length (tokens, re-tokenized with the model's own tokenizer):** median {statistics.median(toks):.0f}, "
              f"90th percentile {np.percentile(toks, 90):.0f}, max {max(toks)} (budget 256).\n")
    md.append("## Verdict granite31 -> granite32 (stress conditions, the study's gates)\n")
    md.append(f"Compared on the trials both runs share (trials {trials[0]}-{trials[-1]}, n = matched records). 'Thinking-off, existing' is the main "
              "study's 10-trial D decision; 'thinking-off, same trials' restricts that run to the same trials as the thinking-ON arm.\n")
    md.append("| Suite | granite32 | n | Stress diff | 95% CI | Point gate (D) | CI gate | Four-class |\n|---|---|---|---|---|---|---|---|")
    for suite in cfg.suites:
        for key, name in (("think", "thinking ON (strict rule)"), ("think_mainrule", "thinking ON (main study's rule)"),
                          ("off_same_trials", "thinking off, same trials"), ("off_existing", "thinking off, existing (10 trials)")):
            v = V[suite][key]
            md.append(f"| {suite} | {name} | {v['n'] if v['n'] else '-'} | {v['diff']:+.3f} | [{v['lo']:+.3f}, {v['hi']:+.3f}] | {v['point']} | {v['ci']} | {v['class4']} |")
    md.append("\n## Decision rule (from the plan)\n")
    md.append(f"- **(a) cut-off share above 10% at 256:** {pc(cut, n)} ({cut} of {n}) -> **{'holds' if a_holds else 'fails'}**.")
    md.append(f"- **(b) verdict moves toward harmful** (mean stress diff over the 3 suites drops by at least 0.05 vs the existing thinking-off decision, "
              f"and the D point label moves at least one step toward harmful in at least one suite): mean change {mean_drop:+.3f}; suites moving toward "
              f"harmful: {', '.join(toward_harm) if toward_harm else 'none'} -> **{'holds' if b_holds else 'fails'}**"
              f"{' (descriptive only, from 3 trials, since (a) fails)' if not a_holds else ''}.")
    md.append("- **(c)** needs the 1024 arm; " + ("not run, because (a) fails." if not a_holds else "to be run next."))
    md.append("\n**Branch that applies next:** " + (
        "**stop.** (a) fails, so by the plan the answer is *not the same hazard*: with thinking ON, granite32's thinking fits the 256-token budget. "
        "The 1024 arm and the extension to 10 trials are not needed; this is reported as a null result for the hazard question."
        if not a_holds else
        "**extend:** (a) holds, so by the plan think256 is extended to 10 trials (trials 3-9, 7 more) and the think1024 arm is run with 10 trials; "
        "(b) and (c) are decided on those."))
    md.append(f"\nSecondary unparsed share {pc(unp, n)} ({unp} of {n}) is reported, not used for the decision.\n")

    # ---- qwen3 under the strict rule (plan section 4): stored D outputs of qwen25 and qwen3, rescored; no rerun
    qtok = Llama(str(REPO_ROOT / "models/qwen/Qwen3-8B-Q4_K_M.gguf"), vocab_only=True, verbose=False)
    task_files = sorted(list((REPO_ROOT / "data").glob("*_tasks.jsonl")) + [f for f in (REPO_ROOT / "data" / "phase2").glob("w3_added_bfcl_*.jsonl") if "provenance" not in f.name])
    all_tasks = {}
    for f in task_files:
        for t in load_tasks(str(f)):
            all_tasks.setdefault(t.task_id, t)
    default_data = {"synthetic": "data/base_tasks.jsonl", "bfcl_simple": "data/bfcl_tasks.jsonl", "bfcl_multiple": "data/bfcl_multiple_tasks.jsonl"}
    qrows, Q, checks = [], {}, {"records": 0, "main_rule_rescore_differs_from_stored": 0, "strict_differs_from_main": {}}
    for model in ("qwen25", "qwen3"):
        for suite in cfg.suites:
            merged = an.run_for("D", model, suite)
            want = {k for k in merged.keys if k[1] in cfg.stress}
            st, mn = Run("D_strict", model, suite, merged.path), Run("D_main", model, suite, merged.path)
            for d, spec in an.store.part_dirs("D", model, suite):
                rd = an.store._find_run_dir(d)
                cp = json.loads((rd / "run_manifest.json").read_text(encoding="utf-8")).get("config_path")
                data = (yaml.safe_load(Path(cp).read_text(encoding="utf-8")) or {}).get("data") if cp and Path(cp).exists() else None
                tasks = dict(all_tasks)
                tasks.update({t.task_id: t for t in load_tasks(str(REPO_ROOT / (data or default_data[suite])))})
                for lp, lr in zip(open(rd / "parsed_results.jsonl", encoding="utf-8"), open(rd / "raw_outputs.jsonl", encoding="utf-8")):
                    p, r = json.loads(lp), json.loads(lr)
                    if p["condition"] not in cfg.stress:
                        continue
                    assert (p["task_id"], p["condition"], p["trial_index"]) == (r["task_id"], r["condition"], r["trial_index"])
                    assert not r.get("retry_raw_output"), "D has no retries"
                    k0 = record_key(p)
                    k = k0[:4] + (k0[4] + spec.trial_offset,)
                    if k not in want:
                        continue
                    outp = r["raw_output"] or ""
                    pm, ps = rescore(p, outp, tasks, None), rescore(p, outp, tasks, "strict")
                    sm, ss = record_score(pm), record_score(ps)
                    mn.keys[k], st.keys[k] = (sm, failure_bucket(pm, sm)), (ss, failure_bucket(ps, ss))
                    checks["records"] += 1
                    checks["main_rule_rescore_differs_from_stored"] += sm != merged.keys[k][0]
                    ext = extract_fault_report if p["condition"] == "fault_reporting" else extract_tool_call_with_format
                    d = checks["strict_differs_from_main"].setdefault(model, [0, 0])
                    d[0] += ext(outp) != ext(outp, thinking_policy="strict")                       # parsed output differs
                    d[1] += (ps["metrics"].get("parse_ok"), ss) != (pm["metrics"].get("parse_ok"), sm)   # parse status or score differs
                    if model == "qwen3":
                        trunc = bool(r.get("truncated"))
                        thought, resp = "<think>" in outp, "</think>" in outp
                        qrows.append({"suite": suite, "task_id": p["task_id"], "condition": p["condition"], "trial": k[4],
                                      "tokens": len(qtok.tokenize(outp.encode("utf-8"), add_bos=False, special=True)), "truncated": int(trunc),
                                      "think_open": int(thought), "think_close": int(resp), "cut_off": int(trunc or (thought and not resp)),
                                      "parse_ok_main_rule": int(bool(pm["metrics"].get("parse_ok"))),
                                      "parse_ok_strict": int(bool(ps["metrics"].get("parse_ok"))), "score_main_rule": sm, "score_strict": ss})
            assert set(st.keys) == want, f"{model}/{suite}: {len(want - set(st.keys))} stress records not found in the parts"
            Q[(model, suite)] = {"strict": st, "main": mn}
    qpair = "qwen25->qwen3"
    QV = {s: {"main": verdict(Q[("qwen25", s)]["main"], Q[("qwen3", s)]["main"]),
              "strict": verdict(Q[("qwen25", s)]["strict"], Q[("qwen3", s)]["strict"]),
              "existing": existing[(qpair, s)], "existing4": s3[("D", qpair, s)]} for s in cfg.suites}

    md.append("## qwen3 under the strict rule (stored D outputs, rescored; no rerun)\n")
    md.append("The plan (section 4) rescores qwen3's existing D numbers under the strict rule so that both thinking models are compared under the same "
              "rule. Both sides of qwen25 -> qwen3 (D main run, 10 trials, stress conditions, results_v2 trials 0-2 + results_v3 trials 3-9) are "
              "rescored from the stored raw outputs with the main study's rule and with `thinking_policy=\"strict\"`; the study's gates as above. "
              f"Checks: {checks['records']} stress records rescored; the main-rule rescore differs from the stored score in "
              f"{checks['main_rule_rescore_differs_from_stored']}. The strict rule parses {checks['strict_differs_from_main']['qwen3'][0]} qwen3 "
              f"records differently (the plan's figure), of which {checks['strict_differs_from_main']['qwen3'][1]} change parse status or score "
              f"(the rest parse to a different call or report that scores the same); qwen25: {checks['strict_differs_from_main']['qwen25'][0]} "
              "parsed differently.\n")
    md.append("Cut-off = hit the 256-token limit, or `<think>` without `</think>`. Unparsed = the scorer's parse_ok is false.\n")
    md.append("| Suite | Outputs | Cut-off | Unparsed, main rule | Unparsed, strict rule |\n|---|---|---|---|---|")
    for suite in list(cfg.suites) + ["all"]:
        sel = [r for r in qrows if suite == "all" or r["suite"] == suite]
        c, um, us = (sum(r["cut_off"] for r in sel), sum(1 - r["parse_ok_main_rule"] for r in sel), sum(1 - r["parse_ok_strict"] for r in sel))
        md.append(f"| {suite} | {len(sel)} | {pc(c, len(sel))} ({c}) | {pc(um, len(sel))} ({um}) | {pc(us, len(sel))} ({us}) |")
    md.append("\n| Suite | Rule | Stress diff | 95% CI | Point gate (D) | CI gate | Four-class |\n|---|---|---|---|---|---|---|")
    for suite in cfg.suites:
        e = QV[suite]["existing"]
        md.append(f"| {suite} | existing D decision (analysis_out_v3_p7) | {float(e['stress_diff']):+.3f} | [{float(e['ci_lo']):+.3f}, {float(e['ci_hi']):+.3f}] | "
                  f"{e['label_point']} | {e['label_ci']} | {QV[suite]['existing4']} |")
        for key, name in (("main", "main study's rule (rescored)"), ("strict", "strict rule")):
            v = QV[suite][key]
            md.append(f"| {suite} | {name} | {v['diff']:+.3f} | [{v['lo']:+.3f}, {v['hi']:+.3f}] | {v['point']} | {v['ci']} | {v['class4']} |")

    md.append("\n## qwen3 vs granite32, both with thinking ON at 256 tokens\n")
    md.append("Token counts re-tokenized with each model's own tokenizer (GGUF vocab). qwen3 thinks by default; granite32 with the template's "
              "`thinking` variable switched on.\n")
    md.append("| Model | Trials | Outputs | Cut-off share | Median tokens | 90th percentile | Max |\n|---|---|---|---|---|---|---|")
    q02 = [r for r in qrows if r["trial"] in trials]
    for name, tr, sel in (("qwen3 (D main run)", "0-9", qrows), ("qwen3 (D main run)", f"{trials[0]}-{trials[-1]}", q02),
                          (f"granite32 thinking ON ({args.arm})", f"{trials[0]}-{trials[-1]}", rows)):
        tk = [r["tokens"] for r in sel]
        c = sum(r["cut_off"] for r in sel)
        md.append(f"| {name} | {tr} | {len(sel)} | {pc(c, len(sel))} ({c}) | {statistics.median(tk):.0f} | {np.percentile(tk, 90):.0f} | {max(tk)} |")
    md.append("\n**Context for the 256 budget:** lm-evaluation-harness 0.4.13 uses `max_gen_toks` = 256 by default (HF, vLLM and API backends) "
              "when a task does not set its own (checked in the 0.4.13 wheel: `models/huggingface.py`, `models/vllm_causallms.py`, "
              "`models/api_models.py`).\n")
    with open(out / "EXPLORATORY_granite_thinking_qwen3_records.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(qrows[0]))
        w.writeheader()
        w.writerows(qrows)
    (out / "EXPLORATORY_granite_thinking.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    with open(out / "EXPLORATORY_granite_thinking_records.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
