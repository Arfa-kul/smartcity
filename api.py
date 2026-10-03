"""api.py - FastAPI server for the SmartCity ITPL dashboard.

    uvicorn api:app --port 8000        then open  http://localhost:8000

"Real time" here = REPLAY of the recorded test period: the server steps through the hours
the model never trained on, one every REPLAY_SECONDS, and forecasts the next 3 hours from
exactly the same preprocessed features used in training. To go live later, replace
`row_at()` / the table with fresh collector rows - nothing else changes.
"""
import asyncio, json, os
from contextlib import asynccontextmanager
import numpy as np
import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest
import common, mopso
from common import ART, ROOT, TARGETS, SEQ, HOR

REPLAY_SECONDS = float(os.getenv("REPLAY_SECONDS", "5"))
S = {}          # loaded state
ESTIMATED = {"co2": "estimated from CO (CO x 13.5 + 400)", "noise_db": "computed from traffic estimate (formula)",
             "congestion": "estimated from traffic estimate", "vehicle_count": "estimated", "traffic_speed": "estimated"}


@asynccontextmanager
async def lifespan(app):
    S["model"], S["cfg"] = common.load_model()
    S["df"], S["meta"], S["Z"], S["T"], S["M"] = common.load_tables()
    S["ends"], S["i"], S["mopso"] = S["meta"]["ends"]["test"], 0, {}
    S["metrics"] = json.load(open(os.path.join(ART, "metrics.json")))
    S["importance"] = json.load(open(os.path.join(ART, "importance.json")))
    F = S["meta"]["features"]
    S["dense"] = [F.index(c) for c in ["vehicle_count", "traffic_speed", "congestion", "noise_db",
                                       "temperature", "humidity", "pressure", "wind_speed", "hour_sin", "hour_cos"]]
    tr = np.unique(np.concatenate([np.arange(e - SEQ + 1, e + 1) for e in S["meta"]["ends"]["train"][::4]]))
    S["iso"] = IsolationForest(contamination=0.03, random_state=0).fit(S["Z"][tr][:, S["dense"]])

    async def tick():
        while True:
            await asyncio.sleep(REPLAY_SECONDS)
            S["i"] = (S["i"] + 1) % len(S["ends"])
    task = asyncio.create_task(tick())
    yield
    task.cancel()


app = FastAPI(title="SmartCity ITPL", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def num(x, nd=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def forecast_at(pos):
    X = torch.tensor(S["Z"][pos - SEQ + 1:pos + 1][None].astype(np.float32))
    with torch.no_grad():
        p = S["model"](X).numpy()[0]
    p = p * np.array(S["meta"]["tgt_std"]) + np.array(S["meta"]["tgt_mean"])
    p[:, 0] = np.maximum(p[:, 0], 0); p[:, 1] = np.maximum(p[:, 1], 0); p[:, 2] = np.clip(p[:, 2], 0, 1)
    return [{"hour": f"+{h + 1}h", "time": str(S["df"].index[pos + 1 + h]),
             "co2": num(p[h, 0]), "noise_db": num(p[h, 1]), "congestion": num(p[h, 2], 3)} for h in range(HOR)]


def anomaly_at(pos):
    z = S["Z"][pos]
    reasons = []
    if S["iso"].predict(z[S["dense"]][None])[0] == -1:
        reasons.append("unusual combination of readings (Isolation Forest)")
    F = S["meta"]["features"]
    for c in ["noise_db", "congestion", "vehicle_count"]:
        if abs(z[F.index(c)]) > 3:
            reasons.append(f"{c} is {abs(z[F.index(c)]):.1f} standard deviations from normal")
    return {"status": "NORMAL" if not reasons else "WARNING" if len(reasons) == 1 else "CRITICAL", "reasons": reasons}


def state():
    i = S["i"]; pos = S["ends"][i]; df = S["df"]; r = df.iloc[pos]
    obs = lambda c, k: (num(df[c].iloc[k]) if df["obs_" + c].iloc[k] > 0 else None)
    recent = [dict(zip(["time", "co2", "noise_db", "congestion"],
                       [str(df.index[k]), obs("co2", k), num(df["noise_db"].iloc[k]), num(df["congestion"].iloc[k], 3)]))
              for k in range(pos - SEQ + 1, pos + 1)]
    future = [{"time": str(df.index[pos + 1 + h]), "co2": obs("co2", pos + 1 + h),
               "noise_db": obs("noise_db", pos + 1 + h), "congestion": obs("congestion", pos + 1 + h)}
              for h in range(HOR)]
    anomalies = [dict(time=str(df.index[S["ends"][j]]), **a) for j in range(max(0, i - 48), i + 1)
                 if (a := anomaly_at(S["ends"][j]))["status"] != "NORMAL"][-5:]
    return {"mode": "replay", "step": i + 1, "of": len(S["ends"]), "time": str(df.index[pos]),
            "now": {"co2": obs("co2", pos), "noise_db": num(r.noise_db), "congestion": num(r.congestion, 3),
                    "vehicle_count": num(r.vehicle_count, 0), "traffic_speed": num(r.traffic_speed, 1),
                    "aqi": obs("aqi", pos), "temperature": num(r.temperature, 1)},
            "forecast": forecast_at(pos), "recent": recent, "recorded_next": future,
            "anomaly": anomaly_at(pos), "recent_anomalies": anomalies, "estimated": ESTIMATED,
            "co2_note": "No CO2 readings exist after 4 Jul 2026, so CO2 forecasts here are not validated."}


@app.get("/state")
def get_state():
    return state()


@app.get("/mopso")
def get_mopso(refresh: bool = False):
    i = S["i"]
    if i not in S["mopso"] or refresh:
        f = float(np.clip(np.mean([r["congestion"] for r in forecast_at(S["ends"][i])]), 0, 1))
        S["mopso"] = {i: mopso.control(f, seed=i)}
    return S["mopso"][i]


@app.get("/importance")
def get_importance():
    return S["importance"]


@app.get("/metrics")
def get_metrics():
    return S["metrics"]


class Q(BaseModel):
    question: str


def rule_answer(q, st):
    q = q.lower(); n, f = st["now"], st["forecast"]
    if any(w in q for w in ["forecast", "predict", "next", "hour"]):
        return "Next 3 hours: " + "; ".join(f"{r['hour']} noise {r['noise_db']} dB, congestion {r['congestion']}" for r in f) + "."
    if any(w in q for w in ["mopso", "optim", "signal", "plan"]):
        b = get_mopso()["picks"]["balanced"]
        return (f"Balanced plan: travel {b['travel_change_pct']:+}% and emissions {b['emissions_change_pct']:+}% "
                f"versus the standard plan (model estimate).")
    if any(w in q for w in ["why", "driver", "explain", "important"]):
        t = S["importance"]["noise_db"][:3]
        return "Biggest drivers of the noise forecast: " + ", ".join(r["feature"] for r in t) + " - mostly time-of-day and day-of-week patterns."
    if any(w in q for w in ["anomal", "alert", "unusual"]):
        a = st["anomaly"]
        return f"Status {a['status']}. " + ("; ".join(a["reasons"]) or "Nothing unusual this hour.")
    return (f"At {st['time']}: noise {n['noise_db']} dB, congestion {n['congestion']}, "
            f"{n['vehicle_count']:.0f} vehicles/h (estimated), speed {n['traffic_speed']} km/h.")


@app.post("/chat")
async def chat(q: Q):
    st = state()
    key = os.getenv("GROQ_API_KEY")
    if key:
        try:
            from groq import Groq
            ctx = json.dumps({k: st[k] for k in ["time", "now", "forecast", "anomaly", "estimated", "co2_note"]})
            r = Groq(api_key=key).chat.completions.create(
                model="llama-3.3-70b-versatile", max_tokens=500,
                messages=[{"role": "system", "content": "You assist city planners with the SmartCity ITPL dashboard. "
                           "Answer only from the JSON context. Say clearly when values are estimated."},
                          {"role": "user", "content": f"Context: {ctx}\n\nQuestion: {q.question}"}])
            return {"answer": r.choices[0].message.content, "source": "groq"}
        except Exception as e:
            return {"answer": rule_answer(q.question, st), "source": f"rules (Groq failed: {type(e).__name__})"}
    return {"answer": rule_answer(q.question, st), "source": "rules (set GROQ_API_KEY for an LLM)"}


@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT, "dashboard.html"))