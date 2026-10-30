#!/usr/bin/env python3
"""Selbsttest WAAGE × ECHO-HEDGE (app.py, 30.10.2026, Befund S3 „nur Shorts" + Finn: „Nicht alle Shorts … Bei denen, die eh
gegengehedgt werden …" / 04:2x: „An der Logik, wie viele Longs und wie viele Shorts, soll sich nichts ändern zu davor"). Rein
rechnend, Stand nachgebaut. Geprüft:
- Schleife: ein ungehedgter CFD-Long läuft, geplant sind Shorts, die eh_tick gleich auf Echo mit Hedge stellt — die Waage zieht bei
  Echo-Hedge an keinen davon vor (Takt für Takt), bei aus wie bisher; Futures-Waage unverändert
- Planer unverändert: ap_planen und die Richtungs-/Zeit-Rechnung sind Byte für Byte wie vor dem 30.10. (kein Würfeln), die Waage
  ändert Richtungen nie (von = nach)
Aufruf: python3 tools/selftest_waage_echo_hedge.py"""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def ok(bed, txt):
    print(("  ok   " if bed else "  FEHL ") + txt)
    if not bed:
        FEHLER.append(txt)


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "random": random}
    teile = []
    for k in ("WD_FUTURES_FIRMEN", "WD_BALANCE_FUTURES", "AP_TYPEN", "AP_CFD_ROUTEN", "AP_KLASSE_TXT", "EH_TYPEN"):
        teile.append(re.search(rf"^{k} = .*$", src, re.M).group(0).split("  #")[0])
    for z in re.findall(r"^AP_WAAGE_[A-Z_]+ = .*$", src, re.M):
        teile.append(z.split("  #")[0])
    for name in ("_wd_num", "_ap_hhmm_txt", "ap_klasse", "ap_waage_ohne_liste", "ap_waage_ohne", "ap_waage_folgt", "_ap_waage_gewicht",
                 "_ap_waage_startet", "ap_waage_zeile_zaehlt", "_ap_eur_txt", "ap_waage_passt", "ap_waage_deckel", "_ap_waage_note",
                 "ap_klassen_waage", "ap_eh_wird_hedgen", "_ap_waage_kandidat", "_ap_waage_rs_frei", "_ap_waage_zielminute",
                 "ap_waage_nachschub"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns, src


def lauf(pid, uid, firma, fk, route, r, eur, typ="phase1"):
    return {"plan_id": pid, "user_id": uid, "user": uid, "firma": firma, "firma_key": fk, "route": route, "richtung": r,
            "verlust_eur": eur, "typ": typ, "gehedgt": False, "start_min": 100.0}


def plan(pid, uid, firma, fk, route, r, eur, start, **kw):
    z = {"plan_id": pid, "user_id": uid, "user": uid, "firma": firma, "firma_key": fk, "route": route, "richtung": r,
         "verlust_eur": eur, "typ": "phase1", "gehedgt": False, "start_min": start, "auto_plan": True, "bestaetigt": True,
         "aenderbar": True, "geclaimt": False}
    z.update(kw)
    return z


def schleife(ns):
    W, N = ns["ap_klassen_waage"], ns["ap_waage_nachschub"]
    FN, FP, T5, TF, LU = (("FundedNext", "fundednext", "mt5v2"), ("FundingPips", "fundingpips", "mt5v2"), ("The5ers", "the5ers", "mt5v2"),
                          ("Tradeify", "tradeify", "tvv2"), ("Lucid Trading", "lucid", "tvv2"))
    jm = 7 * 60 + 30.0                          # deutscher Planer-Tag: 23:30 UTC = 00:30 dt; Kandidaten müssen vor Mitternacht liegen

    def stand(eh_an):
        return {"jetzt_min": jm, "eh_an": eh_an, "id_fest": {}, "starts_heute": [],
                "offen": [lauf("chris-4e9a", "chris", *FN, "buy", 600)],              # der eine ungehedgte Echo-V2-Long (Chris FNX)
                "geplant": [plan(f"s{i}", u, *f, "sell", 400, jm + 20 + 15 * i)
                            for i, (u, f) in enumerate([("ina", T5), ("pascal", FP), ("simon", FP), ("ina", FP), ("mike", FP),
                                                        ("marco", T5), ("simon", FN), ("pascal", T5), ("simon", T5), ("marco", FP)])]}

    print("Schleife „1 Long laufen, kein Short“ (S3, 23:30–00:00 UTC)")
    st = stand(False)
    gezogen_alt = []
    for _takt in range(4):                      # alter Weg: ziehen → eh_tick hedgt den Gezogenen → zählt 0 → nächster
        aend, _info = N(st, W(st), random.Random(1))
        gezogen_alt += [a["plan_id"] for a in aend]
        for z in st["geplant"]:
            if z["plan_id"] in {a["plan_id"] for a in aend}:
                z.update(gehedgt=True, route="mt5")
    ok(len(gezogen_alt) >= 4, f"Echo-Hedge aus (alter Stand): jeder Takt zieht einen weiteren Short vor ({gezogen_alt}) — die Schleife")
    st = stand(True)
    gezogen = []
    for _takt in range(4):
        aend, info = N(st, W(st), random.Random(1))
        gezogen += [a["plan_id"] for a in aend]
    ok(not gezogen, f"Echo-Hedge an: kein Short vorgezogen, Takt für Takt ({gezogen})")
    ok(info and info[0]["kandidaten"] == 0 and info[0]["leicht"] == "sell", f"Waage meldet weiter „kein Short“, ohne Kandidaten ({info})")
    st["geplant"].append(plan("tage-mini", "aurel", *FN, "sell", 50, jm + 40, tage_mini={"tag": "x"}))
    st["geplant"].append(plan("funded", "aurel", *FN, "sell", 300, jm + 45, typ="funded_cfd"))
    aend, _ = N(st, W(st), random.Random(1))
    ok([a["plan_id"] for a in aend] == ["tage-mini"],
       f"Tage-Mini bleibt Echo V2 (ungehedgt, zählt) → darf ausgleichen; andere Kontoart (funded_cfd) nie ({[a['plan_id'] for a in aend]})")
    st2 = stand(True)
    st2["offen"].append(lauf("tf1", "mike", *TF, "buy", 215, typ="challenge"))
    st2["geplant"].append(plan("lu1", "marc", *LU, "sell", 215, jm + 60, typ="challenge"))   # > 30 min: kein „Paar folgt"
    aend, _ = N(st2, W(st2), random.Random(1))
    ok([a["plan_id"] for a in aend] == ["lu1"], f"Futures-Waage unverändert: Lucid-Short wird gegen den Tradeify-Long gezogen ({aend})")
    ok(not ns["ap_eh_wird_hedgen"]({"route": "mt5", "typ": "phase1"}, True) and not ns["ap_eh_wird_hedgen"]({"route": "mt5v2", "typ": "phase1"}, False)
       and ns["ap_eh_wird_hedgen"]({"route": "mt5v2", "typ": "phase2"}, True), "ap_eh_wird_hedgen: nur mt5v2-Challenge bei Schalter an")


PLANER_FUNKTIONEN = ("ap_planen", "ap_richtungen_delta", "ap_zeiten_verteilen", "ap_paare_legen", "ap_dicht_paare", "_ap_gegen_dicht",
                     "ap_fest_am_start", "ap_misch_bewerter", "ap_waage_passt", "ap_waage_zeile_zaehlt", "ap_klassen_waage")
BASIS = "f54267bf"     # Stand vor heute Nacht (30.10.2026 ~03:45 Dubai); ändert ein späterer Commit den Planer bewusst → nachziehen


def planer_unveraendert(src, ns):
    print("Planer unverändert (Richtungen, Zeiten, Anzahl wie vorher)")
    import subprocess
    try:
        alt = subprocess.run(["git", "-C", os.path.dirname(APP), "show", f"{BASIS}:app.py"], capture_output=True, text=True, check=True).stdout
    except Exception as e:
        alt = None
        print(f"  (git show {BASIS} nicht möglich: {e} — nur Quelltext-Prüfung)")

    def fn(t, name):
        i = t.index(f"\ndef {name}(") + 1
        return t[i:t.find("\n\n\n", i)]
    def ohne_gruppe(t):
        """GRUPPE WIE HT (30.10.2026, Slave 3): ap_planen bekam den Parameter gruppe (Verwalter-Gruppe mit eigenem Stand) — der HT-Weg
        (gruppe=None) muss Zeichen für Zeichen gleich bleiben. Vergleich ohne Docstring, Kommentare und Gruppen-Zeilen/-Zusätze."""
        t = re.sub(r'^(def [^\n]*\n(?:[^\n]*\n)*?)\s+"""[\s\S]*?"""\n', r"\1", t, count=1)
        out = []
        for z in t.replace(", gruppe=None", "").split("\n"):
            z = re.sub(r"\s+#.*$", "", z).replace(" and not gruppe", "")
            if "gruppe" in z.lower() or not z.strip():
                continue
            out.append(" ".join(z.split()))
        return "\n".join(out)
    if alt:
        # TAGE-MINI (30.10.2026, Befund S6): ap_waage_zeile_zaehlt bekam bewusst den Ausschluss der Tage-sammeln-Minis — Vergleich ohne ihn
        ohne_tm = lambda t: re.sub(r"\n    if z\.get\(\"tage_mini\"\):\n        return False[^\n]*", "", t)   # noqa: E731
        # TAGESENDE TOPSTEP (30.10.2026, S3): ap_planen liest kette_te und wertet den letzten Ketten-Trade wie abgehakt — bewusst, Vergleich ohne diese zwei Stellen
        ohne_te = lambda t: re.sub(r"\n    plaene = \[dict\(p, status=\"completed\"[^\n]*\n[^\n]*for p in plaene\]", "", re.sub(r',"\n\s+"kette_te:mt5_baseline->kette->tagesende", "order"', '", "order"', t))   # noqa: E731
        # KONTO DEAKTIVIERT (30.10.2026, S4): ap_planen nennt für deaktivierte Konten einen eigenen Grund, die Rechnung bleibt — Vergleich ohne diese Weiche
        ohne_dk = lambda t: t.replace('AP_GRUND_DEAKTIVIERT if a.get("deaktiviert") else ', "")   # noqa: E731
        anders = [n for n in PLANER_FUNKTIONEN
                  if (ohne_gruppe(ohne_te(ohne_dk(fn(src, n)))) != ohne_gruppe(fn(alt, n)) if n == "ap_planen" else ohne_tm(fn(src, n)) != fn(alt, n))]
        ok(not anders, f"Planer-/Waage-Rechnung identisch mit {BASIS} ({anders or 'alle gleich'})")
    ok("ap_eh_richtungen_mischen" not in src and "eh_an" not in fn(src, "ap_planen"), "kein Würfel-Code, ap_planen kennt den Schalter nicht")
    W, N = ns["ap_klassen_waage"], ns["ap_waage_nachschub"]
    jm = 600.0
    FN = ("FundedNext", "fundednext", "mt5v2")
    st = {"jetzt_min": jm, "eh_an": False, "id_fest": {}, "starts_heute": [], "offen": [lauf("o", "chris", *FN, "buy", 600)],
          "geplant": [plan("s1", "ina", *FN, "sell", 400, jm + 30), plan("s2", "simon", "FTMO", "ftmo", "mt5v2", "sell", 400, jm + 50)]}
    aend, _ = N(st, W(st), random.Random(2))
    ok(aend and all(a["von_richtung"] == a["nach_richtung"] for a in aend), "Waage dreht nie eine Richtung (von = nach), auch bei aus")


def stand_zeilen(ns, src):
    """Tage-Mini kommt wirklich in die Waage-Zeile (Prüfer S2 zu 58dbadfd): _ap_stand_laden mit der Fake-DB aus selftest_auto_delta."""
    print("Waage-Zeile aus _ap_stand_laden (Select + basiszeile/z.update)")
    import importlib.util
    from datetime import datetime, timedelta, timezone
    i = src.index("\ndef _ap_stand_laden(")
    blk = src[i:src.index("\n\n\n", i)]
    ok('"tm:mt5_baseline->tage_mini"' in blk and 'tage_mini=bool(p.get("tm"))' in blk, "Select liest mt5_baseline->tage_mini, Zeile setzt tage_mini")
    spec = importlib.util.spec_from_file_location("sad", os.path.join(HIER, "selftest_auto_delta.py"))
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    a = d.lade()
    jetzt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    basis = {"user_id": d.U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "sell",
             "master_tp": 600, "master_sl": 300, "master_contracts": 0.2, "route": "mt5v2", "start_um": (jetzt + timedelta(minutes=30)).isoformat(),
             "auto_plan": True, "auto_bestaetigt_at": jetzt.isoformat(), "created_at": jetzt.isoformat()}
    geplant = [dict(basis, id="p-mini", tm={"tag": "2026-10-30"}),          # PostgREST liefert den Alias tm
               dict(basis, id="p-norm", start_um=(jetzt + timedelta(minutes=45)).isoformat())]
    reg, _ = d.db_stubs(a, jetzt, geplant)
    reg["regeln"]["echo_hedge"] = {"an": True}
    stand = a["_ap_stand_laden"](reg, jetzt=jetzt)
    z = {r["plan_id"]: r for r in list(stand["geplant"]) + list(stand.get("folgetag") or [])}
    ok(stand.get("eh_an") is True, "Stand trägt den Schalter echo_hedge an")
    ok(z.get("p-mini", {}).get("tage_mini") is True and z.get("p-norm", {}).get("tage_mini") is False,
       f"Zeilen: Tage-Mini {z.get('p-mini', {}).get('tage_mini')}, normaler Plan {z.get('p-norm', {}).get('tage_mini')}")
    W = ns["ap_eh_wird_hedgen"]
    ok(not W(z["p-mini"], True) and W(z["p-norm"], True),
       "aus der echten Zeile: Tage-Mini bleibt Kandidat der Waage, die normale CFD-Challenge (eh_tick hedgt) nicht")


def main():
    ns, src = lade()
    schleife(ns)
    stand_zeilen(ns, src)
    planer_unveraendert(src, ns)
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
