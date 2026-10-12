"""PLAN.md F5 (Q8_0) for the 5 small models that run on the laptop:
gemma2_2b, gemma3_4b, phi3_mini, phi35_mini, phi4_mini. Same repos as their
Q4_K_M files (docs/model_manifest.md section 5). Same resumable `curl -C -`
pattern as scripts/download_q2k_controls.py.

Sizes and SHA-256 are each file's Hugging Face "lfs.oid" (HF tree API,
fetched 2026-10-13), not computed-then-trusted: the downloaded bytes are
re-hashed and must match, else the file is reported MISMATCH (and kept for
inspection, never silently replaced).

Usage: python scripts/download_q8_small_models.py [--root PATH]
  --root  the repo checkout whose models/ directory gets the files
          (default: this repo; use the main checkout, where models/ lives).
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (repo_id, filename, local_dir, size_bytes, sha256)
TARGETS = [
    ("bartowski/gemma-2-2b-it-GGUF", "gemma-2-2b-it-Q8_0.gguf", "models/gemma",
     2784495456, "2d448a9aab894b8e8e18168cf3f490cb9f65632222f29f93514ac9ecc754debe"),
    ("bartowski/google_gemma-3-4b-it-GGUF", "google_gemma-3-4b-it-Q8_0.gguf", "models/gemma",
     4130226592, "0bce184b82f70ef6f1fb12c8d4984844baaa0bad0f4aae7150e443f803c4f509"),
    ("bartowski/Phi-3-mini-4k-instruct-GGUF", "Phi-3-mini-4k-instruct-Q8_0.gguf", "models/phi",
     4061221376, "0ac8ee48aeebf7d1b354691fd1e29e91c32ad88bbad10ad45ac880dcd4372a47"),
    ("bartowski/Phi-3.5-mini-instruct-GGUF", "Phi-3.5-mini-instruct-Q8_0.gguf", "models/phi",
     4061222688, "76fbf02f6fe92af57dbd818409bc8a0240026f1f3609bb405c3be94c973fb823"),
    ("bartowski/microsoft_Phi-4-mini-instruct-GGUF", "microsoft_Phi-4-mini-instruct-Q8_0.gguf", "models/phi",
     4084611456, "a12f242c4ee379b9da91673e5d78b30bfacfe4fd86a0b2259d2ecad5d93cb6c7"),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(REPO_ROOT))
    args = ap.parse_args(argv)
    root = Path(args.root)
    errors, results = [], []
    for repo_id, filename, local_dir, size, sha in TARGETS:
        dest = root / local_dir / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {repo_id} / {filename} ===", flush=True)
        if not (dest.exists() and dest.stat().st_size == size):
            url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
            cmd = ["curl", "-L", "-C", "-", "--retry", "200", "--retry-delay", "5", "--retry-all-errors",
                   "--retry-max-time", "0", "--connect-timeout", "30", "-sS", "-o", str(dest), url]
            rc = subprocess.run(cmd).returncode
            if rc != 0:
                errors.append((repo_id, filename, f"curl exit {rc}"))
                continue
        actual_size, actual_sha = dest.stat().st_size, sha256_file(dest)
        ok = actual_size == size and actual_sha == sha
        print(f"  size {actual_size} (expected {size}); sha256 {actual_sha}; {'OK' if ok else 'MISMATCH'}", flush=True)
        if not ok:
            errors.append((repo_id, filename, "size/hash mismatch"))
        results.append((repo_id, filename, dest.relative_to(root).as_posix(), actual_size, actual_sha, "OK" if ok else "MISMATCH"))
    print("\n=== MANIFEST-READY SUMMARY ===")
    for repo_id, filename, rel, size, sha, status in results:
        print(f"| `{rel}` | {size:,} | {size / 1024 ** 3:.2f} | `{sha}` | {repo_id} | [{status}] |")
    for e in errors:
        print("FAILED:", *e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
