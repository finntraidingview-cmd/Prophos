#!/usr/bin/env python3
"""Selbsttest SA1c (05.11.2026, S6-Hinweis zu SA1 #4): POST /admin/wd-plaene ist fail-closed, wenn pending_payouts nicht lesbar ist — kein WD-Plan,
Grund WD_GRUND_PAYOUT_UNLESBAR (im Tab vorübergehend: WD_AUTO_HINWEISE), eine Meldung je 30 min. Lesbar: wie bisher (offene Anfrage → WD_HINWEIS_PAYOUT,
sonst angelegt). Ohne Netz. Aufruf: python3 tools/selftest_sa1c.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


U = "11111111-1111-4111-8111-111111111111"
K1, K2 = "aaaaaaaa-0000-4000-8000-000000000001", "aaaaaaaa-0000-4000-8000-000000000002"
Z = {"po": "ok", "offen": set(), "insert": [], "alarm": []}


def sb_select(t, params):
    if t == "pending_payouts":
        if Z["po"] == "fehler":
            raise RuntimeError("Supabase weg")
        return [{"account_id": k} for k in Z["offen"]]
    if t == "accounts":
        return [{"id": params["id"][3:], "user_id": U, "firm": "Tradeify"}]
    return []


app.sb_select = sb_select
app.sb_insert = lambda t, body: Z["insert"].append(body) or {"id": "neu-" + body["master_account_id"][-1], **body}
app._planer_schreib_gate = lambda: None
app._wd_login = lambda: (U, None)
app._admin_darf_uid = lambda u: True
app._ap_sperren = lambda: {}
app.alarm_senden = lambda *a, **k: Z["alarm"].append((a, k))
c = app.app.test_client()
PLAENE = [{"master_account_id": K1, "user_id": U, "planned_for": "2026-11-05", "start_um": "2026-11-05T14:00:00+00:00", "notes": "Winning-Day-Farmer"},
          {"master_account_id": K2, "user_id": U, "planned_for": "2026-11-05", "start_um": "2026-11-05T14:05:00+00:00", "notes": "Winning-Day-Farmer"}]


def post():
    Z["insert"].clear()
    r = c.post("/admin/wd-plaene", json={"plaene": [dict(p) for p in PLAENE]})
    return r.status_code, r.get_json() or {}


# 1) lesbar, keine Anfrage → beide angelegt (wie bisher)
s1, d1 = post()
ok(s1 == 200 and len(Z["insert"]) == 2 and not d1.get("uebersprungen"), f"lesbar, keine Anfrage: 2 angelegt ({s1}, {len(Z['insert'])})")
# 2) lesbar, K1 offen → K1 WD_HINWEIS_PAYOUT, K2 angelegt
Z["offen"] = {K1}
s2, d2 = post()
ok([u["grund"] for u in d2.get("uebersprungen") or []] == [app.WD_HINWEIS_PAYOUT] and len(Z["insert"]) == 1, "offene Anfrage: Konto übersprungen, das andere angelegt")
# 3) NICHT lesbar → fail-closed: keins angelegt, beide mit WD_GRUND_PAYOUT_UNLESBAR, eine Meldung
Z["offen"], Z["po"] = set(), "fehler"
app._wd_po_fehler_gemeldet["at"] = 0.0
s3, d3 = post()
gr = [u["grund"] for u in d3.get("uebersprungen") or []]
ok(s3 == 200 and not Z["insert"] and gr == [app.WD_GRUND_PAYOUT_UNLESBAR] * 2, f"nicht lesbar: kein Plan, beide Konten mit vorübergehendem Grund ({gr})")
ok(len(Z["alarm"]) == 1 and Z["alarm"][0][0][1] == "wd_payout_unlesbar", "nicht lesbar: eine Meldung an die Master-IDs")
post()
ok(len(Z["alarm"]) == 1, "zweiter Lauf innerhalb 30 min: keine zweite Meldung")
# 4) Tab: der Grund ist vorübergehend (WD_AUTO_HINWEISE) — genau derselbe Text
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
zeile = next(z for z in HTML.splitlines() if "const WD_AUTO_HINWEISE = [" in z)
ok(f"'{app.WD_GRUND_PAYOUT_UNLESBAR}'" in zeile, "Tab: Grund steht in WD_AUTO_HINWEISE → Konto ist beim nächsten Lauf wieder dabei")
ok("if(!wdAktiv(k)){ if(k.farm && k.ext && WD_AUTO_HINWEISE.includes(k.hinweis)){ k.aktiv = true; k.hinweis = ''; ge = true }" in HTML,
   "Tab: wdPlaeneAnlegen holt Konten mit WD_AUTO_HINWEISE von selbst zurück")
# 5) wieder lesbar → wieder angelegt
Z["po"] = "ok"
s5, d5 = post()
ok(len(Z["insert"]) == 2 and not d5.get("uebersprungen"), "wieder lesbar: wieder angelegt")

print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
