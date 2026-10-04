"""One-off script (PLAN.md 10.2 smoke-test downloads, 2026-10-04): fetch the
11 Q4_K_M models not yet present locally, verify each against the SHA-256
already recorded from Hugging Face's own LFS listing (fetched in-session,
not invented), and print a manifest-ready summary line per file.

2026-10-04, two false starts on this specific connection (high latency,
~210-740ms ping, consistent with a satellite-class link) before landing
here:
1. huggingface_hub's default "Xet" transfer backend failed 100% of the
   time over a full 2-hour window -- every attempt died with the same CAS
   "File reconstruction error" partway through file 1, never completing
   one file (confirmed via its own transfer log).
2. Switching to huggingface_hub's classic HTTP path (HF_HUB_DISABLE_XET=1)
   completed file 1 cleanly, but on file 2 a dropped connection caused it
   to abandon a 3.02/4.92 GB partial and restart from zero -- its
   .incomplete filename is keyed by the server's ETag, and on this
   connection a retried HEAD request sometimes got back a different ETag
   than the first one (plausibly different CDN edge nodes under retry),
   so the "resume" path silently became a fresh download.

Downloading via `curl -C -` instead fixes this: resume is based on the
destination FILE's actual current byte count, not any server-provided id,
so it can never be confused by an ETag changing between attempts. `curl`
is on PATH on this machine (verified this session, v8.17).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (repo_id, filename, local_dir, expected_size_bytes, expected_sha256)
# sha256 values are each file's HF "lfs.oid" field, fetched live this
# session via the HF tree API -- this IS the file's SHA-256 per HF's own
# LFS metadata, cross-confirmed this session against a hash this project
# already computed locally for an existing file (Qwen3-8B-Q4_K_M.gguf:
# matches docs/model_manifest.md's own recorded hash exactly).
TARGETS = [
    ("Qwen/Qwen2-7B-Instruct-GGUF", "qwen2-7b-instruct-q4_k_m.gguf", "models/qwen",
     4683071264, "ed93dfc426f926451fa3ec7f996a787a31cfd97e55d7769568fbffc2d69861c2"),
    ("bartowski/Meta-Llama-3-8B-Instruct-GGUF", "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf", "models/llama",
     4920734272, "8ba9baf3a7345f705a11878397500fb25174034f0fd784e83aa4a96aaa47735f"),
    ("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "models/llama",
     4920739232, "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c"),
    ("bartowski/Phi-3-mini-4k-instruct-GGUF", "Phi-3-mini-4k-instruct-Q4_K_M.gguf", "models/phi",
     2393231360, "28a89b4ddb5766355f24e362ae4078b4c35b9ca9568df5fc9e6d9aeee4dee834"),
    ("bartowski/Phi-3.5-mini-instruct-GGUF", "Phi-3.5-mini-instruct-Q4_K_M.gguf", "models/phi",
     2393232672, "e4165e3a71af97f1b4820da61079826d8752a2088e313af0c7d346796c38eff5"),
    ("bartowski/microsoft_Phi-4-mini-instruct-GGUF", "microsoft_Phi-4-mini-instruct-Q4_K_M.gguf", "models/phi",
     2491874688, "01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2"),
    ("bartowski/granite-3.0-8b-instruct-GGUF", "granite-3.0-8b-instruct-Q4_K_M.gguf", "models/granite",
     4942856416, "360c8e306b9a40c59080e60cb51305867457dfa7e66b99fdffdf5afaab8ba34b"),
    ("bartowski/granite-3.1-8b-instruct-GGUF", "granite-3.1-8b-instruct-Q4_K_M.gguf", "models/granite",
     4942858720, "b72cfca8e30f23af77f922ce18d6fe1a5d4925907dddf7249c0cabc2739d48c8"),
    ("bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF", "ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf",
     "models/granite", 4942859808, "bd041eb5bc5e75e4f9a863372000046fd6490374f4dec07f399ca152b1df09c2"),
    ("bartowski/gemma-2-2b-it-GGUF", "gemma-2-2b-it-Q4_K_M.gguf", "models/gemma",
     1708582752, "e0aee85060f168f0f2d8473d7ea41ce2f3230c1bc1374847505ea599288a7787"),
    ("bartowski/google_gemma-3-4b-it-GGUF", "google_gemma-3-4b-it-Q4_K_M.gguf", "models/gemma",
     2489758112, "4996030242583a40aa151ff93f49ed787ac8c25e4120c3ae4588b2e2a7d1ae94"),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024 * 8), b""):
            h.update(chunk)
    return h.hexdigest()


def download_one(repo_id: str, filename: str, local_dir: str, expected_size: int) -> Path:
    dest = REPO_ROOT / local_dir / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == expected_size:
        print(f"  already present at expected size ({expected_size} bytes), skipping curl.", flush=True)
        return dest
    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    cmd = [
        "curl", "-L",
        "-C", "-",                 # resume from dest's current byte count, not any server-side id
        "--retry", "500",
        "--retry-delay", "5",
        "--retry-all-errors",      # retry on DNS failures/timeouts too, not just HTTP 5xx
        "--retry-max-time", "0",   # no cap on total time spent retrying
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
    for repo_id, filename, local_dir, expected_size, expected_sha256 in TARGETS:
        print(f"\n=== {repo_id} / {filename} ===", flush=True)
        try:
            path = download_one(repo_id, filename, local_dir, expected_size)
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
