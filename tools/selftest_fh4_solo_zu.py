#!/usr/bin/env python3
"""Selbsttest FH4 (mt5-copier/copier.py solo_zu_ring, solo_zu_urteil, solo_eintrag_echt + verschachtelte solo_abschluesse_erkennen; Master 16.11.2026,
Folge zu FH3): 18:51 an 488579 lieferte das Terminal kurz eine LEERE Positionsliste — jedes bekannte Solo-Ticket galt als zu, ohne Deal → „unbekannt“, später
verwarf der Ring den echten Deal. Fälle: (a) Lücke (leere Liste, kein Deal) → kein Eintrag, Ticket bleibt bekannt, Lücke vorbei → nichts gebucht;
(b) echter Schluss → nach 2 Lesungen mit Deal gebucht (auch wenn die Liste danach wirklich leer ist); (c) Historie hinkt → „unbekannt“ erst nach 20 s
(leere Liste: 60 s), Nachlesen gedrosselt; (d) später echter Deal ersetzt „unbekannt“ an derselben Stelle, echter Eintrag wird nie überschrieben;
(e) Ring-Größe 20 unverändert; (f) Einbau: liste_leer nur bei ganz leerem positions_get. Ohne MetaTrader, ohne Netz.
Aufruf: python3 tools/selftest_fh4_solo_zu.py"""
import ast
import os
import sys
import textwrap
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "copier.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


uhr = [100_000.0]
welt = {"deals": {}, "lesungen": [], "gespeichert": 0, "log": []}
import datetime as _dt
ns = {"time": types.SimpleNamespace(time=lambda: uhr[0]), "datetime": _dt.datetime, "timezone": _dt.timezone}
baum = ast.parse(SRC)
for n in baum.body:
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith("SOLO_ZU") for t in n.targets):
        exec(ast.get_source_segment(SRC, n), ns)
    if isinstance(n, ast.FunctionDef) and n.name in ("solo_zu_erkennen", "solo_zu_ring", "solo_zu_urteil", "solo_eintrag_echt", "utc_iso_ms"):
        exec(ast.get_source_segment(SRC, n), ns)
inner = next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef) and n.name == "solo_abschluesse_erkennen")
hedge_acc = {"solo_zu": [], "solo_bekannt": {}}


def pl_history(t, versuche=8):
    welt["lesungen"].append((uhr[0], t, versuche))
    return welt["deals"].get(t, (None, None, None))


ns.update(hedge_acc=hedge_acc, solo_pl_aus_history=pl_history, solo_letzter_deal={}, deal_closed_at=lambda d, s: "2026-11-16T14:51:00.000Z",
          log=lambda m: welt["log"].append(m), solo_zu_speichern=lambda r, b: welt.__setitem__("gespeichert", welt["gespeichert"] + 1))
exec(textwrap.dedent(ast.get_source_segment(SRC, inner)), ns)
ERK, RING, URT = ns["solo_abschluesse_erkennen"], ns["solo_zu_ring"], ns["solo_zu_urteil"]


def pos(t):
    return {"ticket": t, "symbol": "NAS100", "lots": 1.0, "richtung": "sell", "fill": 25000.0, "plan8": "abcd1234", "plan_id": f"plan-{t}"}


def neu(bekannt):
    hedge_acc.clear(); hedge_acc.update(solo_zu=[], solo_bekannt={t: {k: v for k, v in pos(t).items() if k != "ticket"} for t in bekannt})
    welt.update(deals={}, lesungen=[], gespeichert=0, log=[])
    uhr[0] += 10_000


def tick(liste, leer=None, dt=0.5):
    sl = [pos(t) for t in liste]
    hedge_acc["solo"] = sl                                   # wie der Copier-Tick: hedge_acc["solo"] = solo, dann erkennen
    ERK(sl, liste_leer=(not liste) if leer is None else leer)
    uhr[0] += dt


def sichtbar():
    return {(p["ticket"], bool(p.get("unbestaetigt"))) for p in (hedge_acc.get("solo") or [])}


# (a) 18:51 Lücke: leere Positionsliste ohne Deal, 3 Takte, dann sind beide wieder da
neu([101, 102])
tick([101, 102])                                             # letzter Stand bekannt
for _ in range(3):
    tick([])
check(sichtbar() == {(101, True), (102, True)}, "a) Prüfer MUSS: während des Wartens bleiben beide in hedge_solo sichtbar (unbestaetigt) — keine Tab-Wache schließt")
check(hedge_acc["solo_zu"] == [] and set(hedge_acc["solo_bekannt"]) == {101, 102}, "a) Lücke (leere Liste, kein Deal) → kein „weg“-Eintrag, beide Tickets bleiben bekannt")
tick([101, 102])
check(hedge_acc["solo_zu"] == [] and set(hedge_acc["solo_bekannt"]) == {101, 102} and not hedge_acc.get("solo_fehlt"),
      "a) Lücke vorbei → nichts gebucht, Zähler weg")
check(len(welt["lesungen"]) == 2 and all(x[2] == 8 for x in welt["lesungen"]), f"a) Historie in der Lücke je Ticket nur einmal voll gelesen ({len(welt['lesungen'])}×)")
check(sichtbar() == {(101, False), (102, False)}, "a) Lücke vorbei → wieder normale Einträge, keine Kennung")
# (b) echter Schluss der einzigen Position (Liste danach wirklich leer) → nach der 2. Lesung mit Deal gebucht
neu([201])
welt["deals"][201] = (-4.2, "level_tp", 25010.5)
tick([])
check(hedge_acc["solo_zu"] == [] and 201 in hedge_acc["solo_bekannt"] and welt["lesungen"] == [], "b) 1. Lesung ohne Ticket → noch nichts (keine Historie gelesen)")
tick([])
z = hedge_acc["solo_zu"]
check(len(z) == 1 and z[0]["ticket"] == 201 and z[0]["pl"] == -4.2 and z[0]["grund"] == "level_tp" and z[0]["fill_close"] == 25010.5
      and 201 not in hedge_acc["solo_bekannt"], "b) 2. Lesung + Deal in der Historie → sofort gebucht (P&L, Grund, Kurs), auch bei danach leerer Liste")
check(sichtbar() == set() and z[0]["closed_at"] == "2026-11-16T14:51:00.000Z",
      "b) im Buchungs-Takt aus hedge_solo raus und im Ring (derselbe Status — Ring-Zweig am Tab), closed_at = Deal-Zeit")
# (c) Historie hinkt bei sonst gefüllter Liste: „unbekannt“ erst nach 20 s, Nachlesen alle ≥ 5 s
neu([301, 302])
t0 = uhr[0]
while not hedge_acc["solo_zu"] and uhr[0] - t0 < 120:
    tick([302])
dauer = uhr[0] - t0
z = hedge_acc["solo_zu"]
abst = [b[0] - a[0] for a, b in zip(welt["lesungen"], welt["lesungen"][1:])]
check(len(z) == 1 and z[0]["grund"] == "unbekannt" and z[0]["pl"] is None and 20 <= dauer <= 21.5, f"c) Liste gefüllt, kein Deal → „unbekannt“ nach {dauer:.1f} s (20 s)")
check(abst and all(x >= 4.99 for x in abst[:-1]), f"c) Historie höchstens alle 5 s neu gelesen ({len(welt['lesungen'])} Lesungen)")
check(welt["lesungen"][0][2] == 8 and all(x[2] == 1 for x in welt["lesungen"][1:]), "c) Prüfer S4: erste Lesung voll (bis 2 s), jedes Nachlesen 1 Versuch ohne Pause")
seit_ = t0 + 0.5
check(z[0]["closed_at"] == ns["utc_iso_ms"](t0), f"c) Prüfer S3: „unbekannt“ trägt closed_at = erstes Fehlen ({z[0]['closed_at']}), nicht das Ende der Wartezeit")
neu([401])
t0 = uhr[0]
while not hedge_acc["solo_zu"] and uhr[0] - t0 < 200:
    tick([])
check(60 <= uhr[0] - t0 <= 61.5, f"c) Liste ganz leer, kein Deal → „unbekannt“ erst nach {uhr[0] - t0:.1f} s (60 s)")
check(len(welt["lesungen"]) == 2, f"c) in der Lücke nur erste Lesung + eine an der Grenze ({len(welt['lesungen'])})")
# (c2) unlesbarer Tick (positions_get None) unterbricht „in Folge“ (Prüfer K5)
neu([451])
tick([451]); tick([])
ERK(None); uhr[0] += 300
tick([])
check(not hedge_acc["solo_zu"] and 451 in hedge_acc["solo_bekannt"], "c2) None-Tick dazwischen → Zählung neu, kein sofortiges „unbekannt“ nach langer Pause")
# (c3) mehrere Tickets gleichzeitig: eines echt zu, eines nur Lücke
neu([601, 602])
tick([601, 602])
welt["deals"][601] = (2.5, "close", 25001.0)
tick([]); tick([])
check([r["ticket"] for r in hedge_acc["solo_zu"]] == [601] and sichtbar() == {(602, True)} and set(hedge_acc["solo_bekannt"]) == {602},
      "c3) zwei fehlen: das mit Deal gebucht, das ohne bleibt sichtbar und bekannt")
# (d) Ersetzen: früheres „unbekannt“ durch den echten Deal (Ticket tauchte wieder auf und schloss echt)
neu([501])
hedge_acc["solo_zu"] = [{"ticket": 499, "pl": 1.0, "grund": "close"}, {"ticket": 501, "pl": None, "grund": "unbekannt", "fill_close": None},
                        {"ticket": 502, "pl": 3.0, "grund": "level_sl"}]
welt["deals"][501] = (-7.5, "level_tp", 24990.0)
tick([]); tick([])
z = hedge_acc["solo_zu"]
check([r["ticket"] for r in z] == [499, 501, 502] and z[1]["pl"] == -7.5 and z[1]["grund"] == "level_tp",
      "d) späterer echter Deal ersetzt „unbekannt“ an derselben Stelle (Reihenfolge bleibt)")
r = RING([{"ticket": 7, "pl": 2.0, "grund": "close"}], {"ticket": 7, "pl": None, "grund": "unbekannt"})
r2 = RING([{"ticket": 7, "pl": 2.0, "grund": "close"}], {"ticket": 7, "pl": 9.0, "grund": "level_tp"})
check(r == [{"ticket": 7, "pl": 2.0, "grund": "close"}] and r2 == [{"ticket": 7, "pl": 2.0, "grund": "close"}],
      "d) echter Eintrag wird nie überschrieben — weder von „unbekannt“ noch von einem zweiten echten (der Erste gewinnt)")
check(ns["solo_eintrag_echt"]({"pl": None, "grund": "unbekannt", "fill_close": 25000.0}) and not ns["solo_eintrag_echt"]({"pl": None, "grund": "unbekannt"}),
      "d) „echt“ = P&L, Schluss-Kurs oder Grund ≠ unbekannt")
# (e) Ring-Größe
ring = []
for t in range(1, 30):
    ring = RING(ring, {"ticket": t, "pl": 1.0, "grund": "close"})
check(len(ring) == 20 and ring[0]["ticket"] == 10 and ring[-1]["ticket"] == 29 and ns["SOLO_ZU_MAX"] == 20, "e) Ring bleibt bei 20, älteste fliegen raus")
check(URT(1, 999, True, False) == "warten" and URT(2, 0, True, True) == "buchen" and URT(2, 19.9, False, False) == "warten"
      and URT(2, 20, False, False) == "buchen" and URT(2, 59, False, True) == "warten" and URT(2, 60, False, True) == "buchen",
      "e) Urteil: 2 Lesungen Pflicht; Deal → sofort; ohne Deal 20 s bzw. 60 s bei leerer Liste")
# (f) Einbau
check("solo_abschluesse_erkennen(solo, liste_leer=solo is not None and fremde is not None and not solo and not fremde\n" in SRC
      and "and not _pos_alle)" in SRC, "f) Aufruf: liste_leer nur, wenn positions_get gar keine Position lieferte")
check("SOLO_ZU_MAX = 20" in SRC, "f) SOLO_ZU_MAX unverändert 20")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
