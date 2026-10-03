"""mopso.py - Multi-Objective PSO, two uses.

    python mopso.py control   # traffic plan (signals / speed limits / diversion) for the current forecast
    python mopso.py tune      # tune the LSTM hyper-parameters (error vs model size)

CONTROL mode keeps Deepthi's 15 decision variables, but fixes the objectives:
  * demand comes from the LSTM congestion forecast (before: a constant read from the DB)
  * green time trades main-road delay against side-street delay (Webster delay formula)
  * speed trades travel time against emissions (U-shaped emission curve)
  * diverting traffic cuts main-road flow but adds detour time and emissions
These are MODEL ASSUMPTIONS (documented below), not calibrated on measured traffic.
"""
import json, os, sys
import numpy as np

JUNCTIONS = ["ITPL Gate", "Whitefield Main", "Hope Farm", "Channasandra Jn", "Kundalahalli", "Brookefield"]
ROUTES = ["Route A (via ORR)", "Route B (side streets)", "Route C (Varthur Rd)"]
CYCLE, SEG_KM = 90.0, 2.0 / 6                   # signal cycle (s); 2 km corridor in 6 segments
LB = np.array([25.0] * 6 + [30.0] * 6 + [0.0] * 3)   # green s | speed km/h | diverted share
UB = np.array([70.0] * 6 + [60.0] * 6 + [0.5] * 3)
REFERENCE = np.array([45.0] * 6 + [50.0] * 6 + [0.0] * 3)   # "do nothing special" plan


def objectives(X, f):
    """X: (n,15) plans, f: forecast congestion 0..1 -> (n,2) [travel min, emissions kg CO2/h]."""
    X = np.atleast_2d(X)
    g, v, d = X[:, :6], X[:, 6:12], X[:, 12:15].mean(1, keepdims=True)
    y = 0.15 + 0.55 * f * (1 - 0.8 * d)                      # main-road flow ratio
    lam = g / CYCLE
    r = y / lam
    delay = CYCLE * (1 - lam) ** 2 / (2 * (1 - lam * np.minimum(r, 0.95))) + 30 * np.maximum(0, r - 0.95)
    ys = 0.20 + 0.30 * d                                     # side-street flow ratio
    ls = np.clip((CYCLE - g - 8) / CYCLE, 0.1, 0.9)
    rs = ys / ls
    delay_s = CYCLE * (1 - ls) ** 2 / (2 * (1 - ls * np.minimum(rs, 0.95))) + 30 * np.maximum(0, rs - 0.95)
    vel = v * (1 - 0.5 * f * (1 - 0.8 * d))
    travel = (SEG_KM / vel * 60).sum(1) + (delay + 0.8 * delay_s).sum(1) / 60 + 2.0 * d[:, 0]
    flow = 6000 * (0.3 + 0.7 * f)                            # vehicles / h
    ef = 0.11 + 1.6 / vel + 0.000025 * vel ** 2              # kg CO2 per km, rises above ~32 km/h
    emis = (flow * SEG_KM * ef).sum(1) + flow * (delay + 0.8 * delay_s).sum(1) * 0.0005 + flow * d[:, 0] * 0.8 * 0.22
    return np.stack([travel, emis], 1)


def _nondom(F):
    le = (F[:, None, :] <= F[None, :, :]).all(2)
    lt = (F[:, None, :] < F[None, :, :]).any(2)
    return ~(le & lt).any(0)          # column j is dominated if some row i dominates it


def _crowding(F):
    n = len(F); cd = np.zeros(n)
    for j in range(F.shape[1]):
        o = np.argsort(F[:, j]); rng = max(F[o[-1], j] - F[o[0], j], 1e-9)
        cd[o[0]] = cd[o[-1]] = 1e9
        cd[o[1:-1]] += (F[o[2:], j] - F[o[:-2], j]) / rng
    return cd


def _prune(A, AF, cap):
    k = _nondom(AF); A, AF = A[k], AF[k]
    _, u = np.unique(np.round(AF, 6), axis=0, return_index=True)
    A, AF = A[u], AF[u]
    while len(A) > cap:                                       # drop the most crowded point
        i = np.argmin(_crowding(AF)); keep = np.arange(len(A)) != i
        A, AF = A[keep], AF[keep]
    return A, AF


def mopso(fn, lb, ub, n=40, iters=60, cap=40, seed=0):
    """Generic MOPSO: archive of non-dominated points, crowding-distance leaders, velocity clamp."""
    rng = np.random.default_rng(seed)
    pos = lb + rng.random((n, len(lb))) * (ub - lb); vel = np.zeros_like(pos)
    F = fn(pos); pb, pF = pos.copy(), F.copy()
    A, AF = _prune(pos, F, cap)
    for t in range(iters):
        w = 0.9 - 0.5 * t / iters
        cd = _crowding(AF)
        i1, i2 = rng.integers(len(A), size=n), rng.integers(len(A), size=n)
        lead = A[np.where(cd[i1] >= cd[i2], i1, i2)]          # each particle gets its own leader
        vel = (w * vel + 1.5 * rng.random(pos.shape) * (pb - pos) + 1.5 * rng.random(pos.shape) * (lead - pos))
        vmax = 0.2 * (ub - lb); vel = np.clip(vel, -vmax, vmax)
        pos = np.clip(pos + vel, lb, ub); F = fn(pos)
        dom = (F <= pF).all(1) & (F < pF).any(1)
        inc = ~dom & ~((pF <= F).all(1) & (pF < F).any(1))
        sw = dom | (inc & (rng.random(n) < 0.5))
        pb[sw], pF[sw] = pos[sw], F[sw]
        A, AF = _prune(np.vstack([A, pos]), np.vstack([AF, F]), cap)
    return A, AF


def describe(x):
    return {"green_s": {j: round(float(v)) for j, v in zip(JUNCTIONS, x[:6])},
            "speed_kmh": {j: round(float(v)) for j, v in zip(JUNCTIONS, x[6:12])},
            "diverted_pct": {r: round(float(v) * 100) for r, v in zip(ROUTES, x[12:15])}}


def control(f, seed=0):
    """Optimise for forecast congestion f; returns Pareto front + three picks vs the reference plan."""
    A, AF = mopso(lambda P: objectives(P, f), LB, UB, seed=seed)
    o = np.argsort(AF[:, 0]); A, AF = A[o], AF[o]
    ref = objectives(REFERENCE, f)[0]
    nrm = (AF - AF.min(0)) / np.maximum(AF.max(0) - AF.min(0), 1e-9)
    idx = {"fastest": 0, "cleanest": len(A) - 1, "balanced": int(np.argmin(np.hypot(nrm[:, 0], nrm[:, 1])))}
    picks = {k: {"travel_min": round(float(AF[i, 0]), 2), "emissions_kg_h": round(float(AF[i, 1])),
                 "travel_change_pct": round(float((AF[i, 0] / ref[0] - 1) * 100), 1),
                 "emissions_change_pct": round(float((AF[i, 1] / ref[1] - 1) * 100), 1),
                 "plan": describe(A[i])} for k, i in idx.items()}
    return {"forecast_congestion": round(float(f), 3),
            "reference": {"travel_min": round(float(ref[0]), 2), "emissions_kg_h": round(float(ref[1]))},
            "pareto": [{"travel_min": round(float(a), 2), "emissions_kg_h": round(float(b))} for a, b in AF],
            "picks": picks}


def tune(n=8, iters=5, epochs=60):
    """MOPSO over LSTM hyper-parameters. Objectives: validation error (lower better), parameter count."""
    from train import get_data, fit, predict
    from common import AttnLSTM, HOR
    D = get_data(); Xv, yv, mv = D["val"]
    lb, ub = np.array([16, 1, 0.0, -3.3]), np.array([96, 3, 0.5, -2.0])   # hidden, layers, dropout, log10(lr)
    cache = {}

    def cfg_of(p):
        return {"hidden": int(round(p[0])), "layers": int(round(p[1])), "dropout": round(float(p[2]), 2),
                "lr": round(float(10 ** p[3]), 5), "w_co2": 1.0}

    def fn(P):
        out = []
        for p in P:
            c = cfg_of(p); key = json.dumps(c, sort_keys=True)
            if key not in cache:
                m, _ = fit(c, D, epochs=epochs, patience=8)
                err = (np.abs(predict(m, Xv) - yv) * mv).sum() / max(mv.sum(), 1)
                cache[key] = [float(err), float(sum(q.numel() for q in m.parameters()) / 1000)]
                print(f"  tried {c} -> val MAE {cache[key][0]:.3f}, {cache[key][1]:.0f}k params", flush=True)
            out.append(cache[key])
        return np.array(out)

    A, AF = mopso(fn, lb, ub, n=n, iters=iters, cap=12)
    best = cfg_of(A[int(np.argmin(AF[:, 0]))])
    from common import ART
    json.dump([{"config": cfg_of(a), "val_mae_std": float(f[0]), "kparams": float(f[1])} for a, f in zip(A, AF)],
              open(os.path.join(ART, "tune_pareto.json"), "w"), indent=2)
    json.dump(best, open(os.path.join(ART, "best_config.json"), "w"))
    print("Best (lowest error):", best, "\nRetrain with: python train.py --config artifacts/best_config.json")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "control"
    if mode == "tune":
        tune()
    else:
        r = control(float(sys.argv[2]) if len(sys.argv) > 2 else 0.5)
        print(f"Forecast congestion {r['forecast_congestion']} | reference plan: {r['reference']}")
        for k, p in r["picks"].items():
            print(f"{k:9s} travel {p['travel_min']} min ({p['travel_change_pct']:+}%)  "
                  f"emissions {p['emissions_kg_h']} kg/h ({p['emissions_change_pct']:+}%)")
        print("Front size:", len(r["pareto"]), "| balanced plan:", json.dumps(r["picks"]["balanced"]["plan"]))