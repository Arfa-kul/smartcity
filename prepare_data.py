"""prepare_data.py - Excel -> clean hourly table + chronological split.

What is different from the original pipeline (and why):
  * Hourly grid (the data is ~30-60 min apart); we do NOT invent 15-minute rows.
  * Interpolation only across short gaps (<=3 h); long gaps stay empty and any
    window touching them is dropped.
  * Split by TIME (70/15/15) and a window never straddles two splits, so the
    test set contains no near-copies of training windows.
  * Scalers / clip bounds are fitted on the training period only.
  * Every target hour records whether it was really observed; the loss and the
    metrics only count observed hours.
"""
import json, os, sys
import numpy as np
import pandas as pd
from common import ART, SEQ, HOR, TARGETS

XLSX = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "smartcity_data.xlsx")
DENSE = ["vehicle_count", "traffic_speed", "congestion", "noise_db", "temperature", "humidity",
         "pressure", "wind_speed", "is_weekend", "is_peak_hour",
         "hour_sin", "hour_cos", "dow_sin", "dow_cos"]
SPARSE = ["co2", "aqi"]                      # mostly missing -> kept, with an 'observed' flag
FEATURES = DENSE + SPARSE + ["obs_co2", "obs_aqi"]


def main():
    os.makedirs(ART, exist_ok=True)
    raw = pd.read_excel(XLSX)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    raw = raw.sort_values("timestamp").set_index("timestamp")
    num = raw.select_dtypes("number").drop(columns=["id"], errors="ignore")

    # obvious sensor/API failures -> missing
    bad_w = (num["pressure"] == 0)
    num.loc[bad_w, ["temperature", "humidity", "pressure"]] = np.nan

    h = num.resample("1h").mean()
    OBS = ["co2", "aqi", "noise_db", "congestion"]
    obs = num[OBS].notna().resample("1h").max().fillna(False).astype(int)
    n = len(h)
    have = np.flatnonzero(num.resample("1h").size().gt(0).values)   # hours with real data
    t1, t2 = int(have[int(len(have) * 0.70)]), int(have[int(len(have) * 0.85)])  # split by DATA, in time order

    # clip vehicle_count using TRAIN-period quantiles only
    lo, hi = h["vehicle_count"].iloc[:t1].quantile([0.01, 0.99])
    h["vehicle_count"] = h["vehicle_count"].clip(lo, hi)

    # short-gap interpolation only
    for c in DENSE[:8] + TARGETS:
        h[c] = h[c].interpolate(method="time", limit=3, limit_area="inside")
    for c in SPARSE:
        h[c] = h[c].interpolate(method="time", limit=6, limit_area="inside")

    idx = h.index
    h["is_weekend"] = (idx.weekday >= 5).astype(int)
    h["is_peak_hour"] = ((idx.weekday < 5) & (((idx.hour >= 7) & (idx.hour <= 10)) |
                                              ((idx.hour >= 17) & (idx.hour <= 20)))).astype(int)
    h["hour_sin"], h["hour_cos"] = np.sin(2 * np.pi * idx.hour / 24), np.cos(2 * np.pi * idx.hour / 24)
    h["dow_sin"], h["dow_cos"] = np.sin(2 * np.pi * idx.weekday / 7), np.cos(2 * np.pi * idx.weekday / 7)
    for c in OBS:
        h["obs_" + c] = obs[c].values
    h = h[FEATURES + [c for c in TARGETS if c not in FEATURES] + ["obs_" + t for t in TARGETS]]
    h = h.loc[:, ~h.columns.duplicated()]

    # train-only statistics (sparse columns: mean over available values)
    tr = h.iloc[:t1]
    mean = tr[FEATURES].mean().fillna(0).values
    std = tr[FEATURES].std().fillna(1).clip(lower=1e-6).values
    fill = dict(zip(FEATURES, mean))
    for c in SPARSE:
        h[c] = h[c].fillna(fill[c])                   # -> z = 0 where unknown (flag tells the model)
    tmean = tr[TARGETS].mean().values
    tstd = tr[TARGETS].std().clip(lower=1e-6).values

    # valid window ends: inputs complete, some target observed, span inside one split
    ok_in = h[DENSE].notna().all(axis=1).values
    ends = {"train": [], "val": [], "test": []}
    obs_t = h[["obs_" + t for t in TARGETS]].values
    for name, (a, b) in {"train": (0, t1), "val": (t1, t2), "test": (t2, n)}.items():
        for e in range(a + SEQ - 1, b - HOR):
            if ok_in[e - SEQ + 1:e + 1].all() and obs_t[e + 1:e + 1 + HOR].any():
                ends[name].append(e)

    h.to_csv(os.path.join(ART, "hourly.csv"))
    meta = {"features": FEATURES, "mean": mean.tolist(), "std": std.tolist(),
            "tgt_mean": tmean.tolist(), "tgt_std": tstd.tolist(), "ends": ends,
            "split": {"train_end": str(idx[t1]), "val_end": str(idx[t2])}}
    json.dump(meta, open(os.path.join(ART, "meta.json"), "w"))

    print(f"raw rows {len(raw):,}  ->  hourly slots {n:,}  (hours with real data: {int(num.resample('1h').size().gt(0).sum())})")
    print(f"vehicle_count clipped to [{lo:.0f}, {hi:.0f}] (train quantiles)")
    for k, v in ends.items():
        print(f"{k:5s}: {len(v):4d} windows")
    for t in TARGETS:
        print(f"observed share of {t:10s}: {100 * h['obs_' + t].mean():.0f}% of hours")


if __name__ == "__main__":
    main()