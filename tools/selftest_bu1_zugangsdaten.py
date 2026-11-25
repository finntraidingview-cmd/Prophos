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

# ── 3. BU1b (26.11.2026): EIN Einfügefeld + gewählte Vorlage auf der Karte ──
check('id="bulk-creds" hidden style="display:none"' in HTML, "eigenes Zugangskarten-Feld ist aus — nur noch das Feld „External IDs“")
check("Zugangskarte/Mail (Login / Password / Server, auch mehrere Konten)" in HTML, "Platzhalter von „External IDs“ nennt die Zugangskarte")
check("if(bulkIstKarte(t)){ e.preventDefault(); bulkInsEineFeld(t); return }" in HTML, "ganze Karte in eine Passwort-/Server-Zeile → ins Feld „External IDs“ umgeleitet")
blk2 = HTML[HTML.index("function bulkInsEineFeld(t){"):HTML.index("window._bulkCredsTest")]
check("altZeilen.every(z => neu.toUpperCase().includes(" in blk2 and "console." not in blk2, "reine Kennungen, die in der Karte stehen, werden ersetzt; kein Log")
blk3 = HTML[HTML.index("function bulkPasteVorlage(x){"):HTML.index("const bulkPaste = {")]
check("if(!a || px) return null" in blk3 and "x.firma !== a.firm" in blk3 and "gr !== ga" in blk3 and blk3.rstrip().endswith("return a\n    }"),
      "oben gewählte Vorlage gilt für MT5-Logins ohne Präfix — nicht bei anderer Firma/Größe/Präfix-Vorlage")
# istKarte echt in JSC
i = HTML.index("    function bulkIstKarte(t){")
j = HTML.index("    }\n", i) + 6
js2 = HTML[i:j] + """
var f = [["Geheim!123", false], ["FivePercentOnline-Real", false], ["Login: 1234", true], ["a\\nb", true], ["26771591 Ab3x FivePercentOnline-Real", true], ["", false], ["GoatFunded-Server", false], ["Server: GoatFunded-Server", false], ["MT5 Login 315500000", true], ["Account ID: 7001234", true]];
print(JSON.stringify(f.map(function(x){ return bulkIstKarte(x[0]) === x[1] ? "ok" : "FALSCH:" + x[0] })));
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js2)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True)
os.unlink(pfad)
check(r.returncode == 0 and all(e == "ok" for e in eval(r.stdout.strip())), f"bulkIstKarte: einzelnes Passwort/Server bleibt Eingabe, Karte/Zeile wird umgeleitet ({r.stdout.strip()[:120]})")

# ── 4. BU2 (26.11.2026): GFT-Karte „Server / GoatFunded-Server / This is your trading server name. / Login / … / Password / … / Platform / URL" ──
blk4 = HTML[HTML.index("function bulkDashboardParsen(text){"):HTML.index("window._bulkDashboardParsen = bulkDashboardParsen")]
check("const davor = bulkZugangLesen(roh.slice(k > 0 ? fnTreffer[k - 1].ende : 0, m.index))" in blk4 and "if(!(bulkZugangLesen(roh.slice(m.ende, bisNaechster)) || {}).server){" in blk4,
      "Server VOR dem Login (GFT) wird genommen, wenn dahinter keiner steht — beschriftet, seit dem vorigen Konto")
check("if(lbl){ e.preventDefault(); i.value = lbl[1]; i.dataset.hand = '1' }" in HTML, "„Server: X“ / „Password: x“ einzeln eingefügt → nur der Wert ins Feld")
check("const fokus = fe && fe.closest('[data-bcr]')" in HTML and "el.focus(); try{ el.setSelectionRange(fokus.a, fokus.b) }catch(_){}" in HTML,
      "Zeilen-Neubau behält Fokus + Cursor (Server-/Passwort-Feld bleibt beim Tippen bedienbar)")
check("pw = a.pw || zg.password || t.password || '', srv = a.srv || zg.server || t.server || std" in HTML and "serverForFirm(bEl.firm?.value.trim())" in HTML,
      "fehlt der Server → aus firm_specs der Firma (serverForFirm) vorausgefüllt")

print(f"\n{n} Prüfungen grün")
