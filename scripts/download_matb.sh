#!/bin/sh
# Restartable downloader for the PRIMARY dataset (PhysioNet neuro-stress-resilience-hci 1.0.0, ODbL).
# Usage: scripts/download_matb.sh docs|matb|ppg|eeg pXX [pYY ...]
# Every file is verified against the official SHA256SUMS.txt after download (scripts/verify_matb.sh).
# TLS: on 2026-09-09 physionet.org served an expired Let's Encrypt certificate (notAfter 20:22:45 UTC).
# The project owner authorised certificate-check bypass for these PUBLIC files only (no credentials are
# ever sent); integrity relies on the SHA256 manifest, so set MATB_CURL_INSECURE=1 only when needed.
set -u
B=https://physionet.org/files/neuro-stress-resilience-hci/1.0.0
D=$(cd "$(dirname "$0")/.." && pwd)/data/raw/matb
K=${MATB_CURL_INSECURE:+-k}
get() { mkdir -p "$D/$(dirname "$1")"; curl $K -sS -L --retry 8 --retry-delay 5 --retry-all-errors -m 3600 -C - -o "$D/$1" "$B/$1" || echo "FAIL $1"; }
what=$1; shift
case "$what" in
  docs) for f in README.txt LICENSE.txt SHA256SUMS.txt EEG_32_Channel_mapping.xyz demographicCDrisk.csv fNIRS_frontal.xyz; do get "$f"; done ;;
  matb) for p in "$@"; do get "MATB-II/${p}resman.csv"; done ;;
  ppg)  for p in "$@"; do for f in ACC.csv BVP.csv EDA.csv HR.csv IBI.csv TEMP.csv tags.csv info.txt; do get "PPG/$p/$f"; done; echo "done $p"; done ;;
  eeg)  for p in "$@"; do grp=$(grep -o "EEGfNIRSeye_p[0-9-]*p[0-9]*/$p/$p.csv" "$D/SHA256SUMS.txt" | head -1); [ -n "$grp" ] && get "$grp" || echo "no EEG entry for $p"; done ;;
  *) echo "unknown target $what"; exit 1 ;;
esac
