#!/usr/bin/env python3
"""Selbsttest R2c (05.11.2026): PAYOUT OFFEN AUCH VON HAND. Vorfall Jacob 04.11.2026: „nur heute rein“/„heute dazu“ am Mac schaltete drei Tradeify-WD-Konten
mit offener Payout-Anfrage wieder an, POST /admin/wd-plaene legte zweimal je 3 Pläne an (00:59:57–01:00:03, 01:17:38–44 UTC), W1 (wd_payout_tick) zog sie
01:00:35 und 01:17:53 zurück; danach schrieb ein Tab mit alter Kopie „weg · Plan wurde gelöscht“ zurück → W1s Hinweis weg, kein WD mehr am selben Tag.
Prüft: (1) POST /admin/wd-plaene überspringt Konten mit offener Anfrage mit Grund = WD_HINWEIS_PAYOUT (Flask-Testclient, nachgebaute DB, ohne Netz),
andere Konten werden normal angelegt, Lesefehler → wie bisher; (2) prophos.html: wdPlaeneAnlegen, wdKontoHeute, wdKontoEinwuerfeln und wdAbgleich nutzen
dieselbe Regel und denselben Hinweis wie W1. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_wd_payout_handweg.py"""
import os
import re
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


U = "11111111-1111-4111-8111-111111111111"
K_PO, K_OK = "aaaaaaaa-0000-4000-8000-000000000001", "aaaaaaaa-0000-4000-8000-000000000002"
DB = {"pending": {K_PO}, "kaputt": False}
ANGELEGT = []


def sb_select(t, p):
    if t == "pending_payouts":
        if DB["kaputt"]:
            raise RuntimeError("DB weg")
        ids = set(re.findall(r"[0-9a-f-]{36}", str(p.get("account_id") or "")))
        return [{"account_id": a} for a in sorted(ids & DB["pending"])] if p.get("status") == "eq.pending" else []
    if t == "accounts":
        mid = str(p.get("id") or "")[3:]
        return [{"id": mid, "user_id": U, "firm": "Tradeify"}]
    if t == "trade_plans":
        return []
    return []


app.sb_select = sb_select
app.sb_insert = lambda t, z: (ANGELEGT.append(z), dict(z, id="neu-" + z["master_account_id"][-4:]))[1]
app._planer_schreib_gate = lambda: None
app._wd_login = lambda: ({"id": U}, None)
app._admin_nur_uid = lambda: None
app._admin_darf_uid = lambda uid: True
app._ap_sperren = lambda: {}
app.ap_firma_gesperrt = lambda acc, sperren: False

zeile = lambda k: {"master_account_id": k, "user_id": U, "master_firm": "Tradeify", "master_contracts": 2, "master_tp": 270,   # noqa: E731
                   "planned_for": "2026-11-04", "start_um": "2026-11-04T10:05:00Z", "notes": "Winning-Day-Farmer"}

print("1) POST /admin/wd-plaene")
c = app.app.test_client()
r = c.post("/admin/wd-plaene", json={"plaene": [zeile(K_PO), zeile(K_OK)]})
d = r.get_json() or {}
ue = {u["master_account_id"]: u["grund"] for u in d.get("uebersprungen") or []}
check(r.status_code == 200, f"Antwort 200 ({r.status_code})")
check(ue.get(K_PO) == app.WD_HINWEIS_PAYOUT, f"Konto mit offener Anfrage übersprungen, Grund = W1-Hinweis ({ue.get(K_PO)!r})")
check([z["master_account_id"] for z in ANGELEGT] == [K_OK], f"nur das Konto ohne Anfrage angelegt ({[z['master_account_id'][-4:] for z in ANGELEGT]})")
ANGELEGT.clear(); DB["pending"] = set()
d = c.post("/admin/wd-plaene", json={"plaene": [zeile(K_PO)]}).get_json() or {}
check(len(ANGELEGT) == 1 and not d.get("uebersprungen"), "nach dem Abhaken (keine offene Anfrage) wird wieder angelegt")
ANGELEGT.clear(); DB.update(pending={K_PO}, kaputt=True)
d = c.post("/admin/wd-plaene", json={"plaene": [zeile(K_PO)]}).get_json() or {}
check(len(ANGELEGT) == 1, "pending_payouts nicht lesbar → wie bisher (Tab + W1 prüfen weiter)")
DB["kaputt"] = False

print("2) prophos.html — dieselbe Regel in allen Hand-Wegen")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("const wdKontoPayoutOffen = k => !!k && (k.hinweis === WD_HINWEIS_PAYOUT || wdPayoutOffen(k.id) || !!(wdKontoDaten(k.id) || {}).payout_offen)" in html,
      "Helfer wdKontoPayoutOffen: Zeilen-Hinweis, eigener Cache, payout_offen vom Server")
i = html.index("async function wdPlaeneAnlegen(")
blk = html[i:html.index("// 2) Ein Aufruf", i)]
# SA1 #4 (05.11.2026): wdPlaeneAnlegen wertet NUR den Hinweis der frisch geladenen Zeile (kein alter Mac-/PC-Stand); die offene Anfrage selbst prüft
# POST /admin/wd-plaene frisch und gibt WD_HINWEIS_PAYOUT als Grund zurück, der Tab schreibt ihn in die Zeile
check(blk.index("if(k.hinweis === WD_HINWEIS_PAYOUT){ k.aktiv = false; delete k.nach_start; ge = true; continue }") < blk.index("allePlaene.push(pr)")
      and "wdKontoPayoutOffen(" not in blk and "wdPayoutOffen(" not in blk,
      "wdPlaeneAnlegen: Payout-Hinweis der Zeile → kein Plan (vor dem Anlegen), kein alter Cache-Stand")
i2 = html.index("for(const u of ((res && res.uebersprungen) || [])){", i)
check("k.aktiv = false; k.hinweis = u.grund" in html[i2:i2 + 600], "wdPlaeneAnlegen: Server-Grund (frisch geprüfte offene Anfrage) wird zum Zeilen-Hinweis")
i = html.index("async function wdKontoHeute(")
blk = html[i:html.index("wdRender()", i)]
check(blk.index("if(rein && wdKontoPayoutOffen(k)) return wdSay(") < blk.index("k.aktiv = !!(rein"), "wdKontoHeute: „heute rein“ bei offener Anfrage abgelehnt, bevor aktiv gesetzt wird")
i = html.index("async function wdKontoEinwuerfeln(")
blk = html[i:html.index("// 1) Haken aus", i)]
check("return { fehler: WD_PAYOUT_KEIN_WD }" in blk, "wdKontoEinwuerfeln: offene Anfrage → Fehler vor Haken und Zeile")
i = html.index("async function wdAbgleich(")
blk = html[i:html.index("async function wdKontenFrisch(", i)]
a = blk.index("if(!plan && wdPayoutOffen(k.id)){ set(k, 'plan_id', null); set(k, 'status', null); set(k, 'start_um', null); set(k, 'aktiv', false); set(k, 'hinweis', WD_HINWEIS_PAYOUT); continue }")
check(a < blk.index("if(!plan){ set(k, 'status', 'weg')"), "wdAbgleich: Plan weg + offene Anfrage → W1-Zustand statt „Plan wurde gelöscht“ (alte Kopie)")
i = html.index("  async function wdDatenLaden(tag){")
blk = html[i:html.index("async function wdApi(", i)]
check("const poOffen = new Set(rail.konten.filter(k => k && k.payout_offen).map(k => String(k.id)))" in blk
      and "for(const k of konten) if(poOffen.has(k.id)) k.payout_offen = true" in blk,
      "wdDatenLaden: payout_offen von Railway kommt auch mit RPC in die Kontenliste (vorher nie)")
check(app.WD_HINWEIS_PAYOUT in html and f"const WD_HINWEIS_PAYOUT = '{app.WD_HINWEIS_PAYOUT}'" in html, "Hinweis-Text in app.py und prophos.html gleich")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
