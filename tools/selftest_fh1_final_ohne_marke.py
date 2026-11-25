#!/usr/bin/env python3
"""Selbsttest FH1 (Master 25.11.2026, Befund Prüfer S2 + S3): finale Futures-Trades (Tradeify/Lucid-Final, hedge_art 'tradeify_final') bekommen die
Hedge-Marke erst von Railway tfh_tick (60-s-Takt). Ohne Marke griffen bei Lucid Halte-Riegel, Freigabe und „ein finaler je ID“ nicht → Start ohne Hedge.
Fix nach Vorgabe Prüfer S2 (sql/2026-11-25_fh1_final_ohne_marke.sql): prophos_final_hedge_kandidat (Firma in prophos_final_hedge_firmen, nicht in einer
Verwalter-Gruppe mit auto_plan_gruppe-Zeile, kein orbit_prio2) + trade_plans_a_final_halten stellt einen finalen tvv2-Auto-Plan ohne Marke nur kurz zurück
(art 'hedge_marke', +2–4 min gestreut, nie +1 Tag, nie Start). Fälle a (tfh_tick steht), b (Gruppen-Modelle nicht lesbar → tfh_tick lässt aus), c (Plan wird
< 60 s vor dem Claim final) laufen alle auf „final ohne Marke beim Claim“ → zurückstellen. Anzeige: tpStartSperre (echte Funktion in jsc).
Ohne Netz, ohne DB. Aufruf: python3 tools/selftest_fh1_final_ohne_marke.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL = open(os.path.join(W, "sql", "2026-11-25_fh1_final_ohne_marke.sql"), encoding="utf-8").read()
LF1 = open(os.path.join(W, "sql", "2026-11-06_lucid_final_hedge.sql"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def zwischen(txt, a, b):
    i = txt.index(a)
    return txt[i:txt.index(b, i + len(a))]


code = "\n".join(z for z in SQL.splitlines() if not z.lstrip().startswith("--"))   # nur ausführbarer Teil (Kommentare tragen Rückbau-Text)

# 1) Kandidat = Spiegel von tfh_plan_dabei
k = zwischen(code, "create or replace function public.prophos_final_hedge_kandidat(", "revoke all on function public.prophos_final_hedge_kandidat")
check("if k is null or not public.prophos_tradeify_final_hedge_an() then\n    return false;" in k, "Hedge-Weg aus → nie Kandidat (bitgleich wie vor FH1)")
check("'Tradeify'" not in k and "k = any(public.prophos_final_hedge_firmen())" in k and "p_user is null" in k,
      "Firma nur aus prophos_final_hedge_firmen() (regeln.tradeify_final_hedge.firmen: Tradeify, Lucid, FNF sobald eingetragen), ohne ID nie")
check(k.count("exists (select 1 from public.auto_plan_gruppe apg where apg.gruppe_id = g.id)") == 2 and "g.verwalter_user_id is not null" in k
      and "where g.verwalter_user_id = p_user" in k, "nicht in einer Verwalter-Gruppe mit auto_plan_gruppe-Zeile (Mitglied oder Verwalter) — Emin bleibt orbit_prio2")
check("f->>'modell' = 'orbit_prio2'" in k and "(n = x or n like x || '%')" in k, "nie mit Firmen-Modell orbit_prio2 (ah_tick)")
check("revoke all on function public.prophos_final_hedge_kandidat(text, uuid) from public, anon, authenticated;" in code, "Kandidat-Funktion nicht von außen aufrufbar")
check("stable security definer set search_path = public" in k, "stable + security definer + fester search_path")

# 2) Halte-Riegel
t = zwischen(code, "create or replace function public.trade_plans_a_final_halten()", "$function$;")
check("weg := coalesce(new.auto_plan, false) and coalesce(new.route, '') = 'tvv2' and not coalesce(new.winning_day, false)" in t and "<> 'apex'" in t
      and "coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = ''" in t and "public.prophos_final_hedge_kandidat(new.master_firm, new.user_id)" in t,
      "Weg: nur tvv2-Auto-Plan, kein Winning Day, nicht Orbit Prio 2 (Marke apex / apex_hedge), Kandidat")
check("kand := weg and coalesce(new.mt5_baseline->>'hedge_art', '') = '' and new.mt5_baseline->'tradeify_hedge' is null;" in t,
      "kurz halten nur ohne jede Entscheidung von tfh_tick (keine Marke, kein tradeify_hedge)")
check("if not (public.prophos_final_hedge_firma(new.master_firm, new.mt5_baseline->>'hedge_art') or weg) then\n    return new;" in t,
      "Riegel greift für die alte Firmen-Regel ODER den Weg (Lucid ohne Marke ist drin)")
i_weg, i_v3, i_final, i_kand = (t.index(x) for x in ("or weg) then", "coalesce(new.orbit_v3, false) and coalesce(new.hedge_eur, 0) > 0",
                                                     "or not public.prophos_plan_final(new.id)", "if kand then"))
check(i_weg < i_v3 < i_final < i_kand, "Reihenfolge: Firma/Weg → umgestellt (Orbit V3 + Hedge) darf starten → nur finale Pläne → dann erst kurz halten")
kb = zwischen(t, "if kand then", "  if ss->>'art' = 'final_halten'")
check("interval '2 minutes' + make_interval(secs => floor(random() * 120))" in kb, "kurz zurückstellen +2–4 min, gestreut (Jitter)")
check("'art', 'hedge_marke'" in kb and "wartet auf Hedge-Kennung" in kb and "'erst_at'" in kb, "start_sperre hedge_marke „wartet auf Hedge-Kennung“ mit erst_at")
check("interval '1 day'" not in kb and "10 minutes" not in t, "nie +1 Tag für einen Plan ohne Marke, keine Eskalation")
# Fälle a/b/c (Prüfer S2): der Riegel hängt nur am Planzustand beim Claim — nie am Railway-Takt, an Gruppen-Modellen aus app.py oder am Alter der Final-Lage
for wort, fall in (("letzter_lauf", "a: tfh_tick steht"), ("firmen_modell", "b: Gruppen-Modelle (tfh liest sie, der Riegel nicht)"), ("created_at", "c: Plan eben erst final")):
    check(wort not in t, f"Fall {fall} → Entscheidung nur aus dem Plan beim Claim, kein {wort}")
check(t.index("public.prophos_plan_final(new.id)") < t.index("if kand then"),
      "Fall c: final wird beim Claim aus Notiz bzw. Ziel − aktueller tv_balance gerechnet (prophos_plan_final), nicht aus einer Marke")
check("ss->>'art' = 'hedge_marke' and (ss->>'at')::timestamptz > now() - interval '1 minute' then\n      return null;" in kb, "Mehrfach-Claim gleich nach dem Halt: nichts weiter schieben")
check(kb.count("insert into public.auto_plan_umplanung") == 2 and "if erst then" in kb, "Protokoll beim ersten Halt (kein Spam je 2–4 min) …")
check("(ss->>'erst_at')::timestamptz < now() - interval '30 minutes'" in kb and "elsif lange and coalesce(ss->>'lange', '') <> 'true' then" in kb
      and "Railway tfh_tick prüfen" in kb and "'lange', case when erst then false else lange or coalesce(ss->>'lange', '') = 'true' end" in kb,
      "… und genau einmal nach 30 min ohne Kennung „Railway tfh_tick prüfen“ (Review-Fund: Takt steht sonst still)")
check(kb.count("return null;") == 2 and "return new" not in kb, "im kurzen Halt nie ein Start (nur return null)")
# alter Tages-Halt bitgleich (aus dem LF1-Stand, live 25.11.)
for zeile in ("ziel := greatest(coalesce(old.start_um, now()), now() - interval '12 hours') + interval '1 day'",
              "if ziel < now() + interval '12 hours' then",
              "'art', 'final_halten', 'text', txt, 'at', now(), 'naechster', ziel,",
              "'[finaler ' || public.prophos_firma_key(new.master_firm) || ' gehalten] ' || txt || ' — Start frühestens '",
              "if coalesce(new.orbit_v3, false) and coalesce(new.hedge_eur, 0) > 0 and public.prophos_tradeify_final_hedge_an() then",
              "if not (public.prophos_tradeify_final_halten_an() or public.prophos_tradeify_final_hedge_an()) or not public.prophos_plan_final(new.id) then"):
    check(zeile in t, f"bitgleich zum bisherigen Riegel: {zeile[:70]}…")
check("|| coalesce(', ' || nullif(new.mt5_baseline->'tradeify_hedge'->>'grund', ''), '') || ')';" in t, "Tages-Halt-Text bitgleich")
check("trade_plans_a_final_halten" in LF1 and "prophos_final_hedge_firma" in LF1, "Grundlage LF1-Datei vorhanden (prophos_final_hedge_firma)")
check(code.strip().startswith("begin;") and "commit;" in code and "$pruef$" in code, "eine Transaktion, Vorab-Prüfung der Grundfunktionen")
check("drop trigger" not in code.lower() and "create trigger" not in code.lower(), "Trigger selbst unverändert (nur Funktion ersetzt, wirkt auf jeden Claim-Weg)")

# 3) Anzeige: echte tpStartSperre in jsc
fn = zwischen(HTML, "  function tpStartSperre(p){", "\n  }\n") + "\n  }\n"
js = """
const tpLotsDeckelFehlt = () => false, tpWdWartetAufBestaetigung = () => false, cfdAufgegeben = () => false
const tpStartUmText = s => 'um 10:00', zweitGrund = () => null, WOCHENENDE_GRUND = ''
const tpFusionLots = () => 0, tpLotsDeckelText = () => ''
""" + fn + """
const jetzt = new Date().toISOString()
const plan = b => ({ status: 'planned', startUmGestartetAt: null, mt5Baseline: b })
const ss = { art: 'hedge_marke', text: 'finaler Lucid Trading-Trade wartet auf Hedge-Kennung (Railway-Takt) — startet nie ohne Gegenhedge', at: jetzt, naechster: jetzt, versuche: 2 }
const a = tpStartSperre(plan({ start_sperre: ss }))
const b = tpStartSperre(plan({ start_sperre: ss, hedge_art: 'tradeify_final' }))
const c = tpStartSperre(plan({ start_sperre: ss, tradeify_hedge: { status: 'ohne' } }))
const d = tpStartSperre(plan({ start_sperre: Object.assign({}, ss, { at: '2026-01-01T00:00:00Z' }) }))
print(JSON.stringify({ a, b, c, d }))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
os.unlink(f.name)
check(r.returncode == 0, f"jsc läuft ({(r.stderr or r.stdout)[:200]})")
e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
a = e.get("a") or {}
check(a.get("kurz", "").startswith("⏳ Wartet auf Hedge-Kennung · neuer Versuch um 10:00") and a.get("marke") == "⏳ Hedge-Kennung"
      and "nie ohne Gegenhedge" in a.get("voll", "") and "nie ohne Hedge" in a.get("voll", "") and a.get("versuche") == 2,
      f"Planer zeigt „Wartet auf Hedge-Kennung“: {a.get('kurz')}")
check(e.get("b") is None and e.get("c") is None, "sobald markiert (hedge_art / tradeify_hedge) verschwindet der Hinweis")
check(e.get("d") is None, "alter Hinweis (> 30 min) wird nicht mehr gezeigt (wie die anderen Sperren)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
