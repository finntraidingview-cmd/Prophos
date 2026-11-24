#!/usr/bin/env python3
"""Selbsttest FN1 (Finn 25.11.2026: „Für FundedNext-Payout-Anfragen: Wenn da steht ‚in 14 Tagen‘, kann man immer erst in 15 Tagen anfragen, immer erst einen
Tag danach. Also nicht 14 oder 21, sondern immer +1 Tag: 15 und 22 Tage.“). Echte Funktionen aus prophos.html in JavaScriptCore: payoutZyklusTage,
payoutErsterTermin, finNextPayoutVorschlag, admReceiveTage (Fenster „Payout erhalten“); SQL nur statisch. Ohne Netz. Aufruf: python3 tools/selftest_fn1_fundednext_plus1.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-11-25_fn1_fundednext_plus1.sql"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(a, b):
    i = HTML.index(a)
    return HTML[i:HTML.index(b, i)]


rt = re.search(r"    const admReceiveTage = .*\n", HTML)
check(bool(rt), "admReceiveTage im Erhalten-Fenster gefunden")
js = ("const window = {}\nconst _deTodayStr = () => '2026-11-25'\nconst tpFirmIstCfd = f => /fundednext|ftmo|fundingpips|the5/i.test(String(f || ''))\n"
      + block("  function payoutZyklusTage(", "  window._payoutZyklusTage")
      + block("  function payoutAbErlaubt(", "  window._payoutAbErlaubt")
      + block("  function payoutErsterTermin(", "  // Feld vorbelegen")
      + block("  function finNextPayoutVorschlag(", "  function updateFinPayoutFields(")
      + block("  function fcfdPayoutAb(", "  /* PAYOUTS AUF DEM WEG")
      + (rt.group(0) if rt else "") + """
print(JSON.stringify({
  zyklus: [payoutZyklusTage('FundedNext', true), payoutZyklusTage('FundedNext', false), payoutZyklusTage('Funded Next', false), payoutZyklusTage('FTMO', true),
           payoutZyklusTage('FTMO', false), payoutZyklusTage('', false), payoutZyklusTage(null, true)],
  anlegen: [payoutErsterTermin('FundedNext', 'funded_cfd', '2026-11-25'), payoutErsterTermin('FTMO', 'funded_cfd', '2026-11-25'), payoutErsterTermin('FundedNext', 'funded', '2026-11-25')],
  anfrage: [finNextPayoutVorschlag({ type: 'funded_cfd', firm: 'FundedNext' }, '2026-11-25'), finNextPayoutVorschlag({ type: 'funded_cfd', firm: 'The5%ers' }, '2026-11-25'),
            finNextPayoutVorschlag({ type: 'funded_cfd', firm: 'FundedNext', onDemand: true }, '2026-11-25')],
  erhalten: [admReceiveTage({ account_firm: 'FundedNext' }, 14), admReceiveTage({ account_firm: 'FTMO' }, 14), admReceiveTage(null, 14)],
  gerechnet: [fcfdPayoutAb({ id: 'k1', firm: 'FundedNext', created: '2026-11-01' }, []).ab, fcfdPayoutAb({ id: 'k1', firm: 'FundedNext', created: '2026-11-01' }, [{ art: 'payout', aid: 'k1', datum: '2026-11-20' }]).ab,
              fcfdPayoutAb({ id: 'k2', firm: 'FTMO', created: '2026-11-01' }, []).ab, fcfdPayoutAb({ id: 'k3', firm: 'FundedNext', payout_ready_at: '2026-12-01' }, []).ab]
}))""")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:200]})")
e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
check(e.get("zyklus") == [22, 15, 15, 14, 14, 14, 14], f"payoutZyklusTage: FundedNext 22/15 (auch „Funded Next“), andere 14/14: {e.get('zyklus')}")
check(e.get("anlegen") == ["2026-12-17", "2026-12-09", ""], f"Anlegen: FundedNext + 22, FTMO + 14, Futures ohne Termin: {e.get('anlegen')}")
check(e.get("anfrage") == ["2026-12-10", "2026-12-09", ""], f"Anfrage: FundedNext + 15, The5%ers + 14, On Demand ohne Termin: {e.get('anfrage')}")
check(e.get("erhalten") == [15, 14, 14], f"Erhalten-Fenster: FundedNext 14 → 15, andere 14: {e.get('erhalten')}")
check(e.get("gerechnet") == ["2026-11-23", "2026-12-05", "2026-11-15", "2026-12-01"],
      f"Waiting-Tabelle ohne Termin (fcfdPayoutAb): FundedNext Start + 22, letzter Payout + 15, FTMO + 14, gesetzter Termin bleibt: {e.get('gerechnet')}")
check(HTML.count("admReceiveTage(") == 3, "Erhalten-Fenster nutzt admReceiveTage an allen drei Vorbelegungen")
check("like '%fundednext%' then 22 else 14" in SQL and "payout_ready_alt + 1" in SQL and "fn1_payout_backup_20261125 b where b.id = a.id" in SQL,
      "SQL: Trigger 22, Bestand +1 gesichert und nie doppelt")
check(SQL.count("a.created_at < timestamptz '2026-11-24 19:00:00+00'") == 2 and SQL.index("-- ── Teil B2") < SQL.index("-- ── Teil A: Trigger")
      and "a.payout_ready_at = b.payout_ready_alt + 1;" in SQL,
      "SQL (Prüfung): Stichtag in Vorschau + Update, erst Bestand dann Trigger, Rückbau nur wo seither nichts Neues steht")
print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
