# Data and code provenance manifest

All raw data live under `data/raw/` (gitignored). Nothing below was modified before analysis.

| Dataset | Source used | Version | License | Size | Integrity |
|---|---|---|---|---|---|
| EEGMAT (Zyma et al., "EEG during mental arithmetic tasks") | `https://physionet-open.s3.amazonaws.com/eegmat/eegmat-1.0.0.zip` (official PhysioNet AWS Open Data mirror) | 1.0.0 | Open Data Commons Attribution License v1.0 (PhysioNet) | 183,634,285 B zip; 72 EDF | zip sha256 in `results/audit/eegmat_zip_sha256.txt`; all 75 entries of the official `SHA256SUMS.txt` verified OK (`results/audit/eegmat_SHA256SUMS_official.txt`) |
| CMx7-MM (Ajra et al.), OpenNeuro ds007554 | `https://s3.amazonaws.com/openneuro.org/ds007554/` (official OpenNeuro S3 bucket) | 1.0.0 (2026-03-23) | CC0 (dataset_description.json) | 3.3 GB downloaded (EEG EDF, ECG, push-button, events, phenotype; fNIRS/EMG/biodex skipped) | sizes matched to the S3 listing on download; sha256 of every downloaded file in `results/audit/ds007554_downloaded_sha256.txt` |
| PRIMARY: Roy & Nuamah, neuro-stress-resilience-hci | `https://physionet.org/files/neuro-stress-resilience-hci/1.0.0/` | 1.0.0 | ODbL (per plan) | not downloaded | **BLOCKED** by the environment network policy (proxy 403); not mirrored on AWS Open Data. No file was obtained. |
| BIOT pretrained EEG encoder (Yang et al. 2023) | `https://raw.githubusercontent.com/ycq091044/BIOT/main/pretrained-models/EEG-PREST-16-channels.ckpt` | repo main | MIT (code and released checkpoints in the repo) | 13,791,969 B | sha256 recorded in RESULTS.md; **not executed** in the analyses |

Software: Python 3.11.15; exact package versions in `requirements.lock.txt`. Seeds: 0 everywhere (`SEED = 0` in scripts).

Analysis provenance: every table in `results/tables/` and figure in `results/figures/` is produced by
`scripts/run_all.sh` from the raw files above; intermediate per-bin features (`data/features/*.parquet`)
are regenerated, not tracked.
