#!/usr/bin/env python3
"""Selbsttest UNT0 — neue ID ohne Unternehmen (Finn 05.11.2026 ~07:20: „Wenn wir eine neue ID kriegen … sage, wo sie hinkommt. Sag mir aber immer
Bescheid"). Rein rechnend mit den echten Funktionen aus app.py (admin_sicht_menge, admin_ohne_unternehmen, ohne_unternehmen_tick mit Stubs),
dazu Route, SQL-Datei und prophos.html als Text. Platzhalter-IDs, keine echten Konten. Aufruf: python3 tools/selftest_unt0_ohne_unternehmen.py"""
import os
import re
import sys
import time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-11-05_unt0_ohne_unternehmen.sql"), encoding="utf-8").read()
RB = open(os.path.join(W, "sql", "2026-11-05_unt0_ohne_unternehmen_rueckbau.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


ns = {"time": time, "re": re}
exec("\n".join(block(n) for n in ("admin_sicht_menge", "admin_ohne_unternehmen")), ns)
sicht, ohne = ns["admin_sicht_menge"], ns["admin_ohne_unternehmen"]

HT, EM = "g-ht", "g-em"
D = {"gruppen": [{"id": HT, "name": "Hermann Technologies", "verwalter_id": None}, {"id": EM, "name": "Emin", "verwalter_id": "emin"}],
     "mitglieder": [{"user_id": "finn", "gruppe_id": HT}, {"user_id": "mike", "gruppe_id": HT}, {"user_id": "emin", "gruppe_id": EM},
                    {"user_id": "amir", "gruppe_id": EM}]}

# ── Sicht: bestehende IDs bitgleich, neue ID nur sich
check(sicht("finn", False, D) == (None, False) and sicht("mike", False, D) == (None, False), "HT-Mitglieder: alles wie bisher (None)")
check(sicht("emin", False, D) == (frozenset({"emin", "amir"}), True), "Verwalter Emin: er + seine Gruppe, Verwalter")
check(sicht("amir", False, D) == (frozenset({"amir"}), False), "Mitglied einer Verwalter-Gruppe: nur sich (wie bisher)")
check(sicht("mike", True, D) == (frozenset({"mike"}), False), "admin_zugang.nur_eigene: nur sich (wie bisher)")
check(sicht("neu1", False, D) == (frozenset({"neu1"}), False), "NEU: ID ohne Zeile = ohne Unternehmen → nur sich, kein Admin")
check(sicht("neu1", False, {"gruppen": [], "mitglieder": []}) == (None, False) and sicht("neu1", False, None) == (None, False),
      "ohne Gruppen-Tabellen (nicht eingespielt) wie vor den Gruppen: None")
D2 = dict(D, gruppen=D["gruppen"] + [{"id": "g-x", "name": "X", "verwalter_id": "chefx"}])
check(sicht("chefx", False, D2) == (frozenset({"chefx"}), True), "Verwalter einer neuen Gruppe ohne Zeile: Verwalter, nicht „ohne Unternehmen“")

# ── Liste ohne Unternehmen
check(ohne(D, ["finn", "neu1", "emin", "amir", "neu2", "neu1", ""]) == ["neu1", "neu2"], "admin_ohne_unternehmen: nur IDs ohne Zeile und nicht Verwalter, einmal")
check(ohne(D2, ["chefx", "neu1"]) == ["neu1"] and ohne({"gruppen": []}, ["neu1"]) == [], "Verwalter zählt nicht, ohne Gruppen leer")

# ── Takt: 🟠 einmal je ID, Entprellung über alarm_log, Lesefehler meldet nichts
tns = {"time": time, "admin_ohne_unternehmen": ohne}
exec(SRC[SRC.index("UNT0_TAKT_S = 300"):SRC.index('@app.route("/admin/id-gruppe"')], tns)
gesendet = []


class R:
    status_code = 200

    def __init__(self, users):
        self._u = users

    def json(self):
        return {"users": self._u}


USERS = [{"id": "finn", "email": "f@x"}, {"id": "neu1", "email": "neu1@x", "user_metadata": {"name": "Neu Eins"}}, {"id": "neu2", "email": "neu2@x"}]
tns.update(admin_gruppen_daten=lambda: D, _auth_liste_anfrage=lambda: R(USERS), alarm_senden=lambda *a, **k: gesendet.append((a, k)),
           alarm_im_log=lambda keys, s: {"ohne_unternehmen|neu2"}, _alarm_empfaenger=lambda: {})
tns["ohne_unternehmen_tick"]()
check(not gesendet and not tns["_unt0"]["gemeldet"], "keine lesbaren Empfänger → nichts senden, nichts als gemeldet merken (Fremd-Review)")
tns["_unt0"]["at"] = 0.0
tns["_alarm_empfaenger"] = lambda: {"finnpascal": 3}
tns["ohne_unternehmen_tick"]()
check(len(gesendet) == 1 and gesendet[0][0][0] == 2 and gesendet[0][1]["schluessel"] == "ohne_unternehmen|neu1" and "Neu Eins · neu1@x" in gesendet[0][0][3]
      and gesendet[0][0][2] == "Neue ID ohne Unternehmen — bitte zuordnen", f"Takt: 🟠 (prio 2) einmal für neu1 mit Name · Mail, neu2 stand schon im alarm_log ({len(gesendet)})")
tns["_unt0"]["at"] = 0.0
tns["ohne_unternehmen_tick"]()
check(len(gesendet) == 1, "zweiter Takt: nichts doppelt (gemerkt)")
tns["_unt0"].update(at=0.0, gemeldet=set())
tns["alarm_im_log"] = lambda keys, s: None
tns["ohne_unternehmen_tick"]()
check(len(gesendet) == 1 and not tns["_unt0"]["gemeldet"], "alarm_log nicht lesbar → nichts senden, nächster Takt versucht es wieder")
tns.update(_unt0={"at": 0.0, "gemeldet": set(), "fehler": ""}, alarm_im_log=lambda keys, s: set(), admin_gruppen_daten=lambda: {"gruppen": [], "mitglieder": []})
tns["ohne_unternehmen_tick"]()
check(len(gesendet) == 1, "ohne Gruppen-Tabellen: keine Meldung")
check('ohne_unternehmen_tick()           # UNT0' in SRC[SRC.index("def ap_loop("):], "Takt hängt im ap_loop (eigener try neben alarm_tick)")

# ── Route Zuordnen: nur Admin ohne Einschränkung, nur ID ohne Zeile
rt = SRC[SRC.index('@app.route("/admin/id-gruppe"'):SRC.index("def _admin_verwalter_gruppen_ids(")]
check("ich, err = _wd_login()" in rt and "if not unt0_darf_zuordnen(ich, mail):" in rt and "if sicht is not None:" in rt and rt.count("403") >= 2,
      "Route: ADMIN_EMAILS oder admin_voll + keine eigene Einschränkung (Emin/Verwalter: 403)")
dns = {"ADMIN_EMAILS": {"finn@x"}}
exec(block("unt0_darf_zuordnen"), dns)
dns["admin_voll_uids"] = lambda: frozenset({"finnpascal"})
dz = dns["unt0_darf_zuordnen"]
check(dz("x", "FINN@x") and dz("finnpascal", "fp@x") and not dz("emin", "e@x") and not dz("", ""), "Recht: ADMIN_EMAILS (Groß/klein egal) oder admin_voll, sonst nein")
dns["admin_voll_uids"] = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
check(not dz("finnpascal", "fp@x") and dz("x", "finn@x"), "admin_voll nicht lesbar → nur ADMIN_EMAILS")
check('if uid not in admin_ohne_unternehmen(daten, [uid]):' in rt and "409" in rt and 'sb_insert("id_gruppe_mitglied"' in rt and "sb_update" not in rt,
      "Route: nur IDs ohne Zeile (409 sonst), nur insert — nie umhängen")
check(rt.count('_admin_gruppe_cache.update(bis=0.0)') == 2, "Route: Gruppen-Stand frisch vor und nach dem Schreiben")
ov = SRC[SRC.index("def admin_ohne_unternehmen_zeilen("):SRC.index("def _wd_login_ich(")]
check("if not unt0_darf_zuordnen(uid_aufrufer, mail_aufrufer):" in ov and "return []" in ov, "Liste mit Name/Mail nur für Admins (unt0_darf_zuordnen)")

# ── SQL + Rückbau
check("drop trigger if exists id_gruppe_neu_ht on auth.users;" in SQL and "insert into public.id_gruppe_mitglied" not in SQL.split("begin;")[1],
      "SQL: Trigger „neue ID → HT“ weg, kein Insert")
check("auth.uid() is not null" in SQL and "not exists (select 1 from public.id_gruppe_mitglied m where m.user_id = auth.uid())" in SQL
      and "exists (select 1 from public.id_gruppen)" in SQL, "SQL: admin_nur_eigene + ohne Unternehmen, nur eingeloggt, nur wenn es Unternehmen gibt")
check("raise exception 'UNT0:" in SQL and SQL.strip().count("begin;") == 1 and "commit;" in SQL, "SQL: Prüfung bestehender IDs ohne Zeile rollt alles zurück")
check("CREATE TRIGGER id_gruppe_neu_ht AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.id_gruppe_neu_ht();" in RB
      and "Hermann Technologies (ohne Zeile)" in RB and "auth.uid() is not null" not in RB, "Rückbau: Trigger + alte admin_nur_eigene + alte View")

# ── Frontend
check('id="adm-ohne-unt"' in HTML and "function admOhneUntRender()" in HTML and "`${WATCHER_HOME}/admin/id-gruppe`" in HTML
      and "try{ admOhneUntRender() }catch(_){}   // UNT0" in HTML and "!admEingeschraenkt() && admData && Array.isArray(admData.ohne_unternehmen)" in HTML,
      "Frontend: Zeile „Ohne Unternehmen“ mit Auswahl + Zuordnen, nur ohne Einschränkung")
# UNT0-Fix (S5): keine zweite /auth/v1/user-Anfrage je Übersicht — _wd_login merkt Login-ID + Mail im g, _wd_login_ich liest sie zuerst
wl = SRC[SRC.index("def _wd_login():"):SRC.index("def _wd_personen(")]
wi = SRC[SRC.index("def _wd_login_ich("):SRC.index("# MELDUNG „NEUE ID OHNE UNTERNEHMEN")]
check('g.login_uid, g.login_mail = str(u["id"]), str(u.get("email") or "").strip().lower()' in wl
      and wi.index('if getattr(g, "login_uid", None):') < wi.index("_auth_user_anfrage("), "Login-Mail aus _wd_login (g), Rückfall nur ohne g")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
