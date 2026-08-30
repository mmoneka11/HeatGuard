"""Core screening logic — shared by the CLI and the dashboard.

Real FortyGuard data shows `persistence` (longest daily run) saturates in peak
summer, so it can't rank sites. `exceedance` — the share of the window spent
above the heat threshold — is the discriminating signal, so we rank and band on
that and keep persistence as a secondary detail.
"""
from __future__ import annotations

import datetime as dt

from .config import THRESHOLD_C, WINDOW_DAYS, WORKSITES

# band name -> lower bound on "% of window above threshold"
BANDS = [("Extreme", 85), ("Warning", 60), ("Caution", 35), ("Elevated", 15), ("Low", 0)]
BAND_COLOR = {"Extreme": "#e63946", "Warning": "#f4a261", "Caution": "#e9c46a",
              "Elevated": "#8ecae6", "Low": "#2a9d8f", "Unknown": "#999999"}
BAND_ACTION = {
    "Extreme": "Stop-work windows; mandatory shade + hydration; reschedule to night shifts",
    "Warning": "Enforced rest/water cycles; buddy checks; monitor vulnerable crew",
    "Caution": "Hydration reminders; watch afternoon peak; brief crews",
    "Elevated": "Standard hot-weather precautions",
    "Low": "No special action",
    "Unknown": "No data returned",
}


def band_from_pct(pct: float | None) -> str:
    if pct is None:
        return "Unknown"
    for name, lo in BANDS:
        if pct >= lo:
            return name
    return "Low"


def screen(client, worksites=None, threshold_c=THRESHOLD_C, window_days=WINDOW_DAYS,
           end=None):
    """Pull real exposure for each site and score it. Returns (rows, meta)."""
    worksites = worksites or WORKSITES
    end = end or (dt.date.today() - dt.timedelta(days=1))
    start = end - dt.timedelta(days=window_days)
    window_hours = window_days * 24 + 24            # inclusive-ish denominator

    rows = []
    for name, lat, lon in worksites:
        e = client.worksite_exposure(lat, lon, start.isoformat(), end.isoformat(), threshold_c)
        ha, lr = e["hours_above"], e["longest_run_h"]
        pct = min(100.0, 100.0 * ha / window_hours) if ha is not None else None
        band = band_from_pct(pct)
        rows.append({
            "site": name, "lat": lat, "lon": lon,
            "hours_above": round(ha, 1) if ha is not None else None,
            "pct_above": round(pct, 1) if pct is not None else None,
            "longest_run_h": round(lr, 1) if lr is not None else None,
            "alert": band, "action": BAND_ACTION[band],
        })
    rows.sort(key=lambda r: (r["hours_above"] or -1), reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    meta = {"start": start.isoformat(), "end": end.isoformat(),
            "threshold_c": threshold_c, "window_hours": window_hours}
    return rows, meta
