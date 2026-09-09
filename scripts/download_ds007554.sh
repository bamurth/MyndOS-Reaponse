#!/bin/sh
# Restartable downloader for OpenNeuro ds007554 (EEG + ECG + push-button only; fNIRS/EMG/biodex skipped).
# Skips files whose size already matches the S3 listing. Usage: scripts/download_ds007554.sh LISTFILE
set -u
B=https://s3.amazonaws.com/openneuro.org/ds007554
D=/home/user/MyndOS-Reaponse/data/raw/ds007554
cd "$D" || exit 1
while read size key; do
  k=${key#ds007554/}
  if [ -f "$k" ] && [ "$(stat -c %s "$k")" = "$size" ]; then continue; fi
  mkdir -p "$(dirname "$k")"
  echo "$k"
done < "$1" | xargs -P 4 -I{} sh -c 'curl -sS -m 600 --retry 3 -o "{}" "'"$B"'/{}" || echo "FAIL {}"'
echo DOWNLOAD_PASS_DONE
