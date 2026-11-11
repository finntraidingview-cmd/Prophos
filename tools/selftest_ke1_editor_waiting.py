#!/usr/bin/env python3
"""Selbsttest KE1 (Master 11.11.2026, Fund S3 aus FT2): der Konto-Editor (Accounts → Stift, saveAccount) schrieb waiting_payout_since bei jedem Speichern eines
Nicht-CFD-Kontos (Winning Days, Funded, Challenge) auf null. Jetzt nur bei eigener Änderung (Neu-Anlegen, sichtbarer Haken umgestellt, Typ weg von Funded CFD),
sonst wird das Feld nicht gesendet. Rechnet die echten Zeilen aus prophos.html mit jsc (ohne DB).
Aufruf:  python3 tools/selftest_ke1_editor_waiting.py"""
import os
import json
import subprocess
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


i = html.index("    const wpVorher = vorher?.waitingPayoutSince || null")
j = html.index("\n", html.index("    const wartetPayoutVal = ", i))
kern = html[i:j]
js = """
function fall(isEdit, type, vorher, haken, sichtbar, start){
  const accEls = { wartetPayout: { checked: haken, dataset: { start: start != null ? start : (vorher && vorher.waitingPayoutSince ? '1' : '0') } }, wartetPayoutRow: { hidden: !sichtbar } }
""" + kern + """
  return { schreiben: wartetSchreiben, wert: wartetPayoutVal }
}
const T = '2026-11-10T08:00:00.000Z'
const r = {
  wd_server: fall(true, 'winning_days', { type: 'winning_days', waitingPayoutSince: T }, false, false),
  wd_leer: fall(true, 'winning_days', { type: 'winning_days', waitingPayoutSince: null }, false, false),
  fut_server: fall(true, 'funded', { type: 'funded', waitingPayoutSince: T }, false, false),
  cfd_gleich_an: fall(true, 'funded_cfd', { type: 'funded_cfd', waitingPayoutSince: T }, true, true),
  cfd_gleich_aus: fall(true, 'funded_cfd', { type: 'funded_cfd', waitingPayoutSince: null }, false, true),
  cfd_aus: fall(true, 'funded_cfd', { type: 'funded_cfd', waitingPayoutSince: T }, false, true),
  cfd_an: fall(true, 'funded_cfd', { type: 'funded_cfd', waitingPayoutSince: null }, true, true),
  neu_cfd: fall(false, 'funded_cfd', null, true, true),
  neu_wd: fall(false, 'winning_days', null, false, false),
  typ_weg: fall(true, 'live', { type: 'funded_cfd', waitingPayoutSince: T }, false, false),
  neu_geladen: fall(true, 'funded_cfd', { type: 'funded_cfd', waitingPayoutSince: T }, false, true, '0'),   // Server setzte Waiting, während der Editor offen war
}
print(JSON.stringify(r))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
rr = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
e = json.loads(rr.stdout.strip().splitlines()[-1]) if rr.returncode == 0 and rr.stdout.strip() else {}
if not e:
    print(rr.stdout, rr.stderr)
T = "2026-11-10T08:00:00.000Z"
g = lambda k: e.get(k) or {}
check(g("wd_server") == {"schreiben": False, "wert": T}, f"1 Winning Days mit Server-Waiting: Feld nicht senden, Wert bleibt ({g('wd_server')})")
check(g("wd_leer").get("schreiben") is False, "2 Winning Days ohne Waiting: nichts senden")
check(g("fut_server") == {"schreiben": False, "wert": T}, "3 Funded Futures mit Waiting: bleibt")
check(g("cfd_gleich_an") == {"schreiben": False, "wert": T} and g("cfd_gleich_aus").get("schreiben") is False, "4 Funded CFD, Haken unverändert: nichts senden")
check(g("cfd_aus") == {"schreiben": True, "wert": None}, "5 Funded CFD, Haken ab: leeren")
check(g("cfd_an").get("schreiben") is True and str(g("cfd_an").get("wert") or "").startswith("20"), "6 Funded CFD, Haken an: jetzt")
check(g("neu_cfd").get("schreiben") is True and g("neu_cfd").get("wert") and g("neu_wd") == {"schreiben": True, "wert": None}, "7 neu angelegt: wie bisher")
check(g("typ_weg") == {"schreiben": True, "wert": None}, "8 Typ weg von Funded CFD: leeren wie bisher")
check(g("neu_geladen") == {"schreiben": False, "wert": T}, "8b Konten neu geladen, während der Editor offen war: unberührter Haken schreibt nichts (Prüfer)")
check("...(wartetSchreiben ? { waiting_payout_since: acc.waitingPayoutSince } : {})" in html, "9 Update sendet waiting_payout_since nur bei eigener Änderung")
check(html.count("waiting_payout_since: acc.waitingPayoutSince,") == 0, "10 kein unbedingtes waiting_payout_since mehr im Update")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
