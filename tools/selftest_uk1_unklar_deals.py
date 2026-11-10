"""UK1 (10.11.2026): geplante Echo-Pläne mit UNKLAR-Startmarke werden über die Deal-Prüfung (N2, deUrteil) geklärt; nur „nicht gelaufen" löst die Marke
(start_fehler.status 'behoben' + Beleg). Schneidet ukKandidat, ukGeloest und deUrteil aus prophos.html und prüft sie in JavaScriptCore (ohne Node).
Aufruf: python3 tools/selftest_uk1_unklar_deals.py"""
import json, os, subprocess, sys, tempfile
HIER = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
def schnitt(a, e):
    i = html.index(a); return html[i:html.index(e, i)]
js = "const window = {};\n" + schnitt("  function deUrteil(res, refBal){", "  window._deUrteil") + \
     schnitt("  const UK_CLAIM_MIN_MS", "  async function ukErgebnis(") + r"""
const J = Date.parse('2026-11-10T12:00:00Z'), vor = m => new Date(J - m * 60000).toISOString()
const plan = (o, b) => Object.assign({ status: 'planned', route: 'mt5', started_at: null, orbit_gesendet_at: null, start_um_gestartet_at: vor(30), master_pl: null, slave_pl: null,
  mt5_baseline: Object.assign({ start_fehler: { unklar: true, status: 'rot', schritt: 'm5still', msg: 'Geclaimt vor 5 min …', at: vor(25) } }, b || {}) }, o || {})
const out = {
  standard: ukKandidat(plan(), J),
  echo_v2: ukKandidat(plan({ route: 'mt5v2' }), J),
  orbit: ukKandidat(plan({ route: 'tvv2' }), J),
  zu_frisch: ukKandidat(plan({ start_um_gestartet_at: vor(10) }), J),
  zu_alt: ukKandidat(plan({ start_um_gestartet_at: vor(25 * 60) }), J),
  gestartet: ukKandidat(plan({ started_at: vor(29) }), J),
  review: ukKandidat(plan({ status: 'review' }), J),
  nicht_unklar: ukKandidat(plan({}, { start_fehler: { unklar: false, status: 'rot' } }), J),
  schon_behoben: ukKandidat(plan({}, { start_fehler: { unklar: true, status: 'behoben' } }), J),
  ticket: ukKandidat(plan({}, { ticket: 123 }), J),
  hedge: ukKandidat(plan({}, { hedge: { status: 'offen' } }), J),
  manuell: ukKandidat(plan({}, { manuell: { at: vor(5) } }), J),
  puls_unklar: ukKandidat(plan({}, { puls_unklar: { code: 'unklar' } }), J),
  pl: ukKandidat(plan({ master_pl: 12 }), J),
  slave_pl: ukKandidat(plan({ slave_pl: 3 }), J),
  gesendet: ukKandidat(plan({ orbit_gesendet_at: vor(29) }), J),
  ohne_claim: ukKandidat(plan({ start_um_gestartet_at: null }), J),
  echo_pos: ukKandidat(plan({}, { echo_pos_gesehen_at: vor(28) }), J),
  live_offen: ukKandidat(plan({}, { live: { offen: true } }), J),
  spur_ok: ukKandidat(plan({}, { puls_spur: { ok: true, at: vor(29) } }), J),
  spur_ok_alt: ukKandidat(plan({}, { puls_spur: { ok: true, at: vor(40) } }), J),
  grenze_20: ukKandidat(plan({ start_um_gestartet_at: vor(20) }), J),
  grenze_19: ukKandidat(plan({ start_um_gestartet_at: vor(19.9) }), J),
  urteil_orders: deUrteil({ ok: true, treffer: [], positionen: 0, orders: 1, balance: 100000 }, 100000).art,
  urteil_offen: deUrteil({ ok: true, treffer: [7], offen: true, positionen: 1, balance: 100000 }, 100000).art,
  urteil_mehrdeutig: deUrteil({ ok: true, treffer: [7, 8], positionen: 0, balance: 100000 }, 100000).art,
  urteil_blind: deUrteil({ ok: true, lesbar: false, grund: 'Master-Terminal läuft nicht' }, 100000).art,
  urteil_leer: deUrteil({ ok: true, treffer: [], positionen: 0, orders: 0, balance: 100000 }, 100000).art,
  urteil_position: deUrteil({ ok: true, treffer: [], positionen: 1, orders: 0, balance: 100000 }, 100000).art,
  urteil_balance: deUrteil({ ok: true, treffer: [], positionen: 0, orders: 0, balance: 99800 }, 100000).art,
  urteil_deal: deUrteil({ ok: true, treffer: [123], offen: false, pl: 45, positionen: 0, balance: 100045 }, 100000).art,
  urteil_ohne_ref: deUrteil({ ok: true, treffer: [], positionen: 0, orders: 0, balance: 100000 }, null).art,
  geloest: ukGeloest({ unklar: true, status: 'rot', msg: 'x', at: vor(25) }, { grund: 'kein Deal, keine Position, Balance unverändert 100.000 $' }, { balance: 100000 }, vor(0), 'pc-x')
}
print(JSON.stringify(out))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60); os.unlink(d.name)
try:
    e = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout[-600:], r.stderr[-600:]); sys.exit(1)
fehler = []
def check(ok, t):
    print(("✓ " if ok else "✗ ") + t)
    if not ok: fehler.append(t)
check(e["standard"] and e["echo_v2"], "Kandidat: geplanter Echo-Plan (mt5/mt5v2), Claim ≥ 20 min, start_fehler unklar")
check(not e["orbit"], "Orbit/Topstep nie (kein Deal-Weg)")
check(not e["zu_frisch"] and not e["zu_alt"], "nur 20 min … 24 h nach dem Claim")
check(not any(e[x] for x in ("gestartet", "review", "nicht_unklar", "schon_behoben")), "nie gestartet / nur planned / nur unklar und noch nicht behoben")
check(not any(e[x] for x in ("ticket", "hedge", "manuell", "puls_unklar", "pl", "slave_pl", "gesendet", "ohne_claim", "echo_pos", "live_offen", "spur_ok")), "jede Order-/Hand-Spur am Plan → nie per Deals lösen")
check(e["spur_ok_alt"] is True, "„ok“-Spur VOR dem Claim (alter Lauf) hindert nicht")
check(e["grenze_20"] is True and e["grenze_19"] is False, "Grenze genau 20 min nach dem Claim")
check(all(e[x] in ("unklar", "offen") for x in ("urteil_orders", "urteil_offen", "urteil_mehrdeutig", "urteil_blind")), "schwebende Order / offene Position / mehrdeutig / Terminal zu → nie „nicht gelaufen“")
check(e["urteil_leer"] == "nicht_gelaufen", "Deals leer + keine Position + Balance gleich → nicht gelaufen")
check(all(e[x] == "unklar" for x in ("urteil_position", "urteil_balance", "urteil_ohne_ref")), "Position / andere Balance / keine Vergleichs-Balance → bleibt unklar")
check(e["urteil_deal"] == "deals", "Deal gefunden → nie lösen (Order lief)")
g = e["geloest"]
check(g["status"] == "behoben" and g["unklar"] is True and g["msg"] == "x" and g["beleg"]["quelle"] == "deals_leer" and g["beleg"]["balance"] == 100000,
      "gelöste Marke: status behoben + Beleg deals_leer, Original (unklar/msg) bleibt")
print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
