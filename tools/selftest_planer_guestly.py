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
    ok("const guestly = apSchlankJetzt() && (_apIdsArtWert === 'challenge' || apSchlankFunded())" in s, "Challenge + Funded Futures im Planer-Gerüst (WD + Funded CFD eigene Bauer)")
    ok("funded: apIstFunded()" in s and "vorschau ? 'Vorschau' : 'Zu bestätigen'" in s, "Funded: Vorschau statt Zu bestätigen")
    ok("let schalter = ''; if(!fd)" in s and "teile.push(Q ? (Q.aktiv ? nm + ' an'" in s, "Funded: Einstellungen = Funded-Regeln, keine Challenge-Schalter")
    ok("function apgZeilenSchmuecken(root, x)" in s and "apgZeilenSchmuecken(root, ow)" in s, "Weg-Chips in den Zeilen")
    ok("if(r === 'mt5v2' && z && z.hedge_weg === 'echo' && apgEchoHedgeAn()){" in s and "['Echo', 'hedge', 'wird ~20 min vor dem Start" in s and "'Echo V2 · ⚠ ohne Hedge', 'warn', `startet ohne Hedge (Echo V2): ${String(g)}`" in s,
       "Echo-Vorschlag mit Vorschau + Schalter an → „Echo“ (Echo-Namen 30.10.2026), mit Grund → „Echo V2 · ⚠ Grund“")
    ok("if(v && v.echo_hedge && v.echo_hedge.an === false) return ''" in s, "Echo-Hedge aus → kein Vorschau-Chip")
    # Master | Fusion (30.10.2026): Fusion-Werte in Lots/TP/SL neben den Master-Werten, Kopf „Master | Fusion", Chip entfällt
    i = s.index("function apgMasterFusion(root, je){")
    mf = s[i:s.index("\n  }\n", s.index("tab.querySelectorAll('.pz-z[data-plan-id]')", i))]
    ok("if(!apIstFunded()){ apgMasterFusion(root, je); apgHedgePaare(root, je, x) }" in s, "nur Challenge (Funded hat die Spalte Fusion)")
    ok("[[3, 'Lots'], [6, 'TP'], [7, 'SL']]" in mf and "Master <i>|</i> Fusion" in mf, "Köpfe Lots/TP/SL mit Master | Fusion")
    ok("zellen.tp.appendChild(fus(passTp != null ? ahfEur(passTp)" in mf and "zellen.sl.appendChild(fus(vs.blow_eur != null ? ahfEur(vs.blow_eur)" in mf, "TP = Fusion am Master-TP, SL = Fusion am Master-SL/Blow")
    ok("fus('—', 'keine Fusion-Vorschau für diesen Plan', 'leer')" in mf and "fus('⚠', `${art} nicht rechenbar: ${grund}`, 'warn')" in mf, "ohne Vorschau „—“, mit Grund „⚠“ + Tooltip")
    ok("s.title = tip" in mf and "s.innerHTML = txt" in mf and "escapeHtml" not in mf.split("const fus")[1].split("\n")[0], "Tooltip als title (kein HTML)")
    ok("if(!/Freigabe offen/.test(c.textContent)) c.remove()" in mf, "Chip weg, nur „Freigabe offen“ bleibt")
    ok("#ap-ids-root.ap-guestly .pz-radar .apg-mfz{display:inline-flex;flex-direction:column" in s, "Handy: Fusion unter Master")
    ok(".pz-radar:not(:has(.pz-fus)) .pz-z > :nth-child(5){display:none}" in s, "Spalte Schritt nur ohne Fusion-Hedge aus")
    # Tokens nur unter #ap-ids-root.ap-guestly, dunkel über den Sonnen-Schalter, Guestly-Farben
    for c in ("--g-a1:#5447ce", "--g-a2:#887cfc", "--g-a3:#4996ff", "--g-a4:#16c8c6"):
        ok(c in s, "Farbe " + c)
    ok('html[data-theme="dark"] :is(#ap-ids-root.ap-guestly,#apg-fcfd,#adm-pane-wd.ap-guestly){' in s, "dunkle Tokens am Sonnen-Schalter (auch WD)")
    ok(not re.search(r":root\{[^}]*--g-a1", s), "keine globalen --g-Tokens")
    css = "\n".join(z for z in s.splitlines() if "apg-" in z and "{" in z and z.lstrip().startswith(("#", "@", "html", ":is(")))
    ok(all(("#ap-ids-root.ap-guestly" in z or z.lstrip().startswith(("#adm-pane-wd.ap-guestly", "#apg-fcfd "))) for z in css.splitlines() if z.lstrip().startswith(("#", ":is(")) and "apg-" in z), "apg-Stile nur im Planer-Bereich")
    ok("border-radius:16px" in css, "Karten 16 px Radius")
    # Aufbau in der Reihenfolge der Vorgabe
    i = s.index("function apGuestlyHtml(x){")
    g = s[i:s.index("function apGuestlyVerdrahten(root){", i)]
    # Funded-CFD-Regeln (30.10.2026) laden bewusst über GET /admin/funded-cfd-plan — ihr Block zählt nicht als „neue Abfrage" des Gerüsts
    _a, _b = g.find("/* FUNDED-CFD-REGELN"), g.find("window._fcfdRegelnStub")
    if 0 <= _a < _b: g = g[:_a] + g[_b:]
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
    # WD + Funded CFD im Guestly-Gerüst (30.10.2026, Bugliste #8/#9)
    ok('<div id="apg-wd" hidden></div>' in s, "WD: Container für Kopf/KPI/Charts im Pane")
    ok("try{ apgWdRender(liste) }catch(e)" in s, "WD: Aufruf aus wdUebRender, Fehler stören die Kacheln nicht")
    i = s.index("function apgWdRender(liste){")
    w = s[i:s.index("  window._wdUebNeu = () =>", i)]
    ok("B = window._apgBau" in w and "if(!an || !wdSichtbar()) return" in w, "WD: Bausteine über window._apgBau, nur sichtbar gezeichnet")
    ok(w.count("apgKpi({ gross: true") == 2 and w.count("apgKpi({ icon:") == 3, "WD: 2 große + 3 kleine KPI-Karten")
    ok("'apg-wd-ls'" in w or 'id="apg-wd-ls"' in w, "WD: Long/Short-Chart")
    ok('id="apg-wd-std"' in w and "_apgWd.charts" in w and "c.destroy()" in w, "WD: Starts je Stunde, Charts vor dem Neuzeichnen zerstört")
    ok("fetch(" not in w and "supabase" not in w and "localStorage" not in w, "WD: keine Abfrage, kein Speicher")
    ok("window._apgBau = { apgKpi, apgPille, APG_ICON, apgKarte, apgChartsMalen, apgZahl, schlank: () => AP_SCHLANK" in s, "Bausteine exportiert")
    ok("#adm-pane-wd.ap-guestly:has(#apg-wd .apg-kpis) #wd-ueb-heute{display:none}" in s, "WD: alte Kopf-Kacheln im Gerüst ausgeblendet (gleiche Zahlen oben)")
    i = s.index("function apgFcfdHtml(ad){")
    c = s[i:s.index("function apgFcfdRender(){", i)]
    ok("r.type === 'funded_cfd' && !r.archived" in s and "fetch(" not in c, "Funded CFD: Konten aus /admin/overview, keine eigene Abfrage")
    ok(c.count("apgKpi({ gross: true") == 2 and c.count("apgKpi({ icon:") == 3, "Funded CFD: 2 große + 3 kleine KPI-Karten")
    ok('id="apg-fc-ls"' in c and 'id="apg-fc-firma"' in c, "Funded CFD: Charts je ID + je Firma")
    ok('class="apg-haupt" disabled' in c, "Funded CFD: Planen bleibt gesperrt")
    ok("if(name === 'fcfd') window._fcfdNebenLaden?.()" in s, "Funded CFD: beim Öffnen Übersicht + Regeln nachladen")
    # Funded CFD im Challenge-Gerüst (30.10.2026, Master nach .1926): dritte Quelle wie Funded Futures, Knöpfe über die eigene Route
    ok("fcfd: { basis: '/admin/funded-cfd-plan'" in s and "bauen: d => fcpQuelleBauen(d)" in s, "Funded CFD: Quelle + Route je Art")
    ok("? fdpArt().basis : null" in s, "Funded CFD: Bestätigen/Zurück/Löschen über /admin/funded-cfd-plan")
    ok("name === 'fcfd' ? 'fcfd' : 'challenge'" in s, "Reiter fcfd schaltet die Quelle")
    ok("unten = fcfdUnterHtml(u)" in s and "Planer aus — Vorschläge kommen, sobald Finn ihn einschaltet" in s, "Funded CFD: Waiting · Firmen · Regeln unten, Leer-Hinweis")
    ok("apgChartsMalen(root, _apg.daten, { ls: '#apg-c-ls', balken: '#apg-c-std', ablage: _apg.charts })" in s, "Challenge zeichnet über denselben Helfer")
    for t in f:
        print("✗", t)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
