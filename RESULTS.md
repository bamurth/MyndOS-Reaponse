# RESULTS — MyndOS response dynamics, 2026-09-09

Everything below was computed tonight from public data inside this repository by `scripts/run_all.sh`.
Nothing is attributed to the primary MATB-II dataset, which could not be reached (see STATUS.md).
Seeds = 0. Frozen parameters as in PLAN.md (10-s bins, ±2 robust-unit band with ±1.5/±2.5 sensitivity,
3 consecutive valid bins, median/1.4826·MAD normalization).

## 0. What kind of evidence each section is

| Section | Dataset | Evidence type |
|---|---|---|
| 1 | EEGMAT (PhysioNet) | Real concurrent EEG+ECG, **before vs during** mental arithmetic; separate recordings; no recovery |
| 2 | ds007554 / CMx7-MM (OpenNeuro) | Real concurrent EEG+ECG+behaviour, 25-s rest → 3-min task; **no recovery period**; cross-device clock unverified except where event-matched |
| 3 | ds007554 | Held-out added-value prediction test: **insufficient-N (15 < 20), exploratory** |
| 4 | — | Primary MATB-II response–recovery: **not run** (blocked) |
| 5 | — | Foundation-model encoder (BIOT): **audited, not run** |
| Tests | synthetic | Software checks only, never evidence about people |

## 1. EEGMAT: EEG + ECG before and during mental arithmetic (N = 36)

Data: 36 subjects × 2 EDF files (baseline `_1`: 182 s in 33 subjects, 170/188/80 s in three; task `_2`: 62 s in all), 21 signals at 500 Hz
(19 monopolar EEG in µV, A2-A1, ECG in mV). All 72 headers audited (`results/audit/eegmat_edf_audit.csv`); all 75 official checksums verified.
Matched comparison: last 60 s of the baseline file vs the 60-s task file (sensitivity: whole baseline, last column).
Cardiac exclusion (frozen rule: valid-beat coverage ≥ 0.8 in both files) removed 4 subjects (02, 13, 20, 35; low-amplitude ECG) → cardiac N = 32.

Participant-level paired change (task − baseline), mean with participant-bootstrap 95% CI:

| Feature | N | mean Δ | 95% CI | fraction Δ>0 | Wilcoxon p | Δ vs whole baseline |
|---|---|---|---|---|---|---|
| Heart rate (bpm) | 32 | +14.9 | [+12.0, +18.1] | 1.00 | 4.7e-10 | +14.8 |
| RMSSD, 30-s windows (ms) | 32 | −13.9 | [−18.8, −9.5] | 0.06 | 7.9e-08 | −14.5 |
| Frontal log10 theta | 36 | +0.070 | [+0.009, +0.131] | 0.64 | 0.038 | +0.068 |
| Frontal log10 alpha | 36 | −0.107 | [−0.169, −0.046] | 0.33 | 0.0025 | −0.123 |
| Central log10 alpha | 36 | −0.185 | [−0.248, −0.122] | 0.14 | 4.0e-06 | −0.183 |
| Parietal log10 alpha | 36 | −0.270 | [−0.367, −0.169] | 0.14 | 1.5e-05 | −0.271 |
| Occipital log10 alpha | 36 | −0.244 | [−0.351, −0.129] | 0.22 | 7.8e-05 | −0.256 |
| Parietal log10 beta | 36 | −0.076 | [−0.115, −0.039] | 0.25 | 5.8e-04 | −0.083 |

Full table: `results/tables/eegmat_summary.json`; per participant: `results/tables/eegmat_participant_metrics.csv`; Figure E1.

Held-out (participant-grouped 12-fold) classification of *baseline vs task* from single 10-s bins:

| Inputs | pooled AUC | mean within-participant AUC | N bins / participants |
|---|---|---|---|
| cardiac (HR, RMSSD) | 0.755 | 0.966 | 757 / 32 |
| EEG (12 band-power features) | 0.697 | 0.830 | 853 / 36 |
| cardiac + EEG | 0.789 | 0.938 | 853 / 36 |

Association of the physiological change with the behavioural anchor (subtractions per 4 min): Spearman ρ between −0.07 and +0.20 for every feature,
none with p < 0.2 (`associations` in the JSON). Leave-one-participant-out ridge predicting subtractions from physiological change was **worse** than
predicting the training mean (MAE 8.8–9.8 vs 8.5; Spearman(pred, true) negative). **Negative result**: on this dataset the *size* of the
physiological response does not carry information about counting performance.

Caveats: the released EEG is ICA-cleaned, 30-Hz low-passed; baseline and task are separate files, so no timing or recovery estimate is possible;
"during" starts after the task instruction, not at a marked onset.

## 2. ds007554 / CMx7-MM: concurrent EEG, ECG and behaviour around graded 3-minute tasks

Data downloaded: 515 EEG EDF files (30 participants, 87 participant-sessions; 2–7 tasks per session), 481 with ECG, 120 push-button files,
per-task subjective load ratings. 32-channel EEG at 250 Hz; Delsys ECG at 1882 Hz; each file = 25 s pre-task rest, 180 s task, ~11 s post.

### 2.1 Chronology audit (results/audit/ds007554_files.csv, ds007554_button_alignment.csv)
* EEG and `events.tsv` share the EEG clock (first `start` event at 25.0 s in all 515 files); accepted as declared (no trigger channel to verify).
* ECG and push-button (`physio.json`, StartTime 0, same Delsys system) are **not** on the EEG clock: push-button presses match stimulus targets only
  after a per-file shift, typically **+3.5 to +6.5 s** (accepted files: ses-01 median +4.5, ses-03 +4.0, nbackarithmetic +5.25) and a cluster at
  **−21.5 to −22.25 s** for session-2 2-back files. This was found by behavioural event matching (press onsets vs target onsets on a 0.25-s grid);
  no physiological correlation was used. Frozen acceptance rule (≥ 8 hits, ≥ 2× grid median, second peak ≤ 0.6× best): **43/120 files, 15 participants**.
  46 rejected files had zero presses, 4 had < 8, 27 had ≥ 8 presses but no unambiguous peak.
* EDF header dates inside one "session" span ~64 days (median), so headers cannot order tasks within a session; not used.
* Consequence: ECG and behaviour are placed on the EEG clock **only** for event-matched files (`clock_source = event_matched`). All other ECG is used at file level only.

### 2.2 EEG demand response on the EEG clock (all files)
Reference = pooled pre-task rest bins of the same participant-session (median 12 valid 10-s bins). 89/515 files had a near-zero MAD reference (21 sessions with < 6 valid rest bins) and carry `scale_flag`; robust-unit results exclude them. EEG artifact screen kept 76% of rest bins, 83% of task bins, 8% of post bins.

Task median minus rest median (log10 µV², median [IQR] over files; n files/participants):

| Task | Frontal theta | Parietal alpha | Central beta |
|---|---|---|---|
| passivemotor | −0.060 [−0.12, 0.07] 40/24 | −0.035 [−0.11, 0.06] | −0.061 [−0.17, −0.01] |
| motorimagery | −0.181 [−0.27, −0.07] 69/30 | −0.008 [−0.10, 0.13] | −0.091 [−0.21, −0.05] |
| activemotor | −0.048 [−0.13, 0.06] 58/27 | −0.002 [−0.07, 0.07] | −0.044 [−0.16, 0.00] |
| mentalarithmetic | −0.127 [−0.23, −0.03] 67/28 | −0.003 [−0.07, 0.08] | −0.077 [−0.23, −0.01] |
| nback | −0.072 [−0.22, 0.06] 71/30 | −0.033 [−0.10, 0.14] | −0.089 [−0.25, −0.02] |
| nbackarithmetic | −0.038 [−0.17, 0.09] 64/28 | +0.019 [−0.09, 0.10] | −0.069 [−0.21, −0.01] |
| full | −0.042 [−0.15, 0.08] 68/28 | −0.012 [−0.11, 0.11] | −0.073 [−0.14, 0.03] |

* A sustained departure from the ±2 rest band (3 consecutive valid bins) occurred in only 12–35% of files per task and feature (Figure 2); median departure times 20–85 s. Most files show **no measurable excursion** at this band, so response timing is mostly not estimable.
* **Recovery: not estimable** on this dataset (one post-task bin, 92% artifact-rejected).
* Within-person Spearman correlation of the response (robust units) with the participant's own subjective load rating across tasks: mean ρ between −0.07 and +0.08 for all four features, 95% CIs include 0 (n = 25 participants). Same for the declared demand ranking. **The EEG band-power response does not track demand level here.**
* Cardiac (event-matched files, own 25-s rest reference): HR task − rest = **−0.15 bpm** [−1.8, +1.4] (15 participants, 38 files). File-level HR across all 481 ECG files is flat across task types (medians 67–71 bpm). **No cardiac demand response was observed** for these seated 3-minute tasks.
* Behaviour (event-matched files): hit rate 577/774 targets, mean error rate 0.082 per event.

### 2.3 Burden vs performance (Figure 3)
No relationship is claimed: parietal-alpha burden and HR response vs task error rate (43 files) show no visible structure, and the EEGMAT anchors above are null.

## 3. Held-out added-value prediction test (ds007554, event-matched files) — INSUFFICIENT-N, EXPLORATORY
Target: mean error rate over the next non-overlapping 30 s within the same task file; inputs end at the current bin. 645 windows, 43 files, **15 participants** (< 20 floor → exploratory, not a claim). Ridge, imputation/scaling fitted inside folds, alpha by inner participant-grouped CV, 10 participant-disjoint outer folds, equal participant weighting.

| Model | participant-weighted MAE | paired Δ vs context (95% CI) |
|---|---|---|
| persistence (last 30 s) | 0.0735 | +0.0142 [+0.0057, +0.0210] |
| condition + time only | 0.0629 | +0.0036 [−0.0007, +0.0096] |
| **context + past performance** | **0.0593** | reference |
| + peripheral (HR, RMSSD, HR vs rest) | 0.0600 | +0.0007 [+0.0001, +0.0014] |
| + peripheral + EEG (24 features) | 0.0616 | +0.0023 [+0.0004, +0.0042] |
| control: physiology from a different participant (matched task, 30-s epoch) | 0.0604 | +0.0011 [+0.0005, +0.0017] |
| control: physiology shifted 3 bins within person | 0.0615 | +0.0004 [+0.0004, +0.0042] |

Target mean 0.085, SD 0.081. **Physiology did not add information** beyond task context and recent performance in this cohort; the real-physiology
models are indistinguishable from the mismatched-physiology and temporal-shift controls (all slightly worse than context alone, consistent with
overfitting 24–28 features on 15 people). Per-participant MAEs: `results/tables/ds007554_prediction_participant_mae.csv`.

## 4. Primary MATB-II response–recovery benchmark — NOT RUN
physionet.org is blocked by the cloud environment's network policy (proxy 403 for curl and for the WebFetch tool), and the dataset is not in the
AWS Open Data mirror (all 253 mirrored prefixes enumerated). `scripts/matb_pipeline.py` implements Checkpoint 1 (E4 audit, bins, frozen metrics,
censoring) against the published E4 format, exits when data are absent, and is untested on real primary files. The four MATB figures and the
20-participant prediction test remain to be produced once `physionet.org` is allowed in the environment's network settings.

## 5. Foundation-model encoder — AUDITED, NOT RUN
BIOT (github.com/ycq091044/BIOT, MIT): `EEG-PREST-16-channels.ckpt` (13,791,969 B) is reachable and its 16 bipolar montages are derivable from
EEGMAT's 19 monopolar channels (`myndos.encoder.bipolar_montage`). Requirements not met tonight: a CPU-only torch wheel is unreachable
(download.pytorch.org blocked); see STATUS.md for the outcome of the PyPI attempt. No embedding, no comparison with handcrafted features, no
random-weight branch was produced. Ridge/PCA/handcrafted features are not a foundation model.

## 6. Software tests
9 synthetic tests pass (`.venv/bin/python -m pytest`): R-peak recovery and polarity, HRV requires beat coverage, bins never cross boundaries,
zero-MAD flag, sustained departure/burden/censored recovery, EEG artifact rejection and channel groups, E4 parsers, strictly-future within-condition
targets, participant-disjoint folds. No test failed at the time of writing.

## 7. Usable N and what may be said
* EEGMAT: 36 participants (32 cardiac). **Supported claim**: concurrent EEG and ECG both change during mental arithmetic in essentially every
  participant (HR +15 bpm, alpha suppression), and a held-out model separates the two states from 10-s windows. **Not supported**: any link between
  the size of that response and performance.
* ds007554: 30 participants for EEG-clock descriptives; 15 for cardiac/behaviour pairing. **Supported claim**: the pipeline measures per-file
  responses with explicit censoring and clock provenance. **Observed**: no consistent EEG or cardiac demand response and no added predictive value
  of physiology at this N. This is a null result on a dataset with short, seated tasks and an unverified cross-device clock, not evidence against
  the approach; it is also not evidence for it.
* Recovery dynamics (the core MyndOS claim) were **not measurable** on any reachable dataset tonight; they require the primary dataset.
* None of this supports clinical diagnosis, cognitive reserve, treatment monitoring or investment claims.
