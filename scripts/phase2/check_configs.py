"""Check every Phase 2 run config against the manifests and against the analysis config.

    python -m scripts.phase2.check_configs [--phase1-root results_v2]

1. each manifest entry builds into a config (laptop's build_config + trial keys only);
2. (with --phase1-root) that config equals Phase 1's generated config for the same run in every key
   except experiment, output_dir and the trial keys (W3: also the task file);
3. against configs/analysis_phase2.yaml: the manifests cover exactly the results_v3 folders the analysis
   reads, with the folder names, first trial index (trial_offset), trial seeds (seed_base + index),
   trial count (n_trials) and the greedy/sampled temperature pattern it expects.
Exit status 0 only if there is no problem.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.phase2.build import ManifestError, build_run_config, diff_against_phase1  # noqa: E402
from scripts.phase2.plan import MANIFEST_DIR, SUITE_ORDER, WORKSTREAMS, load_manifest  # noqa: E402
from vdanalysis.phase2.config import Phase2Config, load_phase2_config  # noqa: E402

KAGGLE_PLACEHOLDER = "/kaggle/temp/models/model.gguf"
SCORING_ONLY = {"F7", "F8", "F10"}            # no runs: rescored, or a view of D


def analysis_needs(cfg: Phase2Config, include_w3: bool = True) -> dict[tuple, dict]:
    """{(folder, model): {protocol, offset, seed_base}} for every results_v3 part the analysis reads."""
    models = list(cfg.models)
    need: dict[tuple, dict] = {}

    def add(protocol: str, ms: list[str]) -> None:
        for m in ms:
            for part in cfg.parts_for(protocol, m):
                if part.root != "v3":
                    continue
                folder = part.folder or cfg.protocols[protocol].get("folder", protocol)
                need[(folder, m)] = {"protocol": protocol, "offset": part.trial_offset,
                                     "seed_base": cfg.seed_base(protocol)}

    trim = cfg.p2.get("f6_trim") or {}
    for proto in cfg.p2.get("decision_protocols", []):
        if proto in SCORING_ONLY or cfg.protocol_p2(proto).get("view_of"):
            continue
        ms = cfg.protocol_models(proto) or models
        if proto == trim.get("protocol"):
            ms = [m for m in ms if m not in cfg.f6_trim_models()]
        add(proto, ms)
    for sh in (cfg.p2.get("same_hardware") or {}).values():
        add(sh["baseline"], sorted(cfg.resolve_models(sh["models"])))
    for ctl in cfg.controls:
        add(ctl["protocol_b"], ctl["models"])
    if include_w3:
        for spec in ((cfg.p2.get("w3") or {}).get("protocols") or {}).values():
            add(spec["protocol"], models)
    return need


def check_against_analysis(manifests: dict[str, dict], cfg: Phase2Config) -> list[str]:
    problems: list[str] = []
    need = analysis_needs(cfg, include_w3="W3" in manifests)
    if cfg.root_path("v3").name != "results_v3":
        problems.append(f"analysis root v3 is {cfg.root_path('v3')}, not results_v3")
    have: dict[tuple, list[dict]] = {}
    for m in manifests.values():
        for e in m["runs"]:
            have.setdefault((e["folder"], e["model"]), []).append(e)
    for key in sorted(set(need) - set(have)):
        problems.append(f"analysis reads {key[0]}/{key[1]} but no manifest has runs for it")
    for key in sorted(set(have) - set(need)):
        problems.append(f"manifest has runs for {key[0]}/{key[1]} that the analysis never reads")
    for key in sorted(set(need) & set(have)):
        want = need[key]
        suites = sorted(e["suite"] for e in have[key])
        want_suites = sorted((cfg.p2.get("w3") or {}).get("suites") or SUITE_ORDER) if key[0].startswith("W3_")             else sorted(SUITE_ORDER)
        if suites != want_suites:
            problems.append(f"{key}: suites {suites}, expected all of {want_suites}")
        for e in have[key]:
            if e["output_dir"] != f"results_v3/{e['folder']}/{e['model']}/{e['suite']}":
                problems.append(f"{e['id']}: output_dir {e['output_dir']}")
            if e["trial_first_index"] != want["offset"]:
                problems.append(f"{e['id']}: first trial {e['trial_first_index']}, analysis trial_offset {want['offset']}")
            if e["trial_first_index"] + e["n_trials"] != cfg.n_trials:
                problems.append(f"{e['id']}: ends at trial {e['trial_first_index'] + e['n_trials']}, "
                                f"analysis n_trials {cfg.n_trials}")
            if want["seed_base"] is not None:
                exp = [want["seed_base"] + e["trial_first_index"] + i for i in range(e["n_trials"])]
                if e["trial_seeds"] != exp:
                    problems.append(f"{e['id']}: trial seeds {e['trial_seeds']}, analysis seed_base gives {exp}")
            if (e["temperatures"][0] == 0.0) != (e["trial_first_index"] == 0):
                problems.append(f"{e['id']}: the greedy trial must be merged trial 0 and only that")
            if any(t == 0.0 for t in e["temperatures"][1:]):
                problems.append(f"{e['id']}: more than one greedy trial")
            if e["run_seed"] != 1234:
                problems.append(f"{e['id']}: run seed {e['run_seed']}")
    return problems


def check_all(manifest_dir: Path = MANIFEST_DIR, analysis_yaml: Path | None = None,
              phase1_root: Path | None = None) -> dict:
    analysis_yaml = analysis_yaml or REPO_ROOT / "configs" / "analysis_phase2.yaml"
    manifests = {n: load_manifest(n, manifest_dir) for n in WORKSTREAMS}
    problems: list[str] = []
    n = n_cmp = n_same = 0
    seen: set[str] = set()
    for m in manifests.values():
        for e in m["runs"]:
            n += 1
            if e["id"] in seen:
                problems.append(f"{e['id']}: listed twice")
            seen.add(e["id"])
            try:
                cfg = build_run_config(e, gguf=KAGGLE_PLACEHOLDER if e["hardware"] == "kaggle" else None)
            except ManifestError as exc:
                problems.append(str(exc))
                continue
            if e["expected_records"] != e["n_tasks"] * len(cfg["conditions"]) * cfg["trials"]:
                problems.append(f"{e['id']}: expected_records {e['expected_records']} != tasks x conditions x trials")
            if phase1_root:
                d = diff_against_phase1(e, cfg, Path(phase1_root))
                if d is not None:
                    n_cmp += 1
                    if d:
                        problems.append(f"{e['id']}: differs from Phase 1 in {d}")
                    else:
                        n_same += 1
    pending = check_task_files(manifests, problems)
    problems += check_against_analysis(manifests, load_phase2_config(analysis_yaml))
    return {"n_runs": n, "n_compared_with_phase1": n_cmp, "n_identical_to_phase1": n_same, "problems": problems,
            "pending_task_files": pending}


def check_task_files(manifests: dict[str, dict], problems: list[str], root: Path = REPO_ROOT) -> list[str]:
    """Every manifest run whose task file is marked ok must point at an existing file with exactly ``n_tasks`` tasks
    (task ids unique); returns the task files that are still pending (and checks that they are not there yet)."""
    pending: set[str] = set()
    checked: set[str] = set()
    for m in manifests.values():
        for e in m["runs"]:
            path = root / e["data"]
            if e["data_status"] == "pending":
                pending.add(e["data"])
                if path.exists():
                    problems.append(f"{e['id']}: task file {e['data']} exists but the manifest still says pending")
                continue
            key = (e["data"], e["n_tasks"])
            if key in checked:
                continue
            checked.add(key)
            if not path.exists():
                problems.append(f"{e['id']}: task file {e['data']} is missing")
                continue
            ids = [__import__("json").loads(l)["task_id"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if len(ids) != e["n_tasks"] or len(set(ids)) != len(ids):
                problems.append(f"{e['id']}: {e['data']} has {len(ids)} tasks ({len(set(ids))} distinct), manifest says {e['n_tasks']}")
    return sorted(pending)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifests", default=str(MANIFEST_DIR))
    ap.add_argument("--analysis", default=str(REPO_ROOT / "configs" / "analysis_phase2.yaml"))
    ap.add_argument("--phase1-root", default=None)
    args = ap.parse_args(argv)
    r = check_all(Path(args.manifests), Path(args.analysis), Path(args.phase1_root) if args.phase1_root else None)
    print(f"{r['n_runs']} runs checked; compared with Phase 1 configs: {r['n_compared_with_phase1']} "
          f"({r['n_identical_to_phase1']} identical outside the trial keys); problems: {len(r['problems'])}")
    if r["pending_task_files"]:
        print(f"task files still pending (not a problem): {r['pending_task_files']}")
    for p in r["problems"][:50]:
        print("  -", p)
    return 0 if not r["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
