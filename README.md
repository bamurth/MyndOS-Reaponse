# MyndOS response dynamics benchmark

CPU-only, reproducible benchmark of how concurrent physiology (EEG, ECG) responds when cognitive
demand changes, with task performance measured alongside. `PLAN.md` is the owner's brief;
`STATUS.md` is the live checkpoint log and blocker list; `RESULTS.md` reports what was actually
observed; `MANIFEST.md` lists sources, licenses and checksums.

## What ran tonight (2026-09-09)
* **EEGMAT** (EEG+ECG, baseline vs mental arithmetic, N=36): before/during evidence, held-out state
  classification, and a (negative) held-out test of predicting counting performance from physiological change.
* **OpenNeuro ds007554 / CMx7-MM** (EEG+ECG+push-button, 30 participants, 3 sessions, 7 graded tasks):
  chronology audit, EEG-clock demand-response descriptives, and the held-out added-value prediction
  test on the subset whose behaviour stream could be placed on the EEG clock (15 participants: insufficient-N).
* **BIOT frozen-encoder audit** on EEGMAT windows: run; pretrained embeddings under-perform handcrafted band power.
* **PRIMARY MATB-II dataset** (PhysioNet neuro-stress-resilience-hci 1.0.0; wrist E4 + RESMAN performance, 35 participants;
  EEG for a five-participant subset): run on 2026-09-09 once physionet.org was allowed. Alignment/QC audit, per-participant
  response/recovery metrics for both challenge cycles, block performance, the held-out added-value prediction test and
  figures `figM1`-`figM5` (see RESULTS.md section 0).

## 2026-09-10 additions (participant-level primary experiment)
* `configs/primary_experiment_frozen.md` (frozen before running), `scripts/recovery_validity.py` (endpoint validity + sensitivity, figures R1-R2),
  `scripts/cross_modality_timing.py` (figure R3), `scripts/primary_prediction.py` (nested models A-F, controls, ablation, shortening curve,
  figures P1-P3), `scripts/drivedb_recovery.py` (external ECG transfer test, figure X1), lanes for EEG (`scripts/eeg_lane.sh`).
* Documents: RESULTS_SUMMARY.md, METHODS_AND_QC.md, CLAIMS_LEDGER.md, NEXT_EXPERIMENTS.md, REPLICATION_AND_ROADMAP.md.

## Reproduce
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt
scripts/run_all.sh            # tests, EEGMAT, ds007554, figures (downloads data if absent)
```
Individual steps: `scripts/eegmat_features.py`, `scripts/eegmat_analysis.py`,
`scripts/ds007554_alignment_audit.py`, `scripts/ds007554_features.py`, `scripts/ds007554_analysis.py`,
`scripts/make_figures.py`, `scripts/download_matb.sh` + `scripts/verify_matb.sh` + `scripts/matb_pipeline.py` (primary wrist/behaviour),
`scripts/matb_eeg.py` (primary EEG, one participant at a time), optional `scripts/biot_frozen_eegmat.py` (needs torch; fetch the BIOT checkpoint and `model/biot.py` into `data/cache/biot/` first). Tests: `.venv/bin/python -m pytest`.

## Layout
* `src/myndos/` library: `signal.py` (R-peaks, beat quality, EEG band power, artifact screen),
  `binning.py` (boundary-safe 10-s bins), `metrics.py` (frozen response/recovery estimators),
  `modeling.py` (strictly-future targets, participant-disjoint nested ridge, controls, paired bootstrap),
  `io_*.py` (loaders), `encoder.py` (encoder interface; BIOT contract documented, not run).
* `results/audit/` alignment and QC audits; `results/tables/` participant/file metrics and JSON summaries;
  `results/figures/` the four static figures. Raw data and per-bin features are never committed.
