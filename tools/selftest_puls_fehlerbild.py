#!/usr/bin/env python3
"""Selbsttest PULS-FEHLERFOTO (29.10.2026, Slave 7) — die Railway-Routen ohne Netz (Flask-Testclient, Storage als Attrappe):
(A) puls_fehlerbild_pfad / puls_fehlerbild_erlaubt — Pfad nur mit gültiger pc_id, id (Datum ± 2 Tage) und art; Stundendeckel je PC.
(B) POST /puls-fehlerbild/<pc> — nur bekannte PCs (_rw_pc_namen, sonst 404), ohne Content-Length 411, nur JPEG, ≤ 400 KB, nie
    überschreiben (x-upsert false), Pfad <pc>/<JJJJ-MM-TT>/<id>-<art>.jpg; Deckel je PC und über alle → 429; Log nur pc_id + Größe;
    Protokoll je Foto und Status-Route.
(C) GET /admin/puls-fehlerbild — Gate zuerst (fremder Login 403, nichts signiert), dann 5-min-Link.
(D) GET /puls-fehlerbild-datei — Token nur als Header (X-Fehlerbild-Token / Bearer), Query-Token zählt nie; fehlt/zu kurz/falsch → 404,
    richtig → JPEG, Token nie im Log.
Aufruf: python3 tools/selftest_puls_fehlerbild.py"""
import contextlib
import hmac
import io
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, Response, jsonify, request

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []
TOKEN = "f" * 40
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 2000
JETZT = datetime.now(timezone.utc)
ID = JETZT.strftime("%Y%m%d-%H%M%S") + "-abc123"
ID2 = JETZT.strftime("%Y%m%d-%H%M%S") + "-def456"
PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 1500
TAG = JETZT.strftime("%Y-%m-%d")


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


class _R:
    def __init__(self, status, daten=None, inhalt=b""):
        self.status_code, self._d, self.content = status, daten, inhalt

    def json(self):
        return self._d


class _Requests:
    def __init__(self):
        self.posts, self.gets, self.dateien = [], [], {}

    def post(self, url, data=None, json=None, headers=None, timeout=None):
        self.posts.append((url, headers or {}))
        if "/object/sign/" in url:
            pfad = url.split("/object/sign/puls-fehlerbilder/", 1)[1]
            return _R(200, {"signedURL": f"/object/sign/puls-fehlerbilder/{pfad}?token=x"}) if pfad in self.dateien else _R(400, {})
        pfad = url.split("/object/puls-fehlerbilder/", 1)[1]
        if pfad in self.dateien and (headers or {}).get("x-upsert") != "true":
            return _R(409, {})
        self.dateien[pfad] = data
        return _R(200, {})

    def get(self, url, headers=None, timeout=None):
        self.gets.append(url)
        pfad = url.split("/object/puls-fehlerbilder/", 1)[1]
        return _R(200, inhalt=self.dateien[pfad]) if pfad in self.dateien else _R(404)


def lade(stubs):
    src = open(APP, encoding="utf-8").read()
    konst = ("PC_ID_MUSTER", "PULS_FEHLERBILD_BUCKET", "PULS_FEHLERBILD_MAX", "PULS_FEHLERBILD_STUNDE", "PULS_FEHLERBILD_ID_RE",
             "PULS_FEHLERBILD_PRAEFIX_RE", "HT_PAYOUTS_CSV_TOKEN_MIN", "PULS_FEHLERBILD_STUNDE_ALLE", "PULS_FEHLERBILD_TYPEN")
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in konst]
    teile += ["_puls_fehlerbild_zeiten = {}", "_puls_fehlerbild_lock = threading.Lock()"]
    for name in ("puls_fehlerbild_typ", "puls_fehlerbild_pfad", "puls_fehlerbild_erlaubt", "ht_payouts_token_ok", "_puls_fehlerbild_tor",
                 "_puls_fehlerbild_protokoll"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    for route in ('@app.route("/puls-fehlerbild/<pc_id>"', '@app.route("/puls-fehlerbild-status/<pc_id>"', '@app.route("/admin/puls-fehlerbild"',
                  '@app.route("/puls-fehlerbild-datei"'):
        i = src.index(route)
        teile.append(src[i:src.find("\n\n\n", i)])
    app = Flask("selftest")
    ns = {"re": re, "os": os, "time": time, "hmac": hmac, "threading": threading, "datetime": datetime, "timezone": timezone, "timedelta": timedelta,
          "request": request, "jsonify": jsonify, "Response": Response, "app": app,
          "SUPABASE_URL": "https://beispiel.supabase.co", "SUPABASE_SERVICE_KEY": "dienst"}
    ns.update(stubs)
    exec("\n".join(teile), ns)
    return ns, app


PCS = {"namen": {"pc-abcd12": "Finn + Pascal", "pc-voll99": "Marc"}}
LOG_ZEILEN = []


def sb_insert(tabelle, zeile):
    assert tabelle == "puls_fehlerbild_log"
    LOG_ZEILEN.append(zeile)
    return zeile


def main():
    rq = _Requests()
    gate = {"err": None}
    ns, app = lade({"requests": rq, "_admin_mail_auth": lambda: gate["err"], "_rw_pc_namen": lambda: dict(PCS["namen"]), "sb_insert": sb_insert})
    P = ns["puls_fehlerbild_pfad"]

    # (A)
    check(P("pc-abcd12", ID, "bildschirm") == f"pc-abcd12/{TAG}/{ID}-bildschirm.jpg", "A1 Pfad pc/Datum/id-art.jpg")
    alt = "20200101-000000-abc123"
    check(P("pc-abcd12", alt, "tab") is None and P("PC-X", ID, "tab") is None and P("pc-abcd12", ID, "anders") is None
          and P("pc-abcd12", "../x", "tab") is None and P("pc-abcd12", "20261399-000000-abc123", "tab") is None,
          "A2 alte id, falsche pc_id/art, Pfad-Tricks, Unsinns-Datum → None")
    z = {}
    erl = [ns["puls_fehlerbild_erlaubt"](z, "pc-a", 1000.0 + i, je_stunde=3) for i in range(4)]
    check(erl == [True, True, True, False] and ns["puls_fehlerbild_erlaubt"](z, "pc-a", 1000.0 + 3601, je_stunde=3), "A3 Stundendeckel je PC, danach wieder frei")

    cl = app.test_client()
    # (B)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        r = cl.post(f"/puls-fehlerbild/pc-abcd12?id={ID}&art=bildschirm", data=JPEG, content_type="image/jpeg")
    up = rq.posts[-1] if rq.posts else ("", {})
    check(r.status_code == 200 and r.get_json()["pfad"] == f"pc-abcd12/{TAG}/{ID}-bildschirm.jpg"
          and up[0].endswith(f"/storage/v1/object/puls-fehlerbilder/pc-abcd12/{TAG}/{ID}-bildschirm.jpg")
          and up[1].get("x-upsert") == "false" and up[1].get("Content-Type") == "image/jpeg", "B1 JPEG hochgeladen, nie überschreiben")
    check(log.getvalue().strip() == "[puls-fehlerbild] pc-abcd12 1 KB" and LOG_ZEILEN[-1] == {"pc": "pc-abcd12", "bild_id": ID, "art": "bildschirm", "kb": 1, "grund": None},
          f"B1b Log nur pc_id + Größe, Protokoll-Zeile je Foto ({log.getvalue().strip()})")
    n_rq = len(rq.posts)
    check(cl.post(f"/puls-fehlerbild/pc-erfunden?id={ID}&art=tab", data=JPEG).status_code == 404 and len(rq.posts) == n_rq,
          "B1c erfundene pc_id (nicht in _rw_pc_namen) → 404, nichts gespeichert")
    r = cl.post(f"/puls-fehlerbild/pc-abcd12?id={ID}&art=tab", data=JPEG, headers={"Transfer-Encoding": "chunked"})   # chunked: keine Länge
    check(r.status_code == 411 and len(rq.posts) == n_rq, f"B1d ohne Content-Length (chunked) → 411, nichts gelesen ({r.status_code})")
    check(cl.post(f"/puls-fehlerbild/pc-abcd12?id={ID}&art=bildschirm", data=JPEG).status_code == 502, "B2 gleicher Pfad nochmal → nicht überschrieben (502)")
    check(cl.post(f"/puls-fehlerbild/pc-abcd12?id={ID}&art=tab", data=b"<html>").status_code == 400, "B3 weder JPEG noch PNG → 400")
    r = cl.post(f"/puls-fehlerbild/pc-abcd12?id={ID2}&art=bildschirm", data=PNG)
    up = rq.posts[-1]
    check(r.status_code == 200 and r.get_json()["pfad"].endswith(f"{ID2}-bildschirm.png") and up[0].endswith(f"{ID2}-bildschirm.png")
          and up[1].get("Content-Type") == "image/png" and up[1].get("x-upsert") == "false",
          "B3b PNG (Bildschirm per GDI) → <id>-bildschirm.png als image/png, nie überschreiben")
    check(cl.post(f"/puls-fehlerbild/pc-abcd12?id={ID}&art=tab", data=b"\xff\xd8\xff" + b"x" * (400 * 1024)).status_code in (400, 413), "B4 zu groß → 400/413")
    check(cl.post(f"/puls-fehlerbild/evil?id={ID}&art=tab", data=JPEG).status_code == 400, "B5 pc_id ungültig → 400")
    check(cl.get(f"/puls-fehlerbild/pc-abcd12?id={ID}&art=tab").status_code == 405, "B6 nur POST")
    ns["_puls_fehlerbild_zeiten"]["pc-voll99"] = [time.time()] * 30
    check(cl.post(f"/puls-fehlerbild/pc-voll99?id={ID}&art=tab", data=JPEG).status_code == 429, "B7 Stundendeckel je PC → 429")
    ns["_puls_fehlerbild_zeiten"]["pc-voll99"] = []
    ns["_puls_fehlerbild_zeiten"]["*"] = [time.time()] * 200
    check(cl.post(f"/puls-fehlerbild/pc-voll99?id={ID}&art=tab", data=JPEG).status_code == 429, "B8 Deckel über alle PCs (200/h) → 429")
    ns["_puls_fehlerbild_zeiten"]["*"] = []
    r = cl.post("/puls-fehlerbild-status/pc-abcd12", json={"id": ID, "art": "tab", "grund": "kein Tab im Puls-Chrome"})
    check(r.status_code == 200 and LOG_ZEILEN[-1] == {"pc": "pc-abcd12", "bild_id": ID, "art": "tab", "kb": None, "grund": "kein Tab im Puls-Chrome"},
          "B9 Status-Route: Grund ohne Bild ins Protokoll")
    check(cl.post("/puls-fehlerbild-status/pc-erfunden", json={"id": ID, "art": "tab", "grund": "x"}).status_code == 404
          and cl.post("/puls-fehlerbild-status/pc-abcd12", json={"id": "x", "art": "tab"}).status_code == 400
          and cl.post("/puls-fehlerbild-status/pc-abcd12", json={"id": ID, "art": "tab"}, headers={"Transfer-Encoding": "chunked"}).status_code == 411,
          "B10 Status-Route: gleiches Tor, id geprüft, ohne Länge 411")
    alt_namen, PCS["namen"] = PCS["namen"], {}
    check(cl.post(f"/puls-fehlerbild/pc-abcd12?id={ID}&art=tab", data=JPEG).status_code == 404, "B11 PC-Liste nicht lesbar (leer) → 404, nie offen")
    PCS["namen"] = alt_namen

    # (C)
    gate["err"] = ("Nur für Admins", 403)
    n = len(rq.posts)
    r = cl.get(f"/admin/puls-fehlerbild?pfad=pc-abcd12/{TAG}/{ID}")
    check(r.status_code == 403 and len(rq.posts) == n, "C1 ohne Admin-Freigabe → 403, nichts signiert")
    gate["err"] = None
    r = cl.get(f"/admin/puls-fehlerbild?pfad=pc-abcd12/{TAG}/{ID}&art=bildschirm")
    d = r.get_json() or {}
    check(r.status_code == 200 and d.get("url", "").startswith("https://beispiel.supabase.co/storage/v1/object/sign/puls-fehlerbilder/"),
          "C2 Admin → signierter Link")
    check(cl.get(f"/admin/puls-fehlerbild?pfad=pc-abcd12/{TAG}/{ID}&art=tab").status_code == 404, "C3 Bild fehlt → 404")
    check(cl.get("/admin/puls-fehlerbild?pfad=../../etc").status_code == 400, "C4 Pfad-Trick → 400")
    d = cl.get(f"/admin/puls-fehlerbild?pfad=pc-abcd12/{TAG}/{ID2}&art=bildschirm").get_json() or {}
    check(d.get("pfad", "").endswith("-bildschirm.png") and ".png?token=" in d.get("url", ""), "C5 PNG-Bild → Link auf .png (JPEG zuerst probiert)")

    # (D)
    os.environ.pop("PULS_FEHLERBILD_TOKEN", None)
    q = f"/puls-fehlerbild-datei?pfad=pc-abcd12/{TAG}/{ID}&art=bildschirm"
    H = lambda t: {"X-Fehlerbild-Token": t}
    check(cl.get(q, headers=H(TOKEN)).status_code == 404, "D1 Variable fehlt → 404")
    os.environ["PULS_FEHLERBILD_TOKEN"] = "kurz"
    check(cl.get(q, headers=H("kurz")).status_code == 404, "D2 Variable zu kurz → 404")
    os.environ["PULS_FEHLERBILD_TOKEN"] = TOKEN
    check(cl.get(q).status_code == 404 and cl.get(q, headers=H("falsch")).status_code == 404, "D3 ohne/falscher Token → 404")
    check(cl.get(q + f"&token={TOKEN}").status_code == 404, "D3b Token in der URL zählt nie → 404")
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        r = cl.get(q, headers=H(TOKEN))
        r2 = cl.get(q, headers={"Authorization": f"Bearer {TOKEN}"})
    check(r.status_code == 200 and r.mimetype == "image/jpeg" and r.data == JPEG and r.headers.get("Cache-Control") == "no-store"
          and r2.status_code == 200 and TOKEN not in log.getvalue(), "D4 Token im Header (X-Fehlerbild-Token / Bearer) → das JPEG, no-store, Token nicht im Log")
    check(cl.get(f"/puls-fehlerbild-datei?pfad=pc-abcd12/{TAG}/{ID}&art=tab", headers=H(TOKEN)).status_code == 404, "D5 Bild fehlt → 404")
    r = cl.get(f"/puls-fehlerbild-datei?pfad=pc-abcd12/{TAG}/{ID2}&art=bildschirm", headers=H(TOKEN))
    check(r.status_code == 200 and r.mimetype == "image/png" and r.data == PNG, "D6 PNG-Bild → image/png")
    os.environ.pop("PULS_FEHLERBILD_TOKEN", None)

    print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
