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
* **Primary MATB-II dataset**: NOT run. physionet.org is blocked by this cloud environment's network
  policy. `scripts/matb_pipeline.py` implements the wrist/behaviour checkpoint and will run when access is granted.

## Reproduce
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt
scripts/run_all.sh            # tests, EEGMAT, ds007554, figures (downloads data if absent)
```
Individual steps: `scripts/eegmat_features.py`, `scripts/eegmat_analysis.py`,
`scripts/ds007554_alignment_audit.py`, `scripts/ds007554_features.py`, `scripts/ds007554_analysis.py`,
`scripts/make_figures.py`, `scripts/matb_pipeline.py`. Tests: `.venv/bin/python -m pytest`.

## Layout
* `src/myndos/` library: `signal.py` (R-peaks, beat quality, EEG band power, artifact screen),
  `binning.py` (boundary-safe 10-s bins), `metrics.py` (frozen response/recovery estimators),
  `modeling.py` (strictly-future targets, participant-disjoint nested ridge, controls, paired bootstrap),
  `io_*.py` (loaders), `encoder.py` (encoder interface; BIOT contract documented, not run).
* `results/audit/` alignment and QC audits; `results/tables/` participant/file metrics and JSON summaries;
  `results/figures/` the four static figures. Raw data and per-bin features are never committed.
