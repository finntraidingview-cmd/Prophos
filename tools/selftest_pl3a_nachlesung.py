#!/usr/bin/env python3
"""Selbsttest PL3-A (Finn 06.11.2026: „ja dann bau den scheiß"): Puls-Nachlesung bei Trades mit Hedge (Orbit V3, Orbit Prio 2, Winning Day mit
Fusion-Hedge, Nova) nach 2–10 min statt 1–120 min — weiter je Plan gestreut (FNV aus der Plan-ID, Jitter-Regel), nie eine feste Zeit; die
Userscript-Frist nimmt dieselbe Zeit statt fest 10 min. Orbit V2 ohne Hedge (1–120 min) und die Topstep-Kette (1–35 min) bleiben.
Ohne Node: die FNV-Rechnung wird hier nachgebaut und gegen die Spanne geprüft, dazu die Verdrahtung im Quelltext (prophos.html).
Aufruf: python3 tools/selftest_pl3a_nachlesung.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


def fnv(id_):
    h = 2166136261
    for ch in str(id_):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF   # Math.imul(h ^ c, 16777619) >>> 0 (ASCII-IDs)
    return h


def nachlese_s(id_, hedge, kette=False):
    h = fnv(id_)
    if kette:
        return 60 + (h % 2041)
    if hedge:
        return 120 + (h % 481)
    return 60 + (h % 7141)


ids = [f"plan-{i}-{i * 7919:x}" for i in range(3000)]
w = [nachlese_s(i, True) for i in ids]
ok(min(w) >= 120 and max(w) <= 600, f"Hedge-Trade: 120–600 s (gesehen {min(w)}–{max(w)} s)")
ok(len(set(w)) > 400, f"gestreut, keine feste Zeit ({len(set(w))} verschiedene Werte auf {len(ids)} Pläne)")
ok(nachlese_s("abc", True) == nachlese_s("abc", True), "je Plan dieselbe Zeit (alle Tabs gleich, kein doppelter Login)")
v2 = [nachlese_s(i, False) for i in ids]
ok(min(v2) >= 60 and max(v2) <= 7200, f"Orbit V2 ohne Hedge unverändert 60–7.200 s ({min(v2)}–{max(v2)})")

src = html
f = src[src.index("  function tvV2HedgeTrade(p){"):src.index("  window._tvV2NachleseMs = tvV2NachleseMs")]
ok("return (p.route === 'tvv2' && (v3 || he > 0)) || (p.route === 'tsv2' && he > 0)" in f, "Hedge-Trade = tvv2 mit Orbit V3 oder hedge_eur > 0, tsv2 mit hedge_eur > 0 (Nova); Echo zählt nicht")
ok("p.hedgeEur != null ? p.hedgeEur : p.hedge_eur" in f and "p.orbitV3 || p.orbit_v3" in f, "camel (tradePlans) und snake (Live-Trades fremder IDs)")
ok("if(k) return (60 + (h % 2041)) * 1000" in f and "if(tvV2HedgeTrade(pk || plan)) return (120 + (h % 481)) * 1000" in f
   and f.index("if(k) return") < f.index("if(tvV2HedgeTrade(") and "return (60 + (h % 7141)) * 1000" in f,
   "Reihenfolge: Topstep-Kette zuerst (1–35 min), dann Hedge 2–10 min, sonst 1–120 min")
g = src[src.index("  function tvV2EndlesungGrund(p, jetzt, force, steht){"):src.index("  function tvV2EndlesungFaellig(")]
ok("< tvV2NachleseMs(p.id, p)) return 'Orbit/Winning Day: P&L kommt aus dem Userscript" in g and "< 10 * 60000) return 'Orbit/Winning Day" not in g,
   "Userscript-Frist = dieselbe gestreute Zeit statt fest 10 min (sonst Puls frühestens nach 10 min)")
ok("jetzt < endeMs + tvV2NachleseMs(p.id, p)) return `Nachlesung ab" in g and "tvV2HedgeTrade(p) ? 'Trade mit Hedge: 2–10 min Zufall'" in g,
   "Nachlesung ab … nutzt den Plan, Text nennt 2–10 min bei Trades mit Hedge")
ok("const tvV2NachleseAb = (id, endeIso, plan) =>" in src and "tvV2NachleseAb(t.id, e.at || t.ended_at, t)" in src,
   "Live-Trades/Radar fremder IDs geben die Zeile mit (Plan nicht in tradePlans)")
e = src[src.index("  function endlesungStatus(fin, planStatus, jetzt, pid, route, mitStartBalance, zeile){"):src.index("  function endlesungZeileHtml(")]
ok(e.count("tvV2NachleseAb(pid, fin.at, zeile)") == 2 and "tvV2NachleseAb(pid, fin.at)" not in e,
   "Abhak-Zeile „Puls bestätigt ab …“ + „Lesung verloren“ rechnen mit derselben Hedge-Zeit wie der Puls-Tab")
ok("endlesungZeileHtml(pid, x.endlesung || x.final, x.status, 'data-mwd-lesen', undefined, x)" in src and "balance_start === 'number') : undefined, zeile || plan)" in src,
   "WD-Abhaken fremder IDs (/admin/wd-heute, Zeile mit route + hedge_eur) gibt die Zeile mit, eigene Pläne den Plan")
ok("const TV_ENDLESUNG_LOGIN_PAUSE_S = 30 * 60, TV_ENDLESUNG_LOGIN_MAX = 2" in src, "Login-Bremse unverändert (30 min nach Login-Fehler, max. 2)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
