# Next experiments, ranked (information gained x feasibility x cost x product relevance)

Ranking written 2026-09-10 before the final primary numbers were in; the ordering does not depend on the sign of the primary result
except where noted.

| Rank | Experiment | Information gained | Feasibility / cost | Product relevance |
|---|---|---|---|---|
| 1 | **Across-day test-retest of the behaviour-first endpoints** (challenge response, integrated excess error, time to return) in ~30 people, two sessions a week apart, same MATB-II protocol, chest ECG + wrist | Whether any "dynamics" endpoint is a stable individual characteristic (ICC) and the minimal detectable change; without it no within-person claim is possible | New collection, ~2 weeks of lab time, low equipment cost | Gates Gen 2 entirely |
| 2 | **Counterbalanced-order and longer-recovery protocol** (recovery 10-12 min, order of cycles randomised, an "easier-than-baseline" arm) | Separates biological recovery from protocol-driven change and fatigue/practice; resolves the censoring that hides slow recoverers (1/3 censored at 6 min here) | New collection, same rig | Determines whether "recovery" is a claimable endpoint |
| 3 | **drivedb ECG replication of the recovery methodology** (planned above; frozen endpoint) | Whether HR/EDA recovery with censoring behaves the same with research-grade ECG in a different task; consistency of reactivity across two city segments | Zero cost, ~1 day, data on the mirror | Supports the sensor-choice decision (ECG vs wrist) |
| 4 | **CLARE inspection and, if suitable, exact-task replication** of the first-cycle -> second-challenge test | Exact replication on the same task family with ECG/EDA/EEG | Needs network access to its host; ~2 days if accessible | Highest scientific value if the primary result is positive; if negative, confirms the null |
| 5 | **Within-person dose-response with graded demand and personal calibration** (3-4 COMMS rates, each followed by recovery) | Whether physiology tracks demand within a person even when it does not predict performance across people; defines a personal calibration procedure | New collection | Enables a within-person product mode (Gen 1/2) that does not rely on cross-person prediction |

Not ranked (deferred until the above): foundation-model encoders (the BIOT audit was negative on EEGMAT), phone-camera PPG (no validation
data here), adaptive stopping (only a future method; the shortening curve in `results/tables/primary_shortening.csv` is the observational
input for it).
