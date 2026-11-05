#!/usr/bin/env python3
"""Selbsttest ECHO-TEMPO (ES3, Finn 05.11.2026: „Orders sollen viel schneller prozessiert werden, wie es ganz am Anfang war"; Befund ES1:
Bot bis Fill 16 s → 24 s seit .1798). Die ECHTEN Funktionen aus mt5-copier/order_bot.py und app.py, ohne Windows, ohne Netz:
 a) echo_tempo_werte: fehlt/kaputt → heutige Werte je Schlüssel, Kappen (Faktor 0,3–1, Versatz 0–3 s), {"werte": …} aus der Datei
 b) feld_takt: Grundwerte einmal je Feld, ±15 % je Zeichen, kein Stocken, nie unter 12/8 ms; warte_dauer ruhig: keine Denkpause, Faktor ≤ 1
 c) app.py puls_echo_tempo_stand: eigener 60-s-Cache, Fehler/fehlende Spalte → None (Schlüssel fehlt), guter Stand bleibt
 d) Verdrahtung run(): Werte vor dem ersten Schritt, Versatz aus der Einstellung, ruhig nur F9-Dialog → Position offen, main setzt zurück
 e) Zeitbudget der Tasten je Feld (Erwartungswert) heute vs. Vorschlag — gedruckt, Ziel ~16 s Bot bis Fill
Aufruf: python3 tools/selftest_echo_tempo.py"""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(os.path.dirname(HIER), "mt5-copier", "order_bot.py")
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


def konst(src, name, ns):
    exec(re.search(rf"^{name} = .*$", src, re.M).group(0), ns)


def main():
    src = open(BOT, encoding="utf-8").read()
    hand = {"tempo": 1.0, "pause": 1.5}
    ns = {"random": random, "_hand": lambda: hand}
    for k in ("WARTE_DENK_AB", "WARTE_DENK_ANTEIL", "WARTE_DENK_S", "ECHO_TEMPO_STANDARD", "ECHO_TIPP_FAKTOR_MIN", "ECHO_VERSATZ_MAX_S",
              "ECHO_TASTE_MIN_S", "_ECHO_RUHIG"):
        konst(src, k, ns)
    for n in ("warte_dauer", "echo_tempo_werte", "echo_tempo_text", "feld_takt", "tasten_takt", "tipp_takt"):
        exec(fn(src, n), ns)
    W, T, FT, WD = ns["echo_tempo_werte"], ns["echo_tempo_text"], ns["feld_takt"], ns["warte_dauer"]
    S = ns["ECHO_TEMPO_STANDARD"]

    # a) Werte
    check(S == {"tipp_faktor": 1.0, "denkpausen": True, "versatz_s": 1.2}, "Standard = heutige Werte (Faktor 1, Denkpausen an, Versatz 1,2 s)")
    check(W(None) == S and W({}) == S and W("quatsch") == S and W({"werte": None}) == S, "ohne Einstellung → heutige Werte")
    check(W({"tipp_faktor": 0.5, "denkpausen": False, "versatz_s": 0.6}) == {"tipp_faktor": 0.5, "denkpausen": False, "versatz_s": 0.6},
          "Vorschlag 0,5 / aus / 0,6 kommt unverändert an")
    check(W({"werte": {"tipp_faktor": 0.4}, "at": 1}) == dict(S, tipp_faktor=0.4), "aus echo_tempo.json ({werte, at}) gelesen, Rest = heute")
    check(W({"tipp_faktor": 0.05, "versatz_s": 9})["tipp_faktor"] == 0.3 and W({"versatz_s": 9})["versatz_s"] == 3.0
          and W({"tipp_faktor": 4})["tipp_faktor"] == 1.0 and W({"versatz_s": -2})["versatz_s"] == 0.0, "Kappen: Faktor 0,3–1, Versatz 0–3 s")
    check(W({"tipp_faktor": "x", "denkpausen": "nein", "versatz_s": None}) == S and W({"tipp_faktor": float("nan")}) == S,
          "unbrauchbare Werte (Text, NaN, kein bool) → heutiger Wert je Schlüssel")
    check(T(S) is None and T(W({"tipp_faktor": 0.5, "denkpausen": False, "versatz_s": 0.6})) == "Tempo: Tippen ×0,5 · Denkpausen aus · Versatz 0–0,6 s",
          "Spur-Zeile nur bei abweichenden Werten")

    # b) Feld-Takt + ruhige Pausen
    rnd = random.Random(7)
    ok = True
    for _ in range(300):
        t = FT(8, 0.5, zufall=rnd, hand={"tempo": 1.35})
        hs, ab = [h for h, _a in t], [a for _h, a in t]
        ok = ok and len(t) == 8 and max(hs) <= min(hs) * 1.15 / 0.85 + 1e-9 and max(ab) <= min(ab) * 1.15 / 0.85 + 1e-9 \
            and min(hs) >= 0.012 and min(ab) >= 0.008 and max(ab) < 0.09 * 1.35 * 0.5 * 1.15 + 1e-9
    check(ok, "feld_takt: ein Grundwert je Feld (Spanne je Zeichen ±15 %), kein Stocken, nie unter 12/8 ms")
    check(all(h >= 0.012 and a >= 0.008 for h, a in FT(20, 0.3, zufall=random.Random(1), hand={"tempo": 0.75})) and FT(0, 0.5) == []
          and len(FT(3, "kaputt")) == 3, "feld_takt: Untergrenze, n=0, kaputter Faktor → 1,0")
    rnd = random.Random(3)
    ruh = [WD(0.4, 0.3, zufall=rnd, hand=hand, ruhig=True) for _ in range(4000)]
    rnd = random.Random(3)
    laut = [WD(0.4, 0.3, zufall=rnd, hand=hand, ruhig=False) for _ in range(4000)]
    check(max(ruh) <= 0.4 + 0.3 + 1e-9 and min(ruh) >= 0.4 and max(laut) > 0.7 and len(set(round(x, 4) for x in ruh)) > 100,
          f"warte_dauer ruhig: Minimum bleibt, Zugabe ≤ Streuung (max {max(ruh):.2f} s statt {max(laut):.2f} s), Streuung bleibt")
    check(WD(0.4, 0, ruhig=True) == 0.4 and WD(0.4, 0, ruhig=False) == 0.4, "streuung 0 bleibt fest")
    ns["_ECHO_RUHIG"]["an"] = True
    check(max(WD(0.4, 0.3, zufall=random.Random(9), hand=hand) for _ in range(2000)) <= 0.7 + 1e-9, "ruhig=None liest _ECHO_RUHIG des Laufs")
    ns["_ECHO_RUHIG"]["an"] = False

    # c) app.py Cache
    asrc = open(APP, encoding="utf-8").read()
    ans = {}
    konst(asrc, "_PULS_ECHO_CACHE", ans)
    konst(asrc, "PULS_ECHO_CACHE_S", ans)
    exec(fn(asrc, "puls_echo_tempo_lesen"), ans)
    exec(fn(asrc, "puls_echo_tempo_stand"), ans)
    P0, rufe = ans["puls_echo_tempo_stand"], []
    P = lambda t, lesen: P0(t, lesen, sofort=True)

    def gut(tab, params):
        rufe.append((tab, params))
        return [{"puls_echo_tempo": {"tipp_faktor": 0.5}}]

    def kaputt(tab, params):
        rufe.append((tab, params))
        raise RuntimeError("column puls_echo_tempo does not exist")
    check(P(1000.0, kaputt) is None and len(rufe) == 1, "Spalte fehlt → None (Schlüssel fehlt, Bot behält seine Werte)")
    check(P(1030.0, gut) is None and len(rufe) == 1, "Fehl-Cache 60 s: kein zweiter Read")
    check(P(1061.0, gut) == {"tipp_faktor": 0.5} and rufe[-1] == ("wd_farmer_regeln", {"id": "eq.1", "select": "puls_echo_tempo"}),
          "nach 60 s gelesen → Wert, nur die eine Spalte")
    check(P(1200.0, kaputt) == {"tipp_faktor": 0.5}, "DB weg nach gutem Stand → guter Stand bleibt")
    check(P(1300.0, lambda t, p: [{"puls_echo_tempo": None}]) == {}, "Spalte null (Rückbau) → {} = ausdrücklich heutige Werte, der Bot überschreibt seine Datei")
    check(W({"werte": {}}) == S, "Bot: {} aus Railway → heutige Werte")
    import threading as _th
    ans["threading"], gest = _th, []
    ans["_PULS_ECHO_CACHE"].update(at=0.0, laeuft=False)
    def langsam(t, p):
        gest.append(1)
        _th.Event().wait(0.5)
        return [{"puls_echo_tempo": {"tipp_faktor": 0.7}}]
    import time as _t
    t0 = _t.time()
    v = P0(5000.0, langsam)
    check(_t.time() - t0 < 0.2 and v == {} and P0(5000.5, langsam) == {} , "Anfrage wartet nie auf den Read (Hintergrund-Thread, liefert den letzten Stand)")
    _th.Event().wait(0.8)
    check(P0(5001.0, langsam) == {"tipp_faktor": 0.7} and len(gest) == 1, "nach dem Hintergrund-Read neuer Stand, nur EIN Read je Cache-Zeit")
    rt = asrc[asrc.index("def puls_regel_lesen("):asrc.index("return jsonify(out)", asrc.index("def puls_regel_lesen("))]
    check('out["echo_tempo"] = et' in rt and "if et is not None:" in rt and rt.index("puls_regel_stand(time.time())") < rt.index("puls_echo_tempo_stand("),
          "/puls-regel: echo_tempo nur mit Wert, Augen/Topstep-Regel unverändert davor")

    # d) Verdrahtung run()/main
    r = fn(src, "run")
    i_tempo, i_sperre = r.index("_ECHO_TEMPO_LAUF.update(_echo_tempo_lauf())"), r.index("_echo_tipp_sperre_holen(trail)")
    check(i_tempo < i_sperre, "run: Tempo-Werte vor dem ersten Schritt (vor PC-Tipp-Sperre/Login)")
    check('_warte(0.0, float(_ECHO_TEMPO_LAUF.get("versatz_s", 1.2)))' in r and "_warte(0.0, 1.2)\n" not in r, "run: Bot-Versatz aus der Einstellung")
    i_f9, i_ruh, i_pos, i_aus = (r.index('trail.append("F9-Dialog offen")'), r.index('_ECHO_RUHIG["an"] = not _ECHO_TEMPO_LAUF.get("denkpausen", True)'),
                                 r.index('trail.append(f"Position offen @ {fill}")'), r.index('_ECHO_RUHIG["an"] = _ECHO_F9["an"] = False'))
    check(i_f9 < i_ruh < i_pos < i_aus and r.index('_ECHO_F9["an"] = True') > i_f9 and '_ECHO_RUHIG["an"] = _ECHO_F9["an"] = False' in r[i_pos:],
          "ruhig + Tipp-Faktor ab „F9-Dialog offen“ bis „Position offen“")
    m = fn(src, "main")
    check('_ECHO_RUHIG["an"] = _ECHO_F9["an"] = False' in m[m.index("finally:"):], "main: jeder Ausgang setzt ruhig + Tipp-Faktor zurück")
    lauf = fn(src, "_echo_tempo_lauf")
    check("timeout=2.0" in lauf and "daemon=True" in lauf and 'isinstance(d.get("echo_tempo"), dict)' in lauf and "_augen_json_lesen(ECHO_TEMPO_DATEI)" in lauf,
          "_echo_tempo_lauf: Datei sofort, Railway im Hintergrund (2 s), nur ausdrückliche Antwort schreibt")
    rc = fn(src, "run_close")
    check("_warte(0.0, 1.2)" in rc, "Close-Weg unverändert (nicht Teil von ES3)")

    # e) Zeitbudget der Tasten je Feld (Erwartungswert, Hand-Tempo 1,0) — Wert 8 Zeichen („28199.12")
    def ew_tasten(n, tempo):            # tasten_takt: Haltezeit Ø 70 ms, Abstand Ø 55 ms × Ø 1,05, Stocken 8 % × Ø 0,2 s
        return n * (0.07 + 0.055 * 1.05 + 0.08 * 0.2) * tempo
    alt_loesch = ew_tasten(4, 1) + ew_tasten(5, 1) + 0.08 + 0.05 + ew_tasten(3, 1) + ew_tasten(4, 1)   # ^a{DEL}, Pos1+Shift+Ende{DEL}, warte, ^a, Pos1+Shift+Ende
    alt_tipp = 8 * ((0.07 + 0.055 * 1.05 + 0.08 * 0.2) * 0.6 + 0.3 * (0.125 * 1.05 + 0.12 * 0.325))
    neu_mark = ew_tasten(3, 0.5) + ew_tasten(4, 0.5)
    neu_tipp = 8 * (0.07 + 0.055) * 0.5
    alt, neu = alt_loesch + alt_tipp, neu_mark + neu_tipp
    print(f"  Zeitbudget je Feld (Tasten, Erwartungswert): heute {alt:.2f} s (Löschversuch {alt_loesch:.2f} + Tippen {alt_tipp:.2f}) → "
          f"Vorschlag ×0,5 {neu:.2f} s (Markieren {neu_mark:.2f} + Tippen {neu_tipp:.2f}); 3 Felder (Volumen/SL/TP): −{3 * (alt - neu):.1f} s")
    check(3 * (alt - neu) > 5.0, "3 Felder sparen > 5 s Tasten (Ziel Bot bis Fill ~16 s statt 24 s)")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("ALLES GRÜN")


if __name__ == "__main__":
    main()
