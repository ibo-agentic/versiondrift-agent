"""W6 human labels: build the labeling files from a draw (DEVIATIONS.md 2026-11-14, entry l).

    python -m scripts.phase2.w6_build --sample w6_labels/private/sample.json \
        --raters-dir w6_labels/for_raters --private-dir w6_labels/private

Writes labels_rater1.xlsx and labels_rater2.xlsx (identical, same random order), labels_key.csv and leak_check.json.
Raters see: item id, condition, tool schema (schema_drift items), user request, injected fault (the tool-status
statement on fault_reporting items), the instructions the model was given, the model's raw output (chat-template
tokens stripped), and empty columns for the label (correct / wrong / unsure) and a comment. Model, protocol, trial,
task id and the rule's verdict go to the key file only. The order is a permutation drawn with seed 20261020.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

SEED = 20261020
CELL_LIMIT = 32000                       # Excel's hard limit is 32,767 characters per cell
NO_SCHEMA = "(no tool schema: this is a fault-reporting item; the tool was already called)"
NO_FAULT = "none (schema-drift item)"
LABELS = ("correct", "wrong", "unsure")

# chat-template tokens that could name the model family (none are expected in the stored outputs)
TEMPLATE_RE = re.compile(
    r"<\|[^|<>\n]{1,40}\|>|<</?SYS>>|\[/?INST\]|</?s>|<start_of_turn>|<end_of_turn>|\[TOOL_CALLS\]|<\|?eot_id\|?>"
    r"|<\|?begin_of_text\|?>|<\|?end_of_text\|?>")
LEAK_RES = {
    "model_or_vendor_name": re.compile(r"(?i)\b(mistral|mixtral|qwen\d*|llama[- ]?\d*|phi[- ]?\d+|granite|gemma\d*|ibm|meta|microsoft|google|alibaba|openai|chatgpt|gpt-?\d|anthropic|claude)\b"),
    "protocol_word": re.compile(r"(?i)\b(protocol|grammar|constrained|robust|aa2|kaggle|laptop|quantiz\w*|q[2-8]_[0-9a-z_]+)\b"),
    "template_token": TEMPLATE_RE,
    "rule_or_score_word": re.compile(r"(?i)\b(strict[_ ]score|rule verdict|record_score|stress diff)\b"),
}


def split_prompt(prompt: str, condition: str) -> dict:
    """Pull the shown parts out of the stored prompt text. Raises ValueError if the layout is not the expected one."""
    head = "You are an agent that answers questions by calling tools.\n"
    if not prompt.startswith(head) or not prompt.rstrip().endswith("Answer:"):
        raise ValueError("unexpected prompt layout (head/tail)")
    body = prompt[len(head):].rstrip()[: -len("Answer:")].rstrip("\n")
    if condition == "schema_drift":
        m = re.fullmatch(r"Available tool schema:\n(.*?)\n(Reply with ONLY.*?)\nQuestion: (.*)", body, re.S)
        if not m:
            raise ValueError("unexpected schema_drift prompt layout")
        return {"tool_schema": m.group(1).strip(), "instructions": m.group(2).strip(), "request": m.group(3).strip(),
                "fault": NO_FAULT}
    if condition == "fault_reporting":
        m = re.fullmatch(r"Question: (.*?)\n(You already called the .*?)\n(Status definitions:.*?)\n(Reply with ONLY.*)", body, re.S)
        if not m:
            raise ValueError("unexpected fault_reporting prompt layout")
        return {"tool_schema": NO_SCHEMA, "instructions": (m.group(3) + "\n" + m.group(4)).strip(),
                "request": m.group(1).strip(), "fault": m.group(2).strip()}
    raise ValueError(f"unexpected condition {condition}")


def clean_output(text: str | None) -> tuple[str, int]:
    """Strip chat-template tokens; returns (text, number of tokens removed)."""
    text = text or ""
    n = len(TEMPLATE_RE.findall(text))
    return TEMPLATE_RE.sub("", text).strip("\n"), n


def read_record(rec: dict) -> tuple[dict, dict]:
    run_dir = REPO_ROOT / rec["part"]
    line = int(rec["line"])
    with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fh:
        parsed = json.loads(next(x for i, x in enumerate(fh) if i == line))
    with open(run_dir / "raw_outputs.jsonl", encoding="utf-8") as fh:
        raw = json.loads(next(x for i, x in enumerate(fh) if i == line))
    for k in ("task_id", "condition", "trial_index"):
        if parsed[k] != raw[k]:
            raise ValueError(f"parsed/raw mismatch on {k} for {rec['part']} line {line}")
    if parsed["task_id"] != rec["task_id"] or parsed["condition"] != rec["condition"]:
        raise ValueError(f"draw does not match the file at {rec['part']} line {line}")
    return parsed, raw


def build_items(records: list[dict], seed: int = SEED) -> tuple[list[dict], dict]:
    order = np.random.default_rng(seed).permutation(len(records))
    items, stats = [], {"template_tokens_stripped": 0, "retry_outputs": 0, "truncated_for_excel": 0}
    for pos, idx in enumerate(order, start=1):
        rec = records[int(idx)]
        parsed, raw = read_record(rec)
        parts = split_prompt(raw["prompt"], rec["condition"])
        out, n_tok = clean_output(raw["raw_output"])
        if raw.get("retry_raw_output"):
            retry, n2 = clean_output(raw["retry_raw_output"])
            out += "\n\n--- second attempt (after the tool reported an error) ---\n" + retry
            n_tok += n2
            stats["retry_outputs"] += 1
        stats["template_tokens_stripped"] += n_tok
        if len(out) > CELL_LIMIT:
            out = out[:CELL_LIMIT] + "\n[... output cut here because of the spreadsheet cell limit ...]"
            stats["truncated_for_excel"] += 1
        items.append({"item_id": f"W6-{pos:03d}", "condition": rec["condition"], "tool_schema": parts["tool_schema"],
                      "request": parts["request"], "fault": parts["fault"], "instructions": parts["instructions"],
                      "output": out, "rec": rec, "drift": (parsed.get("drift") or {}).get("type"),
                      "fault_type": (parsed.get("fault") or {}).get("type")})
    return items, stats


def write_xlsx(items: list[dict], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "items"
    header = ["item_id", "condition", "tool_schema", "user_request", "injected_fault", "instructions_given_to_the_model",
              "model_output", "label (correct / wrong / unsure)", "comment (optional)"]
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True)
    for it in items:
        ws.append([it["item_id"], it["condition"], it["tool_schema"], it["request"], it["fault"], it["instructions"],
                   it["output"], None, None])
    for col, w in zip("ABCDEFGHI", (9, 15, 60, 40, 40, 45, 60, 18, 35)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "B2"
    dv = DataValidation(type="list", formula1='"correct,wrong,unsure"', allow_blank=True, showErrorMessage=True,
                        errorTitle="Label", error="Use correct, wrong or unsure.")
    ws.add_data_validation(dv)
    dv.add(f"H2:H{len(items) + 1}")
    wb.save(path)


def write_key(items: list[dict], path: Path) -> None:
    cols = ["item_id", "model", "protocol", "suite", "condition", "task_id", "trial", "rule_label", "drift_type",
            "fault_type", "stratum", "run_folder", "line"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for it in items:
            r = it["rec"]
            w.writerow([it["item_id"], r["model"], r["protocol"], r["suite"], r["condition"], r["task_id"], r["trial"],
                        "correct" if r["verdict"] == "pass" else "wrong", it["drift"] or "", it["fault_type"] or "",
                        f"{r['suite']}/{r['verdict']}", r["part"], r["line"]])


def leak_check(items: list[dict], stats: dict) -> dict:
    shown = ("tool_schema", "request", "fault", "instructions", "output")
    out = {"n_items": len(items), **stats, "matches": {}, "retained_hints": {}}
    for name, rx in LEAK_RES.items():
        hits = []
        for it in items:
            for f in shown:
                for m in rx.finditer(it[f]):
                    hits.append({"item": it["item_id"], "field": f, "text": m.group(0)})
        out["matches"][name] = {"count": len(hits), "examples": hits[:12]}
    out["retained_hints"] = {
        "think_block": sum("<think>" in it["output"] for it in items),
        "code_fence": sum("```" in it["output"] for it in items),
        "prose_around_json": sum(not it["output"].lstrip().startswith(("{", "<think>", "```")) for it in items),
        "max_output_chars": max(len(it["output"]) for it in items),
    }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--raters-dir", required=True)
    ap.add_argument("--private-dir", required=True)
    args = ap.parse_args(argv)
    records = json.loads(Path(args.sample).read_text(encoding="utf-8"))["records"]
    items, stats = build_items(records)
    rd, pd_ = Path(args.raters_dir), Path(args.private_dir)
    rd.mkdir(parents=True, exist_ok=True)
    pd_.mkdir(parents=True, exist_ok=True)
    write_xlsx(items, rd / "labels_rater1.xlsx")
    write_xlsx(items, rd / "labels_rater2.xlsx")
    write_key(items, pd_ / "labels_key.csv")
    chk = leak_check(items, stats)
    (pd_ / "leak_check.json").write_text(json.dumps(chk, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if k != "matches" else {n: m["count"] for n, m in v.items()}) for k, v in chk.items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
