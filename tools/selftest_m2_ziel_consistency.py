#!/usr/bin/env python3
"""Selbsttest M2 — Consistency vor „Ziel erreicht" (05.11.2026, Vorfall 04.11. EzPoker Tradeify 150k: Balance über dem Ziel, größter Tag über
40 % des Gewinns → die Firma zählte es nicht, die Ziel-Wache setzte trotzdem „Ziel erreicht → Review"). Rein rechnend mit den echten Funktionen
aus app.py (zw_ziel, zw_cons_tage, zw_cons_ziel, ap_konten_stand_zeile, ap_regel_konto, ap_konto_rechnen), dazu Verdrahtung in zw_tick/ap_planen
als Text. Ohne Netz. Werte frei erfunden (keine echten Konten). Aufruf: python3 tools/selftest_m2_ziel_consistency.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_boden_konto", "ap_kette_regel", "ap_kette_mll",
              "ap_kette_trade1", "ap_konto_rechnen", "ap_klein_trade", "_ap_de", "liq_peak", "_ap_peaks", "ap_boden_sicher",
              "_ap_norm", "_ap_tz", "_ap_ts", "ap_consistency_etappe", "ap_konto_flex", "ap_regel_flex", "ap_regel_konto", "zw_ziel",
              "zw_cons_tage", "zw_cons_moeglich", "zw_cons_ziel", "zw_erreicht", "ap_konten_stand_zeile")
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS", "AP_PUFFER_PKT",
              "AP_CFD_ROUTEN", "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT", "AP_SL_HINTER_BODEN", "ZW_CONS_FIRMEN")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}
    teile = [re.search(rf"^{k} = .*$", SRC, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = SRC.index(f"\ndef {name}(") + 1
        teile.append(SRC[i:SRC.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


ns = lade()
zw_ziel, cons_tage, cons_ziel, rk, rechnen = ns["zw_ziel"], ns["zw_cons_tage"], ns["zw_cons_ziel"], ns["ap_regel_konto"], ns["ap_konto_rechnen"]

# Tradeify-artige Regel 150k: Ziel 6 % = 9.000 $, TP-Deckel 3.600 $ = 40 % (Firmen-Consistency wie die Konten-Liste)
TRADEIFY = {"namen": ["Tradeify"], "groessen": [150000], "ziel_pct": {"challenge": 6}, "boden": "nachziehend", "dd_usd": 4500,
            "phasen": {"challenge": {"menge": [2, 2], "tp": [3450, 3550], "tp_max": 3600, "sl": [1500, 1500]}}}
APEX = dict(TRADEIFY, namen=["Apex"])   # gleicher Deckel, aber KEINE Consistency-Regel der Firma
U = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}


def konto(firm="Tradeify", cons=None, typ="challenge", kid="k1"):
    return {"id": kid, "firm": firm, "account_type": typ, "consistency_pct": cons}


def plan(tag, pl, status="completed", kid="k1"):
    return {"master_account_id": kid, "status": status, "master_pl": pl, "ended_at": f"{tag}T14:00:00+00:00"}


EZ = [plan("2026-11-01", 3800), plan("2026-11-02", 3000), plan("2026-11-03", 2400)]   # Gewinn 9.200 ≥ 9.000, größter Tag 3.800 > 40 % × 9.200
T_EZ = cons_tage(EZ, "k1")

# ── zw_cons_tage: Berlin-Tag des Trade-Endes, completed + review, fremde Konten / ohne P&L raus
tt = cons_tage([plan("2026-11-01", 100), {"master_account_id": "k1", "status": "review", "master_pl": 50, "ended_at": "2026-11-01T23:30:00+00:00"},
                plan("2026-11-01", 999, kid="k2"), plan("2026-11-01", None), plan("2026-11-01", 70, status="planned")], "k1")
check(tt == {"2026-11-01": 100.0, "2026-11-02": 50.0}, f"Tage: Berlin-Tag (23:30 UTC = nächster Tag), review zählt, fremd/ohne P&L/geplant nicht ({tt})")

# ── EzPoker-Fall: Firmen-Consistency 40 %, Balance 159.200 über dem Ziel 159.000 → noch NICHT erreicht
c = cons_ziel(TRADEIFY, konto(), 159200, T_EZ)
check(c and c["p"] == 40.0 and c["quelle"] == "firma" and c["groesster_tag"] == 3800 and c["ziel_cons"] == 159500 and not c["erfuellt"],
      f"EzPoker: 40 % Firma, größter Tag 3.800 → Required profit 9.500, Ziel 159.500, nicht erfüllt ({c})")
z = zw_ziel(dict(rk(TRADEIFY, konto(), 159200), _ziel_min=c["ziel_cons"]), "challenge", 159200)
check(z == (159500.0, 150000.0) and not ns["zw_erreicht"](z[0], 159200, "challenge"), f"Ziel-Wache: Ziel 159.500 → „Ziel erreicht“ bleibt aus ({z})")
check(zw_ziel(rk(TRADEIFY, konto(), 159200), "challenge", 159200) == (159000.0, 150000.0), "ohne _ziel_min: Ziel wie bisher 159.000")

# Planer: Rest-Trade bis 159.500 statt „Ziel erreicht — Phase umstellen"
r0 = rk(TRADEIFY, konto(), 159200)
w0, g0 = rechnen(r0, "challenge", 159200, U)
w1, g1 = rechnen(dict(r0, _ziel_min=c["ziel_cons"], _cons=c), "challenge", 159200, U)
check(w0 is None and "Ziel erreicht" in str(g0), f"vorher: Planer sagt „Ziel erreicht“ ({g0})")
check(w1 and not g1 and w1["ziel"] == 159500 and w1["rest"] == 300 and w1["tp"] >= 300 and "Rest bis Ziel" in w1["stufe"]
      and "Consistency 40 %" in w1["stufe"] and "Ziel 159.500 $" in w1["stufe"], f"nachher: Rest-Trade 300 $ bis 159.500 mit Hinweis ({w1 and w1['stufe']}, TP {w1 and w1['tp']})")

# nach dem Rest-Trade (+350 an einem neuen Tag): Gewinn 9.550 ≥ 9.500 → erfüllt
c2 = cons_ziel(TRADEIFY, konto(), 159550, cons_tage(EZ + [plan("2026-11-04", 350)], "k1"))
check(c2 and c2["erfuellt"] and c2["ziel_cons"] == 159500, f"nach dem Rest-Trade: erfüllt ({c2})")

# ── Konto-Wert schlägt Firma: 50 % (Addon) → Required 7.600 < 9.000 → Ziel bleibt 159.000, erfüllt
c3 = cons_ziel(TRADEIFY, konto(cons=50), 159200, T_EZ)
check(c3 and c3["quelle"] == "konto" and c3["p"] == 50 and c3["ziel_cons"] == 159000 and c3["erfuellt"], f"Konto 50 % geht vor: erfüllt ({c3})")
c4 = cons_ziel(APEX, konto(firm="Apex", cons=30), 159200, T_EZ)
check(c4 and c4["quelle"] == "konto" and c4["ziel_cons"] == 150000 + 12667 and not c4["erfuellt"], f"Konto-Wert wirkt auch bei Apex (30 % → 12.667) ({c4})")

# ── Lucid / Topstep: feste 50 % (kein tp_max nötig), Firmen-Feld consistency_pct überschreibt die Vorgabe (später Slider je Firma)
LUCID = dict(TRADEIFY, namen=["Lucid Trading"], phasen={"challenge": {"menge": [2, 2], "tp": [3450, 3550], "sl": [1500, 1500]}})
c5 = cons_ziel(LUCID, konto(firm="Lucid Trading"), 159200, T_EZ)
check(c5 and c5["p"] == 50 and c5["ziel_cons"] == 159000 and c5["erfuellt"], f"Lucid 50 %: 3.800 ÷ 0,5 = 7.600 < 9.000 → erfüllt ({c5})")
c6 = cons_ziel(LUCID, konto(firm="Lucid Trading"), 159200, cons_tage([plan("2026-11-01", 5000), plan("2026-11-02", 4200)], "k1"))
check(c6 and c6["ziel_cons"] == 160000 and not c6["erfuellt"], f"Lucid: größter Tag 5.000 → Ziel 160.000 ({c6})")
c7 = cons_ziel(dict(LUCID, namen=["Topstep"]), konto(firm="Topstep"), 159200, cons_tage([plan("2026-11-01", 5000), plan("2026-11-02", 4200)], "k1"))
check(c7 and c7["p"] == 50 and c7["ziel_cons"] == 160000, f"Topstep Combine 50 % ({c7})")
check(cons_ziel(dict(TRADEIFY, consistency_pct=None), konto(), 159200, T_EZ) is None, "Firmen-Feld consistency_pct = null → keine Consistency (Tradeify Growth)")
c8 = cons_ziel(dict(APEX, consistency_pct=45), konto(firm="Apex"), 159200, T_EZ)
check(c8 and c8["p"] == 45 and c8["quelle"] == "firma", f"Firmen-Feld consistency_pct 45 schlägt die Vorgabe ({c8})")
c9 = cons_ziel(dict(TRADEIFY, consistency_pct=None), konto(cons=40), 159200, T_EZ)
check(c9 and c9["quelle"] == "konto" and c9["ziel_cons"] == 159500, f"Konto-Wert schlägt auch das Firmen-Feld ({c9})")

# ── Rest unter 100 $ (von Hand): Hinweis auf die Consistency im Grund (Fremd-Review)
c_k = cons_ziel(TRADEIFY, konto(), 159440, T_EZ)
w_k, g_k = rechnen(dict(rk(TRADEIFY, konto(), 159440), _ziel_min=c_k["ziel_cons"], _cons=c_k), "challenge", 159440, U)
check(w_k is None and "von Hand" in g_k and "Consistency 40 %" in g_k and "Ziel 159.500 $" in g_k, f"Rest 60 $ von Hand mit Consistency-Hinweis ({g_k})")

# ── Vorprüfung: nur wo Consistency gelten kann, wird überhaupt gelesen
mg = ns["zw_cons_moeglich"]
check(mg(TRADEIFY, konto()) and mg(LUCID, konto(firm="Lucid Trading")) and mg(APEX, konto(firm="Apex", cons=30)) and mg(dict(APEX, consistency_pct=45), konto(firm="Apex")),
      "Vorprüfung ja: Tradeify, Lucid, Konto-Wert, Firmen-Feld")
check(not mg(APEX, konto(firm="Apex")) and not mg(dict(TRADEIFY, consistency_pct=None), konto()) and not mg(TRADEIFY, konto(typ="phase1")),
      "Vorprüfung nein: Apex ohne Konto-Wert, Firmen-Feld null, CFD-Phase")

# ── ohne Consistency unverändert
check(cons_ziel(APEX, konto(firm="Apex"), 159200, T_EZ) is None, "Apex ohne Konto-Wert: tp_max ist nur Tagesdeckel → keine Consistency")
ohne = dict(TRADEIFY, phasen={"challenge": {"menge": [2, 2], "tp": [3450, 3550], "sl": [1500, 1500]}})
check(cons_ziel(ohne, konto(), 159200, T_EZ) is None, "Firma ohne tp_max und ohne Konto-Wert → keine Consistency")
check(cons_ziel(TRADEIFY, konto(), 159200, {}) is None and cons_ziel(TRADEIFY, konto(), 159200, None) is None, "keine Trades → keine Consistency")
check(cons_ziel(TRADEIFY, konto(typ="phase1"), 159200, T_EZ) is None, "nur Challenge-Konten (CFD-Phasen unberührt)")
check(cons_ziel(TRADEIFY, konto(), 159200, cons_tage([plan("2026-11-01", -500)], "k1")) is None, "nur Verlusttage → keine Consistency")
gleich = cons_ziel(TRADEIFY, konto(), 159200, cons_tage([plan("2026-11-01", 3600), plan("2026-11-02", 3000), plan("2026-11-03", 2600)], "k1"))
check(gleich and gleich["ziel_cons"] == 159000 and gleich["erfuellt"], f"größter Tag genau 40 % vom Ziel → Ziel bleibt ({gleich})")
w_ohne, g_ohne = rechnen(r0, "challenge", 155000, U)
w_mit, g_mit = rechnen(dict(r0, _ziel_min=None), "challenge", 155000, U)
check(w_ohne == w_mit and g_ohne == g_mit and w_ohne and "Consistency" not in w_ohne["stufe"], "Planer ohne Consistency-Ziel: Rechnung 1:1 wie vorher")
w_lo, _g = rechnen(dict(r0, _ziel_min=158000.0), "challenge", 155000, U)
check(w_lo == w_ohne, "Consistency-Ziel unter dem Regel-Ziel ändert nichts")

# ── Verdrahtung
tk = SRC[SRC.index("def zw_tick("):SRC.index("# ZIEL-WACHE JETZT")]
check('not (flags.get(aid) or {}).get("ziel_erreicht_at")' in tk and "float(bal) >= _z0[0] and zw_cons_moeglich(regel0, a)" in tk and "cons_tage = _zw_cons_tage_laden(" in tk
      and "except Exception as e:   # Lesefehler" in tk and "if cons_tage is False:" in tk
      and 'regel = dict(regel, _ziel_min=cons["ziel_cons"])' in tk and "zw_cons_ziel(regel0, a, bal" in tk,
      "zw_tick: nur unmarkierte Challenge-Konten am Ziel, Trades einmal je Lauf, Firmen-Regel ungemischt, Ziel angehoben")
pl = SRC[SRC.index("def ap_planen("):SRC.index("# TAGESDECKEL JE FIRMA (19.10.2026")]
check('regel_kk = dict(regel_kk, _ziel_min=_cz["ziel_cons"], _cons=_cz)' in pl and '"regel": regel_kk' in pl
      and 'a.get("account_type") == "challenge" and not a.get("ziel_erreicht_at") and zw_cons_moeglich(regel, a)' in pl
      and "_ct = _zw_cons_tage_laden([aid]).get(aid) or {}" in pl and "_ct = zw_cons_tage(eig, aid)" in pl,
      "ap_planen: Consistency-Ziel nur für unmarkierte Konten, Tage aus allen Trades wie die Ziel-Wache (Rückfall 30 Tage)")
check('ZW_CONS_FIRMEN = {"tradeify": "tp_max", "lucid": 50, "topstep": 50}' in SRC and '"apex"' not in SRC[SRC.index("ZW_CONS_FIRMEN = {"):SRC.index("ZW_CONS_FIRMEN = {") + 80],
      "Vorgabe: Tradeify (TP-Deckel), Lucid 50, Topstep 50 — Apex nie")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
