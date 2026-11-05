#!/usr/bin/env python3
"""Selbsttest SA1 (05.11.2026, offene Prüfer-Hinweise aus berichte/2026-11-05_NK1.md (c)). Je Punkt ein Block; ohne Netz.
Aufruf: python3 tools/selftest_sa1.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


def block(name, n=2500):
    i = HTML.find(name)
    return HTML[i:i + n] if i >= 0 else ""


# ── #1 Claim-Guard auf die Startzeit der Kopie ──
f = block("  async function suClaimSetzen(planId, art, guard, startUm){", 900)
ok("if(startUm !== undefined) q = startUm ? q.eq('start_um', startUm) : q.is('start_um', null)" in f,
   "#1 suClaimSetzen: mit startUm nur genau diese Startzeit (null → start_um is null)")
for marke in ("'verbrauch' : 'start', true, plan.startUm || null)",                       # Start / verpasst nach Fenster
              "'verbrauch', true, plan.startUm || null)   // Verbrauch: verpasst",          # verpasst nach Vorprüfung
              "'verbrauch', false, plan.startUm || null)   // Verbrauch: nie in der Pause",  # Index-Pause aufgegeben
              "'verbrauch', false, plan.startUm || null)   // Verbrauch: Riegel hat aufgegeben"):
    ok(marke in HTML, f"#1 zeitabhängiger Claim mit Startzeit: {marke[:48]}…")
for marke in ("'verbrauch', false)   // Verbrauch: nie starten", "'verbrauch', false)   // Verbrauch: Manuelle Arbeit",
              "'verbrauch', false)   // Verbrauch: Ziel erreicht"):
    ok(marke in HTML, f"#1 Verbrauch ohne Uhrzeit-Bezug bleibt ohne Zeit-Guard: {marke[22:58]}…")
ok(len(re.findall(r"suClaimSetzen\(", HTML)) == 8, "#1 genau 7 Aufrufer + Definition (kein neuer Claim-Weg ohne Entscheidung)")

# ── #4 WD: Payout offen beim Anlegen nur aus der frischen Zeile + Server-Prüfung ──
i = HTML.find("async function wdPlaeneAnlegen(")
blk = HTML[i:HTML.find("// 2) Ein Aufruf", i)]
ok("if(k.hinweis === WD_HINWEIS_PAYOUT){ k.aktiv = false; delete k.nach_start; ge = true; continue }" in blk
   and "wdKontoPayoutOffen(" not in blk and "_wd.payoutOffen" not in blk, "#4 wdPlaeneAnlegen: nur Zeilen-Hinweis, kein alter Mac-/PC-Stand")
APP = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
j = APP.find("# PAYOUT OFFEN (R2c, 05.11.2026")
ok(j > 0 and 'if mid in po_offen:' in APP[j:j + 4000] and '"grund": WD_HINWEIS_PAYOUT' in APP[j:j + 4000],
   "#4 POST /admin/wd-plaene prüft pending_payouts frisch und gibt WD_HINWEIS_PAYOUT als Grund zurück")
ok("if(rein && wdKontoPayoutOffen(k)) return wdSay(" in HTML, "#4 Hand-Weg „heute rein“ behält die strenge Prüfung (sicher in die richtige Richtung)")

if __name__ == "__main__":
    print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
    sys.exit(1 if FEHLER else 0)
