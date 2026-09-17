import os, sys, time
os.environ["WATCHER_DISABLED"] = "1"
os.environ["PROPHOS_SIDECAR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim-sidecar.json")
sys.path.insert(0, "/Applications/Prophos"); os.chdir("/Applications/Prophos")
import app as A
A.TSX_BASE = "http://127.0.0.1:18801"; A.MA_BASE = "http://127.0.0.1:18801"; A.RTC_BASE = "http://127.0.0.1:18765"
modus = sys.argv[2] if len(sys.argv) > 2 else "start"
t0 = time.time()
if modus == "start":
    r = A.app.test_client().post("/mirror/start", json={"pairId": "sim", "tsxToken": "tok", "tsxAccountId": "27613403", "maToken": "ma", "maAccountId": "ACC",
        "multiplier": 0.0194, "direction": "tsx_to_mt", "engine": "realtime", "oneShot": True, "sltpSync": True, "notfallFaktor": 110, "notfallPufferPunkte": 100,
        "baseInstrument": "MNQ", "symbolMap": {"MNQ": "NAS100"}})
    print("start:", r.get_json(), flush=True)
else:
    print("RESUME-Modus: kein /mirror/start — die Session muss aus der Sidecar-Datei kommen", flush=True)
seen = 0; dauer = int(sys.argv[1])
while time.time() - t0 < dauer:
    s = A.mirror_sessions.get("sim")
    if s:
        for e in s["log"][seen:]:
            m = e["msg"]
            if any(x in m for x in ("SignalR:", "Stream-Reconnect", "Verbunden & abonniert", "Ohne Server-Best", "Verbindungsmodus", "Baseline-Sync", "Stream-Verbindung wird", "Stream-Aufbau")): continue
            print(f"[{time.time()-t0:5.1f}s] {m[:230]}", flush=True)
        seen = len(s["log"])
    time.sleep(0.25)
s = A.mirror_sessions.get("sim")
print("ENDE positions:", s and s.get("positions"), "| refState:", s and s.get("refState"), "| opensBlocked:", s and s.get("opensBlocked"), flush=True)
if modus != "kill": pass
os._exit(0)   # harter Abbruch wie beim Selbst-Update — KEIN /mirror/stop, die Sidecar bleibt stehen
