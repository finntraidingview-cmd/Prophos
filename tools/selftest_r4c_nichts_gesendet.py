#!/usr/bin/env python3
"""Selbsttest R4c (05.11.2026): Gegenrichtungs-Riegel — ein Schwester-Plan mit eindeutigem Beleg „nichts gesendet" sperrt nicht.
Ohne Datenbank: das Beleg-Kriterium aus sql/2026-11-05_gegenrichtung_nichts_gesendet.sql wird wörtlich herausgelöst und gegen die echten Pläne vom 04.11.
(Momentaufnahme der Felder, die das Kriterium liest) in einer kleinen Nachbildung ausgewertet; dazu: der neue Riegel-Text ist bis auf die eine R4c-Zeile
die Live-Fassung (Rückbau-Datei), und das Kriterium ist eng (jede fehlende Bedingung → kein Beleg).
Live-Gegenprobe (reines SELECT, 05.11.2026): Ausdruck → Marco …115952 true, Chris …117784 false; in 30 Tagen 6 Pläne mit Beleg, keiner gestartet.
Aufruf: python3 tools/selftest_r4c_nichts_gesendet.py"""
import copy
import os
import re
import sys
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def ts(x):
    return datetime.fromisoformat(str(x).replace("Z", "+00:00"))


# Momentaufnahme 04.11.2026 (trade_plans, Stand nach dem Hängen, vor dem Tagesreset): nur die Felder, die das Kriterium liest
MARCO = {"id": "b98697dc-a571-4b05-9a00-538209e58731", "status": "review", "started_at": None, "orbit_gesendet_at": None, "master_pl": None,
         "start_um_gestartet_at": "2026-11-04T04:58:01.081+00:00",
         "mt5_baseline": {"puls_spur": {"s": None, "at": "2026-11-04T04:58:19.736Z", "ok": False, "pc": "pc-t8wg97", "trail": "",
                                        "msg": "Riegel-Prüfung (Gegenrichtung) nicht erreichbar: <urlopen error [Errno 11001] getaddrinfo failed> — nichts gesendet, der Start wird später erneut versucht."},
                          "start_fehler": {"unklar": True, "schritt": "m5still", "status": "rot"}, "echo_hedge": {}, "hedge_vorschau": {}},
         "order_signale": [], "puls_ergebnisse": []}
CHRIS = {"id": "dc66f1f4-81a4-4d23-ab74-f692fa06e102", "status": "planned", "started_at": None, "orbit_gesendet_at": None, "master_pl": None,
         "start_um_gestartet_at": "2026-11-04T02:25:00.327+00:00",
         "mt5_baseline": {"start_fehler": {"unklar": True, "schritt": "m5still", "status": "rot",
                                           "msg": "Geclaimt vor 5 min, danach keine Order-Antwort und Master-Konto nicht lesbar → im Master-Terminal prüfen, ob eine Order liegt."},
                          "echo_hedge": {}, "hedge_vorschau": {}},
         "order_signale": [], "puls_ergebnisse": []}


def kriterium_teile(sql):
    i = sql.index("create or replace function public.prophos_plan_nichts_gesendet(p_plan uuid)")
    return sql[i:sql.index("$$;", i)]


def beleg(p, krit):
    """Nachbildung des SQL-Kriteriums — jede Bedingung ist an ihrem SQL-Text festgemacht (der Test prüft, dass genau diese Texte im SQL stehen)."""
    b = p.get("mt5_baseline") or {}
    sp = b.get("puls_spur")
    msg = (sp or {}).get("msg") or ""
    teile = [
        ("p.started_at is null", p.get("started_at") is None),
        ("p.orbit_gesendet_at is null", p.get("orbit_gesendet_at") is None),
        ("p.status in ('planned', 'review')", p.get("status") in ("planned", "review")),
        ("coalesce(p.master_pl, 0) = 0", (p.get("master_pl") or 0) == 0),
        ("p.start_um_gestartet_at is not null", p.get("start_um_gestartet_at") is not None),
        ("jsonb_typeof(p.mt5_baseline->'puls_spur') = 'object'", isinstance(sp, dict)),
        ("p.mt5_baseline->'puls_spur'->>'ok' = 'false'", isinstance(sp, dict) and sp.get("ok") is False),
        ("coalesce(p.mt5_baseline->'puls_spur'->>'trail', '') = ''", isinstance(sp, dict) and not (sp.get("trail") or "")),
        ("(p.mt5_baseline->'puls_spur'->>'at')::timestamptz >= p.start_um_gestartet_at - interval '5 seconds'",
         isinstance(sp, dict) and bool(sp.get("at")) and p.get("start_um_gestartet_at") is not None
         and ts(sp["at"]) >= ts(p["start_um_gestartet_at"]) - timedelta(seconds=5)),
        ("'^Riegel-Prüfung \\(Gegenrichtung\\) nicht (erreichbar|möglich):.*nichts gesendet'",
         bool(re.search(r"^Riegel-Prüfung \(Gegenrichtung\) nicht (erreichbar|möglich):.*nichts gesendet", msg, re.I)) or msg.startswith("Gegenrichtung gesperrt:")),
        ("array['ticket', 'hedge', 'puls_unklar', 'live', 'echo_pos_gesehen_at', 'schon_zu']",
         not any(k in b for k in ("ticket", "hedge", "puls_unklar", "live", "echo_pos_gesehen_at", "schon_zu"))),
        ("from public.order_signale o where o.plan_id = p.id::text",
         not any(str((o.get("ergebnis") or {}).get("gesendet")).lower() == "true" or str((o.get("ergebnis") or {}).get("ok")).lower() == "true" for o in p.get("order_signale") or ())),
        ("from public.puls_ergebnisse e where e.plan_id = p.id::text and e.art = 'order'",
         not any(e.get("art") == "order" and (str((e.get("ergebnis") or {}).get("gesendet")).lower() == "true" or str((e.get("ergebnis") or {}).get("ok")).lower() == "true")
                 for e in p.get("puls_ergebnisse") or ())),
    ]
    fehlt = [t for t, _ in teile if t not in krit]
    return all(ok for _, ok in teile), fehlt


def main():
    sql = open(os.path.join(WURZEL, "sql", "2026-11-05_gegenrichtung_nichts_gesendet.sql"), encoding="utf-8").read()
    alt = open(os.path.join(WURZEL, "sql", "2026-11-05_gegenrichtung_nichts_gesendet_rueckbau.sql"), encoding="utf-8").read()
    krit = kriterium_teile(sql)
    ok_m, fehlt = beleg(MARCO, krit)
    check(not fehlt, f"jede Bedingung der Nachbildung steht wörtlich im SQL-Kriterium ({fehlt or 'alle'})")
    check(ok_m is True, "Marco …115952 (04.11. 08:58 Dubai, DNS getaddrinfo, Panel-Abbruch vor dem Bot): Beleg „nichts gesendet“ → sperrt nicht mehr")
    ok_c, _ = beleg(CHRIS, krit)
    check(ok_c is False, "Chris …117784 (04.11. 06:25 Dubai, keine Order-Antwort, Master nicht lesbar): kein Beleg → bleibt UNKLAR und sperrt")
    # eng: jede Spur einer Order nimmt den Beleg
    stoer = {
        "gestartet": lambda p: p.update(started_at="2026-11-04T04:59:00Z"),
        "orbit gesendet": lambda p: p.update(orbit_gesendet_at="2026-11-04T04:59:00Z"),
        "P&L am Plan": lambda p: p.update(master_pl=-12.5),
        "Klick-Spur": lambda p: p["mt5_baseline"]["puls_spur"].update(trail="0.0s·Hand … sell-Knopf: click_input"),
        "Spur ok": lambda p: p["mt5_baseline"]["puls_spur"].update(ok=True),
        "alte Spur (vor dem Claim)": lambda p: p["mt5_baseline"]["puls_spur"].update(at="2026-11-04T04:50:00Z"),
        "anderer Text (Zeitlimit)": lambda p: p["mt5_baseline"]["puls_spur"].update(msg="Zeitlimit: Bot brach nach 260 s ab — nichts gesendet?"),
        "Text nur in der Spur": lambda p: p["mt5_baseline"]["puls_spur"].update(msg="KEINE Bestaetigung binnen 12 s · Spur: Riegel-Prüfung (Gegenrichtung) nicht erreichbar — nichts gesendet"),
        "Ticket": lambda p: p["mt5_baseline"].update(ticket=123),
        "Hedge": lambda p: p["mt5_baseline"].update(hedge={"status": "offen"}),
        "Echo-Position gesehen": lambda p: p["mt5_baseline"].update(echo_pos_gesehen_at="2026-11-04T05:00:00Z"),
        "order_signale gesendet": lambda p: p.update(order_signale=[{"ergebnis": {"gesendet": True}}]),
        "puls_ergebnisse ok": lambda p: p.update(puls_ergebnisse=[{"art": "order", "ergebnis": {"ok": True}}]),
        "Status open": lambda p: p.update(status="open"),
    }
    falsch = []
    for name, f in stoer.items():
        p = copy.deepcopy(MARCO)
        f(p)
        if beleg(p, krit)[0]:
            falsch.append(name)
    check(not falsch, f"eng: {len(stoer)} Störungen nehmen den Beleg ({falsch or 'alle'})")
    check(beleg(dict(copy.deepcopy(MARCO), status="planned"), krit)[0], "auch im Zustand Geplant (vor dem Tagesreset) wirkt der Beleg")
    gs = copy.deepcopy(MARCO)
    gs["mt5_baseline"]["puls_spur"]["msg"] = "Gegenrichtung gesperrt: „…“ läuft dort in Gegenrichtung"
    check(beleg(gs, krit)[0], "Panel-Sperre „Gegenrichtung gesperrt:“ (Bot nie gestartet) zählt als Beleg")
    # Riegel-Funktion: nur die eine Zeile neu
    b = lambda t: t[t.index("$function$") + 10:t.rindex("$function$")]
    neu = sql[sql.index("create or replace function public.prophos_gegenrichtung_frei_konto"):sql.index("end $function$;") + len("end $function$")]
    zeilen = ("         -- R4c: eindeutig nichts gesendet (Panel-Abbruch vor dem Bot, keine Order-Spur) → sperrt die Gegenrichtung nicht\n"
              "         and not (p.status in ('planned', 'review') and public.prophos_plan_nichts_gesendet(p.id))\n")
    check(zeilen in b(neu) and b(neu).replace(zeilen, "") == b(alt), "prophos_gegenrichtung_frei_konto = Live-Fassung (Rückbau-Datei, md5 d6c1f7d5…) + genau die R4c-Bedingung")
    check("d6c1f7d508a4d0d2fad8def2994834dd" in alt and "d6c1f7d508a4d0d2fad8def2994834dd" in sql, "Rückbau-Datei trägt den md5 der Live-Fassung")
    check("start_fehler" not in krit and "sfTick" not in krit, "Kriterium liest start_fehler nicht — Nachholen/Marke (P1 .2040) unverändert, nur der Riegel")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
