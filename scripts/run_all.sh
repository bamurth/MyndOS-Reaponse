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
echo "== MATB primary (only if data present)"; $PY scripts/matb_pipeline.py || true
