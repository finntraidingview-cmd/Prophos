#!/usr/bin/env python3
"""Selbsttest BU3 (26.11.2026, Finn: „Das fuckt mich schon ewig ab, so viele Bugs" — Bulk-Fenster einmal gründlich): die ganze Einfüge-Matrix für
das EINE Feld „External IDs" an den echten Funktionen aus prophos.html in macOS-jsc (bulkDashboardParsen, bulkLoginAnker, bulkZugangVoll,
bulkServerZuletzt, bulkIstKarte). Je erkannter Block genau ein Konto mit Login · Server · Passwort; Passwort/Server/Plattform/URL/Beschreibungs-
zeilen nie ein eigenes Konto; Firma je Block (gemischte Karten); mehrere Kennungen je Zeile (Komma, Leerzeichen, Semikolon, Tab).
Alle Zugangsdaten sind Platzhalter. Die Paste-Wege selbst (ClipboardEvent text/plain, echtes Tippen, ⌘V/Strg+V) sind im Stub geprüft.
Aufruf:  python3 tools/selftest_bu3_bulk_matrix.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("bulk_mail", os.path.join(HIER, "selftest_bulk_mail.py"))
BM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BM)
SRC = BM.quelle(None)
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# ── Karten (Platzhalter) ─────────────────────────────────────────────────────────────
def t5(login, pw, srv="FivePercentOnline-Real"):
    return f"Hello,\n\nLogin: {login}\nPassword: {pw}\nServer: {srv}\n"


def ftmo(login, pw, srv="FTMO-Server3"):
    return f"Login: {login}\nPassword: {pw}\nInvestor Password: ro12345\nServer: {srv}\nPlatform: MT5\n"


def gft(login, pw, srv="GoatFunded-Server"):
    return (f"Server\n{srv}\nThis is your trading server name.\nLogin\n{login}\nYour account login ID\nPassword\n{pw}\nYour account password\n"
            "Platform\nhttps://download.mql5.com/cdn/web/goat/mt5/goatfunded5setup.exe\n")


FN = "MT5 Login\n:\n14000001\n\nMT5 Password\n:\nAb#9xYz!q\n\nMT5 Server\n:\nFundedNext-Server 2\n"
FP = "Hello,\nyour FundingPips account:\nLogin: 12000001\nPassword: Fp$2abcd\nServer: FundingPips-SIM1\nPlatform: MetaTrader 5\n"
BG = "Account Number: 7000001   Password: Qw#12345   Server: BlueGuardian-Server\nPlatform: MT5\n"
BG_TAB = "Account ID\t7000002\nPassword\tqwe!RT9\nServer\tBlueGuardian-Server\n"
AUD = "Your MT5 account is ready.\n\nMT5 Login: 31000001\nMaster Password: Au#12abc\nInvestor Password: ro999x\nServer: AudacityCapital-Live\n"

FAELLE = [
    # (Name, Text, erwartet [(id, passwort?, server)], erwartete Firmen oder None)
    ("einzelne ID", "26771591", [("26771591", None, None)], None),
    ("mehrere IDs je Zeile", "26771591\n26771592\n26771593\n", [("26771591", None, None), ("26771592", None, None), ("26771593", None, None)], None),
    ("mehrere IDs mit Komma", "26771591, 26771592, 26771593", [("26771591", None, None), ("26771592", None, None), ("26771593", None, None)], None),
    ("mehrere IDs mit Leerzeichen", "26771591 26771592", [("26771591", None, None), ("26771592", None, None)], None),
    ("mehrere IDs mit Tab + Semikolon", "26771591\t26771592; 26771593", [("26771591", None, None), ("26771592", None, None), ("26771593", None, None)], None),
    ("Leerzeilen zwischen IDs", "\n26771591\n\n\n26771592\n\n", [("26771591", None, None), ("26771592", None, None)], None),
    ("Tradeify-Kennungen mit Komma", "TDFYAB123456, TDFYCD654321", [("TDFYAB123456", None, None), ("TDFYCD654321", None, None)], ["Tradeify", "Tradeify"]),
    ("The5%ers-Karte", t5("26771591", "Ab3x!kQ9z"), [("26771591", "Ab3x!kQ9z", "FivePercentOnline-Real")], ["The5%ers"]),
    ("FTMO-Karte (Investor ignoriert)", ftmo("511448315", "X1y2Z3!"), [("511448315", "X1y2Z3!", "FTMO-Server3")], ["FTMO"]),
    ("FundedNext-Karte („:“ je Zeile)", FN, [("14000001", "Ab#9xYz!q", "FundedNext-Server 2")], ["FundedNext"]),
    ("FundingPips-Karte", FP, [("12000001", "Fp$2abcd", "FundingPips-SIM1")], None),
    ("Blue Guardian (drei Labels in einer Zeile)", BG, [("7000001", "Qw#12345", "BlueGuardian-Server")], None),
    ("Blue Guardian (Tabs)", BG_TAB, [("7000002", "qwe!RT9", "BlueGuardian-Server")], None),
    ("GFT (Server vor Login, Beschreibungszeilen, Platform-URL)", gft("315500000", "Abc!123x"), [("315500000", "Abc!123x", "GoatFunded-Server")], ["Goat Funded Trader"]),
    ("Audacity (Master Password)", AUD, [("31000001", "Au#12abc", "AudacityCapital-Live")], None),
    ("3 × The5%ers hintereinander", t5("26771591", "Pa!1aaaa") + "\n" + t5("26771592", "Pb!2bbbb") + "\n" + t5("26771593", "Pc!3cccc"),
     [("26771591", "Pa!1aaaa", "FivePercentOnline-Real"), ("26771592", "Pb!2bbbb", "FivePercentOnline-Real"), ("26771593", "Pc!3cccc", "FivePercentOnline-Real")], None),
    ("5 × GFT hintereinander (je eigener Server)", "\n".join(gft(f"31550000{i}", f"Pw!{i}xyzq", f"GoatFunded-Server{i}") for i in range(1, 6)),
     [(f"31550000{i}", f"Pw!{i}xyzq", f"GoatFunded-Server{i}") for i in range(1, 6)], None),
    ("gemischt FTMO + The5%ers + GFT", ftmo("511448315", "X1y2Z3!") + "\n" + t5("26771591", "Ab3x!kQ9z") + "\n" + gft("315500000", "Abc!123x"),
     [("511448315", "X1y2Z3!", "FTMO-Server3"), ("26771591", "Ab3x!kQ9z", "FivePercentOnline-Real"), ("315500000", "Abc!123x", "GoatFunded-Server")],
     ["FTMO", "The5%ers", "Goat Funded Trader"]),
    ("gemischt GFT + FTMO", gft("315500000", "Abc!123x") + "\n" + ftmo("511448315", "X1y2Z3!"),
     [("315500000", "Abc!123x", "GoatFunded-Server"), ("511448315", "X1y2Z3!", "FTMO-Server3")], ["Goat Funded Trader", "FTMO"]),
    ("gemischt The5%ers + FundedNext", t5("26771591", "Ab3x!kQ9z") + "\n" + FN,
     [("26771591", "Ab3x!kQ9z", "FivePercentOnline-Real"), ("14000001", "Ab#9xYz!q", "FundedNext-Server 2")], ["The5%ers", "FundedNext"]),
    ("„Login Passwort Server“-Zeilen", "511000001 Pw!abc12 FundingPips-SIM1\n511000002 Pw!abc13 FundingPips-SIM1\n511000003 Pw!abc14 FundingPips-SIM1\n",
     [("511000001", "Pw!abc12", "FundingPips-SIM1"), ("511000002", "Pw!abc13", "FundingPips-SIM1"), ("511000003", "Pw!abc14", "FundingPips-SIM1")], None),
    ("„Login Passwort Server“ mit Tabs", "511000001\tPw!abc12\tFundingPips-SIM1\n511000002\tPw!abc13\tFundingPips-SIM1\n",
     [("511000001", "Pw!abc12", "FundingPips-SIM1"), ("511000002", "Pw!abc13", "FundingPips-SIM1")], None),
]


def main():
    r = BM.lauf(SRC, [("parse", f[1]) for f in FAELLE])
    werte_nie_id = set()
    for (name, text, soll, firmen), ist in zip(FAELLE, r):
        got = [(b["id"], (b.get("zugang") or {}).get("password"), (b.get("zugang") or {}).get("server")) for b in ist]
        check(got == soll, f"{name}: {[(g[0], 'Passwort ✓' if g[1] else '-', g[2]) for g in got]}")   # Passwort nie im Klartext ausgeben
        if firmen is not None:
            check([b.get("firma") for b in ist] == firmen, f"{name}: Firma je Block {[b.get('firma') for b in ist]}")
        for s in soll:
            if s[1]:
                werte_nie_id.add(s[1])
            if s[2]:
                werte_nie_id.add(s[2])
    check(not any(b["id"] in werte_nie_id for blk in r for b in blk), "nie ein Konto aus Passwort oder Server")
    check(not any("http" in b["id"] or b["id"].lower() in ("mt5", "platform") for blk in r for b in blk), "nie ein Konto aus Platform/URL")

    # bulkIstKarte (Umleitung aus der Passwort-/Server-Zeile) echt in jsc
    i = SRC.index("    function bulkIstKarte(t){")
    j = SRC.index("    }\n", i) + 6
    faelle = [["GoatFunded-Server", False], ["FivePercentOnline-Real", False], ["Abc!123x", False], ["Server: GoatFunded-Server", False],
              ["Login: 315500000", True], ["MT5 Login 315500000", True], ["Account ID: 7000001", True], ["a\nb", True],
              ["511000001 Pw!abc12 FundingPips-SIM1", True], ["", False]]
    js = SRC[i:j] + "\nvar F = " + json.dumps(faelle) + ";\nprint(JSON.stringify(F.map(function(f){ return bulkIstKarte(f[0]) === f[1] })));\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        pfad = f.name
    try:
        out = subprocess.run([BM.JSC, pfad], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(pfad)
    erg = json.loads(out.stdout.strip() or "[]")
    for (txt, soll), ok in zip(faelle, erg):
        check(ok, f"Einfügen in Passwort-/Server-Zeile: {txt[:30]!r} → {'umleiten' if soll else 'normal einfügen'}")

    # Felder immer editierbar: kein readonly/disabled/preventDefault ohne eigenes Einfügen am Feld „External IDs" und an den Zeilen
    blk = SRC[SRC.index("function bulkCredZeilenRender(){"):SRC.index("function bulkCredsAuswerten(){")]
    check("readonly" not in blk.lower() and "disabled" not in blk, "Zeilen (Passwort/Server) nie readonly/disabled")
    check("if(bulkIstKarte(t)){ e.preventDefault(); bulkInsEineFeld(t); return }" in blk and "if(lbl){ e.preventDefault(); i.value = lbl[1]" in blk,
          "preventDefault in den Zeilen nur mit eigenem Einfügen (umleiten bzw. Wert setzen)")
    feld = SRC[SRC.index('id="bulk-extids"') - 80:SRC.index('id="bulk-extids"') + 400]
    check("readonly" not in feld and "disabled" not in feld, "Feld „External IDs“ ohne readonly/disabled")
    check("bpEl.box?.addEventListener('paste'" not in SRC and "bEl.extids?.addEventListener('paste'" not in SRC, "kein Paste-Abfangen am Feld „External IDs“")
    blk5 = SRC[SRC.index("function bulkPasteVorlage(x){"):SRC.index("const bulkPaste = {")]
    check("if(x.firma && a.firm && x.firma !== a.firm){" in blk5 and "return l3.length === 1 ? l3[0] : l2.length === 1 ? l2[0] : l.length === 1 ? l[0] : null" in blk5,
          "gemischte Karten: Block einer anderen Firma bekommt die passende Vorlage DIESER Firma (nie die oben gewählte)")
    check("function bulkFehltHinweis(x, firma)" in SRC and "Passwort fehlt — unten eintragen" in SRC and "ohne erkannten Login — Login-Zeile prüfen" in SRC,
          "Fehlendes ruhig benannt (Passwort/Server je Block, Passwörter ohne Login)")

    print("\nALLES GRUEN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
