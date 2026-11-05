#!/usr/bin/env python3
"""Selbsttest AB3b (05.11.2026): Balance-Vortrag als P&L-Vorbelegung beim Abhaken (app.py echo_vortrag + Quelltext-Prüfungen in prophos.html).
Fall Blue Guardian 100k …7770, Hand-Nachtrade 7869ea6c: Endbalance 100.534,71 − Endbalance Vortrag e8fa35d4 100.447,83 = +86,88 (Finn tippte 50,00).
Ohne Netz. Aufruf: python3 tools/selftest_ab3_vortrag.py (die JS-Regel ab3Vortrag prüft derselbe Fall im Boot-Check über window._ab3Vortrag)."""
import ast
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-11-05_pl_quelle_balance_vortrag.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


baum = ast.parse(SRC)
ns = {}
for f in ("_wd_num", "_vortrag_bal", "echo_vortrag"):
    knoten = next(k for k in baum.body if isinstance(k, ast.FunctionDef) and k.name == f)
    exec(compile(ast.Module(body=[knoten], type_ignores=[]), "app.py", "exec"), ns)
V = ns["echo_vortrag"]

plan = {"id": "7869ea6c", "master_account_id": "k7770", "started_at": "2026-11-05T13:26:51.208+00:00", "ended_at": None, "master_pl": None,
        "mt5_baseline": {"final": {"at": "2026-11-05T13:45:11.667Z", "master_balance": 100534.71, "closed_sum": -14.89}, "master_balance": None}}
vortrag = {"id": "e8fa35d4", "started_at": "2026-11-05T07:24:00+00:00", "ended_at": "2026-11-05T08:10:00+00:00", "bal_echo": 100447.83, "bal_nach": 100447.83, "bal_tv": None}
selbst = {"id": "7869ea6c", "started_at": plan["started_at"], "ended_at": None, "bal_echo": 100534.71}
r = V(plan, [vortrag, selbst])
check(r is not None and r["pl"] == 86.88 and r["plan_id"] == "e8fa35d4" and r["balance_vorher"] == 100447.83,
      f"7869ea6c: 100.534,71 − 100.447,83 = +86,88 aus dem Vortrag e8fa35d4 ({r})")
alt = {"id": "aaaa", "started_at": "2026-11-04T07:00:00+00:00", "ended_at": "2026-11-04T08:00:00+00:00", "bal_echo": 99000.0}
check(V(plan, [alt, vortrag])["plan_id"] == "e8fa35d4", "der JÜNGSTE Vortrag zählt, nicht ein älterer")
check(V(dict(plan, mt5_baseline=dict(plan["mt5_baseline"], master_balance=100447.83)), [vortrag]) is None, "Start-Balance da → kein Vortrag (pl_balance gilt)")
check(V(dict(plan, master_pl=50.0), [vortrag]) is None, "P&L am Plan schon da → nicht anfassen")
check(V(dict(plan, mt5_baseline={"final": {}}), [vortrag]) is None, "ohne Endbalance → nichts")
check(V(plan, []) is None and V(plan, [selbst]) is None, "kein Vortrag gefunden → Feld bleibt leer")
check(V(plan, [dict(vortrag, ended_at=None)]) is None, "Vortrag noch offen → nichts")
check(V(plan, [dict(vortrag, ended_at="2026-11-05T13:30:00+00:00")]) is None, "Vortrag endete erst nach dem Start (überlappt) → nichts")
check(V(plan, [dict(vortrag, bal_echo=None, bal_nach=None), alt]) is None, "Vortrag ohne Endbalance → nichts, nie auf einen älteren ausweichen")
check(V(plan, [dict(vortrag, bal_echo=None, bal_nach=100440.0)])["pl"] == 94.71, "Endbalance des Vortrags aus der Nachlesung, wenn final fehlt")
zwischen = {"id": "bbbb", "started_at": "2026-11-05T13:30:00+00:00", "ended_at": None, "bal_echo": None}
check(V(plan, [vortrag, zwischen]) is None, "anderer Trade begann zwischen Start und Ende (offen) → nichts")
danach = {"id": "cccc", "started_at": "2026-11-05T14:30:00+00:00", "ended_at": None}
check(V(plan, [vortrag, danach])["pl"] == 86.88, "Trade erst NACH dem Ende dieses Trades → stört nicht")
check(V(dict(plan, started_at=None), [vortrag]) is None, "ohne Startzeit → nichts")
# S2-Stopp zu c767c9ea: Trade w desselben Kontos, der VOR dem Vortrag begann und erst danach schloss
w_ueber = {"id": "wwww", "started_at": "2026-11-05T07:00:00+00:00", "ended_at": "2026-11-05T08:30:00+00:00", "bal_echo": 100300.0}
check(V(plan, [vortrag, w_ueber]) is None, "w über v (07:00–08:30, v 07:24–08:10) → nichts (Endbalance von v ist nicht die Balance vor diesem Trade)")
w_luecke = dict(w_ueber, ended_at="2026-11-05T11:15:00+00:00")
check(V(plan, [vortrag, w_luecke]) is None, "w endet in der Lücke zwischen v und diesem Trade (11:15) → nichts")
w_offen = dict(w_ueber, ended_at=None)
check(V(plan, [vortrag, w_offen]) is None, "w begann vor v und ist noch offen → nichts")
w_vorher = dict(w_ueber, ended_at="2026-11-05T08:00:00+00:00")
check(V(plan, [vortrag, w_vorher])["pl"] == 86.88, "w schloss VOR dem Ende von v (08:00) → steckt in v's Endbalance, Vortrag gilt")
w_gleich = dict(w_ueber, ended_at="2026-11-05T08:10:00+00:00")
check(V(plan, [vortrag, w_gleich])["pl"] == 86.88, "w schloss genau mit v → Vortrag gilt")

# Verdrahtung
a = SRC[SRC.index("def _vortrag_anhaengen("):SRC.index("def _lt_echo_zeile(")]
check('"master_account_id": f"eq.{p[\'master_account_id\']}"' in a and "LT_ECHO_ROUTEN" in a and "except Exception" in a,
      "Server fragt nur im seltenen Fall (Echo, Start-Balance fehlt, Endbalance da, kein P&L) je Konto ab, wirft nie")
check("return _vortrag_anhaengen(z, p)   # AB3b" in SRC and "_vortrag_anhaengen(z, p))   # AB3b: Echo ohne Start-Balance" in SRC,
      "Vortrag in /admin/live-trades (Echo-Zeile) und /admin/wd-heute (Radar)")
check('elif daten.get("pl_quelle") == "balance_vortrag":' in SRC and '"balance_vortrag")  # pl_quelle eines echten' in SRC,
      "Radar-Speichern übernimmt pl_quelle 'balance_vortrag'; zählt als echtes Ergebnis")
r_ = SRC[SRC.index('filt = {"id": f"eq.{pid}", "route": f"in.({\',\'.join(WD_ERLEDIGT_ROUTEN)})"'):]
r_ = r_[:r_.index("if z:")]
check('upd.pop("pl_quelle", None)' in r_ and '"23514" in _txt' in r_ and r_.count('sb_update("trade_plans", filt, upd)') == 2 and "raise" in r_,
      "Radar-Speichern: Check lehnt pl_quelle ab (SQL fehlt) → einmal ohne pl_quelle, andere Fehler wie bisher")
check("(!isFinite(ms(x.endedAt)) || ms(x.endedAt) > ve)" in HTML and '(not f.get("ended_at") or str(f["ended_at"]) > ve)' in SRC,
      "dieselbe Dazwischen-Regel in JS (ab3Vortrag) und Python (echo_vortrag)")
check("'balance_vortrag'::text" in SQL and "drop constraint if exists trade_plans_pl_quelle_check" in SQL, "SQL erlaubt 'balance_vortrag' im Check (idempotent)")
check(": _mplWert != null ? _mplWert\n      : _vt ? _fz(_vt.pl) : null" in HTML and "&& _mplWert == null && pw.vortrag" in HTML,
      "Radar-Popup: Vortrag nur als Letztes (nach Balance-Sprung, pl_balance, master_pl.wert) — verdrängt nie einen Wert")
check("zeilen.append(_vortrag_anhaengen(z, p))" in SRC and "datetime.fromisoformat(" not in SRC[SRC.index("def _vortrag_anhaengen("):SRC.index("def _lt_echo_zeile(")],
      "Radar: nur für behaltene Zeilen; Abfrage-Zeitraum ohne fromisoformat (Python < 3.11)")
check("plQuelleVor ? { pl_quelle: plQuelleVor }" in HTML and "const plQuelleVor = plHand ? null : _mwdErlVorQuelle" in HTML,
      "Radar-Popup: unverändert → 'balance_vortrag', geändert → 'hand' wie bisher")
check("const _tcVt = (p.masterPl == null) ? ab3Vortrag(p, tradePlans) : null" in HTML and "_tcVt ? { wert: Number(_tcVt.pl), quelle: 'balance_vortrag' }" in HTML,
      "Trades-Popup: Vortrag aus den eigenen Plänen, unverändert → 'balance_vortrag'")
check(HTML.count("ab3VortragText(") >= 3 and "aus Vortrag" in HTML, "Hilfe-Text „aus Vortrag“ in beiden Popups")
check("window._ab3Vortrag = ab3Vortrag" in HTML, "Test-Haken für den Boot-Check")

print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
