"""Re-download model files that are missing from models/ and verify their SHA-256.

Source repository, file name and SHA-256 come from docs/model_manifest.md (the tables that list
`models/...` paths). The file name on Hugging Face is the file name of the local path; the file goes back to
exactly the same path. A SHA-256 mismatch deletes the partial download and exits with status 1.

    python -m scripts.restore_models --list                   # what the manifest knows, and what is missing
    python -m scripts.restore_models                          # download every missing file
    python -m scripts.restore_models --only Qwen3-8B          # only paths containing this text
    python -m scripts.restore_models --verify-existing        # also hash files that are already present

Interrupted downloads resume (a `.part` file next to the target). Public repositories only; no token is used.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "docs" / "model_manifest.md"
URL = "https://huggingface.co/{repo}/resolve/main/{name}"
ROW = re.compile(r"^\|\s*`(models/[^`]+\.gguf)`\s*\|(?P<rest>.*)$")
SHA = re.compile(r"`([0-9a-f]{64})`")
REPO = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")


def parse_manifest(path: Path = MANIFEST) -> dict[str, dict]:
    """{relative path: {'sha256', 'repo', 'size'}} for every `models/...gguf` row that has a SHA-256 and a source repo."""
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        sha = SHA.search(line)
        repo = next((r for c in cells[1:] for r in [REPO.search(c.replace("`", ""))]
                     if r and not r.group(1).startswith(("models/", "configs/"))), None)
        size = next((int(c.replace(",", "")) for c in cells[1:3] if re.fullmatch(r"[\d,]{7,}", c)), None)
        if sha and repo:
            out[m.group(1)] = {"sha256": sha.group(1), "repo": repo.group(1), "size": size}
    return out


def url_for(rel: str, info: dict) -> str:
    return URL.format(repo=info["repo"], name=Path(rel).name)


def sha256_of(path: Path, chunk: int = 1 << 24) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    """Resumable download to ``dest`` via ``dest.part``."""
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=60) as resp:
        if have and resp.status != 206:             # server ignored the range: start over
            have = 0
        mode = "ab" if have else "wb"
        total = resp.headers.get("Content-Length")
        done = have
        with open(part, mode) as fh:
            while block := resp.read(1 << 20):
                fh.write(block)
                done += len(block)
                if (done // (1 << 20)) % 256 == 0:
                    print(f"    {done / 2**30:6.2f} GiB" + (f" of {(int(total) + have) / 2**30:.2f}" if total else ""), flush=True)
    part.replace(dest)


def restore(rel: str, info: dict, root: Path = REPO_ROOT) -> bool:
    dest = root / rel
    url = url_for(rel, info)
    print(f"[{rel}] downloading {url}", flush=True)
    try:
        download(url, dest)
    except Exception as exc:  # noqa: BLE001
        print(f"[{rel}] DOWNLOAD FAILED: {exc} (a .part file is kept for resuming)", file=sys.stderr)
        return False
    got = sha256_of(dest)
    if got != info["sha256"]:
        dest.unlink()
        print(f"[{rel}] SHA-256 MISMATCH: expected {info['sha256']}, got {got}. File deleted.", file=sys.stderr)
        return False
    print(f"[{rel}] verified sha256 {got}", flush=True)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show manifest entries and which are missing; download nothing")
    ap.add_argument("--only", default=None, help="restrict to paths containing this text")
    ap.add_argument("--verify-existing", action="store_true", help="also hash files that already exist")
    ap.add_argument("--root", default=str(REPO_ROOT))
    args = ap.parse_args(argv)
    root = Path(args.root)
    entries = {k: v for k, v in parse_manifest().items() if args.only is None or args.only in k}
    if not entries:
        print("no manifest entries match", file=sys.stderr)
        return 2
    bad = 0
    for rel, info in sorted(entries.items()):
        dest = root / rel
        if dest.exists():
            if args.verify_existing and not args.list:
                ok = sha256_of(dest) == info["sha256"]
                print(f"[{rel}] present, sha256 {'OK' if ok else 'MISMATCH'}")
                bad += not ok
            elif args.list:
                print(f"present  {rel}")
            continue
        if args.list:
            print(f"MISSING  {rel}  {url_for(rel, info)}")
            continue
        bad += not restore(rel, info, root)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
