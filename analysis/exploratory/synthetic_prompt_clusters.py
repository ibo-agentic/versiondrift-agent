"""EXPLORATORY (Phase 1 data, results_v2 only): do the stress-condition prompts on synthetic collapse into the same
baseline-prompt groups? Reads raw_outputs.jsonl of one D run (trial 0 only); counts distinct prompt hashes per
condition and checks whether tasks that share a baseline prompt also share the stress prompt."""
import json, sys, collections, pathlib
root = pathlib.Path(sys.argv[1])
by = collections.defaultdict(dict)   # cond -> {task: set(hash)}
for line in (root / "raw_outputs.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    if int(r.get("trial_index", 0)) != 0:
        continue
    by[r["condition"]].setdefault(r["task_id"], set()).add(r.get("prompt_sha256"))
base = {t: next(iter(h)) for t, h in by["baseline"].items()}
print("tasks", len(base), "distinct baseline prompts", len(set(base.values())))
for c, d in sorted(by.items()):
    allh = set().union(*d.values())
    multi = sum(len(h) > 1 for h in d.values())
    # group tasks by baseline prompt; within group, is the condition prompt set identical?
    g = collections.defaultdict(list)
    for t, h in d.items():
        g[base[t]].append(frozenset(h))
    same = sum(len(set(v)) == 1 for v in g.values())
    # clusters implied by the condition's own prompts (tasks sharing the full set of hashes)
    own = len({frozenset(h) for h in d.values()})
    print(f"{c:16s} tasks={len(d)} distinct_hashes={len(allh)} tasks_with_>1_hash={multi} "
          f"own_groups(by hash-set)={own} baseline_groups={len(g)} baseline_groups_with_identical_cond_prompts={same}")
