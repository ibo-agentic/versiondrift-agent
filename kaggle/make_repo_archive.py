"""Build the repo archive to upload as a (private) Kaggle dataset.

Uses ``git archive`` of a committed revision, so the archive is exactly that
commit: no results, no models, no .venv, no untracked or uncommitted files.
A REPO_COMMIT.txt (the commit hash) is added; the Kaggle runs record it in
every run_manifest.json (kaggle.repo_commit).

It REFUSES to build if the working tree is dirty, or if ``main`` has changed
the experiment code/data since this revision (stale archive => Kaggle would
run different configs than the laptop). Override with --allow-stale only on
purpose.

Usage (from the repo root):  python kaggle/make_repo_archive.py [--rev HEAD] [--out kaggle_repo.zip]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

CODE_PATHS = ["upgradecanary", "data", "scripts/real_run_one.py", "scripts/real_run_models.py",
              "analysis/audit", "configs"]


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--out", default="kaggle_repo.zip")
    ap.add_argument("--main-branch", default="main")
    ap.add_argument("--allow-stale", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd()))
    commit = git("rev-parse", args.rev, cwd=repo)

    dirty = git("status", "--porcelain", "--untracked-files=no", cwd=repo)
    if dirty and args.rev == "HEAD":
        print("Working tree has uncommitted changes; commit first (the archive is of a commit):\n" + dirty,
              file=sys.stderr)
        return 1

    # Stale = main has commits this revision does not contain AND they touch
    # experiment code/data. (Changes made on THIS branch are not staleness.)
    try:
        main_in_rev = subprocess.run(["git", "merge-base", "--is-ancestor", args.main_branch, commit],
                                     cwd=repo).returncode == 0
        changed = "" if main_in_rev else git("diff", "--stat", commit, args.main_branch, "--", *CODE_PATHS, cwd=repo)
    except subprocess.CalledProcessError:
        changed = ""
        print(f"note: branch {args.main_branch!r} not found; skipping staleness check", file=sys.stderr)
    if changed and not args.allow_stale:
        print(f"{args.main_branch} differs from {commit[:10]} in experiment code/data:\n{changed}\n"
              "Merge/rebase first so Kaggle runs the laptop's current configs (or pass --allow-stale).",
              file=sys.stderr)
        return 1

    out = Path(args.out).resolve()
    with tempfile.TemporaryDirectory() as td:
        marker = Path(td) / "REPO_COMMIT.txt"
        marker.write_text(commit + "\n", encoding="utf-8")
        subprocess.run(["git", "archive", "--format=zip", "--prefix=repo/", f"--add-file={marker}",
                        "-o", str(out), commit], cwd=repo, check=True)
    print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB) from commit {commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
