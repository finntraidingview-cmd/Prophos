#!/usr/bin/env python3
"""Selbsttest Mini-Backend (PS1, 25.11.2026) — ohne Netz, ohne Windows.

Aufruf:  python3 tools/selftest_pc_backend.py
Prüft mt5-copier/pc_backend.py (Routen, Riegel, Durchreichen, Update-Entscheid) und die Server-Seite in app.py
(mini_backend_fuer, code_pfad_fuer). Wo pc_backend.py Logik aus app.py übernommen hat (Zeitlimits der Panel-Brücke,
local_update_entscheiden), wird gegen das Original aus app.py verglichen — driften die beiden auseinander, wird es rot."""
import itertools
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
APP_SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()

import pc_backend as pb      # noqa: E402

ok = True


def check(bed, text):
    global ok
    print(("✓ " if bed else "✗ ") + text)
    ok = ok and bool(bed)


def app_stueck(start, ende):
    i = APP_SRC.index(start)
    return APP_SRC[i:APP_SRC.index(ende, i)]


class Antwort:
    def __init__(self, status=200, content=b"{}", headers=None, text=None):
        self.status_code, self.content, self.headers = status, content, headers or {"Content-Type": "application/json"}
        self.text = text if text is not None else content.decode("utf-8", "replace")
        self.ok = status < 400

    def json(self):
        import json
        return json.loads(self.content)


# ── 1) Server-Seite: wer bekommt das Mini-Backend, welche Datei ──
ns = {}
exec(app_stueck("MINI_BACKEND_TAUSCH = ", "@app.route(\"/code/backend-wahl\""), ns)
mini, pfad_fuer = ns["mini_backend_fuer"], ns["code_pfad_fuer"]
UID, PC = "0f1e2d3c-1111-2222-3333-444455556666", "pc-aaron1"
check(mini((UID, PC), "") is False and mini((UID, PC), None) is False, "leere Liste → niemand ist Mini (alle PCs wie bisher)")
check(mini((UID, PC), "pc-aaron1"), "pc-Kennung in der Liste → Mini")
check(mini((UID, PC), " PC-AARON1 , pc-x "), "Liste mit Leerzeichen/Großschreibung")
check(mini((UID, "pc-anders"), UID), "user_id in der Liste → Mini, egal welche pc-Kennung")
check(not mini((UID, PC), "pc-aaron"), "Teil-Treffer zählt nicht")
check(not mini(None, "pc-aaron1"), "ohne Schlüssel nie Mini")
for p in ("app.py", "prophos.html", "mt5-copier/start-prophos.bat", "mt5-copier/panel.py", "tv-reader/reader-server.py"):
    check(pfad_fuer(p, False) == p, f"nicht in der Liste: {p} unverändert")
check(pfad_fuer("app.py", True) is None, "Mini-PC: app.py gesperrt")
check(pfad_fuer("mt5-copier/start-prophos.bat", True) == "mt5-copier/start-prophos-mini.bat", "Mini-PC: Starter getauscht")
check(pfad_fuer("prophos.html", True) == "prophos.html" and pfad_fuer("mt5-copier/panel.py", True) == "mt5-copier/panel.py",
      "Mini-PC: Oberfläche und Ausführungs-Dateien bleiben")
ns2 = {"re": __import__("re"), "os": os}
exec(app_stueck("_CODE_NAME = ", "_CODE_WURZEL = "), ns2)
muster = ns2["CODE_PFAD_MUSTER"]
check(all(muster.fullmatch(p) for p in ("mt5-copier/pc_backend.py", "mt5-copier/start-prophos-mini.bat")),
      "neue Dateien sind über /code/datei abrufbar")
check(all(os.path.isfile(os.path.join(WURZEL, *p.split("/"))) for p in ("mt5-copier/pc_backend.py", "mt5-copier/start-prophos-mini.bat")),
      "neue Dateien liegen im Repo")

# ── 2) Übernommene Logik gegen das Original in app.py ──
tmo_src = app_stueck("        _tmo = (", "        # vorflug (F-A")
tmo_ausdruck = tmo_src.split("=", 1)[1]
tmo_ausdruck = "\n".join(z.split("#")[0] for z in tmo_ausdruck.splitlines())
pfade = ["master-order", "master-close", "tv-order", "tv-lesen", "tv-close", "tsx-konto", "tsx-lesen", "tsx-inventar", "tsx-close",
         "tv-konten-liste", "tv-konto", "hedge-solo", "tv-neuladen", "tv-tm-update", "vorflug", "instances", "pc-id", "code-token",
         "beschaeftigt", "polar-start", "puls-klick", "irgendwas"]
check(all(pb.copier_zeitlimit(p) == eval(tmo_ausdruck, {"path": p}) for p in pfade), "Zeitlimits der Panel-Brücke = app.py (22 Pfade)")
ns3 = {}
exec(app_stueck("LOCAL_UPDATE_DECKEL_S = ", "def _local_panel_gruende"), ns3)
orig = ns3["local_update_entscheiden"]
gleich = True
for n, gr, seit, jetzt, streu in itertools.product((0, 1, 3), (None, [], ["Order läuft"]), (None, 0.0, 500.0), (10.0, 1000.0, 5000.0),
                                                   (0.0, 20.0, 2000.0)):
    gleich = gleich and pb.local_update_entscheiden(n, gr, seit, jetzt, streu) == orig(n, gr, seit, jetzt, streu)
check(gleich, "local_update_entscheiden = app.py (243 Fälle)")
check(pb.LOCAL_UPDATE_DECKEL_S == ns3["LOCAL_UPDATE_DECKEL_S"] and pb.LOCAL_UPDATE_LEERLAUF_S == ns3["LOCAL_UPDATE_LEERLAUF_S"],
      "Update-Deckel und Leerlauf = app.py")

# ── 3) Rein rechnende Helfer ──
check(pb.seite_gueltig(b"x" * 60000 + b"OS_TAB_BUILD") and not pb.seite_gueltig(b"<html>Login</html>")
      and not pb.seite_gueltig(b"x" * 60000) and not pb.seite_gueltig(None), "seite_gueltig: nur die echte Oberfläche")
check(pb.code_gleich(b"\xef\xbb\xbfa\r\nb\r\n", b"a\nb") and not pb.code_gleich(b"a\nb", b"a\nc"), "code_gleich: Zeilenenden/BOM egal")
wk = pb.weiter_kopf([("Host", "localhost:5000"), ("Authorization", "Bearer x"), ("sb-token", "t"), ("Content-Length", "5"),
                     ("Accept-Encoding", "gzip"), ("Content-Type", "application/json")])
check(wk == {"Authorization": "Bearer x", "sb-token": "t", "Content-Type": "application/json"}, "weiter_kopf: Anmeldung geht mit, Host/Länge nicht")
zk = dict(pb.zurueck_kopf([("Content-Type", "application/json"), ("Content-Encoding", "gzip"), ("Content-Length", "9"),
                           ("Access-Control-Allow-Origin", "x")]))
check(zk == {"Content-Type": "application/json"}, "zurueck_kopf: keine doppelte Kodierung/CORS")

# ── 4) Routen über den Flask-Testclient, Netz ersetzt ──
rufe = []


def falsches_netz(methode, url, **kw):
    rufe.append((methode, url, kw))
    return Antwort(200, b'{"ok":true,"von":"netz"}')


pb.requests.request = falsches_netz
c = pb.app.test_client()

rufe.clear()
r = c.get("/copier/pc-id")
check(r.status_code == 200 and rufe and rufe[0][1] == "http://127.0.0.1:8770/api/pc-id" and rufe[0][2]["timeout"] == 25,
      "/copier/pc-id → Panel auf diesem PC, 25 s")
rufe.clear()
r = c.post("/copier/master-order?file=a.json", json={"volumen": 1}, headers={"Origin": "http://localhost:5000"})
k = rufe[0][2] if rufe else {}
check(rufe and rufe[0][1].endswith("/api/master-order") and k["timeout"] == 310 and k["json"] == {"volumen": 1}
      and k["headers"].get("Origin") == "http://localhost:5000" and k["params"].get("file") == "a.json",
      "/copier/master-order: Inhalt, Origin, Parameter, 310 s")
rufe.clear()
r = c.get("/copier/pc-id", environ_base={"REMOTE_ADDR": "192.168.1.50"})
check(r.status_code == 403 and not rufe, "Panel-Brücke: LAN-Gerät abgewiesen, nichts gesendet")
pb._PROXY["zu"] = True
rufe.clear()
r = c.post("/copier/tv-order", json={})
j = r.get_json()
check(r.status_code == 503 and j.get("_nichtGesendet") and j.get("retry_ok") and not rufe and pb._PROXY["n"] == 0,
      "Brücke zu (Update): 503 „nichts gesendet“, Zähler bleibt 0")
pb._PROXY["zu"] = False
c.get("/copier/instances")
check(pb._PROXY["n"] == 0, "Zähler nach normalem Aufruf wieder 0")

rufe.clear()
r = c.post("/api/Account/search?x=1", data=b'{"a":1}', headers={"Authorization": "Bearer tok", "Content-Type": "application/json"})
k = rufe[0][2] if rufe else {}
check(r.status_code == 200 and rufe and rufe[0][0] == "POST" and rufe[0][1] == pb.CODE_QUELLE + "/api/Account/search"
      and k["data"] == b'{"a":1}' and k["headers"].get("Authorization") == "Bearer tok" and k["params"].get("x") == "1"
      and "Host" not in k["headers"], "/api/… → Railway: Methode, Inhalt, Anmeldung, Parameter")
rufe.clear()
c.get("/push/vapid-public")
c.get("/news/calendar")
c.get("/advisor/firms")
check([x[1] for x in rufe] == [pb.CODE_QUELLE + p for p in ("/push/vapid-public", "/news/calendar", "/advisor/firms")],
      "/push, /news, /advisor → Railway")
rufe.clear()
r = c.get("/api/x", environ_base={"REMOTE_ADDR": "10.0.0.7"})
check(r.status_code == 403 and not rufe, "Durchreichen: LAN-Gerät abgewiesen")
r = c.open("/api/x", method="OPTIONS")
check(r.status_code == 200 and "PATCH" in r.headers.get("Access-Control-Allow-Methods", "") and "sb-token" in
      r.headers.get("Access-Control-Allow-Headers", ""), "Preflight: CORS wie app.py")


def kaputt(*a, **kw):
    raise pb.requests.exceptions.ConnectionError("weg")


# Alte Mirror-Engine: Start wird NICHT nach Railway gereicht (sonst nach dem Not-Schalter zwei Engines = doppelte Hedges)
check(pb.nicht_durchreichen("POST", "mirror/start") and pb.nicht_durchreichen("post", "/Mirror/Start/")
      and not pb.nicht_durchreichen("GET", "mirror/status") and not pb.nicht_durchreichen("POST", "mirror/stop")
      and not pb.nicht_durchreichen("POST", "api/Account/search"), "nicht_durchreichen: nur POST /mirror/start")
rufe.clear()
r = c.post("/mirror/start", json={"pairId": "x"})
check(r.status_code == 409 and r.get_json().get("code") == "mini_backend" and not rufe, "POST /mirror/start → 409, nichts gesendet")
rufe.clear()
c.post("/mirror/stop", json={"pairId": "x"})
check(len(rufe) == 1 and rufe[0][1] == pb.CODE_QUELLE + "/mirror/stop", "POST /mirror/stop geht weiter durch")

pb.requests.request = kaputt
r = c.get("/api/x")
check(r.status_code == 502 and r.get_json().get("ok") is False and r.get_json().get("_nichtGesendet") is True,
      "Railway nicht erreichbar → 502 „nichts gesendet“")


def haengt(*a, **kw):
    raise pb.requests.exceptions.ReadTimeout("keine Antwort")


pb.requests.request = haengt
r = c.post("/push/send", json={})
check(r.status_code == 504 and r.get_json().get("unklar") is True and not r.get_json().get("_nichtGesendet"),
      "Antwort bleibt aus → 504 „unklar“ (nie als „nichts gesendet“ gemeldet)")
pb.requests.request = kaputt
r = c.get("/copier/instances")
check(r.status_code == 502 and r.get_json().get("copier_offline") is True, "Panel weg → 502 copier_offline (wie app.py)")

# Oberfläche: Railway → Speicher → Warteseite; nie von der Platte
SEITE = b"<html>" + b"x" * 60000 + b"OS_TAB_BUILD</html>"
holen = {"antwort": None, "pfade": []}


def falsch_holen(pfad_url, timeout=10):
    holen["pfade"].append(pfad_url)
    return holen["antwort"]


pb._code_holen = falsch_holen
pb._code_token_lokal = lambda: None
pb._seite["html"] = None
r = c.get("/")
check(r.status_code == 200 and b"http-equiv=\"refresh\"" in r.data and "PC-Schlüssel".encode() in r.data,
      "/ ohne Schlüssel und ohne Speicher → Warteseite mit Selbst-Neuladen")
holen["antwort"] = Antwort(200, SEITE)
r = c.get("/")
check(r.data == SEITE and holen["pfade"][-1] == "/code/datei/prophos.html", "/ → Oberfläche von Railway")
holen["antwort"] = Antwort(200, b"<html>Login</html>")
r = c.get("/")
check(r.data == SEITE, "Railway liefert Unsinn → letzte gute Fassung aus dem Speicher")
holen["antwort"] = None
r = c.get("/")
check(r.data == SEITE, "Railway weg → letzte gute Fassung aus dem Speicher")
check(not os.path.exists(os.path.join(os.path.dirname(pb.__file__), "prophos.html")), "keine prophos.html neben pc_backend.py")

pb._frontend_ver.update(at=0.0, wert=None)
holen["antwort"] = Antwort(200, b'{"ok":true,"sha":"' + b"a" * 40 + b'","version":"2026-11-25.4711"}')
r = c.get("/mt5-copier/VERSION")
check(r.status_code == 200 and r.data == b"2026-11-25.4711" and r.headers.get("Cache-Control") == "no-store", "/mt5-copier/VERSION von Railway")
holen["antwort"] = Antwort(200, b"self.addEventListener('push',()=>{})")
r = c.get("/sw.js")
check(r.status_code == 200 and b"addEventListener" in r.data and "javascript" in r.headers.get("Content-Type", ""), "/sw.js von Railway")
holen["antwort"] = None
r = c.get("/sw.js")
check(r.status_code == 200 and r.data.startswith(b"//"), "/sw.js ohne Railway → leerer Worker statt 404")

r = c.post("/local/restart-stack", environ_base={"REMOTE_ADDR": "192.168.1.9"})
check(r.status_code == 403, "Stack-Neustart: LAN-Gerät abgewiesen")
if os.name != "nt":
    r = c.post("/local/restart-stack")
    check(r.status_code == 403, "Stack-Neustart: nur auf Windows")

# Not-Schalter: nur eine klare Antwort zählt
holen["antwort"] = Antwort(200, b'{"ok":true,"backend":"alt"}')
check(pb._local_backend_wahl() == "alt", "backend-wahl: „alt“ erkannt")
holen["antwort"] = Antwort(200, b'{"ok":true,"backend":"mini"}')
check(pb._local_backend_wahl() == "mini", "backend-wahl: „mini“ erkannt")
for unsinn in (None, Antwort(200, b"<html>"), Antwort(200, b'{"backend":"sonstwas"}'), Antwort(200, b"{}")):
    holen["antwort"] = unsinn
    check(pb._local_backend_wahl() is None, "backend-wahl: unklare Antwort ändert nichts")

# ── 5) Starter: der alte bleibt unberührt, der neue startet nie app.py ──
alt = open(os.path.join(WURZEL, "mt5-copier", "start-prophos.bat"), encoding="utf-8", errors="replace").read()
neu = open(os.path.join(WURZEL, "mt5-copier", "start-prophos-mini.bat"), encoding="utf-8", errors="replace").read()
check("python app.py" in alt and "pc_backend" not in alt, "start-prophos.bat (alle bestehenden PCs) unverändert: startet app.py")
check("python pc_backend.py" in neu and "\npython app.py" not in neu and "datei/app.py" not in neu and "github" not in neu.lower(),
      "start-prophos-mini.bat: startet pc_backend.py, holt nie app.py, kein GitHub")
check(len(neu.encode()) >= 500 and all(ord(z) < 128 for z in neu), "Mini-Starter: groß genug für den Tausch (≥ 500 B), reines ASCII")
# Not-Schalter: der geholte Starter wird verworfen, wenn er „pc_backend“ enthält (= noch die Mini-Datei). Der alte besteht, der neue nicht.
check('findstr /c:"pc_backend" start-prophos-alt.bat' in neu and "if not errorlevel 1" in neu, "Not-Schalter prüft den geholten Starter auf pc_backend")
check("pc_backend" in neu and "pc_backend" not in alt, "Echtheitsprüfung trennt wirklich: Mini-Starter fällt durch, alter Starter besteht")

print()
print("ALLES GRÜN" if ok else "FEHLER")
sys.exit(0 if ok else 1)
