"""Selbsttest BU1 (26.11.2026): Bulk-Fenster „Zugangsdaten (optional)" versteht Zugangskarten aus Firmen-Mail/Dashboard (Beschriftung je Zeile oder
„Label: Wert", mehrere Konten, Tabs/Leerzeilen, deutsch/englisch, Investor-Passwort ignoriert), übernimmt erkannte Logins als External IDs, zeigt was
erkannt wurde (Passwort nie im Klartext) bzw. einen Hinweis aufs Format. Prüft die Login-Label-Regel (CRED_LBL.login) echt in JavaScriptCore und die
Verdrahtung im Quelltext. Die Gesamt-Erkennung (bulkLoginAnker/getBulkCreds) ist im Stub mit The5ers-, FTMO-, FundedNext-, Blue-Guardian-Stil geprüft.

Aufruf:  python3 tools/selftest_bu1_zugangsdaten.py
"""
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
n = 0


def check(ok, text):
    global n
    if not ok:
        print("✗", text)
        sys.exit(1)
    n += 1
    print("✓", text)


# ── 1. Login-Labels echt in JSC ──
i = HTML.index("  const CRED_LBL = {")
j = HTML.index("  }\n", i) + 4
k = HTML.index("  const CRED_NIE = ")
k2 = HTML.index("\n", k)
js = HTML[i:j] + HTML[k:k2] + """
var faelle = [["Login", true], ["Login: 26771591", true], ["MT5 Login", true], ["Account ID", true], ["Account Number: 7001", true], ["MT5 ID", true],
  ["ID", true], ["ID: 55667788", true], ["Konto-ID: 88990011", true], ["Kontonummer", true], ["Password", false], ["Server: FTMO-Server3", false],
  ["Investor Password: x", false], ["Order ID 5", false]];
var aus = faelle.map(function(f){ var m = CRED_LBL.login.test(f[0]) && !CRED_NIE.test(f[0]); return f[0] + "=" + (m === f[1] ? "ok" : "FALSCH") });
print(JSON.stringify(aus));
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True)
os.unlink(pfad)
check(r.returncode == 0, f"jsc läuft ({(r.stderr or '')[:200]})")
erg = eval(r.stdout.strip())
for e in erg:
    check(e.endswith("=ok"), f"Login-Label: {e}")

# ── 2. Verdrahtung ──
check("function bulkCredsAuswerten()" in HTML and "bEl.extids.dispatchEvent(new Event('input', { bubbles: true }))" in HTML,
      "erkannte Logins → Feld „External IDs“ (Zeilen je Kennung bauen sich darüber)")
check(re.search(r"filter\(l => !da\.has\(l\.toUpperCase\(\)\)\)", HTML) is not None, "bestehende External IDs bleiben, nur fehlende werden angehängt")
check("Passwort ${c.password ? '✓' : 'fehlt'}" in HTML, "Status zeigt Passwort nur als ✓/fehlt, nie im Klartext")
check("Nicht erkannt. Erwartet je Konto:" in HTML and 'id="bulk-creds-status"' in HTML, "nichts erkannt → Hinweis aufs erwartete Format")
blk = HTML[HTML.index("function bulkCredsAuswerten()"):HTML.index("window._bulkCredsTest")]
check("console." not in blk and "Toast" not in blk and "showSyncBanner" not in blk, "keine Konsole/Toasts im Auswerte-Weg (Passwörter nie im Log)")
check("(zeigen || (bEl.creds?.value || '').trim()) ? '' : 'none'" in HTML, "eingefügte Zugangsdaten werden nie weggeblendet")
check("bulkCredsAuswerten.t = setTimeout(" in HTML, "Auswertung entprellt beim Tippen/Einfügen")

print(f"\n{n} Prüfungen grün")
