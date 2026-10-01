#!/usr/bin/env python3
"""Selbsttest Supabase-Diät B (app.py, 01.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_sb_diaet.py
Lädt die Kurz-Caches und watcher_leerlauf per Quelltext aus app.py (app.py zieht beim Import Flask und startet Threads).
Prüft: Login-Cache nur bei 200 mit id, je Token getrennt, nie über exp hinaus, nach Ablauf neu gefragt; 401 und Netzfehler
werden nie gemerkt; Nutzerliste/admin_zugang/duplikum_credentials 60 s gemerkt, Fehler nie; Leerlauf-Regel des Wächters."""
import base64
import hashlib
import json
import os
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

ok_n, fehl_n = 0, 0


def pruef(bed, text):
    global ok_n, fehl_n
    if bed:
        ok_n += 1
    else:
        fehl_n += 1
        print("  ✗", text)


class Antwort:
    def __init__(self, status, daten):
        self.status_code = status
        self._d = daten

    def json(self):
        return self._d


class Uhr:
    t = 1_000_000.0

    def time(self):
        return self.t


def jwt(exp):
    teil = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"kopf.{teil}.sig"


def lade():
    src = open(APP, encoding="utf-8").read()
    a = src.index("AUTH_USER_CACHE_S = 45")
    e = src.index("\n\n\n", src.index("def dup_creds_lesen("))
    i = src.index("def watcher_leerlauf(")
    leer = src[i:src.find("\n\n\n", i)]
    uhr = Uhr()
    zaehler = {"user": 0, "liste": 0, "select": 0}
    antworten = {"user": [], "liste": [], "select": []}

    def _sb_anfrage(methode, url, **kw):
        art = "liste" if "admin/users" in url else "user"
        zaehler[art] += 1
        r = antworten[art].pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def sb_select(table, params):
        zaehler["select"] += 1
        r = antworten["select"].pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    ns = {"threading": threading, "time": uhr, "json": json, "base64": base64, "hashlib": hashlib,
          "SUPABASE_URL": "https://beispiel.invalid", "SUPABASE_ANON_KEY": "anon", "_sb_headers": lambda p=None: {},
          "_sb_anfrage": _sb_anfrage, "sb_select": sb_select}
    exec(src[a:e] + "\n\n" + leer, ns)
    return ns, uhr, zaehler, antworten


def main():
    ns, uhr, z, ant = lade()
    t0 = uhr.t

    # Login: 200 → gemerkt, zweiter Aufruf ohne Anfrage
    tok_a = jwt(t0 + 3600)
    ant["user"] += [Antwort(200, {"id": "u1", "email": "a@x"})]
    r1 = ns["_auth_user_anfrage"](tok_a)
    r2 = ns["_auth_user_anfrage"](tok_a)
    pruef(z["user"] == 1, "Login zweimal gefragt statt einmal")
    pruef(r2.status_code == 200 and r2.json()["id"] == "u1", "Cache-Antwort falsch")
    # anderes Token → eigene Anfrage
    tok_b = jwt(t0 + 3600) + "x"
    ant["user"] += [Antwort(401, {"msg": "bad"}), Antwort(401, {"msg": "bad"})]
    pruef(ns["_auth_user_anfrage"](tok_b).status_code == 401, "fremdes Token bekam Cache-Treffer")
    pruef(ns["_auth_user_anfrage"](tok_b).status_code == 401 and z["user"] == 3, "401 wurde gemerkt")
    # nach 46 s neu gefragt
    uhr.t = t0 + 46
    ant["user"] += [Antwort(200, {"id": "u1"})]
    ns["_auth_user_anfrage"](tok_a)
    pruef(z["user"] == 4, "Login nach Ablauf nicht neu gefragt")
    # Token läuft in 10 s ab → nur bis exp gemerkt
    tok_c = jwt(uhr.t + 10)
    ant["user"] += [Antwort(200, {"id": "u2"}), Antwort(401, {})]
    ns["_auth_user_anfrage"](tok_c)
    uhr.t += 11
    pruef(ns["_auth_user_anfrage"](tok_c).status_code == 401, "Cache überlebte exp des Tokens")
    # 200 ohne id → nicht merken
    ant["user"] += [Antwort(200, {}), Antwort(200, {})]
    ns["_auth_user_anfrage"]("ohne-jwt")
    n = z["user"]
    ns["_auth_user_anfrage"]("ohne-jwt")
    pruef(z["user"] == n + 1, "200 ohne id wurde gemerkt")
    # Netzfehler → weiterwerfen, nicht merken
    ant["user"] += [RuntimeError("netz")]
    try:
        ns["_auth_user_anfrage"]("tok-netz")
        pruef(False, "Netzfehler nicht weitergeworfen")
    except RuntimeError:
        pruef(True, "")
    pruef(ns["auth_cache_bis"](100, 0) == 145 and ns["auth_cache_bis"](100, 120) == 120, "auth_cache_bis rechnet falsch")

    # Nutzerliste: Fehler nicht merken, Erfolg 60 s
    ant["liste"] += [Antwort(500, {}), Antwort(200, {"users": [{"id": "u1"}]})]
    pruef(ns["_auth_liste_anfrage"]().status_code == 500, "Liste 500 nicht durchgereicht")
    ns["_auth_liste_anfrage"]()
    r = ns["_auth_liste_anfrage"]()
    pruef(z["liste"] == 2 and r.json()["users"][0]["id"] == "u1", "Liste nicht gemerkt")
    uhr.t += 61
    ant["liste"] += [Antwort(200, {"users": []}), Antwort(200, {"users": [{"id": "u9"}]})]
    ns["_auth_liste_anfrage"]()
    ns["_auth_liste_anfrage"]()
    pruef(z["liste"] == 4, "leere Liste wurde gemerkt")

    # admin_zugang
    ant["select"] += [[{"nur_eigene": True}]]
    pruef(ns["admin_zugang_nur_eigene"]("u5") is True and ns["admin_zugang_nur_eigene"]("u5") is True
          and z["select"] == 1, "admin_zugang nicht gemerkt")
    ant["select"] += [RuntimeError("db")]
    try:
        ns["admin_zugang_nur_eigene"]("u6")
        pruef(False, "admin_zugang-Fehler nicht weitergeworfen")
    except RuntimeError:
        pruef(True, "")
    ant["select"] += [[]]
    pruef(ns["admin_zugang_nur_eigene"]("u6") is False, "ohne Zeile nicht False")

    # duplikum_credentials
    n = z["select"]
    ant["select"] += [[{"user_id": "u1"}]]
    a = ns["dup_creds_lesen"]()
    a.append({"user_id": "fremd"})            # Aufrufer verändert seine Kopie
    b = ns["dup_creds_lesen"]()
    pruef(z["select"] == n + 1 and len(b) == 1, "Creds-Cache falsch (Anzahl Abfragen oder Kopie)")

    # Leerlauf-Regel
    L = ns["watcher_leerlauf"]
    pruef(L([]) is True, "leer = Leerlauf")
    pruef(L(None) is False, "gescheiterte Runde = kein Leerlauf")
    pruef(L([{"status": "planned", "route": "tvv2"}]) is False, "geplanter Puls-Plan = schnell")
    pruef(L([{"status": "open", "route": "tvv2"}]) is False, "offener Plan = schnell")
    pruef(L([{"status": "review", "route": "duplikum", "master_pl": 1, "slave_pl": None}]) is False, "P&L-Nachversuch = schnell")
    pruef(L([{"status": "review", "route": "tvv2", "master_pl": None, "slave_pl": None}]) is True, "V2-Review = Leerlauf")
    pruef(L([{"status": "review", "route": None, "master_pl": 1, "slave_pl": 2}]) is True, "Review mit P&L = Leerlauf")

    print(f"Supabase-Diät B: {ok_n}/{ok_n + fehl_n} grün")
    raise SystemExit(1 if fehl_n else 0)


if __name__ == "__main__":
    main()
