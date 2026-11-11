#!/usr/bin/env python3
"""Selbsttest KK1 (Master 11.11.2026): (1) _wd_fruehere_trades schluckt Lesefehler nicht mehr auf den Schreib-/Sperr-Wegen — streng=True wirft,
_wd_sl_kontext versucht es einmal nach 1–3 s erneut, dann fruehere=None → POST /admin/wd-plaene legt den Plan NICHT an (KK1b), SL1-Nachwürfeln schreibt im Takt nichts, Heim-Wache bleibt zu;
Anzeigen wie bisher []. (2) _fdp_regeln_gemerkt: 60 s gemerkt, Lesefehler → letzter guter Stand ≤ 15 min, nur in /konto-ziele benutzt.
Echte Funktionen aus app.py, ohne Netz/DB (Supabase-Aufrufe als Stubs).

Aufruf:  python3 tools/selftest_kk1_fruehere_regeln.py"""
import os
import random
import re
import threading
import time
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "time": time, "threading": threading}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(80):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            n = str(e).split("'")[1]
            lade(n)
    raise RuntimeError(fn)


def kaputt(*_a, **_k):
    raise ConnectionError("Supabase weg")


# ── (1) _wd_fruehere_trades ──
lade("_wd_fruehere_trades")
ns["_sb_all"] = kaputt
check(ruf("_wd_fruehere_trades", ["a1"]) == [], "Anzeige (Standard): Lesefehler → [] wie bisher")
try:
    ruf("_wd_fruehere_trades", ["a1"], streng=True)
    check(False, "streng: Lesefehler wirft")
except ConnectionError:
    check(True, "streng: Lesefehler wirft weiter (kein stilles „keine früheren Trades“)")
ns["_sb_all"] = lambda _t, _p: [{"id": "p1", "master_account_id": "a1"}]
check(ruf("_wd_fruehere_trades", ["a1"], streng=True) == [{"id": "p1", "master_account_id": "a1"}], "streng ohne Fehler: Zeilen wie bisher")

# ── wd_sl_fuer_plan mit fruehere None ──
for n in ("WD_SL_GRUND_FRUEHER", "WD_SL_WUERFEL_STD", "_wd_num", "wd_sl_wuerfeln", "wd_sl_fuer_plan"):
    lade(n)
regel = {"an": True, "stufen": [{"anteil": 0, "von": None, "bis": None}, {"anteil": 100, "von": 10, "bis": 20}]}
acc = {"id": "a1", "firm": "Apex Trader", "account_type": "winning_days", "tv_balance": 152000, "starting_balance": 150000}
w = ruf("wd_sl_fuer_plan", regel, {}, acc, [{"id": 1}], None, rnd=random.Random(1))
check(isinstance(w, dict) and w.get("ohne") is True and w.get("grund") == "frühere Trades nicht lesbar — Puffer unbekannt",
      f"fruehere None → ohne SL mit Grund, auch wenn der Würfel 100 % SL sagt ({w})")
w2 = ruf("wd_sl_fuer_plan", regel, {}, None, [{"id": 1}], None, rnd=random.Random(1))
check(w2.get("grund") == "Konto-Daten nicht lesbar — Puffer unbekannt", "fehlendes Konto bleibt der erste Grund")
check(ruf("wd_sl_fuer_plan", None, {}, acc, [], None) is None, "Würfel aus → None wie bisher")

# ── _wd_sl_kontext ──
lade("_wd_sl_kontext")
lade("_wd_sl_konten_select")   # DL2 (11.11.2026): Konto-Abfrage des WD-SL mit dll_usd (Rückfall ohne Spalte)
ns["_wd_sl_wuerfel_lesen"] = lambda: (regel, "db")
ns["sb_select"] = lambda _t, _p: [acc]
ns["_liq_regeln_laden"] = lambda: [{"id": 1}]
ns["_wd_fruehere_trades"] = lambda ids, streng=False: kaputt() if streng else []
for n in ("WD_SL_FRUEHER_WARTE_S",):
    lade(n)
schlaf = []
ns["time"] = type("T", (), {"sleep": staticmethod(lambda x: schlaf.append(x)), "time": staticmethod(time.time)})
r, konten, liq, fr = ruf("_wd_sl_kontext", ["a1"])
check(r == regel and "a1" in konten and liq and fr is None, "Kontext: zweimal Lesefehler → fruehere None (Konten und liq_regeln bleiben)")
check(len(schlaf) == 1 and 1.0 <= schlaf[0] <= 3.0, f"genau EINE Wiederholung nach 1–3 s gestreuter Pause ({schlaf})")
versuche = {"n": 0}


def einmal_kaputt(ids, streng=False):
    versuche["n"] += 1
    if versuche["n"] == 1:
        raise ConnectionError("kurzer Aussetzer")
    return [{"id": "ok"}]


ns["_wd_fruehere_trades"], schlaf[:] = einmal_kaputt, []
fr2 = ruf("_wd_sl_kontext", ["a1"])[3]
check(fr2 == [{"id": "ok"}] and versuche["n"] == 2 and len(schlaf) == 1, "kurzer Aussetzer: Wiederholung klappt → Zeilen da (Plan wird mit SL gewürfelt)")
ns["_wd_fruehere_trades"] = lambda ids, streng=False: [{"id": "x"}]
check(ruf("_wd_sl_kontext", ["a1"])[3] == [{"id": "x"}], "Kontext ohne Fehler: Zeilen wie bisher")

# ── POST /admin/wd-plaene: Lesefehler → KEIN Plan (KK1b, S2-Stopp) ──
i = app.index("@app.route(\"/admin/wd-plaene\"")
post = app[i:app.index("\n@app.route", i + 10)]
z_rec = post.index("if sl_regel and (wd_ist_recoverer_plan(body)")
z_none = post.index("elif sl_regel and sl_frueher is None:")
z_wurf = post.index("elif sl_regel:\n")
z_ins = post.index('angelegt.append(sb_insert("trade_plans", body))')
blk = post[z_none:z_wurf]
check(z_rec < z_none < z_wurf < z_ins, "Reihenfolge: Recoverer/Ausgleich → frühere Trades nicht lesbar → Würfel → Anlegen")
check('uebersprungen.append({"master_account_id": mid, "grund": WD_SL_GRUND_FRUEHER + WD_SL_FRUEHER_NAECHSTER}); continue' in blk,
      "Lesefehler: übersprungen mit Grund „frühere Trades nicht lesbar — Puffer unbekannt — nächster Lauf“, continue vor dem Anlegen")
check(ns["WD_SL_GRUND_FRUEHER"] + " — nächster Lauf" == "frühere Trades nicht lesbar — Puffer unbekannt — nächster Lauf", "Grundtext")
check('"wd_frueher_unlesbar"' in post and "WD_SL_GRUND_FRUEHER" in post[post.index('"wd_frueher_unlesbar"') - 400:], "Alarm (höchstens stündlich), wenn Pläne deshalb fehlen")
ex = post.index("print(f\"[wd-sl-wuerfel] ⚠️ Kontext:")
check("sl_regel, sl_konten, sl_liq, sl_frueher = None, {}, [], []" in post[ex:ex + 300], "Kontext-Ausnahme: Würfel aus, sl_frueher [] (nicht None) — wie bisher")

# ── KANN: Merker nach dem Speichern leeren ──
check(app.count('_fdp_reg_cache["at"] = 0.0') == 2, "Einstellungs-POST (Regel + IDs) leeren den /konto-ziele-Merker")

# ── Einbau an den Schreib-/Sperr-Wegen, Anzeigen unverändert ──
nach = re.search(r"^def wd_sl_nach_tick\(.*?(?=^\S)", app, re.S | re.M).group(0)
check("frueher = _wd_fruehere_trades(mids, streng=True)" in nach and nach.index("streng=True") < nach.index("except Exception as e:"),
      "SL1-Nachwürfeln: streng im try → Lesefehler = „nächster Takt“, nichts geschrieben")
heim = re.search(r"^def puls_heim_pruefen\(.*?(?=^\S)", app, re.S | re.M).group(0)
check("_wd_fruehere_trades(ids, streng=True)" in heim and heim.index("streng=True") < heim.rindex("except Exception") and "PULS_HEIM_CODE_UNKLAR" in heim[heim.rindex("except Exception"):],
      "Heim-Wache: streng im try → Lesefehler = nicht frei (Puls bleibt im Konto)")
check(len(re.findall(r"_wd_fruehere_trades\([^)]*streng=True\)", app)) == 5, "5 strenge Aufrufer (Kontext, Nachwürfeln, Heim-Wache, Heim-Nähe/Zweit-Prüfung, Hedge-Freigabe)")
naehe = re.search(r"^def _puls_heim_naehe\(.*?(?=^\S)", app, re.S | re.M).group(0)
check("streng=True" in naehe, "Heim-Nähe (Zweit-Prüfung) streng — Aufrufer fangen den Fehler (nicht frei)")
check(len(re.findall(r"_wd_fruehere_trades\((?:ids|acc_ids|kids)\)", app)) == 2, "reine Anzeigen (wd-heute, live-trades) wie bisher")

# ── (2) _fdp_regeln_gemerkt ──
for n in ("FDP_REGELN_CACHE_S", "FDP_REGELN_ALT_S", "_fdp_reg_cache", "_fdp_regeln_gemerkt"):
    lade(n)
zaehl = {"n": 0, "wert": {"id": 1, "firmen": [], "updated_at": "a"}}


def laden():
    zaehl["n"] += 1
    return zaehl["wert"]


ns["_fdp_regeln_laden"] = laden
g = lambda t: ns["_fdp_regeln_gemerkt"](t)   # noqa: E731
check(g(1000)["updated_at"] == "a" and zaehl["n"] == 1, "erster Aufruf liest")
g(1010); g(1059.9)
check(zaehl["n"] == 1, "innerhalb 60 s keine neue Abfrage")
zaehl["wert"] = {"id": 1, "firmen": [], "updated_at": "b"}
check(g(1061)["updated_at"] == "b" and zaehl["n"] == 2, "nach 60 s frisch gelesen")
zaehl["wert"] = None
check(g(1200)["updated_at"] == "b", "Lesefehler → letzter guter Stand (≤ 15 min)")
check(g(1061 + 901) is None, "Lesefehler länger als 15 min → None")
zaehl["wert"] = {"id": 1, "updated_at": "c"}
check(g(1061 + 901 + 61)["updated_at"] == "c", "wieder lesbar → neuer Stand")
kz_txt = app[app.index("def konto_ziele("):app.index("def konto_ziele(") + 20000]
check("_freg = _fdp_regeln_gemerkt() or {}" in kz_txt, "/konto-ziele nutzt die gemerkte Regel")
check(app.count("_fdp_regeln_gemerkt()") == 1, "sonst niemand (Planer, Einstellungen, Schreibwege lesen frisch)")

print()
print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
