"""W6 labeling files: prompt splitting, output cleaning, and merging filled sheets. FAKE data only."""

import csv

import pytest

from scripts.phase2.w6_build import NO_FAULT, NO_SCHEMA, clean_output, split_prompt
from scripts.phase2.w6_merge import RULE, main as merge_main, merge, read_filled

HEAD = "You are an agent that answers questions by calling tools.\n"
DRIFT = (HEAD + 'Available tool schema:\n{\n  "tools": []\n}\nReply with ONLY a single JSON object of the form {"name": <tool name>, '
         '"arguments": {<args>}}. No markdown fences.\nQuestion: What is 2+2?\nAnswer:')
FAULT = (HEAD + "Question: What is the weather in Berlin?\nYou already called the get_weather tool for this question. The tool call "
         'timed out after 30s.\nStatus definitions: "ok" means usable data; "failed" means an error.\nReply with ONLY a single '
         'JSON object of the form {"status": "ok" | "failed", "answer": <string or null>}.\nAnswer:')


def test_split_schema_drift_prompt():
    p = split_prompt(DRIFT, "schema_drift")
    assert p["request"] == "What is 2+2?" and p["fault"] == NO_FAULT
    assert p["tool_schema"].startswith("{") and p["instructions"].startswith("Reply with ONLY")


def test_split_fault_reporting_prompt():
    p = split_prompt(FAULT, "fault_reporting")
    assert p["request"] == "What is the weather in Berlin?" and p["tool_schema"] == NO_SCHEMA
    assert p["fault"] == "You already called the get_weather tool for this question. The tool call timed out after 30s."
    assert p["instructions"].startswith("Status definitions:") and "Reply with ONLY" in p["instructions"]


def test_unexpected_layout_is_refused():
    with pytest.raises(ValueError):
        split_prompt("Something else\nAnswer:", "schema_drift")
    with pytest.raises(ValueError):
        split_prompt(DRIFT, "fault_reporting")


def test_template_tokens_are_stripped_and_counted():
    out, n = clean_output('<|im_start|>assistant\n{"a": 1}<|im_end|> [/INST]</s>')
    assert n == 4 and out.strip() == 'assistant\n{"a": 1}'.strip() and "<|" not in out and "[/INST]" not in out
    assert clean_output('<think>x</think>{"a": 1}') == ('<think>x</think>{"a": 1}', 0)        # think blocks are kept
    assert clean_output(None) == ("", 0)


KEY = {"W6-001": "correct", "W6-002": "wrong", "W6-003": "wrong"}


def test_merge_keeps_unsure_as_a_class_and_can_drop_it():
    raters = {"rater1": {"W6-001": "correct", "W6-002": "wrong", "W6-003": "unsure"},
              "rater2": {"W6-001": "correct", "W6-002": "correct", "W6-003": "wrong"}}
    full, no_unsure, problems = merge(KEY, raters)
    assert problems == [] and len(full) == 9 and len(no_unsure) == 8
    assert {"record_id": "W6-003", "labeler": "rater1", "label": "unsure"} in full
    assert not any(r["label"] == "unsure" for r in no_unsure)
    assert {r["labeler"] for r in full} == {RULE, "rater1", "rater2"}
    assert [r["label"] for r in full if r["labeler"] == RULE] == ["correct", "wrong", "wrong"]


def test_merge_refuses_blank_missing_unknown_and_bad_labels():
    _, _, p = merge(KEY, {"r": {"W6-001": "", "W6-002": "wrong", "W6-003": "yes"}})
    assert any("no label" in x for x in p) and any("other than" in x for x in p)
    _, _, p = merge(KEY, {"r": {"W6-001": "correct", "W6-009": "wrong"}})
    assert any("not in the key" in x for x in p) and any("missing" in x for x in p)


def _write_sheet(path, labels):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "label (correct / wrong / unsure)"])
        w.writerows(labels.items())


def test_command_line_end_to_end_with_two_raters_and_with_one(tmp_path, capsys):
    key = tmp_path / "key.csv"
    key.write_text("item_id,rule_label\n" + "".join(f"{k},{v}\n" for k, v in KEY.items()), encoding="utf-8")
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    _write_sheet(a, {"W6-001": "Correct ", "W6-002": "wrong", "W6-003": "unsure"})
    _write_sheet(b, {"W6-001": "correct", "W6-002": "wrong", "W6-003": "wrong"})
    out = tmp_path / "merged"
    assert merge_main(["--key", str(key), "--rater", f"rater1={a}", "--rater", f"rater2={b}", "--out-dir", str(out)]) == 0
    rows = list(csv.DictReader(open(out / "labels_unsure_as_class.csv", encoding="utf-8")))
    assert list(rows[0]) == ["record_id", "labeler", "label"] and len(rows) == 9
    assert read_filled(a)["W6-001"] == "correct"                                          # case and spaces are normalised
    one = tmp_path / "one"
    assert merge_main(["--key", str(key), "--rater", f"rater1={a}", "--out-dir", str(one)]) == 0
    assert {r["labeler"] for r in csv.DictReader(open(one / "labels_unsure_as_class.csv", encoding="utf-8"))} == {RULE, "rater1"}
    _write_sheet(b, {"W6-001": "correct"})
    assert merge_main(["--key", str(key), "--rater", f"rater2={b}", "--out-dir", str(tmp_path / "bad")]) == 1
    assert "NOT MERGED" in capsys.readouterr().out and not (tmp_path / "bad").exists()


def test_xlsx_round_trip(tmp_path):
    pytest.importorskip("openpyxl")
    from scripts.phase2.w6_build import write_xlsx
    items = [{"item_id": "W6-001", "condition": "schema_drift", "tool_schema": "{}", "request": "r", "fault": NO_FAULT,
              "instructions": "i", "output": "o"}]
    path = tmp_path / "s.xlsx"
    write_xlsx(items, path)
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb["items"]
    ws["H2"] = "Wrong"
    wb.save(path)
    assert read_filled(path) == {"W6-001": "wrong"}
