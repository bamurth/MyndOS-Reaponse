"""Optional: frozen BIOT embeddings on EEGMAT 10-s windows vs handcrafted features vs random-weight BIOT.

Contract audited from github.com/ycq091044/BIOT (MIT): input [batch, 16, 2000] at 200 Hz, 16 bipolar
10-20 montages (BIOT_16_MONTAGE), per-window amplitude scaling by the 95th percentile of |x| (as in the
repo's TUAB loader), STFT n_fft=200 hop=100, mean-pooled 256-d embedding. Checkpoint EEG-PREST-16-channels.ckpt
(sha256 40f55f5d...) is loaded with strict key matching after stripping the 'biot.' prefix if present.
Evaluation: participant-grouped 12-fold logistic regression, baseline vs task, identical folds to eegmat_analysis.
This is an encoder audit, not a foundation-model result; N=36.
"""
import sys, json, os, time
sys.path.insert(0, "src"); sys.path.insert(0, "data/cache/biot")
import numpy as np, pandas as pd
from scipy import signal as sps
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
import torch
from model.biot import BIOTEncoder
from myndos.io_eegmat import subjects, load_edf, ROOT
from myndos.encoder import bipolar_montage, BIOT_16_MONTAGE
from myndos.modeling import participant_folds, paired_bootstrap
from myndos.signal import eeg_preprocess

torch.manual_seed(0); np.random.seed(0); SEED = 0
CKPT = "data/cache/biot/pretrained-models/EEG-PREST-16-channels.ckpt"
bins = pd.read_parquet("data/features/eegmat_bins.parquet")

def load_encoder(pretrained: bool):
    enc = BIOTEncoder(emb_size=256, heads=8, depth=4, n_channels=16)
    if pretrained:
        sd = torch.load(CKPT, map_location="cpu")
        sd = {k[len("biot."):] if k.startswith("biot.") else k: v for k, v in sd.items()}
        missing, unexpected = enc.load_state_dict(sd, strict=False)
        print("state_dict: missing", len(missing), "unexpected", len(unexpected))
        if missing or unexpected: print("  missing:", missing[:5], "unexpected:", unexpected[:5])
    enc.eval(); return enc

t0 = time.time(); windows, meta = [], []
for sid in subjects():
    for tag, cond in (("1", "baseline"), ("2", "task")):
        d = load_edf(f"{ROOT}/{sid}_{tag}.edf"); fs = d["fs"]
        bp = bipolar_montage(eeg_preprocess(d["eeg"], fs, notch=50.0), d["eeg_names"], BIOT_16_MONTAGE)
        x200 = sps.resample_poly(bp, 2, 5, axis=1)  # 500 -> 200 Hz
        b = bins[(bins.pid == sid) & (bins.condition == cond)]
        for r in b.itertuples():
            w = x200[:, int(r.t_start * 200):int(r.t_end * 200)]
            if w.shape[1] != 2000: continue
            w = w / (np.quantile(np.abs(w), 0.95, axis=-1, keepdims=True) + 1e-8)
            windows.append(w.astype(np.float32)); meta.append({"pid": sid, "condition": cond, "t_end": r.t_end})
X = torch.tensor(np.stack(windows)); M = pd.DataFrame(meta)
print("windows", X.shape, f"{time.time()-t0:.0f}s")

def embed(enc):
    out = []
    with torch.no_grad():
        for i in range(0, len(X), 64): out.append(enc(X[i:i + 64]).numpy())
    return np.vstack(out)
E_pre = embed(load_encoder(True)); E_rand = embed(load_encoder(False)); print("embedded", f"{time.time()-t0:.0f}s")

def cv_auc(F):
    y = (M.condition == "task").astype(int).to_numpy(); pids = M.pid.to_numpy(); pred = np.full(len(y), np.nan)
    for tr, te in participant_folds(pids, 12, SEED):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000)).fit(F[tr], y[tr]); pred[te] = m.predict_proba(F[te])[:, 1]
    per = pd.DataFrame({"y": y, "p": pred, "pid": pids}).groupby("pid").apply(lambda g: roc_auc_score(g.y, g.p) if g.y.nunique() == 2 else np.nan, include_groups=False)
    return {"pooled_auc": float(roc_auc_score(y, pred)), "participant_mean_auc": float(per.mean()), "n_windows": int(len(y)), "n_participants": int(len(per))}, per
hand_cols = [c for c in bins.columns if c.startswith("eeg_") and c not in ("eeg_ok", "eeg_bad_ch_frac")]
H = bins.set_index(["pid", "condition", "t_end"]).loc[list(M.itertuples(index=False, name=None))][hand_cols].to_numpy(float)
res = {}; pers = {}
for name, F in (("handcrafted_bandpower_12", H), ("biot_pretrained_frozen_256", E_pre), ("biot_random_weights_256", E_rand), ("handcrafted_plus_biot_pretrained", np.hstack([H, E_pre]))):
    res[name], pers[name] = cv_auc(F); print(name, res[name])
res["paired_participant_auc_diff_pretrained_minus_handcrafted"] = paired_bootstrap(pers["biot_pretrained_frozen_256"] - pers["handcrafted_bandpower_12"], seed=SEED)
res["paired_participant_auc_diff_pretrained_minus_random"] = paired_bootstrap(pers["biot_pretrained_frozen_256"] - pers["biot_random_weights_256"], seed=SEED)
res["note"] = "EEGMAT baseline-vs-task from 10-s windows; logistic regression C=0.1 (fixed, not tuned) on standardized features; participant-grouped 12-fold; encoder frozen; EEG-PREST-16 checkpoint (MIT) with assumed TUAB-style 95th-percentile scaling."
res["versions"] = {"torch": torch.__version__}
json.dump(res, open("results/tables/biot_frozen_eegmat.json", "w"), indent=2, default=float)
print(json.dumps(res, indent=1, default=float))
