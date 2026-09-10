#!/bin/sh
# Reproducible pipeline. Restartable: each step skips nothing but is idempotent; raw data are
# fetched only if missing. Requires .venv (python -m venv .venv && .venv/bin/pip install -r requirements.lock.txt).
set -eu
cd "$(dirname "$0")/.."
PY=.venv/bin/python
echo "== tests"; $PY -m pytest -q
echo "== EEGMAT (PhysioNet AWS mirror)"
if [ ! -d data/raw/eegmat/eeg-during-mental-arithmetic-tasks-1.0.0 ]; then
  mkdir -p data/raw/eegmat && curl -sS -o data/raw/eegmat/eegmat-1.0.0.zip https://physionet-open.s3.amazonaws.com/eegmat/eegmat-1.0.0.zip
  (cd data/raw/eegmat && unzip -q eegmat-1.0.0.zip && cd eeg-during-mental-arithmetic-tasks-1.0.0 && sha256sum -c SHA256SUMS.txt | grep -vc OK || true)
fi
$PY scripts/eegmat_features.py && $PY scripts/eegmat_analysis.py
echo "== ds007554 (OpenNeuro S3)"
if [ ! -f data/raw/ds007554/participants.tsv ]; then
  echo "run: python scripts/list_ds007554.py > /tmp/ds_list.txt && scripts/download_ds007554.sh /tmp/ds_list.txt"; exit 1
fi
$PY scripts/ds007554_alignment_audit.py && $PY scripts/ds007554_features.py && $PY scripts/ds007554_analysis.py
echo "== figures"; $PY scripts/make_figures.py
echo "== PRIMARY MATB-II (PhysioNet neuro-stress-resilience-hci 1.0.0)"
if [ ! -f data/raw/matb/SHA256SUMS.txt ]; then
  scripts/download_matb.sh docs
  P=$(grep -o 'PPG/p[0-9]*/' data/raw/matb/SHA256SUMS.txt | cut -d/ -f2 | sort -u | tr '\n' ' ')
  scripts/download_matb.sh matb $P && scripts/download_matb.sh ppg $P
fi
scripts/verify_matb.sh
$PY scripts/matb_pipeline.py
# EEG: one participant at a time (download, verify, features, delete raw): scripts/eeg_lane.sh LANE p01 p02 ...; then assemble
if ls data/features/matb_eeg_bins_p*.parquet >/dev/null 2>&1; then $PY scripts/matb_eeg.py --cohort-only; fi
$PY scripts/recovery_validity.py && $PY scripts/cross_modality_timing.py
$PY scripts/primary_prediction.py 500   # participant-level primary experiment (configs/primary_experiment_frozen.md); ~40 min
