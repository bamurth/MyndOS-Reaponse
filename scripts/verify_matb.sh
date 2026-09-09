#!/bin/sh
# Verify every downloaded primary-dataset file against the official SHA256SUMS.txt; writes results/audit/matb_SHA256SUMS_verified.txt
set -u
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R/data/raw/matb" || exit 1
while read -r sum f; do [ -f "$f" ] && echo "$sum $f"; done < SHA256SUMS.txt | sha256sum -c > "$R/results/audit/matb_SHA256SUMS_verified.txt" 2>&1
echo "verified OK: $(grep -c ': OK$' "$R/results/audit/matb_SHA256SUMS_verified.txt"); FAILED: $(grep -vc ': OK$' "$R/results/audit/matb_SHA256SUMS_verified.txt")"
grep -v ': OK$' "$R/results/audit/matb_SHA256SUMS_verified.txt" || true
