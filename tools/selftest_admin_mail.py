#!/usr/bin/env python3
"""Selbsttest ADMIN → MAIL (21.10.2026, Slave-Terminal 3 — Finn 05:15 Dubai: „Unter Admin noch einmal Gmail hinzufügen, wo ich alle
Gmail-Accounts jeder einzelnen ID im Überblick habe … nach jeder ID filtern oder alles").
Backend (app.py, Funktionsblöcke ohne Netz): admin_mail_params (UUID, limit 1…500, vor als ISO), admin_mail_zaehler (Content-Range),
admin_mail_ids (Sicht ohne excluded, verbunden = zuletzt_at, Reihenfolge, Ungelesen nur für verbundene). Routen-Vertrag: _admin_auth
(ADMIN_EMAILS) vor allem anderen, fremde ID → 404, PATCH nur in der Sicht. Frontend (prophos.html, per macOS-jsc): mailZeileHtml mit und
ohne ID-Kopf (ungelesen fett, Absender ohne Adresse, escaped); Mail-Reiter und Admin nutzen dieselbe Zeile und dieselbe Lese-Ansicht
(mailLesenZeigen), Reiter nur Hermann Technologies (KASSE_REITER_HT), Laden nur beim Öffnen/↻ (kein setInterval im Block).
Alle Kennungen erfunden. Aufruf: python3 tools/selftest_admin_mail.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []
KONSTANTEN = ("ADMIN_MAIL_LIMIT", "ADMIN_MAIL_LIMIT_MAX", "ADMIN_MAIL_UID_RE")
FUNKTIONEN = ("admin_mail_params", "admin_mail_zaehler", "admin_mail_ids")


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns, src


def js_funktion(src, name):
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


A, B, C, D = ("aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002",
              "cccccccc-0000-4000-8000-000000000003", "dddddddd-0000-4000-8000-000000000004")


def main():
    ns, src = lade()
    P, Z, I = ns["admin_mail_params"], ns["admin_mail_zaehler"], ns["admin_mail_ids"]

    # Parameter
    check(P({}) == (None, 200, None), "ohne Parameter: alle IDs, 200, kein vor")
    check(P({"user_id": A.upper(), "limit": "50"}) == (A, 50, None), "user_id (Großschrift → klein), limit 50")
    check(P({"limit": "9999"})[1] == 500 and P({"limit": "0"})[1] == 1, "limit auf 1…500 geklemmt")
    check(P({"vor": "2026-10-20T10:00:00Z"})[2] == "2026-10-20T10:00:00+00:00", "vor → ISO UTC")
    for bad, name in (({"user_id": "x' or 1=1"}, "user_id"), ({"limit": "zehn"}, "limit"), ({"vor": "gestern"}, "vor")):
        try:
            P(bad)
            check(False, f"ungültig {name} → ValueError")
        except ValueError:
            check(True, f"ungültig {name} → ValueError")

    # Content-Range
    check(Z("0-24/808") == 808 and Z("*/0") == 0 and Z(None) is None and Z("x") is None, "Content-Range → Zahl, sonst None")

    # Chips
    disp = {A: "Moritz", B: "Finn", C: "Emin", D: "Ina"}
    sk = [{"user_id": A, "zuletzt_at": "2026-10-21T01:00:00Z", "zuletzt_mail_at": "2026-10-21T00:55:00Z"},
          {"user_id": B, "zuletzt_at": "2026-10-21T01:00:00Z", "zuletzt_mail_at": None},
          {"user_id": D, "zuletzt_at": None}, {"user_id": C, "zuletzt_at": "2026-10-21T01:00:00Z"}]
    ids = I(disp, {C}, sk, {A: 3, B: 808, D: 5})
    check([x["name"] for x in ids] == ["Finn", "Moritz", "Ina"], f"Reihenfolge verbunden zuerst, dann Name; Emin (excluded) fehlt ({[x['name'] for x in ids]})")
    check(ids[0]["ungelesen"] == 808 and ids[1]["ungelesen"] == 3, "Ungelesen je verbundener ID")
    check(ids[2]["verbunden"] is False and ids[2]["ungelesen"] is None, "Schlüssel ohne zuletzt_at = nicht verbunden, keine Zahl")
    check(I({A: ""}, set(), [], {})[0]["name"] == A[:8], "ohne Namen → erste 8 Zeichen")

    # Routen-Vertrag (Quelltext)
    i = src.index('@app.route("/admin/mail", methods=["GET", "PATCH", "OPTIONS"])')
    blk = src[i:src.index('@app.route("/code/datei/', i)]
    check(blk.count("_admin_auth()") == 2, "beide Admin-Mail-Routen hinter _admin_auth (ADMIN_EMAILS)")
    check(blk.index("_admin_auth()") < blk.index("sb_select("), "Gate vor jedem DB-Zugriff")
    check('"ID nicht in dieser Sicht"' in blk and blk.count("not in sicht") >= 3, "fremde/ausgeblendete ID → 404 (Liste, Lesen, PATCH)")
    sb = src[src.index("\ndef _admin_mail_sicht("):src.index("\ndef _admin_mail_ungelesen(")]
    check("_wd_personen()" in sb and blk.count("_admin_mail_sicht()") == 2, "Sicht = Standard-Sicht HT über _wd_personen (Emins Gruppe draußen), beide Routen")

    # Frontend
    html = open(HTML, encoding="utf-8").read()
    check("const KASSE_REITER_HT = new Set(['rg', 'kasse', 'auftrag', 'mail'])" in html, "Reiter Mail nur Hermann Technologies (nie Verwalter)")
    check('data-admtab="mail">Mail</button>' in html and '<div id="adm-pane-mail" hidden>' in html, "Reiter-Knopf + Pane vorhanden")
    check("$('adm-pane-mail').hidden     = name !== 'mail'" in html and "if(name === 'mail') window._admMailOeffnen?.()" in html, "Umschalter blendet Pane und lädt beim Öffnen")
    a = html.index("/* ══ ADMIN → MAIL (21.10.2026")
    blk = html[a:html.index("window._admMailStub", a)]
    check("setInterval" not in blk and "setTimeout(" not in blk, "kein Takt im Admin-Mail-Block (nur Öffnen + ↻)")
    check("mailLesenZeigen(el, m, _admMail.bilder" in blk and "mailZeileHtml(m," in blk, "Admin nutzt dieselbe Zeile + Lese-Ansicht wie der Mail-Reiter")
    check("mailLesenZeigen(el, m, _mail.bilder" in html and "_mail.liste.map(m => mailZeileHtml(" in html, "Mail-Reiter nutzt die gemeinsamen Funktionen")
    check(html.count("f.setAttribute('sandbox', 'allow-popups allow-popups-to-escape-sandbox')") == 1, "genau EIN Mail-Renderer (sandbox-iframe einmal im Code)")

    if not os.path.exists(JSC):
        print("✗ jsc fehlt"); sys.exit(1)
    js = "\n".join([js_funktion(html, "escapeHtml"), js_funktion(html, "mailVonKurz"), js_funktion(html, "mailZeit"), js_funktion(html, "mailZeileHtml")])
    js += r"""
const m1 = { id: 7, von: '"Lucid Trading" <support@example.com>', betreff: 'Payout <b>approved</b>', snippet: 'Hi', datum: '2026-10-20T10:00:00Z', gelesen: false, anhaenge: [{ name: 'a.pdf' }] }
const m2 = Object.assign({}, m1, { id: 8, gelesen: true, anhaenge: [] })
print(JSON.stringify({ a: mailZeileHtml(m1, true, '<span class="mz-id">Finn</span>'), b: mailZeileHtml(m2, false) }))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    if r.returncode != 0:
        print("✗ jsc:", (r.stdout + r.stderr)[-600:]); sys.exit(1)
    o = json.loads(r.stdout.strip().splitlines()[-1])
    check('class="mail-zeile neu aktiv" data-mail-id="7"' in o["a"] and '<span class="mz-id">Finn</span>Lucid Trading' in o["a"], "Zeile: ungelesen + aktiv, ID-Kopf vor dem Absender (ohne Adresse)")
    check("Payout &lt;b&gt;approved&lt;/b&gt;" in o["a"] and "📎" in o["a"], "Betreff escaped, Anhang-Zeichen")
    check('class="mail-zeile" data-mail-id="8"' in o["b"] and "mz-id" not in o["b"], "Zeile ohne ID-Kopf (Mail-Reiter) unverändert")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  "); sys.exit(1)
    print("alle Prüfungen bestanden")


if __name__ == "__main__":
    main()
