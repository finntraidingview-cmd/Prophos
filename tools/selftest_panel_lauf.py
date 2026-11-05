#!/usr/bin/env python3
"""Selbsttest LAUFENDES PANEL + NUR EIN PANEL JE PC (Betrieb 1 03.11.2026 nach .2012: pc-l5o8bv fuhr seit 06:53 dt altes Panel, mt5_live meldete .2012;
pc-usq1i6 hatte zwei panel.py-Prozesse). Geprüft: Neustart-Check vergleicht mit dem Abbild BEIM LADEN (nicht mit der Datei), panel_lauf im Herzschlag,
Mutex + exklusiver Bind, Reihenfolge in main(). Ohne Netz. Aufruf: python3 tools/selftest_panel_lauf.py"""
import os
import re
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


tmp = tempfile.mkdtemp()
alt_code = b"# panel alt\r\ndef main():\n    pass\n" + b"x" * 100
open(os.path.join(tmp, "panel.py"), "wb").write(alt_code)
open(os.path.join(tmp, "provision.py"), "wb").write(b"# prov\n")
open(os.path.join(tmp, "VERSION"), "w").write("2026-09-22.2011\n")
import time as _time
import types
ns = {"os": os, "time": _time, "provision": types.SimpleNamespace(__file__=os.path.join(tmp, "provision.py")), "__file__": os.path.join(tmp, "panel.py"),
      "HERE": tmp, "PORT": 8770, "sys": sys}
i, j = SRC.index("def _code_glatt("), SRC.index("# Nur diese Felder darf das Panel schreiben.")
exec(SRC[i:j], ns)
check(ns["_GELADEN"]["version"] == "2026-09-22.2011" and ns["_GELADEN"]["panel"] == alt_code and ns["_GELADEN"]["datei"] == "panel.py", "Abbild beim Laden: Quelltext, Version, Datei")
# l5o8bv: Datei auf der Platte wird erneuert, der alte Code läuft weiter
neu_code = b"# panel NEU\ndef main():\n    pass\n" + b"y" * 100
open(os.path.join(tmp, "panel.py"), "wb").write(neu_code)
check(ns["panel_code_weicht_ab"](neu_code) is True, "pc-l5o8bv: Datei schon neu, laufender Code alt → weicht ab → Neustart (vorher: „unverändert“, nur VERSION nachgezogen)")
check(ns["panel_code_weicht_ab"](alt_code.replace(b"\r\n", b"\n")) is False, "gleicher Code (nur Zeilenenden anders) → kein Neustart")
check(ns["panel_code_weicht_ab"](None) is True, "neuer Stand nicht geholt → lieber Neustart")
check(ns["panel_code_weicht_ab"](b"x", "fehlt") is False and ns["panel_code_weicht_ab"](b"y", "fehlt") is False,
      "S9: kein Abbild (beim Laden nicht lesbar) → kein Neustart (keine Schleife), nur einmal Log")
# _panel_code_geaendert nutzt das Abbild
k = SRC.index("def _panel_code_geaendert(")
g = SRC[k:SRC.index("VERSION_NACHZIEHEN_S = 90", k)]
check("panel_code_weicht_ab(neu, name)" in g and "open(pfad" not in g and "__file__" not in g.split('"""')[2], "_panel_code_geaendert vergleicht mit dem Abbild, liest keine Datei")
ns["repo_datei"] = lambda pfad, sha, t=10: {"mt5-copier/panel.py": neu_code, "mt5-copier/provision.py": b"# prov\n"}[pfad]
exec(g, ns)
check(ns["_panel_code_geaendert"]("abc") is True, "Neustart-Check mit neuem Repo-Stand und erneuerter Datei → True")
ns["repo_datei"] = lambda pfad, sha, t=10: {"mt5-copier/panel.py": alt_code, "mt5-copier/provision.py": b"# prov\n"}[pfad]
check(ns["_panel_code_geaendert"]("abc") is False, "Repo-Stand = geladener Code → kein Neustart")
check('_GELADEN["version"] = remote' in SRC, "VERSION nachgezogen → panel_lauf.version zieht mit (Code nachweislich gleich)")
import json as _json
ns["json"] = _json
ns["read_json"] = lambda p, d=None: (_json.load(open(p)) if os.path.exists(p) else d)
ns["tages_neustart_info"] = lambda: None   # DR1 (05.11.2026): eigener Test tools/selftest_tages_neustart.py
info = ns["panel_lauf_info"]()
check(info["version"] == "2026-09-22.2011" and re.fullmatch(r"[0-9a-f]{12}", info["sha12"] or "") and info["pid"] == os.getpid()
      and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", info["start_at"]) and info["datei"] == "panel.py", f"panel_lauf_info: {info}")
check(re.fullmatch(r"[0-9a-f]{12}", info.get("provision_sha12") or "") and info.get("mutex_aufgaben") is None, "S9: provision_sha12 sichtbar, ohne Aufgaben kein Eintrag")
check('"panel_lauf": panel_lauf_info(),' in SRC and "panel_lauf: dd.panel_lauf || null," in HTML, "Herzschlag: /api/instances → Tab → mt5_live.status.panel_lauf")
# Nur ein Panel
check("CreateMutexW(None, False, f\"Local\\\\ProphosPanel{PORT}\")" in SRC and "== 183" in SRC, "benannter Mutex je Port, ERROR_ALREADY_EXISTS → zweites Panel")
m = SRC[SRC.index("\ndef main():"):SRC.index('if __name__ == "__main__":')]
check(m.index("_selbst_auffrischen()") < m.index("panel_einzel_instanz()") < m.index("threading.Thread("), "main(): Mutex nach dem Auffrischen (runpy), vor allen Threads")
check("ThreadingHTTPServer((\"127.0.0.1\", PORT), Handler).serve_forever()" in m and "_PanelServer" not in SRC and "setsockopt" not in SRC,
      "S9-Stopp: Bind wie bisher (kein SO_EXCLUSIVEADDRUSE — TIME_WAIT auf 8770 hätte den Neustart 2–4 min blockiert)")
ns2 = dict(ns)
exec(SRC[SRC.index("_EINZEL_MUTEX = []"):SRC.index("\ndef main():")], ns2)
check(ns2["panel_einzel_instanz"]() is True, "kein Windows → einziges Panel (wie bisher)")
ns2["mutex_aufgabe_merken"](1000.0); ns2["mutex_aufgabe_merken"](1070.0)
ma = ns["panel_lauf_info"]()["mutex_aufgaben"]
check(ma and ma["n"] == 2 and ma["erst_at"] == 1000.0 and ma["letzt_at"] == 1070.0 and ma["pid"] == os.getpid(), f"S9: Mutex-Aufgabe gezählt, im Herzschlag sichtbar ({ma})")
check(m.index("mutex_aufgabe_merken(time.time())") < m.index("time.sleep(60)"), "Aufgabe gemerkt, bevor das Fenster 60 s wartet")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
