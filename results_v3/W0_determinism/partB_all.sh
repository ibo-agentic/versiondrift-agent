cd /c/projects/versiondrift-agent
for p in "gemma2_2b synthetic" "phi3_mini bfcl_simple" "gemma3_4b bfcl_multiple"; do
  .venv/Scripts/python.exe results_v3/W0_determinism/partB_rerun.py $p
done
