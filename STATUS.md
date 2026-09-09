# STATUS

## 2026-09-09 21:10 UTC — PRIMARY dataset access restored; Checkpoint 1 INTERIM (partial cohort, download in progress)
- physionet.org is now allowed by the network policy, but the site served an **expired Let's Encrypt certificate**
  (notAfter 2026-09-09 20:22:45 UTC; container clock verified against external HTTP Date headers). The owner authorised
  certificate-check bypass for these public files only (no credentials involved); integrity relies on the official
  SHA256SUMS.txt: **all 48 files fetched so far verify OK** (results/audit/matb_SHA256SUMS_verified.txt). Not on AWS Open Data.
- Read README.txt, LICENSE.txt (ODbL), SHA256SUMS.txt (383 entries), directory listings: 35 participants (p14, p23 absent),
  `MATB-II/pXXresman.csv` (35 files, 6.3-6.8 KB), `PPG/pXX/{ACC,BVP,EDA,HR,IBI,TEMP,tags}.csv+info.txt`,
  `EEGfNIRSeye_*/pXX/pXX.csv` (p01 = 606,286,984 B).
- MATB-II format verified and parser implemented (`myndos.io_matb.read_matb_resman`): ELAPSED_TIME mm:ss.s at a 10-s
  cadence from working start, TANK_A-D, DIFF_A/B == TANK-2500 in every file; 179-180 rows (29:50-30:00). p01 E4 tag sits
  61.6 s after session start, HR.csv starts +10 s, task time zero = tag (rule frozen).
- Real-data QC finding: vendor HR.csv keeps emitting values with no pulse in the PPG (p01: 100-165 bpm with 1.5 % accepted
  beats; raw BVP shows no waveform for p01/p02). HR bins are therefore gated by accepted-beat (IBI) coverage >= 50 %.
- Interim run on the 20 participants downloaded at that time: all usable, N=20 prediction test executed. Numbers in
  results/tables/matb_* are INTERIM and will be overwritten by the full-cohort run.
- Downloads in progress: remaining PPG folders (~1.4 MB each), then EEG p01 (606 MB). 8 GB cap: ~0.7 GB projected for 5 EEG participants.


Updated: 2026-09-09 21:15 UTC (checkpoint 3, final for tonight: BIOT audit run; all deliverables except the blocked primary dataset)

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
- [ ] 7. PRIMARY MATB-II: waiting on physionet.org network access; scripts/matb_pipeline.py ready but untested on real data

## Final state (21:15 UTC)
- Deliverables present: PLAN.md, README.md, RESULTS.md, MANIFEST.md, requirements.lock.txt, `scripts/run_all.sh`, 9 passing tests,
  audits in results/audit/, participant/file metrics and JSON summaries in results/tables/, five figures in results/figures/.
- Usable N: EEGMAT 36 (32 cardiac); ds007554 30 (EEG-clock descriptives), 15 (cardiac+behaviour, event-matched), prediction test insufficient-N.
- Not delivered: anything from the primary MATB-II dataset (network policy). Recovery dynamics were not measurable on the reachable datasets.
- Disk: ~6 GB venv (torch), 3.5 GB raw data; 18 GB free. No pre-existing files deleted.
- To resume: allow physionet.org in the environment network settings, then `scripts/matb_pipeline.py` (after inspecting the MATB-II performance
  file format, which is unverified) and re-run `scripts/run_all.sh`.
