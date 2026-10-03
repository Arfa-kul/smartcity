"""common.py - shared model + helpers (SmartCity ITPL, rebuilt version)."""
import json, os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

ROOT = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(ROOT, "artifacts")
TARGETS = ["co2", "noise_db", "congestion"]
SEQ, HOR = 24, 3          # look back 24 h, predict the next 3 h (hourly grid)
UNITS = {"co2": "ppm", "noise_db": "dB(A)", "congestion": "0-1"}


class AttnLSTM(nn.Module):
    """Same idea as Deepthi's model: LSTM -> soft attention over time -> dense head
    that outputs HOR steps x 3 targets at once."""

    def __init__(self, n_feat, n_tgt=3, horizon=HOR, hidden=64, layers=2, dropout=0.2):
        super().__init__()
        self.h, self.t = horizon, n_tgt
        self.lstm = nn.LSTM(n_feat, hidden, layers, batch_first=True,
                            dropout=dropout if layers > 1 else 0.0)
        self.attn = nn.Sequential(nn.Linear(hidden, 32), nn.Tanh(), nn.Linear(32, 1))
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden, 64), nn.ReLU(),
                                  nn.Dropout(dropout), nn.Linear(64, horizon * n_tgt))

    def forward(self, x):
        o, _ = self.lstm(x)
        w = torch.softmax(self.attn(o), dim=1)
        return self.head((w * o).sum(1)).view(-1, self.h, self.t)


def masked_huber(pred, y, m, w, delta=1.0):
    """Huber loss that ignores target hours that were never actually observed."""
    a = (pred - y).abs()
    h = torch.where(a <= delta, 0.5 * a ** 2, delta * (a - 0.5 * delta))
    return (h * m * w).sum() / (m * w).sum().clamp_min(1e-6)


def save_model(model, cfg, n_feat, path=None):
    torch.save({"config": cfg, "n_feat": n_feat, "state": model.state_dict()},
               path or os.path.join(ART, "model.pt"))


def load_model(path=None):
    ck = torch.load(path or os.path.join(ART, "model.pt"), map_location="cpu")
    c = ck["config"]
    m = AttnLSTM(ck["n_feat"], 3, HOR, c["hidden"], c["layers"], c["dropout"])
    m.load_state_dict(ck["state"])
    return m.eval(), c


def load_tables():
    """Returns hourly dataframe, meta dict, z-scored feature matrix Z, target matrix T (z), mask M."""
    df = pd.read_csv(os.path.join(ART, "hourly.csv"), index_col=0, parse_dates=True)
    meta = json.load(open(os.path.join(ART, "meta.json")))
    F = meta["features"]
    mu, sd = np.array(meta["mean"]), np.array(meta["std"])
    Z = np.nan_to_num((df[F].values - mu) / sd)
    tm, ts = np.array(meta["tgt_mean"]), np.array(meta["tgt_std"])
    T = (df[TARGETS].values - tm) / ts          # may contain NaN where not interpolable
    M = df[["obs_" + t for t in TARGETS]].values.astype(np.float32)
    return df, meta, Z, T, M


def make_xy(Z, T, M, ends):
    X = np.stack([Z[e - SEQ + 1:e + 1] for e in ends]).astype(np.float32)
    y = np.stack([T[e + 1:e + 1 + HOR] for e in ends])
    m = np.stack([M[e + 1:e + 1 + HOR] for e in ends]).astype(np.float32)
    m = m * (~np.isnan(y))
    return X, np.nan_to_num(y).astype(np.float32), m.astype(np.float32)