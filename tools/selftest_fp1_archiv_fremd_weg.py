#!/usr/bin/env python3
"""Selbsttest FP1 (06.11.2026): Geister-Hand-Positionen auf archivierten Konten sperren den Gegenrichtungs-Riegel nicht mehr.
Anlass: Nova-Test, Start bei Marco blockiert durch fremd_positionen 7573 auf dem seit 05.11. archivierten Topstep-Konto (nie weg_at).
Ohne Datenbank, prüft sql/2026-11-06_fp1_archiv_fremd_weg.sql:
  • der neue Riegel ist bis auf genau drei Zeilen (Kommentar + Filter über 2 Zeilen) die Live-Fassung aus der Rückbau-Datei (md5 b5cebfd9…)
  • (a) Trigger auf user_settings key 'archive', nach insert/update of value, fängt Fehler ab, Sperr-Wartezeit 2 s, setzt weg_at nur für offene,
    ≥ 30 min nicht gesehene Zeilen (gleiche Grenze wie der Riegel, Prüfer S2)
  • (b) Filter steht im execute-Text des Hand-Positions-Teils (doppelte Anführungszeichen), nimmt nur Zeilen mit konto_id aus, die ≥ 30 min nicht
    gesehen wurden (frische Sichtung schlägt das Archiv)
  • Archiv über alle Profile (Konto-IDs global eindeutig, wie app.py _ap_archiviert)
  • Archiv-Kriterium (value -> konto ->> 'archived' = 'true') in einer kleinen Nachbildung gegen die Blob-Formen aus Tab/Server/SQL
Live-Trockenlauf (06.11.2026, do-Block mit erzwungenem raise → alles zurückgerollt, danach geprüft: kein Trigger, keine Testzeilen, Riegel-md5 unverändert):
  vorher frei=false · nachher Geist auf archiviertem Konto (≥ 30 min nicht gesehen) frei=true · frisch gesehen (5 min) sperrt weiter ·
  Zeile ohne konto_id sperrt weiter · Trigger setzt weg_at = zuletzt_gesehen nur bei ≥ 30 min alt, frische bleibt offen.
Aufruf: python3 tools/selftest_fp1_archiv_fremd_weg.py"""
import hashlib
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []
LIVE_MD5 = "b5cebfd95301747578b4f0c149a351c2"


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def riegel(sql):
    a = sql.index("CREATE OR REPLACE FUNCTION public.prophos_gegenrichtung_frei_konto")
    b = sql.index("end $function$;", a) + len("end $function$")
    return sql[a:b]


def archiviert(blob, konto):
    """Nachbildung von  jsonb_typeof(value) = 'object' and value -> konto ->> 'archived' = 'true'."""
    if not isinstance(blob, dict):
        return False
    e = blob.get(konto)
    if not isinstance(e, dict) or "archived" not in e:
        return False
    v = e["archived"]
    return (json.dumps(v) if not isinstance(v, str) else v) == "true"


def main():
    neu = open(os.path.join(WURZEL, "sql", "2026-11-06_fp1_archiv_fremd_weg.sql"), encoding="utf-8").read()
    rb = open(os.path.join(WURZEL, "sql", "2026-11-06_fp1_archiv_fremd_weg_rueckbau.sql"), encoding="utf-8").read()

    live = riegel(rb)
    check(hashlib.md5((live + "\n").encode()).hexdigest() == LIVE_MD5, "Rückbau-Riegel = Live-Fassung 06.11.2026 (md5 " + LIVE_MD5[:8] + "…)")
    r_neu = riegel(neu)
    a, b = live.splitlines(), r_neu.splitlines()
    extra = [z for z in b if z not in a]
    check(len(b) == len(a) + 3 and [z for z in b if z not in extra] == a, "neuer Riegel = Live-Fassung + genau 3 Zeilen")
    check(any(z.strip().startswith("-- FP1") for z in extra), "eine der Zeilen ist der FP1-Kommentar")
    filt = " ".join(z.strip() for z in extra if not z.strip().startswith("--"))
    check(filt == "and not (f.konto_id is not null and coalesce(f.zuletzt_gesehen, ''-infinity''::timestamptz) < now() - interval ''30 minutes'' "
                  "and public.prophos_konto_archiviert(f.user_id, f.konto_id))",
          "Filter: nur Zeilen mit konto_id, ≥ 30 min nicht gesehen, auf archiviertem Konto fallen raus (null-sicher)")
    # Filter steht im execute-Text zwischen „f.weg_at is null“-Block und order by
    m = re.search(r"execute 'select f\.seit.*?order by f\.seit desc limit 1'", r_neu, re.S)
    check(bool(m) and "prophos_konto_archiviert" in m.group(0) and "''" in m.group(0), "Filter steht im execute-Text des Hand-Positions-Teils")
    check(r_neu.index("prophos_konto_archiviert") > r_neu.index("if g.id is null then"), "Plan-Sperren davor unverändert (Filter erst im Hand-Teil)")

    # Reihenfolge: Hilfe vor Bestand-Update und Riegel
    i_hilfe = neu.index("create or replace function public.prophos_konto_archiviert")
    i_best = neu.index("update public.fremd_positionen f\n   set weg_at = coalesce(f.zuletzt_gesehen, now())\n where f.weg_at is null\n   and f.konto_id is not null")
    i_rieg = neu.index("CREATE OR REPLACE FUNCTION public.prophos_gegenrichtung_frei_konto")
    check(i_hilfe < i_best < i_rieg, "Reihenfolge: Hilfe → Trigger/Bestand → Riegel")

    # (a) Trigger
    check("drop trigger if exists user_settings_archiv_fremd_weg on public.user_settings;" in neu, "Trigger idempotent (drop if exists)")
    check(re.search(r"after insert or update of value on public\.user_settings\s+for each row when \(new\.key = 'archive'\)", neu) is not None,
          "Trigger: after insert/update of value, nur key 'archive'")
    tf = neu[neu.index("create or replace function public.prophos_archiv_fremd_weg()"):neu.index("revoke all on function public.prophos_archiv_fremd_weg()")]
    check("exception when others then" in tf and "raise warning" in tf and tf.count("return new;") == 2, "Trigger bricht das Archivieren nie ab")
    check("set_config('lock_timeout', '2s', true)" in tf and "set_config('lock_timeout', lt_vorher, true)" in tf
          and tf.index("lock_timeout', '2s'") < tf.index("update public.fremd_positionen"), "Trigger: Sperr-Wartezeit 2 s, danach zurückgesetzt")
    check("security definer" in tf and "set search_path = public" in tf, "Trigger security definer (Tab darf fremd_positionen per RLS nicht schreiben)")
    for teil in ("f.weg_at is null", "f.konto_id is not null", "new.value -> (f.konto_id::text) ->> 'archived' = 'true'"):
        check(teil in tf, "Trigger-Bedingung: " + teil)
    frisch = "coalesce(f.zuletzt_gesehen, '-infinity'::timestamptz) < now() - interval '30 minutes'"
    check(frisch in tf, "Trigger: frisch gesehene (≤ 30 min) bleiben offen — gleiche Grenze wie der Riegel (Prüfer S2)")
    best = neu[i_best:neu.index(";", i_best)]
    check(frisch in best, "Bestand-Update: frisch gesehene bleiben offen")
    check(frisch.replace("'", "''") in r_neu, "Riegel nutzt dieselbe 30-min-Grenze")
    check(re.search(r"\b(delete|truncate|drop table)\b", neu, re.I) is None, "nichts Destruktives in der Datei")
    hf = neu[i_hilfe:neu.index("$$;", i_hilfe)]
    check("s.user_id" not in hf and "s.key = 'archive'" in hf and "jsonb_typeof(s.value) = 'object'" in hf, "Hilfe liest das Archiv aller Profile (wie app.py)")

    # Rückbau
    check(rb.index("drop trigger if exists user_settings_archiv_fremd_weg") < rb.index("CREATE OR REPLACE FUNCTION")
          < rb.index("drop function if exists public.prophos_konto_archiviert"), "Rückbau: Trigger weg → Riegel zurück → Hilfe weg")

    # Archiv-Kriterium gegen die Blob-Formen
    k = "c640317f-bb6a-45c4-8231-d5604f78dbb3"
    faelle = [
        ({k: {"at": "2026-11-05T06:30:00Z", "reason": "blown", "archived": True}}, True, "Tab/SQL: archived true (blown)"),
        ({k: {"archived": True, "reason": "passed_pending", "successorId": "x"}}, True, "passed_pending zählt als archiviert"),
        ({k: {"archived": "true"}}, True, "archived als Text 'true'"),
        ({k: {"archived": False}}, False, "archived false"),
        ({"anderes-konto": {"archived": True}}, False, "anderes Konto archiviert"),
        ({}, False, "entarchiviert (Schlüssel entfernt)"),
        ([k], False, "Blob kein Objekt"),
    ]
    for blob, soll, text in faelle:
        check(archiviert(blob, k) is soll, f"Kriterium: {text} → {soll}")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("OK — FP1 Selbsttest grün")


if __name__ == "__main__":
    main()
