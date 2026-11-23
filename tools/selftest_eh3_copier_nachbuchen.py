#!/usr/bin/env python3
"""Selbsttest EH3-2 (23.11.2026, Master nach Befund EH2): der Copier verbucht einen Hedge-Close, dessen Deal (Fusion: asynchron, deal=0) in den
4 Versuchen von book_close noch nicht in der History steht, nicht mehr nie — er wandert in m.buchung_offen und nachbuchen() schlägt ihn in jedem
Takt bis HEDGE_NACHBUCHEN_S (30 s) nach. Geprüft ohne MetaTrader/Windows: die reinen Helfer close_deal_waehlen / nachbuchen_urteil und die echten
book_close / close_verbuchen / nachbuchen (per AST aus main() gelöst) mit einer mt5- und Uhr-Attrappe; dazu die Verdrahtung im Hauptlauf.
Aufruf: python3 tools/selftest_eh3_copier_nachbuchen.py   Alle Kennungen erfunden."""
import ast
import os
import sys
import textwrap
import types

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import copier as cp  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


OUT, OUT_BY, IN = 1, 3, 0


MAGIC, EXPERT, SL = 767013, 3, 4


def deal(ticket, vol, entry=OUT, profit=30.0, msc=1000, reason=EXPERT, magic=MAGIC):
    return types.SimpleNamespace(ticket=ticket, volume=vol, entry=entry, profit=profit, commission=-3.5, swap=0.0, time_msc=msc, time=msc // 1000,
                                 reason=reason, magic=magic)


# ── reine Helfer ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
W = cp.close_deal_waehlen
ds = [deal(10, 1.4, IN), deal(11, 1.4, OUT, msc=2000)]
check(W(ds, 11, 1.4, set(), (OUT, OUT_BY)).ticket == 11 and W(ds, 99, 1.4, set(), (OUT, OUT_BY)) is None, "deal_id: genau dieser Deal, sonst None")
check(W(ds, 0, 1.4, set(), (OUT, OUT_BY)).ticket == 11 and W(ds, 0, 1.4, {11}, (OUT, OUT_BY)) is None, "ohne deal_id: unverbuchter OUT-Deal mit Volumen; verbucht → None")
zwei = [deal(11, 0.7, OUT, msc=1), deal(12, 0.7, OUT, msc=2)]
check(W(zwei, 0, 1.4, set(), (OUT, OUT_BY)) is None and W(zwei, 0, 0.7, set(), (OUT, OUT_BY)).ticket == 12
      and W([deal(13, 0.5, OUT)], 0, 1.4, set(), (OUT, OUT_BY)).ticket == 13 and W([], 0, 1.4, set(), (OUT, OUT_BY)) is None,
      "mehrdeutig → None; gleiches Volumen → jüngster; einziger OUT → dieser; leer → None")
U = cp.nachbuchen_urteil
check(W([deal(14, 1.4, OUT, reason=SL)], 0, 1.4, set(), (OUT, OUT_BY), magic=MAGIC, reason_expert=EXPERT) is None
      and W([deal(15, 1.4, OUT, magic=1)], 0, 1.4, set(), (OUT, OUT_BY), magic=MAGIC, reason_expert=EXPERT) is None
      and W([deal(16, 1.4, OUT)], 0, 1.4, set(), (OUT, OUT_BY), magic=MAGIC, reason_expert=EXPERT).ticket == 16
      and W([deal(17, 1.4, OUT, reason=SL)], 17, 1.4, set(), (OUT, OUT_BY), magic=MAGIC, reason_expert=EXPERT).ticket == 17,
      "EH3-2b: ohne deal_id nur eigene Copier-Deals (EXPERT + magic) — Notfall-SL/fremde magic nie; mit deal_id genau dieser")
check(U({"ab": 100.0}, True, 200.0) == "buchen" and U({"ab": 100.0}, False, 129.0) == "warten" and U({"ab": 100.0}, False, 131.0) == "aufgeben"
      and U({}, False, 5.0) == "aufgeben" and cp.HEDGE_NACHBUCHEN_S == 30.0, "Urteil: buchen / warten bis 30 s / aufgeben")

# ── echte book_close / close_verbuchen / nachbuchen mit Attrappen ─────────────────────────────────────────────────────────────
src = open(os.path.join(WURZEL, "mt5-copier", "copier.py"), encoding="utf-8").read()
haupt = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "main")
teile = {n.name: n for n in haupt.body if isinstance(n, ast.FunctionDef) and n.name in ("book_close", "close_verbuchen", "nachbuchen")}
check(set(teile) == {"book_close", "close_verbuchen", "nachbuchen"}, "book_close / close_verbuchen / nachbuchen stehen in main()")
code = "\n\n".join(textwrap.dedent(ast.get_source_segment(src, teile[k])) for k in ("book_close", "close_verbuchen", "nachbuchen"))


class Mt5:
    DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY = OUT, OUT_BY

    def __init__(self):
        self.hist = {}

    def history_deals_get(self, position=None):
        return list(self.hist.get(int(position), []))


class Uhr:
    t = 1000.0


class Zeit:
    @staticmethod
    def time():
        return Uhr.t

    @staticmethod
    def sleep(s):
        Uhr.t += s


def welt():
    mt5 = Mt5()
    mt5.DEAL_REASON_EXPERT = EXPERT
    logs, geschrieben = [], []
    ns = {"mt5": mt5, "time": Zeit, "log": logs.append, "close_deal_waehlen": cp.close_deal_waehlen, "nachbuchen_urteil": cp.nachbuchen_urteil,
          "HEDGE_NACHBUCHEN_S": cp.HEDGE_NACHBUCHEN_S, "deal_closed_at": lambda d, sym=None: f"t{int(d.ticket)}",
          "write_closed": lambda *a, **k: geschrieben.append(len(a[1]))}
    exec(compile(code, "copier_eh3", "exec"), ns)
    m = types.SimpleNamespace(file="config-test.json", magic=MAGIC, booked_deals={}, closed=[], buchung_offen={}, own_close_mark={}, closed_path="x",
                              hedge_last_vol={}, hedge_last_tickets={}, eigene_idents=[])
    return ns, mt5, m, logs, geschrieben


H = {"ticket": 500, "symbol": "NAS100", "volume": 1.4, "type": 0}
ns, mt5, m, logs, gs = welt()
ns["book_close"](m, 7, H, types.SimpleNamespace(deal=0), 1.4)
check(m.closed == [] and any(k[0] == 500 for k in m.buchung_offen) and any("nachgebucht" in x for x in logs), "Deal fehlt nach 4 Versuchen → Warteliste statt verloren")
m.own_close_mark[7] = Uhr.t                     # eigener Close frisch markiert — darf das Nachbuchen nicht aufhalten
Uhr.t += 5
mt5.hist[500] = [deal(501, 1.4, OUT, profit=34.0, msc=2000)]
ns["nachbuchen"](m)
check(len(m.closed) == 1 and m.closed[0]["deal"] == 501 and m.closed[0]["note"] == "nachgebucht" and abs(m.closed[0]["profit"] - 30.5) < 1e-9
      and m.buchung_offen == {} and gs and 7 in m.own_close_mark, "Deal kommt 5 s später → nachgebucht (profit+Kommission), own_close_mark unberührt")
ns["nachbuchen"](m)
ns["book_close"](m, 7, H, types.SimpleNamespace(deal=501), 1.4)
check(len(m.closed) == 1, "nie doppelt: zweites Nachbuchen / erneuter book_close mit demselben Deal verbucht nichts")

ns, mt5, m, logs, gs = welt()
ns["book_close"](m, 8, H, types.SimpleNamespace(deal=0), 1.4)
Uhr.t += 10
ns["nachbuchen"](m)
check(any(k[0] == 500 for k in m.buchung_offen) and m.closed == [], "nach 10 s noch nichts → weiter warten")
Uhr.t += 25
ns["nachbuchen"](m)
check(m.buchung_offen == {} and m.closed == [] and any("auch nach 30 s" in x for x in logs), "nach 30 s nichts → aufgeben, kein Eintrag (wie vor EH3)")

ns, mt5, m, logs, gs = welt()
ns["book_close"](m, 10, H, types.SimpleNamespace(deal=0), 1.4)
mt5.hist[500] = [deal(888, 1.4, OUT, reason=SL)]      # Broker-SL auf demselben Ticket im Fenster — gehört dem Schwund-Wächter
ns["nachbuchen"](m)
check(m.closed == [] and any(k[0] == 500 for k in m.buchung_offen), "EH3-2b: fremder SL-Deal im Fenster wird nicht als „nachgebucht“ verbucht")
H2 = dict(H, volume=0.7)
ns["book_close"](m, 10, H2, types.SimpleNamespace(deal=0), 0.7)
check(len(m.buchung_offen) == 2, f"EH3-2b: zwei offene Teil-Closes desselben Tickets überschreiben sich nicht ({list(m.buchung_offen)})")

ns, mt5, m, logs, gs = welt()
mt5.hist[500] = [deal(777, 1.4, OUT)]
ns["book_close"](m, 9, H, types.SimpleNamespace(deal=777), 1.4)
check(len(m.closed) == 1 and m.closed[0]["deal"] == 777 and "note" not in m.closed[0] and m.buchung_offen == {}, "Deal sofort da → wie bisher verbucht, ohne Notiz")
ns["book_close"](m, 9, H, types.SimpleNamespace(deal=777), 1.4)
check(len(m.closed) == 1 and m.buchung_offen == {}, "bekannter, schon verbuchter Deal → still übersprungen, nicht in die Warteliste")

# EH3b: ein Fehler beim Verbuchen kippt nachbuchen nicht (Hauptschleife), der Eintrag bleibt bis zur Frist
ns, mt5, m, logs, gs = welt()
ns["book_close"](m, 11, H, types.SimpleNamespace(deal=0), 1.4)
mt5.hist[500] = [deal(901, 1.4, OUT)]
ns["close_verbuchen"] = lambda *a, **k: (_ for _ in ()).throw(OSError("Platte voll"))
try:
    ns["nachbuchen"](m)
    geworfen = False
except Exception:
    geworfen = True
check(not geworfen and any(k[0] == 500 for k in m.buchung_offen) and any("Nachbuchen Ticket 500: OSError" in x for x in logs),
      "EH3b: Fehler im Verbuchen → nachbuchen wirft nicht, Eintrag bleibt, Grund im Log")
Uhr.t += 31
ns["nachbuchen"](m)
check(m.buchung_offen == {}, "EH3b: nach der Frist fällt der Eintrag auch nach Fehlern weg")

# ── Verdrahtung im Hauptlauf ──────────────────────────────────────────────────────────────────────────────────────────────────
runde = src[src.index("            for m in masters:\n                # immer_scharf"):]
check(runde.index("nachbuchen(m)") < runde.index("snap_path = os.path.join(common, m.snapshot_file)"),
      "nachbuchen läuft am Anfang jeder Master-Runde, vor allen continue-Pfaden")
check(src.count("or bool(m.buchung_offen)") == 4 and "self.buchung_offen = {}" in src, "offenes Nachbuchen hält den Update-Neustart auf (alle 4 busy-Stellen)")
nb = ast.get_source_segment(src, teile["nachbuchen"])
check("m.own_close_mark" not in nb, "nachbuchen liest own_close_mark nicht (nur der Docstring nennt es)")
print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
