#!/usr/bin/env python3
"""Selbsttest EIN FINALER TRADEIFY JE ID (21.10.2026, Slave 4 — Finn ~23:45 Dubai über Master: „bei den Tradeify finalen Trades immer nur 1
gleichzeitig pro ID … nicht dass dann bei Aurel alle 3 gleichzeitig starten und alle blowen").

Ohne Netz, ohne Postgres, ohne Node:
  SQL (sql/2026-10-21_tradeify_ein_finaler_je_id.sql): Final-Erkennung mit DEM Regex aus der Datei gegen die Notiz-Formate der DB
  (letzter Trade · Klein-Trade · Etappe mit TP < / ≥ Rest · Tage sammeln · Hand ohne Notiz · deutsche Zahlen), dazu der Vertrag:
  Schalter nur Tradeify, „läuft" wie der Gegenrichtungs-Riegel (open / review ohne prophos_plan_gelesen, 72 h) + geclaimt < 10 min,
  Claim-Trigger BEFORE UPDATE OF start_um_gestartet_at (null → gesetzt), Advisory-Lock je ID × Firma VOR der Prüfung, return null,
  start_um + 10–20 min gewürfelt, start_sperre + Protokoll „[ein finaler Tradeify je ID]", ROLLBACK-Probe, Rückbau.
  (Die Datei lief am 21.10.2026 als DO-Block mit erzwungenem Abbruch gegen Supabase: Claims A=1, B=0 → +10,6 min, C/Etappe=1; nichts blieb.)
  Frontend per macOS-JavaScriptCore (jsc): efFrei (RPC-Fehler = frei), efVerschieben (Claim zurück nur ohne Orbit-Sendung, 10–20 min,
  start_sperre art ein_finaler, Protokoll), tpStartSperre (eigener Satz), Einbau in tpOrbitStartenKern (nach dem Richtungsschutz, vor
  Duplikum, nur Puls-V2; Fern-Start meldet, Startzeit verschiebt, Karten-Klick sperrt). Alle Kennungen erfunden.
Aufruf: python3 tools/selftest_ein_finaler.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
SQL = os.path.join(HIER, "..", "sql", "2026-10-21_tradeify_ein_finaler_je_id.sql")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_abhaken_geblowt_vorbelegen.py)."""
    i = src.index(f"function {name}(")
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


def sql_block(sql, name):
    i = sql.index(f"create or replace function public.{name}(")
    return sql[i:sql.index("end $$;", i) + 7]


def final_text_py(sql, notes, tp):
    """prophos_plan_final_text nachgebaut — Muster und Reihenfolge AUS der SQL-Datei gelesen, nicht abgeschrieben."""
    blk = sql_block(sql, "prophos_plan_final_text")
    nie = re.search(r"if n ~ '([^']+)' then\s+return false;", blk).group(1)
    ja = re.search(r"if n ~ '([^']+)' then\s+return true;", blk).group(1)
    rest_rx = re.search(r"substring\(n from '([^']+)'\)", blk).group(1)
    n = notes or ""
    if re.search(nie, n):
        return False
    if re.search(ja, n):
        return True
    m = re.search(rest_rx, n)
    if not m:
        return None
    rest = float(m.group(1).replace(".", "").replace(",", "."))
    if rest <= 0:
        return True
    return (tp or 0) > 0 and tp >= rest


FAELLE_SQL = [  # (Notiz wie in der DB 21.10.2026, TP, erwartet)
    ("Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)", 2300, True),
    ("Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)\n✎ Hand 21.10. 23:50: TP 2300 → 2400", 2400, True),
    ("Auto-Planer · Klein-Trade · Rest 84 $ · 0,5 Lots · TP 120 $ (Rest + Puffer 36 $)", 120, True),
    ("Auto-Planer · Etappe · Rest 5.472 $ bis Ziel · Balance 153.528 (TV)", 3532, False),
    ("Auto-Planer · Etappe · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)", 2100, True),        # TP ≥ Rest = final, auch als Etappe
    ("Auto-Planer · Etappe · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)", 2049, False),
    ("Auto-Planer · Etappe · Rest 1.234,50 $ bis Ziel", 1234.5, True),
    ("Auto-Planer · Etappe, SL hinter den Boden (+300 $) · Rest 9.000 $ bis Ziel · Balance 150.000 (Echo)", 3500, False),
    ("Auto-Planer · Tage sammeln 3/5 · Mini-Trade 0,01 Lot · TP 20 Pkt (40 $) / SL 30 Pkt (60 $)", 9999, False),
    (None, 15000, None),                                                                       # Hand ohne Notiz → Konto-Rückfall
    ("Winning-Day-Farmer", 300, None),
]

JS_TEST = r"""
const LOG = []
let RPC = null, UPD = null, PATCH = null, PROT = null, TOASTS = []
const supabase = {
  rpc: (fn, args) => { LOG.push(['rpc', fn, args]); return RPC === 'wurf' ? Promise.reject(new Error('netz')) : Promise.resolve(RPC) },
  from: tab => ({ update: v => { const q = { v, f: [] }
    const k = { eq: (a, b) => { q.f.push(['eq', a, b]); return k }, is: (a, b) => { q.f.push(['is', a, b]); return k },
      select: () => { UPD = q; return Promise.resolve(globalThis._updAntwort(q)) } }
    return k } })
}
function rkPlanErsetzen(row){ return { id: row.id, startUm: row.start_um } }
async function baselinePatch(id, obj, st){ PATCH = { id, obj, st } }
function rkProtokoll(plan, e){ PROT = e }
function tpStartUmText(iso){ return 'um ' + String(iso).slice(11, 16) }
function atToast(t){ TOASTS.push(t) }
function renderTradePlans(){}
const _console = []; const console = { warn: (...a) => _console.push(a.join(' ')) }
%s
const P = { id: 'p-2', masterName: '150k …9050', masterFirm: 'Tradeify', richtung: 'buy', startUm: '2026-10-21T20:00:00.000Z',
            mt5Baseline: { start_sperre: { art: 'ein_finaler', versuche: 2 } } }
const aus = {}
;(async () => {
  RPC = { data: { frei: false, grund: '„150k …7608“ läuft als finaler Trade', plan: 'p-1' }, error: null }
  aus.gesperrt = await efFrei(P)
  aus.rpc = LOG[0]
  RPC = { data: null, error: { message: 'Could not find the function public.prophos_ein_finaler_frei' } }
  aus.fehlt = await efFrei(P)
  RPC = 'wurf'
  aus.wurf = await efFrei(P)
  RPC = { data: { frei: true }, error: null }
  aus.frei = await efFrei(P)
  const t0 = Date.now()
  globalThis._updAntwort = q => ({ data: [{ id: P.id, start_um: q.v.start_um }], error: null })
  aus.um = await efVerschieben(P, { grund: '„150k …7608“ läuft als finaler Trade', plan: 'p-1' })
  aus.upd = UPD; aus.min = (Date.parse(UPD.v.start_um) - t0) / 60000; aus.patch = PATCH; aus.prot = PROT; aus.toast = TOASTS[0]
  globalThis._updAntwort = q => ({ data: [], error: null })
  aus.weg = await efVerschieben(P, { grund: 'x' })
  // Jitter: 40 Würfe, nie derselbe Wert, alle in 10–20 min
  const w = []
  globalThis._updAntwort = q => ({ data: [{ id: P.id, start_um: q.v.start_um }], error: null })
  for(let i = 0; i < 40; i++){ const t1 = Date.now(); await efVerschieben(P, { grund: 'x' }); w.push((Date.parse(UPD.v.start_um) - t1) / 60000) }
  aus.jitter = { min: Math.min(...w), max: Math.max(...w), n: new Set(w.map(x => x.toFixed(4))).size }
  const jetzt = new Date().toISOString(), naechster = new Date(Date.now() + 14 * 60000).toISOString()
  aus.sperre = tpStartSperre({ status: 'planned', startUmGestartetAt: null, mt5Baseline: { start_sperre: { art: 'ein_finaler', text: 'Tradeify: „150k …7608“ läuft als finaler Trade — je ID nur ein finaler Tradeify-Trade gleichzeitig — Start frühestens 00:10:21', at: jetzt, naechster, versuche: 3 } } })
  aus.richtung = tpStartSperre({ status: 'planned', startUmGestartetAt: null, mt5Baseline: { start_sperre: { art: 'richtung', text: 'x', at: jetzt, naechster } } })
  aus.alt = tpStartSperre({ status: 'planned', startUmGestartetAt: null, mt5Baseline: { start_sperre: { art: 'ein_finaler', text: 'x', at: '2026-10-01T00:00:00Z' } } })
  aus.claim = tpStartSperre({ status: 'planned', startUmGestartetAt: jetzt, mt5Baseline: { start_sperre: { art: 'ein_finaler', text: 'x', at: jetzt } } })
  aus.konsole = _console.length
  print(JSON.stringify(aus))
})().catch(e => print(JSON.stringify({ fehler: String(e && e.stack || e) })))
"""


def main():
    sql = open(SQL, encoding="utf-8").read()
    html = open(HTML, encoding="utf-8").read()

    # ── SQL: Erkennung ─────────────────────────────────────────────────────────
    for notes, tp, soll in FAELLE_SQL:
        ist = final_text_py(sql, notes, tp)
        check(ist is soll, f"final_text {str(notes or '(keine Notiz)').splitlines()[0][:70]!r} TP {tp} → {ist}")

    # ── SQL: Vertrag ───────────────────────────────────────────────────────────
    i0 = sql.index("create or replace function public.prophos_ein_finaler_firmen()\nreturns")   # nicht die Abschalt-Zeile im Kopf
    firmen = sql[i0:sql.index("$$;", sql.index("as $$", i0) + 5)]   # language sql: endet auf „$$;", nicht „end $$;"
    check(re.search(r"select array\[public\.prophos_firma_key\('Tradeify'\)\]", sql) is not None and firmen.count("prophos_firma_key(") == 1,
          "Schalter je Firma: nur Tradeify an")
    frei = sql_block(sql, "prophos_ein_finaler_frei")
    check("p.status in ('open', 'review')" in frei and "not (p.status = 'review' and public.prophos_plan_gelesen(p.id))" in frei
          and "interval '72 hours'" in frei, "läuft = open / review ohne Endlesung, 72 h (wie der Gegenrichtungs-Riegel)")
    check("p.status = 'planned' and p.started_at is null" in frei and "coalesce(p.orbit_gesendet_at, p.start_um_gestartet_at) > now() - interval '10 minutes'" in frei,
          "geclaimt/gesendet < 10 min zählt mit")
    check("p.user_id = pl.user_id" in frei and "public.prophos_firma_key(p.master_firm) = k" in frei and "p.id <> pl.id" in frei
          and "public.prophos_plan_final(p.id)" in frei, "nur dieselbe ID × Firma, nur finale Gegenstücke, nie der Plan selbst")
    check(frei.index("public.prophos_plan_final(pl.id)") < frei.index("from public.trade_plans p"), "nicht finale Pläne (Etappen) sind sofort frei")
    trg = sql_block(sql, "trade_plans_ein_finaler")
    check(trg.index("pg_advisory_xact_lock") < trg.index("prophos_ein_finaler_frei(new.id)"), "Advisory-Lock je ID × Firma VOR der Prüfung (zwei Claims gleichzeitig)")
    check("new.user_id::text || ':' || k" in trg, "Lock-Schlüssel = ID + Firma")
    check("return null;" in trg and "interval '10 minutes' + make_interval(secs => floor(random() * 600))" in trg, "Sperre: Claim scheitert, Start + 10–20 min gewürfelt")
    check("'art', 'ein_finaler'" in trg and "'[ein finaler Tradeify je ID] '" in trg and "auto_plan_umplanung" in trg, "Grund an den Plan (start_sperre) + Protokoll")
    check(re.search(r"create trigger trade_plans_ein_finaler\s+before update of start_um_gestartet_at on public\.trade_plans\s+for each row when "
                    r"\(old\.start_um_gestartet_at is null and new\.start_um_gestartet_at is not null\)", sql) is not None,
          "Claim-Trigger wie trade_plans_gegenhedge (null → gesetzt)")
    check("trade_plans_ein_finaler" < "trade_plans_firmen_abstand" and "trade_plans_big_trade" < "trade_plans_ein_finaler",
          "Trigger-Reihenfolge: big_trade → ein_finaler → firmen_abstand → gegenhedge")
    check(re.search(r"^-- begin;", sql, re.M) is not None and re.search(r"^-- rollback;", sql, re.M) is not None, "ROLLBACK-Probe in der Datei")
    rueck = ["drop trigger if exists trade_plans_ein_finaler", "drop function if exists public.trade_plans_ein_finaler()",
             "drop function if exists public.prophos_ein_finaler_frei(uuid)", "drop function if exists public.prophos_plan_final(uuid)",
             "drop function if exists public.prophos_plan_final_text(text, numeric)", "drop function if exists public.prophos_ein_finaler_firmen()"]
    check(all(("--   " + r) in sql for r in rueck), "Rückbau-Befehle vollständig im Kopf")
    check("security definer" in frei and "grant execute on function public.prophos_ein_finaler_frei(uuid) to authenticated" in sql,
          "Tab darf die Leseprüfung als RPC rufen")

    # ── Frontend ───────────────────────────────────────────────────────────────
    if not os.path.exists(JSC):
        check(False, "jsc fehlt — Frontend-Teil nicht ausführbar")
    else:
        # js_funktion schneidet ab „function" — die beiden sind async
        js = "\n".join(["async " + js_funktion(html, "efFrei"), "async " + js_funktion(html, "efVerschieben"), js_funktion(html, "tpStartSperre")])
        js = JS_TEST % js
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        try:
            r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(f.name)
        try:
            a = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            a = {"fehler": (r.stdout + r.stderr)[-800:]}
        if "fehler" in a:
            check(False, "jsc: " + a["fehler"])
        else:
            check(a["gesperrt"].get("frei") is False and a["rpc"][1] == "prophos_ein_finaler_frei" and a["rpc"][2] == {"p_plan": "p-2"},
                  "efFrei: RPC prophos_ein_finaler_frei(p_plan) → gesperrt")
            check(a["fehlt"] is None and a["wurf"] is None and a["frei"] == {"frei": True} and a["konsole"] >= 2,
                  "efFrei: Funktion fehlt / Netzfehler → null (= frei, DB bleibt die Linie), mit Warnung")
            u = a["upd"]
            check(u["v"].get("start_um_gestartet_at", "x") is None and ["eq", "status", "planned"] in u["f"] and ["is", "orbit_gesendet_at", None] in u["f"],
                  "efVerschieben: Claim zurück nur, solange nichts an Orbit gesendet ist")
            check(10 <= a["min"] <= 20.01, f"efVerschieben: neue Startzeit in 10–20 min ({a['min']:.1f})")
            j = a["jitter"]
            check(j["min"] >= 10 and j["max"] <= 20.01 and j["n"] >= 35, f"Jitter: 40 Würfe in 10–20 min, {j['n']} verschiedene")
            sp = a["patch"]["obj"]["start_sperre"]
            check(sp["art"] == "ein_finaler" and sp["plan"] == "p-1" and sp["versuche"] >= 3 and a["patch"]["st"] == "planned",
                  "efVerschieben: start_sperre art ein_finaler, Versuche zählen hoch, nur planned")
            check(a["prot"]["grund"].startswith("[ein finaler Tradeify je ID] Tradeify: „150k …7608“") and "Versuch 3" in a["prot"]["grund"],
                  f"Protokoll: {a['prot']['grund'][:80]}")
            check(a["um"].startswith("um ") and "wartet" in a["toast"] and a["weg"] == "", "Toast mit neuer Startzeit; nicht mehr verschiebbar → ''")
            check(a["sperre"] and a["sperre"]["kurz"].startswith("⛔ Wartet: nur ein finaler Trade je ID · neuer Versuch") and "Versuch 3" in a["sperre"]["kurz"]
                  and "Start frühestens" not in a["sperre"]["voll"] and "gelesen" in a["sperre"]["voll"], f"Karten-Chip: {a['sperre'] and a['sperre']['kurz']}")
            check(a["richtung"] and "Richtungsschutz" in a["richtung"]["kurz"], "Richtungsschutz-Chip unverändert")
            check(a["alt"] is None and a["claim"] is None, "alte Sperre (> 30 min) und geclaimter Plan: kein Chip")

        i = html.index("async function tpOrbitStartenKern(")
        kern = html[i:html.index("// DUPLIKUM-CHECK ZUERST", i)]
        e = kern.index("const ef = await efFrei(plan)")
        check(kern.index("if(pv2){") < kern.index("v2RichtungKonflikt") < e, "Start-Wächter nach dem Richtungsschutz, im Puls-V2-Zweig, vor Duplikum/Puls")
        rest = kern[e:]
        check("if(fern) return fern.melde({ ok:false, msg: t })" in rest and "opts && opts.vonStartUm" in rest and "await efVerschieben(plan, ef)" in rest
              and "toast('⛔ ' + t, 'end'); return" in rest, "Fern-Start meldet, Startzeit verschiebt, Karten-Klick sperrt")
        check(html.count("efFrei(") == 2 and html.count("efVerschieben(") == 2, "genau ein Aufruf je Funktion (keine zweite Stelle)")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("alle Prüfungen bestanden")


if __name__ == "__main__":
    main()
