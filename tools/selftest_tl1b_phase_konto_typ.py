#!/usr/bin/env python3
"""Selbsttest TL1b — Nachzug zu TL1 (Prüfer S2 KANN, Master 12.11.2026):
(1) ap_kette_mll_belegt fail-closed: eine Zeile OHNE konto_typ zählt nur ab dem Phasenbeginn (erster Plan der aktuellen Phase nach dem letzten Plan eines
    anderen Typs); ohne Plan der aktuellen Phase zählt keine. Quelle des fehlenden konto_typ (Plan 272809d8, 09.11.: von Hand abgeschlossen) → Kettenpläne
    tragen ihn ab dem Anlegen (Trade 1 in ap_planen, Trade 2 in ap_kette_tick, Teile in tt_tick).
(2) prophos.html tsxBaselineAusOrder: mll_start nur, wenn das gelesene Konto (r.konto_aktiv) zum Plan passt — dieselbe Prüfung wie die Balance-Lesung.

Aufruf:  python3 tools/selftest_tl1b_phase_konto_typ.py      (ohne Netz, Platzhalter-IDs, echte Funktionen aus app.py)"""
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


K = "00000000-0000-0000-0000-00000000bb01"
ACC = {"id": K, "account_type": "challenge"}
MB = app.ap_kette_mll_belegt
JETZT = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)


def z(start, ende, bal_end, mll=None, typ="challenge"):
    return {"master_account_id": K, "konto_typ": typ, "started_at": start, "ended_at": ende, "bal_end": bal_end, "mll_start": mll}


print("1) Zeilen ohne konto_typ nur ab dem Phasenbeginn")
MARC = [z("2026-11-05T16:36:05Z", "2026-11-05T16:38:00Z", 152592.44, 145500),
        z("2026-11-06T10:37:46Z", "2026-11-06T11:41:00Z", 157087.32, 148092.44),
        z("2026-11-09T13:33:34Z", "2026-11-09T15:10:59Z", 154087.32, 150000, typ=None)]
m, q = MB(150000, 4500, ACC, MARC, jetzt=JETZT)
check(m == 150000.0 and "09.11." in q, f"Marc: Zeile ohne konto_typ nach dem Phasenbeginn (05.11.) zählt — {m} · {q}")
ALT = [z("2026-11-01T10:00:00Z", "2026-11-01T11:00:00Z", 1500.0, 0, typ="funded"),
       z("2026-11-02T10:00:00Z", "2026-11-02T11:00:00Z", 149000.0, 147777, typ=None),     # VOR dem Phasenbeginn (alte Phase) → zählt nicht
       z("2026-11-03T10:00:00Z", "2026-11-03T11:00:00Z", 151000.0, 145500),               # Phasenbeginn
       z("2026-11-04T10:00:00Z", "2026-11-04T11:00:00Z", 151200.0, 146600, typ=None)]     # nach dem Phasenbeginn → zählt
ma, qa = MB(150000, 4500, ACC, ALT, jetzt=JETZT)
check(ma == 146700.0 or (ma == 146600.0 and "04.11." in qa), f"nach dem Phasenwechsel: Lesung 04.11. (ohne Typ, nach Beginn) zählt — {ma} · {qa}")
mb, qb = MB(150000, 4500, ACC, ALT[:3], jetzt=JETZT)
check("02.11." not in str(qb) and mb != 147777.0, f"Zeile ohne konto_typ VOR dem Phasenbeginn (alte Phase) zählt nicht — {mb} · {qb}")
NUR = [z("2026-11-05T10:00:00Z", "2026-11-05T11:00:00Z", 156000.0, 149000, typ=None)]
mn, qn = MB(150000, 4500, ACC, NUR, jetzt=JETZT)
check(mn != 149000.0 and not str(qn).startswith("TopstepX-Lesung") and "Tagesschluss" not in str(qn),
      f"ohne Plan der aktuellen Phase zählt keine Zeile ohne konto_typ (fail-closed, Rückfall wie ohne Daten) — {mn} · {qn}")
mf, qf = MB(150000, 4500, ACC, [dict(MARC[0]), dict(MARC[1]), dict(MARC[2], konto_typ="funded")], jetzt=JETZT)
check(mf == 150000.0 and "09.11." not in qf, "eine Zeile mit ANDEREM Typ zählt nie (der Lock hält trotzdem)")

print("2) konto_typ ab dem Anlegen (Quelle Plan 272809d8: von Hand abgeschlossen, nie abgehakt)")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check('"konto_typ": (a.get("account_type") or None) if w.get("kette") else None,' in src, "ap_planen: Ketten-Trade 1 trägt den Kontotyp (andere Pläne wie bisher, Schlüssel einheitlich)")
check('"konto_typ": t1.get("konto_typ") or "challenge",' in src and '"planned_for,status,konto_typ,mt5_baseline", "route": "eq.tsv2"' in src,
      "ap_kette_tick: Trade 2 erbt konto_typ von Trade 1 (Select liest ihn), sonst challenge")
check('"konto_typ": (p.get("konto_typ") or "challenge") if p.get("route") == "tsv2" else None,' in src, "tt_tick: nur Topstep-Teile (tsv2) erben konto_typ, CFD-Tagesteilung bleibt NULL (Prüfer S2 SOLLTE 1)")
z_src = src[src.index("def _tt_zeile("):src.index("def _tt_takt(")]
check('"konto_typ"' in z_src, "_tt_zeile setzt konto_typ")

print("3) Frontend: MLL nur vom passenden Konto")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
tb = html[html.index("  function tsxBaselineAusOrder("):html.index("  function tsxBaselineAusOrder(") + 6000]
check("tvBalanceKontoBelegt(r && r.konto_aktiv, plan.masterAccountId, zahl(r.balance_start))) ? zahl(r.mll) : null" in tb and "mll_start: zahl(r.mll)," not in tb,
      "tsxBaselineAusOrder: mll_start nur, wenn r.konto_aktiv zum Plan passt (wie die Balance-Lesung)")
check("function tvBalanceKontoBelegt(kontoText, accountId, balance, konten)" in html, "dieselbe Prüfung wie tvKontoBalanceSchreiben")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER")
    sys.exit(1)
print("alles grün")
