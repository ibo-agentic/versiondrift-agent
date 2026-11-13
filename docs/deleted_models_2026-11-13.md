# Model files deleted on 2026-11-13

25 files, 90,425,231,616 bytes (84.22 GiB). Deleted to free disk space; every file is re-downloadable.
Before deletion each file's size and SHA-256 were recomputed from the file on disk and matched `docs/model_manifest.md`.
Kept in `models/`: the three itlwas Mistral Q4_K_M files.

Restore: `python -m scripts.restore_models --list` shows what is missing; `python -m scripts.restore_models` re-downloads it
from the URLs below to the same paths and verifies the SHA-256 (add `--only <text>` to restore a subset).

| Path | Size (bytes) | SHA-256 | URL |
|---|---|---|---|
| `models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` | 4,372,812,000 | `1270d22c0fbb3d092fb725d4d96c457b7b687a5f5a715abe1e818da303e562b6` | https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf |
| `models/gemma/gemma-2-2b-it-Q4_K_M.gguf` | 1,708,582,752 | `e0aee85060f168f0f2d8473d7ea41ce2f3230c1bc1374847505ea599288a7787` | https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf |
| `models/gemma/gemma-2-2b-it-Q8_0.gguf` | 2,784,495,456 | `2d448a9aab894b8e8e18168cf3f490cb9f65632222f29f93514ac9ecc754debe` | https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q8_0.gguf |
| `models/gemma/google_gemma-3-4b-it-Q4_K_M.gguf` | 2,489,758,112 | `4996030242583a40aa151ff93f49ed787ac8c25e4120c3ae4588b2e2a7d1ae94` | https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF/resolve/main/google_gemma-3-4b-it-Q4_K_M.gguf |
| `models/gemma/google_gemma-3-4b-it-Q8_0.gguf` | 4,130,226,592 | `0bce184b82f70ef6f1fb12c8d4984844baaa0bad0f4aae7150e443f803c4f509` | https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF/resolve/main/google_gemma-3-4b-it-Q8_0.gguf |
| `models/granite/granite-3.0-8b-instruct-Q4_K_M.gguf` | 4,942,856,416 | `360c8e306b9a40c59080e60cb51305867457dfa7e66b99fdffdf5afaab8ba34b` | https://huggingface.co/bartowski/granite-3.0-8b-instruct-GGUF/resolve/main/granite-3.0-8b-instruct-Q4_K_M.gguf |
| `models/granite/granite-3.1-8b-instruct-Q4_K_M.gguf` | 4,942,858,720 | `b72cfca8e30f23af77f922ce18d6fe1a5d4925907dddf7249c0cabc2739d48c8` | https://huggingface.co/bartowski/granite-3.1-8b-instruct-GGUF/resolve/main/granite-3.1-8b-instruct-Q4_K_M.gguf |
| `models/granite/ibm-granite_granite-3.2-8b-instruct-Q2_K.gguf` | 3,103,591,968 | `99e70f124d9be9d5f45118cfbfaf81b4cc6dc71c161205f04e6166c80fb3cef1` | https://huggingface.co/bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF/resolve/main/ibm-granite_granite-3.2-8b-instruct-Q2_K.gguf |
| `models/granite/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf` | 4,942,859,808 | `bd041eb5bc5e75e4f9a863372000046fd6490374f4dec07f399ca152b1df09c2` | https://huggingface.co/bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF/resolve/main/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf |
| `models/llama/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf` | 4,920,734,272 | `8ba9baf3a7345f705a11878397500fb25174034f0fd784e83aa4a96aaa47735f` | https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf |
| `models/llama/Meta-Llama-3.1-8B-Instruct-Q2_K.gguf` | 3,179,136,416 | `3f7f9265554ac91f1fb31c1b63b9cada4362533dfaa3f6e8dfc33c48d36909ce` | https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q2_K.gguf |
| `models/llama/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | 4,920,739,232 | `7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c` | https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf |
| `models/mistral-7b-instruct-v0.2.Q4_K_M.gguf` | 4,368,439,584 | `3e0039fd0273fcbebb49228943b17831aadd55cbcbf56f0af00499be2040ccf9` | https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf |
| `models/mistral_bartowski/Mistral-7B-Instruct-v0.3-Q2_K.gguf` | 2,722,877,664 | `6696020e424ccf3bc4ab6ac2bc639220f3d09ad6a225d5c3e16033a1ff9a4885` | https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3-Q2_K.gguf |
| `models/phi/Phi-3-mini-4k-instruct-Q4_K_M.gguf` | 2,393,231,360 | `28a89b4ddb5766355f24e362ae4078b4c35b9ca9568df5fc9e6d9aeee4dee834` | https://huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF/resolve/main/Phi-3-mini-4k-instruct-Q4_K_M.gguf |
| `models/phi/Phi-3-mini-4k-instruct-Q8_0.gguf` | 4,061,221,376 | `0ac8ee48aeebf7d1b354691fd1e29e91c32ad88bbad10ad45ac880dcd4372a47` | https://huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF/resolve/main/Phi-3-mini-4k-instruct-Q8_0.gguf |
| `models/phi/Phi-3.5-mini-instruct-Q4_K_M.gguf` | 2,393,232,672 | `e4165e3a71af97f1b4820da61079826d8752a2088e313af0c7d346796c38eff5` | https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf |
| `models/phi/Phi-3.5-mini-instruct-Q8_0.gguf` | 4,061,222,688 | `76fbf02f6fe92af57dbd818409bc8a0240026f1f3609bb405c3be94c973fb823` | https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q8_0.gguf |
| `models/phi/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf` | 2,491,874,688 | `01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2` | https://huggingface.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF/resolve/main/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf |
| `models/phi/microsoft_Phi-4-mini-instruct-Q8_0.gguf` | 4,084,611,456 | `a12f242c4ee379b9da91673e5d78b30bfacfe4fd86a0b2259d2ecad5d93cb6c7` | https://huggingface.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF/resolve/main/microsoft_Phi-4-mini-instruct-Q8_0.gguf |
| `models/qwen/Qwen3-8B-Q4_K_M.gguf` | 5,027,783,488 | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` | https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf |
| `models/qwen/qwen2-7b-instruct-q4_k_m.gguf` | 4,683,071,264 | `ed93dfc426f926451fa3ec7f996a787a31cfd97e55d7769568fbffc2d69861c2` | https://huggingface.co/Qwen/Qwen2-7B-Instruct-GGUF/resolve/main/qwen2-7b-instruct-q4_k_m.gguf |
| `models/qwen/qwen2.5-7b-instruct-q2_k.gguf` | 3,015,940,000 | `a0fc885ff014d73c02dcc4ad093f110c6dd4e0e308f84efe1accf078d364a87a` | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q2_k.gguf |
| `models/qwen/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` | 3,993,201,344 | `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf |
| `models/qwen/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf` | 689,872,288 | `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a` | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf |
