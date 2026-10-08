#!/usr/bin/env python3
"""Selbsttest NACHPLANEN neuer Konten (app.py, 08.10.2026; Master/Finn: Finn setzte um 01:20 Dubai fünf IDs in den Planer,
der Nachtlauf war durch — bis zum nächsten hätte niemand Vorschläge bekommen) — ohne Netz.

Aufruf:  python3 tools/selftest_auto_nachplanen.py
Lädt die Auto-Planer-Funktionen wie selftest_auto_delta (per Quelltext aus app.py). Geprüft: ap_nachplan_fenster (Mo–Fr,
00:00 ≤ jetzt < start_bis − 15 min), ap_nachplan_kandidaten (ohne Plan heute, Haken aus / archiviert / fester Grund raus,
Plan anderer Tage blockt nicht, open/review blocken; seit 08.10.2026: Regeln nach dem Lauf geändert → Regel-Gründe nicht mehr fest,
Konto-Gründe bleiben fest; je Tag und Regel-Stand nur EINMAL nachrechnen: ap_nachplan_regeln_at/_merken + ap_nachplan_tick mit
nachgebauter DB), ap_nachplan_letzter (Laufzeit aus Ergebnis/Zeile), ap_planen(nur_konten) gegen die nachgebaute DB: nur das genannte Konto
wird angelegt, bestehender Vorschlag bleibt (kein DELETE), Protokoll quelle 'nachplanen' nur bei Treffer, Startzeit ≥ jetzt + 15 min,
ohne nur_konten unverändert (DELETE + Protokoll). Platzhalter-IDs, keine echten Konten."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

U1, U2 = sd.U1, sd.U2


def lade():
    a = sd.lade()
    src = open(sd.APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    exec("\n".join([re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("AP_NACHPLAN_VORLAUF_MIN", "AP_NACHPLAN_TAKT_S", "AP_TZ_TAG", "AP_NACHPLAN_REST_RE", "AP_REST_MIN_CFD")]
                   + [re.search(rf"^{k} = \([^)]*\)", src, re.M | re.S).group(0)
                      for k in ("AP_NACHPLAN_FEST_GRUENDE", "AP_NACHPLAN_REGEL_GRUENDE")]
                   + [block(f) for f in ("_ap_ts", "ap_nachplan_fenster", "_ap_plan_am_tag", "ap_nachplan_letzter",
                                         "ap_nachplan_ziel_frei", "ap_nachplan_kandidaten", "ap_nachplan_regeln_at", "ap_nachplan_regeln_merken",
                                         # 09.10.2026 Countdown/Knopf: gemeinsame Strecke + Sperre, reine Helfer
                                         "ap_nachplan_naechster", "ap_nachplan_planungstag", "ap_bal_gelesen", "_ap_nachplan_rechnen",
                                         "ap_nachplan_tick")]), a)
    exec("import threading\n" + re.search(r"^_ap_nachplan_lock = .*$", src, re.M).group(0) + "\n"
         + re.search(r"^AP_BAL_FEHLT = .*$", src, re.M).group(0), a)
    # echte Balance-Wahl für ap_bal_gelesen (andere Teile ersetzen acc_balance_wahl durch eine Attrappe mit Stand 2999)
    echt = dict(a)
    for f in ("ist_topstep_express", "acc_balance_wahl"):
        try:
            exec(block(f), echt)
        except Exception:
            pass
    a["_abw_echt"] = echt.get("acc_balance_wahl")
    return a


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    tz = a["_ap_tz"]("Europe/Berlin")
    F = a["ap_nachplan_fenster"]
    z = {"start_bis": "16:30"}
    check(F(datetime(2026, 10, 8, 0, 5, tzinfo=tz), z) and F(datetime(2026, 10, 8, 16, 14, tzinfo=tz), z)
          and not F(datetime(2026, 10, 8, 16, 15, tzinfo=tz), z) and not F(datetime(2026, 10, 10, 9, 0, tzinfo=tz), z),
          "Fenster: 00:05 ja, 16:14 ja, 16:15 nein (start_bis − 15), Samstag nein")

    K = a["ap_nachplan_kandidaten"]
    tag = "2026-10-08"
    konten = [{"id": "k-1", "account_type": "phase1"}, {"id": "k-2", "account_type": "phase2"}, {"id": "k-3", "account_type": "challenge"},
              {"id": "k-4", "account_type": "funded"}, {"id": "k-5", "account_type": "phase1", "auto_planer": False},
              {"id": "k-6", "account_type": "phase1"}, {"id": "k-7", "account_type": "phase1"}, {"id": "k-8", "account_type": "phase1"}]
    plaene = [{"master_account_id": "k-1", "status": "planned", "planned_for": tag},                       # heute geplant → belegt
              {"master_account_id": "k-2", "status": "planned", "planned_for": "2026-10-09"},              # morgen → frei
              {"master_account_id": "k-3", "status": "open"},                                               # läuft → belegt
              {"master_account_id": "k-7", "status": "planned", "start_um": "2026-10-07T23:30:00+00:00"},  # 01:30 dt heute → belegt
              {"master_account_id": "k-8", "status": "completed", "planned_for": tag}]                     # erledigt → frei
    letzter = {"tag": tag, "ausgelassen": [{"konto_id": "k-6", "grund": "keine Regel für diese Firma"},
                                            {"konto_id": "k-8", "grund": "Balance nicht live (seit dem letzten Trade nicht nachgelesen)"}]}
    check(K(konten, plaene, tag, tz, letzter, set()) == ["k-2", "k-8"],
          "Kandidaten: nur Konten ohne Plan heute (k-2 morgen frei, k-8 erledigt + veränderlicher Grund), funded/Haken aus/fester Grund/open/heute raus")
    k2 = K(konten, plaene, tag, tz, {"tag": "2026-10-07", "ausgelassen": [{"konto_id": "k-2", "grund": "keine Regel für diese Firma"}]}, {"k-8"})
    check(k2 == ["k-2", "k-6"], f"Lauf eines anderen Tags zählt nicht (k-6 wieder dabei), Archiv k-8 raus ({k2})")
    # 08.10.2026: Haken wieder gesetzt → Konto ist wieder Kandidat, auch wenn der letzte Lauf „vom Auto-Planer ausgenommen" sagte
    k3 = K([{"id": "k-9", "account_type": "phase1", "auto_planer": True}, {"id": "k-10", "account_type": "phase1", "auto_planer": False}], [], tag, tz,
           {"tag": tag, "ausgelassen": [{"konto_id": "k-9", "grund": "vom Auto-Planer ausgenommen (Haken im Konto aus)"},
                                        {"konto_id": "k-10", "grund": "vom Auto-Planer ausgenommen (Haken im Konto aus)"}]}, set())
    check(k3 == ["k-9"], f"Haken wieder an → k-9 wird nachgeplant, k-10 (Haken aus) bleibt draußen ({k3})")

    # 08.10.2026 (Finn: Chris' Konten nach Regeländerung sofort neu planen): Regeln NACH dem Lauf geändert → Regel-Gründe nicht mehr
    # fest, Konto-Gründe bleiben fest. Zeitformen wie live: Lauf-at aus dem Ergebnis (ISO), updated_at in Postgres-Form („ +00")
    kr = [{"id": f"r-{i}", "account_type": "phase1"} for i in range(1, 9)]
    lauf_r = {"tag": tag, "at": "2026-10-08T03:20:26.709603+00:00", "ausgelassen": [
        {"konto_id": "r-1", "grund": "keine Regel für diese Firma"},
        {"konto_id": "r-2", "grund": "Balance 46.962 passt zu keiner Kontogröße der Regel — stimmt was nicht?"},
        {"konto_id": "r-3", "grund": "kein freies Zeitfenster mehr"},
        {"konto_id": "r-4", "grund": a["AP_GRUND_HEUTE_GEHANDELT"]},
        {"konto_id": "r-5", "grund": "Ziel erreicht — Phase umstellen"},
        {"konto_id": "r-6", "grund": "nur noch 120 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "r-7", "grund": "letzter Trade noch nicht erledigt (Überprüfen)"}]}
    nach = K(kr, [], tag, tz, lauf_r, set(), regeln_at="2026-10-08 03:54:53.115398+00")
    check(nach == ["r-1", "r-2", "r-3", "r-8"],
          f"Regeln nach dem Lauf geändert: „keine Regel“/„Kontogröße“/„kein freies Zeitfenster“ wieder Kandidaten, "
          f"heute gehandelt/Ziel erreicht/bis zum Ziel/letzter Trade bleiben fest ({nach})")
    vor = K(kr, [], tag, tz, lauf_r, set(), regeln_at="2026-10-08T03:10:00.5+00:00")
    check(vor == ["r-8"], f"Regeln VOR dem Lauf geändert: alle Gründe bleiben fest wie bisher ({vor})")
    ohne = K(kr, [], tag, tz, lauf_r, set())
    check(ohne == ["r-8"], f"ohne regeln_at (alte Aufrufe) unverändert: alle Gründe fest ({ohne})")
    ohne_at = K(kr, [], tag, tz, {k: v for k, v in lauf_r.items() if k != "at"}, set(), regeln_at="2026-10-08T03:54:53Z")
    check(ohne_at == ["r-8"], f"Lauf ohne Zeit: lieber wie bisher (fest) als blind neu rechnen ({ohne_at})")
    belegt = K(kr, [{"master_account_id": "r-1", "status": "planned", "planned_for": tag}], tag, tz, lauf_r, set(),
               regeln_at="2026-10-08T03:54:53Z")
    check(belegt == ["r-2", "r-3", "r-8"], f"Regeln neu, aber Konto hat heute schon einen Plan → bleibt draußen ({belegt})")
    # JE TAG UND REGEL-STAND NUR EINMAL (08.10.2026, Befund Slave 2 zu 0ca8e72): plant ap_planen für ein Konto nichts, schreibt es keine
    # auto_plan_lauf-Zeile — ohne Merker würden r-1/r-2/r-3 jeden 10-min-Takt neu gerechnet, bis ein Lauf mit Treffer kommt
    RA, RM = a["ap_nachplan_regeln_at"], a["ap_nachplan_regeln_merken"]
    m = {}
    r1 = RA(m, tag, "2026-10-08 03:54:53+00")
    RM(m, tag, r1)
    r2 = RA(m, tag, "2026-10-08 03:54:53+00")
    r3 = RA(m, tag, "2026-10-08 04:30:00+00")
    RM(m, "2026-10-09", "2026-10-08 04:30:00+00")
    check(r1 == "2026-10-08 03:54:53+00" and r2 is None and r3 == "2026-10-08 04:30:00+00" and m == {"2026-10-09": "2026-10-08 04:30:00+00"}
          and RA({}, tag, None) is None and RM({}, tag, None) == {},
          f"Merker: erst regeln_at, gleicher Stand danach None, neuer Stand wieder regeln_at, alter Tag fliegt raus ({m})")
    # ap_nachplan_tick gegen eine nachgebaute DB: vier Takte, ap_planen plant nichts (wie live bei „keine Regel“)
    # Stubs direkt im Namensraum a (die Funktion sieht dort ihre Globals), am Ende zurück — ap_planen-Tests unten brauchen die echten
    tick_ns = a
    alt = {k: a.get(k) for k in ("sb_select", "_ap_konten_laden", "_sb_all", "_ap_archiviert", "ap_planen")}
    tag_t = "2026-10-08"
    reg_t = {"aktiv": True, "user_ids": [U1], "zeiten": {"start_bis": "16:30"}, "updated_at": "2026-10-08 03:54:53+00"}
    tick_rows = [{"tag": tag_t, "quelle": "nacht", "at": "2026-10-08 03:20:28+00", "ergebnis": lauf_r}]
    aufrufe = []
    tick_ns["sb_select"] = lambda t, q: [dict(reg_t)] if t == "auto_plan_regeln" else ([r for r in tick_rows if q.get("tag") == f"eq.{r['tag']}"] if t == "auto_plan_lauf" else [])
    tick_ns["_ap_konten_laden"] = lambda q: [dict(k, user_id=U1) for k in kr]
    tick_ns["_sb_all"] = lambda t, q: []
    tick_ns["_ap_archiviert"] = lambda: set()
    tick_ns["ap_planen"] = lambda t, quelle=None, nur_konten=None: (aufrufe.append(list(nur_konten or [])), {"ok": True, "geplant": [], "ausgelassen": [
        {"konto_id": k, "grund": "keine Regel für diese Firma"} for k in (nur_konten or [])]})[1]
    zst = {}
    jetzt_t = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)   # 08:00 dt, im Fenster
    T = tick_ns["ap_nachplan_tick"]
    T(jetzt_t, zst); zst["nachplan_at"] = 0
    T(jetzt_t + timedelta(minutes=10), zst); zst["nachplan_at"] = 0
    reg_t["updated_at"] = "2026-10-08 06:05:00+00"                 # Finn ändert die Regeln erneut
    T(jetzt_t + timedelta(minutes=20), zst); zst["nachplan_at"] = 0
    T(jetzt_t + timedelta(minutes=30), zst)
    check(aufrufe == [["r-1", "r-2", "r-3", "r-8"], ["r-8"], ["r-1", "r-2", "r-3", "r-8"], ["r-8"]],
          f"Tick: Regeländerung → einmal nachrechnen, nächster Takt nur noch r-8, neuer Regel-Stand → wieder einmal ({aufrufe})")
    check(zst.get("nachplan_regeln") == {tag_t: "2026-10-08 06:05:00+00"}, f"Merker im Prozess-Speicher je Tag ({zst.get('nachplan_regeln')})")
    # wirft ap_planen, wird NICHT gemerkt → der nächste Takt rechnet neu
    zst2, aufrufe2 = {}, []
    def wirft(t, quelle=None, nur_konten=None):
        aufrufe2.append(list(nur_konten or []))
        raise RuntimeError("DB weg")
    tick_ns["ap_planen"] = wirft
    try:
        T(jetzt_t, zst2)
    except RuntimeError:
        pass
    check(zst2.get("nachplan_regeln", {}) == {} and aufrufe2 == [["r-1", "r-2", "r-3", "r-8"]], f"Fehler in ap_planen → nichts gemerkt ({zst2.get('nachplan_regeln')})")
    for k, v in alt.items():
        if v is None:
            a.pop(k, None)
        else:
            a[k] = v

    # ap_nachplan_letzter: Laufzeit aus dem Ergebnis, sonst aus der Zeile (Nachtlauf-Claim, ältere Zeilen)
    L = a["ap_nachplan_letzter"]
    l1 = L([{"tag": tag, "at": "2026-10-08 03:20:28.272621+00", "ergebnis": {"tag": tag, "at": "2026-10-08T03:20:26.709603+00:00"}}])
    l2 = L([{"tag": tag, "at": "2026-10-08 03:20:28.272621+00", "ergebnis": {"tag": tag, "ausgelassen": []}}])
    check(l1["at"] == "2026-10-08T03:20:26.709603+00:00" and l2["at"] == "2026-10-08 03:20:28.272621+00" and L([]) == {}
          and L([{"tag": tag, "at": "x", "ergebnis": None}]) == {},
          "ap_nachplan_letzter: at aus dem Ergebnis, sonst Zeilen-at; ohne Zeile/Ergebnis leer")
    nach_l2 = K(kr, [], tag, tz, dict(lauf_r, at=l2["at"]), set(), regeln_at="2026-10-08 03:54:53.115398+00")
    check(nach_l2 == ["r-1", "r-2", "r-3", "r-8"], f"Zeilen-at (Postgres-Form) als Laufzeit reicht für den Vergleich ({nach_l2})")

    # ap_planen mit nur_konten gegen die nachgebaute DB
    jetzt = datetime(2026, 10, 8, 7, 0, tzinfo=timezone.utc)
    # Start relativ zur ECHTEN Uhr: ap_planen rechnet mit datetime.now — ein fester 08.10.-Vorschlag ist ab dem Folgetag eine verfallene
    # Leiche (ap_plan_verfallen, .1373) und blockiert zu Recht nicht mehr (Test war am 09.10.2026 rot, Slave-Terminal 4)
    vs_start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=3)
    vorschlag = {"id": "p-alt", "user_id": U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "buy",
                 "master_tp": 1000, "master_sl": 500, "master_contracts": 1, "auto_plan": True, "auto_bestaetigt_at": None,
                 "start_um_gestartet_at": None, "start_um": vs_start.isoformat(), "planned_for": vs_start.astimezone(tz).date().isoformat(), "route": "mt5v2",
                 "mt5_baseline": {}}
    reg, gesch = sd.db_stubs(a, jetzt, geplant_extra=[vorschlag])
    protokoll = []
    a["sb_insert"] = lambda table, body: protokoll.append((table, body))
    class R2:
        status_code = 201

        def raise_for_status(self):
            return None
    a["_sb_anfrage"] = lambda *x, **k: (gesch["post"].append((x, k)), R2())[1]
    konten_db = a["_sb_all"]("accounts", {})
    ziel = next((k["id"] for k in konten_db if k["user_id"] == U1 and k["id"] != "k-2" and k["account_type"] in a["AP_TYPEN"]), None)
    check(ziel is not None, f"Fixture hat ein planbares Konto für nur_konten ({ziel})")
    vorher = datetime.now(timezone.utc)
    erg = a["ap_planen"](None, quelle="nachplanen", nur_konten=[ziel], seed=7)   # heute (Dubai) wie der Takt
    geplant = erg.get("geplant") or []
    posts = [x for x in gesch["post"] if x[0][0] == "POST"]
    deletes = [x for x in gesch["post"] if x[0][0] == "DELETE"]
    check(erg.get("ok") and erg.get("quelle") == "nachplanen" and erg.get("nur_konten") == [ziel], "Lauf ok, quelle nachplanen, nur_konten in der Antwort")
    check(all(g["konto_id"] == ziel for g in geplant) and all(z["konto_id"] == ziel for z in erg.get("ausgelassen") or []),
          f"nur das genannte Konto gerechnet (geplant {len(geplant)}, ausgelassen {len(erg.get('ausgelassen') or [])})")
    check(not deletes, "kein DELETE — bestehender Vorschlag p-alt bleibt")
    if geplant:
        zeilen = posts[-1][1]["json"] if posts else []
        start = datetime.fromisoformat(zeilen[0]["start_um"]) if zeilen else None
        check(len(zeilen) == len(geplant) and start is not None and start >= vorher + timedelta(minutes=14),
              f"angelegt {len(zeilen)} Zeile(n), Start {start} ≥ jetzt + 15 min (jetzt {vorher.strftime('%H:%M')} UTC)")
        check(len(protokoll) == 1 and protokoll[0][0] == "auto_plan_lauf" and protokoll[0][1]["quelle"] == "nachplanen",
              "Protokoll genau einmal mit quelle nachplanen")
    else:
        check(not posts and not protokoll, f"nichts geplant ({(erg.get('ausgelassen') or [{}])[0].get('grund')}) → kein POST, kein Protokoll")
    # Konto ohne Chance (nur_konten mit k-2, das schon den Vorschlag hat): nichts geplant → kein Protokoll, kein DELETE
    protokoll.clear(); gesch["post"].clear()
    erg2 = a["ap_planen"](None, quelle="nachplanen", nur_konten=["k-2"], seed=7)
    check(not (erg2.get("geplant") or []) and any("schon einen geplanten" in z.get("grund", "") for z in erg2.get("ausgelassen") or [])
          and not protokoll and not gesch["post"], "bestehender Vorschlag zählt als Plan → ausgelassen, kein Protokoll, nichts geschrieben")
    # ohne nur_konten wie bisher: Vorschlag wird ersetzt (DELETE) und Protokoll geschrieben
    protokoll.clear(); gesch["post"].clear()
    erg3 = a["ap_planen"](None, quelle="hand", seed=7)
    check(erg3.get("ok") and any(x[0][0] == "DELETE" for x in gesch["post"]) and len(protokoll) == 1 and protokoll[0][1]["quelle"] == "hand",
          "ohne nur_konten unverändert: DELETE der Vorschläge + Protokoll")
    # ── COUNTDOWN + „JETZT NEU BERECHNEN" + „seit dem Lauf gelesen" (Finn 09.10.2026) ──
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    tzb = a["_ap_tz"](a["AP_TZ_TAG"]) if "_ap_tz" in a else __import__("zoneinfo").ZoneInfo("Europe/Berlin")
    zeiten = {"start_bis": "18:00"}
    N, P, G = a["ap_nachplan_naechster"], a["ap_nachplan_planungstag"], a["ap_bal_gelesen"]
    jetzt = _dt(2026, 10, 8, 8, 3, tzinfo=tzb).astimezone(_tz.utc)                       # Do 08:03 dt, im Fenster
    t, art = N(jetzt, (jetzt - _td(minutes=7)).timestamp(), zeiten, tzb)
    check(art == "takt" and abs((t - jetzt).total_seconds() - 180) < 1, f"im Fenster: nächster Takt = letzter + 10 min (in 3 min) → {art} {t}")
    abend = _dt(2026, 10, 8, 22, 15, tzinfo=tzb).astimezone(_tz.utc)                       # Do 22:15 dt, Fenster zu
    t2, art2 = N(abend, (abend - _td(minutes=4)).timestamp(), zeiten, tzb)
    t2d = t2.astimezone(tzb)
    check(art2 == "fenster" and t2d.date().isoformat() == "2026-10-09" and t2d.hour == 0 and t2d.minute < 10,
          f"abends nach dem Fenster: ab 00:00 dt des nächsten Werktags, auf den 10-min-Rhythmus → {art2} {t2d.isoformat()}")
    sa = _dt(2026, 10, 10, 12, 0, tzinfo=tzb).astimezone(_tz.utc)                          # Sa 12:00 dt
    t3, art3 = N(sa, None, zeiten, tzb)
    check(art3 == "fenster" and t3.astimezone(tzb).strftime("%a %H:%M") == "Mon 00:00", f"Wochenende: Mo 00:00 dt → {t3.astimezone(tzb)}")
    check(P("2026-10-08", "2026-10-09") == "2026-10-09", "Planungstag vor 00:00 dt: der Tag des letzten Nachtlaufs (kommender Handelstag)")
    check(P("2026-10-09", "2026-10-09") == "2026-10-09", "Planungstag nach 00:00 dt: heute (Nachtlauf lief für heute)")
    check(P("2026-10-10", "2026-10-09") is None and P("2026-10-10", None) is None, "Wochenende/kein Lauf: kein Planungstag (Lauf-Tag vorbei)")
    lauf_at = "2026-10-08T21:30:15+00:00"
    aus = [{"konto_id": "k-1", "grund": "keine Balance bekannt"}, {"konto_id": "k-2", "grund": "keine Balance bekannt"},
           {"konto_id": "k-3", "grund": "nur noch 36 $ bis zum Ziel — von Hand prüfen"}, {"konto_id": "k-4", "grund": "Balance nicht live"}]
    accs = {"k-1": {"id": "k-1", "firm": "Tradeify", "account_type": "challenge", "tv_balance": 150000, "tv_balance_at": "2026-10-08T21:44:00+00:00"},
            "k-2": {"id": "k-2", "firm": "Tradeify", "account_type": "challenge", "tv_balance": 150000, "tv_balance_at": "2026-10-08T20:00:00+00:00"},
            "k-3": {"id": "k-3", "firm": "FundedNext", "account_type": "phase1", "tv_balance": 107964, "tv_balance_at": "2026-10-08T22:00:00+00:00"},
            "k-4": {"id": "k-4", "firm": "FundedNext", "account_type": "phase1", "external_id": "123", "tv_balance": None}}
    echo = {"123": (101000, "USD", "2026-10-08T21:50:00+00:00")}
    alt_abw = a.get("acc_balance_wahl")
    a["acc_balance_wahl"] = a["_abw_echt"]
    gl = G(aus, lauf_at, accs, echo, {})
    check(set(gl) == {"k-1", "k-4"}, f"seit dem Lauf gelesen: TV-Lesung danach (k-1) und Echo danach (k-4); vorher gelesen (k-2) und anderer Grund (k-3) nicht → {sorted(gl)}")
    check(G(aus, None, accs, echo, {}) == {}, "ohne Laufzeit: nichts als gelesen markiert")
    a["acc_balance_wahl"] = alt_abw
    _src = open(sd.APP, encoding="utf-8").read()
    _i = _src.find('if body.get("nachplanen"):')
    _blk = _src[_i:_src.find("_ap_nachplan_rechnen(ptag", _i)]
    check(_i > 0 and 'reg.get("aktiv")' in _blk and "Auto-Planer ist aus" in _blk,
          "Knopf „Jetzt neu berechnen“ prüft den Not-Aus (aktiv) vor dem Rechnen")
    print("\nNACHPLANEN:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
