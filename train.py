"""train.py - train the attention-LSTM, compare with simple baselines, explain it.

    python train.py                       # default config
    python train.py --config artifacts/best_config.json   # config found by mopso.py tune
"""
import argparse, json, os
import numpy as np
import torch
from common import (ART, TARGETS, UNITS, SEQ, HOR, AttnLSTM, masked_huber,
                    load_tables, make_xy, save_model)

DEFAULT = {"hidden": 48, "layers": 2, "dropout": 0.25, "lr": 2e-3, "w_co2": 1.0}


def get_data():
    df, meta, Z, T, M = load_tables()
    D = {"meta": meta, "Z": Z, "T": T, "M": M, "df": df}
    # CO2 was only measured Apr-Jul, so val/test have none. Hold out the last 20% of the
    # observed CO2 hours: never trained on, used only for the final CO2 score.
    obs = np.flatnonzero(M[:, 0] > 0)
    cut = int(obs[int(len(obs) * 0.8)])
    Mtr = M.copy(); Mtr[cut:, 0] = 0
    for k in ("train", "val", "test"):
        D[k] = make_xy(Z, T, Mtr, meta["ends"][k])
    he = [e for e in meta["ends"]["train"] + meta["ends"]["val"]
          if (M[max(e + 1, cut):e + 1 + HOR, 0] > 0).any()]
    Mh = np.zeros_like(M); Mh[cut:, 0] = M[cut:, 0]
    D["co2_hold"], D["co2_hold_ends"], D["co2_cut"] = make_xy(Z, T, Mh, he), he, cut
    D["F"] = Z.shape[1]
    return D


def predict(model, X):
    with torch.no_grad():
        return model(torch.tensor(X)).numpy()


def fit(cfg, D, epochs=120, patience=15, verbose=False, seed=0):
    torch.manual_seed(seed); np.random.seed(seed)
    model = AttnLSTM(D["F"], 3, HOR, cfg["hidden"], cfg["layers"], cfg["dropout"])
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=1e-4)
    w = torch.tensor([cfg.get("w_co2", 1.0), 1.0, 1.0]).view(1, 1, 3)
    Xtr, ytr, mtr = [torch.tensor(a) for a in D["train"]]
    Xva, yva, mva = [torch.tensor(a) for a in D["val"]]
    best, best_state, bad = 1e9, None, 0
    for ep in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(perm), 32):
            b = perm[i:i + 32]
            opt.zero_grad()
            masked_huber(model(Xtr[b]), ytr[b], mtr[b], w).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            vl = masked_huber(model(Xva), yva, mva, w).item()
        if vl < best - 1e-4:
            best, bad = vl, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
        if verbose and (ep % 10 == 0 or bad == 0):
            print(f"  epoch {ep:3d}  val loss {vl:.4f}  best {best:.4f}")
        if bad >= patience:
            break
    model.load_state_dict(best_state)
    return model.eval(), best


def metrics(pred, y, m, meta):
    """Masked MAE / RMSE / R2 in real units, per target (observed hours only)."""
    out = {}
    for j, t in enumerate(TARGETS):
        k = m[:, :, j] > 0
        sd, mu = meta["tgt_std"][j], meta["tgt_mean"][j]
        p, a = pred[:, :, j][k] * sd + mu, y[:, :, j][k] * sd + mu
        if len(a) < 2:
            continue
        ss = ((a - a.mean()) ** 2).sum()
        out[t] = {"mae": float(np.abs(p - a).mean()), "rmse": float(np.sqrt(((p - a) ** 2).mean())),
                  "r2": float(1 - ((p - a) ** 2).sum() / ss) if ss > 0 else float("nan"),
                  "n": int(len(a)), "unit": UNITS[t]}
    return out


def baselines(D, ends, data):
    """persistence: repeat the last known value; seasonal: same hour yesterday."""
    meta, Z, T = D["meta"], D["Z"], D["T"]
    ends = np.array(ends)
    X, y, m = data
    feats = meta["features"]
    cols = [feats.index(t) for t in TARGETS]
    last = X[:, -1, :][:, cols]                              # z-scored last values
    pers = np.repeat(last[:, None, :], HOR, axis=1)
    seas = np.stack([T[e + 1 - 24:e + 1 - 24 + HOR] for e in ends])
    ms = m * (~np.isnan(seas))
    return pers, np.nan_to_num(seas), ms


def importance(model, X, y, m, meta, seed=0):
    """Permutation importance: how much does MAE (in standardised units) rise when one
    feature is shuffled across windows? (This is what Deepthi's 'SHAP' file really computes.)"""
    rng = np.random.default_rng(seed)
    base = np.abs(predict(model, X) - y) * m
    base = base.sum((0, 1)) / np.maximum(m.sum((0, 1)), 1)
    res = {t: [] for t in TARGETS}
    for j, f in enumerate(meta["features"]):
        Xp = X.copy()
        Xp[:, :, j] = X[rng.permutation(len(X)), :, j]
        e = np.abs(predict(model, Xp) - y) * m
        e = e.sum((0, 1)) / np.maximum(m.sum((0, 1)), 1)
        for i, t in enumerate(TARGETS):
            res[t].append((f, float(e[i] - base[i])))
    return {t: [{"feature": f, "importance": round(v, 4)} for f, v in
                sorted(r, key=lambda z: -z[1])[:8]] for t, r in res.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--epochs", type=int, default=120)
    a = ap.parse_args()
    cfg = json.load(open(a.config)) if a.config else DEFAULT
    D = get_data()
    print(f"windows  train {len(D['train'][0])}  val {len(D['val'][0])}  test {len(D['test'][0])}   features {D['F']}")
    print(f"config   {cfg}")
    model, best = fit(cfg, D, epochs=a.epochs, verbose=True)
    save_model(model, cfg, D["F"])

    Xte, yte, mte = D["test"]
    res = {"config": cfg, "model": metrics(predict(model, Xte), yte, mte, D["meta"])}
    p, s, ms = baselines(D, D["meta"]["ends"]["test"], D["test"])
    res["persistence"] = metrics(p, yte, mte, D["meta"])
    res["same_hour_yesterday"] = metrics(s, yte, ms, D["meta"])

    print("\nTEST SET (later in time than anything the model trained on; observed hours only)")
    print(f"{'target':<11}{'model R2':>9}{'MAE':>8}   {'persist R2':>10}{'MAE':>8}   {'yday R2':>8}{'MAE':>8}")
    for t in TARGETS:
        g = lambda k: res[k].get(t, {"r2": float('nan'), "mae": float('nan')})
        print(f"{t:<11}{g('model')['r2']:>9.3f}{g('model')['mae']:>8.3f}   "
              f"{g('persistence')['r2']:>10.3f}{g('persistence')['mae']:>8.3f}   "
              f"{g('same_hour_yesterday')['r2']:>8.3f}{g('same_hour_yesterday')['mae']:>8.3f}")
    Xh, yh, mh = D["co2_hold"]
    ph, sh, msh = baselines(D, D["co2_hold_ends"], D["co2_hold"])
    res["co2_holdout"] = {"model": metrics(predict(model, Xh), yh, mh, D["meta"]).get("co2"),
                          "persistence": metrics(ph, yh, mh, D["meta"]).get("co2"),
                          "same_hour_yesterday": metrics(sh, yh, msh * (mh > 0), D["meta"]).get("co2"),
                          "from": str(D["df"].index[D["co2_cut"]])}
    h = res["co2_holdout"]
    print(f"{'co2*':<11}{h['model']['r2']:>9.3f}{h['model']['mae']:>8.3f}   {h['persistence']['r2']:>10.3f}"
          f"{h['persistence']['mae']:>8.3f}   {h['same_hour_yesterday']['r2']:>8.3f}{h['same_hour_yesterday']['mae']:>8.3f}")
    print(f"* CO2 was only measured Apr-Jul 2026; this row is a hold-out of its last 20% (from {h['from'][:10]}, n={h['model']['n']}).")
    json.dump(res, open(os.path.join(ART, "metrics.json"), "w"), indent=2)
    imp = importance(model, Xte, yte, mte, D["meta"])
    json.dump(imp, open(os.path.join(ART, "importance.json"), "w"), indent=2)
    print("\nTop drivers:", {t: [r["feature"] for r in imp[t][:3]] for t in TARGETS})
    print("Saved artifacts/model.pt, metrics.json, importance.json")