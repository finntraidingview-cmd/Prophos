#!/usr/bin/env python3
"""Selbsttest PLANER-TAB Schritt 1 (30.10.2026): Struktur in prophos.html — Seitenleisten-Link, Chip-Leiste, Hülle Funded CFD, Planer-Modus
der Admin-Section (gleiche Sperre/Rechte), Verweis-Reiter, Übersicht erst nach dem Planer. Nur Text-/Strukturprüfung, ohne Browser.
Aufruf: python3 tools/selftest_planer_tab.py"""
import os
import re
import sys

HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prophos.html")


def main():
    s = open(HTML, encoding="utf-8").read()
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    # Seitenleiste: unter TRADING, standardmäßig versteckt, eine Datei
    i_trading, i_link, i_admin = s.find('<div class="sb-section">Trading</div>'), s.find('data-view="planer" data-planerhaupt="challenge" style="display:none"'), s.find('<button class="sb-link" data-view="kasse">')
    ok(0 < i_trading < i_link < i_admin, "Link „Planer“ unter TRADING, vor Admin, versteckt bis entsperrt")
    ok("planer:    ['Planer'," in s, "viewTitles kennt planer (#planer beim Start)")
    # Chip-Leiste: vier Planer in fester Reihenfolge, Design-System .subtabs/.subtab
    # PLANER-GLIEDERUNG (30.10.2026): zwei Einträge in der Navigation, je Gruppe ihre Reiter
    ok(s.count('class="sb-link" data-view="planer" data-planerhaupt=') == 2 and "Challenge Planer\n" in s and "Funded Planer\n" in s, "zwei Einträge Challenge Planer · Funded Planer")
    i_ch = s.find('id="adm-planer-chips"')
    reiter = re.findall(r'data-planerchip="([\w-]+)" data-haupt="(\w+)"', s[i_ch:i_ch + 900])
    ok(reiter == [("planer-cfd", "challenge"), ("planer-fut", "challenge"), ("fcfd", "funded"), ("fplaner", "funded"), ("wd", "funded")], f"Reiter {reiter}")
    ok("'planer-cfd': { reiter: 'planer', art: 'cfd', haupt: 'challenge' }" in s and "wd: { reiter: 'wd', haupt: 'funded' }" in s, "Reiter → Admin-Reiter + Kontoart + Gruppe")
    ok("l.addEventListener('click', () => { planerHauptWahl = l.dataset.planerhaupt }, true)" in s, "Gruppe vor switchView gemerkt (Capture)")
    # Kontoart filtert nur den Challenge-Planer im Planer-Modus, an denselben Stellen wie die ID-Sicht
    ok("if((a !== 'cfd' && a !== 'futures') || _apIdsArtWert !== 'challenge') return null" in s, "Kontoart nur im Challenge-Planer")
    ok("return _apIds.offen.filter(z => (!u || String(z.user_id) === u) && apArtPasst(z))" in s, "Zu bestätigen nach Kontoart")
    ok(s.count("return apArtD(u && typeof tplSichtFilter === 'function' ? tplSichtFilter(D, new Set([u])) : D)") == 2, "Kopf + Wartet/Läuft nach Kontoart")
    ok("String(z.user_id) === b.dataset.apOkId && apArtPasst(z)" in s, "„✓ alle n“ je ID nur die sichtbare Kontoart")
    ok('class="subtabs nav-gruppe-tabs adm-planer-chips"' in s, "Chip-Leiste im Stil der Navigations-Gruppen")
    # Hülle Funded CFD: Gerüst, keine Abfrage
    # seit 30.10.2026 (Planer Schritt 2) baut apgHuelleHtml die Hülle mit den Guestly-Bausteinen in #apg-fcfd
    ok('<div id="adm-pane-fcfd" hidden><div id="apg-fcfd" class="ap-guestly"></div></div>' in s, "Hülle-Container Funded CFD")
    i = s.find("function apgHuelleHtml(){")
    huelle = s[i:s.find("function apGuestlyVerdrahten(root){", i)]
    # Funded-CFD-Regeln (30.10.2026) laden bewusst über GET /admin/funded-cfd-plan — ihr Block zählt nicht als „neue Abfrage" des Gerüsts
    _a, _b = huelle.find("/* FUNDED-CFD-REGELN"), huelle.find("window._fcfdRegelnStub")
    if 0 <= _a < _b: huelle = huelle[:_a] + huelle[_b:]
    for teil in ("Zeitstrahl", "'Zu bestätigen', 'Läuft', 'Braucht dich', 'Wartet auf Start'", "kommt", "Long · Short je ID", "Starts je Stunde"):
        ok(teil in huelle, "Hülle Funded CFD: " + teil)
    ok("fetch" not in huelle and "apdApi" not in huelle and "disabled" in huelle, "Hülle ohne Abfragen, Knöpfe gesperrt")
    ok('data-admtab="fcfd" data-reiter-aus="1"' in s and "$('adm-pane-fcfd').hidden     = true" in s and "name !== 'planer' && name !== 'fplaner' && name !== 'fcfd'" in s, "Reiter fcfd nur im Planer, im Planer-Bereich")
    # Planer-Modus = Admin-Section (dieselbe Sperre/Rechte), Chips nach kasseReiterErlaubt
    ok("v.dataset.view === name || (name === 'planer' && v.dataset.view === 'kasse')" in s, "Planer aktiviert die Admin-Section")
    ok("if((name === 'kasse' || name === 'planer') && typeof kasseOnEnter === 'function') kasseOnEnter()" in s, "Planer geht durch kasseOnEnter (Code-Sperre)")
    ok("['wd', 'planer', 'fplaner', 'fcfd'].filter(n => kasseReiterErlaubt(n, ec) ||" in s, "Chips/Link nach kasseReiterErlaubt")
    ok("link.style.display = currentUserId ? '' : 'none'" in s, "Link für jede eingeloggte ID (Sperre kommt im Planer)")
    ok("forEach(pl => { pl.style.display = 'none' })   // PLANER-TAB: Link weg" in s, "Abmelden: Link weg")
    ok("section.view.adm-planer-modus #kasse-content > .subtabs:not(.adm-planer-chips){display:none}" in s, "Admin-Reiter im Planer-Modus aus")
    # Verweis im Admin, Merker nur sessionStorage
    ok("if(['wd', 'planer', 'fplaner', 'fcfd'].includes(name) && !planerModus()){" in s and "switchView('planer'); return" in s, "Admin-Reiter = Verweis auf Planer")
    ok(s.count('title="→ jetzt unter Planer"') == 3, "drei Verweis-Reiter")
    ok("localStorage" not in s[s.find("const PLANER_CHIP_SS"):s.find("function showLocked()")], "Chip-Merker ohne localStorage")
    ok("sessionStorage.getItem(PLANER_CHIP_SS)" in s, "Chip-Merker in sessionStorage")
    # Lazy: Übersicht im Planer-Modus erst nach dem Planer
    ok("if(planerJetzt && !planerWarten) setTimeout(() => { if(!admData || Date.now() - (window._admLadeZeit || 0) > ADM_CACHE_MS) admLoad() }, 2500)" in s,
       "Übersicht im Planer-Modus verzögert (nur bekannte HT-Rolle)")
    # Verwalter zuerst (Master 30.10.2026): ohne bekannte Rolle wartet der Planer auf admLoad, Panes bis dahin aus
    ok("const planerSchnell = eigenerCode === null && !eigenerCodeUnklar && !['verwalter', 'eigen'].includes(planerRolle())" in s
       and "const planerWarten = planerJetzt && !admFrisch && !planerSchnell" in s, "schnell nur mit Standard-Code und ohne eingeschränkte Rolle")
    sql = open(os.path.join(os.path.dirname(HTML), "sql", "2026-10-30_verwalter_braucht_code.sql"), encoding="utf-8").read()
    ok("before insert or update of verwalter_user_id on public.id_gruppen" in sql and "before update or delete on public.admin_zugang" in sql
       and "coalesce(btrim(z.code), '') <> ''" in sql, "Riegel: Verwalter braucht eigenen Code")
    ok("admLoad().finally(() => { planerWarteSetzen(false); if(planerModus()){ kasseReiterFuer(eigenerCode); planerChipsSync(eigenerCode); planerChipOeffnen() } })" in s,
       "Planer öffnet erst nach der Verwalter-Erkennung")
    ok("if(!planerWarten) planerChipOeffnen()" in s, "kein Chip vor der Erkennung")
    ok("(!admData && ec && planerRolle() === 'verwalter' && !KASSE_REITER_HT.has(n))" in s, "bekannter Verwalter: Link vor der Übersicht, ohne HT-Reiter")
    ok("section.view.adm-planer-warten #kasse-content [id^=\"adm-pane-\"]{display:none !important}" in s, "Panes während des Wartens aus")
    ok("try{ planerRolleMerken(d) }catch(_){}" in s and "sessionStorage.setItem(PLANER_ROLLE_SS" in s, "Rolle je ID in sessionStorage")
    for t in f:
        print("✗", t)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
