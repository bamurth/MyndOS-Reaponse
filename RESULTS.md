# RESULTS — MyndOS response dynamics, 2026-09-09

Everything below was computed tonight from public data inside this repository by `scripts/run_all.sh`.
Section 0 (added 21:30 UTC) is the PRIMARY MATB-II dataset, reached once the network policy allowed physionet.org;
sections 1-5 were produced earlier while it was blocked and are unchanged.
Seeds = 0. Frozen parameters as in PLAN.md (10-s bins, ±2 robust-unit band with ±1.5/±2.5 sensitivity,
3 consecutive valid bins, median/1.4826·MAD normalization).

## 0. What kind of evidence each section is

| Section | Dataset | Evidence type |
|---|---|---|
| 0 | PRIMARY neuro-stress-resilience-hci (PhysioNet) | Real wrist physiology + concurrent MATB-II performance through **baseline, challenge 1, recovery 1, challenge 2, recovery 2** (N = 35); held-out prediction test **run** (N = 35 ≥ 20); EEG: Checkpoint 2, see 0.7 |
| 1 | EEGMAT (PhysioNet) | Real concurrent EEG+ECG, **before vs during** mental arithmetic; separate recordings; no recovery |
| 2 | ds007554 / CMx7-MM (OpenNeuro) | Real concurrent EEG+ECG+behaviour, 25-s rest → 3-min task; **no recovery period**; cross-device clock unverified except where event-matched |
| 3 | ds007554 | Held-out added-value prediction test: **insufficient-N (15 < 20), exploratory** |
| 4 | — | (superseded by section 0) |
| 5 | EEGMAT | Foundation-model encoder audit (BIOT frozen): **run**, negative vs handcrafted features |
| Tests | synthetic | Software checks only, never evidence about people |

## 0. PRIMARY: MATB-II stress-resilience dataset, wrist physiology + RESMAN performance (N = 35)

Source `https://physionet.org/files/neuro-stress-resilience-hci/1.0.0/` (ODbL). 35 participants (p14, p23 do not exist in the release).
Files used: `MATB-II/pXXresman.csv` (35) and `PPG/pXX/{ACC,BVP,EDA,HR,IBI,TEMP,tags}.csv` + `info.txt` (35 × 8); all 320 verified against the
official `SHA256SUMS.txt` (`results/audit/matb_SHA256SUMS_verified.txt`). Pipeline: `scripts/matb_pipeline.py`; audit: `results/audit/matb_alignment_audit.csv`;
tables: `results/tables/matb_{participant_metrics,performance_by_block,prediction_participant_mae}.csv`, `matb_summary.json`; figures M1-M5.

### 0.1 Formats verified on the real files (before any analysis)
* **MATB-II log** = RESMAN fuel snapshots every 10 s (`ELAPSED_TIME` mm:ss.s from working start, `TANK_A..D`, `DIFF_A/B`). `DIFF == TANK − 2500` in all 35 files;
  179-180 rows (29:50 or 30:00); no cadence anomalies (tolerance 0.5 s). Task performance = mean of |DIFF_A|, |DIFF_B| (fuel units from the 2500 target)
  — a 10-s snapshot, so the "fixed interval" of PLAN.md is the mean of snapshots inside the interval.
* **E4**: session start row + fs row + samples, ACC 32 Hz (1/64 g), BVP 64 Hz, EDA 4 Hz (µS), TEMP 4 Hz, HR 1 Hz; `HR.csv` starts exactly +10 s after
  the other files in all 35 sessions; `IBI.csv` sparse and irregular; `tags.csv` = working-baseline start (README).
* **Chronology rule (frozen)**: task time zero = first E4 tag; `t_epoch = tag + ELAPSED_TIME`; five 360-s blocks from the tag; quiet rest = ≤ 60 s before the tag.
  No signal-derived offsets. Single tag in 34/35; p02 has a double press 2.83 s apart (first press used, recorded as `tag_uncertainty_s`, below the 5-s limit
  for timing estimates). E4 coverage after the tag ≥ 1,825 s in all 35. **Quiet rest is captured on the wrist for only 4 participants** (p01, p03, p07, p16:
  34-239 s before the tag); the other 31 tags were pressed 3-22 s after the E4 session started, so the "−60 to 0 s" rest state is not available from the wrist.
* **Pulse quality (frozen after looking at raw BVP of p01/p02/p05/p09 only)**: the vendor `HR.csv` keeps emitting values when the PPG carries no pulse
  (p01: 100-165 bpm while seated; raw BVP is noise; p02: flat BVP with spikes). HR bins are valid only when Empatica's accepted inter-beat intervals cover
  ≥ 50 % of the bin. Accepted-beat coverage of the task: median 0.66 (min 0.007, max 0.98); HR-valid bin fraction is 0 for p01/p02 and < 0.15 for p03, p16, p36.
  **No HRV** (sparse IBI). Wrist PPG is never called ECG.
* Scale floors (frozen; the robust scale is never below hr 1 bpm, eda 0.02 µS, temp 0.05 °C, motion 0.02, abs_err 5): flagged references — hr 20, eda 27,
  temp 21, motion 2, abs_err 0 of 35. Most participants' EDA sits below 1 µS with a nearly flat baseline, so EDA z-scores are dominated by the floor.

### 0.2 Task performance (independent behavioural anchor), mean |target deviation| per block

| block | median | IQR | vs working baseline, mean [95 % participant-bootstrap CI], N = 35 |
|---|---|---|---|
| working baseline | 117 | 63-187 | — |
| challenge 1 | 333 | 225-609 | +314 [+214, +419] |
| recovery 1 | 263 | 178-511 | +272 [+155, +412] |
| challenge 2 | 392 | 233-730 | +455 [+290, +636] |
| recovery 2 | 255 | 186-779 | +386 [+222, +561] |

Adding COMMS roughly triples fuel error; the block mean during "recovery" stays far above baseline because the error decays over minutes (Figure M2 bottom:
cohort-median z falls from ≈ 8 at 60 s to ≈ 2 at 180 s and ≈ 1.5 at 360 s after demand drops). Cycle 2 minus cycle 1 challenge error: +163 [+64, +269].

### 0.3 Physiological response magnitude (challenge median − reference A median; physical units; N = participants with a valid reference)

| feature | cycle 1 mean [CI] (N) | cycle 2 mean [CI] (N) | cycle 2 vs pre-cycle-2 state (ref C, median) |
|---|---|---|---|
| HR (bpm, gated) | +1.70 [+0.41, +3.03] (31) | −0.29 [−1.74, +1.25] (29) | −0.55 |
| EDA (µS) | +0.21 [+0.04, +0.39] (35) | +0.18 [−0.08, +0.51] (35) | 0.00 |
| motion (1/64 g) | +0.02 [−0.04, +0.08] (35) | +0.01 [−0.04, +0.06] (35) | −0.06 |
| skin temp (°C) | −0.07 [−0.12, −0.02] (35) | −0.34 [−0.48, −0.19] (35) | −0.17 |
| abs target error | +283 [+170, +396] (35) | +446 [+267, +637] (35) | +309 |

Repeated challenge (cycle 2 − cycle 1, paired, matched 360-s durations): HR −2.34 bpm [−3.35, −1.29] (N = 29); EDA response −0.02 µS [−0.20, +0.17] but EDA burden
+925 [+355, +1751] |z|·s; skin temperature is a monotonic drift over the 31 minutes (cohort median −6.7 robust units by challenge 2), not a response, and is reported only
as a control. Cycle differences are **not** interpreted as trait resilience.

### 0.4 Response timing and recovery (band ±2 robust units of reference A, 3 consecutive valid 10-s bins; N = 35 per row)

| feature, cycle | departed | median t_depart (s) | returned | censored (no return in 360 s) | not estimable (no excursion) | median return (s, returned only) |
|---|---|---|---|---|---|---|
| HR, 1 | 15 | 80 | 14 | 1 | 20 | 85 |
| HR, 2 | 20 | 70 | 15 | 5 | 15 | 70 |
| EDA, 1 | 19 | 50 | 5 | 14 | 16 | 80 |
| EDA, 2 | 22 | 10 | 4 | 18 | 13 | 125 |
| motion, 1 | 18 | 45 | 12 | 6 | 17 | 55 |
| motion, 2 | 19 | 40 | 14 | 5 | 16 | 95 |
| abs error, 1 | 34 | 30 | 22 | 12 | 1 | 150 |
| abs error, 2 | 34 | 30 | 20 | 14 | 1 | 105 |

"Not estimable" for HR includes the participants whose HR never passed the pulse gate. Recovery residuals (median z at 60/180/360 s after demand drops): HR cycle 1
+0.72 / +0.23 / −0.95, cycle 2 −0.89 / −0.24 / −0.89; abs error cycle 1 +8.1 / +2.0 / +1.5, cycle 2 +9.1 / +3.7 / −1.9. Sensitivity: band ±1.5 raises HR departures to
20/22 and returns to 18/16; band ±2.5 lowers them to 13/18 and 12/15; with the whole baseline as reference (B) HR returns are 11/14 (full tables in `matb_summary.json`).
EDA rarely "returns" because its slow drift keeps it outside a band built on a near-flat baseline (floored scale) — a limitation of the wrist EDA here, not evidence of
non-recovery.

### 0.5 Burden versus performance (across participants, Spearman; 16 tests, no correction)
EDA burden during the challenge correlates *negatively* with challenge error: ρ = −0.40 (p = 0.017, cycle 1) and −0.37 (p = 0.029, cycle 2), i.e. participants with the larger
skin-conductance excursion made smaller fuel errors. HR burden: ρ = −0.08 / 0.00 (N = 28/27). Motion and temperature: |ρ| ≤ 0.28. Treat the EDA finding as nominal.

### 0.6 Functional AI test (held-out participants, N = 35, **run**)
Target = mean absolute target error over the next 30 s within the same block; 5,743 rows; nested participant-grouped ridge (10 outer × 5 inner folds), imputation and scaling fitted
inside training folds; personal reference from the pre-challenge baseline only (disclosed calibration).

| model | participant-weighted MAE (fuel units) | Δ vs context + past performance [95 % paired bootstrap CI] |
|---|---|---|
| persistence (last 30 s) | 66.2 | +8.7 [+4.4, +13.1] |
| condition/time only | 326.3 | +268.8 [+208.2, +345.1] |
| context + past performance | 57.5 | — |
| + peripheral physiology (HR, EDA, motion, temp, raw/z/30-s means, beat coverage) | 57.8 | +0.29 [+0.01, +0.60] |
| control: mismatched-participant physiology | 57.6 | +0.09 [+0.02, +0.16] |
| control: within-person 3-bin temporal shift | 57.6 | +0.11 [−0.29, +0.50] |

**Result: wrist physiology adds no predictive information about the next 30 s of task error beyond recent performance and context** (it is marginally worse, and the two
controls are indistinguishable from the real pairing). The multimodal (EEG) comparison is left to Checkpoint 2 on the matched five-participant cohort, which is below 20 participants
and will be labelled insufficient-N.

### 0.7 EEG, Checkpoint 2: five participants (p01-p05), one 600-MB combined file each

Files `EEGfNIRSeye_p1-p5/pXX/pXX.csv` (577-606 MB each; all five SHA256-verified). Orientation verified on every file: row 1 is time in steps of exactly
0.004 s (250 Hz; 482,341-504,214 samples; 1,929-2,017 s), all 74 rows have equal length, rows 34-65 are 32 EEG channels in the order of
`EEG_32_Channel_mapping.xyz` (AF3 ... OZ) in **microvolts** (retained channels: robust SD 7-25 µV), rows 66-73 are the eight eye rows (audited, not analysed),
row 74 carries the markers. The release is already low-passed/notched (55-65 Hz power ≈ 1e-4 of alpha power). Script: `scripts/matb_eeg.py`;
audit `results/audit/matb_eeg_audit.csv`; tables `results/tables/matb_eeg_{participant_metrics.csv,summary.json}`; Figure M6.

**Markers and cross-device chronology.** Every file has exactly five markers (value 1): working start followed by four transitions. The EEG stream starts
112-242 s before working start (no quiet-rest marker; the wrist tag has no counterpart marker, so the two clocks are joined only through the working-start
event on each device). Transition deviations from the 360-s grid: p01 −0.9..−3.3 s, p03 ≤ 0.6 s, p04 1.9-2.3 s, p05 ≤ 0.9 s; **p02's third and fourth
markers are 50 s early** (intervals 361.8, 358.2, 309.9, 360.1 s), so its cycle-2 timing estimates are excluded as ambiguous (magnitudes kept, flagged).
Actual markers define the EEG block boundaries; bins never cross them.

**Channel quality (whole-recording screen, frozen before outcomes).** Rejected channels: p01 15/32 (FZ FT7 FT8 FC3 FC4 FC6 C1 CZ C2 CP1 CP2 P8 PO7 PO8 OZ;
occipital group empty → NaN), p02 1 (C1), p03 5, p04 5, p05 2. Window screen on retained channels: 96.7 % of the 884 bins pass (p04 84 %, others 100 %).
Parietal-minus-frontal log10 alpha is positive in 3/5 (−0.02..+0.20), a weak plausibility check of the channel order.

**Response magnitude (challenge median − reference A, log10 µV²; five participants, individually):**

| feature | p01 | p02 | p03 | p04 | p05 | median c1 / c2 |
|---|---|---|---|---|---|---|
| frontal theta, c1 / c2 | +0.05 / +0.11 | +0.04 / +0.03 | −0.05 / −0.12 | −0.01 / +0.02 | +0.01 / −0.02 | +0.01 / +0.02 |
| parietal alpha, c1 / c2 | +0.05 / +0.02 | +0.07 / +0.06 | −0.05 / −0.13 | −0.04 / +0.03 | +0.10 / +0.12 | +0.05 / +0.03 |
| central beta, c1 / c2 | −0.03 / +0.11 | +0.10 / +0.01 | −0.15 / −0.24 | +0.12 / −0.01 | +0.05 / +0.01 | +0.05 / +0.01 |

Changes are small (|Δ| ≤ 0.25 log10) and mixed in sign; the expected pattern (theta up, alpha down under added load) is not consistent across these five.
Sustained departures at band ±2: frontal theta 1/5 (p04, at 240 s, returned by 30 s), parietal alpha 1/5 (p03, both cycles, returned at 120 s and 50 s),
central alpha 3/5; everything else not estimable (no excursion). Within-participant Spearman between concurrent parietal alpha and task error over all task bins:
+0.30, +0.08, −0.10, +0.22, +0.12. 874 EEG bins were matched to wrist/behaviour bins on the nominal task clock (`data/features/matb_multimodal_bins.parquet`).

**Matched-cohort added-value comparison with EEG: NOT RUN (insufficient-N, 5 < 20)**; Figure M5 carries the peripheral-only comparison at N = 35. Expanding EEG
beyond five participants was possible on disk (19 GB free) but not in the time budget; `scripts/download_matb.sh eeg pXX && scripts/matb_eeg.py pXX` adds one
participant at a time.

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

## 5. Foundation-model encoder — BIOT frozen-embedding audit RUN (EEGMAT only)
Released BIOT checkpoint `EEG-PREST-16-channels.ckpt` (github.com/ycq091044/BIOT, MIT; sha256 40f55f5d23e8…2ad70; 57/57 state-dict keys matched
strictly). Inputs follow the repo's own contract: 16 bipolar 10-20 montages derived from EEGMAT's monopolar channels (T3/T4/T5/T6 → T7/T8/P7/P8),
0.5–40 Hz + 50-Hz notch, resampled 500 → 200 Hz, 10-s windows (2000 samples), per-window 95th-percentile amplitude scaling as in the repo's TUAB
loader, mean-pooled 256-d embedding, encoder frozen. Same 853 windows and participant-grouped 12 folds as Section 1; logistic regression C = 0.1
(fixed). Script: `scripts/biot_frozen_eegmat.py`; output: `results/tables/biot_frozen_eegmat.json`. torch 2.14.0 (CPU execution).

| Representation | pooled AUC | mean within-participant AUC |
|---|---|---|
| handcrafted band power (12 features) | 0.714 | 0.857 |
| BIOT pretrained, frozen (256-d) | 0.646 | 0.711 |
| BIOT random weights, frozen (256-d) | 0.668 | 0.746 |
| handcrafted + BIOT pretrained | 0.678 | 0.760 |

Paired participant-level AUC difference, pretrained BIOT minus handcrafted: **−0.146** [−0.255, −0.046]; pretrained minus random weights:
−0.035 [−0.158, +0.087]. **On this task the frozen pretrained encoder is worse than 12 hand-designed features and no better than its own
random-weight control.** Likely reasons (untested): domain shift from clinical/resting montage data to ICA-cleaned 30-Hz-low-passed EEG, no
fine-tuning, and a linear probe on 36 people. This is an encoder audit, not evidence about foundation models in general; nothing here was
trained tonight, and ridge/PCA/handcrafted features remain non-foundation baselines.

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
