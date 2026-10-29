#!/usr/bin/env python3
"""Selbsttest APEX IMMER MIT HEDGE (30.10.2026): sql/2026-10-30_apex_immer_hedge.sql (Claim-Riegel trade_plans_a1_apex_hedge) und
app.py _ah_ohne / alarm_tick / tpStartSperre. Ohne Netz, nur Text- und Strukturprüfung. Aufruf: python3 tools/selftest_apex_immer_hedge.py"""
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(*teile):
    return open(os.path.join(WURZEL, *teile), encoding="utf-8").read()


def main():
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    sql = lies("sql", "2026-10-30_apex_immer_hedge.sql")
    code = "\n".join(z for z in sql.splitlines() if not z.lstrip().startswith("--"))
    fn = code[code.index("create or replace function public.trade_plans_a1_apex_hedge()"):code.index("drop trigger")]
    # nur Auto-Pläne mit Marke 'apex', nur geplant
    ok("new.status is distinct from 'planned'" in fn and "coalesce(new.auto_plan, false)" in fn
       and "new.mt5_baseline->>'hedge_art', '') <> 'apex'" in fn, "Eingrenzung planned + auto_plan + hedge_art apex")
    # umgestellt → frei, VOR dem Halten
    i_mit = fn.find("'apex_hedge'->>'status', '') = 'mit' and coalesce(new.hedge_eur, 0) > 0")
    i_halt = fn.find("update public.trade_plans")
    ok(0 < i_mit < i_halt, "Umgestellt (status mit + hedge_eur > 0) darf vor dem Halten starten")
    ok(0 < fn.find("prophos_apex_hedge_an()") < i_halt, "Schalter aus → wie bisher (kein Halten)")
    # gehalten: return null, gestreut 15–30 min, start_sperre apex_hedge, Mehrfach-Claim, Protokoll nur beim ersten Halt
    ok(fn.rstrip().endswith("return null;\nend $$;") or fn.count("return null;") == 2, "Claim scheitert (return null)")
    ok("interval '15 minutes' + make_interval(secs => floor(random() * 900))" in fn, "Start rückt 15–30 min gestreut weiter")
    ok("'art', 'apex_hedge'" in fn and "'grund'" in fn and "'versuche'" in fn, "start_sperre mit Grund + Versuchen")
    ok("> now() - interval '1 minute' then\n    return null;" in fn, "Mehrfach-Claim < 1 min schiebt nicht weiter")
    ok(re.search(r"if erst then\s+insert into public\.auto_plan_umplanung", fn) is not None, "Protokoll nur beim ersten Halt")
    ok("hand_werte_at =" not in fn and "hand_werte_at = coalesce" not in fn, "hand_werte_at wird nie gesetzt (ah_tick stellt nur Pläne ohne Hand-Werte um)")
    # Nachtrag Hand-Werte (Master 30.10.2026, Variante 2): weiter halten, eigener Sperrtext; Nachtrag-Datei wortgleich
    i_hand = fn.find("if new.hand_werte_at is not null then")
    ok(i_mit < i_hand < i_halt and "Werte von Hand geändert, Takt stellt nicht mehr um: ablehnen und neu planen" in fn
       and "return new" not in fn[i_hand:i_halt], "Hand-Werte: gehalten mit eigenem Text, nie durchgelassen")
    hand = lies("sql", "2026-10-30_apex_immer_hedge_hand.sql")
    hc = "\n".join(z for z in hand.splitlines() if not z.lstrip().startswith("--"))
    ok(hc[hc.index("create or replace function public.trade_plans_a1_apex_hedge()"):].strip() == fn.strip(), "Nachtrag-Datei wortgleich mit der Hauptdatei")
    ok("create trigger" not in hc and "drop trigger" not in hc, "Nachtrag: nur die Funktion, Trigger bleibt")
    ok("trade_plans_kontoart_weg" not in code, "kontoart_weg unverändert")
    trig = code[code.index("create trigger trade_plans_a1_apex_hedge"):]
    ok("before update of start_um_gestartet_at" in trig and "old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null" in trig,
       "feuert nur beim Claim")
    ok("trade_plans_a0_hedge_freigabe" < "trade_plans_a1_apex_hedge" < "trade_plans_a_final_halten", "Reihenfolge a0 → a1 → a_final")
    # app.py: kein „ohne Hedge starten" mehr, Alarm-Weg + Select
    app = lies("app.py")
    i = app.index("\ndef _ah_ohne(")
    ah = app[i:app.find("\n\n\n", i)]
    ok("Orbit V2 ohne Hedge" not in ah and "startet nie ohne Hedge" in ah, "_ah_ohne-Meldung: wartet statt ohne Hedge")
    ok("ahm:mt5_baseline->apex_hedge" in app and '"apex_hedge"):' in app, "alarm_tick liest apex_hedge, gp_push nimmt die Art aus")
    html = lies("prophos.html")
    ok("'waage_deckel', 'apex_hedge'].includes(s.art)" in html and "if(s.art === 'apex_hedge')" in html, "tpStartSperre zeigt die Sperre")
    ok("/von Hand geändert/.test(text)" in html, "tpStartSperre: eigener Satz für Hand-Werte")
    for t in f:
        print("✗", t)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
