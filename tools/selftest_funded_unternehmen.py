#!/usr/bin/env python3
"""Selbsttest UNT4: Funded-Planer-Regeln je Unternehmen = Standard + Abweichung je Feld (Master 05.11.2026). Standard = funded_plan_regeln /
funded_cfd_plan_regeln id 1 (live gelesen 05.11.2026, tools/selftest_funded_unternehmen_regeln.json, ohne IDs), Abweichung in
auto_plan_gruppe.funded_regeln. Prüft: Überlagerung (bitgleich ohne Abweichung, nur vorhandene Felder, nie name/namen), Schreiben über die Prüfung des
Standards (fdp_regeln_aendern / fcp_regel_patch) als Differenz, ↺, Leser je ID (fd_unt_reg/fd_unt_an), Routen (Verwalter, fremd, Schalter, Spalte fehlt,
GET-Sicht) und — mit UNT4_LIVE=<Auszug> — Vorher/Nachher aller Funded-Konten beider Unternehmen.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_funded_unternehmen.py"""
import copy
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


RG = json.load(open(os.path.join(HIER, "selftest_funded_unternehmen_regeln.json"), encoding="utf-8"))
FDP, FCP = RG["fdp"], RG["fcp"]
EMIN, HT, GID = "22222222-2222-4222-8222-222222222222", "11111111-1111-4111-8111-111111111111", "gr-emin"
ktx = lambda fr: {"ok": True, "gid_von": {EMIN: GID}, "zeilen": {GID: {"gruppe_id": GID, "funded_regeln": fr}}, "ht": frozenset({HT}), "memo": {}}   # noqa: E731
hol = lambda reg, name, pfad: app._unt_hol(next(f for f in reg["firmen"] if f["name"] == name), pfad)[1]   # noqa: E731

print("1) Überlagerung")
check(app.fd_unt_reg_von(FDP, {}) is FDP and app.fd_unt_reg(FDP, "futures", EMIN, ktx({})) is FDP and app.fd_unt_reg(FDP, "futures", HT, ktx({})) is FDP,
      "ohne Abweichung: dieselbe Regel-Zeile (bitgleich) für HT und Emin")
AB = {"futures": {"firmen": {"apextrader": {"je_groesse": {"150000": {"max_trade": 7000}, "50000": {"max_trade": 1}}, "name": "X", "gibtsnicht": 1}}}}
e = app.fd_unt_reg(FDP, "futures", EMIN, ktx(AB))
check(hol(e, "Apex Trader", ["je_groesse", "150000", "max_trade"]) == 7000 and hol(e, "Apex Trader", ["je_groesse", "150000", "ziel_gewinn"]) == 15000
      and "50000" not in next(f for f in e["firmen"] if f["name"] == "Apex Trader")["je_groesse"] and next(f for f in e["firmen"] if f["name"] == "Apex Trader")["name"] == "Apex Trader",
      "Abweichung wirkt je Feld, übrige Felder Standard; nie neue Größen, nie name/namen, nie unbekannte Felder")
K1 = ktx(AB)
e1 = app.fd_unt_reg(FDP, "futures", EMIN, K1)
check(app.fd_unt_reg(FDP, "futures", HT, K1) is FDP and app.fd_unt_reg(FDP, "futures", EMIN, K1) is e1, "HT bleibt Standard; Emins Regel je Takt gemerkt")
check([f["name"] for f in app.fd_unt_an(FDP, "futures", EMIN, ktx({"futures": {"firmen": {"tradeify": {"an": True}}}}))] == ["Apex Trader", "Tradeify", "FTMO Futures"],
      "fd_unt_an: Emin schaltet Tradeify Funded an (HT nicht)")
check(app.fd_unt_reg(FDP, "futures", EMIN, dict(ktx(AB), ok=False)) is FDP, "Kontext nicht lesbar → Anzeige rechnet Standard")
_fh = dict(FDP, user_ids=[HT, EMIN])   # live: funded_cfd_plan_regeln.user_ids enthält auch Emin-IDs (S4)
check(app.fd_unt_an(_fh, "futures", EMIN, dict(ktx(AB), ok=False), True) == [] and app.fd_unt_reg(_fh, "futures", HT, dict(ktx(AB), ok=False), True) is _fh,
      "Prüfer S2/S4: Kontext nicht lesbar → Planer (streng) schlägt für Emin nichts vor, auch wenn er in user_ids der Regel steht; HT (Kontext ht) plant weiter")
_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check('fd_unt_reg(reg, "futures", u, _ktx, True)' in _src and 'fd_unt_reg(reg, "cfd", uid, _ktx, True)' in _src
      and 'fd_unt_reg(reg, "cfd", a.get("user_id"), None, True) or {}).get("firmen") or []' in _src, "beide Planer und die Funded-Ziel-Wache lesen streng (kein Rückfall `or firmen`)")

print("2) Schreiben = Prüfung des Standards auf der wirksamen Regel, gespeichert nur die Differenz")
fa = lambda eff, b: app.fdp_regeln_aendern(dict(eff, updated_at=FDP["updated_at"]), dict(b, updated_at=FDP["updated_at"]))   # noqa: E731
Z = {"gruppe_id": GID, "funded_regeln": {}}
abw, eff, g = app.fd_unt_schreiben(FDP, Z, "futures", {"firma": {"name": "Apex Trader", "je_groesse": {"150000": {"max_trade": 7000}}}}, fa)
check(g is None and abw == {"firmen": {"apextrader": {"je_groesse": {"150000": {"max_trade": 7000}}}}} and hol(eff, "Apex Trader", ["je_groesse", "150000", "max_trade"]) == 7000,
      f"Futures: Max Trade Apex 150k → nur diese Abweichung ({abw or g})")
Z2 = {"gruppe_id": GID, "funded_regeln": {"futures": abw}}
abw2, _e, g = app.fd_unt_schreiben(FDP, Z2, "futures", {"firma": {"name": "Apex Trader", "je_groesse": {"150000": {"max_trade": 7500}}}}, fa)
check(g is None and abw2 == {}, "Wert = Standard → Abweichung weg")
abw3, _e, g = app.fd_unt_schreiben(FDP, Z2, "futures", {"standard": {"firma": "Apex Trader", "pfad": ["je_groesse", "150000", "max_trade"]}}, fa)
check(g is None and abw3 == {}, "↺ auf Standard")
_a, _e, g = app.fd_unt_schreiben(FDP, Z, "futures", {"firma": {"name": "Apex Trader", "je_groesse": {"150000": {"max_trade": -5}}}}, fa)
check(bool(g), f"Grenzen wie der Standard ({g})")
abw4, eff4, g = app.fd_unt_schreiben(FDP, Z, "futures", {"firma": {"name": "Tradeify", "an": True}}, fa)
check(g is None and abw4 == {"firmen": {"tradeify": {"an": True}}}, f"Firma an im Unternehmen ({abw4 or g})")
fn = next(f for f in FCP["firmen"] if f["name"] == "FundedNext")
z100 = fn["je_groesse"]["100000"]["ziel"]
neu_z = [z100[0] + 500, z100[1] + 500] if isinstance(z100, list) else z100 + 500
abw5, eff5, g = app.fd_unt_schreiben(FCP, Z, "cfd", {"firma": "FundedNext", "groesse": "100000", "feld": "ziel", "wert": neu_z}, app.fcp_regel_patch)
check(g is None and abw5 == {"firmen": {"fundednext": {"je_groesse": {"100000": {"ziel": neu_z}}}}}, f"CFD: Ziel FundedNext 100k ({abw5 or g})")
_a, _e, g = app.fd_unt_schreiben(FCP, Z, "cfd", {"firma": "FundedNext", "groesse": "100000", "feld": "tp_erster", "wert": 100}, app.fcp_regel_patch)   # Feld neu
check(g is None and _a and "tp_erster" in json.dumps(_a), f"Feld, das es im Standard (noch) nicht gibt, als ganzer Wert gespeichert ({_a or g})")
_a, _e, g = app.fd_unt_schreiben(FCP, Z, "cfd", {"param": "tp_min_usd", "wert": 200}, app.fcp_regel_patch)
check(bool(g) and "parameter" in g, f"CFD-Parameter ohne Spalte parameter im Standard → Meldung wie beim Standard ({g})")
FCP_P = dict(FCP, parameter={})
abw6, eff6, g = app.fd_unt_schreiben(FCP_P, Z, "cfd", {"param": "tp_min_usd", "wert": 200}, app.fcp_regel_patch)
check(g is None and abw6 == {"parameter": {"tp_min_usd": 200.0}} and app.fcp_param(eff6)["tp_min_usd"] == 200.0, f"CFD-Parameter im Unternehmen ({abw6 or g})")
abw7, _e, g = app.fd_unt_schreiben(FCP_P, {"funded_regeln": {"cfd": abw6}}, "cfd", {"param": "tp_min_usd", "wert": None}, app.fcp_regel_patch)
check(g is None and abw7 == {}, "Parameter leer → wieder wie der Standard (nicht der Code-Standard)")

print("2b) Fremd-Review: Felder neu / weg / anderer Typ (Refund, Gewinntage, Consistency, TP-Deckel leer, Kontrakt-Zeilen)")
def rund(std, art, body, fn):
    _a, eff, g = app.fd_unt_schreiben(std, Z, art, body, fn)
    if g:
        return g
    soll = fn(dict(std), body)[0]
    return None if json.dumps(app.fd_unt_overlay(std["firmen"], (_a or {}).get("firmen") or {}), sort_keys=True) == json.dumps((soll or {}).get("firmen") or std["firmen"], sort_keys=True) else "Rundweg ungleich"
FAELLE = []
for f in FCP["firmen"]:
    FAELLE.append(("cfd", f["name"] + " Refund an/aus", {"firma": f["name"], "feld": "erster_payout", "wert": not bool(f.get("erster_payout"))}))
    FAELLE.append(("cfd", f["name"] + " Consistency 50", {"firma": f["name"], "feld": "consistency_pct", "wert": 50}))
    if f.get("tp_deckel_plus") is not None:
        FAELLE.append(("cfd", f["name"] + " TP-Deckel leer", {"firma": f["name"], "feld": "tp_deckel_plus", "wert": None}))
    g0 = sorted((f.get("je_groesse") or {}).keys())[0]
    FAELLE.append(("cfd", f["name"] + f" Gewinntage {g0} umschalten", {"firma": f["name"], "groesse": g0, "feld": "gewinntage",
                                                                      "wert": not isinstance(f["je_groesse"][g0].get("gewinntage"), dict)}))
for f in FDP["firmen"]:
    FAELLE.append(("futures", f["name"] + " Consistency", {"firma": {"name": f["name"], "consistency_pct": None if f.get("consistency_pct") else 40}}))
apx = next(f for f in FDP["firmen"] if f["name"] == "Apex Trader")
FAELLE.append(("futures", "Apex 150k Kontrakt-Zeile 4 dazu", {"firma": {"name": "Apex Trader", "je_groesse": {"150000": {"kontrakte": {"2": 0.8, "3": 0.1, "4": 0.1}}}}}))
FAELLE.append(("futures", "Apex 150k Kontrakt-Zeile 3 weg", {"firma": {"name": "Apex Trader", "je_groesse": {"150000": {"kontrakte": {"2": 1.0}}}}}))
schief = []
for art, name, body in FAELLE:
    std = FCP if art == "cfd" else FDP
    g = rund(std, art, body, app.fcp_regel_patch if art == "cfd" else fa)
    if g:
        schief.append(f"{name}: {g}")
check(not schief, f"{len(FAELLE)} Strukturänderungen im Unternehmen speicherbar, Standard + Abweichung = gewünschte Regel ({schief[:3] or 'alle'})")
_a, _e, g = app.fd_unt_schreiben(FDP, Z, "futures", {"firma": {"name": "Apex Trader", "je_groesse": {"999000": {"dd": 1}}}}, fa)
check(bool(g), f"neue Größe → abgelehnt ({g})")
check(app.fd_unt_overlay(FDP["firmen"], {"apextrader": {"je_groesse": {"999000": {"__wert__": {"dd": 1}}}}}) == json.loads(json.dumps(FDP["firmen"])),
      "Marker legen nie eine neue Größe an")
_a, _e, g = app.fd_unt_schreiben(dict(FCP, parameter={}), Z, "cfd", {"param": "richtung_laufend", "wert": True}, app.fcp_regel_patch)
check(bool(g) and "Schalter" in g, f"Parameter-Schalter (richtung_laufend) gilt für alle ({g})")
a1, _e, g = app.fd_unt_schreiben(FDP, Z, "futures", {"firma": {"name": "Apex Trader", "je_groesse": {"150000": {"kontrakte": {"2": 0.8, "3": 0.1, "4": 0.1}}}}}, fa)
a2, _e, g2 = app.fd_unt_schreiben(FDP, {"funded_regeln": {"futures": a1}}, "futures", {"standard": {"firma": "Apex Trader", "pfade": app.fd_unt_liste(a1)["firmen"]["apextrader"]}}, fa)
check(g is None and g2 is None and a2 == {}, f"↺ mit mehreren Pfaden (Kontrakte) → wieder Standard ({app.fd_unt_liste(a1)})")

print("3) Routen")
UPD, ZEILE = [], {"gruppe_id": GID, "aktiv": True, "funded_regeln": {}, "regeln_at": None}
app.sb_select = lambda t, p: [dict(ZEILE)] if t == "auto_plan_gruppe" else []
app.sb_update = lambda t, f, u: (UPD.append((t, f, u)), [u])[1]
app._fdp_regeln_laden = lambda: copy.deepcopy(FDP)
app._fcp_regeln_laden = lambda: copy.deepcopy(FCP)
app._planer_schreib_gate = lambda: None
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": GID, "name": "Emin", "verwalter_id": EMIN}, {"id": "gr-x", "name": "X", "verwalter_id": "x"}]}
app.ap_unt_kontext = lambda frisch=False: ktx(ZEILE.get("funded_regeln") or {})
app.ap_planer_gruppen = lambda nur_aktiv=False: [{"gruppe_id": GID, "name": "Emin", "ids": frozenset({EMIN})}]
app._fdp_login = lambda: (False, EMIN, EMIN, None)
app._fcp_login = lambda: (False, EMIN, {EMIN}, EMIN, None)
c = app.app.test_client()
r = c.post("/admin/funded-plan/regeln", json={"gruppe_id": GID, "firma": {"name": "Apex Trader", "je_groesse": {"150000": {"max_trade": 7000}}}})
d = r.get_json() or {}
check(r.status_code == 200 and UPD and UPD[-1][2]["funded_regeln"] == {"futures": {"firmen": {"apextrader": {"je_groesse": {"150000": {"max_trade": 7000}}}}}}
      and (d.get("regeln") or {}).get("abweichung", {}).get("firmen", {}).get("apextrader") and "regeln_at" in UPD[-1][2],
      f"Verwalter Emin speichert eine Futures-Abweichung ({r.status_code} {d.get('msg', '')})")
r = c.post("/admin/funded-plan/regeln", json={"gruppe_id": "gr-x", "firma": {"name": "Apex Trader", "an": False}})
check(r.status_code == 403, "fremdes Unternehmen → 403")
r = c.post("/admin/funded-plan/regeln", json={"gruppe_id": GID, "schalter": {"aktiv": True}})
check(r.status_code == 400, "Schalter im Unternehmen → 400 (gelten für alle)")
r = c.post("/admin/funded-plan/regeln", json={"firma": {"name": "Apex Trader", "an": False}, "updated_at": FDP["updated_at"]})
check(r.status_code == 403, "Verwalter ohne gruppe_id: Standard nie (403)")
r = c.post("/admin/funded-cfd-plan/regel", json={"gruppe_id": GID, "firma": "FundedNext", "groesse": "100000", "feld": "ziel", "wert": neu_z})
check(r.status_code == 200 and UPD[-1][2]["funded_regeln"].get("cfd") == {"firmen": {"fundednext": {"je_groesse": {"100000": {"ziel": neu_z}}}}},
      f"CFD-Abweichung gespeichert ({r.status_code} {(r.get_json() or {}).get('msg', '')})")
r = c.post("/admin/funded-cfd-plan/regel", json={"gruppe_id": GID, "zeit": "vorlauf_min", "wert": 20})
check(r.status_code == 400, "CFD-Zeiten im Unternehmen → 400")
ZEILE.pop("funded_regeln")
r = c.post("/admin/funded-cfd-plan/regel", json={"gruppe_id": GID, "firma": "FundedNext", "an": False})
check(r.status_code == 409 and "noch nicht freigeschaltet" in (r.get_json() or {}).get("msg", ""), "Spalte fehlt → klare Meldung „noch nicht freigeschaltet“")
ZEILE["funded_regeln"] = {"cfd": {"firmen": {"fundednext": {"je_groesse": {"100000": {"ziel": neu_z}}}}}}
app.fcp_planen = lambda trocken=True, **k: {"ok": True, "firmen": app.fcp_firmen_anzeige(FCP["firmen"], app.fcp_param(FCP)), "parameter": {"wert": app.fcp_param(FCP)},
                                            "geplant": [], "ziel": [], "ausgelassen": [], "plaene": [], "konten_stand": []}
app.fcp_sicht = lambda erg, sicht: erg
r = c.get("/admin/funded-cfd-plan")
d = r.get_json() or {}
fn_d = next((f for f in d.get("firmen") or [] if f.get("name") == "FundedNext"), {})
check(r.status_code == 200 and (d.get("unternehmen") or {}).get("gruppe_id") == GID and d.get("gruppe_darf") is True
      and fn_d.get("je_groesse", {}).get("100000", {}).get("ziel") == neu_z and ["je_groesse", "100000", "ziel"] in d.get("abweichung", {}).get("firmen", {}).get("fundednext", []),
      "GET CFD im Login Emin: wirksame Werte + Markierung")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
fn_src = lambda n: src[src.index("\ndef " + n + "("):src.index("\ndef ", src.index("\ndef " + n + "(") + 5)]   # noqa: E731
LESER = {"fdp_planen": "an_von(a.get(\"user_id\"))", "fcp_planen": "fd_unt_reg(reg, \"cfd\", uid, _ktx, True)", "zw_funded_cfd": "fd_unt_reg(reg, \"cfd\"",
         "konto_ziele": "fd_unt_reg(_fcp_regeln_laden()", "ap_bal_auto_gruppen_tick": "fd_unt_reg(_r, \"futures\""}
fehlt = [k for k, m in LESER.items() if m not in fn_src(k)] + ([] if '"id,user_id,name,firm,starting_balance,created_at"' in fn_src("zw_funded_cfd") else ["zw_funded_cfd liest user_id"])
check(not fehlt, f"{len(LESER)} Funded-Leser lesen die Regel des Unternehmens ({fehlt or 'alle'})")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("data-fcr-std=" in html and "data-e2-std=" in html and "body.gruppe_id = R.unternehmen.gruppe_id" in html and "gruppe_id: fcrUnt().gruppe_id" in html
      and "const darfG = darfR && !(R && R.unternehmen)" in html, "Frontend: Markierung + ↺, Speichern mit gruppe_id, globale Karten im Unternehmen nur Anzeige")

PFAD = os.environ.get("UNT4_LIVE")
if PFAD and os.path.exists(PFAD):
    print("4) Live: Vorher/Nachher aller Funded-Konten beider Unternehmen")
    L = json.load(open(PFAD, encoding="utf-8"))
    G = set(L.get("mitglieder") or []) | {L.get("verwalter")}
    K = L["konten"]

    def rechnen(a, fdp, fcp):
        g = app._wd_konto_groesse(a)
        if a["account_type"] == "funded":
            an = [f for f in fdp["firmen"] if f.get("an")]
            r_ = app.ap_regel_finden(an, a.get("firm"))
            return json.dumps({"an": bool(r_), "jg": ((r_ or {}).get("je_groesse") or {}).get(str(int(g or 0)))}, sort_keys=True)
        an = [f for f in fcp["firmen"] if f.get("an")]
        r_ = app.ap_regel_finden(an, a.get("firm"))
        return json.dumps({"an": bool(r_), "jg": app.fcp_je_groesse(r_, g) if r_ else None, "p": app.fcp_param(fcp)}, sort_keys=True, default=str)

    def lauf(fr):
        k = {"ok": True, "gid_von": {u: GID for u in G}, "zeilen": {GID: {"funded_regeln": fr}}, "ht": frozenset(), "memo": {}}
        return [a for a in K if rechnen(a, L["fdp"], L["fcp"]) != rechnen(a, app.fd_unt_reg(L["fdp"], "futures", a["user_id"], k), app.fd_unt_reg(L["fcp"], "cfd", a["user_id"], k))]
    anders = lauf({})
    check(not anders, f"alle {len(K)} Funded-Konten ({sum(a['user_id'] in G for a in K)} bei Emin) bitgleich ohne Abweichung ({len(anders)} anders)")
    anders = lauf({"cfd": {"firmen": {"fundednext": {"je_groesse": {"100000": {"ziel": neu_z}}}}}})
    em_fn = [a for a in K if a["user_id"] in G and a["account_type"] == "funded_cfd" and "fundednext" in str(a.get("firm")).lower().replace(" ", "")
             and app._wd_konto_groesse(a) == 100000]
    check(anders and all(a["user_id"] in G for a in anders) and {a["id"] for a in anders} == {a["id"] for a in em_fn},
          f"Probe Emin FundedNext 100k Ziel: genau seine FundedNext-100k-Konten anders ({len(anders)}/{len(em_fn)}), 0 HT")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
