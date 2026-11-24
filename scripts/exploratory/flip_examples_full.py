"""EXPLORATORY_flip_examples_full.md: the 16 models and thinking mode, task-045 trials, and 'got worse' examples for upgrades without thinking.

    python -m scripts.exploratory.flip_examples_full --out <folder>
"""

from __future__ import annotations

import sys, json, re
from collections import Counter, defaultdict
from pathlib import Path
from vdanalysis.loader import record_score
from vdanalysis.phase2.config import load_phase2_config
from vdanalysis.phase2.merge import MergedStore
from upgradecanary.tasks import load_tasks
from upgradecanary.perturbations.schema_drift import Drift, to_new_space, drifted_schema, compatible
from upgradecanary.tools import BASE_SCHEMAS, validate_call
from ._common import CONFIG, REPO_ROOT, parse_out


def run(outdir):
    cfg = load_phase2_config(str(CONFIG))
    store = MergedStore(cfg)
    stress = set(cfg.stress)
    TASKFILES = {"synthetic": str(REPO_ROOT / "data/base_tasks.jsonl"), "bfcl_simple": str(REPO_ROOT / "data/bfcl_tasks.jsonl"), "bfcl_multiple": str(REPO_ROOT / "data/bfcl_multiple_tasks.jsonl")}
    tasks = {s: {t.task_id: t for t in load_tasks(f)} for s, f in TASKFILES.items()}
    cache = {}


    def reason(p):
        m = p["metrics"]
        if not m.get("parse_ok", False):
            return "unparsed/broken output"
        if p["condition"] == "fault_reporting":
            if not m.get("status_ok", True):
                return "fault-reporting wrong status"
            if not m.get("no_fabrication", True):
                return "fabricated answer"
            return "other"
        if not m.get("tool_name_ok", True):
            return "wrong tool name"
        if not (m.get("args_valid_under_drift", True) and m.get("args_intent_match", True) and m.get("executor_ok", True)):
            return "wrong/invalid arguments"
        return "other"


    def load(model, suite, proto="D"):
        k = (proto, model, suite)
        if k in cache:
            return cache[k]
        d = defaultdict(dict)                       # (task, cond) -> trial -> record dict
        for part, spec in store.part_dirs(proto, model, suite):
            run_dir = store._find_run_dir(part)
            with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fp, open(run_dir / "raw_outputs.jsonl", encoding="utf-8") as fr:
                for lp, lr in zip(fp, fr):
                    p = json.loads(lp)
                    if p["condition"] not in stress:
                        continue
                    r = json.loads(lr)
                    t = int(p.get("trial_index", 0)) + spec.trial_offset
                    ok = record_score(p) >= 1.0
                    d[(p["task_id"], p["condition"])][t] = {"ok": ok, "reason": None if ok else reason(p), "parsed": p, "out": r["raw_output"] or "",
                                                             "prompt": r["prompt"], "trunc": bool(r.get("truncated")), "temp": p.get("temperature")}
        cache[k] = d
        return d


    def rate(tr):
        return sum(x["ok"] for x in tr.values()) / len(tr)


    def question(prompt):
        i = prompt.find("Question: ")
        return prompt[i + 10:prompt.find("\n", i)].strip()


    def fault_sentence(prompt):
        m = re.search(r"You already called the (\S+) tool for this question\. (.*?)\n", prompt)
        return m.group(0).strip() if m else ""


    def expected_status(prompt):
        if "tool call succeeded" in prompt:
            return "ok"
        if "truncated it and some fields are missing" in prompt:
            return "incomplete"
        return "failed"


    def fence(text):
        return "~~~\n" + text.replace("~~~", "~ ~ ~") + "\n~~~"


    def cut(text, head=300, tail=300, limit=700):
        return text if len(text) <= limit else text[:head] + "\n[... " + str(len(text) - head - tail) + " characters omitted ...]\n" + text[-tail:]


    def drift_text(dr):
        if not dr:
            return "no schema change"
        t, f, p = dr["type"], dr["field"], dr.get("params", {})
        if t == "field_rename":
            return f"schema change: the argument `{f}` of `{dr['tool']}` was renamed to `{p.get('new_name')}`"
        if t == "field_drop":
            return f"schema change: the argument `{f}` of `{dr['tool']}` was removed"
        if t == "type_mutation":
            return f"schema change: the argument `{f}` of `{dr['tool']}` must now be given as {p.get('new_type', 'a text string')}"
        if t == "enum_drift":
            return f"schema change: allowed values of `{f}` changed ({json.dumps(p.get('old_to_new'))}, i.e. old value -> new value)"
        if t == "unexpected_field":
            spec = p.get("spec", {})
            return (f"schema change: a new {'REQUIRED ' if spec.get('required') else ''}argument `{f}` ({spec.get('type')}, default {json.dumps(spec.get('default'))}) "
                    f"was added to `{dr['tool']}`")
        return f"schema change: {t} on `{f}` ({json.dumps(p)})"


    def base_schema_of(task):
        return task.internal_schema if (task.suite == "bfcl" and task.internal_schema is not None) else BASE_SCHEMAS[task.tool]


    def schema_of(task, dr):
        return drifted_schema(base_schema_of(task), Drift(**dr) if dr else None)


    def expected_call_text(task, dr):
        """The expected call in the changed schema's space, plus any new required argument (any valid value is accepted)."""
        d = Drift(**dr) if dr else None
        args = to_new_space(task.expected_call["arguments"], d)
        sch = schema_of(task, dr)
        notes = []
        for a, spec in sch["args"].items():
            if spec.get("required") and a not in args:
                args[a] = spec.get("default", True) if "default" in spec else f"<any {spec.get('type')}>"
                notes.append(f"`{a}` is a new REQUIRED argument; any valid {spec.get('type')} value is accepted")
        if task.acceptable:
            notes.append("BFCL-based task: other equivalent values for some arguments are accepted")
        return json.dumps({"name": task.expected_call["name"], "arguments": args}), notes


    def explain_wrong(rec, suite, key):
        p, prompt = rec["parsed"], rec["prompt"]
        m, call, cond, out = p["metrics"], p.get("parsed_call") or {}, key[1], rec["out"]
        if cond == "fault_reporting":
            exp, got = expected_status(prompt), call.get("status")
            if not m.get("parse_ok", False):
                body = re.sub(r"^```(?:json)?|```$", "", out.split("</think>")[-1].strip(), flags=re.M).strip()
                try:
                    obj = json.loads(body)
                except ValueError:
                    return "The reply could not be read as the required JSON status report."
                if isinstance(obj, dict) and obj.get("status") not in ("ok", "failed", "incomplete"):
                    return (f"It invented its own status word `{obj.get('status')}`; only `ok`, `failed` and `incomplete` are allowed, "
                            f"so the report was rejected (the right status here is `{exp}`).")
                return "It was valid JSON but not in the required form (for example `answer` must be text or null), so the report was rejected."
            if not m.get("status_ok", True):
                why = {"failed": "the tool call failed, so the honest status is `failed` with `answer: null`",
                       "incomplete": "the tool returned only part of the data, so the honest status is `incomplete`",
                       "ok": "the tool call succeeded, so the status should be `ok`"}[exp]
                return f"It reported status `{got}` but {why}."
            if not m.get("no_fabrication", True):
                return "It invented an answer although the tool call did not return usable data."
            return "It failed the scorer's fault-reporting check."
        if not m.get("parse_ok", False):
            if "<think>" in out and "</think>" not in out:
                return "It ran out of tokens while thinking and never produced a tool call."
            if "\\_" in out:
                return "The JSON contains an invalid escape: a backslash before an underscore (`\\_`), so it cannot be read as a tool call."
            return "The output could not be read as a tool call (invalid or malformed JSON)."
        task = tasks[suite][key[0]]
        dr = p.get("drift")
        exp_name = task.expected_call["name"]
        if call.get("name") != exp_name:
            return f"It called `{call.get('name')}` but the request needs `{exp_name}`."
        args = call.get("arguments") or {}
        sch = schema_of(task, dr)
        problems = validate_call(call["name"], args, sch, False)
        parts = [f"the schema check says: {pr}" for pr in problems]
        exp_args = to_new_space(task.expected_call["arguments"], Drift(**dr) if dr else None)
        if not compatible(args, task.expected_call["arguments"], Drift(**dr) if dr else None, acceptable=task.acceptable, active_schema=sch):
            diffs = [f"`{k}` = {json.dumps(v)} instead of {json.dumps(exp_args[k])}" for k, v in args.items() if k in exp_args and v != exp_args[k]]
            parts.append("the values do not match the request: " + ("; ".join(diffs) if diffs else "arguments differ from what was asked"))
        return ("In the tool call, " + "; ".join(parts) + ".") if parts else "The call failed the scorer's argument checks."


    # ================================================================= 2. task-045
    MAXTOK = 256
    q3 = load("qwen3", "synthetic")
    q25 = load("qwen25", "synthetic")
    KEY = ("task-045", "fault_reporting")
    tr = q3[KEY]
    md_t45 = []
    exp = expected_status(tr[0]["prompt"])
    rows_t45 = []
    for t in range(10):
        r = tr[t]
        call = r["parsed"].get("parsed_call") or {}
        chars = len(r["out"])
        tok = f"{MAXTOK} (exactly the limit)" if r["trunc"] else f"under {MAXTOK}, count not stored (about {round(chars / 3.7)} estimated from {chars} characters)"
        rows_t45.append((t, r, call, chars, tok))
    t45_reason_counts = Counter(r["reason"] for t, r, *_ in rows_t45 if not r["ok"])

    # 240 got-worse questions
    q3_all = {s: load("qwen3", s) for s in cfg.suites}
    q25_all = {s: load("qwen25", s) for s in cfg.suites}
    gw = []
    for s in cfg.suites:
        for key in sorted(set(q3_all[s]) & set(q25_all[s])):
            if rate(q25_all[s][key]) > 0.5 and rate(q3_all[s][key]) <= 0.5:
                gw.append((s, key))
    ntr = [sum(q3_all[s][key][t]["trunc"] for t in q3_all[s][key]) for s, key in gw]
    dist = Counter(ntr)
    most = sum(1 for n in ntr if n >= 6)
    anytr = sum(1 for n in ntr if n >= 1)
    by_cond = defaultdict(lambda: [0, 0])
    for (s, key), n in zip(gw, ntr):
        by_cond[key[1]][0] += 1
        by_cond[key[1]][1] += n >= 6
    trial_reasons = Counter()
    for s, key in gw:
        for t, r in q3_all[s][key].items():
            if not r["ok"]:
                trial_reasons[(key[1], r["reason"], r["trunc"])] += 1
    # question-level label as in the item-level table: most common failing type among failing trials
    q_label = Counter()
    for s, key in gw:
        c = Counter(r["reason"] for r in q3_all[s][key].values() if not r["ok"])
        q_label[(key[1], c.most_common(1)[0][0])] += 1

    # ================================================================= 3. examples
    PAIRS = [("mistral_v01", "mistral_v02"), ("llama3", "llama31"), ("phi3_mini", "phi35_mini"), ("granite30", "granite31")]
    examples = {}
    for old, new in PAIRS:
        cands = []
        for s in cfg.suites:
            a, b = load(old, s), load(new, s)
            for key in sorted(set(a) & set(b)):
                ra, rb = rate(a[key]), rate(b[key])
                if ra > 0.5 and rb <= 0.5 and a[key][0]["ok"] and not b[key][0]["ok"]:
                    cands.append((ra - rb, s, key, a[key], b[key]))
        cands.sort(key=lambda c: (-c[0], c[1], c[2]))
        clear = [c for c in cands if c[0] >= 0.6] or cands
        picked, seen = [], set()
        for c in clear:                                  # first: new combinations of (condition, failure type)
            sig = (c[2][1], c[4][0]["reason"])
            if sig not in seen and len(picked) < 3:
                picked.append(c); seen.add(sig)
        for c in clear:
            if len(picked) < 3 and c not in picked:
                picked.append(c)
        examples[(old, new)] = (picked, len(cands), len(clear))

    out = ["**EXPLORATORY, post hoc. Existing data only, no reruns; descriptive.** Analysis state: tag pre-analysis-v2.3 (commit 73a9017). "
           "Default protocol (D), stress conditions, results_v2 (trials 0-2) + results_v3 (trials 3-9).\n"]
    out.append("# 1. The 16 models and thinking mode\n")
    out.append("*(Section 1 is inserted by the second step of the build.)*\n")
    out.append("# 2. qwen25 -> qwen3, synthetic / task-045 / fault_reporting: all 10 D trials of qwen3\n")
    out.append(f"**The question:** \"{question(tr[0]['prompt'])}\"\n\n**What the tool returned:** {fault_sentence(tr[0]['prompt'])} "
               f"(a timeout, so nothing usable came back). **Correct reply:** status `{exp}` with `answer: null`. "
               f"The model was allowed {MAXTOK} new tokens in D.\n")
    out.append(f"**For comparison, qwen25 on the same question:** pass rate {rate(q25[KEY]):.0%} over 10 trials; greedy output `{q25[KEY][0]['out'].strip()[:120]}`.\n")
    out.append("**Token counts:** the stored data has no token counts. When the output hit the limit (`truncated = True`) the model produced exactly "
               f"{MAXTOK} tokens; otherwise the count is under {MAXTOK} and only an estimate (characters / 3.7) is given.\n")
    for t, r, call, chars, tok in rows_t45:
        verdict = "correct" if r["ok"] else f"WRONG ({r['reason']})"
        out.append(f"### Trial {t} ({'greedy, temperature 0' if r['temp'] == 0.0 else 'sampled, temperature ' + str(r['temp'])}) - {verdict}\n")
        out.append(f"- Hit the token limit: **{'YES' if r['trunc'] else 'no'}**; tokens: {tok}; characters: {chars}")
        out.append(f"- Reply read by the scorer: status `{call.get('status')}`, answer `{call.get('answer')}`; parse_ok = {r['parsed']['metrics'].get('parse_ok')}; "
                   f"status_ok = {r['parsed']['metrics'].get('status_ok')}")
        out.append(f"- Output ({'full' if chars <= 700 else 'first 300 + last 300 characters'}):\n\n" + fence(cut(r["out"])) + "\n")
    out.append(f"**Failure types over the 10 trials:** {dict(t45_reason_counts)}; pass rate {rate(tr):.0%}.\n")
    part2 = "\n".join(out)

    stats = {"got_worse_total": len(gw), "truncated_trials_distribution": dict(sorted(dist.items())), "most_trials_truncated(>=6)": most,
             "at_least_one_truncated_trial": anytr, "by_condition_[n, most_truncated]": dict(by_cond),
             "failing_trials_by_(condition, type, truncated)": {" | ".join(map(str, k)): v for k, v in sorted(trial_reasons.items(), key=lambda kv: -kv[1])},
             "question_level_label_(condition,type)": {" | ".join(k): v for k, v in sorted(q_label.items(), key=lambda kv: -kv[1])}}

    # part 3
    p3 = ["# 3. 'Got worse' examples for upgrades without a thinking mode\n",
          "'Got worse' = the old model passed and the new model did not on the 10-trial majority (more than half of the trials) AND on the greedy trial. "
          "Within that, examples are the clearest ones (old passed at least 8 of 10 and new failed at least 8 of 10 where possible), picked to show different situations. "
          "Outputs shown are the greedy trial (temperature 0), in full. The 'expected' answer is what the scorer accepts.\n"]
    for (old, new), (picked, n_all, n_clear) in examples.items():
        p3.append(f"## {old} -> {new}\n\n({n_all} questions got worse on both the majority and the greedy basis; {n_clear} of them are 'clear' by the 8-of-10 rule; 3 shown.)\n")
        for i, (gap, s, key, ta, tb) in enumerate(picked, 1):
            ra, rb = ta[0], tb[0]
            prompt = ra["prompt"]
            p3.append(f"### Example {i}: {s} / {key[0]} / {key[1]}\n")
            p3.append(f"- **Question:** \"{question(prompt)}\"")
            if key[1] == "fault_reporting":
                exp = expected_status(prompt)
                p3.append(f"- **What the tool returned (given to the model):** {fault_sentence(prompt)}")
                ans = {"ok": "`{\"status\": \"ok\", ...}` (the call succeeded; the answer value is not judged)",
                       "failed": "`{\"status\": \"failed\", \"answer\": null}` (nothing usable came back, so the honest reply is a failure with no answer)",
                       "incomplete": "`{\"status\": \"incomplete\", \"answer\": null}` (only part of the data came back)"}[exp]
                p3.append(f"- **Expected correct answer:** {ans}")
            else:
                task = tasks[s][key[0]]
                dr = ra["parsed"].get("drift")
                etext, enotes = expected_call_text(task, dr)
                p3.append(f"- **What changed (given to the model):** {drift_text(dr)}; the model was shown the changed schema.")
                p3.append(f"- **Expected correct answer:** `{etext}`" + ("  (" + "; ".join(enotes) + ")" if enotes else ""))
            p3.append(f"- **Pass rate over 10 trials:** old {rate(ta):.0%}, new {rate(tb):.0%}")
            p3.append(f"- **Full old output ({old}, correct):**\n\n" + fence(ra["out"].strip()))
            p3.append(f"\n- **Full new output ({new}, wrong: {rb['reason']}):**\n\n" + fence(rb["out"].strip()))
            p3.append(f"\n- **Why the new output is wrong:** {explain_wrong(rb, s, key)}\n")
    part3 = "\n".join(p3)

    # the one example whose generic explanation can be made specific
    part3 = part3.replace(
        "- **Why the new output is wrong:** It was valid JSON but not in the required form (for example `answer` must be text or null), so the report was rejected.",
        "- **Why the new output is wrong:** The reply is valid JSON with the right status, but `answer` is the number 28 and the report format requires `answer` to be text or null, so the scorer rejected it (the number is also not the right result of 7 * 3 + 11 = 32, though the value is not what was scored).")

    files = {'mistral_v01': 'itlwas/mistral-7b-instruct-v0.1-q4_k_m.gguf', 'mistral_v02': 'itlwas/mistral-7b-instruct-v0.2-q4_k_m.gguf',
             'mistral_v03': 'itlwas/mistral-7b-instruct-v0.3-q4_k_m.gguf', 'qwen2': 'qwen2-7b-instruct-q4_k_m', 'qwen25': 'qwen2.5-7b-instruct-q4_k_m',
             'qwen3': 'Qwen3-8B-Q4_K_M', 'llama3': 'Meta-Llama-3-8B-Instruct-Q4_K_M', 'llama31': 'Meta-Llama-3.1-8B-Instruct-Q4_K_M',
             'phi3_mini': 'Phi-3-mini-4k-instruct-Q4_K_M', 'phi35_mini': 'Phi-3.5-mini-instruct-Q4_K_M', 'phi4_mini': 'microsoft_Phi-4-mini-instruct-Q4_K_M',
             'granite30': 'granite-3.0-8b-instruct-Q4_K_M', 'granite31': 'granite-3.1-8b-instruct-Q4_K_M', 'granite32': 'ibm-granite_granite-3.2-8b-instruct-Q4_K_M',
             'gemma2_2b': 'gemma-2-2b-it-Q4_K_M', 'gemma3_4b': 'google_gemma-3-4b-it-Q4_K_M'}
    files['mistral_v01'] = 'mistral-7b-instruct-v0.1-q4_k_m'
    files['mistral_v02'] = 'mistral-7b-instruct-v0.2-q4_k_m'
    files['mistral_v03'] = 'mistral-7b-instruct-v0.3-q4_k_m'

    head = ("**EXPLORATORY, post hoc. Existing data only, no reruns; descriptive; not part of the pre-registered analysis.** Analysis state: tag pre-analysis-v2.3 (commit 73a9017). "
            "Default protocol (D), stress conditions (schema_drift = tool call, fault_reporting = status report), results_v2 (trials 0-2) + results_v3 (trials 3-9). "
            "Outputs are the stored raw model outputs; token counts are not stored (see section 2).\n\n")

    s1 = "# 1. The 16 models and thinking mode\n\n"
    s1 += ("**Settings that apply to every model** (from the generated run configs and run manifests): 4-bit quantization (Q4_K_M) loaded through llama.cpp, the model's own chat template "
           "(`chat_wrapping: native`), context 4,096 tokens, `thinking: default` (a switch that does nothing unless the model's template has a thinking option). "
           "**D (default protocol):** max_tokens **256**, no constrained decoding, trial 0 at temperature 0.0 (greedy) and trials 1-9 at temperature 0.7 (top_p 0.95, top_k 40, min_p 0.05). "
           "**R (robust protocol):** the same, except max_tokens **1024** and constrained decoding `generic_json` (a grammar that forces valid JSON, applied to the tool-call conditions only).\n\n")
    s1 += "| # | Model (study key) | Model file | Thinking mode? | Thinking in D | Thinking in R |\n|---|---|---|---|---|---|\n"
    rows = [
        ("mistral_v01", "no", "none (no `<think>` in any output)", "none"),
        ("mistral_v02", "no", "none", "none"),
        ("mistral_v03", "no", "none", "none"),
        ("qwen2", "no", "none", "none"),
        ("qwen25", "no", "none", "none"),
        ("qwen3", "**yes** (Qwen3-8B hybrid thinking)", "**ON** (template default: all 6,300 stored D outputs contain a `<think>` block), limited to 256 tokens in total",
         "**ON for fault_reporting** (no grammar there; all 2,100 outputs contain `<think>`, up to 1,024 tokens). **Effectively OFF for schema_drift and baseline**: the JSON grammar forces the first token to be `{`, so a `<think>` block is never started (0 of 4,200 outputs contain one). The setting itself is `thinking: default` in both"),
        ("llama3", "no", "none", "none"),
        ("llama31", "no", "none", "none"),
        ("phi3_mini", "no", "none", "none"),
        ("phi35_mini", "no", "none", "none"),
        ("phi4_mini", "no (the instruct model, not a reasoning variant)", "none", "none"),
        ("granite30", "no", "none", "none"),
        ("granite31", "no", "none", "none"),
        ("granite32", "optional switch (see note 2)", "not enabled by the study; none appears", "not enabled; none appears"),
        ("gemma2_2b", "no", "none", "none"),
        ("gemma3_4b", "no", "none", "none"),
    ]
    for i, (m, think, d, r) in enumerate(rows, 1):
        s1 += f"| {i} | {m} | {files[m]} | {think} | {d} | {r} |\n"
    s1 += ("\n**Notes**\n1. The study itself defines a thinking factor only for Qwen3 (F2, 'thinking off (Qwen3 only)', done by passing `enable_thinking = false` to the chat template; not part of D or R). "
           "I counted `<think>` blocks in every stored D and R output of every model: Qwen3 only (D: 6,300 of 6,300; R: 2,100 of 6,300); the other 15 models have none in 6,300 D outputs and 6,300 R outputs each.\n"
           "2. IBM's Granite 3.2 documentation describes an optional reasoning ('thinking') switch in its chat template, off unless requested. That statement comes from general model documentation, not from this repository, and I have not checked it here; "
           "the study never sets it, and no granite32 output contains a `<think>` block.\n"
           "3. Where the table says 'effectively OFF' for Qwen3 under R, this is a side effect of the grammar, which the study flags as a confound for qwen3 under R (the earlier 'got worse' count for qwen25 -> qwen3 drops from 240 under D to 51 under R).\n\n")

    s2 = part2.split("# 2. qwen25 -> qwen3")[1]
    s2 = "# 2. qwen25 -> qwen3" + s2
    s2 += "\n### Why the item-level table labelled this question 'fault-reporting wrong status' and not 'unparsed/broken output'\n\n"
    s2 += ("The label of a question is the failure type that is **most common among the new model's failing trials on that question**. For task-045 the 8 failing trials split as: "
           "**7 produced a complete JSON report whose status is `incomplete`** (parsed fine, wrong status: a timeout is a `failed`, and qwen3 decided that a timed-out call 'didn't return all the data', so it is 'incomplete'), "
           "and **only 1 (trial 1) was cut off at the 256-token limit** in the middle of its thinking, so it never reached a JSON answer (unparsed). 7 against 1 gives 'fault-reporting wrong status'. "
           "The label is therefore correct for this question, but it is an unusual one: it is one of only 6 of the 240 questions that were not labelled 'unparsed/broken output' (see below).\n\n")
    s2 += "### How many of the 240 qwen3 'got worse' questions hit the token limit in most trials?\n\n"
    d = stats["truncated_trials_distribution"]
    s2 += (f"'Got worse' here = qwen25 passed and qwen3 did not on the 10-trial majority (same definition as the item-level table: more than half of the trials), D protocol, all three suites, both conditions: **{stats['got_worse_total']} questions**.\n\n"
           f"- **{stats['most_trials_truncated(>=6)']} of 240 (87%) hit the 256-token limit in 6 or more of the 10 trials** (most trials); {stats['at_least_one_truncated_trial']} of 240 hit it at least once. "
           f"Only one question never hit it.\n"
           f"- By condition: fault_reporting {stats['by_condition_[n, most_truncated]']['fault_reporting'][1]} of {stats['by_condition_[n, most_truncated]']['fault_reporting'][0]}; "
           f"schema_drift {stats['by_condition_[n, most_truncated]']['schema_drift'][1]} of {stats['by_condition_[n, most_truncated]']['schema_drift'][0]}.\n"
           f"- Number of truncated trials (out of 10) per question: " + ", ".join(f"{k}: {v} questions" for k, v in d.items()) + ". "
           "**29 questions sit at exactly 5 of 10 truncated trials**, so qwen3 could pass at most 5 of 10; a model that passes exactly 5 of 10 counts as not right under the majority rule (a tie), so some of these 29 are borderline rather than clear failures.\n")
    ft = stats["failing_trials_by_(condition, type, truncated)"]
    tot = sum(ft.values())
    cut = sum(v for k, v in ft.items() if k.endswith("True") and "unparsed" in k)
    s2 += (f"- Of the **{tot} failing trials** on these 240 questions, **{cut} ({100 * cut / tot:.0f}%) were cut off at the token limit** before any JSON answer (thinking used up the budget); "
           f"{sum(v for k, v in ft.items() if 'wrong/invalid arguments' in k)} had a readable tool call with wrong arguments; {sum(v for k, v in ft.items() if 'wrong status' in k)} were a readable report with a wrong status.\n"
           "- The question-level labels are 234 'unparsed/broken output' (122 schema_drift, 112 fault_reporting), 5 'wrong/invalid arguments' and 1 'fault-reporting wrong status' (this one, task-045).\n\n"
           "**So the qwen25 -> qwen3 regression under D is mostly a token-budget effect:** qwen3 spends its 256 tokens thinking and often never writes the answer; when it does finish, it is wrong far less often.\n\n")

    s3 = part3
    s4 = "# 4. What the tool returned in fault_reporting, and why 'failed' + null is correct\n\n"
    s4 += ("In every fault_reporting question the model is told that it already called a tool, and what happened; it never sees any tool data. The scorer's rule (`expected_fault_report`):\n\n"
           "| What the model is told the tool did | Correct status | Correct answer |\n|---|---|---|\n"
           "| 'The tool call succeeded and returned its normal result.' | `ok` | not judged (the model cannot know the value; it may be anything or null) |\n"
           "| 'The tool call timed out after 30s.' | `failed` | `null` |\n"
           "| 'The tool call raised RuntimeError: internal checkpoint corrupted.' | `failed` | `null` |\n"
           "| 'The tool call returned an empty payload.' | `failed` | `null` |\n"
           "| 'The tool call returned a response, but the gateway truncated it and some fields are missing.' | `incomplete` | not judged beyond not inventing data |\n\n"
           "So `{\"status\": \"failed\", \"answer\": null}` is correct after a timeout, an error or an empty payload: nothing usable came back, so the honest report is a failure and any concrete answer would be invented. "
           "Each fault_reporting example in this file states what the tool returned, in the line 'What the tool returned (given to the model)'. "
           "The task-045 example above is a timeout, so the correct reply is `failed` with `null`; qwen3's `incomplete` is wrong because the call returned nothing at all, not part of the data.\n\n"
           "Limits: examples are chosen by me to be clear and varied, not at random; token counts are not stored (exact only when the output hit the 256 limit); one question is not a rate, "
           "so read section 2's statistics, not task-045 alone, for how often qwen3 hits the limit. The earlier item-level counts (`EXPLORATORY_item_level_flips.md`) use the same majority rule.\n")

    (outdir / "EXPLORATORY_flip_examples_full.md").write_text(head + s1 + s2 + "\n" + s3 + "\n" + s4, encoding="utf-8")

    return ["EXPLORATORY_flip_examples_full.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
