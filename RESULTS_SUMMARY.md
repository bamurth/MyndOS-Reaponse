# RESULTS_SUMMARY — first-cycle dynamics -> second-challenge performance (2026-09-10)

Dataset: PhysioNet `neuro-stress-resilience-hci` 1.0.0 (Roy & Nuamah), ODbL, 35 participants (p14/p23 absent from the release),
all 325 used files SHA256-verified. Protocol: quiet rest, working baseline (RESMAN), Stress 1 (+COMMS), Recovery 1, Stress 2, Recovery 2,
six minutes each, fixed order. Everything below is produced by `scripts/run_all.sh` from the raw files; frozen plan in
`configs/primary_experiment_frozen.md` (written before the participant-level models were run; earlier bin-level and descriptive analyses
in RESULTS.md were done before that plan and are retrospective).

## 1. Audit of the earlier claims (traced to files)

| Claim as previously stated | Verified value | Source |
|---|---|---|
| 35 participants | 35 audited, 35 usable for wrist+behaviour, 35 with EEG features | `results/audit/matb_alignment_audit.csv`, `matb_eeg_audit.csv` |
| Baseline, two challenges, two recoveries | MATB logs span 1,790-1,800 s from working start; five 360-s blocks; EEG markers at the four transitions in all 35 (p16 stopped at 24 min: challenge 2 truncated, recovery 2 absent in EEG; wrist/behaviour complete) | same |
| Four unusable wrist-pulse recordings | 4 participants with < 10 % pulse-valid bins (p01, p02, p03, p16); p36 at 10.6 %; HR reference available for 28 | `matb_summary.json` hr_bins_valid_fraction_by_participant |
| Fifteen failed EEG channels in one participant | p01: 15/32 rejected; all others reject 0-5 | `matb_eeg_audit.csv` channels_rejected |
| One mistimed event marker | **Corrected: four participants** have an EEG transition marker > 10 s off the 360-s grid (p02 50 s x2, p18 10 s, p20 16 s, p28 14 s); p02 also has a wrist double-press 2.8 s apart. No marker was altered; affected cycles are flagged ambiguous for timing estimates | `matb_eeg_audit.csv` transition_deviation_s |
| ~3x increase in control error | Ratio of medians 2.9 (cycle 1) / 3.4 (cycle 2); ratio of means 3.2 / 4.2; **median per-person ratio 5.1 / 5.9** | `matb_performance_by_block.csv` |
| ~2-3 min behavioural recovery | Among the 22/35 who return to the end-of-baseline band within 6 min, median 150 s (IQR 55-238); **12 right-censored, 1 not estimable**; cycle 2: 20 returned (median 105 s), 14 censored | `recovery_endpoints.csv` |

## 2. Is "recovery" a valid endpoint here?
* Same task in baseline and recovery (RESMAN), same scoring (deviation from 2,500), same 10-s snapshots; recovery = COMMS removed. Whether
  the scripted pump-failure schedule is identical across blocks cannot be verified from the release.
* The baseline itself is not stationary: error rises within the working-baseline block (23/35 positive slopes, median +5.4 units/min;
  block-minute medians 50 -> 146), so only the **end** of baseline is a fair reference (used throughout).
* End-of-recovery error stays above end-of-baseline error (recovery 1: median +46 units, Wilcoxon p = 0.002; recovery 2: +53, p = 0.0002).
  "Recovery" therefore means decay of the excess error over minutes, not return to the pre-challenge state for most people.
* Challenge 2 is harder than challenge 1 (+141 units mean, Wilcoxon p = 0.014; rank correlation 0.77). With a fixed order, fatigue, practice,
  carryover and any block-script differences cannot be separated.
* No smoothing, overlap or filter lag affects behaviour (raw snapshots). Wrist HR is a vendor ~10-s running estimate (lag not corrected).
  EEG filtering is zero-phase.
* Endpoints computed and compared (`recovery_validity.json`, Figures R1-R2): response magnitude; integrated excess error (primary; defined
  for all 35, no censoring); time to sustained return (22 returned / 12 censored); residual at 360 s (median +1.5 z, cycle 1); recovery slope
  (median -2.3 z/min over the first 3 min); exponential time constant accepted for 19/35 (median tau 114 s) and rejected otherwise.
* Sensitivity: reference B (whole baseline) 22/9 returned/censored vs 22/12; band 1.5: 22/13; band 2.5: 25/9; k = 2: 24/10; k = 4: 22/12;
  30-s bins: 10/24 (a 90-s sustained rule); HR gate 0.3/0.7 changes HR returns 15/12 vs 14. Participant ranking on the primary endpoint is
  stable across definitions (Spearman 0.94-0.998).

## 3. EEG processing outcome (N = 35)
Median 30/32 channels retained; 96.9 % of 6,152 bins pass the artifact screen; layouts and marker anomalies documented in METHODS_AND_QC.md.
Cohort-median band-power changes are tiny (|delta| <= 0.06 log10); the theta-up/alpha-down pattern is absent at the cohort level; beta shows the
most excursions (consistent with muscle activity during COMMS responding). Artifacts vs condition: usable-bin fraction differs by < 3 points across
blocks (`eeg_ok_fraction_by_block`). Bin-level test: EEG adds nothing to next-30-s error prediction (+1.29 MAE [+0.59, +2.0], RESULTS.md 0.7).

## 4. PRIMARY EXPERIMENT (participant level; frozen plan; `results/tables/primary_model_comparison.json`)
**Question.** Does first-cycle physiology predict second-challenge performance beyond task context, baseline and first-cycle behaviour?
**Answer: no.** Behaviour carries essentially all the predictable variance; every physiology block makes held-out prediction worse.

Design (frozen before running): unit = participant; cutoff = end of recovery 1; target = mean absolute RESMAN target error in challenge 2
(mean 597, SD 527, median 392 fuel units); nested ridge with in-fold imputation/scaling and inner-CV alpha; leave-one-participant-out;
paired participant bootstrap; 500 participant-level target permutations; jackknife influence. Feature availability: all behavioural, EDA,
motion, temperature and EEG features for 35/35; HR features for 28/35 (missing for p01, p02, p03, p07, p16, p27, p36 whose pulse gate leaves
too few valid bins). Frozen success criterion: >= 10 % lower MAE than model C with a bootstrap CI excluding zero.

Matched complete-data cohort (n = 28; identical folds for every model):

| model | features | held-out MAE | Spearman(pred, obs) | OOF R^2 | vs C: dMAE [95 % CI] | relative | permutation p (improvement) | jackknife range of dMAE |
|---|---|---|---|---|---|---|---|---|
| A context only (fold mean) | 0 | 396.8 | — | -0.08 | +227 [+92, +373] | +133 % | — | — |
| B + baseline (behaviour + wrist levels) | 7 | 426.6 | 0.07 | -0.27 | +256 [+110, +415] | +151 % | — | — |
| **C + first-cycle behaviour** | 14 | **170.2** | **0.67** | **0.79** | reference | — | — | — |
| D C + first-cycle peripheral physiology | 23 | 205.0 | 0.59 | 0.74 | +35 [-14, +86] | +20.5 % | 0.93 | [+11, +75] |
| E C + first-cycle EEG | 20 | 220.2 | 0.59 | 0.69 | +50 [+5, +99] | +29.4 % | 0.98 | [-5, +74] |
| F C + peripheral + EEG | 29 | 261.8 | 0.42 | 0.34 | +92 [+17, +181] | +53.9 % | 0.99 | [+17, +123] |

All 35 participants with in-fold imputation (HR missing indicator included): C 164.1; D 168.8 (+2.9 % [-23, +32]); E 177.9 (+8.4 % [-15, +41]);
F 183.0 (+11.5 % [-19, +56]). The ladder A -> B -> C on all 35: 405 -> 350 -> 164 (C vs B: -53 % [-286, -90]). Frozen target: **not met by any
physiology model; the point estimates go the wrong way in every variant.** Out-of-fold predictions: `results/tables/primary_oof_predictions.csv`;
Figure P1 (predicted vs observed), Figure P2 (nested comparison).

Secondary targets (n = 28): baseline-adjusted challenge-2 error, D +22.9 % [-13, +98], F +50.8 % [+6, +185]; integrated excess error in
recovery 2, D +13.6 %, F +20.8 % [CI excludes zero]. Same conclusion.

What behaviour predicts with: the largest contributions are the challenge-1 error level and the recovery-1 excess (carryover; section 5C).
The most influential participant for each comparison is reported in the JSON (p06, p15, p12); removing any single participant never turns a
physiology model into an improvement (jackknife ranges above).


## 5. Secondary hypotheses
**A. Physiological change at equivalent performance.** Partial Spearman of first-cycle physiological response with challenge-2 error, adjusting
for end-of-baseline and challenge-1 error: HR response +0.03 (n = 28, p = 0.86); EDA response -0.06 (p = 0.73); HR challenge burden -0.19 (p = 0.33);
EDA burden +0.06; frontal theta response -0.11 (n = 35, p = 0.55); parietal alpha +0.10 (p = 0.58). Against recovery-2 excess: HR +0.26 (p = 0.18),
EDA +0.09. Within challenge-1 error tertiles the HR/EDA correlations are inconsistent in sign. **No physiological-cost relationship is detectable.**

**B. Cross-system recovery timing** (cycle 1; `cross_modality_timing.csv`, Figure R3). Behaviour: 22 returned (median 150 s), 12 censored.
HR: 14 returned (85 s), 1 censored, 20 not estimable (no excursion or no valid pulse). EDA: 5 returned (80 s), 14 censored, 16 not estimable.
EEG frontal theta: 5 returned (30 s), 27 not estimable; parietal alpha: 7 returned (50 s), 26 not estimable. Only 9 participants have both a
behavioural and an HR return time (Spearman 0.55); EDA/EEG pairs are too few to correlate. Adding the HR/EDA return times and censoring flags
to model C changes MAE by -0.5 % [-39, +37]: **timing differences do not improve prediction.** Sensor lags (wrist HR ~10 s, EDA seconds) exceed
several of the apparent differences, so no ordering claim is made.

**C. Carryover.** Adjusting for challenge-1 error, recovery-1 integrated excess error predicts challenge-2 error with partial rho 0.66 (p = 1.5e-5)
and the residual at the end of recovery 1 with rho 0.43 (p = 0.010): **behavioural carryover is the strongest relationship in the dataset.**
Physiological residuals at the end of recovery 1 do not carry over: HR -0.09 (p = 0.66), EDA 0.00, frontal theta burden +0.15 (p = 0.38),
parietal alpha -0.08. An exploratory model adding HR/EDA end-of-recovery residuals and recovery burdens to C gives MAE 153.6 vs 170.2 (-9.7 %),
but its CI [-61, +25] includes zero and its jackknife range crosses zero: **not supported.** Fixed order means carryover, fatigue, practice and
block scripts are confounded; two cycles give no test-retest reliability, and no phenotypes are proposed.


## 6. Negative controls, robustness, ablation, shortening
**Negative controls (D vs C unless stated).** Sham segmentation (+180-s shifted physiology windows): +14.2 % [-10, +51] (n = 27) — the same
degradation as the real windows, so the real physiology features are not distinguishable from misaligned ones. Participant-level target permutation:
p = 0.93 (D), 0.98 (E), 0.99 (F) for improvement. Strict QC (pulse gate 0.7, n = 27): +23.5 % [+9, +76]; permissive QC (gate 0.3, n = 30): +7.4 %
[-27, +53]. Missingness: imputing HR for all 35 with an indicator, D +11.2 % [-11, +46]; the indicator alone +1.6 % [-4, +10] — missingness is
not driving anything. Temporal autocorrelation: the unit is the participant (one row each), so no window-level dependence enters the folds.
Task-phase or identity shortcuts cannot operate at the participant level (a single target per person).

**Ablation on the matched n = 28 (identical LOO folds):** A 397, B 427, C 170, C + peripheral 205 [+(-14, +86)], C + EEG 220 [+5, +99],
C + both 262 [+17, +181]; Spearman 0.67 (C) vs 0.59 / 0.59 / 0.42. **Minimum useful sensor set for predicting second-challenge performance:
the task log alone.** Neither wrist physiology nor EEG survives; the combination is worst (more features, no signal). Any modality claim would
require a different protocol, not more modelling.

**Assessment shortening (`primary_shortening.csv`, Figure P3).** Behaviour-only MAE by observation cutoff: end of baseline 427 (rho 0.10);
end of challenge 1 (12 min of protocol) 262 (rho 0.7); 1 min into recovery 158; 3 min into recovery 147; end of recovery 1 170. The predictive
information is in the challenge block and the first 1-3 minutes of recovery; adding peripheral (+EEG) features hurts at every cutoff
(e.g. at 900 s: 218 [+19, +129] and 259 [+40, +194]). A 2-minute assessment is not supported; a ~9-10-minute protocol (baseline end,
6-min challenge, 1-3 min recovery) preserves the behavioural signal. Adaptive stopping is a future method, not implemented.


## 7. External transfer test (drivedb, ECG; frozen endpoint)
9 eligible records (8 distinct drives: drive13 and drive14 are byte-identical duplicates) with a final-rest marker. ECG-derived HR: last 15 min of
driving is +6.5 bpm (IQR +6.2 to +12.2) above the initial rest; all 9 departed and all 9 returned to the +-2 band, median 50 s; residual at 360 s
median -0.25 z. Hand skin conductance: 7 departed, 4 returned (median 345 s), 3 censored. Read as: with research-grade ECG and a stronger stressor,
the same recovery estimators give estimable, mostly uncensored HR recovery; with wrist PPG on the seated MATB task they mostly do not. No behaviour,
so this says nothing about the primary hypothesis (`results/tables/drivedb_recovery.{csv,json}`, Figure X1).

## 8. What is established, provisional, failed

* **Established:** verified chronology and QC on 35 participants; behaviour responds strongly to added demand and decays over minutes;
  first-cycle behaviour predicts second-challenge error well out of sample (MAE 164-170, Spearman 0.67-0.72); behavioural carryover
  (recovery-1 excess -> challenge-2 error) is robust; wrist physiology and EEG add nothing to that prediction under every control tried.
* **Provisional:** a small wrist HR rise in challenge 1 (+1.7 bpm); EDA burden vs error correlations (nominal, uncorrected); cross-system timing
  medians (few estimable pairs); the drivedb ECG transfer result (8 distinct drives).
* **Failed / inconclusive:** the primary hypothesis (physiology adds predictive value) failed; EEG demand response at the cohort level absent;
  HRV not attempted (wrist PPG); recovery as return-to-baseline is right-censored for a third of participants.

## 9. Most important next experiment
Across-day test-retest of the behaviour-first endpoints with chest ECG (NEXT_EXPERIMENTS.md #1). Without reliability, no within-person claim can be made,
and the present data show that the informative signal is behavioural carryover, which is exactly what a second session would test for stability.
