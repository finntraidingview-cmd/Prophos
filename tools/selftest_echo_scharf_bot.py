#!/usr/bin/env python3
"""Selbsttest SCHARF-BEWEIS IM BOT (ES2/ES3-Zusatz, 05.11.2026): der Echo-Bot prüft bei scharf_pflicht selbst, ob der Copier für diese Config
ein offenes Trade-Fenster meldet — nach „Login/Lesen ok“, VOR „Terminal betreten“/F9. Die ECHTEN Funktionen aus mt5-copier/order_bot.py,
Status-/Plan-Dateien in einem Temp-Ordner, Uhr ersetzt, ohne Windows.
 a) echo_scharf_urteil: running + armed + frisch (≤ 15 s) = scharf; alt/ohne Zeit/armed false/kaputt = warten; „laufend“ bei flachem Master
    = warten (altLaufend-Regel wie im Tab), „laufend“ mit Master-Position = scharf
 b) echo_scharf_max: 5–60 s, Standard 30
 c) _echo_scharf_abwarten: wird scharf nach ein paar Takten → True + Spur „Copier scharf nach …“; bleibt alt → False nach max_s, Grund
 d) Verdrahtung: nur scharf_pflicht True + Echo mit Hedge, vor Versatz/Terminal-Suche/F9, Abbruch nicht_scharf retry_ok ohne Fehlerfoto,
    Panel reicht scharf_pflicht nur bei Echo mit Hedge durch
Aufruf: python3 tools/selftest_echo_scharf_bot.py"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(os.path.dirname(HIER), "mt5-copier", "order_bot.py")
PANEL = os.path.join(os.path.dirname(HIER), "mt5-copier", "panel.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


class Uhr:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t


def main():
    src = open(BOT, encoding="utf-8").read()
    uhr = Uhr()
    ns = {"os": os, "re": re, "json": json, "time": uhr}
    for k in ("ECHO_SCHARF_FRISCH_S", "ECHO_SCHARF_MAX_S", "ECHO_SCHARF_STANDARD_S", "TERMINAL_SUCHE_BIS"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    for n in ("echo_scharf_urteil", "echo_scharf_max", "_echo_scharf_abwarten"):
        exec(fn(src, n), ns)
    U, M, A = ns["echo_scharf_urteil"], ns["echo_scharf_max"], ns["_echo_scharf_abwarten"]
    jetzt = datetime(2026, 11, 5, 19, 0, 0)
    frisch = (jetzt - timedelta(seconds=3)).isoformat(timespec="seconds")
    gut = {"running": True, "armed": True, "updated_at": frisch, "master_positions": []}
    geplant = [{"file": "config-a.json", "status": "geplant", "armed_at": (jetzt - timedelta(minutes=2)).isoformat(timespec="seconds")}]

    # a) Urteil
    check(U(gut, geplant, "config-a.json", jetzt) == ("scharf", ""), "running + armed + 3 s alt + geplant → scharf")
    check(U(dict(gut, armed=False), geplant, "config-a.json", jetzt)[0] == "warten", "armed false → warten")
    check(U(dict(gut, armed="true"), geplant, "config-a.json", jetzt)[0] == "warten", "armed nur als Text → warten (nur === true)")
    check(U(dict(gut, running=False), geplant, "config-a.json", jetzt)[0] == "warten", "Copier läuft nicht → warten")
    alt = (jetzt - timedelta(seconds=16)).isoformat(timespec="seconds")
    check(U(dict(gut, updated_at=alt), geplant, "config-a.json", jetzt) == ("warten", "Copier-Status nicht frisch (16 s alt)"), "16 s alt → warten, Grund mit Zahl")
    check(U(dict(gut, updated_at=None), geplant, "config-a.json", jetzt)[0] == "warten" and U(None, None, "x", jetzt)[0] == "warten",
          "ohne Zeit / ohne Status → warten")
    laufend = [{"file": "config-a.json", "status": "laufend"}]
    check(U(gut, laufend, "config-a.json", jetzt)[0] == "warten", "„laufend“ bei flachem Master → warten (altes Fenster)")
    check(U(dict(gut, master_positions=[{"ticket": 1}]), laufend, "config-a.json", jetzt)[0] == "scharf", "„laufend“ mit Master-Position → scharf")
    check(U(gut, [{"file": "config-b.json", "status": "laufend"}] + geplant, "config-a.json", jetzt)[0] == "scharf"
          and U(gut, [{"file": "config-b.json", "status": "geplant", "armed_at": geplant[0]["armed_at"]}], "config-a.json", jetzt)[0] == "warten",
          "Pläne anderer Configs zählen weder dafür noch dagegen")
    check(U(gut, None, "config-a.json", jetzt)[0] == "warten" and U(gut, "kaputt", "config-a.json", jetzt)[0] == "warten",
          "plans.json unlesbar → warten (der Copier hedgt ohne Fenster selbst nicht)")
    check(U(gut, [{"file": "config-a.json", "status": "beendet"}], "config-a.json", jetzt)[0] == "warten",
          "Gegenprüfung 1: armed im Status noch true, Plan schon „beendet“ → warten (Status hinkt ~1,5 s hinterher)")
    check(U(gut, [], "config-a.json", jetzt)[0] == "warten", "kein Plan für die Config → warten")
    alt_g = [{"file": "config-a.json", "status": "geplant", "armed_at": (jetzt - timedelta(hours=7)).isoformat(timespec="seconds")}]
    check(U(gut, alt_g, "config-a.json", jetzt)[0] == "warten", "„geplant“ älter als 6 h → warten (wie copier.plan_armed_files)")
    check(U(dict(gut, note="warte auf Snapshot des Master-Terminals"), geplant, "config-a.json", jetzt)[0] == "warten",
          "Gegenprüfung 2: note gesetzt (kein Snapshot) → warten, wie der Tab (alive && !note)")
    check(U(dict(gut, paused=True), geplant, "config-a.json", jetzt)[0] == "warten", "Echo pausiert → warten")
    check(U(gut, None, "config-a.json", jetzt, immer_scharf=True)[0] == "scharf", "immer_scharf (Config) → scharf ohne Fenster, wie der Copier")
    check(U(dict(gut, armed=False), None, "config-a.json", jetzt, immer_scharf=True)[0] == "warten", "immer_scharf, aber armed false → warten")

    # b) max
    check(M({}) == 30.0 and M({"scharf_max_s": 2}) == 5.0 and M({"scharf_max_s": 999}) == 60.0 and M({"scharf_max_s": "x"}) == 30.0
          and M({"scharf_max_s": 12}) == 12.0 and M({"scharf_max_s": float("nan")}) == 30.0, "scharf_max_s: Standard 30, gekappt 5–60")

    # c) Warten mit echten Dateien
    with tempfile.TemporaryDirectory() as d:
        cfg = os.path.join(d, "config-a.json")
        stp = os.path.join(d, "status-a.json")
        open(cfg, "w").write("{}")
        json.dump([dict(geplant[0], armed_at=datetime.now().isoformat(timespec="seconds"))], open(os.path.join(d, "plans.json"), "w"))
        takte = {"n": 0}

        def warte(a, b):
            takte["n"] += 1
            uhr.t += a + b / 2
            if takte["n"] == 4:   # nach dem 4. Takt meldet der Copier armed
                json.dump(dict(gut, updated_at=datetime.now().isoformat(timespec="seconds")), open(stp, "w"))
        ns["_warte"] = warte
        json.dump(dict(gut, armed=False, updated_at=datetime.now().isoformat(timespec="seconds")), open(stp, "w"))
        spur = []
        ok, grund = A(cfg, 30.0, spur)
        check(ok and grund == "" and takte["n"] == 4 and spur and spur[-1].startswith("Copier scharf nach ") and "," in spur[-1],
              f"wird nach 4 Takten scharf → True, Spur „{spur[-1] if spur else ''}“")
        takte["n"], spur = 0, []
        ns["_warte"] = lambda a, b: setattr(uhr, "t", uhr.t + a + b / 2)
        json.dump(dict(gut, updated_at="2026-01-01T00:00:00"), open(stp, "w"))
        t0 = uhr.t
        ok, grund = A(cfg, 10.0, spur)
        check(not ok and "nicht frisch" in grund and 10.0 <= uhr.t - t0 < 11.0 and not spur, f"bleibt alt → False nach max_s ({grund})")
        os.remove(stp)
        ok, grund = A(cfg, 0.0, [])
        check(not ok and "nicht lesbar" in grund, "Status-Datei fehlt, max 0 → sofort False mit Grund (ein Blick, kein Warten)")

    # d) Verdrahtung
    r = fn(src, "run")
    i_login, i_sch = r.index('trail.append("Login/Lesen ok")'), r.index('if cmd.get("scharf_pflicht") is True and not cmd.get("ohne_hedge"):')
    i_vers, i_such, i_f9 = r.index('_warte(0.0, float(_ECHO_TEMPO_LAUF.get("versatz_s", 1.2)))'), r.index("_finde_terminal_geduldig("), r.index('trail.append("F9-Dialog offen")')
    check(i_login < i_sch < i_vers < i_such < i_f9, "run: Scharf-Beweis nach „Login/Lesen ok“, vor Versatz, Terminal-Suche und F9")
    blk = r[i_sch:i_vers]
    check('"retry_ok": True' in blk and '"code": "nicht_scharf"' in blk and "TERMINAL_SUCHE_BIS - trail.sekunden()" in blk and "_spur(trail)" in blk,
          "Abbruch nicht_scharf: retry_ok (nichts gesendet), Budget bis TERMINAL_SUCHE_BIS, Spur in der Meldung")
    kn = r[r.index("if knopf is None:"):r.index("def _dialog_weg():")]
    check('_echo_scharf_abwarten(cfg_path, 0.0, [], immer_scharf=' in kn and '"code": "nicht_scharf"' in kn and '"{ESC}"' in kn
          and kn.index('_echo_scharf_abwarten(cfg_path, 0.0') < kn.index("_maus_fahren(") and r.index("def _dialog_weg():") < r.index('("Fokus+Leertaste", _weg_leertaste)'),
          "Gegenprüfung 3: letzter Blick (ohne Warten) direkt vor dem Order-Knopf, sonst ESC + nicht_scharf")
    check('"nicht_scharf"' in re.search(r"^FEHLERFOTO_CODES_OHNE = .*?\)", src, re.M | re.S).group(0), "kein Fehlerfoto bei nicht_scharf")
    p = open(PANEL, encoding="utf-8").read()
    check('if not ohne_hedge and body.get("scharf_pflicht") is True:' in p and 'cmd["scharf_max_s"] = body.get("scharf_max_s")' in p
          and p.index('cmd["scharf_pflicht"] = True') < p.index("json.dumps(cmd)", p.index('if u.path == "/api/master-order":')),
          "Panel: scharf_pflicht nur bei Echo mit Hedge und nur als bool true, vor dem Bot-Start im Befehl")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("ALLES GRÜN")


if __name__ == "__main__":
    main()
