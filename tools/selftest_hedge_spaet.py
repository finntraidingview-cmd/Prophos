#!/usr/bin/env python3
"""Selbsttest SPÄTER HEDGE + KONTENLISTE (30.10.2026, Master nach Plan 27ef28f4: Order 14:38:49, Nachholen öffnete 14:43:42 trotz Hand-Hedge; Konto
14:32:28 angelegt, drei Fehlstarts „keine External ID"). Grenze: 89 s öffnet, 90 s öffnet, 91 s öffnet nicht und alarmiert. Funktionen per macOS-JavaScript
(jsc) aus prophos.html geschnitten, Supabase/Kern als Attrappe; Alarm über alarm_ereignisse aus app.py (Lader von selftest_alarme). Ohne Netz, Zahlen erfunden.
Aufruf: python3 tools/selftest_hedge_spaet.py"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
APP = os.path.join(HIER, "..", "app.py")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung, Kopf über die Parameter-Klammer (wie tools/selftest_pulsmodus.py)."""
    i = src.index(f"function {name}(")
    if src[max(0, i - 6):i] == "async ":
        i -= 6
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


JS = r"""
const MT5_LOCAL = true, hedgePcId = () => 'pc-xxxxxx'
const HEDGE_SPAET_MAX_MS = 90000
const _hedgeSpaetToast = new Set()
let LOG, HEDGE_DB, EIGEN
const window = { mtcApi: () => {} }
const atToast = t => LOG.toast.push(t)
const hedgeSoloOeffnenKern = async () => { LOG.kern++; return { ticket: 1 } }
const hedgeSoloEigen = () => EIGEN
let _tpKontoNeuP = null
const hedgeAmPlanSchreiben = async (id, f) => { LOG.vermerk.push(f) }
const supabase = { from: () => ({ select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: { mt5_baseline: { hedge: HEDGE_DB } } }) }) }) }) }
%FUNKTIONEN%
const PLAN = { id: 'p1', hedgeEur: 100, route: 'tvv2', masterName: 'Test', startedAt: null }
const JETZT = Date.now()
async function fall(name, r, o){
  LOG = { kern: 0, vermerk: [], toast: [] }; HEDGE_DB = (o && o.hedge) || null; EIGEN = (o && o.eigen) || null
  const erg = await hedgeSoloOeffnen(Object.assign({}, PLAN, (o && o.plan) || {}), r)
  return { name, kern: LOG.kern, code: LOG.vermerk[0] && LOG.vermerk[0].grund_code, st: LOG.vermerk[0] && LOG.vermerk[0].status, alter: LOG.vermerk[0] && LOG.vermerk[0].alter_s, msg: LOG.vermerk[0] && LOG.vermerk[0].msg, toast: LOG.toast.length, erg: erg && (erg.ticket || erg.status) }
}
const vor = s => JETZT - s * 1000
const iso = s => new Date(vor(s)).toISOString()
async function kontoFall(name, liste, nach, neuAt){
  accounts = liste; _tpKontoNeuAt = neuAt || 0; let geladen = 0
  loadAccountsFromSupabase = async () => { geladen++; accounts = nach }
  const a = await tpKontoMitExtId({ masterAccountId: 'k1' })
  return { name, geladen, ext: a ? (a.externalId || '') : null }
}
var accounts = [], _tpKontoNeuAt = 0, loadAccountsFromSupabase
(async () => {
  const aus = []
  aus.push(await fall('89', { order_klick_ms: vor(89) }))
  aus.push(await fall('90', { order_klick_ms: vor(90) + 500 }))
  aus.push(await fall('91', { order_klick_ms: vor(91) }))
  aus.push(await fall('91_iso', { klick_at: iso(91) }))
  aus.push(await fall('294_nachholen', { klick_at: iso(294), nachgeholt: true }))
  aus.push(await fall('selbstheilung', { klick_at: iso(150), nachgeholt: true }))
  aus.push(await fall('altes_ticket', { order_klick_ms: vor(300) }, { hedge: { status: 'geschlossen', ticket: 5, opened_at: iso(3600) } }))
  aus.push(await fall('frisch_zu', { order_klick_ms: vor(300) }, { hedge: { status: 'geschlossen', ticket: 5, opened_at: iso(120) } }))
  aus.push(await fall('manuell', { klick_at: iso(500), manuell: true }))
  aus.push(await fall('rueckkehr', { klick_at: iso(500), rueckkehr: true }))
  aus.push(await fall('ohne_zeit', {}))
  aus.push(await fall('hat_ticket', { order_klick_ms: vor(300) }, { hedge: { status: 'offen', ticket: 7 } }))
  aus.push(await fall('eigene_position', { order_klick_ms: vor(300) }, { eigen: { ticket: 9 } }))
  aus.push(await fall('frueh_und_ende', { order_klick_ms: vor(300) }))
  aus.push(await kontoFall('konto_neu', [], [{ id: 'k1', externalId: 'X1' }]))
  aus.push(await kontoFall('id_leer_dann_da', [{ id: 'k1', externalId: '' }], [{ id: 'k1', externalId: 'X1' }]))
  aus.push(await kontoFall('schon_da', [{ id: 'k1', externalId: 'X1' }], []))
  aus.push(await kontoFall('sperre_15s', [], [{ id: 'k1', externalId: 'X1' }], Date.now() - 1000))
  aus.push(await kontoFall('fehlt_auch_nachher', [], []))
  print('ERG' + JSON.stringify(aus))
})().catch(e => print('ERR ' + e + ' ' + (e && e.stack)))
"""


def main():
    src = open(HTML, encoding="utf-8").read()
    teile = [js_funktion(src, n) for n in ("hedgeSpaetAlterS", "hedgeSpaetVermerken", "hedgeSoloOeffnen", "tpKontoMitExtId")]
    code = JS.replace("%FUNKTIONEN%", "\n".join(teile))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=30).stdout
    os.unlink(f.name)
    zeile = next((z for z in out.splitlines() if z.startswith("ERG")), None)
    if not zeile:
        print(out[:800])
        check(False, "jsc-Lauf liefert Ergebnis")
        return
    e = {x["name"]: dict({"code": None, "st": None, "alter": None, "msg": None, "erg": None, "ext": None}, **x) for x in json.loads(zeile[3:])}
    check(e["89"]["kern"] == 1 and not e["89"]["code"], "89 s: öffnet wie bisher, kein Vermerk")
    check(e["90"]["kern"] == 1 and not e["90"]["code"], "90 s: öffnet noch")
    check(e["91"]["kern"] == 0 and e["91"]["code"] == "zu_spaet" and e["91"]["st"] == "uebersprungen" and e["91"]["alter"] == 91, "91 s: öffnet nicht, Vermerk zu_spaet mit Alter")
    check("Hedge fehlt, von Hand prüfen" in (e["91"]["msg"] or ""), "Vermerk nennt „Hedge fehlt, von Hand prüfen“")
    check(e["91_iso"]["kern"] == 0 and e["91_iso"]["code"] == "zu_spaet", "91 s über klick_at")
    check(e["294_nachholen"]["kern"] == 0 and e["294_nachholen"]["alter"] == 294, "Nachholen 294 s (Vorfall): öffnet nicht")
    check(e["selbstheilung"]["kern"] == 0 and e["selbstheilung"]["code"] == "zu_spaet", "Selbstheilung: startedAt 150 s alt, öffnet nicht")
    check(e["altes_ticket"]["code"] == "zu_spaet", "Ticket eines früheren Versuchs: gilt nicht als Hedge dieses Starts, Vermerk + Alarm")
    check(e["frisch_zu"]["erg"] == 5 and not e["frisch_zu"]["code"], "dieser Start hatte seinen Hedge (zu nach < 10 min): kein Vermerk")
    check(e["manuell"]["kern"] == 1 and not e["manuell"]["code"], "Knopf „Hedge öffnen“ bleibt frei")
    check(e["rueckkehr"]["kern"] == 1, "Rückkehr-Wache bleibt frei")
    check(e["ohne_zeit"]["kern"] == 1 and not e["ohne_zeit"]["code"], "Zeit unbekannt: wie bisher")
    check(e["hat_ticket"]["kern"] == 0 and not e["hat_ticket"]["code"] and e["hat_ticket"]["erg"] == 7, "Hedge steht schon: kein Vermerk darüber")
    check(e["eigene_position"]["kern"] == 1 and not e["eigene_position"]["code"], "Position mit Plan-Kennung liegt: Kern übernimmt sie")
    check(e["konto_neu"]["geladen"] == 1 and e["konto_neu"]["ext"] == "X1", "Konto fehlt: Liste einmal laden, gefunden")
    check(e["id_leer_dann_da"]["geladen"] == 1 and e["id_leer_dann_da"]["ext"] == "X1", "External ID leer: Liste laden, gefunden")
    check(e["schon_da"]["geladen"] == 0 and e["schon_da"]["ext"] == "X1", "Konto mit ID da: nichts geladen")
    check(e["sperre_15s"]["geladen"] == 0, "höchstens einmal je 15 s")
    check(e["fehlt_auch_nachher"]["geladen"] == 1 and e["fehlt_auch_nachher"]["ext"] is None, "fehlt auch danach: Meldung bleibt dem Aufrufer")

    # Quelltext-Vertrag: ein einziger Open-Auftrag (im Kern), jeder Selbst-Weg über den Wrapper, beide External-ID-Stellen laden nach
    check(src.count("aktion: 'open'") == 1, "genau ein Open-Auftrag an den Copier")
    check(src.count("hedgeSoloOeffnenKern(") == 2, "Kern nur über den Wrapper erreichbar")
    kern = js_funktion(src, "hedgeSoloOeffnenKern")
    check("hedgeSpaetAlterS(plan, r, Date.now())" in kern, "Wiederholschleife prüft die Grenze")
    check("Date.now() + 450000" in js_funktion(src, "hedgeFruehWache"), "Früh-Wache überdauert den Lauf (Klick bis 161 s nach Laufstart gemessen)")
    check("}finally{ if(_hedgeFrueh) _hedgeFrueh.stop = true }" in src, "Früh-Wache endet auch bei einer Ausnahme im Lauf")
    check(src.count("await tpKontoMitExtId(plan)") == 2, "beide Stellen vor „keine External ID“ laden nach")

    # Alarm
    sys.path.insert(0, HIER)
    import selftest_alarme
    ns = selftest_alarme.lade()
    jetzt = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    seit = (jetzt - timedelta(minutes=20)).isoformat()
    plan = {"id": "p1", "user_id": "u1", "status": "open", "route": "tvv2", "orbit_v3": True, "hedge_eur": 100, "master_name": "Konto", "master_firm": "Firma",
            "started_at": (jetzt - timedelta(seconds=30)).isoformat(),
            "hedge": {"status": "uebersprungen", "grund_code": "zu_spaet", "alter_s": 91, "at": (jetzt - timedelta(seconds=5)).isoformat()}}
    ev = [x for x in ns["alarm_ereignisse"]([plan], {"u1": "Wer"}, jetzt, seit) if x[2] == "hedge_zu_spaet"]
    check(len(ev) == 1 and ev[0][1] == 1 and "91 s" in ev[0][4], "91 s: 🔴 an die Master-IDs")
    p2 = json.loads(json.dumps(plan))
    p2["hedge"]["grund_code"] = "master_flach"
    check(not [x for x in ns["alarm_ereignisse"]([p2], {"u1": "Wer"}, jetzt, seit) if x[2] == "hedge_zu_spaet"], "anderer Überspring-Grund: kein Zu-spät-Alarm")
    p3 = json.loads(json.dumps(plan))
    p3["hedge"]["at"] = (jetzt - timedelta(hours=1)).isoformat()
    check(not [x for x in ns["alarm_ereignisse"]([p3], {"u1": "Wer"}, jetzt, seit) if x[2] == "hedge_zu_spaet"], "alter Vermerk: nicht noch einmal")


if __name__ == "__main__":
    main()
    if FEHLER:
        print(f"FEHLER: {len(FEHLER)}")
        sys.exit(1)
    print("OK — später Hedge + Kontenliste grün")
