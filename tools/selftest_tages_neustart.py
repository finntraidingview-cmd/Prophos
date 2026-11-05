#!/usr/bin/env python3
"""Selbsttest TÄGLICHER NEUSTART JE PC (DR1, Finn 05.11.2026): app.py pc_neustart_regel/_fenster/_unruhe/_sicht, panel.py
tages_neustart_entscheiden, copier.py neustart_wunsch_offen + Verdrahtung. Aufruf: python3 tools/selftest_tages_neustart.py"""
import ast
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
ok = True


def chk(bed, text):
    global ok
    print(("  OK   " if bed else "  FEHLER ") + text)
    ok = ok and bool(bed)


def funktionen(pfad, namen, ns):
    baum = ast.parse(open(pfad, encoding="utf-8").read())
    gefunden = set()
    for n in baum.body:
        if isinstance(n, ast.FunctionDef) and n.name in namen:
            exec(compile(ast.Module([n], []), pfad, "exec"), ns)
            gefunden.add(n.name)
    assert gefunden == set(namen), f"fehlt in {pfad}: {set(namen) - gefunden}"
    return ns


def _ap_tz(name):
    from zoneinfo import ZoneInfo
    return ZoneInfo(name)


def _ap_ts(roh):
    if not roh:
        return None
    try:
        return datetime.fromisoformat(str(roh).replace("Z", "+00:00"))
    except ValueError:
        return None


def _ap_hhmm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


app_pfad = os.path.join(WURZEL, "app.py")
app_src = open(app_pfad, encoding="utf-8").read()
std = {"an": False, "tz": "Asia/Dubai", "von": "02:30", "bis": "05:00", "nur_pcs": [], "ruhe_vor_start_min": 30,
       "teile": {"backend": True, "reader": True}}
ns = funktionen(app_pfad, {"pc_neustart_regel", "pc_neustart_fenster", "pc_neustart_unruhe", "pc_neustart_sicht"},
                {"PC_NEUSTART_STANDARD": std, "_ap_tz": _ap_tz, "_ap_ts": _ap_ts, "_ap_hhmm": _ap_hhmm, "re": re, "timedelta": timedelta})
regel, fenster, unruhe, sicht = ns["pc_neustart_regel"], ns["pc_neustart_fenster"], ns["pc_neustart_unruhe"], ns["pc_neustart_sicht"]

print("Regel")
chk(regel(None) == std, "fehlt → Standard (aus)")
chk(regel({"an": "true"})["an"] is False, "an nur mit echtem true")
r = regel({"an": True, "von": "25:00", "bis": "4:5", "tz": "Mars/Olymp", "nur_pcs": ["PC-ONKRBK", "x"], "ruhe_vor_start_min": 1})
chk(r["von"] == "02:30" and r["bis"] == "05:00" and r["tz"] == "Asia/Dubai", "ungültige Uhrzeit/Zone → Standard")
chk(r["nur_pcs"] == ["pc-onkrbk"] and r["ruhe_vor_start_min"] == 5, "nur_pcs normiert, Ruhe ≥ 5 min")
chk(regel({"an": True, "von": "03:00", "bis": "03:00"})["an"] is False, "leeres Fenster → aus")
chk(regel({"an": True, "nur_pcs": ["pc-x"]})["nur_pcs"] == ["-"], "nur Tippfehler in nur_pcs → kein PC (nie alle)")
chk(regel({"an": True, "nur_pcs": []})["nur_pcs"] == [], "leere Liste = alle PCs")
chk(regel({"an": True, "teile": {"reader": False}})["teile"] == {"backend": True, "reader": False}, "DR1b: Teil nur mit false aus")
chk(regel({"an": True, "teile": {"backend": 0, "reader": "nein"}})["teile"] == {"backend": True, "reader": True}, "DR1b: kein echtes false → bleibt an")
chk(regel({"an": True})["teile"] is not std["teile"], "DR1b: Standard-teile nie geteilt (Kopie)")

print("Fenster (Dubai = UTC+4)")
u = lambda h, m=0: datetime(2026, 11, 6, h, m, tzinfo=timezone.utc)
r = regel({"an": True})
chk(fenster(r, u(22, 29)) == ("2026-11-07", False, False), "02:29 Dubai (06.11. 22:29 UTC = 07.11. Dubai): noch zu")
t, o, v = fenster(r, datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc))
chk((t, o, v) == ("2026-11-07", True, False), f"02:30 Dubai am 07.11.: offen ({t},{o},{v})")
t, o, v = fenster(r, datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc))
chk((t, o, v) == ("2026-11-07", False, True), f"05:00 Dubai: vorbei ({t},{o},{v})")
t, o, v = fenster(r, datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc))
chk(o is False and v is False, "00:00 Dubai vor dem Fenster: weder offen noch vorbei")
rw = regel({"an": True, "von": "23:30", "bis": "02:00"})
t, o, v = fenster(rw, datetime(2026, 11, 6, 21, 0, tzinfo=timezone.utc))   # 01:00 Dubai 07.11. → Fenster vom 06.11.
chk((t, o, v) == ("2026-11-06", True, False), f"über Mitternacht: Tag des Fensterbeginns ({t},{o},{v})")
t, o, v = fenster(rw, datetime(2026, 11, 7, 2, 0, tzinfo=timezone.utc))   # 06:00 Dubai 07.11.: Fenster vom 06.11. vorbei
chk((t, o, v) == ("2026-11-06", False, True), f"über Mitternacht nach dem Ende: weiter Tag des Fensterbeginns, kein Fehlalarm ({t},{o},{v})")
t, o, v = fenster(rw, datetime(2026, 11, 7, 19, 45, tzinfo=timezone.utc))   # 23:45 Dubai 07.11.: neues Fenster
chk((t, o, v) == ("2026-11-07", True, False), f"über Mitternacht ab von: neuer Tag ({t},{o},{v})")

print("Ruhe")
j = datetime(2026, 11, 6, 23, 0, tzinfo=timezone.utc)
iso = lambda d: d.isoformat()
chk(unruhe([], [{"id": 1}], [], j, 30, "pc-a").startswith("Puls/Signal"), "laufendes Signal")
chk(unruhe([], [], [{"id": 1}], j, 30, "pc-a").startswith("Polar"), "Polar-Lauf")
chk(unruhe([{"status": "open"}], [], [], j, 30, "pc-a") == "Trade läuft (open)", "offener Plan")
chk(unruhe([{"status": "review", "hedge_status": "offen", "hedge_pc": "pc-a"}], [], [], j, 30, "pc-a") != "", "Überprüfen mit offenem Hedge hier")
chk(unruhe([{"status": "review", "hedge_status": "offen", "hedge_pc": "pc-b"}], [], [], j, 30, "pc-a") == "", "Hedge auf anderem PC zählt nicht")
chk(unruhe([{"status": "review", "hedge_status": "geschlossen"}], [], [], j, 30, "pc-a") == "", "Überprüfen mit zuem Hedge ist ruhig")
chk(unruhe([{"status": "planned", "start_um": iso(j + timedelta(minutes=25)), "auto_plan": False}], [], [], j, 30, "pc-a").startswith("Start in 25"),
    "Handplan in 25 min")
chk(unruhe([{"status": "planned", "start_um": iso(j + timedelta(minutes=25)), "auto_plan": True}], [], [], j, 30, "pc-a") == "",
    "unbestätigter Vorschlag startet nie → ruhig")
chk(unruhe([{"status": "planned", "start_um": iso(j + timedelta(minutes=25)), "auto_plan": True, "auto_bestaetigt_at": iso(j)}], [], [], j, 30,
           "pc-a") != "", "bestätigter Vorschlag in 25 min")
chk(unruhe([{"status": "planned", "start_um": iso(j + timedelta(minutes=45)), "auto_plan": False}], [], [], j, 30, "pc-a") == "", "Start in 45 min ist ruhig")
chk(unruhe([{"status": "planned", "start_um": iso(j - timedelta(minutes=40)), "auto_plan": False}], [], [], j, 30, "pc-a") != "",
    "Start vor 40 min, noch nicht geclaimt (Nachholen) → nicht ruhig")
chk(unruhe([{"status": "review", "hedge_status": "unklar"}], [], [], j, 30, "pc-a") != "", "Hedge unklar → nicht ruhig")
chk(unruhe([{"status": "planned", "start_um": iso(j - timedelta(minutes=5)), "start_um_gestartet_at": iso(j - timedelta(minutes=5))}], [], [], j, 30,
           "pc-a").startswith("Start geclaimt"), "frischer Claim")

print("Sicht")
nie = lambda m: (_ for _ in ()).throw(AssertionError("darf nicht laden"))
s = sicht(None, "pc-a", datetime(2026, 11, 6, 23, 0, tzinfo=timezone.utc), nie)
chk(s["an"] is False and s["ruhig"] is False, "Standard aus, keine Abfrage")
s = sicht({"an": True, "nur_pcs": ["pc-b"]}, "pc-a", datetime(2026, 11, 6, 23, 0, tzinfo=timezone.utc), nie)
chk(s["pc_frei"] is False, "anderer PC im Testlauf: keine Abfrage")
s = sicht({"an": True}, "pc-a", datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc), nie)
chk(s["offen"] is False, "außerhalb des Fensters: keine Abfrage")
s = sicht({"an": True}, "pc-a", datetime(2026, 11, 6, 23, 0, tzinfo=timezone.utc), lambda m: ([], [], []))
chk(s["ruhig"] is True and s["tag"] == "2026-11-07", "an + offen + ruhig")
s = sicht({"an": True}, "pc-a", datetime(2026, 11, 6, 23, 0, tzinfo=timezone.utc), lambda m: (_ for _ in ()).throw(RuntimeError("weg")))
chk(s["ruhig"] is False and "nicht prüfbar" in s["grund"], "Lesefehler → nicht ruhig (fail-closed)")
chk('"tages_neustart": tn' in app_src and "pc_neustart_sicht((_puls_heim_regel() or {}).get(\"pc_neustart\")" in app_src, "im Tab-Stand verdrahtet")

print("Panel")
p_pfad = os.path.join(WURZEL, "mt5-copier", "panel.py")
p_src = open(p_pfad, encoding="utf-8").read()
pn = funktionen(p_pfad, {"tages_neustart_entscheiden"}, {"TN_LEERLAUF_MIN_S": 120.0})
e = pn["tages_neustart_entscheiden"]
ok_s = {"an": True, "pc_frei": True, "tag": "2026-11-07", "offen": True, "vorbei": False, "ruhig": True, "grund": ""}
chk(e(None, None, 0, None, [], 999, "")[0] == "aus", "kein Feld → aus")
chk(e(dict(ok_s, an=False), None, 0, None, [], 999, "")[0] == "aus", "an false → aus")
chk(e(dict(ok_s, pc_frei=False), None, 0, None, [], 999, "")[0] == "aus", "PC nicht frei → aus")
chk(e(ok_s, "2026-11-07", 0, None, [], 999, "")[0] == "aus", "heute schon erledigt → aus")
chk(e(ok_s, None, 0, None, [], 999, "")[0] == "streuen", "erster ruhiger Moment → Streuung würfeln")
chk(e(ok_s, None, 100, 200, [], 999, "")[0] == "warten", "in der Streuung warten")
chk(e(ok_s, None, 300, 200, [], 999, "")[0] == "jetzt", "nach der Streuung → jetzt")
chk(e(ok_s, None, 300, 200, ["Polar-Lauf"], 999, "")[0] == "warten", "Panel belegt → warten")
chk(e(ok_s, None, 300, 200, [], 30, "")[0] == "warten", "jemand am PC → warten")
chk(e(dict(ok_s, ruhig=False, grund="Trade läuft"), None, 300, 200, [], 999, "")[0] == "warten", "Railway nicht ruhig → warten")
chk(e(dict(ok_s, offen=False, vorbei=True), None, 0, None, [], 999, "")[0] == "verpasst", "Fenster vorbei ohne Neustart → einmal melden")
chk(e(dict(ok_s, offen=False, vorbei=True), None, 0, None, [], 999, "2026-11-07")[0] == "aus", "… nur einmal je Tag")
chk(e(dict(ok_s, offen=False, vorbei=True), "2026-11-07", 0, None, [], 999, "")[0] == "aus", "erledigt + vorbei → nichts melden")
chk("threading.Thread(target=_tages_neustart_waechter" in p_src, "Wächter gestartet")
chk('"tages_neustart": tages_neustart_info()' in p_src, "Ergebnis in panel_lauf (→ mt5_live über den Tab)")
tn = p_src[p_src.index("def _tages_neustart_ausfuehren"):p_src.index("def _tages_neustart_nachher")]
chk(tn.index("_tn_frisch_ruhig") < tn.index("_panel_zu_und_leeren") and tn.index("_tn_schreiben(merk)") < tn.index("_panel_zu_und_leeren"),
    "frisch prüfen und Merker schreiben VOR dem ersten Schritt")
chk(tn.index("panel_beschaeftigt_gruende()") < tn.rindex("os._exit(0)") and "Polar" in tn, "letzte Belegt-Prüfung vor dem Exit, Polar nie abreißen")
chk('_tab_heil_melden(' in p_src and '"tages_neustart")' in p_src and 'art") or "") == "tages_neustart"' in app_src, "verpasst → eigene 🟠-Meldung (nicht Update-Spur)")
chk('"mt5_baseline->hedge->>pc": f"eq.{pc}"' in app_src and "start_um.is.null" in app_src, "Hedges dieses PCs und Handstarts ohne Startzeit geladen")
chk("_puls_chrome_beenden" in p_src and "_tab_oeffnen(TAB_URL, lock_gehalten=True)" in p_src, "bestehende Wege: Puls-Chrome zu, Tab wieder auf")
chk("terminal64" not in p_src[p_src.index("def _tages_neustart_ausfuehren"):p_src.index("def _tages_neustart_nachher")], "MT5-Terminals werden nicht angefasst")

print("DR1b: Backend + Reader")
pn2 = funktionen(p_pfad, {"netstat_lauscher", "tn_prozesse_parsen", "tn_port_ziel", "tn_spiegel_scharf"}, {"json": json, "re": re})
nl, pp, pz, sp = pn2["netstat_lauscher"], pn2["tn_prozesse_parsen"], pn2["tn_port_ziel"], pn2["tn_spiegel_scharf"]
NS = """
Aktive Verbindungen
  Proto  Lokale Adresse         Remoteadresse          Status           PID
  TCP    0.0.0.0:5000           0.0.0.0:0              ABHÖREN          4711
  TCP    127.0.0.1:8790         0.0.0.0:0              ABHÖREN          815
  TCP    127.0.0.1:50000        127.0.0.1:5000         HERGESTELLT      999
  TCP    127.0.0.1:15000        0.0.0.0:0              ABHÖREN          123
  TCP    [::]:5000              [::]:0                 LISTENING        4711
"""
chk(nl(NS, 5000) == [4711], "netstat: nur der Lauscher auf :5000 (nicht die Verbindung zu 5000, nicht :15000), Sprache egal")
chk(nl(NS, 8790) == [815], "netstat: Reader-Lauscher")
chk(nl("Müll\nTCP kaputt\n", 5000) == [] and nl("", 5000) == [] and nl(None, 5000) == [], "netstat kaputt/leer → keine PID")
chk(nl("  TCP    0.0.0.0:5000   0.0.0.0:0   LISTENING   abc", 5000) == [], "PID keine Zahl → nichts")
pr = pp(json.dumps([{"ProcessId": 4711, "Name": "python.exe", "CommandLine": "python  app.py"},
                    {"ProcessId": 815, "Name": "python.exe", "CommandLine": "C:\\Python312\\python.exe reader-server.py"}]))
chk(pz([4711], pr, "app.py") == (4711, ""), "python app.py → beenden")
chk(pz([815], pr, "reader-server.py") == (815, ""), "python reader-server.py → beenden")
chk(pz([], pr, "app.py")[0] is None, "Port frei → nichts")
chk(pz([4711, 815], pr, "app.py")[0] is None, "zwei Lauscher → nichts")
fremd = pp(json.dumps({"ProcessId": 4711, "Name": "node.exe", "CommandLine": "node app.py"}))
chk(pz([4711], fremd, "app.py")[0] is None, "fremdes Programm (node) auf :5000 → NIE beenden")
fremd2 = pp(json.dumps({"ProcessId": 4711, "Name": "python.exe", "CommandLine": "python -m http.server 5000"}))
chk(pz([4711], fremd2, "app.py")[0] is None, "python ohne app.py (anderes Skript) → nie beenden")
fremd3 = pp(json.dumps({"ProcessId": 4711, "Name": "python.exe", "CommandLine": "python myapp.py"}))
chk(pz([4711], fremd3, "app.py")[0] is None, "myapp.py ist nicht app.py → nie beenden")
chk(pz([4711], pp(json.dumps({"ProcessId": 4711, "Name": "python.exe", "CommandLine": "python C:\\Prophos\\mt5-copier\\app.py"})), "app.py")[0] == 4711,
    "voller Pfad …\\app.py → ja")
chk(pz([4711], {}, "app.py")[0] is None and pz([4711], pp("kaputt"), "app.py")[0] is None, "Befehlszeile unlesbar → nie beenden")
chk(pz([4711], pp(json.dumps({"ProcessId": 4711, "Name": "chrome.exe", "CommandLine": "chrome app.py"})), "app.py")[0] is None, "chrome → nie")
chk(pz([4711], pp(json.dumps({"ProcessId": 4711, "Name": "python3.12.exe", "CommandLine": "python3.12.exe app.py"})), "app.py")[0] == 4711,
    "Store-Python python3.12.exe → ja")
chk(pz([4711], pp(json.dumps({"ProcessId": 4711, "Name": "pythonx.exe", "CommandLine": "pythonx.exe app.py"})), "app.py")[0] is None, "pythonx.exe → nie")
chk(sp({}) == [] and sp({"a": {"active": False}}) == [], "Spiegel: keine aktive Sitzung → frei")
chk(sp({"a": {"active": True, "positions": {}}, "b": {"active": False}}) == ["a"], "Spiegel: jede aktive Sitzung sperrt (auch ohne Position)")
chk(sp(None) is None and sp([]) is None, "Spiegel unlesbar → None (kein Kill)")
tb = p_src[p_src.index("def _tn_teil_neu"):p_src.index("def _tages_neustart_ausfuehren")]
chk(tb.index("vorab()") < tb.index('"taskkill"') and "r.returncode != 0" in tb, "Spiegel-Schutz vor dem Kill, abgelehnter taskkill = übersprungen")
chk("_tn_spiegel_frei if name == \"backend\"" in p_src and '"/health")' in p_src, "Backend: Spiegel-Schutz + Rückkehr über /health")
chk('"taskkill", "/PID", str(int(pid)), "/F"]' in tb and '"/T"' not in tb, "taskkill /F OHNE /T (die .bat-Schleife lebt weiter)")
chk("tn_port_ziel(" in tb and tb.index("tn_port_ziel(") < tb.index("taskkill"), "erst prüfen, dann beenden")
ta = p_src[p_src.index("def _tages_neustart_ausfuehren"):p_src.index("def _tages_neustart_nachher")]
chk(ta.index("for name, port, skript, frist, pfad in TN_TEILE") < ta.index("_puls_chrome_beenden"), "Backend/Reader VOR dem Chrome-Schritt")
chk('name == "backend" and st in ("nicht_zurueck", "fehler")' in ta and "abbruch=" in ta and ta.index("abbruch=") < ta.index("_puls_chrome_beenden"),
    "Backend nicht zurück → Abbruch vor Chrome, im Merker vermerkt")
chk('teile.get(name) is False' in ta, "Unterschalter je Teil")
rb = ta[ta.index('if name == "reader" and st in ("nicht_zurueck", "fehler")'):]
chk("_tab_heil_melden(" in rb[:600] and "return" not in rb[:rb.index("flush=True)") + 12], "Reader nicht zurück → 🟠, aber kein Abbruch")
chk('("backend", 5000, "app.py", 120.0, "/health"), ("reader", 8790, "reader-server.py", 60.0, "/")' in p_src, "Fristen Backend 120 s, Reader 60 s")

print("Copier")
c_pfad = os.path.join(WURZEL, "mt5-copier", "copier.py")
c_src = open(c_pfad, encoding="utf-8").read()


def load_json(pfad):
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


cn = funktionen(c_pfad, {"neustart_wunsch_offen"}, {"load_json": load_json, "json": json, "NEUSTART_WUNSCH_S": 900})
w = cn["neustart_wunsch_offen"]
with tempfile.TemporaryDirectory() as d:
    pf = os.path.join(d, "copier_neustart.json")
    chk(w(pf, 1000.0) is False, "kein Wunsch → nein")
    json.dump({"at": 1000.0}, open(pf, "w"))
    chk(w(pf, 1100.0) is True, "frischer Wunsch → ja")
    chk(w(pf, 1000.0 + 900) is False, "nach 15 min verfallen")
    chk(w(pf, 900.0) is False, "Zukunft → nein")
    open(pf, "w").write("kaputt")
    chk(w(pf, 1100.0) is False, "kaputt → nein")
blk = c_src[c_src.index("TÄGLICHER NEUSTART (DR1"):c_src.index("Neue/geloeschte config*.json")]
chk("_weg = False" in blk and "if _weg:" in blk, "Wunsch nicht löschbar → kein Neustart")
chk('getattr(m, "busy", True)' in blk and "hedge_bereit_rest" in blk and "break" in blk, "nur flach + ohne bevorstehenden Start, Weg wie Selbst-Update")

print("\nALLES OK" if ok else "\nFEHLER")
sys.exit(0 if ok else 1)
