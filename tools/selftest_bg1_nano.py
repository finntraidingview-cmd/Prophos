#!/usr/bin/env python3
"""Selbsttest BG1 (Finn 19.11.2026): Blue Guardian 2 Step NANO neben Standard — Variante über regel.flex (ab_dd_pct 10, Kennung
accounts.max_drawdown) aus sql/2026-11-19_bg1_blue_guardian_nano.sql, dazu der Kontowert der Variante (app.py ap_kw_regel_konto).

Aufruf:  python3 tools/selftest_bg1_nano.py      (ohne Netz, Platzhalter-Konten)
Geprüft: Erkennung Nano (10.000) / Standard (8.000, leer); Nano-Plan P1/P2 (Ziel 108.000 / 105.000, SL ≤ 2.600, Tagesgrenze 3 %, kein
Gewinntag-Weg); Standard-Plan, Ziel-Wache, Boden und Kontowert bitgleich mit und ohne flex; Nano-Boden 90.000; Kontowert-Satz Nano
0,0145 €/$ (Kauf 145 / DD 10.000) statt 0,0375; FundingPips Flex (flex ohne kauf_eur) behält bitgleich den Firmen-Kontowert."""
import copy
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


# blueguardian-Eintrag wie live (auto_plan_regeln id 1, gelesen 19.11.2026)
BG = {"namen": ["blueguardian"], "planen": True, "route": "mt5v2", "dd_pct": 8, "boden": "statisch", "groessen": [100000],
      "wert_groessen": [100000, 200000], "kauf_eur": {"100000": 300, "200000": 600}, "ziel_pct": {"phase1": 8, "phase2": 4},
      "gewinntage": {"tp": [1000, 1100]},
      "phasen": {"phase1": {"sl": [2700, 3150], "tp": [4950, 5850], "menge": [4, 5.3], "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 8,
                            "menge_schritt": 0.1},
                 "phase2": {"sl": [2700, 3150], "tp": [2700, 3150], "menge": [4, 5.3], "puffer": [25, 50], "ziel_pct": 4, "boden_pct": 8,
                            "menge_schritt": 0.1}}}
# flex wie in der SQL-Datei
FLEX = {"name": "Nano", "ab_dd_pct": 10, "dd_pct": 10, "kauf_eur": {"100000": 145},
        "je_groesse": {"100000": {"dd_pct": 10, "ziel_pct": {"phase1": 8, "phase2": 5}, "daily_pct": 3, "gewinntage": None,
                                  "phasen": {"phase1": {"sl": [2000, 2500], "tp": [4950, 5850], "menge": [4, 5.3], "menge_schritt": 0.1,
                                                        "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10},
                                             "phase2": {"sl": [2000, 2500], "tp": [2700, 3150], "menge": [4, 5.3], "menge_schritt": 0.1,
                                                        "puffer": [25, 50], "ziel_pct": 5, "boden_pct": 10}}}}}
BGN = dict(copy.deepcopy(BG), flex=copy.deepcopy(FLEX))
U = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
U_HOCH = {"tp": 1.0, "sl": 1.0, "menge": 1.0, "puffer": 1.0}


def konto(dd, typ="phase1", **kw):
    return dict({"id": "00000000-0000-0000-0000-0000000000b1", "firm": "Blue Guardian", "account_type": typ, "max_drawdown": dd}, **kw)


def plan(regel, k, bal, u=U, **kw):
    return app.ap_konto_rechnen(app.ap_regel_konto(regel, k, bal), k["account_type"], bal, u, ppl=10.0, **kw)


def main():
    F = app.ap_konto_flex
    print("1 Erkennung Nano / Standard")
    check(F(BGN, konto(10000), 100000.0) is True, "Max DD 10.000 → Nano")
    check(F(BGN, konto(8000), 100000.0) is False, "Max DD 8.000 → Standard")
    check(F(BGN, konto(None), 100000.0) is False, "ohne Max DD → Standard")
    check(F(BGN, konto(10000), 106500.0) is True, "Nano auch mit Balance 106.500 (Größe aus der Balance)")

    print("2 Nano-Plan")
    for bal in (100000.0, 103000.0):
        w, g = plan(BGN, konto(10000), bal)
        check(w is not None and w["ziel"] == 108000 and w["sl"] <= 2500, f"P1 bei {bal:,.0f}: Ziel 108.000, SL {w and w['sl']} ≤ 2.500 ({g})")
        check(w is not None and w["tages_grenze_usd"] == round(bal * 0.03, 2), f"P1 bei {bal:,.0f}: Tagesgrenze 3 % = {w and w['tages_grenze_usd']}")
    w, g = plan(BGN, konto(10000, "phase2"), 100000.0)
    check(w is not None and w["ziel"] == 105000, f"P2: Ziel 105.000 (5 %) → {w and w['ziel']} ({g})")
    w, g = plan(BGN, konto(10000), 100000.0, U_HOCH, heute_verlust=1000.0)
    check(w is not None and w["sl"] <= 3000 - 1000 - 100, f"Tagesgrenze mit 1.000 $ Verlust heute: SL {w and w['sl']} ≤ 1.900")
    w, g = plan(BGN, konto(10000), 100000.0, tage=(0, 3))
    check(w is not None and "Gewinntag" not in str(w.get("stufe")) and w["tp"] >= 4950,
          f"Nano mit Tage-Zähler: kein Gewinntag-Trade (TP {w and w['tp']}, {w and w['stufe']})")
    w, g = plan(BGN, konto(10000), 91000.0)
    check(w is not None and w["sl"] <= 91000 - 90000 + app.AP_SL_HINTER_BODEN, f"Nano bei 91.000: SL am Boden 90.000 gekappt → {w and w['sl']}")

    print("3 Standard bitgleich mit und ohne flex")
    for typ, bal, tage in (("phase1", 100000.0, None), ("phase1", 104200.0, None), ("phase2", 101000.0, (1, 3)), ("phase2", 100000.0, (0, 3))):
        for k in (konto(8000, typ), konto(None, typ)):
            a1 = plan(BG, k, bal, tage=tage)
            a2 = plan(BGN, k, bal, tage=tage)
            check(a1 == a2, f"Plan {typ} {bal:,.0f} DD {k['max_drawdown']} tage {tage}: gleich")
        check(app.zw_ziel(app.ap_regel_konto(BG, konto(8000, typ), bal), typ, bal) ==
              app.zw_ziel(app.ap_regel_konto(BGN, konto(8000, typ), bal), typ, bal), f"Ziel-Wache {typ} {bal:,.0f}: gleich")
        check(app.ap_boden_konto(app.ap_regel_konto(BG, konto(8000, typ), bal), typ, bal) ==
              app.ap_boden_konto(app.ap_regel_konto(BGN, konto(8000, typ), bal), typ, bal), f"Boden {typ} {bal:,.0f}: gleich")

    print("4 Nano Ziel-Wache + Boden")
    zz = app.zw_ziel(app.ap_regel_konto(BGN, konto(10000, "phase2"), 102000.0), "phase2", 102000.0)
    check(zz and zz[0] == 105000, f"Ziel-Wache Nano P2 = 105.000 → {zz}")
    bo = app.ap_boden_konto(app.ap_regel_konto(BGN, konto(10000), 100000.0), "phase1", 100000.0)
    check(bo.get("boden") == 90000, f"Boden Nano = 90.000 → {bo}")

    print("5 Kontowert / Echo-Hedge-Satz")
    kn = app.ap_kontowert_konto(konto(10000), 100000.0, [BGN])
    check(kn.get("wert_eur") == 145 and abs((kn.get("satz_eur_pro_usd") or 0) - 0.0145) < 1e-9,
          f"Nano P1 frisch: Wert 145 €, Satz 0,0145 → {kn.get('wert_eur')}, {kn.get('satz_eur_pro_usd')}")
    kn2 = app.ap_kontowert_konto(konto(10000, "phase2"), 100000.0, [BGN])
    check(kn2.get("wert_eur") == 261, f"Nano P2 frisch: 145 × 18.000 / 10.000 = 261 → {kn2.get('wert_eur')}")
    kn3 = app.ap_kontowert_konto(konto(10000), 100000.0, [BGN], kauf_eur=150)
    check(kn3.get("wert_eur") == 150 and kn3.get("quelle") == "kauf_echt", f"echter Kauf 150 € gilt (plausibel zu 145) → {kn3.get('wert_eur')}")
    for typ, bal in (("phase1", 100000.0), ("phase1", 103000.0), ("phase2", 101000.0), ("funded_cfd", 100500.0)):
        for kauf in (None, 310):
            check(app.ap_kontowert_konto(konto(8000, typ), bal, [BG], kauf) == app.ap_kontowert_konto(konto(8000, typ), bal, [BGN], kauf),
                  f"Standard-Kontowert {typ} {bal:,.0f} Kauf {kauf}: gleich")
    ks = app.ap_kontowert_konto(konto(8000), 100000.0, [BGN])
    check(abs((ks.get("satz_eur_pro_usd") or 0) - 0.0375) < 1e-9, f"Standard-Satz bleibt 0,0375 → {ks.get('satz_eur_pro_usd')}")
    check(app.ap_kw_regel_konto(BGN, konto(10000), None) is BGN, "ohne Balance: Firmen-Regel (kein Raten)")

    print("5b Gewicht/Delta (_ap_bewerten, Planer + Waage — Prüfer S2)")

    def bew(firmen, k, bal):
        ctx = {"firmen": firmen, "kauf": {}, "ppl": {}, "ppl_firma": {"blueguardian": (10.0, "NAS100", "Lots")}}
        return app._ap_bewerten(ctx, dict(k, user_id="00000000-0000-0000-0000-0000000000a1"), bal, 4.5, "mt5v2", "NAS100", "buy", 5400, 2450)
    bn, bn2 = bew([BGN], konto(10000), 100000.0), bew([BGN], konto(10000, "phase2"), 100000.0)
    check(abs(((bn["kw"] or {}).get("satz") or 0) - 0.0145) < 1e-9, f"Nano P1 Satz 0,0145 → {(bn['kw'] or {}).get('satz')}")
    check(abs(((bn2["kw"] or {}).get("satz") or 0) - 0.0261) < 1e-4, f"Nano P2 Satz ≈ 0,0261 → {(bn2['kw'] or {}).get('satz')}")
    for typ, bal in (("phase1", 100000.0), ("phase2", 102000.0)):
        check(bew([BG], konto(8000, typ), bal) == bew([BGN], konto(8000, typ), bal), f"Standard _ap_bewerten {typ} {bal:,.0f}: gleich")

    print("6 FundingPips Flex (flex ohne kauf_eur) bitgleich")
    FP = {"namen": ["fundingpips"], "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [50000, 100000], "wert_groessen": [50000, 100000],
          "ziel_pct": {"phase1": 8, "phase2": 5}, "kauf_eur": {"50000": 240, "100000": 464},
          "phasen": {"phase1": {"sl": [2500, 3500], "tp": [3500, 4000], "menge": [1, 1.5], "puffer": [50, 75], "boden_pct": 10, "menge_schritt": 0.1}},
          "flex": {"ab_dd_pct": 12, "dd_pct": 12, "je_groesse": {"100000": {"dd_pct": 12, "ziel_pct": {"phase1": 10, "phase2": 5}, "phasen": {}}}}}
    kf = dict(konto(12000), firm="FundingPips")
    check(app.ap_kw_regel_konto(FP, kf, 100000.0) is FP, "FP-Flex-Konto: Kontowert-Regel = Firma (unverändert)")
    p_alt = app.ap_kw_param(FP)
    v_alt = app.ap_kontowert("phase1", 100000.0, p_alt)
    v_neu = app.ap_kontowert_konto(kf, 100000.0, [FP])
    check(v_neu.get("wert_eur") == v_alt["wert"] and v_neu.get("satz_eur_pro_usd") == v_alt["satz"], f"FP-Flex-Kontowert wie bisher ({v_alt['wert']} €)")

    print("7 Schablonen Standard + Nano (Teil C): Reset wählt nach Max DD")
    VS = [{"name": "Blue Guardian 100k Standard Phase 1", "firm": "Blue Guardian", "account_type": "phase1", "account_size": 100000,
           "purchase_cost": 300, "max_drawdown": 8000, "aktiv": True},
          {"name": "Blue Guardian 100k Nano Phase 1", "firm": "Blue Guardian", "account_type": "phase1", "account_size": 100000,
           "purchase_cost": 145, "max_drawdown": 10000, "aktiv": True},
          {"name": "Tradeify Select 150k", "firm": "Tradeify", "account_type": "challenge", "account_size": 150000, "purchase_cost": 213,
           "max_drawdown": 4500, "aktiv": True}]
    VF = app.konto_vorlage_finden
    check(VF(VS, "Blue Guardian", "phase1", 100000)["name"].endswith("Standard Phase 1"), "ohne dd: erste = Standard (wie bisher)")
    check(VF(VS, "Blue Guardian", "phase1", 100000, dd=10000)["name"].endswith("Nano Phase 1"), "dd 10.000 → Nano-Schablone")
    check(VF(VS, "Blue Guardian", "phase1", 100000, dd="8000")["name"].endswith("Standard Phase 1"), "dd 8.000 → Standard-Schablone")
    check(VF(VS, "Blue Guardian", "phase1", 100000, dd=12345)["name"].endswith("Standard Phase 1"), "dd ohne Treffer → erste")
    check(VF(VS, "Tradeify", "challenge", 150000, dd=4000) is VS[2] and VF(VS, "Tradeify", "challenge", 150000) is VS[2],
          "eine Schablone je Firma × Typ × Größe: dd ändert nichts")
    check(VF(VS, "Blue Guardian", "phase2", 100000, dd=10000) is None, "keine Phase-2-Schablone → None wie bisher")
    alt = {"firm": "Blue Guardian", "account_type": "phase2", "account_size": 100000, "max_drawdown": 10000, "purchase_cost": 0,
           "name": "100k 700001 → Phase 2"}
    z = app.konto_reset_zeile(alt, "700002", VF(VS, "Blue Guardian", app.konto_reset_typ(alt["account_type"]), 100000, dd=alt["max_drawdown"]))
    check(z["purchase_cost"] == 145 and z["max_drawdown"] == 10000 and z["account_type"] == "phase1" and z["name"] == "100k 700002 → Phase 1",
          f"Reset Nano: Kauf 145, Max DD 10.000, Phase 1 → {z.get('purchase_cost')}, {z.get('max_drawdown')}, {z.get('name')}")
    src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
    r = src[src.index('@app.route("/konto-reset-bestaetigen"'):]
    check('_gr_alt, dd=alt.get("max_drawdown"))' in r[:r.index("\n@app.route(")], "Route /konto-reset-bestaetigen gibt den Max DD der alten Zeile mit")

    print("8 Kernwerte-Reiter (E3): Standard / Nano über flex.name")
    html = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
    k = html[html.index("const e3FlexName = "):html.index("  function e3GrStatus(")]
    check("(fn || 'Flex') + ' ' + e3Gr(t.slice(5))" in k and "(fn ? 'Standard ' : '') + e3Gr(t)" in k, "e3Kopf: mit Name „Nano 100k“/„Standard 100k“, ohne wie bisher")
    check("${e3Kopf(t, f)}" in html and "${e3Kopf(t)}" not in html, "Reiter-Knopf gibt die Firma mit")
    check("`${e3FlexName(f) || 'Flex'}-Konten ${e3Gr(g)}" in html, "Status-Zeile: „Nano-Konten 100k“, FundingPips weiter „Flex-Konten“")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
