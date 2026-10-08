#!/usr/bin/env python3
"""Selbsttest HEUTE BEENDET (app.py ap_hb_gelesen / ap_hb_zeile / _ap_hb_laden / ap_delta_antwort, Finn 08.10.2026: „einmal die laufenden
und einmal die vergangenen, heute schon gelaufenen Trades … plus wie viel hypothetische Euro diese ID heute gemacht oder verloren hat").
Rein rechnend bzw. gegen eine nachgebaute DB (Platzhalter-IDs, keine echten Konten), ohne Netz.
Geprüft: € = genau hypo_bilanz_zeile (P&L $ × Kontowert-Satz), Ergebnis nicht gelesen → offen (nicht geraten), geblowt → −Kontowert vor
dem Trade, bestanden (Ziel / ziel_pct_konto / Ziel-Wache / Archiv), Dubai-Tag, WD/Funded raus, Sicht-Filter wie offen[]/geplant[].
Aufruf: python3 tools/selftest_auto_heute.py"""
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
sys.path.insert(0, HIER)

FIRMEN = [
    {"namen": ["apextrader", "apex"], "groessen": [150000], "kauf_eur": 150, "dd_usd": 4000, "boden": "statisch", "daily_usd": 2000,
     "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"tp": None}}},
    {"namen": ["tradeify"], "groessen": [150000], "kauf_eur": 215, "dd_usd": 4500, "boden": "nachziehend", "ziel_pct": {"challenge": 6},
     "phasen": {"challenge": {"tp_max": 3600}}},
    {"namen": ["fundednext"], "groessen": [100000], "kauf_eur": {"50000": 261, "100000": 500}, "dd_pct": 10, "boden": "statisch",
     "ziel_pct": {"phase1": 8, "phase2": 5}, "wert_groessen": [50000, 100000], "phasen": {"phase1": {}}},
]
UA, UB, UX = "00000000-0000-0000-0000-0000000000b1", "00000000-0000-0000-0000-0000000000b2", "00000000-0000-0000-0000-0000000000b9"


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "time": time,
          "threading": threading}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    teile = [konst(k) for k in ("_KETTE_DLL_CACHE", "AP_KW_FUNDED", "LT_BALANCE_SPRUNG_USD", "AP_KW_PHASEN", "AP_TYPEN", "AP_GROESSE_TOLERANZ", "LT_ECHO_ROUTEN", "AP_HB_TZ",
                                "AP_HB_CACHE_S", "AP_HB_BLOW_ANTEIL", "AP_HB_ECHT_QUELLEN", "_ap_hb_cache", "_ap_hb_lock")]
    teile += [block(f) for f in ("_wd_num", "lt_pl_balance", "lt_balance_sprung", "_ap_norm", "ap_regel_finden", "ap_groesse", "ap_kw_param", "_ap_kw_kauf",
                                 "_ap_kw_wachsen", "_ap_kw_lock", "kette_dll_chance", "ap_kontowert", "_ap_ende4", "_ap_tz", "_ap_ts", "ap_bal_vorher_konto", "ap_konto_plaene_grenze", "hypo_bilanz_zeile",
                                 "ap_hb_ende", "ap_hb_gelesen", "ap_hb_zeile", "_ap_konto_plaene", "_ap_hb_laden", "ap_heute_beendet_gemerkt")]
    exec("\n".join(teile), ns)
    return ns


def plan(pid, uid, kid, firma, richtung="sell", status="review", auto=True, typ="challenge", pl=None, quelle=None, route="tvv2",
         start="2026-10-07T23:57:00+00:00", ende="2026-10-08T02:26:00+00:00", tv=None, fin=None, completed=None):
    return {"id": pid, "user_id": uid, "master_account_id": kid, "master_name": f"Konto {kid}", "master_firm": firma, "route": route,
            "richtung": richtung, "status": status, "auto_plan": auto, "master_pl": pl, "pl_quelle": quelle, "konto_typ": typ,
            "started_at": start, "ended_at": ende, "completed_at": completed, "mt5_baseline": {"tv": tv or {}, "final": fin}}


def main():
    ns = lade()
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    Z, G, H = ns["ap_hb_zeile"], ns["ap_hb_gelesen"], ns["hypo_bilanz_zeile"]
    namen = {UA: "ID A", UB: "ID B"}
    apex = {"id": "k-a1", "name": "150k Apex …0901", "firm": "Apex Trader", "account_type": "challenge", "external_id": "APEX-000901"}

    # 1) Apex −2.065,50 $ (Puls-Today + Endbalance) — gelesen, Satz aus der Balance vorher: Kauf 150 € / DD 4.000 $ = 0,0375 €/$
    p1 = plan("p-1", UA, "k-a1", "Apex Trader", pl=-2065.5, tv={"balance_start": 150000},
              fin={"grund": "demo_liq", "quelle": "puls", "today_pnl": -2065.5, "balance_end": 147934.5, "master_pl_schaetzung": -2000})
    z1 = Z(p1, apex, FIRMEN, None, None, namen)
    h1 = H(p1, apex, FIRMEN, None, None, namen)
    check(G(p1) and z1["art"] == "normal" and z1["ergebnis_usd"] == -2065.5, f"Apex −2.065,50 $ gelesen → normal ({z1['art']}, {z1['ergebnis_usd']})")
    check(z1["eur"] == h1["hypo_eur"] and z1["satz"] == h1["satz"] == 0.0375 and z1["satz_quelle"] == "balance_vorher",
          f"€ GENAU wie die Hypo-Bilanz: {z1['eur']} € = {h1['hypo_eur']} € (Satz {z1['satz']}, {z1['satz_quelle']})")
    check(z1["kontowert_eur"] == 150 and z1["user"] == "ID A" and z1["ende4"] == "0901" and z1["auto"] is True,
          f"Kontowert vor dem Trade 150 €, Name/Ende4/auto ({z1['kontowert_eur']}, {z1['user']}, {z1['ende4']})")
    # Apex-Tagesstopp (−2.000 $) ist kein Blow: Polster 4.000 $, 95 % = 3.800 $
    check(z1["art"] != "geblowt", "Apex-Tagesstopp −2.065 $ bei Polster 4.000 $ → nicht geblowt")

    # 2) Endbalance aus dem Reader, quelle demo → trotzdem gelesen (Balance beweist das Ergebnis)
    p2 = plan("p-2", UA, "k-a1", "Apex Trader", pl=-1965.5, tv={"balance_start": 150000},
              fin={"grund": "demo_liq", "quelle": "demo", "today_pnl": None, "balance_end": 148034.5, "master_pl_schaetzung": -2000})
    z2 = Z(p2, apex, FIRMEN, None, None, namen)
    check(G(p2) and z2["art"] == "normal" and z2["eur"] == round(-1965.5 * 0.0375, 2), f"Reader-Endbalance zählt als gelesen ({z2['eur']} €)")

    # 3) NUR Demo-Schätzung (master_pl −2.000 = Schätzung, keine Endbalance) → offen, nicht in die Summe (Anlass 08.10.2026)
    p3 = plan("p-3", UA, "k-a1", "Apex Trader", pl=-2000, tv={"balance_start": 150000},
              fin={"grund": "demo_liq", "quelle": "demo", "today_pnl": None, "master_pl_schaetzung": -2000})
    z3 = Z(p3, apex, FIRMEN, None, None, namen)
    check(not G(p3) and z3["art"] == "offen" and z3["eur"] is None and z3["ergebnis_usd"] is None,
          f"nur Demo-Schätzung → offen, € und $ leer ({z3['art']}, {z3['eur']})")
    check("Demo-Schätzung" in (z3["grund"] or "") and "zählt nicht" in z3["grund"], f"Grund nennt die Schätzung ({z3['grund']})")
    p3b = plan("p-3b", UA, "k-a1", "Apex Trader", pl=None, fin=None)
    check(Z(p3b, apex, FIRMEN, None, None, namen)["art"] == "offen", "ohne P&L und ohne final → offen")
    p3c = plan("p-3c", UA, "k-a1", "Apex Trader", pl=20, quelle="hand", fin=None, tv={"balance_start": 150000})
    check(G(p3c) and Z(p3c, apex, FIRMEN, None, None, namen)["art"] == "normal", "pl_quelle hand → gelesen")

    # 4) Hand-Trade +9.003,70 $ → Balance 159.003,70 ≥ Ziel 159.000 → bestanden, € = P&L × Satz
    p4 = plan("p-4", UA, "k-a1", "Apex Trader", richtung="buy", auto=False, pl=9003.7, tv={"balance_start": 150000},
              fin={"quelle": "close", "today_pnl": 9003.7, "balance_end": 159003.7})
    z4 = Z(p4, apex, FIRMEN, None, None, namen)
    check(z4["art"] == "bestanden" and z4["eur"] == round(9003.7 * 0.0375, 2) and z4["auto"] is False,
          f"Ziel erreicht → bestanden, Hand-Trade ({z4['art']}, {z4['eur']} €, {z4['grund']})")

    # 5) Blow: −4.000 $ bei Polster 4.000 $ → geblowt, € = −Kontowert vor dem Trade (150 €), nicht P&L × Satz
    p5 = plan("p-5", UA, "k-a1", "Apex Trader", pl=-4000, tv={"balance_start": 150000},
              fin={"quelle": "puls", "today_pnl": -4000, "balance_end": 146000})
    z5 = Z(p5, apex, FIRMEN, None, None, namen)
    check(z5["art"] == "geblowt" and z5["eur"] == -150.0 and z5["ergebnis_usd"] == -4000, f"Blow → −Kontowert 150 € ({z5['art']}, {z5['eur']})")
    # Konto vorher im Plus (Polster 7.000 $): −4.000 $ ist KEIN Blow
    p5b = plan("p-5b", UA, "k-a1", "Apex Trader", pl=-4000, tv={"balance_start": 153000},
               fin={"quelle": "puls", "today_pnl": -4000, "balance_end": 149000})
    check(Z(p5b, apex, FIRMEN, None, None, namen)["art"] == "normal", "Polster 7.000 $ (Konto im Plus) → −4.000 $ nicht geblowt")

    # 6) Als geblowt archiviert (nach dem Start), Ergebnis nicht gelesen → geblowt mit −Kontowert; älterer Archiv-Eintrag / nicht letzter → offen
    nach = datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc)
    z6 = Z(p3, apex, FIRMEN, None, None, namen, archiv=(nach, "blown"), letzter=True)
    check(z6["art"] == "geblowt" and z6["eur"] == -150.0, f"archiviert blown + ungelesen → geblowt −150 € ({z6['art']}, {z6['eur']})")
    check(Z(p3, apex, FIRMEN, None, None, namen, archiv=(nach, "blown"), letzter=False)["art"] == "offen",
          "Archiv gilt nur für den letzten Trade des Kontos")
    vor = datetime(2026, 10, 1, 4, 0, tzinfo=timezone.utc)
    check(Z(p1, apex, FIRMEN, None, None, namen, archiv=(vor, "blown"), letzter=True)["art"] == "normal",
          "Archiv-Eintrag VOR dem Trade-Start zählt nicht")
    check(Z(p1, apex, FIRMEN, None, None, namen, archiv=(nach, "passed"), letzter=True)["art"] == "bestanden", "Archiv passed → bestanden")

    # 7) Echo (mt5v2) FundedNext Phase 1: master_pl + final.master_balance → gelesen; Balance vorher = Ende − P&L; Satz 500 € / 10.000 $
    fn = {"id": "k-f1", "name": "100k FN", "firm": "FundedNext", "account_type": "phase1", "external_id": "00012345"}
    p7 = plan("p-7", UB, "k-f1", "FundedNext", typ="phase1", route="mt5v2", pl=-2200.4, fin={"master_balance": 101235.16})
    z7 = Z(p7, fn, FIRMEN, None, None, namen)
    check(G(p7) and z7["art"] == "normal" and z7["satz"] == 0.05 and z7["eur"] == round(-2200.4 * 0.05, 2),
          f"Echo: gelesen, Satz 0,05 aus der Balance vorher ({z7['satz']}, {z7['eur']} €)")
    check(z7["kontowert_eur"] == round(500 * (10000 + 3435.56) / 10000), f"Echo: Kontowert vor dem Trade ({z7['kontowert_eur']} €)")
    # 8) FundedNext Phase 1 bestanden (108.200 ≥ 108.000) — mit ziel_pct_konto 10 % nicht
    p8 = plan("p-8", UB, "k-f1", "FundedNext", typ="phase1", route="mt5v2", pl=1200, fin={"master_balance": 108200})
    check(Z(p8, fn, FIRMEN, None, None, namen)["art"] == "bestanden", "Phase 1 Ziel 8 % erreicht → bestanden")
    fn10 = dict(fn, ziel_pct_konto={"phase1": 10})
    check(Z(p8, fn10, FIRMEN, None, None, namen)["art"] == "normal", "ziel_pct_konto 10 % geht vor → noch nicht bestanden")
    # 9) Ziel-Wache: ziel_erreicht_at nach dem Start + letzter Trade → bestanden
    fnz = dict(fn, ziel_erreicht_at="2026-10-08 03:00:00.5+00")
    check(Z(p7, fnz, FIRMEN, None, None, namen, letzter=True)["art"] == "bestanden"
          and Z(p7, fnz, FIRMEN, None, None, namen, letzter=False)["art"] == "normal", "Ziel-Wache nur am letzten Trade des Kontos")
    # 10) Firma ohne Kernwerte: ohne Satz → € leer + Grund; mit Kontowert heute → Satz-Quelle heute; Lauf-Satz geht vor
    luc = {"id": "k-l1", "name": "Lucid", "firm": "Lucid Trading", "account_type": "challenge", "external_id": "LUC-1"}
    p10 = plan("p-10", UB, "k-l1", "Lucid Trading", pl=-500, tv={"balance_start": 50000}, fin={"balance_end": 49500})
    z10 = Z(p10, luc, FIRMEN, None, None, namen)
    check(z10["art"] == "normal" and z10["eur"] is None and "ohne Kontowert-Satz" in (z10["grund"] or ""), f"ohne Satz → € leer ({z10['grund']})")
    z10b = Z(p10, luc, FIRMEN, None, 0.04, namen)
    check(z10b["eur"] == -20.0 and z10b["satz_quelle"] == "heute", f"Kontowert heute als letzte Stufe ({z10b['eur']}, {z10b['satz_quelle']})")
    z10c = Z(p1, apex, FIRMEN, 0.05, 0.04, namen)
    check(z10c["satz_quelle"] == "lauf" and z10c["eur"] == round(-2065.5 * 0.05, 2), "Satz aus dem Lauf des Tages geht vor (wie Hypo-Bilanz)")

    # ── _ap_hb_laden gegen eine nachgebaute DB: Dubai-Tag, WD raus, ausgeblendete ID raus, letzter je Konto, Kontowerte nur bei Bedarf
    jetzt = datetime(2026, 10, 8, 3, 14, tzinfo=timezone.utc)          # 07:14 Dubai → Tag ab 07.10. 20:00 UTC
    def roh(p):
        q = {k: v for k, v in p.items() if k != "mt5_baseline"}
        b = p.get("mt5_baseline") or {}
        q.update(tv=b.get("tv"), final=b.get("final"), bstart=b.get("balance_start"), bn=b.get("bal_nach"))
        return q
    db_plaene = [
        roh(plan("d-1", UA, "k-a1", "Apex Trader", pl=-2065.5, tv={"balance_start": 150000},
                 fin={"quelle": "puls", "today_pnl": -2065.5, "balance_end": 147934.5}, ende="2026-10-08T02:26:00+00:00")),
        roh(plan("d-2", UA, "k-a1", "Apex Trader", pl=-2000, tv={"balance_start": 150000},
                 fin={"quelle": "demo", "master_pl_schaetzung": -2000}, ende="2026-10-08T02:32:00+00:00")),
        roh(plan("d-3", UA, "k-a1", "Apex Trader", pl=-100, tv={"balance_start": 150000}, fin={"balance_end": 149900},
                 ende="2026-10-07T19:59:00+00:00", completed="2026-10-07T20:30:00+00:00")),          # Ende 23:59 Dubai gestern → raus
        roh(plan("d-4", UA, "k-w1", "Tradeify", typ="winning_days", pl=-600, fin={"balance_end": 159000}, tv={"balance_start": 159600},
                 ende="2026-10-07T21:12:00+00:00")),                                                    # WD → raus
        roh(plan("d-5", UX, "k-a9", "Apex Trader", pl=-50, tv={"balance_start": 150000}, fin={"balance_end": 149950})),   # ausgeblendet
        roh(plan("d-6", UB, "k-l1", "Lucid Trading", pl=-500, tv={"balance_start": 50000}, fin={"balance_end": 49500},
                 ende=None, completed="2026-10-07T20:09:00+00:00", status="completed")),              # nur completed_at → drin
        roh(plan("d-7", UB, "k-f1", "FundedNext", typ=None, route="mt5v2", pl=-508.2, fin={"master_balance": 90002},
                 ende="2026-10-08T00:29:45+00:00")),                                                    # konto_typ leer → Kontoart phase1
    ]
    konten = {"k-a1": apex, "k-w1": {"id": "k-w1", "name": "TDFY WD", "firm": "Tradeify", "account_type": "winning_days"},
              "k-a9": dict(apex, id="k-a9"), "k-l1": luc, "k-f1": fn}
    # BALANCE NACH ECHO-TRADE (08.10.2026): bal_nach ok:false nur beim jüngsten Trade des Kontos und nur, solange die Konto-Balance älter ist
    bn_fehlt = {"ok": False, "code": "", "msg": "Terminal-Start fehlgeschlagen: x", "tun": "Am PC ↻", "versuche": 3, "at": "2026-10-08T00:45:00Z"}
    db_plaene[6]["bn"] = dict(bn_fehlt)                     # d-7 FundedNext, Ende 00:29:45, Balance 00:10 → bleibt
    db_plaene[0]["bn"] = dict(bn_fehlt)                     # d-1 Apex, aber d-2 ist jünger → nicht
    db_plaene[5]["bn"] = dict(bn_fehlt)                     # d-6 Lucid, Balance nach dem Ende gelesen → nicht
    konten["k-f1"] = dict(fn, tv_balance_at="2026-10-08T00:10:00+00:00")
    konten["k-l1"] = dict(luc, tv_balance_at="2026-10-08T01:00:00+00:00")
    aufrufe = {"kw": 0, "anfragen": []}

    def sb_all(tabelle, q):
        aufrufe["anfragen"].append((tabelle, q))
        if tabelle == "trade_plans":
            return [dict(p) for p in db_plaene]
        if tabelle == "accounts":
            ids = re.findall(r"[\w-]+", q["id"][4:])
            return [konten[i] for i in ids if i in konten]
        if tabelle == "user_settings":
            return [{"value": json.dumps({"k-l1": {"archived": True, "reason": "manual", "at": "2026-10-08T05:00:00Z"}})}]
        if tabelle == "auto_plan_lauf":
            return [{"tag": "2026-10-08", "at": "x", "trocken": None, "geplant": [{"konto_id": "k-a1", "satz_eur_je_usd": None}]}]
        return []

    def kw_gemerkt(sicht=None):
        aufrufe["kw"] += 1
        return {"k-l1": {"satz_eur_pro_usd": 0.04}}
    ns["_sb_all"], ns["_ap_namen"], ns["ap_kontowerte_gemerkt"] = sb_all, (lambda: (dict(namen), {UX})), kw_gemerkt

    class _Req:
        class exceptions:
            HTTPError = type("HTTPError", (Exception,), {})
    ns["requests"] = _Req
    zeilen, ab = ns["_ap_hb_laden"](FIRMEN, jetzt)
    ids = [z["plan_id"] for z in zeilen]
    check(ab.startswith("2026-10-08T00:00:00+04:00"), f"Tag = Dubai ab 00:00 ({ab})")
    check(set(ids) == {"d-1", "d-2", "d-6", "d-7"}, f"heute beendet: Dubai-Tag, WD raus, ausgeblendete ID raus, completed_at zählt ({ids})")
    check(ids == ["d-2", "d-1", "d-7", "d-6"], f"neueste zuerst ({ids})")
    je = {z["plan_id"]: z for z in zeilen}
    check((je["d-7"].get("bal_nach") or {}).get("msg") == "Terminal-Start fehlgeschlagen: x" and je["d-7"].get("konto_id") == "k-f1"
          and (je["d-7"].get("bal_nach") or {}).get("versuche") == 3, f"bal_nach: jüngster Trade, Balance älter als Ende → mit Grund ({je['d-7'].get('bal_nach')})")
    check("bal_nach" not in je["d-1"] and "bal_nach" not in je["d-6"] and "bal_nach" not in je["d-2"],
          "bal_nach: älterer Trade desselben Kontos / Balance inzwischen live / ohne Meldung → kein Feld")
    check(je["d-2"]["art"] == "offen" and je["d-1"]["art"] == "normal" and je["d-7"]["typ"] == "phase1",
          f"Arten + Typ aus der Kontoart ({je['d-2']['art']}, {je['d-1']['art']}, {je['d-7']['typ']})")
    check(je["d-6"]["eur"] == -20.0 and aufrufe["kw"] == 1, f"Kontowert heute genau einmal nachgeladen ({je['d-6']['eur']}, {aufrufe['kw']}×)")
    q_tp = next(q for t, q in aufrufe["anfragen"] if t == "trade_plans")
    check("+" not in q_tp["or"] and "2026-10-07T20:00:00Z" in q_tp["or"] and "mt5_baseline->final" in q_tp["select"],
          f"Abfrage: Dubai-Mitternacht ohne „+“, nur tv/final aus mt5_baseline ({q_tp['or']})")
    # ARCHIVIERT (08.10.2026): Konto des d-7 archiviert → kein bal_nach mehr, die Zeile selbst bleibt (Bilanz)
    alt_sb = ns["_sb_all"]
    def sb_arch(tabelle, q):
        if tabelle == "user_settings":
            return [{"value": json.dumps({"k-l1": {"archived": True, "reason": "manual", "at": "2026-10-08T05:00:00Z"},
                                          "k-f1": {"archived": True, "reason": "manual", "at": "2026-10-08T04:30:51Z"}})}]
        return alt_sb(tabelle, q)
    ns["_sb_all"] = sb_arch
    z2 = {z["plan_id"]: z for z in ns["_ap_hb_laden"](FIRMEN, jetzt)[0]}
    ns["_sb_all"] = alt_sb
    check("d-7" in z2 and "bal_nach" not in z2["d-7"], "bal_nach: archiviertes Konto → kein Hinweis, Zeile bleibt in heute_beendet")
    # GET /admin/auto-plan: ap_ohne_archiv nimmt archivierte Konten aus ausgelassen[], geplant[] bleibt
    import re as _re
    src_app = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
    i_ = src_app.index("\ndef ap_ohne_archiv(") + 1
    ns2 = {}
    exec(src_app[i_:src_app.find("\n\n\n", i_)], ns2)
    erg = {"ausgelassen": [{"konto_id": "k-x", "grund": "keine Balance bekannt"}, {"konto_id": "k-y", "grund": "keine Regel"}],
           "geplant": [{"konto_id": "k-x"}], "summe": 3}
    o = ns2["ap_ohne_archiv"](erg, {"k-x"})
    check([x["konto_id"] for x in o["ausgelassen"]] == ["k-y"] and o["geplant"] == [{"konto_id": "k-x"}] and o["summe"] == 3
          and len(erg["ausgelassen"]) == 2, "ap_ohne_archiv: archiviertes Konto aus ausgelassen raus, geplant/Summen bleiben, Eingabe unverändert")
    check(ns2["ap_ohne_archiv"](erg, set()) is erg and ns2["ap_ohne_archiv"](None, {"k-x"}) is None, "ap_ohne_archiv: ohne Archiv/ohne Ergebnis unverändert")
    check(_re.search(r"erg = ap_ohne_archiv\(erg, _ap_archiviert\(\)\)", src_app) is not None, "GET /admin/auto-plan filtert den gespeicherten Lauf gegen das aktuelle Archiv")
    # Merker: zweiter Aufruf im selben Dubai-Tag ohne neue Abfrage
    vorher = len(aufrufe["anfragen"])
    ns["ap_heute_beendet_gemerkt"](FIRMEN, jetzt)
    ns["ap_heute_beendet_gemerkt"](FIRMEN, jetzt)
    # 4 Anfragen je Laden: die Pläne je Konto (ap_bal_vorher_konto) werden nur für Konten MIT Konto-Lesung geholt — hier keine → keine
    # Abfrage (Last-Grenze 08.10.2026); der zweite Abruf kommt aus dem Merker
    check(len(aufrufe["anfragen"]) - vorher == 4, f"30-s-Merker: zweiter Abruf ohne DB ({len(aufrufe['anfragen']) - vorher} Anfragen)")

    # ── Sicht wie offen[]/geplant[]: ap_delta_antwort filtert heute_beendet je ID (nachgebaute DB aus selftest_auto_delta)
    import selftest_auto_delta as sd
    a = sd.lade()
    jj = datetime.now(timezone.utc)
    reg, _g = sd.db_stubs(a, jj, [])
    stand = a["_ap_stand_laden"](reg, jetzt=jj)
    dl0 = a["ap_delta_antwort"](stand)
    check("heute_beendet" not in dl0, "ohne Stand-Feld (Bot, alte Aufrufer) → kein heute_beendet in der Antwort")
    hb = [{"plan_id": "x1", "user_id": sd.U1, "eur": -75}, {"plan_id": "x2", "user_id": sd.U2, "eur": 10}]
    dl = a["ap_delta_antwort"](dict(stand, heute_beendet=hb, heute_ab="2026-10-08T00:00:00+04:00"))
    check([x["plan_id"] for x in dl["heute_beendet"]] == ["x1", "x2"] and dl["heute_ab"].startswith("2026-10-08"), "Admin/alle: alle Zeilen")
    dlu = a["ap_delta_antwort"](dict(stand, heute_beendet=hb), sd.U1)
    check([x["plan_id"] for x in dlu["heute_beendet"]] == ["x1"] and dlu["sicht"] == "eigene", "eigene Sicht: nur die eigene ID")
    check(hb[1]["plan_id"] == "x2" and len(hb) == 2, "Merker-Liste wird beim Filtern nicht verändert")
    dlf = a["ap_delta_antwort"](dict(stand, heute_beendet_fehler="HTTPError: 503"), sd.U1)
    check(dlf["heute_beendet"] is None and dlf["heute_beendet_fehler"] == "HTTPError: 503" and isinstance(dlf["offen"], list),
          "Ladefehler → heute_beendet null + Fehlertext, übriges Delta unberührt")

    # BALANCE VORHER AUS DER KONTO-LESUNG (Finn 08.10.2026 „Die Zahl stimmt doch nie"): Orbit V1/Duplikum ohne Start-/Endbalance fiel still
    # aus der Summe. Lesung am Konto VOR dem Start → Satz wie tv.balance_start (Tradeify 215 € / 4.500 $ = 0,0478); Lesung NACH dem Start → ohne €
    trd = {"id": "k-t9", "name": "150k Tradeify …0909", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000909",
           "tv_balance": 150000, "tv_balance_at": "2026-10-08T07:00:53+00:00", "_plaene": [("p-d1", "2026-10-08T07:14:26+00:00", None)]}
    pd = plan("p-d1", UA, "k-t9", "Tradeify", richtung="buy", status="completed", auto=False, pl=3570.0, quelle="duplikum", route="tvplus",
              start="2026-10-08T07:14:26+00:00", ende="2026-10-08T08:19:45+00:00", fin=None)
    zd = Z(pd, trd, FIRMEN, None, None, namen)
    check(zd["eur"] is not None and zd["satz_quelle"] == "balance_vorher" and abs(zd["satz"] - 0.0478) < 0.0001 and zd["art"] == "normal",
          f"Duplikum ohne Balance + Konto-Lesung vor dem Start → Satz {zd['satz']} ({zd['satz_quelle']}), {zd['eur']} €")
    zd2 = Z(pd, dict(trd, tv_balance_at="2026-10-08T09:00:00+00:00"), FIRMEN, None, None, namen)
    check(zd2["eur"] is None and "ohne Kontowert-Satz" in str(zd2["grund"]), "Konto-Lesung NACH dem Start zählt nicht → ohne € (nicht raten)")
    hd = H(pd, trd, FIRMEN, None, None, namen)
    check(hd["satz"] == zd["satz"] and hd["hypo_eur"] == zd["eur"] and hd["satz_quelle"] == "balance_vorher",
          f"Hypo-Bilanz rechnet dieselbe Regel: {hd['hypo_eur']} € = Kachel {zd['eur']} €")
    hd2 = H(pd, dict(trd, tv_balance_at="2026-10-08T09:00:00+00:00"), FIRMEN, None, 0.05, namen)
    check(hd2["satz_quelle"] == "heute", "Hypo-Bilanz: Lesung nach dem Start → wie bisher Rückfall „Satz heute\"")
    # NACHSCHÄRFUNG (Prüfer 08.10.2026): Lesung muss NACH dem Ende des vorigen Trades desselben Kontos liegen
    vor_nach = dict(trd, _plaene=trd["_plaene"] + [("p-v1", "2026-10-08T06:00:00+00:00", "2026-10-08T07:05:00+00:00")])
    check(Z(pd, vor_nach, FIRMEN, None, None, namen)["eur"] is None and H(pd, vor_nach, FIRMEN, None, None, namen)["hypo_eur"] is None,
          "voriger Trade endete NACH der Lesung (07:05 > 07:00) → ohne € (Kachel und Hypo-Bilanz)")
    vor_vor = dict(trd, _plaene=trd["_plaene"] + [("p-v2", "2026-10-08T05:00:00+00:00", "2026-10-08T06:30:00+00:00")])
    check(Z(pd, vor_vor, FIRMEN, None, None, namen)["eur"] == zd["eur"], "voriger Trade endete VOR der Lesung (06:30 < 07:00) → Satz wie ohne Vorgänger")
    vor_offen = dict(trd, _plaene=trd["_plaene"] + [("p-v3", "2026-10-08T05:00:00+00:00", None)])
    check(Z(pd, vor_offen, FIRMEN, None, None, namen)["eur"] is None, "voriger Trade ohne Ende → ohne € (nicht raten)")
    ohne_liste = {k: v for k, v in trd.items() if k != "_plaene"}
    check(Z(pd, ohne_liste, FIRMEN, None, None, namen)["eur"] is None, "Pläne des Kontos nicht gelesen → ohne € (nicht raten)")
    # LAST-GRENZE (Prüfer 08.10.2026): Pläne nur noch ab Ende ≥ früheste Konto-Lesung (oder ohne Ende) — Ergebnis IDENTISCH zu allen Plänen
    B = ns["ap_bal_vorher_konto"]
    alle_pl = [("v1", "2026-10-05T10:00:00+00:00", "2026-10-05T12:00:00+00:00"), ("v2", "2026-10-07T20:00:00+00:00", "2026-10-08T06:50:00+00:00"),
               ("v3", "2026-10-06T09:00:00+00:00", "2026-10-08T07:30:00+00:00"), ("v4", "2026-10-01T09:00:00+00:00", None),
               ("p-d1", "2026-10-08T07:14:26+00:00", None)]
    gleich = True
    for les in ("2026-10-08T06:00:00+00:00", "2026-10-08T07:00:53+00:00", "2026-10-08T07:40:00+00:00", "2026-10-04T08:00:00+00:00"):
        konto = dict(trd, tv_balance_at=les)
        _, ab = ns["ap_konto_plaene_grenze"]({"k-t9": konto})
        eng = [x for x in alle_pl if x[2] is None or ns["_ap_ts"](x[2]) >= ab]
        for liste in (alle_pl, [x for x in alle_pl if x[0] != "v4"], [x for x in alle_pl if x[0] not in ("v3", "v4")]):
            weit = B(pd, dict(konto, _plaene=liste)); knapp = B(pd, dict(konto, _plaene=[x for x in liste if x in eng]))
            gleich = gleich and weit == knapp
    check(gleich, "Last-Grenze über das ENDE: Rechnung mit begrenzten Plänen identisch zu allen Plänen (4 Lesezeiten × 3 Plan-Sätze)")
    kg, abg = ns["ap_konto_plaene_grenze"]({"k-a": {"tv_balance": 150000, "tv_balance_at": "2026-10-08T07:00:00+00:00"},
                                            "k-b": {"tv_balance": 0, "tv_balance_at": "2026-10-01T07:00:00+00:00"}, "k-c": {"tv_balance": 100000}})
    check(kg == ["k-a"] and abg.isoformat().startswith("2026-10-08T07:00"), "nur Konten mit Lesung (>0 und Zeit) brauchen Pläne; ab = früheste Lesung")

    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
