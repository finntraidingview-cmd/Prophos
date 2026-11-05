#!/usr/bin/env python3
"""Selbsttest DU1 (05.11.2026): /duplikum/session gibt nur die eigene Duplikium-Zeile oder den geteilten Zugang DESSELBEN Unternehmens heraus —
nie „irgendeine" Zeile (bis .2066 rows[0] = live Emins Zugang für jede ID ohne eigene Zeile). Fixture = Live-Stand 05.11.2026 (Reihenfolge der
Tabelle, Mail nur als Kürzel, Unternehmen aus id_gruppe_mitglied). Ohne Netz. Aufruf: python3 tools/selftest_du1_duplikum_session.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


HT, EM = "7ad374a1-c470-4b13-bf6b-24722f82739a", "90c616f3-3ec1-49cb-b3ba-8a267d0a43df"
EMIN = "6cceb3f3-dc78-48ee-8668-26081da3e70f"
# duplikum_credentials in Tabellen-Reihenfolge (live): user_id → Mail-Kürzel
ROWS = [(EMIN, "c48f911e"), ("7b1bc9a3-94d3-4603-a232-c10fc2df3262", "8740f448"), ("46ce0409-4dd5-46b0-b88b-963c3194ae26", "8740f448"),
        ("32b854d1-866f-4e7e-ba0b-9bf63df2d993", "8740f448"), ("8ad6a2f1-816e-4229-85cd-03a9c693bb71", "8cad7f36"),
        ("13905525-69d0-4949-b081-efdbc397e888", "8740f448"), ("b55d7ab4-5246-4101-abca-f729c71d17ec", "76c920cd"),
        ("d55671f9-d587-4ef1-95f3-95622008fe98", "c48f911e"), ("368076fd-67c1-460c-aa86-38d81ae69350", "7b80d9bb"),
        ("728b4d23-ff5c-45f9-b6de-9b75c1f9a78a", "8740f448")]
rows = [{"user_id": u, "email": f"{h}@stub", "password": "x"} for u, h in ROWS]
HT_IDS = ["8ad6a2f1-816e-4229-85cd-03a9c693bb71", "48f272b4-913e-4598-a06a-1dcc3d5679fb", "eeeeeeee-0000-4000-a000-000000000001",
          "32b854d1-866f-4e7e-ba0b-9bf63df2d993", "d1f5bcae-2129-49a4-8415-915ab6474a64", "7b1bc9a3-94d3-4603-a232-c10fc2df3262",
          "aff98e60-e9a0-4821-9d1d-31634571a2f4", "13905525-69d0-4949-b081-efdbc397e888", "b55d7ab4-5246-4101-abca-f729c71d17ec",
          "1c96cf0f-5aa6-46c6-8073-617e083e4378", "46ce0409-4dd5-46b0-b88b-963c3194ae26", "728b4d23-ff5c-45f9-b6de-9b75c1f9a78a",
          "368076fd-67c1-460c-aa86-38d81ae69350", "6c206a34-c4a7-4352-8097-bb17366bcea1", "5409e926-09bc-4789-9c99-f8584d87a89a"]
EM_IDS = [EMIN, "d55671f9-d587-4ef1-95f3-95622008fe98", "fb42b5c3-def9-4bc0-8b5b-bb2525b76ad8", "f6e166c1-d77c-45b0-8d0a-52dd22290112",
          "6370fb87-29b0-4cf0-a896-616f6754e328", "fcd47013-9bc8-4278-8768-5f8dec5fafcf"]
daten = {"gruppen": [{"id": HT, "verwalter_id": None}, {"id": EM, "verwalter_id": EMIN}],
         "mitglieder": [{"user_id": u, "gruppe_id": HT} for u in HT_IDS] + [{"user_id": u, "gruppe_id": EM} for u in EM_IDS]}
eigen = dict(ROWS)
alt = lambda uid: next((c for c in rows if c["user_id"] == uid), None) or rows[0]   # noqa: E731  — Verhalten bis .2066

# 1) Liste vorher/nachher für alle 21 IDs
print("ID        Unternehmen  vorher    nachher   Quelle")
for uid in HT_IDS + EM_IDS:
    c, q = app.dup_creds_fuer(uid, rows, daten)
    v, n = alt(uid)["email"][:8], (c["email"][:8] if c else "— 404")
    print(f"{uid[:8]}  {'HT   ' if uid in HT_IDS else 'Emin '}        {v}  {n:9} {q}")
    if uid in eigen:
        ok(c is not None and c["user_id"] == uid and q == "eigen" and n == v, f"{uid[:8]} eigene Zeile wie vorher")
    else:
        firma = HT_IDS if uid in HT_IDS else EM_IDS
        ok(c is not None and c["user_id"] in firma and q == "unternehmen", f"{uid[:8]} ohne eigene → Zugang des eigenen Unternehmens")
        ok(n == ("8740f448" if uid in HT_IDS else "c48f911e"), f"{uid[:8]} = meistgenutzter Zugang des Unternehmens ({n})")

# 2) nie Fremdes: keine HT-ID bekommt Emins Zugang, keine Emin-ID einen HT-Zugang
fremd = [u for u in HT_IDS if (app.dup_creds_fuer(u, rows, daten)[0] or {}).get("user_id") in EM_IDS] + \
        [u for u in EM_IDS if (app.dup_creds_fuer(u, rows, daten)[0] or {}).get("user_id") in HT_IDS]
ok(not fremd, f"kein Zugang über Unternehmensgrenzen ({len(fremd)}) — vorher bekamen 7 HT-IDs Emins Zugang")

# 3) ohne Unternehmen / Gruppen nicht lesbar / leere Mail
neu = "99999999-0000-4000-a000-000000000099"
ok(app.dup_creds_fuer(neu, rows, daten) == (None, None), "ID ohne Unternehmen (UNT0) → nichts")
ok(app.dup_creds_fuer("48f272b4-913e-4598-a06a-1dcc3d5679fb", rows, None) == (None, None), "Gruppen nicht lesbar → nur eigene Zeile, sonst nichts")
c, q = app.dup_creds_fuer(EMIN, rows, None)
ok(c is not None and c["user_id"] == EMIN and q == "eigen", "Gruppen nicht lesbar → eigene Zeile bleibt")
leer = [{"user_id": "48f272b4-913e-4598-a06a-1dcc3d5679fb", "email": " "}] + rows
c, q = app.dup_creds_fuer("48f272b4-913e-4598-a06a-1dcc3d5679fb", leer, daten)
ok(c is not None and c["email"].startswith("8740f448") and q == "unternehmen", "eigene Zeile ohne Mail zählt nicht → Unternehmen")
ok(app.dup_creds_fuer("", rows, daten) == (None, None), "ohne uid → nichts")
# Verwalter ohne Mitglied-Zeile gehört zu seiner Gruppe
d2 = {"gruppen": daten["gruppen"], "mitglieder": [m for m in daten["mitglieder"] if m["user_id"] != EMIN]}
r2 = [r for r in rows if r["user_id"] != EMIN]
c, q = app.dup_creds_fuer(EMIN, r2, d2)
ok(c is not None and c["user_id"] in EM_IDS and q == "unternehmen", "Verwalter ohne eigene Zeile → Zugang seiner Gruppe")

# 4) Route: 404 ohne Zugang, eigener Token, kein Env-Rückfall
ZU = {"uid": neu}


class R:
    status_code = 200

    def json(self):
        return {"id": ZU["uid"]}


app._auth_user_anfrage = lambda tok: R()
app.dup_creds_lesen = lambda: list(rows)
app.admin_gruppen_daten = lambda: daten
app.wt_email_token = lambda creds: "TOK-" + creds["email"][:8]
app.DUP_EMAIL, app.DUP_PASSWORD = "env@stub", "x"
app.SUPABASE_SERVICE_KEY = app.SUPABASE_SERVICE_KEY or "stub"
c = app.app.test_client()
r = c.get("/duplikum/session", headers={"sb-token": "t"})
ok(r.status_code == 404 and not (r.get_json() or {}).get("token"), f"Route: ID ohne Unternehmen → 404, kein Token, kein Env-Rückfall ({r.status_code})")
ZU["uid"] = "fb42b5c3-def9-4bc0-8b5b-bb2525b76ad8"
d = c.get("/duplikum/session", headers={"sb-token": "t"}).get_json()
ok(d.get("token") == "TOK-c48f911e", f"Route: Emin-Mitglied ohne Zeile → Emins geteilter Zugang ({d.get('token')})")
ZU["uid"] = "48f272b4-913e-4598-a06a-1dcc3d5679fb"
d = c.get("/duplikum/session", headers={"sb-token": "t"}).get_json()
ok(d.get("token") == "TOK-8740f448", f"Route: HT-ID ohne Zeile → HT-Zugang statt Emins ({d.get('token')})")
ZU["uid"] = "b55d7ab4-5246-4101-abca-f729c71d17ec"
d = c.get("/duplikum/session", headers={"sb-token": "t"}).get_json()
ok(d.get("token") == "TOK-76c920cd", f"Route: eigene Zeile → eigener Token ({d.get('token')})")
app.admin_gruppen_daten = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
ZU["uid"] = "48f272b4-913e-4598-a06a-1dcc3d5679fb"
r = c.get("/duplikum/session", headers={"sb-token": "t"})
ok(r.status_code == 404, f"Route: Gruppen nicht lesbar → ohne eigene Zeile 404 ({r.status_code})")
app.dup_creds_lesen = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
r = c.get("/duplikum/session", headers={"sb-token": "t"})
ok(r.status_code == 502, f"Route: Zugänge nicht lesbar → 502 ({r.status_code})")
ok(c.get("/duplikum/session").status_code == 401, "Route: ohne Login 401")

print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
