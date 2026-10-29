#!/usr/bin/env python3
"""Selbsttest GEISTER-PLÄNE (30.10.2026, Slave 7; Master: „Echo-Pläne bleiben open, obwohl der Trade längst zu ist" + S1-Triage #8
„Hedge zu (hand), Master laut Prophos offen").
(1) Echter JS-Code aus prophos.html in JavaScriptCore: echoEndeScharf / echoBelegMs / echoGeistFaellig (Echo) und hedgeHandFlachFaellig +
    nieDaLesung/nieDaSchritt/nieDaBewiesen (Orbit V2 nach Hedge-Hand-Close) mit gespielten Fällen — ein eingefrorener Stand beendet nie.
(2) Verdrahtung: nicht frisch → nur Geist-Prüfung (frische Lesung), Ende nur über zwei frische 0-Messungen; Re-Arm nach Tab-Neuladen;
    Remote-Close „schon_zu" wird durchgereicht und nachgefasst; Hedge-Wächter ruft den Hand-Flach-Weg; kein Auto-Abhaken.
Aufruf: python3 tools/selftest_echo_geist.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def bis(anfang, ende):
    i = HTML.index(anfang)
    return HTML[i:HTML.index(ende, i) + len(ende)]


def zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


def js(prog_koerper):
    code = "\n".join([
        zeile("  function routeIstEcho(r){"),
        bis("  const ECHO_GEIST_AB_MS =", "window._echoGeist = { scharf: echoEndeScharf, faellig: echoGeistFaellig, belegMs: echoBelegMs }"),
        zeile("  const HEDGE_REVIEW_GRUENDE ="),
        zeile("  const HEDGE_REVIEW_SPAET ="),
        zeile("  const NIE_DA_LESUNGEN ="),
        bis("  function nieDaLesung(st, kontoPlan, wurzel){", "const nieDaBewiesen = st => !!(st && !st.position && st.n >= NIE_DA_LESUNGEN && st.letzte - st.erste >= NIE_DA_BEWEIS_MS)"),
        bis("  const HEDGE_HAND_AB_MS =", "window._handFlachLesung = handFlachLesung"),
    ])
    prog = "var window = {};\nvar tvSymbolWurzel = s => /MNQ/i.test(String(s)) ? 'MNQ' : 'NQ';\n" + code + "\n" + prog_koerper
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(prog)
        pfad = f.name
    try:
        out = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(pfad)
    t = (out.stdout or "").strip()
    if not t.startswith("{"):
        check(False, f"JS läuft in jsc ({(t or out.stderr)[:300]})")
        return None
    return json.loads(t)


def main():
    J = 1793300000000   # „jetzt" (ms)
    M = 60000
    r = js("""
var J = %d, M = 60000, iso = ms => new Date(ms).toISOString()
var frost = { alive: true, status: { note: 'Snapshot eingefroren — Lese-EA …', standby: true, master_positions: [], hedges: {} } }
var frisch = { alive: true, status: { note: null, master_positions: [], hedges: {} } }
var pMt5 = (b, st, start) => ({ id: 'p1', route: 'mt5', status: st || 'open', startedAt: iso(start || (J - 500*M)), mt5Baseline: b })
var out = {}
out.scharf_puls = echoEndeScharf(pMt5({ puls_spur: { ok: true, at: iso(J - 60*M) } }))
out.scharf_puls_fehler = echoEndeScharf(pMt5({ puls_spur: { ok: false, at: iso(J - 60*M) } }))
out.scharf_hand_ohne_beleg = echoEndeScharf(pMt5({ master_balance: 100000, hedge_balance: 5000, at: iso(J - 60*M) }))
out.scharf_railway = echoEndeScharf(pMt5({ echo_pos_gesehen_at: iso(J - 60*M) }))
out.scharf_schon_zu = echoEndeScharf(pMt5({ schon_zu: { at: iso(J - 60*M) } }))
out.scharf_alter_lauf = echoEndeScharf(pMt5({ puls_spur: { ok: true, at: iso(J - 900*M) }, echo_pos_gesehen_at: iso(J - 900*M), schon_zu: { at: iso(J - 900*M) } }, 'open', J - 20*M))
out.scharf_ohne_start = echoEndeScharf({ id: 'p', route: 'mt5', status: 'open', mt5Baseline: { puls_spur: { ok: true, at: iso(J - 60*M) } } })
out.scharf_v2 = echoEndeScharf({ id: 'v', route: 'mt5v2', status: 'open', mt5Baseline: { master_balance: 99000 } })
out.scharf_v2_ohne = echoEndeScharf({ id: 'v', route: 'mt5v2', status: 'open', mt5Baseline: {} })
out.scharf_tvv2 = echoEndeScharf({ id: 't', route: 'tvv2', status: 'open', mt5Baseline: { puls_spur: { ok: true } } })
var jacob = pMt5({ at: iso(J - 400*M), master_balance: 98344.31, puls_spur: { ok: true, at: iso(J - 400*M) } })
out.geist_jacob = echoGeistFaellig(jacob, frost, J, null)
out.geist_frisch = echoGeistFaellig(jacob, frisch, J, null)
out.geist_pos_im_frost = echoGeistFaellig(jacob, { alive: true, status: { note: 'Snapshot eingefroren', master_positions: [{ ident: 1 }], hedges: {} } }, J, null)
out.geist_hedge_im_frost = echoGeistFaellig(jacob, { alive: true, status: { note: 'Snapshot eingefroren', master_positions: [], hedges: { '1': [{ ticket: 9 }] } } }, J, null)
out.geist_zu_frueh = echoGeistFaellig(pMt5({ puls_spur: { ok: true, at: iso(J - 5*M) } }), frost, J, null)
out.geist_ohne_beleg = echoGeistFaellig(pMt5({ master_balance: 1, at: iso(J - 400*M) }), frost, J, null)
out.geist_abstand = echoGeistFaellig(jacob, frost, J, { n: 1, at: J - 10*M })
out.geist_wieder = echoGeistFaellig(jacob, frost, J, { n: 1, at: J - 31*M })
out.geist_max = echoGeistFaellig(jacob, frost, J, { n: 3, at: J - 300*M })
out.geist_copier_gestoppt = echoGeistFaellig(jacob, { alive: false, lesen: true, status: { note: 'warte auf Snapshot', master_positions: [], hedges: {} } }, J, null)
out.geist_review = echoGeistFaellig(pMt5(jacob.mt5Baseline, 'review'), frost, J, null)
out.geist_v2_lesen_frisch = echoGeistFaellig({ id: 'v', route: 'mt5v2', status: 'open', mt5Baseline: { master_balance: 1, at: iso(J - 60*M) } }, { alive: false, lesen: true, status: { note: null, master_positions: [] } }, J, null)
out.beleg_max = echoBelegMs(pMt5({ at: iso(J - 400*M), schon_zu: { at: iso(J - 20*M) } })) === J - 20*M
// Orbit V2 nach Hedge-Hand-Close
var hp = (h, extra) => Object.assign({ id: 'm', route: 'tvv2', status: 'open', startedAt: iso(J - 600*M), mt5Baseline: Object.assign({ hedge: h }, extra || {}) })
out.hand_faellig = hedgeHandFlachFaellig(hp({ status: 'geschlossen', grund: 'hand', closed_at: iso(J - 2*M) }), J)
out.hand_zu_frisch = hedgeHandFlachFaellig(hp({ status: 'geschlossen', grund: 'hand', closed_at: iso(J - 30000) }), J)
out.hand_tp = hedgeHandFlachFaellig(hp({ status: 'geschlossen', grund: 'tp_feed', closed_at: iso(J - 2*M) }), J)
out.hand_nie_da = hedgeHandFlachFaellig(hp({ status: 'geschlossen', grund: 'master_nie_da', closed_at: iso(J - 2*M) }), J)
out.hand_offen = hedgeHandFlachFaellig(hp({ status: 'offen', grund: null, closed_at: null }), J)
out.hand_final = hedgeHandFlachFaellig(hp({ status: 'geschlossen', grund: 'hand', closed_at: iso(J - 2*M) }, { final: { at: 'x' } }), J)
out.hand_master_da = hedgeHandFlachFaellig(hp({ status: 'geschlossen', grund: 'hand', closed_at: iso(J - 2*M) }, { hand_flach: { status: 'master_da' } }), J)
out.hand_alter_lauf = hedgeHandFlachFaellig(hp({ status: 'geschlossen', grund: 'hand', closed_at: iso(J - 700*M) }), J)
out.hand_tsv2 = hedgeHandFlachFaellig(Object.assign(hp({ status: 'geschlossen', grund: 'hand', closed_at: iso(J - 2*M) }), { route: 'tsv2' }), J)
// Beweis: Puls-Chrome-Reader, ≤ 3 s, Plan-Konto, keine NQ/MNQ-Position — 6 Lesungen über ≥ 60 s
var st = (pos, extra) => Object.assign({ an: true, positionen_ok: true, positionen: pos, positionen_tab: 'puls-1', positionen_alter_s: 1, konto: 'FTDFYSLX150393423058' }, extra || {})
out.les_flach = nieDaLesung(st([]), 'FTDFYSLX150393423058', 'MNQ')
out.les_pos = nieDaLesung(st([{ symbol: 'MNQZ6', wurzel: 'MNQ', menge_zahl: 2 }]), 'FTDFYSLX150393423058', 'MNQ')
out.les_alt = nieDaLesung(st([], { positionen_alter_s: 9 }), 'FTDFYSLX150393423058', 'MNQ')
out.les_fremd = nieDaLesung(st([], { konto: 'ANDERESKONTO1' }), 'FTDFYSLX150393423058', 'MNQ')
out.les_nicht_puls = nieDaLesung(st([], { positionen_tab: 'haupt' }), 'FTDFYSLX150393423058', 'MNQ')
out.hf_nq_versteckt = handFlachLesung(st([{ symbol: 'NQZ6', wurzel: 'NQ', menge_zahl: 1 }]), 'FTDFYSLX150393423058')
out.hf_flach = handFlachLesung(st([]), 'FTDFYSLX150393423058')
out.hf_alt = handFlachLesung(st([], { positionen_alter_s: 9 }), 'FTDFYSLX150393423058')
var s = null; for(var i = 0; i < 6; i++) s = nieDaSchritt(s, 'flach', J + i * 12000)
out.beweis_6x60 = nieDaBewiesen(s)
var s2 = null; for(var i = 0; i < 5; i++) s2 = nieDaSchritt(s2, 'flach', J + i * 15000)
out.beweis_5 = nieDaBewiesen(s2)
var s3 = null, t3 = [0, 12000, 24000, 44000, 56000, 68000, 80000]; for(var i = 0; i < t3.length; i++) s3 = nieDaSchritt(s3, 'flach', J + t3[i])   // Lücke 20 s zwischen 24 und 44 s
out.beweis_luecke = nieDaBewiesen(s3)
var s4 = null; for(var i = 0; i < 8; i++) s4 = nieDaSchritt(s4, i === 2 ? 'position' : 'flach', J + i * 12000)
out.beweis_pos = nieDaBewiesen(s4)
print(JSON.stringify(out))
""" % J)
    if r:
        check(r["scharf_puls"] and not r["scharf_puls_fehler"], "Echo mit Hedge: Puls-Spur ok macht die Ende-Erkennung nach dem Neuladen scharf, Fehl-Spur nicht")
        check(not r["scharf_hand_ohne_beleg"], "Hand-„Läuft“ nur mit Baseline-Balancen (kein Positions-Beleg) bleibt unscharf — kein falsches Ende vor dem Einstieg")
        check(r["scharf_railway"] and r["scharf_schon_zu"], "Beleg auch aus echo_pos_gesehen_at (Railway) und schon_zu (Close-Antwort)")
        check(not r["scharf_alter_lauf"] and not r["scharf_ohne_start"], "Belege aus einem früheren Lauf (wiederverwendeter Plan) oder ohne startedAt machen nie scharf")
        check(r["scharf_v2"] and not r["scharf_v2_ohne"] and not r["scharf_tvv2"], "Echo V2 wie bisher über die Start-Baseline; andere Routen nie")
        check(r["geist_jacob"], "Jacob-Fall (Copier eingefroren, letzter Stand flach, 6 h nach Puls-Klick) → frische Lesung anstoßen")
        check(not r["geist_frisch"], "frischer Stand → keine Geist-Prüfung (normaler Weg)")
        check(not r["geist_pos_im_frost"] and not r["geist_hedge_im_frost"], "eingefrorener Stand mit Position oder Hedge → nichts anstoßen (Alarm-Weg)")
        check(not r["geist_zu_frueh"] and not r["geist_ohne_beleg"], "erst 10 min nach dem Beleg, nie ohne Beleg")
        check(not r["geist_abstand"] and r["geist_wieder"] and not r["geist_max"], "höchstens 3 Versuche im Abstand von 30 min")
        check(not r["geist_copier_gestoppt"], "mit Hedge: gestoppter Copier → keine (wirkungslose) Lesung")
        check(not r["geist_review"] and not r["geist_v2_lesen_frisch"], "nur offene Pläne; V2 mit frischer Lese-Instanz → normaler Weg")
        check(r["beleg_max"], "Beleg-Zeit = jüngster Beleg (schon_zu nach Puls-Spur)")
        check(r["hand_faellig"] and not r["hand_zu_frisch"], "Orbit V2: Hedge von Hand zu ≥ 60 s, Plan open → Flach-Prüfung")
        check(not r["hand_tp"] and not r["hand_nie_da"], "TP/SL-Gründe und master_nie_da behalten ihre eigenen Wege")
        check(not r["hand_offen"] and not r["hand_final"] and not r["hand_master_da"] and not r["hand_tsv2"],
              "nicht bei offenem Hedge, schon gesetztem final, bewiesener Master-Position oder anderer Route")
        check(not r["hand_alter_lauf"], "Hedge-Schluss aus einem früheren Lauf zählt nie")
        check(r["hf_nq_versteckt"] == "position" and r["hf_flach"] == "flach" and r["hf_alt"] is None, "Flach nur, wenn weder NQ noch MNQ steht — falsche Wurzel versteckt nichts")
        check(r["les_flach"] == "flach" and r["les_pos"] == "position", "Reader-Lesung: Plan-Konto flach / mit MNQ-Position")
        check(r["les_alt"] is None and r["les_fremd"] is None and r["les_nicht_puls"] is None, "alt (> 3 s), fremdes Konto, kein Puls-Chrome → keine Aussage")
        check(r["beweis_6x60"] and not r["beweis_5"] and not r["beweis_luecke"] and r["beweis_pos"] is False,
              "Beweis erst mit ≥ 6 Lesungen über ≥ 60 s ohne Lücke > 15 s; eine Position stoppt ihn")

    # (2) Verdrahtung
    tick = HTML[HTML.index("  async function mt5PlanPollTick(){"):HTML.index("        /* ECHO V2 (24.09.2026): Ende = Master flach")]
    check("if(!fresh){ if(plan.status === 'open') echoGeistAnstossen(plan, route); continue }" in tick,
          "mt5PlanPollTick: nicht frisch → nur Geist-Prüfung, kein Ende")
    check("else if(!istV2 && echoEndeScharf(plan)) mt5PlanPoll.wasOpen.add(String(plan.id))" in tick
          and tick.index("echoEndeScharf(plan)) mt5PlanPoll.wasOpen") < tick.index("if(!mt5PlanPoll.wasOpen.has(String(plan.id))) continue")
          and "if(n < 2) continue" in tick, "Re-Arm vor der Streak-Prüfung; Ende weiter erst nach 2 frischen 0-Messungen")
    an = HTML[HTML.index("  function echoGeistAnstossen(plan, route){"):HTML.index("  async function echoSchonZuNachfassen(")]
    check("ebnStartNah()" in an and "polarLaeuft()" in an and "mt5KontoBalanceJetzt(" in an and "status: 'review'" not in an and "atMoveToReview" not in an,
          "Geist-Prüfung: nur frisch lesen (mt5KontoBalanceJetzt), nicht vor einem Start/bei Polar, beendet selbst nichts")
    sz = HTML[HTML.index("  async function echoSchonZuNachfassen("):HTML.index("  async function mt5PlanAufOpen(")]
    check("schon_zu: {" in sz and "'open')" in sz and "atMoveToReview" not in sz and "status: 'review'" not in sz,
          "schon_zu: Beleg am Plan (Guard open) + Lesung, kein Ende aus der Antwort allein")
    rc = HTML[HTML.index("const r = await window.mtcApi(`master-close?file=${encodeURIComponent(routeC.inst.file)}`"):][:1400]
    check("schon_zu: r.schon_zu === true || undefined" in rc and "if(r && r.ok && r.schon_zu === true) echoSchonZuNachfassen(plan, r, t.ticket)" in rc,
          "Remote-Close Echo: schon_zu im Signal-Ergebnis + nachfassen")
    wt = HTML[HTML.index("  async function hedgeWacheTick(){"):HTML.index("  function hedgeMasterWegStatus(")]
    check("if(hedgeHandFlachFaellig(p, Date.now())){ try{ await hedgeHandFlachPruefen(p) }" in wt, "Hedge-Wächter ruft den Hand-Flach-Weg (nur am Hedge-PC, Liste 'meine')")
    hf = HTML[HTML.index("  async function hedgeHandFlachPruefen(p){"):HTML.index("  async function hedgeNieDaPruefen(p){")]
    check("hedgeSperre(pid, 'waechter', 20)" in hf and "frisch.status !== 'open'" in hf and "tvV2EndeSetzen(frisch, null, 'reader_flach'" in hf
          and "if(h.pl == null && h.pl_offen) return" in hf and "status: 'completed'" not in hf,
          "Hand-Flach: Sperre, frisch aus der DB, Fusion-P&L zuerst, Ende ohne Zahl (→ Puls-Endlesung), nie abgehakt")
    check("status: 'completed'" not in an and "abhaken" not in sz.lower(), "kein Auto-Abhaken (Testphase)")
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
