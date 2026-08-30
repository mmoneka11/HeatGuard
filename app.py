"""HeatGuard dashboard — worker-safety heat screening on real FortyGuard data.

    streamlit run app.py

Loads the CSV produced by screen_worksites.py (instant, reliable for the demo)
and shows a U.S. map, a ranked safety table, and headline metrics. A sidebar
button re-pulls live from the FortyGuard API on demand.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from heatguard.config import OUTPUTS_DIR, THRESHOLD_C
from heatguard.screener import BAND_COLOR, BAND_ACTION, BANDS, band_from_pct

load_dotenv()
CSV = OUTPUTS_DIR / "worksite_heat_screening.csv"
BAND_ORDER = [b for b, _ in BANDS]
WINDOW_HOURS = 15 * 24        # fallback denominator if the CSV lacks pct_above

st.set_page_config(page_title="HeatGuard · Worker-Safety Heat Screener", layout="wide")
st.title("🛰️ HeatGuard — Worker-Safety Heat Screener")
st.markdown("##### Rank worksites by real heat danger — before your crews are exposed.")
st.caption(f"Real FortyGuard 2 m temperature · exceedance / persistence · "
           f"threshold {THRESHOLD_C:.0f} °C · Hackathon'26 · Model Designing · "
           f"by **Team IG-OGs**")


def legend_html() -> str:
    chips = "".join(
        f"<span style='display:inline-block;padding:3px 10px;margin:2px;border-radius:12px;"
        f"background:{BAND_COLOR[b]};color:white;font-size:0.8rem;font-weight:600'>{b}</span>"
        for b in BAND_ORDER)
    return f"<div style='line-height:2'>{chips}</div>"


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp1252")          # older Windows-written CSV
    df = df.sort_values("hours_above", ascending=False).reset_index(drop=True)
    # Repair columns so old/partial CSVs still render with correct bands.
    if "pct_above" not in df.columns:
        df["pct_above"] = (100 * df["hours_above"] / WINDOW_HOURS).clip(upper=100).round(1)
        df["alert"] = df["pct_above"].map(band_from_pct)   # re-band stale/all-Extreme data
    if "rank" not in df.columns:
        df["rank"] = range(1, len(df) + 1)
    if "action" not in df.columns:
        df["action"] = df["alert"].map(BAND_ACTION)
    return df


# --- sidebar: optional live refresh -------------------------------------
with st.sidebar:
    st.header("Data")
    st.write("Showing cached results from your last screening run.")
    if st.button("🔄 Refresh live from FortyGuard API"):
        with st.spinner("Pulling real exposure for each site (async — ~1 min)…"):
            from heatguard.fortyguard_client import FortyGuardClient
            from heatguard.screener import screen
            client = FortyGuardClient()
            if not client.live:
                st.error("No API key found in .env — can't refresh.")
            else:
                try:
                    rows, meta = screen(client)
                    pd.DataFrame(rows).to_csv(CSV, index=False, encoding="utf-8")
                    load_csv.clear()
                    st.success(f"Refreshed {len(rows)} sites for {meta['start']} → {meta['end']}")
                except Exception as ex:
                    st.error(
                        f"Live refresh failed ({type(ex).__name__}). Showing the last "
                        f"saved data instead. Check your internet/DNS (VPN off, then "
                        f"`ipconfig /flushdns`) and retry, or run `python screen_worksites.py`."
                    )

if not Path(CSV).exists():
    st.warning("No results yet. Run `python screen_worksites.py` first to create the CSV.")
    st.stop()

df = load_csv(str(CSV))

# --- sidebar extras (legend, download, about) ---------------------------
with st.sidebar:
    st.divider()
    st.subheader("Alert bands")
    st.markdown(legend_html(), unsafe_allow_html=True)
    st.download_button(
        "⬇️ Download screening CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="worksite_heat_screening.csv", mime="text/csv",
    )
    st.divider()
    st.caption("HeatGuard scores each U.S. worksite from FortyGuard's real "
               "exceedance (hours above the heat threshold) and persistence "
               "(longest continuous run) layers.")
    st.caption("Team IG-OGs")

# --- headline metrics ---------------------------------------------------
worst = df.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sites screened", len(df))
c2.metric("At Warning or worse", int(df["alert"].isin(["Warning", "Extreme"]).sum()))
c3.metric("Most exposed", worst["site"].split(" - ")[0], f"{worst['pct_above']:.0f}% of window")
c4.metric("Total danger-hours", f"{df['hours_above'].sum():,.0f} h")

# --- map ----------------------------------------------------------------
st.subheader("Worksite heat map")
fig = px.scatter_geo(
    df, lat="lat", lon="lon", scope="usa",
    color="alert", color_discrete_map=BAND_COLOR,
    category_orders={"alert": BAND_ORDER},
    size="hours_above", size_max=28,
    hover_name="site",
    hover_data={"pct_above": True, "longest_run_h": True, "lat": False, "lon": False},
)
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend_title="Alert band", height=430)
st.plotly_chart(fig, width='stretch')
st.markdown(legend_html(), unsafe_allow_html=True)
st.caption("Dot size = total hours above the heat threshold over the screening window.")

# --- ranked table -------------------------------------------------------
st.subheader("Worker-safety ranking")


def badge(band: str) -> str:
    return f"background-color: {BAND_COLOR.get(band, '#999')}; color: white;"


show = df[["rank", "site", "alert", "pct_above", "hours_above", "longest_run_h"]].copy()
show.columns = ["#", "Worksite", "Alert", "% window > threshold", "Danger-hours", "Longest run (h)"]
st.dataframe(
    show.style.map(badge, subset=["Alert"]).format({"% window > threshold": "{:.1f}%"}),
    width='stretch', hide_index=True,
)

# --- recommended actions ------------------------------------------------
st.subheader("Recommended action for the top site")
st.info(f"**{worst['site']} — {worst['alert']}**  ·  {BAND_ACTION[worst['alert']]}")

with st.expander("How HeatGuard scores a site"):
    st.markdown(
        "- For each worksite we pull FortyGuard's real **`exceedance`** "
        "(hours above the heat threshold) and **`persistence`** (longest "
        "continuous run) over a trailing window.\n"
        "- Persistence saturates in peak summer (every hot site hits its daily "
        "max), so we **rank and band on exceedance** — the share of the window "
        "spent above the threshold — which cleanly separates sites.\n"
        "- Each site maps to a band (Extreme → Low) with a recommended action, "
        "so a safety manager knows where to act first."
    )

st.caption("Alert bands follow general public-health heat guidance; not a substitute "
           "for official advisories.")

# --- footer -------------------------------------------------------------
st.markdown("<hr style='margin-top:2rem;margin-bottom:0.5rem'>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center;color:#888;font-size:0.85rem'>"
    "HeatGuard &nbsp;·&nbsp; © 2026 <b>Team IG-OGs</b> &nbsp;·&nbsp; "
    "Built for the FortyGuard Hackathon&rsquo;26 &nbsp;·&nbsp; All rights reserved"
    "</div>",
    unsafe_allow_html=True,
)