# SmartCity ITPL - rebuilt forecasting dashboard

LSTM (with attention) + MOPSO + FastAPI dashboard, trained on `data/smartcity_data.xlsx`.

## Run it (Windows Command Prompt, Python 3.10-3.12)

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

    python prepare_data.py          :: clean data, hourly grid, time-ordered split
    python train.py                 :: train, compare with baselines, feature importance
    uvicorn api:app --port 8000     :: then open http://localhost:8000

Optional:

    python mopso.py tune            :: MOPSO searches LSTM settings (error vs model size)
    python train.py --config artifacts/best_config.json
    python mopso.py control 0.6     :: traffic plan for a forecast congestion of 0.6
    set GROQ_API_KEY=your_key       :: chatbot answers with an LLM instead of rules
    set REPLAY_SECONDS=2            :: faster replay

## Files

| File | Job |
|---|---|
| prepare_data.py | Excel -> hourly table; short-gap interpolation only; time-ordered 70/15/15 split; scalers fitted on training data only |
| common.py | Model (LSTM + attention), masked loss, loaders |
| train.py | Training, test scores vs two baselines, permutation importance |
| mopso.py | MOPSO: `control` (signals, speed limits, diversion) and `tune` (LSTM settings) |
| api.py | REST API; replays the unseen test period as "live" data |
| dashboard.html | The web page |

## Read this before you present results

- CO2, noise, vehicle count, speed and congestion in the Excel file are **estimates computed by the collector**
  (CO2 = CO x 13.5 + 400; noise from a formula; traffic from a time-of-day table), not sensor measurements.
  The model therefore mostly learns those patterns. Say so in any report.
- CO2 was only recorded from April to July 2026. It is scored on a hold-out inside that period and is the weakest forecast.
- The MOPSO traffic objectives are a simple model with stated assumptions (see top of mopso.py), not calibrated on real junction data.
- "Live" is a replay of recorded data. To go live, feed fresh rows into the hourly table; the rest stays the same.