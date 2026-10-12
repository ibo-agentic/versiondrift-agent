"""Import run zips downloaded from Kaggle into results_v2/ on the laptop.

Each zip (kaggle__<protocol>__<model>__<suite>.zip) holds exactly one finished
run in the laptop's layout: results_v2/<protocol>/<model>/<suite>/_status.json
+ <run_id>/{parsed_results,raw_outputs}.jsonl, run_manifest.json, summary.json.

Safety rules (nothing is changed unless every check passes for that zip):
  * the zip must pass kaggle/kaggle_verify.py: CRC, only expected paths, one
    run, 900 parsed + 900 raw records, unique record keys, manifest/status
    agree, seed 1234, run_factors as planned, llama-cpp-python == pinned,
    model-file SHA-256 == the planned (Hugging Face-published) hash, a
    hardware field;
  * the task file hash recorded on Kaggle must equal the local data file's hash;
  * the target results_v2/<protocol>/<model>/<suite>/ must NOT exist (nothing
    is ever overwritten or merged into an existing run folder);
  * files are extracted to a staging directory, re-counted there, then moved.

Usage:
  python scripts/import_kaggle_results.py <zip-or-folder> [...] [--results-root results_v2] [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "kaggle"))
import kaggle_plan as plan  # noqa: E402
import kaggle_verify  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_zips(sources: list[str]) -> list[Path]:
    out: list[Path] = []
    for s in sources:
        p = Path(s)
        if p.is_dir():
            out += sorted(p.rglob("kaggle__*.zip"))
        elif p.is_file():
            out.append(p)
        else:
            print(f"WARNING: {p} does not exist", file=sys.stderr)
    return out


def _count(path: Path) -> int:
    return sum(1 for line in open(path, encoding="utf-8") if line.strip())


def import_zips(zips: list[Path], results_root: Path, expected_records: int = plan.EXPECTED_RECORDS_PER_RUN,
                dry_run: bool = False, repo_root: Path = REPO_ROOT) -> list[dict]:
    report: list[dict] = []
    seen: dict[tuple[str, str, str], tuple[str, Path]] = {}
    staging_root: Path | None = None
    for z in zips:
        row = {"zip": str(z), "status": "", "detail": ""}
        report.append(row)
        res = kaggle_verify.verify_run_zip(z, expected_records)
        if not res.ok:
            row.update(status="REJECTED", detail="; ".join(res.problems))
            continue
        info = res.info
        triple = (info["protocol"], info["model"], info["suite"])
        row["run"] = "/".join(triple)
        row["run_id"] = info["run_id"]
        row["records"] = info["n_parsed"]
        row["gpu"] = info.get("gpu")

        if triple in seen:
            prev_id, prev_zip = seen[triple]
            same = prev_id == info["run_id"]
            row.update(status="DUPLICATE" if same else "REJECTED",
                       detail=f"same run as {prev_zip.name} (identical run_id, skipped)" if same else
                       f"CONFLICT: {prev_zip.name} holds a different run_id ({prev_id}) for the same run")
            continue
        seen[triple] = (info["run_id"], z)

        # task file must be the same bytes (LF-normalized) as this repo's
        with zipfile.ZipFile(z) as zf:
            mname = next(n for n in zf.namelist() if n.endswith("/run_manifest.json"))
            manifest = json.loads(zf.read(mname))
        tf = manifest["kaggle"]["task_file"]
        local = repo_root / tf["path"]
        if not local.exists() or plan.lf_normalized_sha256(local) != tf["sha256_lf_normalized"]:
            row.update(status="REJECTED", detail=f"task file {tf['path']} differs from this repo's copy "
                                                 f"(or is missing); Kaggle ran different tasks")
            continue

        target = results_root / triple[0] / triple[1] / triple[2]
        if target.exists():
            row.update(status="REFUSED", detail=f"{target} already exists; not overwriting")
            continue
        cfg_target = results_root / "_generated_configs" / f"{triple[0]}__{triple[1]}__{triple[2]}.yaml"

        if dry_run:
            row.update(status="WOULD-IMPORT", detail=str(target))
            continue

        if staging_root is None:
            results_root.parent.mkdir(parents=True, exist_ok=True)
            staging_root = Path(tempfile.mkdtemp(prefix="_kimp_", dir=results_root.parent))
        stage = staging_root / str(len(report))  # short: Windows path-length limit
        with zipfile.ZipFile(z) as zf:
            zf.extractall(stage)
        s_run = stage / "results_v2" / triple[0] / triple[1] / triple[2]
        run_dir = s_run / info["run_id"]
        n_p, n_r = _count(run_dir / "parsed_results.jsonl"), _count(run_dir / "raw_outputs.jsonl")
        if n_p != expected_records or n_r != expected_records:
            row.update(status="REJECTED", detail=f"after extraction: parsed={n_p}, raw={n_r}, expected {expected_records}")
            shutil.rmtree(stage, ignore_errors=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():  # re-check right before the move
            row.update(status="REFUSED", detail=f"{target} appeared; not overwriting")
            continue
        shutil.move(str(s_run), str(target))
        s_cfg = stage / "results_v2" / "_generated_configs" / cfg_target.name
        if s_cfg.exists() and not cfg_target.exists():
            cfg_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s_cfg), str(cfg_target))
        with open(results_root / "_kaggle_import_log.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "zip": z.name, "zip_sha256": _sha256(z), "run": "/".join(triple),
                                 "run_id": info["run_id"], "records": n_p, "gpu": info.get("gpu")}) + "\n")
        row.update(status="IMPORTED", detail=str(target), records=n_p)
    if staging_root is not None:
        shutil.rmtree(staging_root, ignore_errors=True)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", help="zip files and/or folders containing kaggle__*.zip")
    ap.add_argument("--results-root", default=str(REPO_ROOT / "results_v2"))
    ap.add_argument("--expected-records", type=int, default=plan.EXPECTED_RECORDS_PER_RUN)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    zips = collect_zips(args.sources)
    if not zips:
        print("no zips found", file=sys.stderr)
        return 1
    report = import_zips(zips, Path(args.results_root), args.expected_records, args.dry_run)
    counts: dict[str, int] = {}
    for r in report:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"{r['status']:13s} {r.get('run', '?'):40s} {r.get('records', ''):>5}  {Path(r['zip']).name}"
              + (f"\n               -> {r['detail']}" if r["status"] not in ("IMPORTED", "WOULD-IMPORT") else ""))
    print("\n" + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    bad = sum(v for k, v in counts.items() if k in ("REJECTED", "REFUSED"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
