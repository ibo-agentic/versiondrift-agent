"""Analysis pipeline for the upgrade-verdict stability study (PLAN.md sections 8-9).

Reads only the per-run record files the runner writes (parsed_results.jsonl,
run_manifest.json, optionally raw_outputs.jsonl); never runs a model.
"""
