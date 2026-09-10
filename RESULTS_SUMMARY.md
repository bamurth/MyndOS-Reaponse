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

## 4. PRIMARY EXPERIMENT (participant level; frozen plan) — see section 4 below, filled from `results/tables/primary_model_comparison.json`
PRIMARY_PLACEHOLDER

## 5. Secondary hypotheses
SECONDARY_PLACEHOLDER

## 6. Negative controls, robustness, ablation, shortening
CONTROLS_PLACEHOLDER

## 7. External transfer test (drivedb, ECG; frozen endpoint)
9 eligible records (8 distinct drives: drive13 and drive14 are byte-identical duplicates) with a final-rest marker. ECG-derived HR: last 15 min of
driving is +6.5 bpm (IQR +6.2 to +12.2) above the initial rest; all 9 departed and all 9 returned to the +-2 band, median 50 s; residual at 360 s
median -0.25 z. Hand skin conductance: 7 departed, 4 returned (median 345 s), 3 censored. Read as: with research-grade ECG and a stronger stressor,
the same recovery estimators give estimable, mostly uncensored HR recovery; with wrist PPG on the seated MATB task they mostly do not. No behaviour,
so this says nothing about the primary hypothesis (`results/tables/drivedb_recovery.{csv,json}`, Figure X1).

## 8. Most important next experiment
Across-day test-retest of the behaviour-first endpoints with chest ECG (NEXT_EXPERIMENTS.md #1). Without reliability, no within-person claim can be made,
and the present data show that the informative signal is behavioural carryover, which is exactly what a second session would test for stability.
