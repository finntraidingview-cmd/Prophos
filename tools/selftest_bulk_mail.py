#!/usr/bin/env python3
"""Selbsttest BULK-MAIL (23.10.2026, Finn per Screenshot: Popup „Bulk: Accounts anlegen", Vorlage „FundedNext 100k Phase 1" — die
Zugangs-Mail der Firma in „External IDs" ergab DREI Konten (Login, Passwort, Server je eins), im Feld „Zugangsdaten" wurde nichts erkannt).
Geprüft per macOS-jsc an den echten Funktionen aus prophos.html (ohne Netz, ohne Browser):
(A) bulkDashboardParsen: Zugangs-Mails von FundedNext, FundingPips, FTMO (deutsch), The5%ers, Blue Guardian in leicht anderen Formaten
    („Login: 123" in einer Zeile, Label und Wert auf eigenen Zeilen mit „:" dazwischen, deutsche Beschriftungen, mehrere Labels in einer
    Zeile, Server mit Bindestrich / „Server 2") — je Mail-Block GENAU ein Konto (Login = Kennung), Passwort + Server im Block (zugang),
    nie ein Konto aus Passwort/Server/Plattform; mehrere Mails hintereinander = mehrere Konten; Typ leer (Vorlage/Formular gewinnt).
(B) getBulkCreds (Feld „Zugangsdaten"): derselbe Mail-Text → je Login Passwort + Server.
(C) acParseCredBlob (Konto-Popup „Mail reinpasten"): dieselben Mails, Passwort mit „#" nicht mehr abgeschnitten.
(D) Bisherige Erkennung unverändert: eine Kennung je Zeile, Tradeify-Karten, Topstep-Tabelle, FundedNext-Dashboard, Zeilen-Format
    „Login Passwort Server", Werte-Paste ohne Labels — Ergebnis EXAKT wie im Vergleichsstand (git HEAD oder --alt <commit>).
Alle Zugangsdaten sind Platzhalter. Aufruf: python3 tools/selftest_bulk_mail.py [--alt <commit>]
ACHTUNG (D): Ohne --alt wird gegen HEAD verglichen — liegt der Umbau schon auf HEAD, vergleicht das ihn mit sich selbst. Dann --alt 635aba60
(letzter Stand vor dem Umbau) angeben."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def quelle(commit):
    if not commit:
        return open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    return subprocess.run(["git", "-C", WURZEL, "show", f"{commit}:prophos.html"], capture_output=True, text=True, check=True).stdout


def schnitt(src, von, bis):
    i = src.index(von)
    return src[i:src.index(bis, i)]


def js_prog(src, faelle):
    """faelle: [(art, text)] mit art parse | creds | ac → JSON-Liste der Ergebnisse"""
    start = "  const CRED_LBL = {" if "  const CRED_LBL = {" in src else "  function acParseCredBlob(text"
    teile = [
        "var window = {}; var SERVER_FIRMA = ''; function serverForFirm(){ return SERVER_FIRMA }",
        "var bEl = { creds: { value: '' }, firm: { value: '' } };",
        schnitt(src, start, "  const acPasteBlob = document"),
        schnitt(src, "    function getBulkCreds(){", "    function buildName("),
        schnitt(src, "    const BULK_PRAEFIX", "    window._bulkDashboardParsen"),
        "var F = " + json.dumps(faelle) + ";",
        """var R = F.map(function(f){
          if(f[0] === 'parse') return bulkDashboardParsen(f[1]);
          if(f[0] === 'creds'){ bEl.creds.value = f[1]; return getBulkCreds() }
          return acParseCredBlob(f[1]);
        });
        print(JSON.stringify(R));""",
    ]
    return "\n".join(teile)


def lauf(src, faelle):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js_prog(src, faelle))
        pfad = f.name
    try:
        r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(pfad)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("jsc: " + (r.stderr or r.stdout)[:800])
    return json.loads(r.stdout.strip().splitlines()[-1])


# ── Zugangs-Mails (Platzhalter) ─────────────────────────────────────────────────────────────────────────────────────────────
FN = "MT5 Login\n:\n14000001\n\nMT5 Password\n:\nAb#9xYz!q\n\nMT5 Server\n:\nFundedNext-Server2\n\nPlatform\n:\nMT5\n"
FN_ZW = "MT5 Login\u200b\n:\u00a0\n14000002\n\nMT5 Password\n\uff1a\nQq7_test\n\nMT5 Server\n:\nFundedNext-Server 2\n"   # Mail-Kopie mit Null-Breite-Zeichen
FN_GRUSS = "Dear Trader,\nYour FundedNext Stellar 2-Step Challenge is ready.\n\n" + FN
FN_ZWEI = FN + "\n\n" + FN.replace("14000001", "14000009").replace("Ab#9xYz!q", "Zz9!plat").replace("Server2", "Server3")
FP = "Hello,\nyour FundingPips account:\nLogin: 12000001\nPassword: Fp$2abcd\nServer: FundingPips-SIM1\nPlatform: MetaTrader 5\n"
FTMO_DE = "Ihre Zugangsdaten\nKontonummer: 510000001\nPasswort: Pw!2abcd\nInvestor-Passwort: NurLesen9\nServer: FTMO-Demo\nPlattform: MT5\n"
F5 = "Login\n26000001\nPassword\nAbc123!x\nChange Investor Password\nServer\nFivePercentOnline-Real\nPlatform\nMT5\n"
BG = "Blue Guardian — Account Details\nAccount Number: 7000001   Password: Qw#12345   Server: BlueGuardian-Server\nPlatform: MT5\n"
LOGIN_ID = "MT5 Login ID : 9000001\nMT5 Password : pl4tzhalter\nMT5 Server : FundingPips-SIM2\n"

# ── Bisherige Formate (D) ──────────────────────────────────────────────────────────────────────────────────────────────────
ALT = [
    ("parse", "511000001\n511000002\nFTDFYSLX12345678\n"),
    ("parse", "Select Flex Funded 150K\nactive\nFTDFYSLX12345678\nTradovate\nAccount Balance\n$151,234.50\nTrailing Max Drawdown\n$146,000.00\n"
              "Growth 50K\nactive\nTDFYGR87654321\nTradovate\nAccount Balance\n$50,500.00\n"),
    ("parse", "10/20/2026\t150KTC-SKU-V2-123456-7890123\t1234567\t150K Buying Power\t$151,200.00\tactive\tEvaluation\n"
              "10/21/2026\tEXPRESS-V2-000000-00000000\t7654321\t50K Buying Power\t$50,100.00\tactive\tExpress Funded\n"),
    ("parse", "Stellar 2-Step\n$50K\nCHALLENGE • P1\nCurrent Balance\n$50,120.00\nLogin: 15000001\nMT5\n"
              "Stellar 2-Step\n$100K\nFUNDED\nCurrent Balance\n$101,000.00\nLogin: 15000002\nMT5\n"),
    ("parse", "Login 541000001 Server FTMO-Server"),
    ("parse", "APEX1234567\nPAAPEX7654321\n"),
    ("parse", "#511000003, 511000004; 511000005\n"),
    ("creds", "511000001 Pw!abc12 FundingPips-SIM1\n511000002 Pw!abc13 FundingPips-SIM1\n"),
    ("creds", "511000001\tPw!abc12\n"),
    ("creds", "Login: 26000002\nPassword: •••••\nServer: FivePercentOnline-Real\nPlatform: MT5\n"),
    ("ac", "511290000\nAb12cd!\nFundingPips-SIM1\n"),
    ("ac", "Login: 511290001\nPassword: Abc!1234\nInvestor Password: Inv12345\nServer: FTMO-Server3\nMetaTrader 5"),
    ("ac", "Your login: 511290002 password: Abcd1234 server: Demo-Server"),
]


def main():
    args = sys.argv[1:]
    alt = args[args.index("--alt") + 1] if "--alt" in args else "HEAD"
    neu_src = quelle(None)

    # (A) Zugangs-Mails im Feld „External IDs"
    mails = [FN, FN_ZW, FN_GRUSS, FN_ZWEI, FP, FTMO_DE, F5, BG, LOGIN_ID]
    r = lauf(neu_src, [("parse", m) for m in mails])
    erwart = [
        ("FundedNext (Label/„:“/Wert je Zeile)", [("14000001", "Ab#9xYz!q", "FundedNext-Server2")]),
        ("FundedNext mit Null-Breite-Zeichen + breitem Doppelpunkt", [("14000002", "Qq7_test", "FundedNext-Server 2")]),
        ("FundedNext mit Begrüßung davor", [("14000001", "Ab#9xYz!q", "FundedNext-Server2")]),
        ("zwei FundedNext-Mails hintereinander", [("14000001", "Ab#9xYz!q", "FundedNext-Server2"), ("14000009", "Zz9!plat", "FundedNext-Server3")]),
        ("FundingPips („Login: 123“ je Zeile)", [("12000001", "Fp$2abcd", "FundingPips-SIM1")]),
        ("FTMO deutsch (Kontonummer/Passwort, Investor übersprungen)", [("510000001", "Pw!2abcd", "FTMO-Demo")]),
        ("The5%ers-Karte (Label und Wert je Zeile)", [("26000001", "Abc123!x", "FivePercentOnline-Real")]),
        ("Blue Guardian (Account Number, drei Labels in einer Zeile)", [("7000001", "Qw#12345", "BlueGuardian-Server")]),
        ("Login ID mit „ : “", [("9000001", "pl4tzhalter", "FundingPips-SIM2")]),
    ]
    for (name, soll), ist in zip(erwart, r):
        got = [(b["id"], (b.get("zugang") or {}).get("password"), (b.get("zugang") or {}).get("server")) for b in ist]
        check(got == soll, f"(A) {name}: {len(ist)} erkannt → {[(g[0], 'Passwort' if g[1] else '-', g[2]) for g in got]}")
        check(all(not b.get("typ") for b in ist), f"(A) {name}: Typ leer → Vorlage/Formular gewinnt (Phase 1)")
    fn = r[0][0]
    check(fn.get("firma") == "FundedNext" and fn.get("plattform") == "MT5", "(A) FundedNext-Mail: Firma FundedNext (am Server), Plattform MT5")
    werte = {"Ab#9xYz!q", "FundedNext-Server2", "MT5", "Fp$2abcd", "FundingPips-SIM1", "Qw#12345", "BlueGuardian-Server"}
    check(not any(b["id"] in werte for blk in r for b in blk), "(A) nie ein Konto aus Passwort, Server oder Plattform")

    # (B) Feld „Zugangsdaten"
    rc = lauf(neu_src, [("creds", m) for m in mails])
    for (name, soll), ist in zip(erwart, rc):
        got = [(c["login"], c["password"], c["server"]) for c in ist if c]
        check(got == soll, f"(B) Zugangsdaten-Feld · {name}: {[(g[0], 'Passwort' if g[1] else '-', g[2]) for g in got]}")

    # (C) Konto-Popup „Mail reinpasten"
    ra = lauf(neu_src, [("ac", m) for m in mails])
    for (name, soll), ist in zip(erwart, ra):
        check((ist.get("login"), ist.get("password"), ist.get("server")) == soll[0], f"(C) Konto-Popup · {name}: Login/Passwort/Server = erste Mail")

    # (D) bisherige Formate exakt wie vorher
    src_alt = quelle(alt)
    if "const CRED_LBL" in src_alt:
        print(f"Hinweis: Vergleichsstand {alt} enthält den Umbau schon — (D) vergleicht ihn mit sich selbst. --alt 635aba60 nehmen.")
    ra, rn = lauf(src_alt, ALT), lauf(neu_src, ALT)
    for (art, text), a, n in zip(ALT, ra, rn):
        kurz = text.replace("\n", " / ")[:60]
        check(a == n, f"(D) unverändert [{art}] {kurz}" + ("" if a == n else f"\n    vorher {json.dumps(a, ensure_ascii=False)}\n    jetzt  {json.dumps(n, ensure_ascii=False)}"))

    # (E) bewusste Änderung: FundedNext-Zugangskarte OHNE Dashboard-Karte davor („$50K", „CHALLENGE • P1") bekommt keinen Typ mehr
    #     (vorher fest „challenge") — die gewählte Vorlage/das Formular gewinnt („FundedNext 100k Phase 1" → Phase 1). Rest wie vorher.
    karte = "Login\n15000003\nPassword\nAb12cd!x\nChange Investor Password\nServer\nFundedNext-Server 2\n"
    (a,), (n,) = lauf(src_alt, [("parse", karte)]), lauf(neu_src, [("parse", karte)])
    check(len(a) == len(n) == 1 and a[0]["typ"] == "challenge" and n[0]["typ"] == "" and {**a[0], "typ": ""} == n[0],
          "(E) FundedNext-Zugangskarte ohne Dashboard: Typ „challenge“ → leer (Vorlage gewinnt), sonst identisch")

    print("\nALLES GRUEN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
