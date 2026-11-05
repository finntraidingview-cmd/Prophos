#!/usr/bin/env python3
"""Selbsttest PF2 — Funded Futures / Winning Days haben NIE ein „Payout anfragbar ab" (Finn 05.11.2026: „Futures haben nicht Payout ab … Payout ab ist meistens
nur bei den CFDs"; Fall Jacob Apex 100k …0003/…0004/…0005 → Funded mit „Payout ab 19.11. · in 14 Tagen"). Prüft jeden Weg, auf dem ein Datum entstehen oder
angezeigt werden kann — damit es nie wieder auftaucht:
 a) prophos.html (echte Funktionen über JavaScriptCore): payoutAbErlaubt, payoutErsterTermin (Anlegen), payoutReadyInfo (alle Anzeigen), finNextPayoutVorschlag
    (Anfrage/Erhalten) — für jede Futures-Firma und beide Futures-Typen leer/null; Funded CFD unverändert
 b) prophos.html Verdrahtung: Nachfolger-Assistent, Account-Modal (Sichtbarkeit + Speichern), payoutReadySetzen, Admin-Erhalten/-Anfragen
 c) app.py (echte Funktionen): payout_ab_erlaubt, payout_anfrage_konto_felder (kein Termin, Alt-Termin wird geleert), _konto_ohne_payout_termin;
    Verdrahtung Erhalten, Payout-Kalender, Übersicht
 d) SQL: DB-Wache (before insert/update) + Bestand leeren, P2-Datei als überholt markiert
Ohne Netz. Aufruf: python3 tools/selftest_futures_ohne_payout_ab.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []
FUT_FIRMEN = ["Apex Trader", "Tradeify", "Lucid Trading", "Topstep", "FundedNext Futures", "FTMO Futures", "Alpha Future", "MyFundedFutures"]


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_block(start, ende):
    return HTML[HTML.index(start):HTML.index(ende, HTML.index(start))]


def py_fn(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


# a) Frontend-Rechnung
js = ("const window = {}\nconst _deTodayStr = () => '2026-11-05'\nconst tpFirmIstCfd = f => /fundednext(?!\\s*futures)|ftmo(?!\\s*futures)|fundingpips|the5|tradeify cfd|blue guardian/i.test(String(f || ''))\n"
      + js_block("  function payoutAbErlaubt(", "  window._payoutAbErlaubt")
      + js_block("  function payoutErsterTermin(", "  // Feld vorbelegen")
      + js_block("  function payoutReadyInfo(", "  /* PAYOUT AB (16.10.2026")
      + js_block("  function finNextPayoutVorschlag(", "  function updateFinPayoutFields(")
      + "\nconst F = __FIRMEN__\nconst T = ['funded', 'winning_days']\nprint(JSON.stringify({\n"
        "  erlaubt: ['funded', 'winning_days', 'funded_cfd', 'phase1', 'challenge', 'live', ''].map(payoutAbErlaubt),\n"
        "  anlegen: F.flatMap(f => T.map(t => payoutErsterTermin(f, t, '2026-11-05'))),\n"
        "  anzeige: F.flatMap(f => T.map(t => payoutReadyInfo({ type: t, firm: f, payoutReadyAt: '2026-11-19' }))),\n"
        "  anfrage: F.flatMap(f => T.map(t => finNextPayoutVorschlag({ type: t, firm: f, payoutReadyAt: '2026-11-19' }, '2026-11-05'))),\n"
        "  cfdAnlegen: [payoutErsterTermin('FundedNext', 'funded_cfd', '2026-11-05'), payoutErsterTermin('The5%ers', 'funded_cfd', '2026-11-05')],\n"
        "  cfdAnzeige: payoutReadyInfo({ type: 'funded_cfd', firm: 'The5%ers', payoutReadyAt: '2026-11-19' }),\n"
        "  cfdAnfrage: finNextPayoutVorschlag({ type: 'funded_cfd', firm: 'FundingPips', payoutReadyAt: null }, '2026-11-05')\n"
        "}))\n").replace("__FIRMEN__", json.dumps(FUT_FIRMEN))
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({(r.stderr or r.stdout)[-200:]})")
e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
n = len(FUT_FIRMEN) * 2
check(e.get("erlaubt") == [False, False, True, True, True, True, True], "payoutAbErlaubt: funded/winning_days nein, alle anderen Kontoarten ja")
check(e.get("anlegen") == [""] * n, f"Anlegen: keine der {len(FUT_FIRMEN)} Futures-Firmen × 2 Typen bekommt ein Datum (vorher P1 + 14 / + 21)")
check(e.get("anzeige") == [None] * n, "Anzeige (payoutReadyInfo → Accounts-Zeile, Radar, Admin, Finanzen): Alt-Termin bei Futures stumm")
check(e.get("anfrage") == [""] * n, "Anfrage/Erhalten: kein „+ 14“ bei Futures, auch nicht mit Alt-Termin")
check(e.get("cfdAnlegen") == ["2026-11-26", "2026-11-19"] and (e.get("cfdAnzeige") or {}).get("tag") == "2026-11-19" and e.get("cfdAnfrage") == "2026-11-19",
      "Funded CFD unverändert: Anlegen + 21 (FundedNext) / + 14, Anzeige, Anfrage + 14")

# b) Frontend-Verdrahtung
check("if(row) row.hidden = typ !== 'funded_cfd'" in HTML, "Nachfolger-Assistent: Feld nur bei Funded CFD")
check("&& payoutAbErlaubt(type)) newAcc.payoutReadyAt = pr.value" in HTML, "Nachfolger-Assistent speichert bei Futures nie ein Datum")
check("if(accEls.payoutSec) accEls.payoutSec.hidden = !istCfd" in HTML, "Account-Modal: Payout-Feld nur bei Funded CFD sichtbar")
check("const payoutReadyVal = !payoutAbErlaubt(type) ? null :" in HTML, "Account-Modal: Speichern bei Futures leert einen Alt-Termin")
ps = js_block("  async function payoutReadySetzen(", "  document.getElementById('fin-currency')")
check("if(!payoutAbErlaubt(a.type)){ if(typeof payoutReadyClear === 'function') await payoutReadyClear(accountId); return }" in ps
      and ps.index("payoutAbErlaubt(a.type)") < ps.index(".update({ payout_ready_at: nextVal })"), "payoutReadySetzen: Futures → leeren statt setzen (auch Hand-Datum)")
check("if(konto && typeof payoutAbErlaubt === 'function' && !payoutAbErlaubt(konto.type)){ $('adm-receive-next').value = ''" in HTML, "Admin → Erhalten: bei Futures nichts vorbelegt")
check("fundedArt" not in HTML, "Admin → Anfragen: kein Futures-„+ 14“ mehr (P1-Zweig fundedArt weg)")
# Gegenprüfung PF2: Finanzen → ✓ Erhalten (finReceivePending/finReceiveConfirm) war ein eigener Schreibweg
check("const _poFut = !!acc && !payoutAbErlaubt(acc.type)" in HTML and "nextEl.disabled = !acc || _poFut" in HTML
      and "const nextVal = (_nvAcc && !payoutAbErlaubt(_nvAcc.type)) ? null :" in HTML, "Finanzen → ✓ Erhalten: bei Futures Feld leer + gesperrt, gespeichert wird null")
check("$('adm-receive-next').disabled = !t.account_id || !!(konto && typeof payoutAbErlaubt === 'function' && !payoutAbErlaubt(konto.type))" in HTML
      and "el.disabled = !!(acc && typeof payoutAbErlaubt === 'function' && !payoutAbErlaubt(acc.type))" in HTML, "Admin → Erhalten/Anfragen: Datumsfeld bei Futures gesperrt")
check("const _nextSrv = d && Object.prototype.hasOwnProperty.call(d, 'naechster_payout') ? d.naechster_payout : next" in HTML,
      "Admin → Erhalten: lokaler Stand übernimmt nur den vom Server gesetzten Termin")
check("a.type === 'live' || !payoutAbErlaubt(a.type)) return null" in HTML, "payoutReadyInfo: zentrale Sperre für alle Anzeigen")
check(not re.search(r"const\s+PAYOUT_OHNE_AB_TYPEN", HTML), "keine const-Liste im Frontend (TDZ beim Boot ausgeschlossen)")

# c) Backend
ns = {"datetime": datetime, "timezone": timezone}
exec(re.search(r"^PAYOUT_OHNE_AB_TYPEN = .*$", APP, re.M).group(0), ns)
exec(py_fn("payout_ab_erlaubt"), ns)
E = ns["payout_ab_erlaubt"]
check(not E("funded") and not E("winning_days") and E("funded_cfd") and E("phase2") and E(None), "app.py payout_ab_erlaubt: Futures nein, Rest ja")
ns.update(WD_BALANCE_FUTURES=("apex", "tradeify", "lucid", "topstep", "futures"), _ist_tradeify_cfd=lambda f: "cfd" in str(f).lower(),
          wd_auto_konto=lambda k: False)
exec(py_fn("payout_anfrage_konto_felder"), ns)
PA = ns["payout_anfrage_konto_felder"]
f1 = PA({"account_type": "funded", "firm": "Apex Trader", "payout_ready_at": "2026-11-19"}, "2026-11-19", "2026-11-06")
f2 = PA({"account_type": "winning_days", "firm": "Tradeify", "payout_ready_at": None}, "2026-11-19", "2026-11-06")
f3 = PA({"account_type": "funded_cfd", "firm": "FundedNext", "payout_ready_at": None}, "2026-11-19", "2026-11-06")
check(f1.get("payout_ready_at", "x") is None and "payout_ready_at" not in f2 and f3.get("payout_ready_at") == "2026-11-19",
      "Anfrage (payout_anfrage_konto_felder): Futures nie ein Termin, Alt-Termin wird geleert; Funded CFD unverändert")
lese = {"fut": [{"id": "fut", "account_type": "funded", "on_demand": None}], "wd": [{"id": "wd", "account_type": "winning_days"}],
        "cfd": [{"id": "cfd", "account_type": "funded_cfd", "on_demand": False}], "od": [{"id": "od", "account_type": "funded_cfd", "on_demand": True}]}

def sb_select(tab, params):
    k = params["id"][3:]
    if k == "kaputt":
        raise RuntimeError("weg")
    return lese.get(k, [])
ns.update(sb_select=sb_select)
exec(py_fn("_konto_ohne_payout_termin"), ns)
K = ns["_konto_ohne_payout_termin"]
check(K("fut") and K("wd") and K("od") and not K("cfd") and not K("kaputt") and not K("") and not K("fehlt"),
      "Erhalten (_konto_ohne_payout_termin): Futures + On Demand ohne Termin, Funded CFD mit, Lesefehler wie bisher")
def sb_select2(tab, params):
    if "on_demand" in params["select"]:
        raise RuntimeError("column on_demand does not exist")
    return [{"id": "x", "account_type": "winning_days"}]
ns.update(sb_select=sb_select2)
check(K("x"), "Erhalten: on_demand nicht lesbar → zweiter Versuch nur mit der Kontoart, Futures bleibt ohne Termin")
check("if naechster and _konto_ohne_payout_termin(aid):" in APP, "Erhalten-Route nutzt die Futures-Sperre")
check('"ready_at": d[:10] if (d and payout_ab_erlaubt(typ)) else ""' in APP, "Payout-Kalender: Futures ohne Datum (zählen Winning Days)")
check('"payout_at": str(a.get("payout_ready_at") or "")[:10] if payout_ab_erlaubt(a.get("account_type")) else ""' in APP, "Admin-Übersicht: payout_at bei Futures leer")

# d) SQL
sql = open(os.path.join(W, "sql", "2026-11-05_futures_ohne_payout_ab.sql"), encoding="utf-8").read()
check("before insert or update of payout_ready_at, account_type on public.accounts" in sql and "new.account_type in ('funded', 'winning_days')" in sql
      and "new.payout_ready_at := null" in sql, "SQL: DB-Wache bei jedem Schreiben (insert/update), egal welcher Weg")
up = sql[sql.index("update public.accounts"):]
check("set payout_ready_at = null" in up and "account_type in ('funded', 'winning_days')" in up and "funded_cfd" not in up, "SQL: Bestand leeren, nur Futures-Typen")
p2 = open(os.path.join(W, "sql", "2026-11-04_fundednext_futures_payout_datum.sql"), encoding="utf-8").read()
check(p2.startswith("-- ⚠️ ÜBERHOLT 05.11.2026") and "NICHT EINSPIELEN" in p2.splitlines()[0], "P2-SQL (FundedNext Futures + 21) als überholt markiert")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
