# 🛰️ HeatGuard — Real-Data Worker-Safety Heat Screener

**FortyGuard Hackathon'26 · Track 05: Model Designing**

HeatGuard screens a portfolio of U.S. worksites for outdoor-crew heat danger
using **only real FortyGuard data**. For each site it pulls two of FortyGuard's
own analysis layers and turns them into an actionable worker-safety alert:

- **`exceedance`** — how many hours the site spends above the heat threshold.
- **`persistence`** — the longest *continuous* dangerous stretch (the number
  that decides whether a crew must stop work).

Each site is scored into a band — **Safe / Caution / Warning / Extreme** —
mapped to NWS HeatRisk & OSHA-NIOSH exposure guidance, then the portfolio is
ranked so a safety manager knows which sites to act on first.

> **No synthetic data.** A FortyGuard API key is required; the client never
> falls back to generated data. Every number in the output comes from the API.

## Why this fits the API (and the judging criteria)

FortyGuard serves hyperlocal **spatial** heat with `exceedance`/`persistence`
analysis layers — not cheap hourly point histories. This tool is built around
what the API actually provides, so the data is genuinely central, the calls are
credit-cheap (~2 per site), and the output is something a construction,
logistics, or municipal safety team would actually use.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # paste your key into .env

python screen_worksites.py    # 1) pull real data -> outputs/worksite_heat_screening.csv
streamlit run app.py          # 2) open the dashboard on that data
```

Step 1 pulls real FortyGuard exposure for each site and scores it (also saves
`reports/worksite_exposure.png`). Step 2 opens an interactive dashboard — a U.S.
map coloured by alert band, headline metrics, and the ranked safety table —
reading that CSV so it loads instantly. A sidebar button re-pulls live on demand.
Edit `WORKSITES`, `THRESHOLD_C`, `WINDOW_DAYS` in `heatguard/config.py`.

### Live demo link (for the submission)

Deploy free on Streamlit Community Cloud: push this repo to GitHub, go to
share.streamlit.io, pick the repo and `app.py`, and add `FORTYGUARD_API_KEY`
under *Secrets*. That gives the public URL the submission asks for. (Or just
screen-record `streamlit run app.py` locally for the video.)

## The model

Real data shows `persistence` (longest daily danger-run) **saturates** in peak
summer — every hot U.S. site hits ~16 h — so it can't rank sites. The
discriminating signal is `exceedance`: the share of the window spent above the
threshold. HeatGuard ranks and bands on that (Extreme/Warning/Caution/Elevated/
Low) and surfaces the recommended action per band. Choosing the metric that
discriminates — and showing why — is the core modelling decision.

## FortyGuard API usage

- Base `https://api.fortyguard.com` · auth header `api-key` · U.S.-only · dates 2021→today.
- Async: `POST /v1/heatmap` (with `date_time` object, `analytic_type`,
  `threshold` °C, `direction`) → `data.activity_id` → poll `GET /v1/status/{id}`
  until `Completed`. Implemented in `heatguard/fortyguard_client.py`;
  `worksite_exposure()` wraps the exceedance + persistence calls.

## Project layout

```
heatguard/
├── heatguard/
│   ├── config.py             # worksites, threshold, window, paths
│   └── fortyguard_client.py  # real API client (no synthetic fallback)
├── screen_worksites.py       # the screener — main entry point
├── test_client.py            # offline payload/parsing checks (no network)
├── requirements.txt
└── .env.example
```

## Model & extension

The scoring model is a transparent, policy-aligned mapping from real exposure
(`exceedance`, `persistence`) to an action band. With a log of real
heat-incident outcomes it becomes a supervised classifier trained end-to-end on
FortyGuard features; the exposure pull and banding here are the pipeline that
feeds it. A natural next step is FortyGuard's up-to-12-hour heatmap forecast for
**next-shift** alerts rather than trailing-window screening.

*Alert bands follow general public-health heat guidance and are not a substitute
for official advisories.*
