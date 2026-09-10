# Data and code provenance manifest

All raw data live under `data/raw/` (gitignored). Nothing below was modified before analysis.

| Dataset | Source used | Version | License | Size | Integrity |
|---|---|---|---|---|---|
| EEGMAT (Zyma et al., "EEG during mental arithmetic tasks") | `https://physionet-open.s3.amazonaws.com/eegmat/eegmat-1.0.0.zip` (official PhysioNet AWS Open Data mirror) | 1.0.0 | Open Data Commons Attribution License v1.0 (PhysioNet) | 183,634,285 B zip; 72 EDF | zip sha256 in `results/audit/eegmat_zip_sha256.txt`; all 75 entries of the official `SHA256SUMS.txt` verified OK (`results/audit/eegmat_SHA256SUMS_official.txt`) |
| CMx7-MM (Ajra et al.), OpenNeuro ds007554 | `https://s3.amazonaws.com/openneuro.org/ds007554/` (official OpenNeuro S3 bucket) | 1.0.0 (2026-03-23) | CC0 (dataset_description.json) | 3.3 GB downloaded (EEG EDF, ECG, push-button, events, phenotype; fNIRS/EMG/biodex skipped) | sizes matched to the S3 listing on download; sha256 of every downloaded file in `results/audit/ds007554_downloaded_sha256.txt` |
| PRIMARY: Roy & Nuamah, neuro-stress-resilience-hci | `https://physionet.org/files/neuro-stress-resilience-hci/1.0.0/` (direct; not mirrored on AWS Open Data) | 1.0.0 | ODbL (LICENSE.txt in the release) | docs 6 files; MATB-II 35 × ~6.5 KB; PPG 35 folders ≈ 34 MB; EEG p01-p05 combined CSVs 577-606 MB each (2.9 GB total raw) | every downloaded file verified against the official `SHA256SUMS.txt` (`results/audit/matb_SHA256SUMS_verified.txt`; 325/325 OK for docs+MATB+PPG+EEG p01-p05). Transport note: physionet.org served an expired TLS certificate on 2026-09-09; the owner authorised a certificate-check bypass for these public files only, so integrity rests on the SHA256 manifest, not on TLS. |
| drivedb (Healey & Picard, stress recognition in automobile drivers) | `https://physionet-open.s3.amazonaws.com/drivedb/1.0.0/` (official PhysioNet AWS Open Data mirror) | 1.0.0 | PhysioNet open data terms (ODbL-type; LICENSE per PhysioNet) | 109 MB, 18 records (drive13 = drive14 duplicate) | 37/37 entries of the official SHA256SUMS.txt verified OK; used only for the frozen ECG recovery transfer test (`scripts/drivedb_recovery.py`) |
| BIOT pretrained EEG encoder (Yang et al. 2023) | `https://raw.githubusercontent.com/ycq091044/BIOT/main/pretrained-models/EEG-PREST-16-channels.ckpt` | repo main | MIT (code and released checkpoints in the repo) | 13,791,969 B | sha256 `40f55f5d23e83796495616c8145c8336fcff2b901c42e8ba5115223081c2ad70`; executed frozen on EEGMAT windows only (Section 5 of RESULTS.md); cached under `data/cache/biot/` (gitignored) |

Software: Python 3.11.15; exact package versions in `requirements.lock.txt` (wfdb 4.3.1 added 2026-09-10 for drivedb) (torch 2.14.0 and linear-attention-transformer 0.19.1 are needed only by `scripts/biot_frozen_eegmat.py`). Seeds: 0 everywhere (`SEED = 0` in scripts).

Analysis provenance: every table in `results/tables/` and figure in `results/figures/` is produced by
`scripts/run_all.sh` from the raw files above; intermediate per-bin features (`data/features/*.parquet`)
are regenerated, not tracked.
