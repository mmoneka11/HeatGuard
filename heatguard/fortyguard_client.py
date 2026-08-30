"""FortyGuard Temperature API client — payloads matched to the official Quickstart.

Endpoints (base https://api.fortyguard.com):
  POST /v1/heatmap     analytic_type = tcm | time_of_measure | exceedance | persistence
  POST /v1/env_params  heat index / apparent temp / AQI at a point
  GET  /v1/status/{id} poll async task (may 404 briefly right after submit)
  POST /v1/system/fetch-api-key-usage   credit summary

Request shape (the important part): date fields go INSIDE a nested `date_time`
object; the async submit returns data.activity_id; status/result live under
`data`. Auth header is `api-key`. Coverage U.S.-only; dates 2021-01-01..today.
A key is required — the client never falls back to synthetic data.
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests


BASE_URL = "https://api.fortyguard.com"
DONE = {"succeeded", "completed", "success", "done"}
FAILED = {"failed", "error", "cancelled"}


class FortyGuardError(RuntimeError):
    pass


class FortyGuardClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 timeout: float = 60.0):
        self.api_key = api_key or os.getenv("FORTYGUARD_API_KEY")
        raw = (base_url or os.getenv("FORTYGUARD_BASE_URL") or BASE_URL).strip().rstrip("/")
        if not raw.startswith("http"):
            raw = "https://" + raw
        if "dashboard.fortyguard.com" in raw:          # web app, not the API (405s)
            raw = raw.replace("dashboard.fortyguard.com", "api.fortyguard.com")
        if raw.endswith("/v1"):                         # paths already include /v1
            raw = raw[:-3]
        self.base_url = raw
        self.timeout = timeout
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"api-key": self.api_key,
                                         "Content-Type": "application/json"})

    @property
    def live(self) -> bool:
        return bool(self.api_key)

    # -- async plumbing (matches the official client's response shapes) -------
    def _submit(self, path: str, payload: dict[str, Any]) -> str:
        r = self.session.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        if not r.ok:
            raise FortyGuardError(f"POST {path} -> {r.status_code}: {r.text[:400]}")
        body = r.json()
        if body.get("error"):
            raise FortyGuardError(body.get("message", "Submission failed"))
        try:
            return body["data"]["activity_id"]
        except (KeyError, TypeError):
            aid = body.get("activity_id")
            if aid:
                return aid
            raise FortyGuardError(f"Unexpected submit response: {body}")

    def get_status(self, activity_id: str) -> dict[str, Any] | None:
        r = self.session.get(f"{self.base_url}/v1/status/{activity_id}", timeout=self.timeout)
        if r.status_code == 404:
            return None                                 # not queryable yet — keep polling
        if not r.ok:
            raise FortyGuardError(f"GET /v1/status/{activity_id} -> {r.status_code}: {r.text[:400]}")
        body = r.json()
        if body.get("error"):
            raise FortyGuardError(body.get("message", "Status lookup failed"))
        return body.get("data", body)

    def wait_for(self, activity_id: str, poll_interval: float = 3.0,
                 timeout: float = 600.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            data = self.get_status(activity_id)
            if data is not None:
                status = str(data.get("status", "")).lower()
                if status in DONE:
                    return data.get("result", data)
                if status in FAILED:
                    raise FortyGuardError(f"Task {activity_id} failed: {data.get('message') or data}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Polling timed out for {activity_id}")
            time.sleep(poll_interval)

    def _submit_and_wait(self, path, payload, wait=True, timeout=600):
        activity_id = self._submit(path, payload)
        if not wait:
            return {"activity_id": activity_id, "result": None}
        return {"activity_id": activity_id, "result": self.wait_for(activity_id, timeout=timeout)}

    # -- geometry helper -----------------------------------------------------
    @staticmethod
    def point_aoi(lat: float, lon: float, half_deg: float = 0.006) -> dict[str, Any]:
        ring = [
            [lon - half_deg, lat - half_deg], [lon + half_deg, lat - half_deg],
            [lon + half_deg, lat + half_deg], [lon - half_deg, lat + half_deg],
            [lon - half_deg, lat - half_deg],
        ]
        return {"type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}]}

    # -- endpoints -----------------------------------------------------------
    def create_heatmap(self, polygon_aoi, start_date, filter_type=1, granularity=100,
                       start_time=None, end_time=None, end_date=None,
                       analytic_type="tcm", threshold=None, direction=None,
                       wait=True, timeout=600):
        if analytic_type in ("exceedance", "persistence"):
            if threshold is None or direction not in ("above", "below"):
                raise ValueError(f"{analytic_type} needs threshold (°C) and direction above/below")
        date_time: dict[str, Any] = {"start_date": start_date, "filter_type": filter_type}
        if start_time is not None:
            date_time["start_time"] = start_time
        if end_time is not None:
            date_time["end_time"] = end_time
        if end_date is not None:
            date_time["end_date"] = end_date
        payload: dict[str, Any] = {
            "polygon_aoi": polygon_aoi, "date_time": date_time,
            "granularity": granularity, "analytic_type": analytic_type,
        }
        if threshold is not None:
            payload["threshold"] = threshold
        if direction is not None:
            payload["direction"] = direction
        return self._submit_and_wait("/v1/heatmap", payload, wait, timeout)

    def environmental_parameters(self, latitude, longitude, start_date, filter_type=3,
                                 start_time=None, end_date=None, analysis=None,
                                 wait=True, timeout=600):
        date_time: dict[str, Any] = {"start_date": start_date, "filter_type": filter_type}
        if start_time is not None:
            date_time["start_time"] = start_time
        if end_date is not None:
            date_time["end_date"] = end_date
        payload: dict[str, Any] = {"latitude": latitude, "longitude": longitude,
                                   "date_time": date_time}
        if analysis is not None:
            payload["analysis"] = list(analysis)
        return self._submit_and_wait("/v1/env_params", payload, wait, timeout)

    def fetch_api_key_usage(self):
        r = self.session.post(f"{self.base_url}/v1/system/fetch-api-key-usage",
                              json={"api_key": self.api_key}, timeout=self.timeout)
        if not r.ok:
            raise FortyGuardError(f"usage -> {r.status_code}: {r.text[:300]}")
        body = r.json()
        return body.get("data", body)

    # -- worker-safety features (API-native, credit-cheap) -------------------
    @staticmethod
    def _stats_mean(result: dict[str, Any]) -> float | None:
        s = (result or {}).get("stats_data", {})
        if "mean" in s:
            return float(s["mean"])
        ts = s.get("temperature_stats", {})
        for k in ("mean", "average", "avg"):
            if k in ts:
                return float(ts[k])
        return None

    def worksite_exposure(self, lat, lon, start_date, end_date, threshold_c=32.0):
        """Worker-safety heat features for one U.S. site over a date range.

        Two analysis heatmaps (exceedance + persistence) — ~2 successful calls
        per site. Returns hours-above-threshold and longest continuous run (h).
        """
        if not self.live:
            raise FortyGuardError("A FORTYGUARD_API_KEY is required — this tool uses real data only.")
        aoi = self.point_aoi(lat, lon)
        exc = self.create_heatmap(aoi, start_date, end_date=end_date, filter_type=4,
                                  analytic_type="exceedance", threshold=threshold_c,
                                  direction="above")["result"]
        per = self.create_heatmap(aoi, start_date, end_date=end_date, filter_type=4,
                                  analytic_type="persistence", threshold=threshold_c,
                                  direction="above")["result"]
        return {"lat": lat, "lon": lon, "start_date": start_date, "end_date": end_date,
                "threshold_c": threshold_c,
                "hours_above": self._stats_mean(exc),
                "longest_run_h": self._stats_mean(per)}

