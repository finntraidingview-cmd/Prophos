import os, sys, time
os.environ["WATCHER_DISABLED"] = "1"
sys.path.insert(0, "/Applications/Prophos"); os.chdir("/Applications/Prophos")
import app as A
A.TSX_BASE = "http://127.0.0.1:18801"; A.MA_BASE = "http://127.0.0.1:18801"; A.RTC_BASE = "http://127.0.0.1:18765"
c = A.app.test_client()
t0 = time.time()
r = c.post("/mirror/start", json={"pairId": "sim", "tsxToken": "tok", "tsxAccountId": "27613403", "maToken": "ma", "maAccountId": "ACC",
    "multiplier": 0.0194, "direction": "tsx_to_mt", "engine": "realtime", "oneShot": (os.environ.get("ONESHOT") == "1"), "baseInstrument": "MNQ", "symbolMap": {"MNQ": "NAS100", "NQ": "NAS100", "ENQ": "NAS100"}})
print("start:", r.get_json(), flush=True)
seen = 0; dauer = int(sys.argv[1]) if len(sys.argv) > 1 else 45
while time.time() - t0 < dauer:
    s = A.mirror_sessions.get("sim")
    if s:
        log = s["log"]
        for e in log[seen:]:
            m = e["msg"]
            if "SignalR:" in m or "Stream-Reconnect" in m or "Verbunden & abonniert" in m: continue   # Sturm-Rauschen ausblenden
            print(f"[{time.time()-t0:5.1f}s] {m[:200]}", flush=True)
        seen = len(log)
    time.sleep(0.25)
s = A.mirror_sessions.get("sim")
print("ENDE positions:", s and s.get("positions"), "closedHedges:", s and s.get("closedHedges"), "log-Zeilen:", s and len(s["log"]), flush=True)
c.post("/mirror/stop", json={"pairId": "sim"})
