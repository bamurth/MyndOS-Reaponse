"""Synthetic software checks only. These fixtures are never evidence about people."""
import numpy as np
import pandas as pd
import pytest

from myndos.signal import detect_r_peaks, rr_quality, beat_features, eeg_bin_features, eeg_preprocess, channel_groups
from myndos.binning import make_bins
from myndos.metrics import robust_reference, normalize, first_sustained_departure, burden, recovery, response_magnitude


def synth_ecg(fs=500, dur=60, hr=70, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(0, dur, 1 / fs)
    beats = np.arange(0.5, dur, 60 / hr)
    x = np.zeros_like(t)
    for b in beats:
        x += 1.0 * np.exp(-((t - b) ** 2) / (2 * 0.008 ** 2)) - 0.15 * np.exp(-((t - b - 0.25) ** 2) / (2 * 0.03 ** 2))
    return t, x + 0.02 * rng.standard_normal(t.size), beats


def test_r_peaks_recover_known_beats_and_polarity():
    fs = 500
    _, x, beats = synth_ecg(fs=fs)
    for sign in (1, -1):
        p = detect_r_peaks(sign * x, fs)
        assert abs(p.size - beats.size) <= 1
        err = np.abs(p / fs - beats[:p.size]) if p.size <= beats.size else np.abs(p[:beats.size] / fs - beats)
        assert np.median(err) < 0.01
    tt, rr, valid = rr_quality(p, fs)
    f = beat_features(tt, rr, valid, 0, 60)
    assert abs(f["hr"] - 70) < 1 and f["hr_valid"]


def test_hrv_requires_beat_coverage():
    fs = 500
    _, x, beats = synth_ecg(fs=fs, dur=40)
    p = detect_r_peaks(x, fs)
    tt, rr, valid = rr_quality(p, fs)
    f = beat_features(tt, rr, valid, 0, 40)
    assert f["hrv_valid"]
    # random beat dropout: interval jumps invalidate RR, coverage collapses, HRV must be NaN
    rng = np.random.default_rng(3)
    p2 = p[rng.random(p.size) < 0.6]
    tt, rr, valid = rr_quality(p2, fs)
    f2 = beat_features(tt, rr, valid, 0, 40)
    assert not f2["hrv_valid"] and np.isnan(f2["rmssd"])


def test_bins_never_cross_boundaries():
    segs = [(0, 25, "rest"), (25, 205, "task"), (205, 216, "post")]
    b = make_bins(segs, width=10)
    assert (b.t_end - b.t_start).round(6).eq(10).all()
    for (s, e, lab) in segs:
        sub = b[b.condition == lab]
        assert (sub.t_start >= s - 1e-9).all() and (sub.t_end <= e + 1e-9).all()
    assert (b[b.condition == "rest"].shape[0] == 2) and (b[b.condition == "task"].shape[0] == 18)
    assert b[b.condition == "post"].shape[0] == 1


def test_robust_reference_zero_mad_flag():
    med, sc, flag = robust_reference(np.array([1.0, 1.0, 1.0, 1.0, 1.0]))
    assert flag and np.isnan(sc)
    assert np.isnan(normalize(np.array([1.0, 2.0]), med, sc)).all()
    med, sc, flag = robust_reference(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert not flag and med == 3.0 and abs(sc - 1.4826) < 1e-9


def test_departure_burden_and_censoring():
    t = np.arange(10, 70, 10.0)
    z = np.array([0.5, 2.5, 2.5, 2.5, 0.1, 0.1])
    assert first_sustained_departure(z, t, band=2.0, k=3) == 20.0
    assert np.isnan(first_sustained_departure(z, t, band=2.0, k=4))
    assert np.isnan(first_sustained_departure(z, t, band=3.0))
    assert burden(z, 10.0) == pytest.approx(np.sum(np.abs(z)) * 10)
    # recovery: returns after 3 consecutive in-band valid bins; NaN breaks the run
    zr = np.array([3.0, 1.0, np.nan, 1.0, 1.0, 1.0, 1.0])
    tr = np.arange(10, 80, 10.0)
    r = recovery(zr, tr, band=2.0, k=3)
    assert r["status"] == "returned" and r["return_time"] == 60.0
    r2 = recovery(np.array([3.0, 3.0, 2.5]), np.array([10.0, 20, 30]), band=2.0)
    assert r2["status"] == "censored" and np.isnan(r2["return_time"]) and r2["observed_duration"] == 30
    r3 = recovery(zr, tr, excursion=False)
    assert r3["status"] == "not_estimable"
    assert r["residual_60"] == 1.0


def test_response_magnitude_and_eeg_features():
    assert response_magnitude(np.array([5.0, 6.0, np.nan]), np.array([1.0, 2.0])) == 4.0
    fs = 250
    rng = np.random.default_rng(1)
    names = ["Fp1", "F3", "C3", "P3", "O1", "T7"]
    x = rng.standard_normal((6, fs * 30)) * 10
    tt = np.arange(fs * 30) / fs
    x[4] += 30 * np.sin(2 * np.pi * 10 * tt)  # strong alpha at O1
    y = eeg_preprocess(x, fs)
    f = eeg_bin_features(y, fs, names, 10, 20)
    assert f["eeg_ok"] and f["eeg_occipital_alpha"] > f["eeg_frontal_alpha"] + 0.5
    g = channel_groups(names)
    assert g["frontal"] == [0, 1] and g["central"] == [2, 5] and g["parietal"] == [3] and g["occipital"] == [4]
    # ocular artifact rejects the window when too many channels are bad
    x2 = x.copy(); x2[:, fs * 12:fs * 13] += 500
    f2 = eeg_bin_features(eeg_preprocess(x2, fs), fs, names, 10, 20)
    assert not f2["eeg_ok"] and np.isnan(f2["eeg_frontal_theta"])
