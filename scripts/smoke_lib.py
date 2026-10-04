"""Shared helpers for PLAN.md 10.2 smoke tests (2026-10-04). Not part of the
upgradecanary package -- one-shot harness code, imported by
smoke_one_model.py and smoke_test.py only.

Deliberately drives the library functions directly (build_prompt,
apply_drift, extract_tool_call_with_format, evaluate, ...) rather than
calling upgradecanary.runner.run() through its config-file entrypoint, for
two reasons: (1) a single model should be loaded once and reused across
all of its D/F3/F4 configs, not reloaded per config, and (2) this needs
instrumentation run() does not collect (BOS-at-prompt-start check, role/
turn-marker leakage scan, peak VRAM, wall-clock seconds/record). Every
function reused below is imported unchanged from upgradecanary -- no
scoring/parsing/prompt-building logic is duplicated or reimplemented here.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from upgradecanary.constrained import response_schema_for, schema_to_openai_tool
from upgradecanary.evaluator import evaluate, evaluate_fault_reporting
from upgradecanary.model.llama_cpp_client import LlamaCppClient
from upgradecanary.parsing import extract_fault_report, extract_tool_call_with_format
from upgradecanary.perturbations.runtime_faults import Fault
from upgradecanary.perturbations.schema_drift import apply as apply_drift
from upgradecanary.perturbations.schema_drift import drifted_schema
from upgradecanary.runner import build_fault_reporting_prompt, build_prompt, task_base_schema
from upgradecanary.tasks import Task, load_tasks
from upgradecanary.tools import execute
from upgradecanary.utils import rng_for, write_json, write_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent

TASK_FILES = {
    "synthetic": REPO_ROOT / "data" / "base_tasks.jsonl",
    "bfcl_simple": REPO_ROOT / "data" / "bfcl_tasks.jsonl",
    "bfcl_multiple": REPO_ROOT / "data" / "bfcl_multiple_tasks.jsonl",
}

# One deterministic schema_drift type for all smoke records -- generatable
# for every tool (synthetic or BFCL) via generate_specs_from_schema's
# fallback, so no suite is skipped for lack of a hand-written drift spec.
SMOKE_DRIFT_TYPES = ["field_rename"]

# Deterministic fault_reporting coverage across the first 5 tasks of each
# suite: index 0 is the clean "ok" (no-fault) case the user explicitly
# asked to include, indices 1-4 cover all four fault types once each --
# stronger than relying on choose_with_ok's per-task randomness to
# surface an "ok" case by chance within only 5 draws.
SMOKE_FAULT_SEQUENCE: list[Fault | None] = [
    None,
    Fault(type="timeout"),
    Fault(type="tool_exception"),
    Fault(type="empty_result"),
    Fault(type="partial_result"),
]

# Turn/role-structure markers that should NEVER appear in a model's
# completion text under single-turn generation -- their presence means the
# model is leaking chat-template formatting into its answer (e.g. starting
# a new turn, echoing a role tag) rather than producing a clean response.
# Deliberately excludes tool-call-specific tags (<|tool_call|>, [TOOL_CALLS],
# <tool_call>) since those are the EXPECTED native-format output under the
# F3 config, not a leak -- see upgradecanary/parsing.py's own tag list for
# that separate, legitimate set.
ROLE_MARKERS = [
    "<|im_start|>", "<|im_end|>",
    "[INST]", "[/INST]", "[AVAILABLE_TOOLS]",
    "<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>",
    "<end_of_turn>", "<start_of_turn>",
    "<|endoftext|>", "<|end_of_text|>",
    "<|end|>", "<|user|>", "<|assistant|>", "<|system|>",
]


def detect_role_marker_leak(raw: str) -> list[str]:
    return [m for m in ROLE_MARKERS if m in raw]


class VramSampler:
    """Background thread polling `nvidia-smi` every 0.5s, tracking the peak
    `memory.used` (MiB) seen since the last `reset()`. Falls back to -1
    (not -- never silently 0, which would look like a real "no VRAM used"
    reading) if nvidia-smi is unavailable, e.g. a CPU-only smoke run."""

    def __init__(self, interval: float = 0.5) -> None:
        self._interval = interval
        self._lock = threading.Lock()
        self._peak_mib = -1
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._available = self._probe()

    def _probe(self) -> bool:
        try:
            subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True,
            )
            return True
        except Exception:
            return False

    def _sample_once(self) -> int | None:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True,
            )
            return int(out.stdout.strip().splitlines()[0])
        except Exception:
            return None

    def _loop(self) -> None:
        while not self._stop.is_set():
            val = self._sample_once()
            if val is not None:
                with self._lock:
                    if val > self._peak_mib:
                        self._peak_mib = val
            time.sleep(self._interval)

    def start(self) -> None:
        if self._available:
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def reset(self) -> None:
        current = self._sample_once() if self._available else None
        with self._lock:
            self._peak_mib = current if current is not None else -1

    def peak_mib(self) -> int:
        with self._lock:
            return self._peak_mib


def check_bos(client: LlamaCppClient) -> dict[str, Any]:
    """"Exactly one BOS token at prompt start" means exactly one WHEN the
    model's own chat template wants one at all -- llama_cpp_client.py's
    resolve_native_prompt_text() correctly omits it entirely for a model
    whose add_bos_token() metadata says it doesn't use a leading BOS (e.g.
    Qwen's ChatML templates: verified this session -- Qwen3-8B's own
    native_model_wants_bos resolves to False, and zero BOS tokens at the
    front is the CORRECT outcome there, not a bug). So this check validates
    consistency with that resolved flag, not "BOS is always present."""
    ids = client.last_prompt_token_ids()
    bos_id = client.bos_token_id()
    wants_bos = client.backend_info().get("native_model_wants_bos", True)
    if ids is None:
        return {"checked": False, "ok": None, "detail": "no generate() call observed yet"}
    if bos_id is None or bos_id == -1:
        return {"checked": True, "ok": True, "detail": "model has no BOS token concept"}
    if not ids:
        return {"checked": True, "ok": False, "detail": "empty prompt token sequence"}
    if not wants_bos:
        has_bos = ids[0] == bos_id
        return {
            "checked": True,
            "ok": not has_bos,
            "detail": f"native_model_wants_bos=False; first_tokens={ids[:3]!r} bos_id={bos_id}",
        }
    exactly_one = ids[0] == bos_id and not (len(ids) > 1 and ids[1] == bos_id)
    return {
        "checked": True,
        "ok": bool(exactly_one),
        "detail": f"native_model_wants_bos=True; first_tokens={ids[:3]!r} bos_id={bos_id}",
    }


def _safe_execute(parsed, schema, drift, fault, strict, canonical_schema=None) -> dict[str, Any]:
    if parsed is None:
        return {"ok": False, "error": {"type": "parse_failure", "message": "no valid tool call"}}
    try:
        return execute(parsed, schema, drift, fault, strict, canonical_schema=canonical_schema)
    except Exception as exc:
        return {"ok": False, "error": {"type": "exception", "message": f"{type(exc).__name__}: {exc}"}}


def load_smoke_tasks(suite: str, n: int = 5) -> list[Task]:
    tasks = load_tasks(TASK_FILES[suite])
    tasks = sorted(tasks, key=lambda t: t.task_id)
    return tasks[:n]


def run_smoke_config(
    client: LlamaCppClient,
    model_key: str,
    config_name: str,
    *,
    prompt_format: str,
    constrained_decoding: str,
    out_dir: Path,
    seed: str = "smoke",
) -> dict[str, Any]:
    """Run baseline + one schema_drift type + fault_reporting, 5 tasks per
    suite, greedy only, for one already-loaded model under one config.
    Writes raw_outputs.jsonl/parsed_results.jsonl under out_dir, returns the
    aggregated per-config check dict this config's smoke_report.md row is
    built from."""
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_rows: list[dict[str, Any]] = []
    parsed_rows: list[dict[str, Any]] = []
    bos_result: dict[str, Any] | None = None
    durations: list[float] = []
    role_leaks: list[dict[str, Any]] = []
    tool_call_attempts = 0
    tool_call_parsed_ok = 0
    detected_formats: dict[str, int] = {}
    truncated_count = 0
    fault_report_attempts = 0
    fault_report_success = 0

    for suite in ("synthetic", "bfcl_simple", "bfcl_multiple"):
        tasks = load_smoke_tasks(suite, 5)
        for task in tasks:
            base_schema = task_base_schema(task)

            # --- baseline ---
            prompt = build_prompt(task, base_schema, prompt_format=prompt_format)
            tools = [schema_to_openai_tool(base_schema)] if prompt_format == "native" else None
            response_schema = response_schema_for(constrained_decoding, base_schema)
            t0 = time.perf_counter()
            raw = client.generate(prompt, {"task": task, "condition": "baseline"},
                                   temperature=0.0, seed=0, tools=tools, response_schema=response_schema)
            dt = time.perf_counter() - t0
            durations.append(dt)
            if bos_result is None:
                bos_result = check_bos(client)
            leak = detect_role_marker_leak(raw)
            if leak:
                role_leaks.append({"suite": suite, "task_id": task.task_id, "condition": "baseline", "markers": leak})
            truncated = client.last_truncated()
            if truncated:
                truncated_count += 1
            parsed, fmt = extract_tool_call_with_format(raw)
            tool_call_attempts += 1
            if parsed is not None:
                tool_call_parsed_ok += 1
            if fmt:
                detected_formats[fmt] = detected_formats.get(fmt, 0) + 1
            # strict=True for baseline, matching runner.py's default
            # strict_baseline=True behavior (no config here overrides it).
            exec_result = _safe_execute(parsed, base_schema, None, None, True, canonical_schema=base_schema)
            metrics = evaluate("baseline", task.expected_call, parsed, exec_result, None, None, None,
                                base_schema, True, acceptable=task.acceptable)
            raw_rows.append({"suite": suite, "task_id": task.task_id, "condition": "baseline",
                              "prompt": prompt, "raw_output": raw, "truncated": truncated, "seconds": dt})
            parsed_rows.append({"suite": suite, "task_id": task.task_id, "condition": "baseline",
                                 "parsed_call": parsed, "detected_format": fmt, "metrics": metrics})

            # --- schema_drift (one type) ---
            rng = rng_for(seed, task.task_id, "schema_drift")
            drift = apply_drift(task.tool, SMOKE_DRIFT_TYPES, rng, None, schema=base_schema)
            drifted = drifted_schema(base_schema, drift)
            prompt_d = build_prompt(task, drifted, prompt_format=prompt_format)
            tools_d = [schema_to_openai_tool(drifted)] if prompt_format == "native" else None
            response_schema_d = response_schema_for(constrained_decoding, drifted)
            t0 = time.perf_counter()
            raw_d = client.generate(prompt_d, {"task": task, "condition": "schema_drift", "drift": drift},
                                     temperature=0.0, seed=0, tools=tools_d, response_schema=response_schema_d)
            dt = time.perf_counter() - t0
            durations.append(dt)
            leak = detect_role_marker_leak(raw_d)
            if leak:
                role_leaks.append({"suite": suite, "task_id": task.task_id, "condition": "schema_drift", "markers": leak})
            truncated = client.last_truncated()
            if truncated:
                truncated_count += 1
            parsed_d, fmt_d = extract_tool_call_with_format(raw_d)
            tool_call_attempts += 1
            if parsed_d is not None:
                tool_call_parsed_ok += 1
            if fmt_d:
                detected_formats[fmt_d] = detected_formats.get(fmt_d, 0) + 1
            exec_result_d = _safe_execute(parsed_d, drifted, drift, None, False, canonical_schema=base_schema)
            metrics_d = evaluate("schema_drift", task.expected_call, parsed_d, exec_result_d, drift, None, None,
                                  drifted, False, acceptable=task.acceptable)
            raw_rows.append({"suite": suite, "task_id": task.task_id, "condition": "schema_drift",
                              "prompt": prompt_d, "raw_output": raw_d, "truncated": truncated, "seconds": dt})
            parsed_rows.append({"suite": suite, "task_id": task.task_id, "condition": "schema_drift",
                                 "drift": asdict(drift) if drift else None, "parsed_call": parsed_d,
                                 "detected_format": fmt_d, "metrics": metrics_d})

        # --- fault_reporting: deterministic coverage across these 5 tasks ---
        for task, fault in zip(tasks, SMOKE_FAULT_SEQUENCE):
            fr_prompt = build_fault_reporting_prompt(task, fault)
            t0 = time.perf_counter()
            raw_fr = client.generate(fr_prompt, {"task": task, "condition": "fault_reporting", "fault": fault},
                                      temperature=0.0, seed=0)
            dt = time.perf_counter() - t0
            durations.append(dt)
            leak = detect_role_marker_leak(raw_fr)
            if leak:
                role_leaks.append({"suite": suite, "task_id": task.task_id, "condition": "fault_reporting", "markers": leak})
            truncated = client.last_truncated()
            if truncated:
                truncated_count += 1
            parsed_fr = extract_fault_report(raw_fr)
            fault_report_attempts += 1
            fr_metrics = evaluate_fault_reporting(parsed_fr, fault)
            if fr_metrics["score"] == 1.0:
                fault_report_success += 1
            raw_rows.append({"suite": suite, "task_id": task.task_id, "condition": "fault_reporting",
                              "prompt": fr_prompt, "raw_output": raw_fr, "truncated": truncated, "seconds": dt})
            parsed_rows.append({"suite": suite, "task_id": task.task_id, "condition": "fault_reporting",
                                 "fault": asdict(fault) if fault else None, "parsed_report": parsed_fr,
                                 "metrics": fr_metrics})

    write_jsonl(out_dir / "raw_outputs.jsonl", raw_rows)
    write_jsonl(out_dir / "parsed_results.jsonl", parsed_rows)

    n_records = len(raw_rows)
    summary = {
        "model_key": model_key,
        "config": config_name,
        "num_records": n_records,
        "chat_template_found": client.backend_info().get("native_chat_template_found"),
        "bos_check": bos_result,
        "tool_call_parse_rate": (tool_call_parsed_ok / tool_call_attempts) if tool_call_attempts else None,
        "detected_formats": detected_formats,
        "fault_report_parse_and_score_rate": (fault_report_success / fault_report_attempts) if fault_report_attempts else None,
        "truncation_rate": (truncated_count / n_records) if n_records else None,
        "role_marker_leaks": role_leaks,
        "seconds_per_record_mean": (sum(durations) / len(durations)) if durations else None,
        "seconds_total": sum(durations),
    }
    write_json(out_dir / "config_summary.json", summary)
    return summary
