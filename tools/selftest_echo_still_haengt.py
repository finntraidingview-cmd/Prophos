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


def still(p, jetzt, laeuft_hier=False, master_flach=None):
    """Python-Spiegel von sfStillUrteil → None | (unklar, msg)."""
    if (not p or p.get("route") != "mt5" or p.get("status") != "planned" or not p.get("claim") or p.get("started")
            or p.get("orbit") or laeuft_hier):
        return None
    claim = p["claim"]
    if jetzt - claim < STILL_MS or jetzt - claim > 24 * 3600000:
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
    return (True, "unklar")


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    # ── Spiegel-Regel im Frontend ──
    u = html[html.index("function sfStillUrteil("):html.index("async function sfStillPruefen(")]
    check("p.route !== 'mt5'" in u and "p.status !== 'planned'" in u and "!p.startUmGestartetAt" in u and "p.startedAt" in u
          and "p.orbitGesendetAt" in u and "laeuftHier) return null" in u, "Kandidat: Echo mit Hedge, geplant, geclaimt, nicht gestartet, hier läuft kein Check")
    check("const SF_STILL_MS = 4 * 60000" in html and "jetzt - claim > 24 * 3600000" in u and "(Date.parse(f.at) || 0) >= claim - 5000" in u,
          "4 min nach dem Claim, höchstens 24 h, nicht doppelt (Start-Fehler nach dem Claim zählt)")
    check("/nichts gesendet|nichts platziert/i" in u and "!spNach && masterFlach === true) return { unklar: false" in u and "return { unklar: true" in u,
          "unklar = false nur mit Beleg (Antwort „nichts gesendet“ oder keine Antwort + Master flach), sonst unklar")
    k = html[html.index("async function sfStillPruefen("):html.index("let _sfLaeuft = false, _sfAbgleichAt = 0")]
    check("mt5RouteResolve(p0, dd.instances || [])" in k and "if(!ri) continue" in k and "dd.copier_offline || dd._httpFail) return" in k,
          "Nachkontrolle nur für Pläne dieses PCs (lokale Copier-Instanz), Panel nicht lesbar → nichts")
    check("row.start_claim_art === 'verbrauch'" in k and ".select('*').eq('id', p0.id).maybeSingle()" in k and "schritt: 'm5still'" in k,
          "frisch aus der DB, verpasste Claims (verbrauch) ausgenommen, Schritt m5still")
    check("ri.inst.alive && !st.note && Array.isArray(st.master_positions)" in k, "Master flach nur aus frischem Copier-Status (alive, keine note)")
    check("pfLebtJetzt(p && p.id)" in k and "pfLebtJetzt(p0.id)" in k and "_pfPlanId" not in k,
          "„Check läuft hier“ = eigener Merker pfLebt (läuft von selbst ab), nicht _pfPlanId (Prüf-Agent)")
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
    check(still(dict(basis, started=True), j) is None and still(dict(basis, route="mt5v2"), j) is None and still(dict(basis, claim=j - 25 * 60 * MIN), j) is None,
          "gestartet / anderer Weg / älter als 24 h → nichts")
    alte_spur = dict(heil, at=j - 30 * MIN)
    check(still(dict(basis, spur=alte_spur), j) == (True, "unklar"), "Antwort von VOR dem Claim zählt nicht als Beleg")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
