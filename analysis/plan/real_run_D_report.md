# PLAN v1 real D-protocol runs: completion report (2026-10-05)

All 48 runs (16 models x 3 suites), 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. No verdict analysis here -- record-keeping only, per instruction.

**Runs completed: 48/48**
**Total elapsed time across all runs: 11.5 hours**
**Errors: 0**

| Model | Suite | Records | Expected | Seconds | run_dir |
|---|---|---|---|---|---|
| gemma2_2b | synthetic | 900 | 900 | 222 | C:\projects\versiondrift-agent\results_v2\D\gemma2_2b\synthetic\upgradecanary-real-D-gemma2_2b-synthetic_seed1234_20261004T203407Z |
| gemma2_2b | bfcl_simple | 900 | 900 | 304 | C:\projects\versiondrift-agent\results_v2\D\gemma2_2b\bfcl_simple\upgradecanary-real-D-gemma2_2b-bfcl_simple_seed1234_20261004T203750Z |
| gemma2_2b | bfcl_multiple | 900 | 900 | 328 | C:\projects\versiondrift-agent\results_v2\D\gemma2_2b\bfcl_multiple\upgradecanary-real-D-gemma2_2b-bfcl_multiple_seed1234_20261004T204254Z |
| gemma3_4b | synthetic | 900 | 900 | 370 | C:\projects\versiondrift-agent\results_v2\D\gemma3_4b\synthetic\upgradecanary-real-D-gemma3_4b-synthetic_seed1234_20261004T204823Z |
| gemma3_4b | bfcl_simple | 900 | 900 | 481 | C:\projects\versiondrift-agent\results_v2\D\gemma3_4b\bfcl_simple\upgradecanary-real-D-gemma3_4b-bfcl_simple_seed1234_20261004T205434Z |
| gemma3_4b | bfcl_multiple | 900 | 900 | 506 | C:\projects\versiondrift-agent\results_v2\D\gemma3_4b\bfcl_multiple\upgradecanary-real-D-gemma3_4b-bfcl_multiple_seed1234_20261004T210235Z |
| phi3_mini | synthetic | 900 | 900 | 330 | C:\projects\versiondrift-agent\results_v2\D\phi3_mini\synthetic\upgradecanary-real-D-phi3_mini-synthetic_seed1234_20261004T211102Z |
| phi3_mini | bfcl_simple | 900 | 900 | 431 | C:\projects\versiondrift-agent\results_v2\D\phi3_mini\bfcl_simple\upgradecanary-real-D-phi3_mini-bfcl_simple_seed1234_20261004T211632Z |
| phi3_mini | bfcl_multiple | 900 | 900 | 531 | C:\projects\versiondrift-agent\results_v2\D\phi3_mini\bfcl_multiple\upgradecanary-real-D-phi3_mini-bfcl_multiple_seed1234_20261004T223552Z |
| qwen2 | synthetic | 900 | 900 | 474 | C:\projects\versiondrift-agent\results_v2\D\qwen2\synthetic\upgradecanary-real-D-qwen2-synthetic_seed1234_20261004T214950Z |
| qwen2 | bfcl_simple | 900 | 900 | 656 | C:\projects\versiondrift-agent\results_v2\D\qwen2\bfcl_simple\upgradecanary-real-D-qwen2-bfcl_simple_seed1234_20261004T215744Z |
| qwen2 | bfcl_multiple | 900 | 900 | 672 | C:\projects\versiondrift-agent\results_v2\D\qwen2\bfcl_multiple\upgradecanary-real-D-qwen2-bfcl_multiple_seed1234_20261004T220841Z |
| llama31 | synthetic | 900 | 900 | 509 | C:\projects\versiondrift-agent\results_v2\D\llama31\synthetic\upgradecanary-real-D-llama31-synthetic_seed1234_20261004T221954Z |
| llama31 | bfcl_simple | 900 | 900 | 651 | C:\projects\versiondrift-agent\results_v2\D\llama31\bfcl_simple\upgradecanary-real-D-llama31-bfcl_simple_seed1234_20261004T224443Z |
| llama31 | bfcl_multiple | 900 | 900 | 669 | C:\projects\versiondrift-agent\results_v2\D\llama31\bfcl_multiple\upgradecanary-real-D-llama31-bfcl_multiple_seed1234_20261004T225534Z |
| mistral_v01 | synthetic | 900 | 900 | 567 | C:\projects\versiondrift-agent\results_v2\D\mistral_v01\synthetic\upgradecanary-real-D-mistral_v01-synthetic_seed1234_20261004T230644Z |
| mistral_v01 | bfcl_simple | 900 | 900 | 748 | C:\projects\versiondrift-agent\results_v2\D\mistral_v01\bfcl_simple\upgradecanary-real-D-mistral_v01-bfcl_simple_seed1234_20261004T231613Z |
| mistral_v01 | bfcl_multiple | 900 | 900 | 804 | C:\projects\versiondrift-agent\results_v2\D\mistral_v01\bfcl_multiple\upgradecanary-real-D-mistral_v01-bfcl_multiple_seed1234_20261004T232842Z |
| qwen25 | synthetic | 900 | 900 | 478 | C:\projects\versiondrift-agent\results_v2\D\qwen25\synthetic\upgradecanary-real-D-qwen25-synthetic_seed1234_20261004T234206Z |
| qwen25 | bfcl_simple | 900 | 900 | 599 | C:\projects\versiondrift-agent\results_v2\D\qwen25\bfcl_simple\upgradecanary-real-D-qwen25-bfcl_simple_seed1234_20261004T235006Z |
| qwen25 | bfcl_multiple | 900 | 900 | 625 | C:\projects\versiondrift-agent\results_v2\D\qwen25\bfcl_multiple\upgradecanary-real-D-qwen25-bfcl_multiple_seed1234_20261005T000005Z |
| mistral_v03 | synthetic | 900 | 900 | 523 | C:\projects\versiondrift-agent\results_v2\D\mistral_v03\synthetic\upgradecanary-real-D-mistral_v03-synthetic_seed1234_20261005T001031Z |
| mistral_v03 | bfcl_simple | 900 | 900 | 715 | C:\projects\versiondrift-agent\results_v2\D\mistral_v03\bfcl_simple\upgradecanary-real-D-mistral_v03-bfcl_simple_seed1234_20261005T001915Z |
| mistral_v03 | bfcl_multiple | 900 | 900 | 716 | C:\projects\versiondrift-agent\results_v2\D\mistral_v03\bfcl_multiple\upgradecanary-real-D-mistral_v03-bfcl_multiple_seed1234_20261005T003604Z |
| llama3 | synthetic | 900 | 900 | 547 | C:\projects\versiondrift-agent\results_v2\D\llama3\synthetic\upgradecanary-real-D-llama3-synthetic_seed1234_20261005T004801Z |
| llama3 | bfcl_simple | 900 | 900 | 664 | C:\projects\versiondrift-agent\results_v2\D\llama3\bfcl_simple\upgradecanary-real-D-llama3-bfcl_simple_seed1234_20261005T005708Z |
| llama3 | bfcl_multiple | 900 | 900 | 681 | C:\projects\versiondrift-agent\results_v2\D\llama3\bfcl_multiple\upgradecanary-real-D-llama3-bfcl_multiple_seed1234_20261005T010812Z |
| granite32 | synthetic | 900 | 900 | 629 | C:\projects\versiondrift-agent\results_v2\D\granite32\synthetic\upgradecanary-real-D-granite32-synthetic_seed1234_20261005T011933Z |
| granite32 | bfcl_simple | 900 | 900 | 843 | C:\projects\versiondrift-agent\results_v2\D\granite32\bfcl_simple\upgradecanary-real-D-granite32-bfcl_simple_seed1234_20261005T013006Z |
| granite32 | bfcl_multiple | 900 | 900 | 847 | C:\projects\versiondrift-agent\results_v2\D\granite32\bfcl_multiple\upgradecanary-real-D-granite32-bfcl_multiple_seed1234_20261005T014410Z |
| granite31 | synthetic | 900 | 900 | 618 | C:\projects\versiondrift-agent\results_v2\D\granite31\synthetic\upgradecanary-real-D-granite31-synthetic_seed1234_20261005T015818Z |
| granite31 | bfcl_simple | 900 | 900 | 855 | C:\projects\versiondrift-agent\results_v2\D\granite31\bfcl_simple\upgradecanary-real-D-granite31-bfcl_simple_seed1234_20261005T020837Z |
| granite31 | bfcl_multiple | 900 | 900 | 874 | C:\projects\versiondrift-agent\results_v2\D\granite31\bfcl_multiple\upgradecanary-real-D-granite31-bfcl_multiple_seed1234_20261005T023623Z |
| granite30 | synthetic | 900 | 900 | 625 | C:\projects\versiondrift-agent\results_v2\D\granite30\synthetic\upgradecanary-real-D-granite30-synthetic_seed1234_20261005T025058Z |
| granite30 | bfcl_simple | 900 | 900 | 836 | C:\projects\versiondrift-agent\results_v2\D\granite30\bfcl_simple\upgradecanary-real-D-granite30-bfcl_simple_seed1234_20261005T030123Z |
| granite30 | bfcl_multiple | 900 | 900 | 908 | C:\projects\versiondrift-agent\results_v2\D\granite30\bfcl_multiple\upgradecanary-real-D-granite30-bfcl_multiple_seed1234_20261005T031519Z |
| phi4_mini | synthetic | 900 | 900 | 367 | C:\projects\versiondrift-agent\results_v2\D\phi4_mini\synthetic\upgradecanary-real-D-phi4_mini-synthetic_seed1234_20261005T033029Z |
| phi4_mini | bfcl_simple | 900 | 900 | 494 | C:\projects\versiondrift-agent\results_v2\D\phi4_mini\bfcl_simple\upgradecanary-real-D-phi4_mini-bfcl_simple_seed1234_20261005T033637Z |
| phi4_mini | bfcl_multiple | 900 | 900 | 522 | C:\projects\versiondrift-agent\results_v2\D\phi4_mini\bfcl_multiple\upgradecanary-real-D-phi4_mini-bfcl_multiple_seed1234_20261005T034451Z |
| mistral_v02 | synthetic | 900 | 900 | 642 | C:\projects\versiondrift-agent\results_v2\D\mistral_v02\synthetic\upgradecanary-real-D-mistral_v02-synthetic_seed1234_20261005T035334Z |
| mistral_v02 | bfcl_simple | 900 | 900 | 800 | C:\projects\versiondrift-agent\results_v2\D\mistral_v02\bfcl_simple\upgradecanary-real-D-mistral_v02-bfcl_simple_seed1234_20261005T040419Z |
| mistral_v02 | bfcl_multiple | 900 | 900 | 837 | C:\projects\versiondrift-agent\results_v2\D\mistral_v02\bfcl_multiple\upgradecanary-real-D-mistral_v02-bfcl_multiple_seed1234_20261005T041740Z |
| phi35_mini | synthetic | 900 | 900 | 478 | C:\projects\versiondrift-agent\results_v2\D\phi35_mini\synthetic\upgradecanary-real-D-phi35_mini-synthetic_seed1234_20261005T043643Z |
| phi35_mini | bfcl_simple | 900 | 900 | 773 | C:\projects\versiondrift-agent\results_v2\D\phi35_mini\bfcl_simple\upgradecanary-real-D-phi35_mini-bfcl_simple_seed1234_20261005T044441Z |
| phi35_mini | bfcl_multiple | 900 | 900 | 915 | C:\projects\versiondrift-agent\results_v2\D\phi35_mini\bfcl_multiple\upgradecanary-real-D-phi35_mini-bfcl_multiple_seed1234_20261005T045735Z |
| qwen3 | synthetic | 900 | 900 | 3845 | C:\projects\versiondrift-agent\results_v2\D\qwen3\synthetic\upgradecanary-real-D-qwen3-synthetic_seed1234_20261005T051250Z |
| qwen3 | bfcl_simple | 900 | 900 | 4865 | C:\projects\versiondrift-agent\results_v2\D\qwen3\bfcl_simple\upgradecanary-real-D-qwen3-bfcl_simple_seed1234_20261005T063711Z |
| qwen3 | bfcl_multiple | 900 | 900 | 5058 | C:\projects\versiondrift-agent\results_v2\D\qwen3\bfcl_multiple\upgradecanary-real-D-qwen3-bfcl_multiple_seed1234_20261005T083916Z |