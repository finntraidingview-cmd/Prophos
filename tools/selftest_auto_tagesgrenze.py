#!/usr/bin/env python3
"""Selbsttest TAGESGRENZE + ENDE IM FENSTER (app.py _ap_stand_laden folgetag, _ap_stand_plaene, ap_delta_antwort, ap_umplanen,
08.10.2026, Slave-Terminal 3 — Master: mit dem 24/7-Takt kennt der Zustand zwischen ~23:00 und 24:00 dt die Pläne ab 00:00 dt nicht
(Nachtlauf 23:30 dt legt sie an); beim Hinausschieben prüfte die Suche nur den Start, nicht Start + Laufzeit gegen das Fenster).

Aufruf:  python3 tools/selftest_auto_tagesgrenze.py
Ohne Netz (Fake-DB aus selftest_auto_delta). Geprüft: Stand 23:20 dt → Plan morgen 00:10 dt steht als feste Zeile in stand.folgetag
(start_min ≥ 1440, nicht änderbar, nicht in geplant[]), Plan morgen 05:00 dt (nach jetzt + 60 + Laufzeit) nicht; _ap_stand_plaene
reicht ihn fest weiter; Delta-Szenario +60 rechnet ihn mit; Bot: Vorziehen respektiert den Gegenhedge gegen den Folgetag-Plan (ohne ihn
→ Zug), bewegt ihn nie; Hinausschieben nur, wenn Start + Laufzeit im Fenster bleibt."""
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


S = 180.0 / 2500.0
LAUFEND = [{"richtung": "sell", "satz": S, "usd_pro_pkt": 100.0, "wert": 180.0, "polster_usd": 2500.0, "daily_usd": 2000.0,
            "tp_punkte": 40.0, "sl_punkte": None} for _ in range(3)]


def plan(pid, uid, firma, richtung, start, **kw):
    p = {"plan_id": pid, "user_id": uid, "user": uid.capitalize(), "firma": firma, "firma_name": firma.capitalize(), "richtung": richtung,
         "start_min": float(start), "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "fest_durch": None, "auto_plan": True,
         "bestaetigt": True, "route": "tvv2", "satz_eur_je_usd": 0.06, "usd_pro_pkt": 40.0, "wert_eur": 900.0, "polster_usd": 3000.0,
         "daily_usd": None, "tp_punkte": 40.0, "sl_punkte": None}
    p.update(kw)
    return p


def main():
    a = sd.lade()
    BER = ZoneInfo("Europe/Berlin")

    # ── 1 Stand über die Tagesgrenze ─────────────────────────────────────────────────────────────────────────────────────────
    tag = datetime.now(timezone.utc).astimezone(BER) + timedelta(days=1)
    mitt = datetime(tag.year, tag.month, tag.day, tzinfo=BER)
    jetzt = mitt + timedelta(hours=23, minutes=20)
    morgen = mitt + timedelta(days=1)

    def p_(pid, uid, konto, firma, start, richtung="buy", **kw):
        return dict({"id": pid, "user_id": uid, "master_account_id": konto, "master_firm": firma, "status": "planned", "richtung": richtung,
                     "master_tp": 6000, "master_sl": 3000, "master_contracts": 3.0, "route": "mt5v2", "start_um": start.isoformat(),
                     "auto_plan": True, "auto_bestaetigt_at": jetzt.isoformat(), "created_at": jetzt.isoformat()}, **kw)
    geplant = [p_("p-heute", sd.U1, "k-2", "FundedNext", mitt + timedelta(hours=9)),
               p_("p-nacht", sd.U1, "k-2", "FundedNext", morgen + timedelta(minutes=10), "sell"),
               p_("p-frueh", sd.U1, "k-2", "FundedNext", morgen + timedelta(hours=5))]
    reg, _g = sd.db_stubs(a, jetzt, geplant)
    st = a["_ap_stand_laden"](reg, jetzt=jetzt)
    fol = {z["plan_id"]: z for z in st.get("folgetag") or []}
    gp = {z["plan_id"] for z in st["geplant"]}
    check("p-nacht" in fol and fol["p-nacht"]["start_min"] >= 1440 and fol["p-nacht"]["aenderbar"] is False
          and fol["p-nacht"]["fest_durch"] == a["AP_FEST_FOLGETAG"] and "p-nacht" not in gp,
          f"23:20 dt: Plan morgen 00:10 dt als feste Folgetag-Zeile ({ {k: (v['start_min'], v['aenderbar']) for k, v in fol.items()} })")
    check("p-frueh" not in fol and "p-frueh" not in gp and "p-heute" in gp, "morgen 05:00 dt (nach jetzt + 60 + Laufzeit) nicht dabei, heute wie bisher")
    pl = {x["plan_id"]: x for x in a["_ap_stand_plaene"](st)}
    check(pl.get("p-nacht", {}).get("folgetag") is True and pl["p-nacht"]["aenderbar"] is False and pl["p-heute"]["folgetag"] is False,
          "_ap_stand_plaene: Folgetag-Plan fest weitergereicht (folgetag=True)")
    dl = a["ap_delta_antwort"](st)
    dl0 = a["ap_delta_antwort"](dict(st, folgetag=[]))
    check(dl["szenario"]["plus60"] != dl0["szenario"]["plus60"] and dl["szenario"]["jetzt"] == dl0["szenario"]["jetzt"]
          and not any(g["plan_id"] == "p-nacht" for g in dl["geplant"]),
          "Delta: Szenario +60 rechnet den Plan nach 00:00 dt mit, jetzt-Kurve und geplant[] unverändert")

    # ── 2 Bot: Richtungsschutz gegen den Folgetag-Plan, nie bewegt ───────────────────────────────────────────────────────────────────
    U = a["ap_umplanen"]
    Z = {"fenster": [["00:00", "23:59", 1]], "start_bis": "23:59", "abstand_id_min": 3}
    EK = {"basis": 0.0, "brutto": 0.0, "gross_ab": 100000.0, "laufzeit": 180, "szenario_laufend": LAUFEND}
    jm = 1300.0
    a_long = plan("a_long", "u-a", "fundednext", "buy", 1420)
    b_morgen = plan("b_morgen", "u-b", "fundednext", "sell", 1445, aenderbar=False, fest_durch=a["AP_FEST_FOLGETAG"], folgetag=True)
    ohne = U([a_long], 0.0, 0.0, jm, Z, 25, random.Random(1), einsatz=EK)
    mit = U([a_long, b_morgen], 0.0, 0.0, jm, Z, 25, random.Random(1), einsatz=EK)
    check([x["plan_id"] for x in ohne["aenderungen"]] == ["a_long"], f"ohne Folgetag-Plan: Long wird vorgezogen ({[x['plan_id'] for x in ohne['aenderungen']]})")
    # seit 08.10.2026 ~17:00 Dubai (Finn: „kann natürlich eine ANDERE ID … short gehen") sperrt eine andere ID nur ±3 min um ihren Start —
    # der Folgetag-SELL 00:05 dt liegt weit hinter dem Vorzieh-Platz; die eigene ID sperrt ihre Gegenrichtung weiter über die Laufzeit
    check([x["plan_id"] for x in mit["aenderungen"]] == ["a_long"],
          f"mit Folgetag-SELL einer anderen ID 00:05 dt: Vorziehen erlaubt (Gegenrichtung über IDs) ({[x['plan_id'] for x in mit['aenderungen']]})")
    selbe = U([a_long, dict(b_morgen, user_id="u-a", user="U-a", plan_id="a_morgen")], 0.0, 0.0, jm, Z, 25, random.Random(1), einsatz=EK)
    # seit 09.10.2026 ~03:45 (Finn: Richtung je Trade frei, nur nie gleichzeitig): auch derselben ID sperrt ein GEPLANTER Gegen-Plan nichts
    # mehr — „nie gleichzeitig" sichert der Start-Wächter im PC-Tab (erst verschieben, dann drehen)
    check([x["plan_id"] for x in selbe["aenderungen"]] == ["a_long"],
          f"mit Folgetag-SELL DERSELBEN ID 00:05 dt: Vorziehen erlaubt (geplante Gegenrichtung sperrt nicht) ({[x['plan_id'] for x in selbe['aenderungen']]})")
    m2 = U([dict(a_long, user_id="u-b", user="U-b", richtung="sell", plan_id="b_heute", start_min=1350), b_morgen], 0.0, 0.0, jm, Z, 25,
           random.Random(1), einsatz=EK)
    check(not any(x["plan_id"] == "b_morgen" for x in m2["aenderungen"]), "Folgetag-Plan wird nie bewegt")

    # ── 3 Hinausschieben: Ende (Start + Laufzeit) im Fenster ───────────────────────────────────────────────────────────────────
    Zf = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
    fest = {"jacob|the5ers": {"richtung": "sell"}}
    EK60 = dict(EK, laufzeit=60)
    frueh = U([plan("s1", "jacob", "the5ers", "sell", 630, usd_pro_pkt=80.0, satz_eur_je_usd=0.08)], 0.0, 0.0, 600, Zf, 25,
              random.Random(1), einsatz=EK60, id_fest=fest)
    x = frueh["aenderungen"][0] if frueh["aenderungen"] else {}
    check(x.get("plan_id") == "s1" and x["nach_start_min"] + 60 <= 870, f"Vormittag: hinausgeschoben, Ende {x.get('nach_start_min', 0) + 60:g} ≤ 14:30 dt (870)")
    spaet = U([plan("s1", "jacob", "the5ers", "sell", 925, usd_pro_pkt=80.0, satz_eur_je_usd=0.08)], 0.0, 0.0, 900, Zf, 25,
              random.Random(1), einsatz=EK60, id_fest=fest)
    check(not spaet["aenderungen"], f"15:00 dt: kein Hinausschieben — Start + 60 läge nach 16:30 dt ({[(y['plan_id'], y['nach_start_min']) for y in spaet['aenderungen']]})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
