#!/usr/bin/env python3
"""Selbsttest P1 — „Payout anfragbar ab“ beim Anlegen vorbelegt (Finn 03.11.2026 ~22:55 Dubai: FundedNext erster Zyklus 21 Tage, alles andere 14;
nach jeder Payout-Anfrage wieder 14). prophos.html payoutErsterTermin (gerechnet in JavaScriptCore), Account-Modal, Nachfolger-Assistent, Admin-Anfrage,
Erhalten-Modal, SQL-Bestand. Ohne Netz. Aufruf: python3 tools/selftest_payout_anlegen.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-11-03_fundednext_payout_datum.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


fn = HTML[HTML.index("  function payoutErsterTermin("):HTML.index("  window._payoutErsterTermin")]
FAELLE = [("FundedNext", "funded_cfd", "2026-11-03", "2026-11-24"), ("Funded Next", "funded_cfd", "2026-11-03", "2026-11-24"),
          ("FTMO", "funded_cfd", "2026-11-03", "2026-11-17"), ("Apex", "funded", "2026-11-03", "2026-11-17"),
          ("Tradeify", "winning_days", "2026-12-25", "2027-01-08"), ("FundedNext Futures", "funded", "2026-11-03", "2026-11-24"), ("FundedNext", "phase2", "2026-11-03", ""),
          ("FundedNext", "live", "2026-11-03", ""), ("FTMO", "funded_cfd", "", "")]
js = fn + "\nconst _deTodayStr = () => '2026-11-03';\nprint(JSON.stringify(" + json.dumps(FAELLE) + ".map(f => payoutErsterTermin(f[0], f[1], f[2]))));"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:160]})")
erg = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
for (firm, typ, tag, soll), g in zip(FAELLE, erg):
    check(g == soll, f"{firm} {typ} angelegt {tag or '–'} → {soll or 'kein Termin'} (ist {g or '–'})")

vf = HTML[HTML.index("  function payoutVorschlagFeld("):HTML.index("  window._payoutErsterTermin")]
check("el.value && el.value !== (el.dataset.vorschlag || '')" in vf, "von Hand geändert bleibt (nur leer oder letzter Vorschlag wird überschrieben)")
tg = HTML[HTML.index("  function toggleAcBloecke(){"):HTML.index("  function toggleAcBloecke(){") + 6000]
check("accEls.payoutSec.hidden = !(istFunded || istCfd)" in tg and "if(!_editingAccountId) payoutVorschlagFeld(accEls.payoutReady, firm, typ)" in tg,
      "Account-Modal: Feld bei allen Funded-Typen sichtbar, nur beim Anlegen vorbelegt (Bearbeiten nie)")
check("accEls.payoutReady.value = ''; accEls.payoutReady.dataset.vorschlag = ''" in HTML, "neues Konto: Feld und Vorschlag zurückgesetzt")
check('id="suc-payout-ready"' in HTML and 'id="suc-payout-row" hidden' in HTML, "Nachfolger-Assistent hat das Feld (versteckt bis Funded-Typ)")
sw = HTML[HTML.index("  function openSuccessorWizard("):HTML.index("  function openSuccessorWizard(") + 5000]
check("sucPayoutVorschlag()" in sw and "pr.dataset.vorschlag = ''" in sw, "Assistent belegt beim Öffnen frisch vor")
check("document.getElementById('suc-type')?.addEventListener('change', sucPayoutVorschlag)" in HTML and "document.getElementById('suc-firm')?.addEventListener('input', sucPayoutVorschlag)" in HTML,
      "Assistent folgt Typ und Firma")
check("if(pr && prRow && !prRow.hidden && /^\\d{4}-\\d{2}-\\d{2}$/.test(pr.value)) newAcc.payoutReadyAt = pr.value" in HTML, "Assistent speichert das Datum nur bei sichtbarem Feld")
check("payout_ready_at:  a.payoutReadyAt  || null" in HTML, "accountToRow schreibt payout_ready_at")
check("(window._finKontoIstCfd(acc) || fundedArt)" in HTML, "Admin-Anfrage: Anfrage-Datum + 14 auch bei Funded Futures/Winning Days")
check("else if(_admReceiveO.naechsterTage && t.account_id && !$('adm-receive-next').value)" in HTML and "admReceivePlus(String(t.requested_at).slice(0, 10), 14)" in HTML,
      "Erhalten-Modal: Termin vom Konto geht vor, sonst Anfrage-Datum + 14, erst dann Erhalten + N")
fv = HTML[HTML.index("  function finNextPayoutVorschlag("):HTML.index("  function finKontoIstCfd(")]
check("setUTCDate(d.getUTCDate() + 14)" in fv, "Finanzen → Payout-Anfrage: Anfrage-Datum + 14 (alle Firmen)")
# SQL
check("like '%fundednext%'" in SQL and "a.account_type = 'funded_cfd'" in SQL and "a.waiting_payout_since is not null" in SQL and "a.payout_ready_at is null" in SQL,
      "SQL: nur FundedNext, Funded CFD, Waiting for Payout, Feld leer (idempotent)")
check(SQL.count("not exists (select 1 from public.pending_payouts pp where pp.account_id = a.id)") >= 2
      and SQL.count("not exists (select 1 from public.transactions tx where tx.account_id = a.id and tx.kind = 'payout')") >= 2, "SQL: nur Konten ohne Payout (Vorschau und Update gleich)")
check(SQL.count("at time zone 'Europe/Berlin')::date + 21") >= 2 and "p.slave_account_id = a.id" in SQL and "min(p.started_at)" in SQL and "coalesce(" in SQL, "SQL: erster Trade (Berlin-Tag) + 21, sonst waiting_payout_since + 21")
up = SQL[SQL.index("update public.accounts a"):]
check("g.gruppe like 'Hermann Technologies%'" in up, "SQL: Update nur Gruppe Hermann Technologies")
check("14367785" in SQL and "14367823" in SQL, "SQL: Kontrolle Aurel 100k / Marc 100k")
SQL2 = open(os.path.join(W, "sql", "2026-11-04_fundednext_futures_payout_datum.sql"), encoding="utf-8").read()
up2 = SQL2[SQL2.index("update public.accounts a"):]
check("like '%fundednext%'" in up2 and "like '%futures%'" in up2 and "a.account_type in ('funded', 'winning_days')" in up2 and "a.payout_ready_at is null" in up2
      and "g.gruppe like 'Hermann Technologies%'" in up2, "P2-SQL: nur FundedNext Futures Funded/Winning Days, Feld leer, nur HT")
check(up2.count("not exists") == 3 and "at time zone 'Europe/Berlin')::date + 21" in up2 and "a.created_at)" in up2, "P2-SQL: ohne Payout (3 Quellen), erster Trade (Berlin) + 21, sonst Anlegetag + 21")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
