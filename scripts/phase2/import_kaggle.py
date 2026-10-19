"""Verify and import Phase 2 Kaggle run zips (p2__<folder>__<model>__<suite>.zip) into results_v3/.

    python -m scripts.phase2.import_kaggle DIR_WITH_ZIPS            # check only
    python -m scripts.phase2.import_kaggle DIR_WITH_ZIPS --apply    # extract the ones that pass

A zip is accepted only if every member sits under results_v3/<folder>/<model>/<suite>/ (or is its generated
config), the run is in the W1_kaggle manifest, there is exactly one run folder, _status.json says completed
with the manifest's record count, parsed_results.jsonl has exactly that many records, and run_manifest.json
names a Tesla T4. Nothing is ever overwritten: an existing suite folder makes the zip a refusal.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.phase2.plan import MANIFEST_DIR, load_manifest  # noqa: E402


def _count(zf: zipfile.ZipFile, name: str) -> int:
    with zf.open(name) as fh:
        return sum(1 for line in fh if line.strip())


def verify_run_zip(zip_path: Path, entries_by_id: dict[str, dict]) -> tuple[dict | None, list[str]]:
    """(entry, problems). Reads the zip in place."""
    problems: list[str] = []
    try:
        zf = zipfile.ZipFile(zip_path)
    except Exception as exc:  # noqa: BLE001
        return None, [f"not a readable zip: {exc}"]
    with zf:
        bad = zf.testzip()
        if bad:
            return None, [f"corrupt member (CRC): {bad}"]
        names = [n for n in zf.namelist() if not n.endswith("/")]
        run_ids: set[str] = set()
        key = None
        for n in names:
            parts = PurePosixPath(n).parts
            if n.startswith("/") or ".." in parts or parts[0] != "results_v3":
                problems.append(f"unsafe or foreign member: {n}")
                continue
            if len(parts) == 3 and parts[1] == "_generated_configs":
                continue
            if len(parts) < 5:
                problems.append(f"member outside a run folder: {n}")
                continue
            k = (parts[1], parts[2], parts[3])
            key = key or k
            if k != key:
                problems.append(f"zip mixes runs: {key} and {k}")
            if parts[4] != "_status.json":
                run_ids.add(parts[4])
        if problems or key is None:
            return None, problems or ["empty zip"]
        entry = entries_by_id.get(f"{key[0]}/{key[1]}/{key[2]}")
        if entry is None:
            return None, [f"{'/'.join(key)} is not in the W1_kaggle manifest"]
        base = f"results_v3/{key[0]}/{key[1]}/{key[2]}"
        if len(run_ids) != 1:
            problems.append(f"expected exactly one run folder, found {sorted(run_ids)}")
        else:
            rid = next(iter(run_ids))
            for f in ("parsed_results.jsonl", "raw_outputs.jsonl", "run_manifest.json", "summary.json"):
                if f"{base}/{rid}/{f}" not in names:
                    problems.append(f"missing {f}")
            if not problems:
                n_parsed = _count(zf, f"{base}/{rid}/parsed_results.jsonl")
                if n_parsed != entry["expected_records"]:
                    problems.append(f"{n_parsed} parsed records, manifest expects {entry['expected_records']}")
                man = json.loads(zf.read(f"{base}/{rid}/run_manifest.json"))
                gpu = ((man.get("hardware") or {}).get("gpu") or {}).get("name", "")
                if "T4" not in gpu:
                    problems.append(f"not run on a T4 (gpu: {gpu!r})")
                if (man.get("phase2") or {}).get("id") != entry["id"]:
                    problems.append("run_manifest.json does not name this manifest entry")
        if f"{base}/_status.json" not in names:
            problems.append("missing _status.json")
        else:
            st = json.loads(zf.read(f"{base}/_status.json"))
            if not (st.get("completed") and st.get("record_count_ok") and st.get("expected_records") == entry["expected_records"]):
                problems.append("_status.json does not say complete with the right record count")
    return (entry if not problems else None), problems


def import_zips(zip_dir: Path, dest_root: Path, apply: bool = False, manifest_dir: Path = MANIFEST_DIR) -> list[dict]:
    entries = {e["id"]: e for e in load_manifest("W1_kaggle", manifest_dir)["runs"]}
    out = []
    for z in sorted(Path(zip_dir).glob("p2__*.zip")):
        entry, problems = verify_run_zip(z, entries)
        status = "ok" if not problems else "REFUSED"
        if entry and (dest_root / entry["output_dir"]).exists():
            problems.append(f"{entry['output_dir']} already exists; not overwritten")
            status = "REFUSED"
        if status == "ok" and apply:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest_root)
            status = "imported"
            log = dest_root / "results_v3" / "_kaggle_import_log.jsonl"
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"zip": z.name, "run": entry["id"]}) + "\n")
        out.append({"zip": z.name, "status": status, "problems": problems})
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("zip_dir")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dest", default=str(REPO_ROOT))
    args = ap.parse_args(argv)
    res = import_zips(Path(args.zip_dir), Path(args.dest), args.apply)
    for r in res:
        print(f"{r['status']:9s} {r['zip']}  {'; '.join(r['problems'][:2])}")
    return 0 if all(r["status"] != "REFUSED" for r in res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
