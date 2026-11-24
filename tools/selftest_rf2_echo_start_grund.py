#!/usr/bin/env python3
"""Selbsttest RF2 (24.11.2026, Befund RF1): der Echo-Start meldet seinen Ausstiegs-Grund.
(1) tpPreflightMt5 liest die Startzeit-Marke _rkTickStart VOR dem ersten await (vorher erst nach tpLotsDeckelFrisch — tpStartUmTick hatte sie
    da schon gelöscht, sfEinmal meldete nie; alle Echo-Fehlstarts des Tages trugen nur „m5still").
(2) jeder frühe Ausstieg in tpJetztStarten / tpPreflightMt5 / Takt-Ausnahme merkt sich seinen Grund (sfAusstiegHier).
(3) sfStillUrteil hängt Ausstiegs-Grund und Vorflug-Grund HINTEN an; Schlüssel-Texte vorne und das Urteil (unklar) bleiben.
(4) sfVorflugText / sfStillUrteil laufen echt (JavaScriptCore über osascript, macOS) mit gestellten Plänen.
Aufruf: python3 tools/selftest_rf2_echo_start_grund.py"""
import json
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def stueck(html, von, bis):
    a = html.index(von)
    return html[a:html.index(bis, a)]


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()

    # ── (1) Marke vor dem ersten await ──
    pf = stueck(html, "async function tpPreflightMt5(plan){", "\n  }\n")
    # nur Code-Zeilen (Kommentare nennen „await“ und die alte Zeile wörtlich)
    pf_code = "\n".join(z for z in pf.split("\n") if not z.strip().startswith("//"))
    i_marke = pf_code.find("const vonTick = _rkTickStart.delete(String(plan.id))")
    i_await = pf_code.find("await ")
    check(i_marke > 0 and i_await > 0 and i_marke < i_await, "tpPreflightMt5: vonTick vor dem ersten await gelesen")
    check(pf_code.count("_rkTickStart.delete(") == 1 and pf_code.count("const vonTick") == 1, "tpPreflightMt5: Marke genau einmal gelesen, vonTick genau einmal")
    check("if(!vonTick || sfSchon) return" in pf, "sfEinmal meldet weiter nur bei Start zur Startzeit, genau einmal")
    tj = stueck(html, "async function tpJetztStarten(planId, opts){", "\n  }\n")
    check("tpPreflightMt5(plan)\n" in tj and "await tpPreflightMt5" not in tj,
          "tpJetztStarten ruft den Check weiter ohne await (Grund der Reihenfolge-Falle, darum die Marke vorn)")
    tick = stueck(html, "await tpJetztStarten(plan.id); _rkTickStart.delete(String(plan.id)) }", "finally{")
    check("sfAusstiegHier(plan.id, 'Fehler im Start-Ablauf: '" in tick and "_rkTickStart.delete(String(plan.id)); sfAusstiegHier" in tick,
          "Takt-Ausnahme: Marke weg (leckt nicht in Hand-Starts) + Grund gemerkt")

    # ── (2) jeder frühe Ausstieg in tpJetztStarten mit Grund ──
    rets = [z for z in tj.split("\n") if "return" in z and "tpV2Nacheinander" not in z and "_rsQueueAdd" not in z]
    ohne = [z.strip()[:90] for z in rets if "sfAusstiegHier" not in z and "return\n" not in z and z.strip() != "return"]
    check(not ohne, "tpJetztStarten: jede return-Zeile mit sfAusstiegHier" + (f" — ohne: {ohne}" if ohne else ""))
    check("sfAusstiegHier(plan.id, 'für den Start fehlt: '" in tj and "sfAusstiegHier(plan.id, sperre.text)" in tj
          and "const _fa = await faVorStart(plan); if(_fa){ sfAusstiegHier(plan.id, _fa); return }" in tj,
          "Sperre, Firmen-Abstand, fehlende Werte: Grund = derselbe Text wie im Toast")
    check(pf.count("sfAusstiegHier(plan.id,") == 2, "tpPreflightMt5: Wochenende + Lots-Deckel merken den Grund")

    # ── (3) Texte: Schlüssel vorne unverändert, Zusätze hinten ──
    u = stueck(html, "function sfStillUrteil(", "\n  }\n")
    check("der Start endete in diesem Tab ohne Ergebnis, bevor etwas an ${p.route === 'mt5' || p.route === 'mt5v2' ? 'den Bot' : 'Puls'} ging — nichts gesendet.${ausZ}${vfZ}` }" in u,
          "„endete in diesem Tab ohne Ergebnis … nichts gesendet.“ + Grund + Vorflug hinten")
    check("Master-Konto ${masterFlach === false ? 'NICHT flach' : 'nicht lesbar'} → im Master-Terminal prüfen, ob eine Order liegt.${vfZ}${tabZ}` }" in u,
          "„Master-Konto nicht lesbar → …“ + Vorflug vor dem Tab-Zustand")
    check("const vfZ = spNach ? '' : sfVorflugText(p, claim)" in u and "Number(hier.ausstieg.at) >= claim - 5000 && Number(hier.ausstieg.at) <= claim + 3 * 60000" in u,
          "Vorflug nur ohne Order-Antwort, Ausstieg nur kurz nach diesem Claim (≤ 3 min)")
    check(u.count("return { unklar: false") == 3 and u.count("return { unklar: true") == 2, "Urteile unverändert (3× nichts gesendet, 2× unklar)")

    # ── (4) echt laufen lassen (JavaScriptCore) ──
    if sys.platform != "darwin":
        print("(JavaScriptCore-Teil übersprungen: nur macOS)")
    else:
        teile = [stueck(html, "function sfAusstiegHier(id, grund){", "\n  }\n") + "\n  }",
                 stueck(html, "function sfVorflugText(p, claim){", "\n  }\n") + "\n  }",
                 stueck(html, "function sfHier(id){", "\n  }\n") + "\n  }",
                 u + "\n  }"]
        claim = 1764000000000          # fest, damit die Uhrzeiten stabil sind
        js = ("var window = {}; var SF_STILL_ROUTEN = ['mt5','mt5v2','tvv2','tsv2'], SF_STILL_FREMD_MS = 600000, SF_STILL_MS = 240000;\n"
              "function sfFlag(p){ return p.mt5Baseline && p.mt5Baseline.start_fehler || null }\n"
              "function sfVorOrderBeleg(m){ return /nichts gesendet|nichts platziert/i.test(String(m||'')) }\n"
              "function sfTabZustandText(){ return ' [Tab: x]' }\n"
              "function pulsPlattform(){ return 'TradingView' }\n"
              + "\n".join(teile) + "\n"
              f"var C = {claim};\n"
              "function iso(ms){ return new Date(ms).toISOString() }\n"
              "var vf = { a: { at: iso(C - 14*60000), lesbar: false, grund: 'Master-Terminal läuft nicht — nicht gelesen (wird nicht gestartet)' },\n"
              "           b: { at: iso(C - 3*60000),  lesbar: false, grund: 'Vorflug nach dem Vorwärmen bis T−60 s nicht gelaufen (PC oder Instanz belegt)' } };\n"
              "var p = { id: 'p1', route: 'mt5', status: 'planned', startUmGestartetAt: iso(C), mt5Baseline: { vorflug: vf } };\n"
              "var out = {};\n"
              "out.vf = sfVorflugText(p, C);\n"
              "out.vf_alt = sfVorflugText({ mt5Baseline: { vorflug: { a: { at: iso(C - 3*3600000), lesbar: false, grund: 'alt' } } } }, C);\n"
              "out.vf_lesbar = sfVorflugText({ mt5Baseline: { vorflug: { a: { at: iso(C - 60000), lesbar: true, grund: 'ok' } } } }, C);\n"
              "window._sfClaimHier = new Map([['p1', C]]);\n"
              "sfAusstiegHier('p1', 'für den Start fehlt: „Symbol“');\n"
              "window._sfAusstiegHier.get('p1').at = C + 1000;\n"
              "var u1 = sfStillUrteil(p, C + 5*60000, false, null, sfHier('p1'));\n"
              "out.hier = u1;\n"
              "window._sfClaimHier = new Map();\n"
              "var u2 = sfStillUrteil(p, C + 5*60000, false, null, sfHier('p1'));\n"
              "out.fremd = u2;\n"
              "window._sfClaimHier = new Map([['p1', C]]);\n"
              "window._sfAusstiegHier.get('p1').at = C + 4*60000;\n"
              "out.spaet_ausstieg = sfStillUrteil(p, C + 5*60000, false, null, sfHier('p1'));\n"
              "window._sfAusstiegHier.get('p1').at = C - 60000;\n"
              "window._sfClaimHier = new Map([['p1', C]]);\n"
              "out.alt_ausstieg = sfStillUrteil(p, C + 5*60000, false, null, sfHier('p1'));\n"
              "JSON.stringify(out)")
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            check(False, "JavaScriptCore lief nicht: " + (r.stderr or "")[:200])
        else:
            o = json.loads(r.stdout.strip())
            vfz = o["vf"]
            check(vfz.startswith(" Vorflug ") and "Master-Terminal läuft nicht" in vfz and "PC oder Instanz belegt" in vfz and vfz.index("Master-Terminal") < vfz.index("Instanz belegt")
                  and " Dubai: " in vfz and vfz.endswith("."), "sfVorflugText: beide Gründe, zeitlich geordnet, mit Dubai-Uhrzeit")
            check(o["vf_alt"] == "" and o["vf_lesbar"] == "", "sfVorflugText: alter Vorflug (> 30 min vor dem Claim) und lesbarer Vorflug zählen nicht")
            h = o["hier"]
            check(h and h["unklar"] is False and h["msg"].startswith("Geclaimt vor 5 min, der Start endete in diesem Tab ohne Ergebnis, bevor etwas an den Bot ging — nichts gesendet.")
                  and "Grund: für den Start fehlt: Symbol." in h["msg"] and "Vorflug" in h["msg"], "Beleg hier: Schlüssel-Text vorne, Grund + Vorflug hinten, nichts gesendet")
            f = o["fremd"]
            check(f and f["unklar"] is True and "Master-Konto nicht lesbar → im Master-Terminal prüfen, ob eine Order liegt. Vorflug" in f["msg"]
                  and f["msg"].endswith(" [Tab: x]") and "Grund:" not in f["msg"], "ohne Beleg: unklar wie bisher, Vorflug vor dem Tab-Zustand, kein fremder Ausstieg")
            a = o["alt_ausstieg"]
            check(a and a["unklar"] is False and "Grund:" not in a["msg"], "Ausstieg von VOR dem Claim zählt nicht")
            sa = o["spaet_ausstieg"]
            check(sa and sa["unklar"] is False and "Grund:" not in sa["msg"], "Ausstieg 4 min nach dem Claim (später Hand-Klick) zählt nicht")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER: {FEHLER}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
