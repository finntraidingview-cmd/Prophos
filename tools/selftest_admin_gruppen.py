#!/usr/bin/env python3
"""Selbsttest ADMIN-GRUPPEN (app.py, 08.10.2026, Finn: „Emin bekommt das volle Admin wie Finn, aber nur mit den IDs seiner Gruppe";
Nachtrag 23:00: Tabellen id_gruppen + id_gruppe_mitglied, sql/2026-10-08_admin_gruppen.sql). Ohne Netz: die echten Funktionen laufen
gegen eine Fake-DB (sb_select/_sb_anfrage/_auth_* gestubbt), die Routen über einen Flask-Testclient.
Geprüft: Mengen-Logik (HT alle · Verwalter = Gruppe · Mitglied ohne Zugang = kein Admin), Finns ?gruppe=-Filter, Gruppen-Liste für die
Chips, _admin_basis-Ausblendung, Trade-Planer-Sicht (ap_*), pc-stand-Filter, Schreib-Schutz fremder Objekte (wd-plaene PATCH/DELETE/POST,
prop-baum, /ids POST, konto_balance_darf). Platzhalter-IDs, keine echten Namen. Aufruf: python3 tools/selftest_admin_gruppen.py"""
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, g, jsonify, request

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

HT1, HT2, NEU = "uid-ht-0001", "uid-ht-0002", "uid-neu-0003"   # ≥ 10 Zeichen wie echte IDs (die Routen prüfen die Länge)
VERW, MITGL = "uid-verw-0004", "uid-mitg-0005"
SOLO = "uid-solo-0006"                     # admin_zugang nur_eigene, aber keine eigene Gruppe
G_HT, G_V = "g-ht-0000", "g-verw-0000"
GRUPPEN = [{"id": G_HT, "name": "Hermann Technologies", "verwalter_user_id": None},
           {"id": G_V, "name": "Gruppe V", "verwalter_user_id": VERW}]
MITGLIEDER = [{"user_id": HT1, "gruppe_id": G_HT}, {"user_id": HT2, "gruppe_id": G_HT},
              {"user_id": VERW, "gruppe_id": G_V}, {"user_id": MITGL, "gruppe_id": G_V}]
ZUGANG = {VERW: True, SOLO: True}
ALLE = [HT1, HT2, NEU, VERW, MITGL, SOLO]
DATEN = {"gruppen": [{"id": x["id"], "name": x["name"], "verwalter_id": x["verwalter_user_id"]} for x in GRUPPEN],
         "mitglieder": MITGLIEDER}

FEHLER = []


def check(bed, name):
    if not bed:
        FEHLER.append(name)
    print(("✓ " if bed else "✗ ") + name)


class Antwort:
    def __init__(self, status, daten):
        self.status_code, self._d = status, daten

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


def lade():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)

    namen = ["admin_zugang_nur_eigene", "admin_gruppen_daten", "admin_sicht_menge", "admin_sicht_lesen", "admin_in_sicht",
             "admin_sicht_filter", "_admin_verwalter_gruppen_ids", "admin_gruppen_liste", "admin_gruppe_filter_menge",
             "admin_gruppe_ist_ht", "_admin_filter_aus_anfrage", "_admin_nur_uid", "_admin_sicht", "_admin_eingeschraenkt",
             "_admin_darf_uid", "_admin_verwalter", "_wd_login", "_wd_personen", "_admin_basis",
             "ap_sicht", "ap_sicht_uid", "ap_eingriff_sicht", "ap_eingriff_admin_reiter", "ap_admin_reiter_ok", "ap_eingriff_filter",
             "_ap_gruppe_lesen", "_ap_sicht_param", "konto_balance_darf",
             "admin_pc_stand", "admin_prop_baum", "admin_wd_plaene", "admin_auto_plan_ids"]
    teile = [konst(k) for k in ("AP_SICHT_ADMIN", "AP_EINGRIFF_MAX", "AUTH_LISTE_CACHE_S", "ADMIN_GRUPPE_HT", "AP_NUR_PLANER_TXT")]
    teile += ["_admin_zugang_cache = {}", '_admin_gruppe_cache = {"bis": 0.0, "daten": None}']
    teile += [block(n) for n in namen]
    ns = {"re": re, "time": time, "threading": threading, "requests": requests, "request": request, "jsonify": jsonify, "g": g,
          "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "_kurz_cache_lock": threading.Lock(),
          "SUPABASE_SERVICE_KEY": "svc", "SUPABASE_URL": "https://beispiel.invalid", "ADMIN_EMAILS": {"admin@beispiel.invalid"},
          "ADMIN_EXCLUDE_EMAILS": {"aus@beispiel.invalid"}, "AP_TYPEN": ("challenge", "phase1", "phase2")}
    exec("\n".join(teile), ns)
    return ns


def fake_db(ns, tabellen_fehlen=False):
    log = {"select": [], "anfrage": [], "insert": []}
    plaene = {"plan-ht-0001": HT1, "plan-mitglied-1": MITGL, "plan-verwalter-1": VERW}
    konten = {"a-ht": HT1, "a-mitgl": MITGL}

    def sb_select(table, params):
        log["select"].append((table, dict(params)))
        if table in ("id_gruppen", "id_gruppe_mitglied") and tabellen_fehlen:
            raise requests.exceptions.HTTPError(response=Antwort(404, {}))
        if table == "id_gruppen":
            return [dict(x) for x in GRUPPEN]
        if table == "id_gruppe_mitglied":
            return [dict(x) for x in MITGLIEDER]
        if table == "admin_zugang":
            uid = params["user_id"].split(".", 1)[1]
            return [{"nur_eigene": True}] if ZUGANG.get(uid) else []
        if table == "trade_plans":
            pid = params.get("id", "").split(".", 1)[-1]
            return [{"user_id": plaene[pid]}] if pid in plaene else []
        if table == "accounts":
            aid = params.get("id", "").split(".", 1)[-1]
            return [{"id": aid, "user_id": konten[aid]}] if aid in konten else []
        if table == "mt5_live":
            return [{"user_id": u} for u in ALLE]
        return []

    def _sb_all(table, params):
        if table == "accounts":
            return [{"id": f"k-{u}", "user_id": u, "account_type": "funded"} for u in ALLE]
        return []

    def _auth_user_anfrage(token):
        return Antwort(200, {"id": token}) if token else Antwort(401, {})

    def _auth_liste_anfrage():
        mails = {HT2: "aus@beispiel.invalid"}
        return Antwort(200, {"users": [{"id": u, "email": mails.get(u, f"{u}@beispiel.invalid"), "user_metadata": {"name": u}}
                                       for u in ALLE]})

    def _sb_anfrage(methode, url, **kw):
        log["anfrage"].append((methode, url, kw.get("params")))
        return Antwort(200, [{"id": "x"}])

    def sb_insert(table, body):
        log["insert"].append((table, body))
        return {"id": "sig-1"}

    ns.update({"sb_select": sb_select, "_sb_all": _sb_all, "_auth_user_anfrage": _auth_user_anfrage,
               "_auth_liste_anfrage": _auth_liste_anfrage, "_sb_anfrage": _sb_anfrage, "_sb_pruefen": lambda r: None,
               "sb_insert": sb_insert, "_sb_headers": lambda p=None: {}, "_wt_now_iso": lambda: "2026-10-08T20:00:00Z",
               "pb_handelstag": lambda jetzt=None: ("2026-10-08", None, None),
               "pc_stand_zusammenfassen": lambda rows, jetzt: {r["user_id"]: {"pcs": []} for r in rows}, "PC_STAND_LEBT_S": 90,
               "_wd_ende_upd": lambda *a: (None, (404, "Plan nicht gefunden")), "_cme_handelstag": lambda *a: "2026-10-08",
               "_ap_im_planer": lambda uid: False, "_firm_norm": lambda x: x,
               "WD_PLAN_FELDER": ("master_account_id", "user_id"), "_wd_ohne_master_sl": lambda b: (b, False)})
    ns["_admin_zugang_cache"].clear()
    ns["_admin_gruppe_cache"].update(bis=0.0, daten=None)
    return log


def main():
    ns = lade()
    menge, liste, filt = ns["admin_sicht_menge"], ns["admin_gruppen_liste"], ns["admin_gruppe_filter_menge"]

    # 1) Mengen-Logik
    check(menge(HT1, False, DATEN) == (None, False), "HT-Mitglied (Finn) → alle IDs (None)")
    check(menge(NEU, False, DATEN) == (None, False), "neue ID ohne Zeile → zählt als HT, alle IDs")
    check(menge(VERW, True, DATEN) == (frozenset({VERW, MITGL}), True), "Verwalter → {Verwalter, Mitglied}, verwalter=True")
    check(menge(VERW, False, DATEN) == (frozenset({VERW, MITGL}), True), "Verwalter-Rolle hängt an id_gruppen, nicht am admin_zugang-Flag")
    check(menge(MITGL, False, DATEN) == (frozenset({MITGL}), False), "Mitglied ohne admin_zugang → nur sich selbst, kein Admin")
    check(menge(SOLO, True, DATEN) == (frozenset({SOLO}), False), "admin_zugang nur_eigene ohne Gruppe → nur sich selbst (wie bis .1380)")
    check(menge(HT1, False, {}) == (None, False) and menge(SOLO, True, {}) == (frozenset({SOLO}), False),
          "ohne Gruppen-Tabellen: alles wie vor den Gruppen")

    # 2) Finns Filter + Chips
    check(filt("", DATEN, ALLE) is None, "kein ?gruppe= → kein Filter")
    check(filt(G_V, DATEN, ALLE) == frozenset({VERW, MITGL}), "?gruppe=<Gruppe V> → Verwalter + Mitglied")
    ht = filt(G_HT, DATEN, ALLE)
    check(ht == frozenset({HT1, HT2, NEU, SOLO}) and filt("ht", DATEN, ALLE) == ht, "?gruppe=HT (id oder 'ht') → alle ohne Gruppe V, neue ID inklusive")
    check(filt("g-gibt-es-nicht", DATEN, ALLE) == frozenset(), "unbekannte Gruppe → leer (nie alles)")
    li = liste(DATEN)
    check([x["name"] for x in li] == ["Hermann Technologies", "Gruppe V"] and li[0]["ht"] and not li[1]["ht"],
          "Chips: HT zuerst, Name aus id_gruppen.name")
    check(li[1]["ids"] == sorted([VERW, MITGL]) and li[0]["ausser"] == sorted([VERW, MITGL]), "Chips: ids je Gruppe, HT mit ausser-Liste")
    check(ns["admin_gruppe_ist_ht"](G_HT, DATEN) and ns["admin_gruppe_ist_ht"]("ht", DATEN) and not ns["admin_gruppe_ist_ht"](G_V, DATEN),
          "HT-Erkennung über verwalter_user_id null")
    sf, ins = ns["admin_sicht_filter"], ns["admin_in_sicht"]
    check(sf(None) is None and sf("u1") == "eq.u1" and sf(frozenset({"b", "a"})) == "in.(a,b)" and sf(frozenset()).startswith("eq.0000"),
          "PostgREST-Filter: alle / eine ID / Gruppe / leer = nie alles")
    check(ins("x", None) and ins("a", "a") and not ins("b", "a") and ins("a", frozenset({"a"})) and not ins(None, frozenset({"a"})),
          "admin_in_sicht")

    # 3) Trade-Planer-Sicht (rein)
    su, es, ok_, ef, ea = ns["ap_sicht_uid"], ns["ap_eingriff_sicht"], ns["ap_admin_reiter_ok"], ns["ap_eingriff_filter"], ns["ap_eingriff_admin_reiter"]
    gr = frozenset({VERW, MITGL})
    check(su(False, VERW, True, "admin", False, gr) == gr and su(False, VERW, True, "", False, gr) == VERW,
          "Lauf/Delta: Verwalter im Admin-Reiter = Gruppe, Planer-Seite = eigene ID")
    check(su(False, MITGL, True, "admin", True, None) == MITGL, "Mitglied (auch im Planer) im Admin-Reiter → nur eigene ID, nie alle")
    check(es(False, VERW, False, True, "admin", gr) == gr and es(False, MITGL, True, True, "admin", None) == MITGL,
          "Eingriffe: Verwalter = Gruppe, Mitglied = eigene ID")
    check(ok_(False, False, True, "admin", verwalter=True) and not ok_(False, False, True, "admin") and not ok_(False, False, True, "", verwalter=True),
          "Lese-Zugang Admin-Reiter: Verwalter nur mit sicht=admin, Mitglied nie")
    check(not ea(False, VERW, True, "admin", False), "Verwalter darf keine BELIEBIGEN Pläne (Route prüft je Plan die Gruppe)")
    pid = "00000000-0000-0000-0000-00000000aa01"
    p, _b, _a = ef("bestaetigen", [pid], gr)
    check(p["user_id"] == "in.(" + ",".join(sorted(gr)) + ")", "Bestätigen-Guard: user_id in (Gruppe)")
    p2, _b, _a = ef("bestaetigen", [pid], VERW)
    check(p2["user_id"] == f"eq.{VERW}", "Bestätigen-Guard: eine ID wie bisher")
    erg = {"geplant": [{"user_id": HT1}, {"user_id": MITGL}, {"user_id": VERW}], "ausgelassen": [{"user_id": HT2}],
           "ausgleich": {"offen": [{"user_id": HT1}], "hinweise": [{"user_id": MITGL}]}}
    s1 = ns["ap_sicht"](erg, gr)
    check([x["user_id"] for x in s1["geplant"]] == [MITGL, VERW] and s1["ausgelassen"] == [] and s1["sicht"] == "gruppe"
          and s1["ausgleich"]["offen"] == [] and len(s1["ausgleich"]["hinweise"]) == 1, "Lauf-Antwort: nur Gruppe, sicht=gruppe")
    check(ns["ap_sicht"](erg, HT1)["sicht"] == "eigene" and len(ns["ap_sicht"](erg, HT1)["geplant"]) == 1, "Lauf-Antwort eine ID wie bisher")

    # 4) konto_balance_darf
    kbd = ns["konto_balance_darf"]
    check(kbd(VERW, "v@x", {"user_id": MITGL}, set(), gr) and not kbd(VERW, "v@x", {"user_id": HT1}, set(), gr)
          and not kbd(MITGL, "m@x", {"user_id": VERW}, set(), None) and kbd(HT1, "admin@beispiel.invalid", {"user_id": MITGL}, {"admin@beispiel.invalid"}),
          "Balance lesen: Verwalter für seine Gruppe, nicht für HT; Mitglied nicht für den Verwalter; Admin immer")

    # 5) Routen über Flask (Fake-DB)
    log = fake_db(ns)
    app = Flask("selftest_admin_gruppen")
    app.add_url_rule("/admin/pc-stand", "pc", ns["admin_pc_stand"], methods=["GET", "OPTIONS"])
    app.add_url_rule("/admin/prop-baum", "pb", ns["admin_prop_baum"], methods=["GET", "POST", "OPTIONS"])
    app.add_url_rule("/admin/wd-plaene", "wd", ns["admin_wd_plaene"], methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"])
    app.add_url_rule("/admin/auto-plan/ids", "ids", ns["admin_auto_plan_ids"], methods=["GET", "POST", "OPTIONS"])
    ns["_admin_auth"] = lambda: (None, (jsonify({"error": "Nur für Admins"}), 403))
    c = app.test_client()
    h = lambda uid: {"sb-token": uid}

    d = c.get("/admin/pc-stand", headers=h(HT1)).get_json()
    check(set(d["stand"]) == set(ALLE), "pc-stand: Finn (HT) sieht alle IDs")
    d = c.get("/admin/pc-stand", headers=h(VERW)).get_json()
    check(set(d["stand"]) == {VERW, MITGL}, "pc-stand: Verwalter nur seine Gruppe")
    d = c.get("/admin/pc-stand", headers=h(MITGL)).get_json()
    check(set(d["stand"]) == {MITGL}, "pc-stand: Mitglied nur sich")
    d = c.get(f"/admin/pc-stand?gruppe={G_V}", headers=h(HT1)).get_json()
    check(set(d["stand"]) == {VERW, MITGL}, "pc-stand: Finn mit ?gruppe=<Gruppe V>")
    d = c.get("/admin/pc-stand?gruppe=ht", headers=h(HT1)).get_json()
    check(set(d["stand"]) == {HT1, HT2, NEU, SOLO}, "pc-stand: Finn mit ?gruppe=ht (neue ID ohne Zeile inklusive)")
    d = c.get(f"/admin/pc-stand?gruppe={G_HT}", headers=h(VERW)).get_json()
    check(set(d["stand"]) == {VERW, MITGL}, "pc-stand: Verwalter kann ?gruppe= nicht ausweiten")

    # _admin_basis: Ausblendung
    with app.test_request_context("/admin/overview", headers=h(HT1)):
        ns["_wd_login"]()
        b = ns["_admin_basis"]()
        check(b["excluded_ids"] == {HT2} and b["excluded_names"] == ["aus@beispiel.invalid"], "Übersicht Finn: nur die Server-Ausblendung")
    with app.test_request_context(f"/admin/overview?gruppe={G_V}", headers=h(HT1)):
        ns["_wd_login"]()
        b = ns["_admin_basis"]()
        check(b["excluded_ids"] == {HT1, HT2, NEU, SOLO}, "Übersicht Finn mit Gruppe V: alle außer Gruppe V ausgeblendet")
    with app.test_request_context("/admin/overview?gruppe=ht", headers=h(HT1)):
        ns["_wd_login"]()
        b = ns["_admin_basis"]()
        check(b["excluded_ids"] == {HT2, VERW, MITGL}, "Übersicht Finn mit HT: Gruppe V raus, Server-Ausblendung bleibt")
    with app.test_request_context("/admin/overview", headers=h(VERW)):
        ns["_wd_login"]()
        b = ns["_admin_basis"]()
        check(b["excluded_ids"] == {HT1, HT2, NEU, SOLO} and b["excluded_names"] == [], "Übersicht Verwalter: nur seine Gruppe, keine fremden E-Mails")
        disp, excl = ns["_wd_personen"]()
        check(excl == {HT1, HT2, NEU, SOLO}, "WD/Live-Trades Verwalter: alle außer seiner Gruppe ausgeblendet")
    with app.test_request_context("/admin/overview", headers=h(MITGL)):
        ns["_wd_login"]()
        b = ns["_admin_basis"]()
        check(b["excluded_ids"] == set(ALLE) - {MITGL}, "Übersicht Mitglied: nur er selbst")

    # Schreib-Schutz wd-plaene
    r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": "ende", "plan_id": "plan-ht-0001"})
    check(r.status_code == 403, "wd-plaene PATCH: Verwalter auf HT-Plan → 403")
    r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": "ende", "plan_id": "plan-mitglied-1"})
    check(r.status_code == 404, "wd-plaene PATCH: Verwalter auf Plan seines Mitglieds → durch das Gate (hier 404 aus der Fake-DB)")
    r = c.patch("/admin/wd-plaene", headers=h(MITGL), json={"aktion": "ende", "plan_id": "plan-verwalter-1"})
    check(r.status_code == 403, "wd-plaene PATCH: Mitglied auf Plan des Verwalters → 403")
    r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": "tab_neu_laden", "user_id": MITGL, "pc": "pc-abc123"})
    check(r.status_code == 200 and log["insert"][-1][1]["user_id"] == MITGL, "tab_neu_laden: Verwalter für ID seiner Gruppe")
    r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": "tab_neu_laden", "user_id": HT1, "pc": "pc-abc123"})
    check(r.status_code == 403, "tab_neu_laden: Verwalter für HT-ID → 403")
    r = c.delete("/admin/wd-plaene", headers=h(VERW), json={"id": "plan-ht-0001"})
    check(r.status_code == 403, "wd-plaene DELETE: Verwalter auf HT-Plan → 403")
    r = c.delete("/admin/wd-plaene", headers=h(VERW), json={"id": "plan-mitglied-1"})
    letzte = log["anfrage"][-1]
    check(r.status_code == 200 and letzte[0] == "DELETE" and letzte[2]["user_id"] == "in.(" + ",".join(sorted(gr)) + ")",
          "wd-plaene DELETE: Plan der Gruppe, Guard user_id in (Gruppe) in derselben Anfrage")
    r = c.get("/admin/wd-plaene", headers=h(MITGL))
    check(r.status_code == 403, "wd-plaene GET: Mitglied ohne Admin → 403")
    r = c.post("/admin/wd-plaene", headers=h(VERW), json={"plaene": [{"master_account_id": "a-ht-0000000", "user_id": HT1}]})
    d = r.get_json()
    check(d["angelegt"] == [] and d["uebersprungen"][0]["grund"] == "ID nicht in deiner Gruppe", "wd-plaene POST: Verwalter für HT-ID → übersprungen")

    # prop-baum POST
    aid_ht, aid_m = "00000000-0000-0000-0000-0000000000a1", "00000000-0000-0000-0000-0000000000a2"
    orig = ns["sb_select"]

    def sb_select2(table, params):
        if table == "accounts" and params.get("id") in (f"eq.{aid_ht}", f"eq.{aid_m}"):
            return [{"id": params["id"][3:], "user_id": HT1 if params["id"].endswith("a1") else MITGL}]
        return orig(table, params)
    ns["sb_select"] = sb_select2
    r = c.post("/admin/prop-baum", headers=h(VERW), json={"account_id": aid_ht, "art": "done"})
    check(r.status_code == 403, "prop-baum: Verwalter hakt HT-Account ab → 403")
    r = c.post("/admin/prop-baum", headers=h(VERW), json={"account_id": aid_m, "art": "done"})
    check(r.status_code == 200, "prop-baum: Verwalter hakt Account seiner Gruppe ab → ok")
    r = c.post("/admin/prop-baum", headers=h(HT1), json={"account_id": aid_m, "art": "done"})
    check(r.status_code == 200, "prop-baum: Finn wie bisher überall")
    ns["sb_select"] = orig

    # /admin/auto-plan/ids: Planer-Haken sind HT-weit
    r = c.post("/admin/auto-plan/ids", headers=h(VERW), json={"user_id": MITGL, "drin": True})
    check(r.status_code == 403 and "HT-weit" in r.get_json()["msg"], "/ids POST: Verwalter darf auto_plan_regeln.user_ids nicht ändern")
    r = c.get("/admin/auto-plan/ids", headers=h(MITGL))
    check(r.status_code == 403, "/ids GET: Mitglied ohne Admin → 403")

    # 6) Tabellen fehlen (SQL nicht eingespielt) → keine Gruppen, nichts kippt
    fake_db(ns, tabellen_fehlen=True)
    d = c.get("/admin/pc-stand", headers=h(MITGL)).get_json()
    check(set(d["stand"]) == set(ALLE), "Tabellen fehlen: Mitglied ist (noch) unbeschränkt wie vor den Gruppen")
    d = c.get("/admin/pc-stand", headers=h(SOLO)).get_json()
    check(set(d["stand"]) == {SOLO}, "Tabellen fehlen: admin_zugang nur_eigene bleibt bei sich")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
