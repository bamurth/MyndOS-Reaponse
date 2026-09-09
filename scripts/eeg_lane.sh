#!/bin/bash
# One download+process lane for the primary EEG cohort: for each participant, fetch the ~600 MB combined CSV,
# run scripts/matb_eeg.py --no-cohort (verifies SHA256, streams rows, writes per-participant features + audit row),
# then delete the raw file to respect the disk floor (features and audit are kept; re-download restores it).
# Usage: scripts/eeg_lane.sh LANE_NAME pXX [pYY ...]
set -u
cd "$(dirname "$0")/.."
lane=$1; shift
for p in "$@"; do
  for attempt in 1 2 3; do
    MATB_CURL_INSECURE=1 scripts/download_matb.sh eeg "$p" >/dev/null 2>&1
    f=$(ls data/raw/matb/EEGfNIRSeye_*/$p/$p.csv 2>/dev/null | head -1)
    .venv/bin/python scripts/matb_eeg.py --no-cohort "$p" > "results/audit/matb_eeg_audit_rows/$p.log" 2>&1
    st=$(.venv/bin/python -c "import json;print(json.load(open('results/audit/matb_eeg_audit_rows/$p.json')).get('status'))" 2>/dev/null)
    echo "$(date -u +%H:%M:%S) $lane $p attempt=$attempt status=$st"
    case "$st" in
      "checksum FAILED"*) rm -f "$f"; continue ;;   # partial/corrupt: refetch from scratch
      *) break ;;
    esac
  done
  case "$st" in
    ok|ambiguous*|"EEG unusable"*) [ -n "${f:-}" ] && [ -f "$f" ] && rm -f "$f" && echo "$(date -u +%H:%M:%S) $lane $p raw deleted" ;;
    *) echo "$(date -u +%H:%M:%S) $lane $p raw KEPT for inspection (status=$st)" ;;
  esac
done
echo "LANE_DONE $lane"
