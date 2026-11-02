#!/usr/bin/env python3
"""Selbsttest Payout-Termin von selbst (Finn 03.11.2026 ~01:15 Dubai über den Eingang): (a) Funded-CFD-Konto anlegen → Anlegetag + 14 Tage,
FundedNext + 21 (SQL-Trigger, ein von Hand eingetragenes Datum bleibt); (b) Payout anfragen → Vorschlag ab dem Anfrage-Datum + 14 Tage
(Finanzen-Fenster und Admin → Payouts „Anfragen"). Echte Funktion finNextPayoutVorschlag aus prophos.html über jsc; SQL nur statisch (kein Postgres hier).

Aufruf:  python3 tools/selftest_payout_termin_auto.py"""
import json
import os
import subprocess
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(WURZEL, "sql", "2026-11-03_payout_termin_beim_anlegen.sql"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
fehler = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        fehler.append(text)


# (a) SQL-Trigger
check("before insert on public.accounts" in sql and "new.account_type = 'funded_cfd' and new.payout_ready_at is null" in sql,
      "Trigger nur beim Anlegen, nur Funded CFD, nur bei leerem Feld (Hand-Datum bleibt)")
check("at time zone 'Europe/Berlin')::date" in sql and "like '%fundednext%' then 21 else 14" in sql and "regexp_replace(lower(" in sql,
      "Basis Anlegetag Berlin, FundedNext (auch „Funded Next“) 21, sonst 14")
check("for each row execute function public.accounts_payout_termin_neu()" in sql and "update public." not in sql, "kein Backfill, Bestand bleibt unberührt")

# (b) Vorschlag ab dem Anfrage-Datum
a = html.index("  function finNextPayoutVorschlag(")
js = "const _deTodayStr = () => '2026-11-03', window = {}\nconst tpFirmIstCfd = f => /fundednext|ftmo|fundingpips|the5|tradeify cfd/i.test(String(f || ''))\n" \
     + html[a:html.index("  function updateFinPayoutFields(")] + """
const cfd = { type: 'funded_cfd', firm: 'FundedNext', payoutReadyAt: null }
const r = {
  ab: finNextPayoutVorschlag(cfd, '2026-11-01'),
  heute: finNextPayoutVorschlag(cfd, ''),
  spaeter: finNextPayoutVorschlag(Object.assign({}, cfd, { payoutReadyAt: '2026-12-01' }), '2026-11-01'),
  frueher: finNextPayoutVorschlag(Object.assign({}, cfd, { payoutReadyAt: '2026-11-10' }), '2026-11-01'),
  fut: finNextPayoutVorschlag({ type: 'funded', firm: 'Apex Trader', payoutReadyAt: null }, '2026-11-01'),
  istCfd: [finKontoIstCfd({ type: 'winning_days', firm: 'Tradeify' }), finKontoIstCfd({ type: 'funded_cfd', firm: 'X' })]
}
print(JSON.stringify(r))"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
rr = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
try:
    e = json.loads(rr.stdout.strip().splitlines()[-1])
except Exception:
    print(rr.stdout[-400:], rr.stderr[-400:]); e = {}
check(e.get("ab") == "2026-11-15" and e.get("heute") == "2026-11-17", "Anfrage-Datum + 14 (auch FundedNext, zweiter Zyklus); ohne Datum heute + 14")
check(e.get("spaeter") == "2026-12-01" and e.get("frueher") == "2026-11-15", "späteres Datum am Konto bleibt, früheres gehört zum alten Zyklus")
check(e.get("fut") == "2026-11-15" and e.get("istCfd") == [False, True], "Futures im Finanzen-Fenster wie bisher; CFD-Erkennung")

# Einbau
check("nextEl.dataset.ab !== abTag && nextEl.value === (nextEl.dataset.vorschlag || '')" in html and "addEventListener('change', () => { updateFinWiederholen(); updateFinPayoutFields() })" in html,
      "Finanzen: Datum oben geändert → Vorschlag zieht mit, solange das Feld unberührt ist")
check("admAnfrageNextVorschlag(true)" in html and "window._finKontoIstCfd(acc) && typeof window._finNextPayoutVorschlag" in html and "if(!neu && el.value !== (el.dataset.vorschlag || '')) return" in html,
      "Admin → Payouts „Anfragen“: CFD vorbelegt, Futures leer, Hand-Datum bleibt beim Datumswechsel")
print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
