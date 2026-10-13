"""Verification of one exported Kaggle run zip -- shared by the notebook's
restore step (resuming from earlier sessions' zips) and by
scripts/import_kaggle_results.py on the laptop. Reads the zip in place; never
extracts, never writes.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import PurePosixPath

import kaggle_plan as plan

RUN_FILES = ("parsed_results.jsonl", "raw_outputs.jsonl", "run_manifest.json", "summary.json")
_CFG_RE = re.compile(r"^[A-Za-z0-9_]+__[A-Za-z0-9_]+__[A-Za-z0-9_]+\.yaml$")


class VerifyResult:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.info: dict = {}

    @property
    def ok(self) -> bool:
        return not self.problems


def _count_lines(zf: zipfile.ZipFile, name: str) -> int:
    n = 0
    with zf.open(name) as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


def verify_run_zip(zip_path, expected_records: int = plan.EXPECTED_RECORDS_PER_RUN) -> VerifyResult:
    res = VerifyResult()
    P = res.problems.append
    try:
        zf = zipfile.ZipFile(zip_path)
    except Exception as exc:  # noqa: BLE001
        P(f"not a readable zip: {exc}")
        return res
    with zf:
        bad = zf.testzip()
        if bad:
            P(f"corrupt member (CRC): {bad}")
            return res
        names = [n for n in zf.namelist() if not n.endswith("/")]
        run_files: dict[str, str] = {}
        triple: set[tuple[str, str, str]] = set()
        run_ids: set[str] = set()
        status_name = None
        cfg_names = []
        for n in names:
            parts = PurePosixPath(n).parts
            if n.startswith("/") or ".." in parts or parts[0] != "results_v2":
                P(f"unexpected path in zip: {n}")
                continue
            if len(parts) == 3 and parts[1] == "_generated_configs":
                if _CFG_RE.match(parts[2]):
                    cfg_names.append(n)
                else:
                    P(f"unexpected config file name: {n}")
                continue
            if len(parts) == 5 and parts[4] == "_status.json":
                triple.add(parts[1:4])
                status_name = n
                continue
            if len(parts) == 6 and parts[5] in RUN_FILES:
                triple.add(parts[1:4])
                run_ids.add(parts[4])
                run_files[parts[5]] = n
                continue
            P(f"unexpected path in zip: {n}")
        if len(triple) != 1:
            P(f"zip must hold exactly one (protocol, model, suite); found {sorted(triple)}")
            return res
        if len(run_ids) != 1:
            P(f"zip must hold exactly one run folder; found {sorted(run_ids)}")
            return res
        protocol, model, suite = next(iter(triple))
        run_id = next(iter(run_ids))
        res.info = {"protocol": protocol, "model": model, "suite": suite, "run_id": run_id}
        if protocol not in plan.PROTOCOLS:
            P(f"unknown protocol folder {protocol!r}")
            return res
        if suite not in plan.SUITES:
            P(f"unknown suite {suite!r}")
        missing = [f for f in RUN_FILES if f not in run_files]
        if missing or status_name is None:
            P(f"missing files: {missing + ([] if status_name else ['_status.json'])}")
            return res
        if cfg_names and f"results_v2/_generated_configs/{protocol}__{model}__{suite}.yaml" not in cfg_names:
            P(f"config file name does not match run: {cfg_names}")

        n_parsed = _count_lines(zf, run_files["parsed_results.jsonl"])
        n_raw = _count_lines(zf, run_files["raw_outputs.jsonl"])
        res.info["n_parsed"], res.info["n_raw"] = n_parsed, n_raw
        if n_parsed != expected_records:
            P(f"parsed_results.jsonl has {n_parsed} records, expected {expected_records}")
        if n_raw != expected_records:
            P(f"raw_outputs.jsonl has {n_raw} records, expected {expected_records}")

        # unique record keys
        keys = set()
        with zf.open(run_files["parsed_results.jsonl"]) as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                keys.add((r["task_id"], r["condition"], (r.get("drift") or {}).get("type", ""),
                          (r.get("fault") or {}).get("type", ""), int(r.get("trial_index", 0))))
        if len(keys) != n_parsed:
            P(f"duplicate record keys: {n_parsed} rows but {len(keys)} unique keys")

        status = json.loads(zf.read(status_name))
        manifest = json.loads(zf.read(run_files["run_manifest.json"]))
        if not (status.get("completed") and status.get("record_count_ok")):
            P(f"_status.json says not completed: {status.get('error') or status}")
        if status.get("run_id") != run_id:
            P(f"_status.json run_id {status.get('run_id')!r} != folder {run_id!r}")
        if manifest.get("run_id") != run_id:
            P(f"run_manifest run_id {manifest.get('run_id')!r} != folder {run_id!r}")
        if manifest.get("num_records") != expected_records:
            P(f"run_manifest num_records {manifest.get('num_records')} != {expected_records}")
        if manifest.get("seed") != plan.SEED:
            P(f"run_manifest seed {manifest.get('seed')} != {plan.SEED}")
        if manifest.get("num_tasks") != 100 or manifest.get("num_trials") != 3:
            P(f"num_tasks/num_trials = {manifest.get('num_tasks')}/{manifest.get('num_trials')}, expected 100/3")

        factors = manifest.get("run_factors", {})
        for k, v in plan.EXPECTED_FACTORS[protocol].items():
            if factors.get(k) != v:
                P(f"run_factors[{k}] = {factors.get(k)!r}, expected {v!r} for {protocol}")
        if factors.get("n_ctx") != 4096:
            P(f"run_factors n_ctx = {factors.get('n_ctx')!r}, expected 4096")

        backend = manifest.get("model_backend", {})
        if backend.get("llama_cpp_python_version") != plan.LLAMA_CPP_PYTHON_VERSION:
            P(f"llama_cpp_python_version {backend.get('llama_cpp_python_version')!r} != "
              f"pinned {plan.LLAMA_CPP_PYTHON_VERSION!r}")

        hw = manifest.get("hardware")
        if not hw or not (hw.get("gpu") or {}).get("name"):
            P("run_manifest has no hardware.gpu.name")
        else:
            res.info["gpu"] = hw["gpu"]["name"]
        kg = manifest.get("kaggle") or {}
        files = kg.get("model_files") or []
        want_srcs = (plan.Q4_SOURCES if protocol == "KAGGLE_HWCHECK" else plan.Q8_SOURCES).get(model)
        if not want_srcs:
            P(f"no planned model source for {model!r} under {protocol}")
        else:
            want = {f.filename: f.sha256 for f in want_srcs}
            got = {f.get("filename"): f.get("sha256_actual") for f in files}
            if got != want:
                P(f"model file hashes in manifest do not match the plan: got {got}, plan {want}")
        if not (kg.get("task_file") or {}).get("sha256_lf_normalized"):
            P("run_manifest.kaggle.task_file sha256 missing")
        res.info["elapsed_seconds"] = status.get("elapsed_seconds")
        res.info["python"] = manifest.get("python")  # informational; importer flags != laptop's 3.12.12
    return res
