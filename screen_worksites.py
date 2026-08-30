"""HeatGuard CLI — pull real FortyGuard exposure, score, rank, save CSV + chart.

    cp .env.example .env       # paste your key
    python screen_worksites.py
"""
from __future__ import annotations

import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

from heatguard.config import REPORTS_DIR, OUTPUTS_DIR
from heatguard.screener import screen, BAND_COLOR
from heatguard.fortyguard_client import FortyGuardClient

load_dotenv()


def main():
    client = FortyGuardClient()
    if not client.live:
        sys.exit("No API key found. Put FORTYGUARD_API_KEY=... in .env, then rerun.")
    print(f"Using API base URL: {client.base_url}")
    try:
        u = client.fetch_api_key_usage().get("credit_summary", {})
        print(f"Credits remaining: {u.get('total_remaining_credits', '?')}")
    except Exception as e:
        print("(usage check skipped:", e, ")")

    rows, meta = screen(client)
    print(f"\nScreened {len(rows)} worksites · {meta['start']} → {meta['end']} · "
          f"threshold {meta['threshold_c']:.0f} °C\n")
    print("=== Worker-safety ranking (most exposed first) ===")
    for r in rows:
        print(f"  {r['rank']}. {r['site']:28s}  {r['alert']:9s}  "
              f"{r['pct_above']:5.1f}% of window >{meta['threshold_c']:.0f}°C  "
              f"({r['hours_above']} h total, {r['longest_run_h']} h run)")

    csv_path = OUTPUTS_DIR / "worksite_heat_screening.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"\nSaved CSV → {csv_path}")

    names = [r["site"].split(" — ")[0] for r in rows][::-1]
    pct = [r["pct_above"] for r in rows][::-1]
    colors = [BAND_COLOR[r["alert"]] for r in rows][::-1]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(names, pct, color=colors)
    ax.set_xlabel(f"% of last {meta['window_hours']//24} days above "
                  f"{meta['threshold_c']:.0f} °C")
    ax.set_xlim(0, 100)
    ax.set_title("Worksite heat exposure — real FortyGuard data")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "worksite_exposure.png")
    print(f"Saved chart → {REPORTS_DIR / 'worksite_exposure.png'}")


if __name__ == "__main__":
    main()
