#!/usr/bin/env python3
"""Selbsttest PLANER Schritt 2, Guestly-Design Challenge-Planer (30.10.2026): Struktur in prophos.html — nur Challenge, Tokens nur im
Planer-Bereich (hell + dunkel), Aufbau Kopf · KPI · Charts · Einstellungen · Zeitstrahl · Listen, bestehende Handler weiterverwendet.
Nur Text-/Strukturprüfung, ohne Browser. Aufruf: python3 tools/selftest_planer_guestly.py"""
import os
import re
import sys

HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prophos.html")


def main():
    s = open(HTML, encoding="utf-8").read()
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    ok("const guestly = apSchlankJetzt() && (_apIdsArtWert === 'challenge' || apSchlankFunded())" in s, "Challenge + Funded Futures (WD unverändert)")
    ok("funded: _apIdsArtWert === 'funded'" in s and "vorschau ? 'Vorschau' : 'Zu bestätigen'" in s, "Funded: Vorschau statt Zu bestätigen")
    ok("let schalter = ''; if(!fd)" in s and "teile.push(Q ? (Q.aktiv ? 'Funded-Planer an'" in s, "Funded: Einstellungen = Funded-Regeln, keine Challenge-Schalter")
    ok("function apgZeilenSchmuecken(root, x)" in s and "apgZeilenSchmuecken(root, ow)" in s, "Weg-Chips in den Zeilen")
    ok(".pz-radar:not(:has(.pz-fus)) .pz-z > :nth-child(5){display:none}" in s, "Spalte Schritt nur ohne Fusion-Hedge aus")
    # Tokens nur unter #ap-ids-root.ap-guestly, dunkel über den Sonnen-Schalter, Guestly-Farben
    for c in ("--g-a1:#5447ce", "--g-a2:#887cfc", "--g-a3:#4996ff", "--g-a4:#16c8c6"):
        ok(c in s, "Farbe " + c)
    ok('html[data-theme="dark"] :is(#ap-ids-root.ap-guestly,#apg-fcfd){' in s, "dunkle Tokens am Sonnen-Schalter")
    ok(not re.search(r":root\{[^}]*--g-a1", s), "keine globalen --g-Tokens")
    css = "\n".join(z for z in s.splitlines() if "apg-" in z and "{" in z and z.lstrip().startswith(("#", "@", "html", ":is(")))
    ok(all("#ap-ids-root.ap-guestly" in z for z in css.splitlines() if z.lstrip().startswith(("#", ":is(")) and "apg-" in z), "apg-Stile nur im Planer-Bereich")
    ok("border-radius:16px" in css, "Karten 16 px Radius")
    # Aufbau in der Reihenfolge der Vorgabe
    i = s.index("function apGuestlyHtml(x){")
    g = s[i:s.index("function apGuestlyVerdrahten(root){", i)]
    ok(g.rstrip().endswith("return kopf + kpis + charts + leiste + zs + listen\n  }") or "return kopf + kpis + charts + leiste + zs + listen" in g, "Reihenfolge Kopf · KPI · Charts · Einstellungen · Zeitstrahl · Listen")
    ok('<button type="button" disabled title="kommt">7 Tage</button><button type="button" disabled title="kommt">30 Tage</button>' in g, "7/30 Tage ausgegraut mit „kommt“")
    ok("data-ap-tag" in g and "data-apg-id" in g and "data-apg-firma" in g, "Zeitraum + Filter ID/Firma")
    ok(g.count("apgKpi({ gross: true") >= 2 and g.count("apgKpi({ icon:") >= 3, "2 große + 3 kleine KPI-Karten")
    for n in ("P&amp;L hypothetisch", "Zu bestätigen", "Läuft", "Braucht dich", "Wartet auf Start"):
        ok(f"name: '{n}'" in g, "KPI " + n)
    ok('id="apg-c-ls"' in g and 'id="apg-c-std"' in g, "Chart-Reihe Long/Short + Starts je Stunde")
    ok(g.count('data-tpl-nachplan="1"') == 1 and 'class="apg-haupt"' in g, "EIN Hauptknopf Nachplanen (bestehender Handler)")
    ok("apdBotSchalterHtml(v, apdAdmin())" in g and "<details class=\"apg-schalter\"" in g, "bestehende Schalter aufklappbar, nicht entfernt")
    ok("x.ow.offen" in g and "x.ow.laeuft" in g and "T.braucht" in g and "x.ow.warten" in g and "T.zeitstrahl" in g, "Zeitstrahl + Listen aus den bestehenden Bausteinen")
    ok('id="ap-ids-tpl"' in g and 'id="ap-ids-neu"' in g, "bestehende Kopf-Knöpfe")
    # keine neue Abfrage, Charts aufgeräumt
    ok("fetch(" not in g and "apdApi(" not in g, "keine neue Abfrage")
    ok("apgChartsWeg()" in s and "c.destroy()" in s, "Charts vor dem Neuzeichnen zerstört")
    ok("localStorage" not in g and "localStorage" not in s[s.index("function apGuestlyVerdrahten(root){"):s.index("function apIdsRenderChallenge(){")], "kein localStorage")
    for t in f:
        print("✗", t)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
