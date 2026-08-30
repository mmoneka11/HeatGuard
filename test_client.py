"""Verify request payload + response parsing against the official API shapes (no network)."""
import heatguard.fortyguard_client as fg
fg.time.sleep = lambda s: None
from heatguard.fortyguard_client import FortyGuardClient
import screen_worksites as sw

class FakeResp:
    def __init__(self, p, code=200): self._p, self.status_code = p, code
    @property
    def ok(self): return self.status_code < 400
    def json(self): return self._p

cap = []

def client(result):
    c = FortyGuardClient(api_key="TESTKEY")
    n = {"i": 0}
    def post(url, json=None, timeout=None):
        cap.append((url, json))
        if "fetch-api-key-usage" in url:
            return FakeResp({"data": {"plan": "Basic", "credits_remaining": 1990000}})
        return FakeResp({"data": {"activity_id": "act_1"}})
    def get(url, timeout=None):
        n["i"] += 1
        if n["i"] == 1: return FakeResp({}, 404)                 # not-ready race
        if n["i"] == 2: return FakeResp({"data": {"status": "Processing"}})
        return FakeResp({"data": {"status": "Completed", "result": result}})
    c.session.post, c.session.get = post, get
    return c

# 1) no key -> hard error (never synthetic)
try:
    FortyGuardClient(api_key=None).worksite_exposure(33.4, -112.0, "2026-08-01", "2026-08-14")
    raise SystemExit("FAIL: should have required a key")
except fg.FortyGuardError as e:
    assert "real data only" in str(e)
    print("no-key path raises (no synthetic fallback)  ✓")

# 2) heatmap payload nests date_time (the 422 fix)
c = client({"stats_data": {"mean": 4.0}})
c.create_heatmap(c.point_aoi(33.4, -112.0), "2026-08-01", end_date="2026-08-14",
                 filter_type=4, analytic_type="exceedance", threshold=32.0, direction="above")
_, body = cap[-1]
assert body["date_time"]["filter_type"] == 4 and body["date_time"]["end_date"] == "2026-08-14"
assert "start_date" not in body and body["threshold"] == 32.0
print("heatmap payload nests date_time + threshold  ✓")

# 3) worksite_exposure end-to-end (exceedance then persistence)
seq = {"i": 0, "v": [4.0, 6.0]}
c = FortyGuardClient(api_key="K")
c.session.post = lambda url, json=None, timeout=None: FakeResp({"data": {"activity_id": "a"}})
c.session.get = lambda url, timeout=None: FakeResp(
    {"data": {"status": "Completed", "result": {"stats_data": {"mean": seq["v"][min(seq["i"], 1)]}}}})
_wf = c.wait_for
c.wait_for = lambda a, poll_interval=3.0, timeout=600: (lambda r: (seq.__setitem__("i", seq["i"]+1), r)[1])(_wf(a, poll_interval, timeout))
exp = c.worksite_exposure(33.4, -112.0, "2026-08-01", "2026-08-14", 32.0)
assert exp["hours_above"] == 4.0 and exp["longest_run_h"] == 6.0
print("worksite_exposure parsed:", {k: exp[k] for k in ("hours_above", "longest_run_h")}, " ✓")

# 4) alert banding
assert sw.safety_band(4.0, 6.0) == "Extreme"
assert sw.safety_band(4.0, 3.0) == "Warning"
assert sw.safety_band(2.0, 1.0) == "Caution"
assert sw.safety_band(0, 0) == "Safe"
print("safety_band mapping  ✓")
print("\nALL CHECKS PASSED ✓ — real-data-only, payload + display correct")
