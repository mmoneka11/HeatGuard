"""Configuration for the real-data HeatGuard screener."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
OUTPUTS_DIR = ROOT / "outputs"
REPORTS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

# Heat-caution threshold for outdoor crews (°C). 32 °C ≈ 90 °F, aligned with
# NWS HeatRisk / OSHA-NIOSH caution guidance for sustained outdoor exposure.
THRESHOLD_C = 32.0
WINDOW_DAYS = 14        # trailing window to screen exposure over

# Real U.S. worksites to screen (name, lat, lon) — all within U.S. coverage.
# Edit / extend freely; each site costs ~2 successful API calls.
WORKSITES = [
    ("Phoenix, AZ — downtown",        33.4484, -112.0740),
    ("Las Vegas, NV — strip",         36.1147, -115.1728),
    ("Dallas, TX — downtown",         32.7767, -96.7970),
    ("Houston, TX — ship channel",    29.7355, -95.2860),
    ("Sacramento, CA — downtown",     38.5816, -121.4944),
    ("Miami, FL — downtown",          25.7617, -80.1918),
]
