# STATUS

## 2026-09-09 22:35 UTC — PRIMARY dataset: Checkpoints 1 and 2 COMPLETE (wrist + behaviour N = 35; EEG N = 5)
- physionet.org allowed by the network policy since this session; the site served an **expired Let's Encrypt certificate**
  (notAfter 2026-09-09 20:22:45 UTC; container clock checked against external HTTP Date headers). The owner authorised
  certificate-check bypass for these public files only (no credentials; `MATB_CURL_INSECURE=1 scripts/download_matb.sh`).
  Integrity rests on the official SHA256SUMS.txt: **320/320 downloaded docs + MATB-II + PPG files verify OK**
  (`results/audit/matb_SHA256SUMS_verified.txt`). Dataset is not on AWS Open Data.
- Read README.txt, LICENSE.txt (ODbL), SHA256SUMS.txt (383 entries), directory listings: 35 participants (p14, p23 absent).
- MATB-II format verified and parsed (`myndos.io_matb.read_matb_resman`, tests in `tests/test_matb.py`, 14 tests pass).
- Alignment audit `results/audit/matb_alignment_audit.csv`: 35/35 usable; task zero = E4 tag; HR.csv +10 s in all; one
  double-press tag (p02, 2.83 s); quiet rest on the wrist only for 4 participants.
- Real-data QC finding: vendor HR.csv emits values without a pulse (p01 100-165 bpm, 1.5 % accepted beats; raw BVP is noise).
  HR bins gated by accepted-beat coverage >= 50 % (frozen after inspecting 4 raw traces, before outcomes). No HRV.
- Results (RESULTS.md section 0): HR +1.7 bpm [0.4, 3.0] in challenge 1 (N=31), ~0 in challenge 2; EDA +0.21 uS; target error
  +314 fuel units in challenge 1, +455 in challenge 2, decaying over minutes in recovery; recovery table with censoring;
  prediction test run at N=35: peripheral physiology adds nothing beyond past performance (+0.29 MAE, controls identical).
- Figures: figM1 (p01 first real baseline/challenge/recovery plot), figM2 cohort event-aligned, figM3 recovery incl. censoring,
  figM4 burden vs performance, figM5 added-value.
- Disk/download: 34 MB wrist+behaviour; EEG p01 (606 MB) downloading; 8 GB cap → 5 EEG participants ≈ 3 GB projected.
- Checkpoint 2 (EEG) complete, 22:35 UTC: p01-p05 combined CSVs (577-606 MB each) downloaded one at a time, all SHA256-verified
  (325/325 files OK overall). Orientation, 250-Hz time row, microvolt units, channel order (xyz file) and marker semantics verified
  on every file; 5 markers each = working start + 4 transitions. Cross-device chronology: transitions within 3.3 s of the grid
  for p01/p03/p04/p05; p02's last two markers 50 s early → cycle-2 timing excluded as ambiguous. Whole-recording channel screen
  rejected 15/32 channels for p01 (occipital group empty), 1-5 for the others; 96.7 % of 884 bins pass the window screen.
  EEG responses are small and mixed in sign across the five (RESULTS.md 0.7); multimodal prediction NOT RUN (N=5 < 20).
- Disk: raw primary data 2.9 GB (cap 8 GB), 19 GB free. Nothing deleted.
- Not done: EEG beyond five participants (feasible; one at a time via scripts/download_matb.sh eeg pXX + scripts/matb_eeg.py pXX).

Updated: 2026-09-09 22:40 UTC (primary dataset checkpoints 1-2 complete; earlier EEGMAT/ds007554/BIOT sections below unchanged)

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
- [x] 1. EEGMAT EDF audit, QC, per-bin features, before/during metrics (results/tables/eegmat_*.{csv,json}, results/figures/figE1)
- [x] 2. ds007554 clock/format audit (results/audit/ds007554_*.csv): Delsys ECG/button streams are offset from the EEG/events clock by an undeclared per-file amount (typically +4 to +6.5 s, one -21.75 s); 43/120 button files pass the frozen event-matching acceptance rule; EDF header dates within one 'session' span ~2 months and are not used for chronology
- [x] 3. ds007554 cohort features and descriptives (515 files / 30 participants; results/tables/ds007554_*.{csv,json})
- [x] 4. Held-out prediction test run with controls on the event-matched cohort: 15 participants → labelled insufficient-N/exploratory; physiology added nothing beyond past performance
- [x] 5. Figures (results/figures/fig1-4, figE1), 9 tests passing, RESULTS.md, MANIFEST.md
- [x] 6. Optional BIOT frozen-encoder audit run on EEGMAT (results/tables/biot_frozen_eegmat.json): pretrained frozen embeddings worse than handcrafted band power and not better than random weights
- [x] 7. PRIMARY MATB-II Checkpoint 1: access, checksums, verified parser, audit, cohort metrics, prediction test, figures M1-M5 (21:35 UTC)
- [x] 8. PRIMARY MATB-II Checkpoint 2: EEG p01-p05, one at a time; audit, metrics, figM6 (22:35 UTC)

## Final state (22:40 UTC)
- Deliverables: PLAN.md, README.md, RESULTS.md (section 0 = PRIMARY), MANIFEST.md, requirements.lock.txt, `scripts/run_all.sh`, 16 passing tests,
  audits in results/audit/ (incl. matb_alignment_audit.csv, matb_eeg_audit.csv, matb_SHA256SUMS_verified.txt), participant metrics and JSON
  summaries in results/tables/, figures fig1-4, figE1, figM1-M6 in results/figures/.
- Usable N, PRIMARY: 35/35 wrist+behaviour (HR after pulse gating: 31 cycle 1, 29 cycle 2); EEG 5 (p02 cycle-2 timing ambiguous).
  Prediction test run at N = 35 (peripheral adds nothing); multimodal EEG comparison NOT RUN (N = 5 < 20).
- Earlier tonight (unchanged): EEGMAT 36 (32 cardiac); ds007554 30 / 15 event-matched, prediction insufficient-N; BIOT audit negative.
- Disk: venv ~1 GB (no torch in this container), raw data 2.9 GB primary (+ EEGMAT/ds007554 not re-downloaded in this container); 19 GB free.
  No pre-existing files deleted.
- To extend EEG: `MATB_CURL_INSECURE=1 scripts/download_matb.sh eeg pXX && .venv/bin/python scripts/matb_eeg.py pXX` (one at a time; the
  TLS bypass is only needed while physionet.org's certificate is expired).
