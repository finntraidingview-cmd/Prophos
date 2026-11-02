#!/usr/bin/env python3
"""Selbsttest Abhaken ohne unnötiges Popup + Rechte-Toast (Finn 02.11.2026 ~19:30, Moritz Tradeify …9553, Plan 955c18be).

1. Planer-Gate in /admin/wd-plaene: eigene Pläne abhaken (erledigt, vormerken, manuell …) bleibt frei, fremde nicht (wd_plan_eigen).
2. wdlEinKlickGrund (prophos.html): echte Puls-Lesung am TP schlägt „demo_liq“, Funded nur am TP — läuft im Browser über die Test-Haken
   window._wdlEinKlickGrund / window._wdlLesungAmTp (02.11.2026 geprüft: Moritz → kein Popup; echter Blow, ohne Lesung, P&L-Widerspruch,
   Konto weg → Popup; Funded −8,90/111 $ → kein Popup, Funded am TP → Popup); hier nur die Verdrahtung.

Aufruf:  python3 tools/selftest_einklick_rechte.py"""
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {}
for name in ("WD_ABHAK_EIGEN", "wd_plan_eigen"):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?$", app, re.M)
    exec(m.group(0), ns)
PLAENE = {"955c18be-d35d-4791-abde-b10656ee0dcd": "aff98e60", "fremd000-0000-0000-0000-000000000000": "anders00"}
ns["sb_select"] = lambda tab, q: [{"user_id": PLAENE[q["id"][3:]]}] if q["id"][3:] in PLAENE else []
eigen = ns["wd_plan_eigen"]
check(eigen("aff98e60", "955c18be-d35d-4791-abde-b10656ee0dcd") is True, "eigener Plan → frei")
check(eigen("aff98e60", "fremd000-0000-0000-0000-000000000000") is False, "fremder Plan → Gate bleibt")
check(eigen(None, "955c18be-d35d-4791-abde-b10656ee0dcd") is False and eigen("aff98e60", "") is False, "ohne Login oder Plan-ID → Gate bleibt")
ns["sb_select"] = lambda tab, q: (_ for _ in ()).throw(RuntimeError("DB weg"))
check(eigen("aff98e60", "955c18be-d35d-4791-abde-b10656ee0dcd") is False, "DB nicht lesbar → Gate bleibt (fail-safe)")
check("erledigt" in ns["WD_ABHAK_EIGEN"] and "hand" not in ns["WD_ABHAK_EIGEN"], "Abhak-Wege in der Ausnahme, Hand-Bearbeiten nicht")
check("_akt in WD_ABHAK_EIGEN and wd_plan_eigen(_wd_login_uid_still()" in app and "_gs[1] == 403" in app, "Gate in /admin/wd-plaene nutzt die Ausnahme nur bei 403")
check('msg += f" (angemeldet: {_nm})"' in app, "Rechte-Toast nennt die angemeldete ID")

check("function wdlLesungAmTp(t)" in html and "!wdlLesungAmTp(t))) return 'Blow-Beweis oder unklares Ende'" in html, "demo_liq/beide/unklar nur ohne Lesung am TP")
check("['tsx_geblowt', 'demo_konto_weg', 'demo_konto_unklar', 'konto_weg'].includes" in html, "Konto weg / TopstepX-Blow bleiben immer Popup")
check("&& !wdlLesungAmTp(t)) return 'Demo an der Liq, Lesung ohne Blow'" in html, "„Demo an der Liq“ entfällt bei Lesung am TP")
check("if(typ === 'funded' && (!zahl(t.pl_balance) || (Number(t.pl_balance) > 0" in html, "Funded: Popup nur am TP oder ohne Lesung")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
