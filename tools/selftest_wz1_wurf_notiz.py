#!/usr/bin/env python3
"""Selbsttest WZ1 (Master 10.11.2026 nach dem WS2-Test):
 a) tt_zschluss_wurf: Wurf-Beleg {p, zug, treffer[, nach_min]} — auch bei Nieten; Ergebnis und rnd-Züge bitgleich zur alten tt_zschluss.
 b) Speicherorte: ap_planen legt den Wurf in kette.zs_wurf (ohne Kette in mt5_baseline.zs_wurf, finaler/Klein-Trade ohne Zug „fest“),
    _tt_zeile in kette.zs_wurf des Folge-Teils.
 c) notiz_hedge_zeile_setzen: „Echo: x Lot Fusion · q …“ ersetzt statt angehängt (Doppel-Zeile in 165 von 209 Echo-Plänen 08.–10.11.),
    andere Zeilen und andere Modelle (Echo V2, Orbit V3) bleiben; beide Schreiber (ap_echo_hedge_anlegen, eh_tick) nutzen ihn.
Aufruf: python3 tools/selftest_wz1_wurf_notiz.py"""
import os
import random
import re

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
SRC = open(APP, encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


ns = {}
for name in ("_ap_spanne", "tt_zschluss_wurf", "tt_zschluss", "notiz_hedge_zeile_setzen"):
    exec(fn(name), ns)


# ── a) bitgleich zur alten Fassung ──────────────────────────────────────────────────────────────────────────────────────────────────
def alt_zschluss(param, rnd):
    p = ns["_ap_spanne"](param["schluss_pct"], rnd.random()) / 100.0
    if rnd.random() >= p:
        return None
    return {"nach_min": int(round(ns["_ap_spanne"](param["schluss_min"], rnd.random()))),
            "topstep": param.get("schluss_topstep") is True, "news_sperre": param.get("schluss_news_sperre") is not False}


std = {"schluss_pct": [5, 10], "schluss_min": [2, 120], "schluss_topstep": False, "schluss_news_sperre": True}
gleich, treffer_ok, nieten, treffer = True, True, 0, 0
for i in range(5000):
    r1, r2, r3 = random.Random(i), random.Random(i), random.Random(i)
    a = alt_zschluss(std, r1)
    b, w = ns["tt_zschluss_wurf"](std, r2)
    c = ns["tt_zschluss"](std, r3)
    if a != b or a != c or r1.getstate() != r2.getstate() or r2.getstate() != r3.getstate():
        gleich = False
    # gerundete Werte: treffer kommt aus den ungerundeten — nur bei echtem Abstand zu p muss die gerundete Probe passen
    if (b is not None) != w["treffer"] or not (0.05 <= w["p"] <= 0.10) or not (0 <= w["zug"] <= 1) \
            or (abs(w["zug"] - w["p"]) > 1e-3 and w["treffer"] != (w["zug"] < w["p"])):
        treffer_ok = False
    if b is not None and w.get("nach_min") != b["nach_min"]:
        treffer_ok = False
    if b is None:
        nieten += 1
        if "nach_min" in w:
            treffer_ok = False
    else:
        treffer += 1
check(gleich, "a: Ergebnis + rnd-Züge bitgleich zur alten tt_zschluss (5000 Seeds)")
check(treffer_ok, "a: Beleg stimmt: p in schluss_pct, treffer ⇔ zug < p, nach_min nur bei Treffer")
check(nieten > 4000 and 250 < treffer < 500, f"a: Nieten werden belegt ({nieten} Nieten, {treffer} Treffer bei 5–10 %)")
_, w0 = ns["tt_zschluss_wurf"](dict(std, schluss_pct=[0, 0]), random.Random(1))
check(w0 == {"p": 0.0, "zug": w0["zug"], "treffer": False}, "a: schluss_pct 0 → Niete mit p 0")

# ── b) Speicherorte im Quelltext ────────────────────────────────────────────────────────────────────────────────────────────────────
ap = SRC[SRC.index("\ndef ap_planen("):]
ap = ap[:ap.index("\ndef ", 10)]
check('_zs, _wurf = (None, {"aus": "fest"}) if _tt_fest else tt_zschluss_wurf(_tt_p, rnd)' in ap, "b: ap_planen würfelt mit Beleg, fest ohne Zug")
check('kette=dict(w["kette"], zs_wurf=_wurf)' in ap and 'dict(w, zs_wurf=_wurf)' in ap, "b: ap_planen: kette.zs_wurf bzw. w.zs_wurf")
check('zs_wurf=w["zs_wurf"]' in ap and 'if w.get("zs_wurf") and not w.get("kette")' in ap, "b: ohne Kette landet der Wurf in mt5_baseline.zs_wurf")
check('{"kette": dict(w["kette"], tag=tag)}' in ap, "b: mit Kette geht zs_wurf über dict(w[\"kette\"]) in mt5_baseline.kette")
tz = fn("_tt_zeile")
check('zs, k2["zs_wurf"] = tt_zschluss_wurf(param, rnd)' in tz and tz.index('k2["zs_wurf"]') < tz.index('base = {"kette": k2}'),
      "b: _tt_zeile legt den Wurf in kette.zs_wurf des Folge-Teils")
check(len(re.findall(r"\btt_zschluss\(", SRC)) == 1, "b: kein Aufrufer würfelt mehr ohne Beleg (nur noch die def von tt_zschluss)")

# ── c) Notiz-Zeile setzen ───────────────────────────────────────────────────────────────────────────────────────────────────────────
S = ns["notiz_hedge_zeile_setzen"]
kopf = "Auto-Planer · Tag 2/4 · Neben · bisher -3.918 $ → TP 650 $ / SL 1.243 $ · Balance 190.986 (Nachlesung)"
z1 = "Echo: 0,32 Lot Fusion · q 0,0110 €/$ (Kontowert 121 € ÷ Polster ÷ 1,0)"
z2 = "Echo: 0,35 Lot Fusion · q 0,0112 €/$ (Kontowert 127 € ÷ Polster ÷ 1,0)"
n1 = S(kopf, z1)
check(n1 == kopf + "\n" + z1, "c: erste Zeile wird angehängt")
check(S(n1, z1) == n1, "c: zweites Schreiben derselben Zeile → keine Doppel-Zeile")
check(S(n1, z2) == kopf + "\n" + z2, "c: neuer Wert ersetzt den alten")
check(S(kopf + "\n" + z1 + "\n" + z1, z2) == kopf + "\n" + z2, "c: alte Doppel-Zeile wird beim nächsten Schreiben bereinigt")
v2 = "Echo V2: ohne Hedge"
o3 = "Orbit V3 (finaler Tradeify, Gegenhedge): 3,20 Lot Fusion · q 0,0450 €/$"
check(S(kopf + "\n" + v2 + "\n" + o3 + "\n" + z1, z2) == kopf + "\n" + v2 + "\n" + o3 + "\n" + z2, "c: Echo V2 / Orbit V3 und Kopf bleiben")
check(S(None, z1) == z1 and S("", z1) == z1, "c: leere Notiz")
check(S(kopf + "\nEcho: Hand-Hinweis", z1) == kopf + "\nEcho: Hand-Hinweis\n" + z1, "c: andere „Echo:“-Zeile ohne „Lot Fusion · q“ bleibt")
check(S("Kopf\r\n" + z1 + "\r\nEnde", z2) == "Kopf\r\nEnde\n" + z2, "c: CRLF + Zeile in der Mitte: ersetzt, neue Zeile ans Ende")
t3a = "Orbit (finaler Tradeify, Gegenhedge): 3,20 Lot Fusion · q 0,0450 €/$ · Blow +120 € · Pass −80 €"
t3b = "Orbit (finaler Tradeify, Gegenhedge): 3,40 Lot Fusion · q 0,0460 €/$ · Blow +125 € · Pass −82 €"
p2a = "Orbit Prio 2: 1,10 Lot Fusion · q 0,0300 €/$ (Kontowert 90,00 € ÷ Polster 3000 $ ÷ 1,0) · Hedge zu am Boden 47000 $"
p2b = "Orbit Prio 2: 1,20 Lot Fusion · q 0,0310 €/$ (Kontowert 93,00 € ÷ Polster 3000 $ ÷ 1,0) · Hedge zu am Boden 47000 $"
check(S(S(kopf, t3a), t3b) == kopf + "\n" + t3b and S(S(kopf, p2a), p2b) == kopf + "\n" + p2b, "c: Orbit V3 / Orbit Prio 2 ersetzen ihre eigene Zeile")
check(S(kopf + "\n" + z1 + "\n" + t3a, p2a) == kopf + "\n" + z1 + "\n" + t3a + "\n" + p2a, "c: verschiedene Modelle verdrängen sich nicht")
check(SRC.count("notiz_hedge_zeile_setzen(p.get(\"notes\"), (f\"{MODELL_NAME['orbit']} (finaler") == 1
      and SRC.count("notiz_hedge_zeile_setzen(p.get(\"notes\"), (f\"{MODELL_NAME['orbit_prio2']}:") == 1, "c: Orbit V3 (tfh) und Orbit Prio 2 nutzen den Helfer")
check(not re.search(r'rstrip\(\) \+ "\\n" \+ \(f"\{MODELL_NAME', SRC), "c: kein Hedge-Schreiber hängt mehr direkt an")
check(SRC.count("notiz_hedge_zeile_setzen(z.get(\"notes\")") == 1 and SRC.count("notiz_hedge_zeile_setzen(p.get(\"notes\"), (f\"{MODELL_NAME['echo']}") == 1,
      "c: ap_echo_hedge_anlegen und eh_tick setzen die Zeile über den Helfer")
check(not re.search(r'rstrip\(\) \+ "\\n" \+ \(f"\{MODELL_NAME\[\'echo\'\]\}: \{h\[\'lots\'\]', SRC), "c: kein Echo-Schreiber hängt mehr direkt an")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: " + "; ".join(FEHLER))
raise SystemExit(1 if FEHLER else 0)
