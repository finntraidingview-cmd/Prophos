#!/usr/bin/env python3
"""Selbsttest TS1 „Time Sync Warning" (Finn 16.11.2026 über den Master): TopstepX zeigt das Modal „Time Sync Warning" mit genau einem Knopf
„PROCEED" — Puls (Weg tsv2) klickt NUR diesen bekannten Dialog weg (Ziel-Beweis, höchstens eine Wiederholung), hält es in Spur/puls_diagnose
fest und markiert die Antwort (pc_uhr_unsynchron). Geprüft: Erkennen (nur der EINE Dialog mit genau dieser Überschrift), Knopfwahl (genau ein
PROCEED, nie OK/Cancel/zweideutig), Ablauf mit nachgebauter Sitzung (weg nach 1 bzw. 2 Drücken, bleibt → genau 2 Drücke und Fehler, fremder
Dialog → nichts), Antwort-Feld nur nach Erfolg, und ein Diff-Test gegen origin/main: an bestehenden Stellen kommt nur Code hinzu, der unter
der Time-Sync-Bedingung steht — alle anderen tsv2-Abläufe bleiben bitgleich (die volle Reihe mt5-copier/selftest.py prüft sie zusätzlich).
Aufruf: python3 tools/selftest_ts1_zeitsync.py"""
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


R = [400, 300, 90, 32]
DLG = {"titel": "Time Sync Warning", "text": "Time Sync Warning Your computer clock is not synchronized with the correct time. PROCEED",
       "knoepfe": [{"text": "PROCEED", "rect": R}]}

# ── 1) Erkennen ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
zd = ob.tsx_zeitsync_dialog
check(zd([DLG]) is DLG, "Dialog mit Überschrift „Time Sync Warning“ erkannt")
check(zd([dict(DLG, titel="TIME SYNC WARNING")]) is not None and zd([dict(DLG, titel="time sync  warning")]) is not None, "Groß-/Kleinschreibung egal")
check(zd([dict(DLG, titel="")]) is not None, "ohne Überschrift: Text beginnt mit „Time Sync Warning“ → ja")
check(zd([dict(DLG, titel="", text="Notice: time sync warning below")]) is None, "ohne Überschrift, Wort nicht am Anfang → nicht")
check(zd([dict(DLG, titel="Trade Copier Notice")]) is None, "andere Überschrift (auch wenn der Text es enthält) → nicht")
check(zd([DLG, {"titel": "Confirm Order"}]) is None and zd([]) is None and zd(None) is None, "zwei Dialoge / keiner → nicht")

# ── 2) Knopf ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
zk = ob.tsx_zeitsync_knopf
k = zk(DLG)
check(k and k["text"] == "PROCEED" and not k["aus_aria"], "genau ein PROCEED")
check((zk(dict(DLG, knoepfe=[{"text": "", "aria": "Proceed", "rect": R}])) or {}).get("aus_aria") is True, "PROCEED nur als aria → aus aria")
check(zk(dict(DLG, knoepfe=[{"text": "PROCEED", "rect": R}, {"text": "Proceed", "rect": [500, 300, 90, 32]}])) is None, "zwei PROCEED → nichts")
check(zk(dict(DLG, knoepfe=[{"text": "OK", "rect": R}])) is None and zk(dict(DLG, knoepfe=[{"text": "Continue", "rect": R}])) is None,
      "OK/Continue zählen nie")
check((zk(dict(DLG, knoepfe=[{"text": "Cancel", "rect": [300, 300, 80, 32]}, {"text": "PROCEED", "rect": R}])) or {}).get("text") == "PROCEED",
      "PROCEED neben Cancel → PROCEED")
check(zk(dict(DLG, knoepfe=[{"text": "PROCEED", "rect": [1, 1, 0, 0]}])) is None and zk(dict(DLG, knoepfe=[{"text": "PROCEED"}])) is None,
      "ohne brauchbares Rechteck → nichts")
check(zk(dict(DLG, knoepfe=[{"text": "Proceed to place order", "rect": R}])) is None, "kein Teilstring/Order-Wort")


# ── 3) Ablauf mit nachgebauter Sitzung ───────────────────────────────────────────────────────────────────────────────────────
class Sitzung:
    def __init__(self, staende, klick_ok=True):
        self.staende, self.klicks, self.klick_ok, self.gelesen = list(staende), [], klick_ok, 0

    def stand(self):
        self.gelesen += 1
        return self.staende.pop(0) if self.staende else {"popups": []}

    def klick(self, rect, name, toast_ok=False, pruef=None, doppel=False):
        self.klicks.append((list(rect), name, dict(pruef or {})))
        return self.klick_ok

    def taste(self, *a, **k):
        raise AssertionError("keine Taste im Time-Sync-Weg")


diag = []
ob._warte = lambda *a, **k: None
ob._tsx_pause = lambda *a, **k: None
ob._puls_diagnose_senden = lambda spur=None, schritt="": diag.append((schritt, list(spur or [])))
ob._pc_id_lesen = lambda: "pc-test01"
MIT, OHNE = {"popups": [DLG]}, {"popups": []}


def lauf(st0, staende, klick_ok=True):
    ob._TSX_ZEITSYNC.clear()
    if hasattr(ob, "_TSX_ZEITSYNC_N"):
        ob._TSX_ZEITSYNC_N[0] = 0      # TX1 (17.11.2026): Zähler je Lauf (im Betrieb setzt modus_tsxlesen_cdp ihn zurück) — hier je Fall ein neuer Lauf
    diag.clear()
    s, trail = Sitzung(staende, klick_ok), []
    st, weg = ob._tsx_zeitsync_weg(s, st0, trail)
    return s, trail, st, weg


s, t, st, weg = lauf(OHNE, [])
check(weg is None and not s.klicks and s.gelesen == 0 and not t and not ob._TSX_ZEITSYNC, "ohne Dialog: nichts gelesen, nichts gedrückt, kein Merker")
s, t, st, weg = lauf({"popups": [dict(DLG, titel="Trade Copier Notice")]}, [])
check(weg is None and not s.klicks, "fremder Dialog: nichts gedrückt")
s, t, st, weg = lauf({"popups": [DLG, {"titel": "Confirm Order", "knoepfe": [{"text": "OK", "rect": R}]}]}, [])
check(weg is None and not s.klicks, "Time Sync + zweiter Dialog: nichts gedrückt")
s, t, st, weg = lauf(MIT, [OHNE])
pr = s.klicks[0][2] if s.klicks else {}
check(weg is True and len(s.klicks) == 1 and s.klicks[0][0] == R and pr.get("wort") == "proceed" and pr.get("text") == "PROCEED"
      and re.search(pr.get("tabu") or "x^", "buy", re.I) and re.search(pr.get("tabu") or "x^", "sell", re.I),
      f"weg nach EINEM Druck, Ziel-Beweis wort=proceed + Order-Tabu ({s.klicks})")
check(any("Time Sync Warning weggeklickt" in x and "pc-test01" in x for x in t) and ob._TSX_ZEITSYNC.get("pc") == "pc-test01"
      and ob._TSX_ZEITSYNC.get("at") and diag and diag[-1][0] == "zeitsync", "Spur + puls_diagnose „zeitsync“ + Merker {at, pc}")
s, t, st, weg = lauf(MIT, [MIT, OHNE])
check(weg is True and len(s.klicks) == 2 and any("Versuch 2 von 2" in x for x in t), "steht nach dem 1. Druck → EINE Wiederholung, dann weg")
s, t, st, weg = lauf(MIT, [MIT, MIT, MIT])
check(weg is False and len(s.klicks) == 2 and any("steht nach 2 Versuchen noch" in x for x in t) and not ob._TSX_ZEITSYNC and not diag,
      "bleibt → genau 2 Drücke, dann Fehler wie bisher (kein Merker, keine Erfolgs-Spur)")
s, t, st, weg = lauf(MIT, [MIT, OHNE], klick_ok=False)
check(weg is True and len(s.klicks) == 2 and any("nicht ausgeführt (Ziel-Beweis)" in x for x in t), "Ziel-Beweis verweigert → neu lesen, zweiter Versuch")
s, t, st, weg = lauf({"popups": [dict(DLG, knoepfe=[{"text": "OK", "rect": R}])]}, [])
check(weg is False and not s.klicks and any("kein eindeutiger PROCEED-Knopf" in x for x in t), "kein PROCEED → nichts gedrückt")

# ── 4) Antwort-Feld ──────────────────────────────────────────────────────────────────────────────────────────────────────────
import io  # noqa: E402
import contextlib  # noqa: E402
import json  # noqa: E402


def ausgabe(merker):
    ob._TSX_ZEITSYNC.clear()
    ob._TSX_ZEITSYNC.update(merker)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ob._EineAntwort().ausgeben({"ok": True, "code": ""})
    return json.loads(buf.getvalue().strip())


check(ausgabe({}) == {"ok": True, "code": ""}, "ohne Wegklicken: Antwort bitgleich")
check(ausgabe({"at": "2026-11-16T08:00:00Z", "pc": "pc-test01"}).get("pc_uhr_unsynchron") == {"at": "2026-11-16T08:00:00Z", "pc": "pc-test01"},
      "nach dem Wegklicken: pc_uhr_unsynchron {at, pc}")
ob._TSX_ZEITSYNC.clear()

# ── 5) Diff-Test gegen origin/main: an bestehenden Stellen nur Code unter der Time-Sync-Bedingung ──────────────────────────────
src = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
try:
    # HW1 (16.11.2026): der Diff-Test schützt nur den TS1-Commit bis zum Push — liegt TS1 schon auf origin/main, gehören spätere Änderungen an
    # order_bot.py nicht mehr zu TS1 (sonst wäre der Test bei jeder Folgeänderung rot)
    basis = subprocess.run(["git", "show", "origin/main:mt5-copier/order_bot.py"], cwd=WURZEL, capture_output=True, text=True).stdout
    if "# TIME SYNC WARNING (TS1" in basis:
        diff = ""
        print("(Diff-Test übersprungen: TS1 liegt schon auf origin/main)")
    else:
        diff = subprocess.run(["git", "diff", "-U0", "origin/main", "--", "mt5-copier/order_bot.py"], cwd=WURZEL, capture_output=True, text=True).stdout
except Exception as e:
    diff = ""
    print(f"(Diff-Test übersprungen: {type(e).__name__})")
if diff:
    neu_block = src[src.index("# TIME SYNC WARNING (TS1"):src.index("\ndef _tsx_geblowt_merken(")]
    weg_z = [z[1:] for z in diff.splitlines() if z.startswith("-") and not z.startswith("---")]
    dazu = [z[1:] for z in diff.splitlines() if z.startswith("+") and not z.startswith("+++")]
    ausserhalb = [z for z in dazu if z.strip() and z not in neu_block]
    erlaubt = re.compile(r"zeitsync|_zs\b|TS1|Time Sync|zs_versucht|_TSX_ZEITSYNC|pc_uhr_unsynchron|bracket_dialog|^\s*#|^\s*try:\s*$|^\s*except Exception as e_:\s*$")
    fremd = [z for z in ausserhalb if not erlaubt.search(z)]
    check(not fremd, f"jede neue Zeile an bestehenden Stellen gehört zum Time-Sync-Zweig ({fremd[:3]})")
    check(len(weg_z) == 1 and "bracket_dialog" in weg_z[0], f"genau eine bestehende Zeile verändert: bracket_dialog nur noch ohne Time-Sync-Dialog ({weg_z})")
    check("                if not tsx_zeitsync_dialog(st.get(\"popups\")):\n                    res.setdefault(\"bracket_dialog\"" in src,
          "Brackets: ohne Time-Sync-Dialog wird bracket_dialog wie bisher gesetzt")
# Aufrufstellen: jede steht hinter tsx_zeitsync_dialog (_tsx_zeitsync_weg selbst prüft ebenfalls zuerst)
aufrufe = [m.start() for m in re.finditer(r"(?<!def )_tsx_zeitsync_weg\(s, st, trail\)", src)]
check(len(aufrufe) == 4, f"vier Aufrufstellen: Kontowahl, vor dem Order-Klick, Brackets, Lesen beim Start ({len(aufrufe)})")
check(all("tsx_zeitsync_dialog(" in src[max(0, a - 420):a] for a in aufrufe), "jede Aufrufstelle prüft vorher tsx_zeitsync_dialog")
check("s.taste" not in src[src.index("def _tsx_zeitsync_weg("):src.index("\ndef _tsx_geblowt_merken(")], "kein Esc/keine Taste — nur der PROCEED-Druck")

print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
raise SystemExit(1 if FEHLER else 0)
