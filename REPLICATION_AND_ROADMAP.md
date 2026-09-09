# External replication plan and methodology roadmap

## 1. Access reality (checked 2026-09-10 00:05 UTC from the analysis container)
Reachable: physionet.org (expired certificate, checksum-verified downloads), the PhysioNet AWS Open Data mirror (252 dataset slugs
enumerated), github.com. Blocked by the environment's egress policy (CONNECT 403): zenodo.org, osf.io, figshare.com, borealisdata.ca,
data.mendeley.com, openneuro.org, ieee-dataport.org, nature.com. No credentials were submitted anywhere and no restriction was bypassed.
Consequence: CLARE (Bhatti et al. 2024; MATB-II with ECG/EDA/EEG/gaze; hosted outside PhysioNet) could not be inspected, only described
from the literature; it stays a candidate to inspect, not an assumed match.

## 2. Suitability table (what each dataset can and cannot test)

| Dataset | Concurrent modalities | N | Demand change | Baseline / recovery | Repeated challenge | Task performance | Access & terms | Hypothesis it can test |
|---|---|---|---|---|---|---|---|---|
| **neuro-stress-resilience-hci 1.0.0 (this study)** | wrist PPG/EDA/TEMP/ACC + 32-ch EEG + fNIRS + RESMAN log | 35 | RESMAN -> +COMMS | 6-min working baseline; two 6-min recoveries (COMMS removed) | yes (2 cycles, fixed order) | continuous (10-s snapshots) | PhysioNet, ODbL, verified | the primary question, as run here |
| drivedb 1.0.0 (Healey & Picard) | ECG, EDA (hand/foot), EMG, respiration; marker channel | 17 drives (some incomplete) | rest -> city -> highway -> city -> rest | 15-min rest before and after | yes (city twice, highway once) | none (self-report stress per segment) | PhysioNet mirror, ODbL-type PhysioNet terms, verified on the mirror | ECG-derived recovery dynamics with censoring; consistency of HR/EDA response across the two city segments; **transfer to another task, physiology only** |
| eeg-eye-gaze-for-fls-tasks 1.0.0 | EEG + eye gaze | ~30 trainees x tasks (EDF per task) | surgical training task blocks | no marked recovery | task repeats | task scores (FLS) | PhysioNet mirror, verified | EEG-vs-performance transfer only; no recovery |
| wearable-exam-stress 1.0.0 | E4 wrist only | 10 students x 3 exams | exam (hours) | none within recording | across exams | grade only | PhysioNet mirror, verified | wrist reactivity vs outcome at whole-session level; **not** recovery |
| EEGMAT 1.0.0 (used earlier) | EEG + ECG | 36 | rest -> arithmetic | no recovery (separate files) | no | subtraction count | PhysioNet, verified | before/during only (RESULTS.md 1) |
| ds007554 CMx7-MM (used earlier) | EEG + ECG + button | 30 | 25-s rest -> 3-min task | 11 s after task only | 7 task types | button accuracy | OpenNeuro CC0 (blocked now) | graded demand response, no recovery (RESULTS.md 2) |
| CLARE (literature only) | ECG, EDA, EEG, gaze during MATB-II | 24 (per paper) | MATB-II difficulty levels | unknown from here | per paper: several levels | MATB-II performance (per paper) | not reachable from this environment | potentially the closest **exact-task** replication; must be inspected first |

Selection: **drivedb** is the only reachable dataset with baseline, repeated demand changes and a true post-demand rest, so it is the
best fit for replicating the *recovery methodology* (ECG rather than wrist PPG). It cannot test the primary behaviour-prediction
hypothesis. Frozen endpoint for that replication (before looking at any drivedb outcome): HR (from ECG R-peaks, `myndos.signal`) and
EDA response magnitude for city-1 and city-2 vs the initial rest; recovery in the final rest = time to sustained return (band +-2, k = 3,
10-s bins) with right-censoring; consistency = Spearman between city-1 and city-2 HR response across drivers. Status: **planned, not run**
(this session prioritised the primary experiment; the data are ~200 MB on the mirror and WFDB format 16 is parseable without new packages).

Replication classes for any future run: exact replication (same MATB-II design; only CLARE or a new collection); transfer to another task
(drivedb, FLS); partial support for a related hypothesis (EEGMAT/ds007554 before-during evidence).

## 3. Methodology roadmap (organised by the four dynamics)

For each proposed feature: operational definition -> biological interpretation (hypothesis, not fact) -> observable outcome ->
confounders -> validation needed.

**Reactivity**
* Definition: challenge median minus end-of-baseline median (physical units) and robust-unit version; first sustained departure.
* Hypothesis: autonomic/cortical engagement scales with imposed demand. Outcome: concurrent task error, subjective load.
* Confounders: movement, sensor contact (wrist PPG fails in 4/35), time-on-task drift (temperature), block scripts.
* Validation: dose-response across graded demand (ds007554-type designs), ECG vs PPG agreement, test-retest across days.

**Recovery**
* Definition: integrated excess over the recovery window (primary), time to sustained return with censoring (secondary), residual at end,
  slope, exponential tau when the fit qualifies.
* Hypothesis: speed of return indexes regulatory capacity. Outcome: performance in the following block; subjective recovery.
* Confounders: the "recovery" task is easier but not baseline (error stays elevated; baseline itself drifts); fixed order; censoring at
  360 s truncates slow recoverers; vendor HR lag.
* Validation: longer and counterbalanced recovery periods, replication with ECG (drivedb), within-person reliability.

**Carryover**
* Definition: residual deviation at the end of recovery 1 (behaviour, HR, EDA, EEG) and its association with cycle-2 outcomes
  after adjusting for cycle-1 performance.
* Hypothesis: incomplete recovery raises vulnerability to the next demand. Outcome: cycle-2 error and cycle-2 recovery.
* Confounders: fatigue, practice, block difficulty, regression to the mean. Validation: randomised inter-challenge intervals; test-retest.

**Cross-system coordination**
* Definition: per-modality return times and their differences; lag structure between behaviour, autonomic and EEG trajectories.
* Hypothesis: desynchronised recovery signals inefficient regulation. Outcome: cycle-2 performance. Confounders: sensor lags
  (E4 HR ~10 s, EDA seconds), artifact-driven EEG gaps, shared task timing. Validation: only after ECG-grade timing and lag calibration.

**What is required next**
* Across-day reliability: two sessions >= 7 days apart, same protocol; ICC of each endpoint; minimal detectable change.
* Within-person meaningful change: repeated sessions with an anchor (subjective, performance) to define a change threshold.
* Generalisation to another challenge: same participants, MATB-II and a non-MATB stressor (arithmetic, social); correlation of endpoints.
* Prospective intervention-response: see section 4. Clinically characterised cohorts and differentiation of causes of impairment require
  diagnosed groups and ECG/EEG of research grade; nothing in this dataset speaks to diagnosis, etiology or treatment selection.

## 4. Proposed controlled prospective study (design level only)
Randomised, two-arm, three-session design: session 1 (baseline dynamics), 4-6 weeks of intervention vs active control (matched time
and attention), session 2 (post), session 3 (retention at 3 months). Primary endpoint: change in recovery integrated excess error and HR
recovery (ECG) in cycle 1, adjusted for session-1 values and practice (the control arm estimates practice effects). Sample size to be
powered on session-1 test-retest ICC from the reliability study above. Pre-registered analysis identical to `scripts/primary_prediction.py`.

## 5. Development path
* Gen 1: reproducible task-based wellness/performance assessment: fixed MATB-II-like protocol, behaviour-first endpoints, wrist sensor
  optional; claims limited to reactivity and observed recovery of performance.
* Gen 2: longitudinal and wearable validation: across-day reliability, ECG-grade chest patch or validated PPG, meaningful-change thresholds.
* Gen 3: EEG-enriched clinical validation for specific indications: only after Gen 2, in characterised cohorts, with pre-registered endpoints.
