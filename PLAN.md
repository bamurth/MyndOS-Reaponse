# MyndOS response dynamics: tonight's execution plan

(Verbatim brief supplied by the project owner on 2026-09-09. Engineering
deviations forced by the execution environment are recorded in STATUS.md and
RESULTS.md, never here.)

## Decision

Build a reproducible demonstration of how concurrent physiology responds when
cognitive demand increases and recovers when demand decreases, with actual task
performance alongside it.

Primary: Roy–Nuamah MATB-II stress-resilience dataset
(https://physionet.org/content/neuro-stress-resilience-hci/1.0.0/). Start with
wrist physiology plus task performance for the available cohort. Add concurrent
EEG for five quality-qualified participants, then expand. Backup: EEGMAT
(https://physionet.org/content/eegmat/1.0.0/), which contains EEG and ECG during
baseline and arithmetic, but no recovery. Next cognitive benchmark: CMx7-MM /
OpenNeuro ds007554, with concurrent EEG, ECG, and cognitive/motor measurements.

Tonight's target: four figures, participant-level metrics, a model-comparison
table if the usable sample permits, and reproducible code. Budget approximately
six hours after cloud access works.

## Experiment to reconstruct (MATB-II)

| Time relative to working start | Condition        | Meaning                         |
|--------------------------------|------------------|---------------------------------|
| approx. −60 to 0 s, if present | Quiet rest       | Initial resting state           |
| 0–360 s                        | Working baseline | Easier resource-management task |
| 360–720 s                      | Challenge 1      | Increased multitask demand      |
| 720–1,080 s                    | Recovery 1       | Return to easier work           |
| 1,080–1,440 s                  | Challenge 2      | Repeated increased demand       |
| 1,440–1,800 s                  | Recovery 2       | Return to easier work           |

Expected boundaries, not permission to overwrite actual markers. Reconcile task
elapsed time, EEG events and wrist clocks per participant. Exclude ambiguous
transitions from timing estimates.

Reference: final three valid minutes of working baseline (whole block as
sensitivity). Preserve the original reference through cycle 2 and separately
show the immediately preceding state.

## Frozen first metrics

| Attribute                    | Estimator                                                          |
|------------------------------|--------------------------------------------------------------------|
| Task performance             | Mean absolute target deviation over a fixed interval               |
| Response magnitude           | Challenge median minus working-baseline median                     |
| Response timing              | First sustained departure from a baseline band                     |
| Response burden              | Integral of absolute baseline-standardized deviation               |
| Recovery                     | Residual at 60/180/360 s and sustained reference-band return       |
| Repeated-challenge change    | Cycle 2 minus cycle 1, matched durations                           |
| Added functional information | Held-out performance prediction with versus without physiology     |

Trailing 10-second bins, never spanning condition boundaries. Median/MAD
normalization (subtract reference median, divide by 1.4826 × MAD; flag
near-zero scale). Band ±2 robust units, sensitivity ±1.5/±2.5. Recovery = three
consecutive valid bins inside the band; missing bins break the sequence; no
excursion → not estimable; no return → right-censored.

## Functional AI test

Predict next non-overlapping 30-second mean absolute task error from information
available before that horizon; targets stay within a condition. Compare
persistence; task/time/cycle + past performance; that + peripheral physiology;
matched cohort + EEG. Ridge regression, nested participant-grouped tuning,
held-out participants, equal participant weighting, paired participant-bootstrap
MAE differences. Controls: condition/time-only; mismatched-physiology shuffles;
within-person temporal shifts. At least 20 usable participants before attempting;
otherwise label predictive evidence insufficient-N.

## Paste-ready execution brief

```text
Build and run a CPU-only MyndOS response-dynamics benchmark in this private repo tonight. Follow PLAN.md if supplied, and these instructions. Produce actual public-data results, not a mockup. No public deployment, contacting others, paid compute or permission changes. Respect licenses and access blockers; ask me for authorized access if required.

PRIMARY:
https://physionet.org/content/neuro-stress-resilience-hci/1.0.0/
Raw files base:
https://physionet.org/files/neuro-stress-resilience-hci/1.0.0/
Read README.txt, LICENSE.txt, SHA256SUMS.txt and actual directory listings. Expected sequence: working baseline, challenge 1, working recovery 1, challenge 2, working recovery 2; six minutes each. Quiet rest is approximately one minute if present. Actual markers govern. Recovery means easier work.

CHECKPOINT 1:
Start with small PPG and MATB-II files, p01 then sorted participant IDs. Read E4 info.txt. Regular files have epoch start, sample rate, then samples; IBI is irregular; tags are epoch event times. Match working-start tag and task time zero; inspect all timestamp gaps and anomalies. No clock offset inferred from signal correlations. Produce an alignment/exclusion audit and first real baseline/challenge/recovery plot within about one hour. Expand peripheral+behavior analysis to all usable participants.

CHECKPOINT 2:
Add EEG sequentially. p01 file:
EEGfNIRSeye_p1-p5/p01/p01.csv
It is about 606 MB with channels as rows. Stream numeric rows, not hundreds of thousands of pandas columns. Documented one-based rows: time 1; EEG 34–65; pupil/gaze 66–73; event markers 74. Verify orientation and official channel mapping. Match EEG markers to wrist working start and subsequent transitions; record uncertainty and exclude ambiguity. Start five subjects, expand only as time/disk permit. Do not call wrist PPG ECG. Independently recorded eye streams require separate proven alignment.

ANALYSIS:
Freeze parameters before outcome inspection. Use trailing non-boundary-crossing 10-second bins for HR, EDA, motion, target error and artifact-screened EEG log theta/alpha/beta power. Inspect units, flatlines, clipping, EEG ocular/muscle artifact and pulse quality. No HRV if valid beats are sparse.
Use final three valid minutes of working baseline as reference; sensitivity to the full block. Retain original reference through both cycles and separately show pre-cycle-2 state. Normalize with median and 1.4826*MAD, flagging near-zero MAD. Show physical units too.
Measure response magnitude, excursion area, recovery residual at 60/180/360 seconds, and baseline-band return sustained across three valid bins. Draft band +/-2 robust scale units; sensitivity +/-1.5 and +/-2.5; not a confidence interval. No excursion: not estimable. No return: right-censored. Never force recovery curves or interpret cycle differences as trait resilience.

FUNCTIONAL AI TEST:
If at least 20 participants qualify in a comparison cohort, predict next-30-second mean absolute task error using only information available before that horizon; targets stay within a condition. Compare persistence; task/time/cycle+past-performance; that baseline+peripheral physiology; matched-cohort models adding EEG. Ridge regression, nested participant-grouped tuning, completely held-out participants, equal participant weighting, paired participant-bootstrap MAE differences. Learned preprocessing only within training folds. Held-out pre-challenge personal calibration is allowed and disclosed. Never random-split windows or train on held-out future data. Include condition/time-only and mismatched-physiology controls. Below 20, prioritize descriptives and label predictive evidence insufficient-N. A positive multimodal result is not required.

BACKUP:
https://physionet.org/content/eegmat/1.0.0/
175 MB. Inspected EDF metadata contains EEG+ECG. Verify every EDF, actual lengths and ECG quality. Compare matched baseline/task windows, with participant-held-out evaluation if modeling. No recovery and no continuous trial-level behavior. Never concatenate into a fabricated continuous experiment. Use if primary EEG is blocked, preserving valid primary recovery results.

FOUNDATION MODEL:
Provide an encoder interface. Do not call ridge/PCA a foundation model or train a large one tonight. Only after core outputs, optionally audit a released BIOT checkpoint from https://github.com/ycq091044/BIOT for frozen features, respecting weights/data rights and preprocessing. Stop after 30 minutes if blocked; mark not run.

ENGINEERING:
Use Python scientific packages, MNE/pyedflib and scikit-learn as appropriate. Record versions and seeds. Test clock alignment, row indexing, boundary windows, no participant overlap/future leakage, censoring and zero-MAD. Synthetic fixtures are software tests only, never real evidence. Initial download cap 8 GB, one EEG participant at a time, at least 5 GB free disk. No deletion of pre-existing files; ask before quota expansion. Update STATUS.md at every checkpoint.

DELIVER:
Reproducible CLI, README, dependency lock, source/license/checksum manifest, alignment/QC audit, participant metrics CSV, model metrics JSON, RESULTS.md and four static figures: event-aligned response/recovery; participant recovery including non-returns; burden versus performance; matched-cohort added-value comparison or explicit not-run status. Optional offline HTML report, no deployment. Keep raw data/checkpoints out of Git. Preserve code and permitted compact aggregate outputs on the task branch; do not merge or publish. Summarize actual usable N, observed results, failed tests and permitted investor claims. No fabricated metrics, missing modalities or markers.
```

## Definition of done tonight

Real data and verified chronology; actual usable N; response/recovery metrics
with uncertainty; independent behavioral anchor; honest attempted/not-attempted
prediction; tests and reproducible code. Clearly distinguish primary recovery
evidence, EEGMAT before/during evidence, synthetic software checks and future
foundation-model work.
