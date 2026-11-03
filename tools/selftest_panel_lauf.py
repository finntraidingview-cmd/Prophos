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
check(ns["panel_code_weicht_ab"](None) is True and ns["panel_code_weicht_ab"](b"x", "fehlt") is True, "kein Abbild / kein Abruf → lieber Neustart")
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
info = ns["panel_lauf_info"]()
check(info["version"] == "2026-09-22.2011" and re.fullmatch(r"[0-9a-f]{12}", info["sha12"] or "") and info["pid"] == os.getpid()
      and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", info["start_at"]) and info["datei"] == "panel.py", f"panel_lauf_info: {info}")
check('"panel_lauf": panel_lauf_info(),' in SRC and "panel_lauf: dd.panel_lauf || null," in HTML, "Herzschlag: /api/instances → Tab → mt5_live.status.panel_lauf")
# Nur ein Panel
check("CreateMutexW(None, False, f\"Local\\\\ProphosPanel{PORT}\")" in SRC and "== 183" in SRC, "benannter Mutex je Port, ERROR_ALREADY_EXISTS → zweites Panel")
m = SRC[SRC.index("\ndef main():"):SRC.index('if __name__ == "__main__":')]
check(m.index("_selbst_auffrischen()") < m.index("panel_einzel_instanz()") < m.index("threading.Thread("), "main(): Mutex nach dem Auffrischen (runpy), vor allen Threads")
check("_PanelServer((\"127.0.0.1\", PORT), Handler).serve_forever()" in m and "ThreadingHTTPServer((" not in m, "Server mit exklusivem Bind")
k = SRC.index("class _PanelServer(")
check('allow_reuse_address = os.name != "nt"' in SRC[k:k + 600] and "SO_EXCLUSIVEADDRUSE" in SRC[k:k + 600], "Windows: kein SO_REUSEADDR, SO_EXCLUSIVEADDRUSE")
ns2 = dict(ns)
exec(SRC[SRC.index("_EINZEL_MUTEX = []"):SRC.index("class _PanelServer(")], ns2)
check(ns2["panel_einzel_instanz"]() is True, "kein Windows → einziges Panel (wie bisher)")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
