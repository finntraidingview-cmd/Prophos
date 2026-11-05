#!/usr/bin/env python3
"""Selbsttest: Echo mit Hedge (route mt5) — ein geclaimter Plan hängt nie still (30.10.2026, Master ECHO-STILL-HAENGT: f47544cf und
e7e9782d blieben nach „Terminal wird gerade geheilt" geclaimt auf planned, ohne Start-Fehler). Prüft (1) jeden Ausstieg von
tpPreflightMt5 nach einem Claim auf genau EINEN Start-Fehler (sfEinmal) und (2) die Nachkontrolle in sfTick (sfStillUrteil) mit
gestellten Plänen. Aufruf: python3 tools/selftest_echo_still_haengt.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []
STILL_MS = 4 * 60000
MIN = 60000


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


ROUTEN = ("mt5", "mt5v2", "tvv2", "tsv2")   # CL1 (05./06.11.2026): alle Puls-Wege
FREMD_MS = 10 * MIN if "MIN" in globals() else 600000


def still(p, jetzt, laeuft_hier=False, master_flach=None, hier=None):
    """Python-Spiegel von sfStillUrteil → None | (unklar, msg). hier = (claim_ms, gesendet) aus dem Speicher der Seite (CL1)."""
    if (not p or p.get("route") not in ROUTEN or p.get("status") != "planned" or not p.get("claim") or p.get("started")
            or p.get("orbit") or laeuft_hier):
        return None
    claim = p["claim"]
    if jetzt - claim < STILL_MS or jetzt - claim > 24 * 3600000:
        return None
    hier_beleg = bool(hier and hier[0] is not None and abs(hier[0] - claim) < 5000 and not hier[1]
                      and not p.get("puls_unklar") and not (p["route"] == "mt5" and master_flach is False))
    if p["route"] != "mt5" and not hier_beleg and jetzt - claim < 10 * 60000:
        return None
    f = p.get("sf")
    if f and f["at"] >= claim - 5000:
        return None
    sp = p.get("spur")
    sp_nach = bool(sp and sp["at"] >= claim)
    sp_nichts = sp_nach and not sp.get("ok") and re.search(r"nichts gesendet|nichts platziert", sp.get("msg", ""), re.I)
    if sp_nichts:
        return (False, "spur")
    if not sp_nach and master_flach is True:
        return (False, "flach")
    if not sp_nach and hier_beleg:
        return (False, "hier")
    return (True, "unklar")


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    # ── Spiegel-Regel im Frontend ──
    u = html[html.index("function sfStillUrteil("):html.index("async function sfStillPruefen(")]
    check("!SF_STILL_ROUTEN.includes(p.route)" in u and "const SF_STILL_ROUTEN = ['mt5', 'mt5v2', 'tvv2', 'tsv2'], SF_STILL_FREMD_MS = 10 * 60000" in html
          and "p.status !== 'planned'" in u and "!p.startUmGestartetAt" in u and "p.startedAt" in u
          and "p.orbitGesendetAt" in u and "laeuftHier) return null" in u, "Kandidat: Echo mit Hedge, geplant, geclaimt, nicht gestartet, hier läuft kein Check")
    check("const SF_STILL_MS = 4 * 60000" in html and "jetzt - claim > 24 * 3600000" in u and "(Date.parse(f.at) || 0) >= claim - 5000" in u,
          "4 min nach dem Claim, höchstens 24 h, nicht doppelt (Start-Fehler nach dem Claim zählt)")
    # N2 (04.11.2026): der Beleg steht in sfVorOrderBeleg (Kopf der Antwort, „nichts gesendet/platziert" + Abbrüche vor dem Order-Knopf) — der Spiegel
    # oben prüft weiter die alten Wörter, die Erweiterung prüft tools/selftest_endlesung_deals.js im Browser
    beleg = html[html.index("function sfVorOrderBeleg("):html.index("window._sfVorOrderBeleg = sfVorOrderBeleg")]
    check("sfVorOrderBeleg(sp.msg)" in u and "/nichts gesendet/i" in html and "/nichts platziert/i" in html and "split(/\\s+(?:Spur:|\\[(?=[\\d…]|\\.\\.\\.))/)[0]" in beleg
          and "!spNach && masterFlach === true) return { unklar: false" in u and "return { unklar: true" in u,
          "unklar = false nur mit Beleg (Kopf der Antwort sagt „nichts gesendet/platziert“ o. ä., oder keine Antwort + Master flach), sonst unklar")
    k = html[html.index("async function sfStillPruefen("):html.index("let _sfLaeuft = false, _sfAbgleichAt = 0")]
    check("mt5RouteResolve(p0, dd.instances || [])" in k and "if(!ri) continue" in k and "dd.copier_offline || dd._httpFail) dd = null" in k
          and "if(p0.route === 'mt5'){\n        if(!dd) continue" in k,
          "Echo mit Hedge: nur Pläne dieses PCs (lokale Copier-Instanz), Panel nicht lesbar → diese Pläne nicht (die anderen Wege brauchen das Panel nicht)")
    check("row.start_claim_art === 'verbrauch'" in k and ".select('*').eq('id', p0.id).maybeSingle()" in k and "schritt: p.route === 'mt5' ? 'm5still' : 'puls_still'" in k,
          "frisch aus der DB, verpasste Claims (verbrauch) ausgenommen, Schritt m5still")
    check("ri.inst.alive && !st.note && Array.isArray(st.master_positions)" in k, "Master flach nur aus frischem Copier-Status (alive, keine note)")
    lh = html[html.index("function sfLaeuftHier(p){"):html.index("async function sfStillPruefen(")]
    check("sfLaeuftHier(p)" in k and "sfLaeuftHier(p0)" in k and "_pfPlanId" not in k and "pfLebtJetzt(id)" in lh and "!!_pfV2Laeuft" in lh
          and "!!_tpOrbitLaeuft" in lh and "!!_osActive || !!_rsAktiv" in lh and "String(_suLaufId) === id" in lh
          and "window._sfLaeuftIds.get(id)" in lh and "catch(_){ return true }" in lh,
          "„Start läuft hier“ = pfLebt / jede Echo-V2-Kette / Orbit-Lauf / Signal / Remote / Laufmarke / Startzeit-Takt (Fehler → läuft), nicht _pfPlanId")
    om = html[html.index("async function tpOrbitStarten(planId, fern, opts){"):html.index("async function tpOrbitStartenMitMarke(")]
    check("sfLaeuftMarke(planId, true)" in om and "finally{ sfLaeuftMarke(planId, false) }" in om, "Gegenprüfung: Hand-/Fern-Start in tpOrbitStarten trägt eine Laufmarke bis zum Ende")
    v2 = html[html.index("function tpV2Nacheinander(planId, order){"):html.index("_pfV2Kette = Promise.race(")]
    check("sfLaeuftMarke(planId, true)" in v2 and ".finally(() => sfLaeuftMarke(planId, false))" in v2, "Gegenprüfung: Plan in der Echo-V2-Kette gilt als laufend")
    bh = html[html.index("async function sfBehoben("):html.index("async function sfNeuEinplanen(")]
    ps = bh[bh.index("if(f.schritt === 'puls_still'){"):]
    ps = ps[:ps.index("\n    }\n") + 6]
    check("sfHier(plan.id).gesendet || sfLaeuftHier(plan)) return null" in ps and ".select('status,started_at,orbit_gesendet_at,start_um_gestartet_at,mt5_baseline')" in ps
          and "row.status !== 'planned' || row.started_at || row.orbit_gesendet_at) return null" in ps and "b.puls_unklar" in ps
          and "b.start_fehler.schritt !== 'puls_still' || b.start_fehler.unklar) return null" in ps and "(Date.parse(b.puls_spur.at) || 0) >= cl - 5000) return null" in ps,
          "Gegenprüfung (hoch): puls_still wird erst neu eingeplant, wenn JETZT frisch nichts dagegen spricht (Hand-/Handy-Start dazwischen)")
    # CL1: Speicher-Beleg — Claim dieser Seite merken, VOR jedem Senden markieren
    check("if(!(verspaetet > fenster)) sfGeclaimtHier(plan.id, data[0].start_um_gestartet_at)" in html, "tpStartUmTick merkt den eigenen Claim (nur echte Starts)")
    for anker, name in (("    sfSendetHier(plan.id)   // CL1: ab hier kann eine Order raus — nie „nichts gesendet\" aus dem Speicher\n    for(;;){\n      const tReq = Date.now()", "Echo V2"),
                        ("_pfV2Laeuft = String(plan.id)\n                sfSendetHier(plan.id)", "Echo mit Hedge"),
                        ("    _tpOrbitLaeuft = true\n    sfSendetHier(plan.id)   // CL1: ab hier kann Puls klicken", "Orbit/Topstep scharf"),
                        ("        _tpOrbitLaeuft = true\n        sfSendetHier(plan.id)   // CL1 (Probe", "Topstep Probe")):
        check(anker in html, f"Sendemarke vor dem Senden: {name}")
    check(html.index("sfSendetHier(plan.id)   // CL1: ab hier kann Puls klicken") < html.index("await window.mtcApi('tsx-konto', { method:'POST'") if "await window.mtcApi('tsx-konto', { method:'POST'" in html else True,
          "Orbit/Topstep: Marke steht vor dem Puls-Aufruf")
    check("!row.start_claim_art && Date.parse(row.start_um_gestartet_at) - Date.parse(row.start_um) > 30 * 60000" in k,
          "verpasst auch ohne start_claim_art erkannt (Claim > 30 min nach Startzeit)")
    check("unklar: u.unklar || alt" in k, "Plan von einem früheren Tag → unklar (Handy-Meldung, sfTick plant nur heutige neu ein)")
    b = html[html.index("async function sfBehoben("):html.index("async function sfNeuEinplanen(")]
    check("f.schritt === 'm5still'" in b and "st.master_positions.length === 0)) return null" in b,
          "Neu-Einplanen nach m5still nur mit frischem Flach-Beweis des Copiers (keine Doppel-Order)")
    check("await tpJetztStarten(plan.id); _rkTickStart.delete(String(plan.id)) }" in html, "Startzeit-Merker leckt nicht in spätere Hand-Starts")
    lebt = html[html.index("const _pfLebtBis = new Map()"):html.index("const _pfLebtBis = new Map()") + 400]
    check("pfLebtJetzt = id => (_pfLebtBis.get(String(id)) || 0) > Date.now()" in lebt, "pfLebt: Merker mit Ablaufzeit")
    t = html[html.index("async function sfTick(){"):html.index("function sfHaengtMelden(")]
    check("await sfStillPruefen()" in t and t.index("for(const p of kand)") < t.index("await sfStillPruefen()"), "sfTick ruft die Nachkontrolle jeden Takt")
    # ── tpPreflightMt5: jeder Ausstieg meldet genau einmal ──
    s = html.index("async function tpPreflightMt5(plan){")
    f = html[s:html.index("/* „Echo fortsetzen & neu starten\"", s)] if "/* „Echo fortsetzen & neu starten\"" in html[s:s + 80000] else html[s:s + 80000]
    check("const sfEinmal = async f => { pfLebt(plan.id, 0); if(!vonTick || sfSchon) return; sfSchon = true; await sfMelden(plan, f) }" in f,
          "sfEinmal: nur nach Start zur Startzeit, höchstens einmal je Lauf")
    check("await sfMelden(plan" not in f.replace("sfSchon = true; await sfMelden(plan, f)", ""), "kein direkter sfMelden-Aufruf mehr im Check (alle über sfEinmal)")
    for schritt in ("m5fenster", "m5scharf", "m5order", "m5abbruch", "m5login", "m5term", "m5check", "m5pause"):
        check(f"schritt: '{schritt}'" in f, f"Ausstieg {schritt} meldet Start-Fehler")
    ab = f[f.index("// Abbruch heißt auch: gemerkte Bot-Order verwerfen"):]
    check(ab.index("_pfMt5StopTimer()") < ab.index("schritt: 'm5abbruch'") < ab.index("return"), "Ticker-Abbruch (Popup zu): Timer aus, dann Start-Fehler, dann raus")
    lb = f[f.index("// Letzter Blick VOR dem Abschuss"):]
    check(lb.index("schritt: 'm5abbruch'") < lb.index("master-order?file="), "letzter Blick vor dem Abschuss: Popup zu → Start-Fehler, keine Order")
    hf = f[f.index("_pfFinish(false, 'Es gibt Probleme"):]
    check(hf.index("schritt: 'm5check'") < hf.index("} else {"), "Check-Abbruch (hardFail) → Start-Fehler m5check")
    check("const sfEinmal = async f => { pfLebt(plan.id, 0);" in f and "pfLebt(plan.id, 30000)" in f and "pfLebt(plan.id, 340000)" in f
          and f.index("pfLebt(plan.id, 340000)") < f.index("master-order?file="), "Merker: Start, je Ticker-Runde, vor jeder master-order (340 s), Ausstieg löscht")
    check("schritt: 'm5pause'" in f, "Echo pausiert → Start-Fehler m5pause statt still (Prüf-Agent)")
    check("unklar: true })   // Start-Fehler (unklar)" in f or "'Order-Abschuss gestört: ' + String(e && e.message || e), unklar: true" in f,
          "gestörter Abschuss bleibt unklar (keine Doppel-Order)")

    # ── Simulation der Nachkontrolle ──
    j = 1_000_000_000_000
    basis = {"route": "mt5", "status": "planned", "claim": j - 5 * MIN}
    heil = {"at": j - 5 * MIN + 13000, "ok": False, "msg": "Terminal wird gerade geheilt (EA-Selbstheilung, nichts gesendet) — gleich erneut."}
    check(still(dict(basis, spur=heil), j) == (False, "spur"), "f47544cf-Fall: Claim + Heil-Antwort, still → Start-Fehler, nicht unklar (wird neu eingeplant)")
    check(still(basis, j, master_flach=True) == (False, "flach"), "Tab neu geladen, keine Antwort, Master flach → Start-Fehler, neu einplanbar")
    check(still(basis, j, master_flach=False) == (True, "unklar") and still(basis, j) == (True, "unklar"),
          "keine Antwort + Master offen/nicht lesbar → unklar (keine Doppel-Order)")
    check(still(dict(basis, spur={"at": j - 4 * MIN, "ok": True, "msg": "ok"}), j) == (True, "unklar"), "Antwort ok, Plan trotzdem nicht offen → unklar")
    check(still(dict(basis, claim=j - 3 * MIN), j) is None, "jünger als 4 min → noch nichts")
    check(still(basis, j, laeuft_hier=True) is None, "Check läuft in diesem Tab → nichts")
    check(still(dict(basis, sf={"at": j - 4 * MIN}), j) is None, "nach dem Claim schon gemeldet → nicht doppelt")
    check(still(dict(basis, sf={"at": j - 60 * MIN}), j, master_flach=True) == (False, "flach"), "alter Start-Fehler vor dem Claim zählt nicht")
    check(still(dict(basis, started=True), j) is None and still(dict(basis, route="polar"), j) is None and still(dict(basis, claim=j - 25 * 60 * MIN), j) is None,
          "gestartet / anderer Weg / älter als 24 h → nichts")
    # ── CL1: alle Puls-Wege, Beleg aus dem Speicher ──
    for route in ("tvv2", "tsv2", "mt5v2"):
        b2 = dict(basis, route=route)
        check(still(b2, j, hier=(b2["claim"], False)) == (False, "hier"), f"{route}: diese Seite hat geclaimt, nichts gesendet → Start-Fehler, nachholbar")
        check(still(b2, j, hier=(b2["claim"], True)) is None and still(b2, j) is None, f"{route}: gesendet bzw. ohne Speicher-Beleg → vor 10 min nichts")
        check(still(dict(b2, claim=j - 11 * MIN), j) == (True, "unklar") and still(dict(b2, claim=j - 11 * MIN), j, hier=(j - 11 * MIN, True)) == (True, "unklar"),
              f"{route}: nach 10 min ohne Beleg (Tab neu geladen) oder mit Sendung → unklar, kein Doppelstart")
        check(still(b2, j, laeuft_hier=True, hier=(b2["claim"], False)) is None, f"{route}: Lauf hier aktiv → nichts")
    check(still(basis, j, hier=(basis["claim"], False)) == (False, "hier") and still(basis, j, hier=(basis["claim"], True)) == (True, "unklar"),
          "mt5: eigener Claim ohne Sendung → nichts gesendet; mit Sendung → unklar (Neu-Einplanen braucht weiter den Flach-Beweis, sfBehoben)")
    check(still(basis, j, hier=(basis["claim"] - 60000, False)) == (True, "unklar"), "Speicher kennt einen ANDEREN Claim → kein Beleg")
    check(still(dict(basis, route="polar"), j, hier=(basis["claim"], False)) is None, "Polar → nicht hier")
    check(still(dict(basis, route="tvv2", puls_unklar=True), j, hier=(basis["claim"], False)) is None
          and still(dict(basis, route="tvv2", puls_unklar=True, claim=j - 11 * MIN), j, hier=(j - 11 * MIN, False)) == (True, "unklar"),
          "Gegenprüfung: UNKLAR-Marke am Plan hebt den Speicher-Beleg auf")
    check(still(basis, j, master_flach=False, hier=(basis["claim"], False)) == (True, "unklar"), "Gegenprüfung: Echo mit Hedge, Master offen → kein „nichts gesendet“")
    js = html[html.index("function sfStillUrteil("):html.index("async function sfStillPruefen(")]
    check("Math.abs(Number(hier.claim) - claim) < 5000 && !hier.gesendet" in js and "if(!spNach && hierBeleg) return { unklar: false" in js
          and "p.route !== 'mt5' && !hierBeleg && jetzt - claim < SF_STILL_FREMD_MS) return null" in js, "JS: Speicher-Beleg = Spiegel hier")
    alte_spur = dict(heil, at=j - 30 * MIN)
    check(still(dict(basis, spur=alte_spur), j) == (True, "unklar"), "Antwort von VOR dem Claim zählt nicht als Beleg")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
