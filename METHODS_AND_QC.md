# METHODS_AND_QC — PRIMARY dataset analyses (neuro-stress-resilience-hci 1.0.0)

Written 2026-09-10 during the analysis; everything here describes what the code in `scripts/` and `src/myndos/` actually does.
Result-dependent statements live in RESULTS_SUMMARY.md and CLAIMS_LEDGER.md.

## 1. Provenance and integrity
* Dataset: "Neurophysiological Dataset of Stress Resilience During Human-Computer Interaction", Roy & Nuamah (Oklahoma State
  University), PhysioNet `neuro-stress-resilience-hci` version 1.0.0, https://physionet.org/files/neuro-stress-resilience-hci/1.0.0/.
  License: ODC Open Database License (ODbL) v1.0 (LICENSE.txt in the release). Not mirrored on AWS Open Data (checked).
* Files used: README.txt, LICENSE.txt, SHA256SUMS.txt (383 entries), demographicCDrisk.csv, EEG_32_Channel_mapping.xyz,
  MATB-II/pXXresman.csv (35), PPG/pXX/{ACC,BVP,EDA,HR,IBI,TEMP,tags}.csv + info.txt (35 x 8), EEGfNIRSeye_*/pXX/pXX.csv (35, 577-606 MB
  each) and the 15 participant Note(s).txt files. Every file was verified against the official SHA256SUMS.txt before use
  (`scripts/verify_matb.sh`; `results/audit/matb_SHA256SUMS_verified.txt`; per-EEG-file check inside `scripts/matb_eeg.py`, field `sha256_ok`).
* Transport: physionet.org presented an expired Let's Encrypt certificate on 2026-09-09 (notAfter 20:22:45 UTC; container clock checked
  against external HTTP Date headers). The project owner authorised a certificate-check bypass for these public files only
  (`MATB_CURL_INSECURE=1` in `scripts/download_matb.sh`; no credentials were ever sent). Integrity therefore rests on the SHA256 manifest.
* Raw files are never modified. EEG raw files were deleted after feature extraction to respect the disk floor; they are restored by
  re-running the downloader (features, audits and checksums are kept).
* Participants: 35 in the release (IDs p01-p37; p14 and p23 do not exist in any folder or manifest entry).

## 2. Protocol and modalities
* Sequence (README): resting baseline (~1 min), working baseline (RESMAN only, 6 min), Stress 1 (RESMAN + COMMS, 6 min), Recovery 1
  (RESMAN, 6 min), Stress 2 (RESMAN + COMMS), Recovery 2 (RESMAN). Fixed order, no counterbalancing. "Recovery" = removal of the COMMS
  task; the RESMAN task (keep tanks A and B at 2,500 units) continues throughout.
* Concurrent modalities: Empatica E4 wrist (BVP 64 Hz, EDA 4 Hz, TEMP 4 Hz, ACC 32 Hz, vendor HR 1 Hz, vendor IBI irregular);
  MATB-II RESMAN log (10-s snapshots); 32-channel EEG at 250 Hz with fNIRS (32 rows) and, for p01-p24, eye tracking in the same file.
  p25-p37: eye tracking recorded separately (66-row files). Wrist PPG is never called ECG; no ECG exists in this dataset.
* Clocks and synchronisation: three independent clocks (E4 unix time; MATB elapsed time; EEG file time from 0). Joined through the
  working-start event on each device only: E4 button tag (README: "Working Baseline start"), MATB ELAPSED_TIME zero, and the EEG marker
  row. No clock offset is inferred from signal correlations anywhere. Evidence that the E4 tag is the MATB zero: every MATB log spans
  1,790-1,800 s from its zero; every E4 session covers >= 1,825 s after the tag; the tag falls 3-239 s after the E4 session start
  (quiet rest on the wrist exists for only 4 participants).
* Event markers (EEG): every file has exactly 5 binary markers = working start + four transitions (p15 has 6 with a documented spurious
  one; p25/p26 notes say "last 5 are the main markers"). Anchor rule (frozen, `scripts/matb_eeg.py::find_working_start`): the earliest
  marker with a marker near its +360-s transition and at least two of four transitions within 15 s of the 360-s grid. The four
  transition deviations are recorded per participant (`results/audit/matb_eeg_audit.csv`, `transition_deviation_s`); boundaries deviating
  by more than 10 s are labelled ambiguous and the adjacent cycle's timing estimates are dropped (magnitudes kept, flagged).
  Actual markers, not the nominal grid, define the EEG block boundaries. No marker was moved or "corrected".
* Marker anomalies found (original values, all retained as recorded): p02 third and fourth EEG markers 50.2 s and 50.1 s early
  (intervals 361.8/358.2/309.9/360.1 s); p18 last two markers ~10 s early; p20 first transition 16.1 s late (which also exposed and fixed an
  anchor-rule brittleness: the earlier rule anchored on the third marker; the corrected rule is tested in `tests/test_matb.py`); p28 second
  transition 13.9 s late. E4: p02 has a double tag press 2.83 s apart (first press used; timing uncertainty recorded; below the 5-s limit).

## 3. Behaviour (MATB-II RESMAN)
* Parser `myndos.io_matb.read_matb_resman`: ELAPSED_TIME mm:ss.s, TANK_A-D, DIFF_A/B. Verified on all 35 files: DIFF == TANK - 2500,
  179-180 rows at a 10-s cadence with no anomalies (tolerance 0.5 s).
* Performance measure: abs_err = mean(|DIFF_A|, |DIFF_B|) per snapshot (fuel units from the 2,500 target). Block means are means of
  snapshots. No smoothing, no overlapping windows.
* Known limitation: whether the scripted RESMAN pump-failure schedule is identical across blocks cannot be verified from the release;
  the rising error within the working-baseline block (median +5.4 units/min) suggests it is not stationary.

## 4. Wrist physiology (E4)
* Bins: trailing 10-s bins that never cross a block boundary (`myndos.binning.make_bins`); per bin HR mean (>= 8 samples), EDA median
  (>= 32 samples; a flat 10-s EDA bin is set to NaN), TEMP mean, motion = mean |diff| of the ACC magnitude (1/64 g).
* Pulse quality gate (frozen after inspecting raw BVP of p01/p02/p05/p09, before outcomes): the vendor HR keeps emitting values with no
  pulse in the PPG; a bin's HR is valid only when Empatica's accepted inter-beat intervals cover >= 50 % of the bin. Sensitivity 0.3/0.7.
  Participants with < 10 % valid HR bins: p01, p02, p03, p16 (p36 at 10.6 %). No HRV is computed from wrist IBI (sparse, vendor-selected
  beats; not ECG-derived).
* Reference and standardisation: reference A = final 3 min of the working baseline (sensitivity B = whole block); median and 1.4826*MAD
  with resolution-based scale floors (hr 1 bpm, eda 0.02 uS, temp 0.05 degC, motion 0.02, abs_err 5); floored references are flagged.
  Skin temperature drifts monotonically over 31 min and is treated as a control, not a response.

## 5. EEG
* Streaming: only the needed rows of each ~600 MB channels-as-rows CSV are parsed (`myndos.io_matb.stream_combined_csv_rows`);
  orientation verified per file (row 1 = time at exactly 0.004 s; all rows equal length; 74-row or 66-row layout detected).
* Channel order: rows 34-65 mapped to AF3..OZ in the order of `EEG_32_Channel_mapping.xyz` (the only mapping in the release).
  Plausibility check per participant: parietal-minus-frontal log alpha (positive in most participants; reported, not enforced).
* Reference: as released (unknown hardware reference; no re-referencing applied, to avoid propagating bad channels). Units: microvolts
  (retained channels robust SD 7-30 uV). The release already has no 55-65 Hz power (pre-filtered by the authors).
* Filtering: zero-phase (filtfilt) 0.5-40 Hz Butterworth + 60-Hz notch (US mains). Zero-phase => no timing shift.
* Channel screen (whole recording, frozen after the p01 QC table): retain iff robust SD in 1-40 uV and 99th-percentile |amplitude|
  <= 300 uV. Window screen per 10-s bin on retained channels: reject a channel if peak > 150 uV or SD < 0.5 uV; reject the bin if
  > 25 % of retained channels are rejected. Usable-data duration per participant and block = `eeg_ok_fraction_by_block` in the audit.
* Features (deliberately small; supported by a 32-channel 10-20 montage and a sustained-attention protocol): log10 Welch power (2-s
  segments inside the 10-s bin) for theta 4-8, alpha 8-13, beta 13-30 Hz averaged over frontal (AF/F/FC/FT), central (C/CP/T), parietal
  (P/PO) and occipital (O) retained channels. Frontal theta and parietal alpha are the two features carried into prediction
  (with central beta as a muscle-sensitive control). No ICA (the release appears already cleaned; an ICA stage would add unverifiable
  timing/selection decisions on a 4-CPU budget).
* No band-power change is interpreted as a unique measure of effort, arousal, reserve or disease.

## 6. Frozen response/recovery estimators (PLAN.md; `myndos.metrics`)
Response magnitude = challenge median - reference median (physical units) and its robust-unit version; timing = first run of 3
consecutive valid bins with |z| > band (2, sensitivity 1.5/2.5); burden = integral of |z|; recovery = residual z at 60/180/360 s
(last valid bin within 30 s) and time to 3 consecutive valid in-band bins; censored if no return within the 360-s block; not estimable if
no excursion. Primary recovery endpoint for participant-level work (configs/primary_experiment_frozen.md): integrated excess error over
the recovery window (positive part relative to the end-of-baseline median); exponential time constants only when R^2 >= 0.5, tau < 720 s
and a positive decay amplitude.

## 7. Leakage prevention
* Bin-level test (RESULTS.md 0.6): targets are strictly future (next three snapshots within the same block); features use only bins
  ending at or before the current bin; imputation/scaling/alpha fitted inside participant-grouped training folds; participants never split.
* Participant-level test (this document, section 8): cutoff = end of recovery 1; every feature is computed from bins ending at or before
  1,080 s (or the shortening cutoff); the target is challenge 2. Personal standardisation uses the pre-challenge baseline only.
  EEG filtering is zero-phase over the whole recording (a non-causal operation), so an on-line deployment would need a causal filter;
  band power in a 10-s bin depends only on that bin's samples, and the 0.5-Hz high-pass has a transient of a few seconds, so no
  information from after the cutoff enters the features at the bin level.
* Nested tuning: ridge alpha by inner 5-fold participant-grouped CV; outer leave-one-participant-out. Windows are never randomly split.

## 8. Statistics and their limits
Paired participant-bootstrap CIs (5,000 resamples, equal participant weight); one-sided participant-level permutation tests of the MAE
difference; jackknife influence; Spearman correlations; Wilcoxon signed-rank for paired block contrasts. Multiplicity: exploratory
tables list the number of tests and apply no correction; the primary comparison is one pre-specified contrast (D/E/F vs C).
Limits: N = 35, single session, fixed block order (fatigue, practice, carryover and block scripts are confounded), wrist PPG rather than
ECG, unknown EEG reference, no counterbalanced control condition, no test-retest.
