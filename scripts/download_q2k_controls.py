"""PLAN.md section 6 positive control (a), 2026-10-11: download the 4
Q2_K GGUF files for the Q2_K quantization control (mistral_v03, qwen25,
llama31, granite32). Same pattern as scripts/download_smoke_models.py
(curl -C - for reliable resume on this connection).

Sizes and sha256 (= each file's HF "lfs.oid") fetched live this session
via the HF tree API (https://huggingface.co/api/models/<repo>/tree/main),
not guessed -- see DEVIATIONS.md, 2026-10-11, for the per-model source
reasoning (mistral_v03's own Q4_K_M repo, itlwas, ships no Q2_K; using
bartowski's Mistral v0.3 repo instead, confirmed with the user first).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (repo_id, filename, local_dir, local_filename, expected_size_bytes, expected_sha256)
TARGETS = [
    ("Qwen/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b-instruct-q2_k.gguf", "models/qwen",
     "qwen2.5-7b-instruct-q2_k.gguf",
     3015940000, "a0fc885ff014d73c02dcc4ad093f110c6dd4e0e308f84efe1accf078d364a87a"),
    ("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "Meta-Llama-3.1-8B-Instruct-Q2_K.gguf", "models/llama",
     "Meta-Llama-3.1-8B-Instruct-Q2_K.gguf",
     3179136416, "3f7f9265554ac91f1fb31c1b63b9cada4362533dfaa3f6e8dfc33c48d36909ce"),
    ("bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF", "ibm-granite_granite-3.2-8b-instruct-Q2_K.gguf",
     "models/granite", "ibm-granite_granite-3.2-8b-instruct-Q2_K.gguf",
     3103591968, "99e70f124d9be9d5f45118cfbfaf81b4cc6dc71c161205f04e6166c80fb3cef1"),
    ("bartowski/Mistral-7B-Instruct-v0.3-GGUF", "Mistral-7B-Instruct-v0.3-Q2_K.gguf", "models/mistral_bartowski",
     "Mistral-7B-Instruct-v0.3-Q2_K.gguf",
     2722877664, "6696020e424ccf3bc4ab6ac2bc639220f3d09ad6a225d5c3e16033a1ff9a4885"),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024 * 8), b""):
            h.update(chunk)
    return h.hexdigest()


def download_one(repo_id: str, filename: str, local_dir: str, local_filename: str, expected_size: int) -> Path:
    dest = REPO_ROOT / local_dir / local_filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == expected_size:
        print(f"  already present at expected size ({expected_size} bytes), skipping curl.", flush=True)
        return dest
    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    cmd = [
        "curl", "-L",
        "-C", "-",
        "--retry", "500",
        "--retry-delay", "5",
        "--retry-all-errors",
        "--retry-max-time", "0",
        "--connect-timeout", "30",
        "-o", str(dest),
        url,
    ]
    print(f"  running: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)
    return dest


def main() -> int:
    results = []
    errors = []
    for repo_id, filename, local_dir, local_filename, expected_size, expected_sha256 in TARGETS:
        print(f"\n=== {repo_id} / {filename} ===", flush=True)
        try:
            path = download_one(repo_id, filename, local_dir, local_filename, expected_size)
        except subprocess.CalledProcessError as exc:
            print(f"  GIVING UP on this file: curl exit code {exc.returncode}", flush=True)
            errors.append((repo_id, filename, f"curl exit code {exc.returncode}"))
            continue
        actual_size = path.stat().st_size
        print(f"downloaded to {path} ({actual_size} bytes); hashing...", flush=True)
        actual_sha256 = sha256_file(path)
        size_ok = actual_size == expected_size
        hash_ok = actual_sha256 == expected_sha256
        status = "OK" if (size_ok and hash_ok) else "MISMATCH"
        if not (size_ok and hash_ok):
            errors.append((repo_id, filename, f"size_ok={size_ok} hash_ok={hash_ok}"))
        print(
            f"  size: {actual_size} (expected {expected_size}) {'OK' if size_ok else 'MISMATCH'}\n"
            f"  sha256: {actual_sha256}\n"
            f"  expected: {expected_sha256}\n"
            f"  status: {status}",
            flush=True,
        )
        results.append((repo_id, filename, str(path), actual_size, actual_sha256, status))

    print("\n\n=== MANIFEST-READY SUMMARY ===")
    for repo_id, filename, path, size, sha256_hex, status in results:
        gib = size / (1024 ** 3)
        rel = Path(path).relative_to(REPO_ROOT).as_posix()
        print(f"| `{rel}` | {size:,} | {gib:.2f} | `{sha256_hex}` | {repo_id} | [{status}] |")

    if errors:
        print("\n=== FAILED FILES (re-run this script to retry just these) ===")
        for repo_id, filename, msg in errors:
            print(f"  {repo_id}/{filename}: {msg}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
