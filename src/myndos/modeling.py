"""Held-out participant prediction with nested tuning, persistence baseline and controls."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0)


def make_targets(df: pd.DataFrame, horizon: float, value_col: str, time_col: str = "t_end",
                 group_cols: tuple[str, ...] = ("pid", "file", "condition")) -> pd.Series:
    """Target for each row = mean of ``value_col`` over the bins whose end time lies in
    (t, t + horizon], within the same (pid, file, condition). NaN unless the horizon is
    fully covered (last covered bin ends exactly at t + horizon) and no value is NaN.
    Inputs at row t may only use information ending at or before t."""
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for _, g in df.groupby(list(group_cols), sort=False):
        g = g.sort_values(time_col)
        t = g[time_col].to_numpy(); v = g[value_col].to_numpy(dtype=float)
        for i in range(len(g)):
            m = (t > t[i] + 1e-9) & (t <= t[i] + horizon + 1e-9)
            if m.sum() == 0 or abs(t[m].max() - (t[i] + horizon)) > 1e-6:
                continue
            vals = v[m]
            if np.isnan(vals).any():
                continue
            out.loc[g.index[i]] = float(np.mean(vals))
    return out


def participant_folds(pids: np.ndarray, n_splits: int, seed: int = 0):
    """GroupKFold over participants with a seeded participant permutation."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(pids)
    perm = {p: i for i, p in enumerate(rng.permutation(uniq))}
    order = np.array([perm[p] for p in pids])
    gkf = GroupKFold(n_splits=min(n_splits, uniq.size))
    return list(gkf.split(np.zeros(len(pids)), groups=order))


def _model(alpha: float):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=alpha))


def nested_ridge_predict(X: np.ndarray, y: np.ndarray, pids: np.ndarray, n_outer: int = 10, n_inner: int = 5,
                         alphas=ALPHAS, seed: int = 0) -> np.ndarray:
    """Out-of-fold predictions; alpha chosen by inner participant-grouped CV on training folds only.
    Imputation and scaling are fitted inside training folds."""
    pred = np.full(len(y), np.nan)
    for tr, te in participant_folds(pids, n_outer, seed):
        best, best_mae = None, np.inf
        inner = participant_folds(pids[tr], n_inner, seed + 1)
        for a in alphas:
            maes = []
            for itr, ite in inner:
                m = _model(a).fit(X[tr][itr], y[tr][itr])
                maes.append(np.mean(np.abs(m.predict(X[tr][ite]) - y[tr][ite])))
            if np.mean(maes) < best_mae:
                best, best_mae = a, np.mean(maes)
        m = _model(best).fit(X[tr], y[tr])
        pred[te] = m.predict(X[te])
    return pred


def participant_mae(y: np.ndarray, pred: np.ndarray, pids: np.ndarray) -> pd.Series:
    d = pd.DataFrame({"e": np.abs(y - pred), "pid": pids})
    return d.groupby("pid")["e"].mean()


def paired_bootstrap(diff_by_pid: pd.Series, n_boot: int = 5000, seed: int = 0) -> dict:
    """Bootstrap over participants of the mean paired difference (equal participant weight)."""
    rng = np.random.default_rng(seed)
    v = diff_by_pid.to_numpy(dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"mean": np.nan, "ci_low": np.nan, "ci_high": np.nan, "n": 0}
    boots = np.array([rng.choice(v, v.size, replace=True).mean() for _ in range(n_boot)])
    return {"mean": float(v.mean()), "ci_low": float(np.percentile(boots, 2.5)),
            "ci_high": float(np.percentile(boots, 97.5)), "n": int(v.size),
            "frac_boot_below_zero": float(np.mean(boots < 0))}


def shuffle_physiology_across_participants(df: pd.DataFrame, phys_cols: list[str], match_cols: list[str],
                                            seed: int = 0) -> pd.DataFrame:
    """Control: replace each row's physiology with that of a *different participant's* row
    matched on ``match_cols`` (e.g. task and elapsed-time bin). Tests whether the correct
    pairing of person and physiology matters."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    for _, g in df.groupby(match_cols, sort=False):
        if g["pid"].nunique() < 2:
            out.loc[g.index, phys_cols] = np.nan
            continue
        idx = g.index.to_numpy()
        for _ in range(20):
            perm = rng.permutation(idx)
            if (df.loc[perm, "pid"].to_numpy() != df.loc[idx, "pid"].to_numpy()).all():
                break
        out.loc[idx, phys_cols] = df.loc[perm, phys_cols].to_numpy()
    return out


def temporal_shift_within_person(df: pd.DataFrame, phys_cols: list[str], shift_bins: int = 3) -> pd.DataFrame:
    """Control: circularly shift each (pid, file) physiology series by ``shift_bins`` bins,
    preserving autocorrelation while breaking the exact temporal pairing."""
    out = df.copy()
    for _, g in df.groupby(["pid", "file"], sort=False):
        g = g.sort_values("t_end")
        out.loc[g.index, phys_cols] = np.roll(g[phys_cols].to_numpy(), shift_bins, axis=0)
    return out
