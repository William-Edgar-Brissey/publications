#!/usr/bin/env python3
"""Recompute public RQ5 R0 correlations from processed_rq5_matrix.csv.

This script intentionally begins from the published processed matrix. Exact source
reconstruction requests and remote-payload hashes are in SOURCE_FREEZE_R0.json.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
SEED = 20260831
N_SHUFFLES = 2000

df = pd.read_csv(HERE / "processed_rq5_matrix.csv")

TESTS = {
    "ubay_djf_vs_oni_djf": ("ubay_djf_mm", "oni_djf"),
    "ubay_djf_vs_prev_son_oni": ("ubay_djf_mm", "oni_prev_son"),
    "ubay_jja_vs_djf_oni": ("ubay_jja_mm", "oni_djf"),
    "ubay_djf_vs_dmi_djf": ("ubay_djf_mm", "dmi_djf"),
    "oni_djf_vs_dmi_djf": ("oni_djf", "dmi_djf"),
    "manaus_djf_vs_oni_djf": ("manaus_djf_mm", "oni_djf"),
}

def calculate(xcol, ycol):
    a = df[[xcol, ycol]].dropna()
    x = a[xcol].to_numpy()
    y = a[ycol].to_numpy()
    r, p = stats.pearsonr(x, y)
    rng = np.random.default_rng(SEED)
    target = abs(r)
    hits = 0
    for _ in range(N_SHUFFLES):
        if abs(np.corrcoef(x, rng.permutation(y))[0, 1]) >= target:
            hits += 1
    return {
        "n": len(a),
        "pearson_r": float(r),
        "ordinary_p": float(p),
        "shuffle_hits": hits,
        "shuffle_n": N_SHUFFLES,
        "shuffle_p": hits / N_SHUFFLES,
    }

if __name__ == "__main__":
    for name, (x, y) in TESTS.items():
        print(name, calculate(x, y))
