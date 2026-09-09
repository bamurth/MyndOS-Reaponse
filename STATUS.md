# STATUS

Updated: 2026-09-09 19:40 UTC (checkpoint 0: environment and data access)

## Environment
- Claude Code cloud session, 4 vCPU, 15 GB RAM, 30 GB writable disk, CPU only.
- Python 3.11.15 venv at `.venv`; numpy 2.4.6, pandas 3.0.5, scipy 1.17.1,
  scikit-learn 1.9.0, matplotlib 3.11.1, pyedflib 0.1.42, mne 1.13.0.

## Data access audit (performed 2026-09-09 19:33–19:40 UTC)

| Source | Route tried | Result |
|---|---|---|
| PRIMARY neuro-stress-resilience-hci (physionet.org/content, /files) | curl via egress proxy | **BLOCKED**: proxy answers 403 to CONNECT physionet.org:443 (network policy denial) |
| PRIMARY via WebFetch tool | tool | **BLOCKED**: `EGRESS_BLOCKED domain physionet.org` |
| PRIMARY via AWS Open Data mirror `s3://physionet-open` | S3 listing | **NOT MIRRORED**: 0 keys under `neuro-stress-resilience-hci/`; all 253 mirrored prefixes enumerated, no matching slug |
| BACKUP eegmat 1.0.0 | `physionet-open` S3 mirror | **OK**: `eegmat-1.0.0.zip` 183,634,285 bytes downloaded; all 75 SHA256SUMS entries verified OK |
| NEXT CMx7-MM / OpenNeuro ds007554 | `s3://openneuro.org/ds007554/` | **OK**: 5,738 objects, 4.52 GB total, CC0, BIDS layout with per-task EEG EDF, ECG tsv.gz, push-button, events.tsv, cognitive-load ratings |
| openneuro.org website, archive.ics.uci.edu, zenodo, osf, figshare, huggingface | curl | blocked (000) |
| github.com raw / api | curl | OK |
| drivedb, cebsdb, challenge-2018, wearable-exam-stress | `physionet-open` mirror | present (not used tonight) |

## Action required from the owner (cannot be resolved from inside the session)
Add `physionet.org` to the allowed domains of this cloud environment's network
policy (Claude Code on the web: environment settings → network access). No
other route to the primary dataset exists from this container. The MATB-II
pipeline in this repo is written against the documented E4/MATB formats but is
**untested on real primary data** until access is granted; nothing in
RESULTS.md is attributed to the primary dataset.

## Decision taken under the blocker
1. Preserve the plan's analysis definitions and build the restartable pipeline.
2. Produce real results tonight from the two reachable concurrent datasets:
   - EEGMAT (EEG + ECG, baseline vs mental arithmetic, N=36, behavioral anchor =
     number of subtractions / count-quality group): before/during evidence only,
     no recovery.
   - ds007554 (EEG + ECG + push-button behavior + per-task cognitive load ratings,
     N=30, 3 sessions, 7 task types of graded demand): concurrent
     brain–body–behavior trajectories and, if usable N permits, the held-out
     added-value prediction test on trial-level behavior.
3. Never relabel either of these as MATB response–recovery evidence.

## Checkpoints
- [x] 0. Environment, access audit, plan committed
- [ ] 1. EEGMAT EDF audit, QC, per-bin features, before/during metrics
- [ ] 2. ds007554 one-subject clock/format audit
- [ ] 3. ds007554 cohort features and descriptives
- [ ] 4. Held-out prediction test (if N ≥ 20 usable) with controls
- [ ] 5. Figures, tests, RESULTS.md, manifest
