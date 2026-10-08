#!/usr/bin/env python3
"""Selbsttest ADMIN-GRUPPEN (app.py, 08.10.2026, Finn: „Emin bekommt das volle Admin wie Finn, aber nur mit den IDs seiner Gruppe";
Nachtrag 23:00: Tabellen id_gruppen + id_gruppe_mitglied, sql/2026-10-08_admin_gruppen.sql). Ohne Netz: die echten Funktionen laufen
gegen eine Fake-DB (sb_select/_sb_anfrage/_auth_* gestubbt), die Routen über einen Flask-Testclient.
Geprüft: Mengen-Logik (HT alle · Verwalter = Gruppe · Mitglied ohne Zugang = kein Admin), Finns ?gruppe=-Filter, Gruppen-Liste für die
Chips, _admin_basis-Ausblendung, Trade-Planer-Sicht (ap_*), pc-stand-Filter, Schreib-Schutz fremder Objekte (wd-plaene PATCH/DELETE/POST,
prop-baum, /ids POST, konto_balance_darf). Nachbesserungen Master 08.10.2026: (A) Gruppe nur mit ?ansicht=admin — der PC-Tab des
Verwalters (ohne Marker) sieht/ändert nur die eigene ID, dazu Quelltext-Proben der PC-Wege in prophos.html; (B) Trade-Planer-Summen
nur über die Sicht (ap_stand_sicht, ap_lauf_ohne_summen); (C) Finns Chip einer Verwalter-Gruppe zeigt auch den ausgeblendeten Verwalter.
Platzhalter-IDs, keine echten Namen. Aufruf: python3 tools/selftest_admin_gruppen.py"""
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
    def __init__(self, status, daten, text=""):
        self.status_code, self._d, self.text = status, daten, text

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
             "admin_gruppe_ist_ht", "admin_gruppen_tabelle_fehlt", "_admin_ansicht", "_admin_filter_ist_ht", "_admin_filter_aus_anfrage", "_admin_nur_uid", "_admin_sicht", "_admin_eingeschraenkt",
             "_admin_darf_uid", "_admin_verwalter", "_wd_login", "_wd_personen", "_admin_basis",
             "ap_sicht", "ap_sicht_uid", "ap_eingriff_sicht", "ap_eingriff_admin_reiter", "ap_admin_reiter_ok", "ap_eingriff_filter",
             "_ap_gruppe_lesen", "_ap_sicht_param", "konto_balance_darf", "ap_stand_sicht", "ap_lauf_ohne_summen",
             "admin_pc_stand", "admin_prop_baum", "admin_wd_plaene", "admin_auto_plan_ids"]
    teile = [konst(k) for k in ("AP_SICHT_ADMIN", "AP_EINGRIFF_MAX", "AUTH_LISTE_CACHE_S", "ADMIN_GRUPPE_HT", "AP_NUR_PLANER_TXT",
                                "ADMIN_ANSICHT", "AP_LAUF_SUMMEN", "ADMIN_RUECKFALL_S")]
    teile += ["_admin_zugang_cache = {}", '_admin_gruppe_cache = {"bis": 0.0, "daten": None, "letzte": None}']
    teile += [block(n) for n in namen]
    ns = {"re": re, "time": time, "threading": threading, "requests": requests, "request": request, "jsonify": jsonify, "g": g,
          "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "_kurz_cache_lock": threading.Lock(),
          "SUPABASE_SERVICE_KEY": "svc", "SUPABASE_URL": "https://beispiel.invalid", "ADMIN_EMAILS": {"admin@beispiel.invalid"},
          "ADMIN_EXCLUDE_EMAILS": {"aus@beispiel.invalid", "verw-aus@beispiel.invalid"}, "AP_TYPEN": ("challenge", "phase1", "phase2")}
    exec("\n".join(teile), ns)
    return ns


def fake_db(ns, tabellen_fehlen=False):
    log = {"select": [], "anfrage": [], "insert": []}
    plaene = {"plan-ht-0001": HT1, "plan-mitglied-1": MITGL, "plan-verwalter-1": VERW}
    konten = {"a-ht": HT1, "a-mitgl": MITGL}

    def sb_select(table, params):
        log["select"].append((table, dict(params)))
        if table in ("id_gruppen", "id_gruppe_mitglied") and tabellen_fehlen:
            if tabellen_fehlen == "kaputt":     # K1: anderer Fehler (DB-Schluckauf)
                raise requests.exceptions.HTTPError(response=Antwort(503, {}, '{"code":"PGRST003","message":"timeout"}'))
            raise requests.exceptions.HTTPError(response=Antwort(404, {}, '{"code":"PGRST205","message":"Could not find the table"}'))
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
        mails = {HT2: "aus@beispiel.invalid", VERW: "verw-aus@beispiel.invalid"}   # der Verwalter ist für HT ausgeblendet (wie heute)
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
    ns["_admin_gruppe_cache"].update(bis=0.0, daten=None)   # letzte bleibt (K1: Rückfall auf den zuletzt bekannten Stand)
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

    # 5) Routen über Flask (Fake-DB). Admin-Ansicht = ?ansicht=admin (nur die Admin-Reiter schicken es); ohne Marker ist ein Verwalter
    # wie bis .1380 auf die eigene ID beschränkt — das ist der Weg seines PC-Tabs (Nachbesserung A, Master 08.10.2026)
    log = fake_db(ns)
    app = Flask("selftest_admin_gruppen")
    app.add_url_rule("/admin/pc-stand", "pc", ns["admin_pc_stand"], methods=["GET", "OPTIONS"])
    app.add_url_rule("/admin/prop-baum", "pb", ns["admin_prop_baum"], methods=["GET", "POST", "OPTIONS"])
    app.add_url_rule("/admin/wd-plaene", "wd", ns["admin_wd_plaene"], methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"])
    app.add_url_rule("/admin/auto-plan/ids", "ids", ns["admin_auto_plan_ids"], methods=["GET", "POST", "OPTIONS"])
    ns["_admin_auth"] = lambda: (None, (jsonify({"error": "Nur für Admins"}), 403))
    c = app.test_client()
    h = lambda uid: {"sb-token": uid}
    AA = "ansicht=admin"

    d = c.get("/admin/pc-stand", headers=h(HT1)).get_json()
    check(set(d["stand"]) == set(ALLE), "pc-stand: Finn (HT) sieht alle IDs")
    d = c.get(f"/admin/pc-stand?{AA}", headers=h(VERW)).get_json()
    check(set(d["stand"]) == {VERW, MITGL}, "pc-stand: Verwalter in der Admin-Ansicht = seine Gruppe")
    d = c.get("/admin/pc-stand", headers=h(VERW)).get_json()
    check(set(d["stand"]) == {VERW}, "A: pc-stand ohne Admin-Ansicht (PC-Tab des Verwalters) = nur eigene ID")
    d = c.get(f"/admin/pc-stand?{AA}", headers=h(MITGL)).get_json()
    check(set(d["stand"]) == {MITGL}, "pc-stand: Mitglied auch mit Marker nur sich")
    d = c.get(f"/admin/pc-stand?gruppe={G_V}", headers=h(HT1)).get_json()
    check(set(d["stand"]) == {VERW, MITGL}, "pc-stand: Finn mit ?gruppe=<Gruppe V>")
    d = c.get("/admin/pc-stand?gruppe=ht", headers=h(HT1)).get_json()
    check(set(d["stand"]) == {HT1, HT2, NEU, SOLO}, "pc-stand: Finn mit ?gruppe=ht (neue ID ohne Zeile inklusive)")
    d = c.get(f"/admin/pc-stand?{AA}&gruppe={G_HT}", headers=h(VERW)).get_json()
    check(set(d["stand"]) == {VERW, MITGL}, "pc-stand: Verwalter kann ?gruppe= nicht ausweiten")

    # _admin_basis / _wd_personen: Ausblendung. Der Verwalter steht in der Server-Ausblendung (ADMIN_EXCLUDE) wie heute.
    def basis(pfad, uid):
        with app.test_request_context(pfad, headers=h(uid)):
            ns["_wd_login"]()
            return ns["_admin_basis"](), ns["_wd_personen"]()[1]
    b, ex = basis("/admin/overview", HT1)
    check(b["excluded_ids"] == {HT2, VERW} and sorted(b["excluded_names"]) == ["aus@beispiel.invalid", "verw-aus@beispiel.invalid"],
          "Übersicht Finn „Alle“: Server-Ausblendung wie heute")
    b, ex = basis(f"/admin/overview?gruppe={G_V}", HT1)
    check(b["excluded_ids"] == {HT1, HT2, NEU, SOLO} and b["excluded_names"] == ["aus@beispiel.invalid"] and ex == {HT1, HT2, NEU, SOLO},
          "C: Finns Chip „Gruppe V“ zeigt Verwalter UND Mitglied, obwohl der Verwalter ausgeblendet ist")
    b, ex = basis("/admin/overview?gruppe=ht", HT1)
    check(b["excluded_ids"] == {HT2, VERW, MITGL} and ex == {HT2, VERW, MITGL}, "C: Chip HT — Gruppe V raus, Server-Ausblendung bleibt")
    b, ex = basis(f"/admin/overview?gruppe={G_HT}", HT1)
    check(b["excluded_ids"] == {HT2, VERW, MITGL}, "C: Chip HT über die Gruppen-ID wie 'ht'")
    b, ex = basis(f"/admin/overview?{AA}", VERW)
    check(b["excluded_ids"] == {HT1, HT2, NEU, SOLO} and b["excluded_names"] == [] and ex == {HT1, HT2, NEU, SOLO},
          "Übersicht/WD Verwalter (Admin-Ansicht): nur seine Gruppe, keine fremden E-Mails")
    b, ex = basis("/admin/live-trades", VERW)
    check(b["excluded_ids"] == set(ALLE) - {VERW} and ex == set(ALLE) - {VERW}, "A: ohne Admin-Ansicht (PC-Tab) nur die eigene ID")
    b, ex = basis(f"/admin/overview?{AA}", MITGL)
    check(b["excluded_ids"] == set(ALLE) - {MITGL}, "Übersicht Mitglied: nur er selbst")

    # Schreib-Schutz wd-plaene — mit Admin-Ansicht (Reiter „Winning Days")
    W = f"/admin/wd-plaene?{AA}"
    r = c.patch(W, headers=h(VERW), json={"aktion": "ende", "plan_id": "plan-ht-0001"})
    check(r.status_code == 403, "wd-plaene PATCH: Verwalter auf HT-Plan → 403")
    r = c.patch(W, headers=h(VERW), json={"aktion": "ende", "plan_id": "plan-mitglied-1"})
    check(r.status_code == 404, "wd-plaene PATCH: Verwalter (Admin-Ansicht) auf Plan seines Mitglieds → durch das Gate (404 aus der Fake-DB)")
    r = c.patch(W, headers=h(MITGL), json={"aktion": "ende", "plan_id": "plan-verwalter-1"})
    check(r.status_code == 403, "wd-plaene PATCH: Mitglied auf Plan des Verwalters → 403")
    r = c.patch(W, headers=h(VERW), json={"aktion": "tab_neu_laden", "user_id": MITGL, "pc": "pc-abc123"})
    check(r.status_code == 200 and log["insert"][-1][1]["user_id"] == MITGL, "tab_neu_laden: Verwalter (Admin-Ansicht) für ID seiner Gruppe")
    r = c.patch(W, headers=h(VERW), json={"aktion": "tab_neu_laden", "user_id": HT1, "pc": "pc-abc123"})
    check(r.status_code == 403, "tab_neu_laden: Verwalter für HT-ID → 403")
    r = c.delete(W, headers=h(VERW), json={"id": "plan-ht-0001"})
    check(r.status_code == 403, "wd-plaene DELETE: Verwalter auf HT-Plan → 403")
    r = c.delete(W, headers=h(VERW), json={"id": "plan-mitglied-1"})
    letzte = log["anfrage"][-1]
    check(r.status_code == 200 and letzte[0] == "DELETE" and letzte[2]["user_id"] == "in.(" + ",".join(sorted(gr)) + ")",
          "wd-plaene DELETE: Plan der Gruppe, Guard user_id in (Gruppe) in derselben Anfrage")
    r = c.get(W, headers=h(MITGL))
    check(r.status_code == 403, "wd-plaene GET: Mitglied ohne Admin → 403")
    r = c.post(W, headers=h(VERW), json={"plaene": [{"master_account_id": "a-ht-0000000", "user_id": HT1}]})
    d = r.get_json()
    check(d["angelegt"] == [] and d["uebersprungen"][0]["grund"] == "ID nicht in deiner Gruppe", "wd-plaene POST: Verwalter für HT-ID → übersprungen")

    # A: dieselben Wege OHNE Admin-Ansicht = PC-Tab des Verwalters → nie ein Objekt des Mitglieds
    anz = len(log["anfrage"])
    r = c.get("/admin/wd-plaene?tag=2026-10-09", headers=h(VERW))
    check(r.status_code == 403, "A: wd-plaene GET des PC-Tabs (ohne Marker) → 403 wie bis .1380 — keine Pläne des Mitglieds in der Antwort")
    r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": "ende", "plan_id": "plan-mitglied-1"})
    check(r.status_code == 403, "A: PC-Tab beendet keinen Plan des Mitglieds (PATCH ende → 403)")
    for akt in ("endlesung", "ansehen", "erledigt", "manuell"):
        r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": akt, "plan_id": "plan-mitglied-1", "master_pl": 1})
        check(r.status_code == 403, f"A: PC-Tab — PATCH {akt} auf Plan des Mitglieds → 403")
    r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": "ende", "plan_id": "plan-verwalter-1"})
    check(r.status_code == 404, "A: PC-Tab — eigener Plan geht wie bisher durchs Gate (404 aus der Fake-DB)")
    r = c.patch("/admin/wd-plaene", headers=h(VERW), json={"aktion": "tab_neu_laden", "user_id": MITGL, "pc": "pc-abc123"})
    check(r.status_code == 403, "A: PC-Tab — tab_neu_laden für das Mitglied → 403")
    r = c.delete("/admin/wd-plaene", headers=h(VERW), json={"id": "plan-mitglied-1"})
    check(r.status_code == 403 and len(log["anfrage"]) == anz, "A: PC-Tab löscht keinen Plan des Mitglieds (kein DELETE abgeschickt)")
    r = c.post("/admin/wd-plaene", headers=h(VERW), json={"plaene": [{"master_account_id": "a-mitg-000000", "user_id": MITGL}]})
    check(r.status_code == 403, "A: PC-Tab legt keine Pläne fürs Mitglied an (POST → 403)")

    # prop-baum POST
    aid_ht, aid_m = "00000000-0000-0000-0000-0000000000a1", "00000000-0000-0000-0000-0000000000a2"
    orig = ns["sb_select"]

    def sb_select2(table, params):
        if table == "accounts" and params.get("id") in (f"eq.{aid_ht}", f"eq.{aid_m}"):
            return [{"id": params["id"][3:], "user_id": HT1 if params["id"].endswith("a1") else MITGL}]
        return orig(table, params)
    ns["sb_select"] = sb_select2
    r = c.post(f"/admin/prop-baum?{AA}", headers=h(VERW), json={"account_id": aid_ht, "art": "done"})
    check(r.status_code == 403, "prop-baum: Verwalter hakt HT-Account ab → 403")
    r = c.post(f"/admin/prop-baum?{AA}", headers=h(VERW), json={"account_id": aid_m, "art": "done"})
    check(r.status_code == 200, "prop-baum: Verwalter (Admin-Ansicht) hakt Account seiner Gruppe ab → ok")
    r = c.post("/admin/prop-baum", headers=h(VERW), json={"account_id": aid_m, "art": "done"})
    check(r.status_code == 403, "A: prop-baum ohne Admin-Ansicht → nur eigene Accounts")
    r = c.post("/admin/prop-baum", headers=h(HT1), json={"account_id": aid_m, "art": "done"})
    check(r.status_code == 200, "prop-baum: Finn wie bisher überall")
    ns["sb_select"] = orig

    # /admin/auto-plan/ids: Planer-Haken sind HT-weit; Lesen nur aus der Admin-Ansicht
    r = c.post(f"/admin/auto-plan/ids?{AA}", headers=h(VERW), json={"user_id": MITGL, "drin": True})
    check(r.status_code == 403 and "HT-weit" in r.get_json()["msg"], "/ids POST: Verwalter darf auto_plan_regeln.user_ids nicht ändern")
    r = c.get("/admin/auto-plan/ids", headers=h(VERW))
    check(r.status_code == 403, "A: /ids GET ohne Admin-Ansicht → 403 (wie bis .1380)")
    r = c.get(f"/admin/auto-plan/ids?{AA}", headers=h(MITGL))
    check(r.status_code == 403, "/ids GET: Mitglied ohne Admin → 403")

    # B: Summen im Trade-Planer nur über die Sicht
    stand = {"offen": [{"user_id": HT1, "delta_eur_pkt": 10.0, "einsatz_eur": 500.0}, {"user_id": MITGL, "delta_eur_pkt": -4.0, "einsatz_eur": -200.0},
                       {"user_id": VERW, "delta_eur_pkt": 1.0, "einsatz_eur": 50.0}],
             "geplant": [{"user_id": HT2}, {"user_id": VERW}], "folgetag": [{"user_id": HT1}], "hinweise": [{"grund": "global"}, {"user_id": MITGL}],
             "heute_beendet": [{"user_id": HT1}, {"user_id": MITGL}], "fremd": [{"user_id": HT2}],
             "basis_netto": 7.0, "basis_brutto": 15.0, "basis_einsatz": 350.0, "brutto_einsatz": 750.0, "zeiten": {}}
    sg = ns["ap_stand_sicht"](stand, gr)
    check(sg["basis_netto"] == -3.0 and sg["basis_brutto"] == 5.0 and sg["basis_einsatz"] == -150.0 and sg["brutto_einsatz"] == 250.0,
          "B: Basis Netto/Brutto (€/Pkt und € Einsatz) nur aus der Gruppe neu gerechnet")
    check([z["user_id"] for z in sg["geplant"]] == [VERW] and sg["folgetag"] == [] and sg["hinweise"] == [{"user_id": MITGL}]
          and len(sg["heute_beendet"]) == 1 and sg["fremd"] == [] and stand["basis_netto"] == 7.0,
          "B: Listen (geplant/folgetag/hinweise/heute beendet/fremd) nur Gruppe, Original unverändert")
    check(ns["ap_stand_sicht"](stand, MITGL)["basis_einsatz"] == -200.0, "B: eine ID (Mitglied) → nur ihre Summe")
    lo = ns["ap_lauf_ohne_summen"]({"geplant": [1], "ausgelassen": [], "netto_max_abs": 99, "id_misch": {"x": 1}, "firma_misch": {}, "misch_fenster": [],
                                     "einsatz": {"laufzeit_min": 180, "basis": 5000}, "ausgleich": {"offen": [], "hinweise": [], "long_eur": 1}})
    check("netto_max_abs" not in lo and "id_misch" not in lo and lo["einsatz"] == {"laufzeit_min": 180} and "long_eur" not in lo["ausgleich"]
          and lo["geplant"] == [1], "B: Lauf-Antwort für Eingeschränkte ohne HT-Summen, Listen + laufzeit_min bleiben")

    # A: Quelltext der PC-Wege (prophos.html) — Ausführung nur aus eigenen Daten
    html = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
    i = html.index("async function loadTradePlansFromSupabase(")
    check(".eq('user_id', currentUserId)" in html[i:i + 600], "A: tradePlans (Start/Hedge/Endlesung/sfTick) nur eigene ID (RLS + eq user_id)")
    i = html.index("async function tpStartUmTick(")
    check("_tp = tradePlans" in html[i:i + 1200] and "/admin/" not in html[i:i + 1200], "A: tpStartUmTick startet nur aus tradePlans, nie aus Admin-Antworten")
    check("/admin/live-trades?tage=1&nur_eigene=1&status=open" in html, "A: Endlesung des PC-Tabs fragt live-trades nur_eigene=1 (Server eq.me)")
    check(html.count("ansicht=admin") >= 8 and "wdSichtbar() ? '&ansicht=admin'" in html and "(wdSichtbar() ? ((query ? '&' : '?') + 'ansicht=admin')" in html,
          "A: Admin-Ansicht nur aus Admin-Reitern (Farmer nur bei sichtbarem Reiter)")
    i = html.index("async function wdWuerfelnSchreiben(")
    check("window._admNurGruppe()) ? {}" in html[i:i + 900], "A: Würfel-Automatik nimmt keine Richtungen aus der Verwalter-Ansicht")
    i = html.index("async function wdNeuLaden(")
    check("!nurGruppe && d && d.rail" in html[i:i + 2200] and "String(x.user_id) === ich" in html[i:i + 2600],
          "A: Farmer-Reiter eines Verwalters räumt/heilt nur die eigene Zeile")
    # 6) Tabellen fehlen (SQL nicht eingespielt) → keine Gruppen, nichts kippt
    fake_db(ns, tabellen_fehlen=True)
    d = c.get("/admin/pc-stand", headers=h(MITGL)).get_json()
    check(set(d["stand"]) == set(ALLE), "Tabellen fehlen: Mitglied ist (noch) unbeschränkt wie vor den Gruppen")
    d = c.get("/admin/pc-stand", headers=h(SOLO)).get_json()
    check(set(d["stand"]) == {SOLO}, "Tabellen fehlen: admin_zugang nur_eigene bleibt bei sich")

    # K1: andere Lesefehler → zuletzt bekannter Stand; nie bekannt → Fehler (502), nie still unbeschränkt
    ns["_admin_gruppe_cache"].update(letzte=None)
    fake_db(ns)
    ns["admin_gruppen_daten"]()                                   # Stand bekannt
    fake_db(ns, tabellen_fehlen="kaputt")
    d = c.get("/admin/pc-stand", headers=h(MITGL)).get_json()
    check(set(d["stand"]) == {MITGL}, "K1: DB-Fehler beim Lesen der Gruppen → letzter Stand, Mitglied bleibt beschränkt")
    ns["_admin_gruppe_cache"].update(letzte=None)
    fake_db(ns, tabellen_fehlen="kaputt")
    r = c.get("/admin/pc-stand", headers=h(MITGL))
    check(r.status_code == 502, "K1: nie ein Stand + Lesefehler → Anfrage scheitert (502), nicht unbeschränkt")
    tf = ns["admin_gruppen_tabelle_fehlt"]
    err = lambda st, txt: requests.exceptions.HTTPError(response=Antwort(st, {}, txt))
    check(tf(err(404, '{"code":"PGRST205"}')) and tf(err(404, 'relation "x" does not exist 42P01')) and not tf(err(404, '{"code":"PGRST116"}'))
          and not tf(err(503, "PGRST205 maybe")), "K1: nur PGRST205/42P01 zählt als „Tabelle fehlt“")

    # K1-Nachtrag (09.10.2026): Rückzug — im Rückfall ADMIN_RUECKFALL_S lang keine neuen Abfragen
    fake_db(ns)
    ns["_admin_gruppe_cache"].update(bis=0.0, daten=None, letzte=None)
    ns["admin_gruppen_daten"]()
    log = fake_db(ns, tabellen_fehlen="kaputt")
    ns["admin_gruppen_daten"]()
    n1 = sum(1 for tb, _p in log["select"] if tb in ("id_gruppen", "id_gruppe_mitglied"))
    for _ in range(5):
        ns["admin_gruppen_daten"]()
    n2 = sum(1 for tb, _p in log["select"] if tb in ("id_gruppen", "id_gruppe_mitglied"))
    bis = ns["_admin_gruppe_cache"]["bis"] - time.time()
    check(n1 == 1 and n2 == 1 and 0 < bis <= ns["ADMIN_RUECKFALL_S"] + 0.5,
          f"K1: nach dem Rückfall {ns['ADMIN_RUECKFALL_S']} s keine neuen Abfragen (1 Versuch, dann {n2 - n1} weitere; bis +{bis:.1f} s)")
    ns["_admin_gruppe_cache"]["bis"] = 0.0
    ns["admin_gruppen_daten"]()
    n3 = sum(1 for tb, _p in log["select"] if tb in ("id_gruppen", "id_gruppe_mitglied"))
    check(n3 == 2, "K1: nach Ablauf des Rückzugs wird wieder gefragt")

    # K2 (09.10.2026): admin_zugang — Lesefehler → letzter Stand je Nutzer (auch abgelaufen), ADMIN_RUECKFALL_S lang; nie ein Stand → Fehler
    fake_db(ns)
    zf = {"n": 0}

    def zugang_kaputt(table, params):
        zf["n"] += 1
        raise requests.exceptions.HTTPError(response=Antwort(503, {}, '{"code":"PGRST003"}'))
    ns["_admin_zugang_cache"].clear()
    ns["_admin_zugang_cache"][SOLO] = (0.0, True)                # abgelaufener, aber bekannter Stand
    ns["sb_select"] = zugang_kaputt
    erg1 = ns["admin_zugang_nur_eigene"](SOLO)
    erg2 = ns["admin_zugang_nur_eigene"](SOLO)
    bis = ns["_admin_zugang_cache"][SOLO][0] - time.time()
    check(erg1 is True and erg2 is True and zf["n"] == 1 and 0 < bis <= ns["ADMIN_RUECKFALL_S"] + 0.5,
          f"K2: admin_zugang nicht lesbar → letzter Stand (nur_eigene bleibt), {ns['ADMIN_RUECKFALL_S']} s ohne neue Abfrage ({zf['n']} Versuch)")
    ns["_admin_zugang_cache"].clear()
    try:
        ns["admin_zugang_nur_eigene"](SOLO)
        check(False, "K2: nie ein Stand + Lesefehler muss werfen (502)")
    except requests.exceptions.HTTPError:
        check(True, "K2: nie ein Stand + Lesefehler → Fehler wie bisher (Aufrufer 502)")
    fake_db(ns)

    # K3–K5 (09.10.2026): Quelltext-Proben prophos.html
    html0 = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
    i = html0.index("async function wdSpeichern(")
    blk = html0[i:i + 6000]
    j = blk.index("for(const [uid, e] of _wd.umsortiert){")
    check("if(!(await wdDarf(uid))) continue" in blk[j:j + 300], "K3: wdSpeichern — Riegel wdDarf auch in der Schleife über umsortierte Blöcke")
    i = html0.index("async function wdZeilenHeilen(")
    check("if(!(await wdDarf(x.user_id))) continue" in html0[i:i + 700], "K3: wdZeilenHeilen — Riegel wdDarf je Zeile")
    i = html0.index("async function eigenerCodeLaden(")
    blk = html0[i:i + 900]
    check("if(!gelesen){ eigenerCodeUnklar = true; return null }" in blk and blk.index("if(!gelesen)") < blk.index("eigenerCodeUid = uid; eigenerCode = c"),
          "K4: eigenerCodeLaden merkt bei Lesefehler nichts (nächstes Mal neu fragen)")
    check("return eigenerCodeUnklar || admEingeschraenkt() || !!eigenerCode" in html0 and "catch(_){ return true } return eigenerCodeUnklar" in html0,
          "K4: _admNurGruppeLaden — nicht prüfbar → eingeschränkt")
    check(html0.count("wdVerwalter()") >= 8 and "const wdVerwalter = () => !!document.querySelector('#dashboard-view section.view[data-view=\"kasse\"].adm-verwalter')" in html0,
          f"K5: Hinweistexte im WD-Reiter fragen wdVerwalter() ({html0.count('wdVerwalter()')} Stellen) — gleiche Bedingung wie das Ausblenden")

    # S1: verfallen im Lauf nur für die Sicht
    erg = {"geplant": [], "verfallen": [{"user_id": HT1, "plan_id": "a"}, {"user_id": MITGL, "plan_id": "b"}]}
    check([x["plan_id"] for x in ns["ap_sicht"](erg, gr)["verfallen"]] == ["b"], "S1: Lauf-Antwort — verfallen nur der eigenen Sicht")

    # S6 / M1: Quelltext-Proben
    src = open(APP, encoding="utf-8").read()
    i = src.index("\ndef admin_build_auftrag(")
    blk = src[i:src.find("\n\n\n", i)]
    check("if not _admin_nur_uid():" in blk and blk.index("if not _admin_nur_uid():") < blk.index('"auftrag_plan"'),
          "S6: auftrag_plan (Soll/Ziel/ID-Namen) nur ohne Einschränkung")
    html = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
    def fn(name, n=4000):
        j = html.index(name); return html[j:j + n]
    check("konten = await wdNurErlaubte(konten)" in fn("async function wdDatenLaden(", 3600), "M1: wdDatenLaden nimmt für Eingeschränkte nur Konten der Sicht (keine „archiviert“-Markierung fremder)")
    check("await wdNurErlaubte(await wdRowsLaden(tag))" in fn("async function wdPlaeneAnlegen(", 700) and
          "await wdNurErlaubte(await wdRowsLaden(tag))" in fn("async function wdPlaeneNachziehen(", 400), "M1: Pläne anlegen/nachziehen nur Zeilen der Gruppe")
    check("if(!(await wdDarf(row && row.user_id))) return" in fn("async function wdZeileSchreiben(", 300), "M1: wdZeileSchreiben — Riegel gegen fremde Zeilen")
    for name in ("async function wdSlotEinplanen(", "async function wdKontoHaken(", "async function wdKontoHakenOhneZeile(", "async function wdKontoHeute(",
                 "async function wdRichtungUmschalten(", "async function mklWdPlanSpeichern(", "async function mklWdPlanTauschen(", "async function mklWdPlanNeuAnlegen("):
        check("await wdDarf(" in fn(name, 900), f"M1: {name[15:-1]} prüft wdDarf vor dem Schreiben")
    check("await wdNurErlaubte(offen, true)" in fn("async function wdWuerfelnSchreiben(", 1600), "M1: Würfel-Automatik schreibt eingeschränkt nur die eigene Zeile")
    # jede Schreibstelle in wd_farmer_regeln bzw. jeder Aufruf von wd_konto_setzen hat in SEINER Funktion/seinem Handler vorher einen Riegel
    import re as _re

    def umgebung(k):   # vom letzten Funktions- bzw. Handler-Anfang bis zur Stelle
        return html[max(html.rfind("function ", 0, k), html.rfind("addEventListener(", 0, k)):k]
    stellen = [m.start() for m in _re.finditer(r"supabase\.from\('wd_farmer_regeln'\)\.update", html)]
    check(len(stellen) == 5 and all(("wdNurGruppe()" in umgebung(k) or "_admNurGruppeLaden()" in umgebung(k)) for k in stellen),
          f"M1: alle {len(stellen)} Schreibstellen in wd_farmer_regeln für Eingeschränkte gesperrt")
    rpc = [m.start() for m in _re.finditer(r"supabase\.rpc\('wd_konto_setzen'", html)]
    check(len(rpc) == 4 and all(("wdDarf(" in umgebung(k) or "wdNurGruppe()" in umgebung(k)) for k in rpc),
          f"M1: alle {len(rpc)} Aufrufe von wd_konto_setzen hinter wdDarf/wdNurGruppe")
    i = html.index("async function admKapSpeichern(")
    check("if(admEingeschraenkt() || eigenerCode)" in html[i:i + 900], "M1: kapitel (HT-weit) schreibt ein eingeschränkter Login nie")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
