# Frozen analysis plan: first-cycle dynamics -> second-challenge performance (written 2026-09-09 23:35 UTC, BEFORE any model in scripts/primary_prediction.py was run)

Retrospective note. The following were already computed and inspected before this plan was written and are therefore NOT
pre-registered: the wrist/behaviour descriptives and the bin-level next-30-s prediction test (RESULTS.md 0.1-0.6), the
five-participant EEG descriptives (0.7), and the exploratory burden-vs-behavioural-recovery table in matb_summary.json.
Nothing below has been run at the time of writing.

## Participant-level primary experiment
* Unit: participant (N = 35 in the release). Prediction cutoff: end of recovery 1 (task time 1,080 s). No feature may use bins after it.
* Primary target: mean absolute RESMAN target deviation over challenge 2 (task time 1,080-1,440 s; 36 snapshots), raw fuel units.
* Secondary targets: (i) challenge-2 error minus end-of-baseline error (baseline-adjusted); (ii) integrated excess error over recovery 2.
* Nested models (identical participants and folds within each comparison):
  A context only = training-fold mean (no participant features);
  B A + baseline: end-of-baseline error (last 3 min mean), whole-baseline error, baseline error slope, baseline HR/EDA/motion/temp medians;
  C B + first-cycle behaviour: challenge-1 mean error, challenge-1 minus baseline, recovery-1 mean error, recovery-1 integrated excess
    error, recovery-1 residual at 360 s (z), recovery-1 return time (censored -> 360 s + indicator);
  D C + first-cycle peripheral: HR and EDA response magnitude, challenge burden, recovery-1 burden and residual at 360 s; motion response;
  E C + first-cycle EEG: frontal theta, parietal alpha and central beta response magnitude (log10 power) and recovery-1 burden;
  F C + D + E.
* Estimator: ridge regression on median-imputed, standardized features (imputer and scaler fitted inside the training fold);
  alpha chosen by inner participant-grouped 5-fold CV over {0.1, 1, 10, 100, 1000}; outer leave-one-participant-out.
* Metrics: out-of-fold MAE (primary), Spearman rho(pred, obs) and OOF R^2 (secondary); absolute and relative MAE change vs model C;
  paired participant-bootstrap 95 % CI (5,000 resamples); participant-level permutation test of the C-vs-D/E/F MAE difference
  (1,000 target shuffles across participants); jackknife influence (largest change in the MAE difference when one participant is dropped).
* Engineering target (frozen): >= 10 % relative reduction in held-out MAE versus model C with a bootstrap CI excluding zero. A point
  estimate alone does not establish success. This is not a clinical threshold.
* Missingness: HR is unavailable for participants whose pulse fails the coverage gate. Each comparison is run on participants with
  complete features for both models being compared (matched subset), and separately on all 35 with imputation plus a missing indicator,
  with an indicator-only control to show whether missingness itself carries information.
* Recovery endpoint chosen as primary for descriptive/secondary use: integrated excess error over the 360-s recovery window (raw units x s,
  positive part relative to the end-of-baseline median). Reason: defined for everyone, no censoring, no model fit. Time to sustained
  return (band +-2, k = 3) is secondary with right-censoring; residual at 360 s and recovery slope tertiary; an exponential time constant
  is reported only when the fit meets R^2 >= 0.5, tau < 720 s and a positive decay amplitude.
* Sensitivity grid (recovery endpoints): reference A (last 3 min) vs B (whole baseline); band 1.5/2/2.5; sustained k = 2/3/4;
  bin width 10 vs 30 s; HR pulse-coverage gate 0.3/0.5/0.7.
* Negative controls: sham segmentation (+180-s shifted "challenge" window for physiology features), participant-level target permutation,
  jackknife influence, missing-indicator-only model, strict (coverage 0.7, band 2.5) vs permissive (0.3, 1.5) QC.
* Ablation: models B, C, D, E, F on the matched complete-data participants with identical LOO folds.
* Assessment shortening: cutoffs at end of baseline (360 s), end of challenge 1 (720 s), recovery 1 + 60 s, + 180 s, end of recovery 1;
  at each cutoff, behaviour-only vs behaviour + peripheral (+ EEG when available) with features restricted to bins before the cutoff.
