#!/usr/bin/env python3
"""Selbsttest PAYOUT OFFEN = RAUS / ABGEHAKT = WIEDER REIN (app.py wd_payout_abgleich, 03.11.2026 — Finn ~18:15 Dubai: „Ein Account, der eine offene
Payout-Anfrage hat, wird nicht Winning-Day-gefarmt … Kein Trade wird geschadet. Sobald ich den Payout abhake, soll der Account, wenn es am gleichen Tag
ist, wieder an dem Tag reingemacht werden."). Rein rechnend, ohne Netz, Platzhalter-IDs. Fenster wie live: 04:00–16:30 Dubai.
Fälle: Anfrage 02:00 mit geplantem WD → Plan zurückgezogen, Konto raus (auch Folgetag); laufender Trade bleibt; Abhaken 12:00 → heute Startzeit
(nach_start, Zeile ohne Block bekommt Start + Richtung, „fertig" geht auf „geplant"); Abhaken 17:00 → ab morgen; heute schon getradet → ab morgen;
Block liegt noch vor uns → kein nach_start. Aufruf: python3 tools/selftest_wd_payout.py"""
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("wd_cme_tag_start", "wd_payout_abgleich")
KONSTANTEN = ("WD_HINWEIS_PAYOUT", "WD_HINWEIS_PAYOUT_MORGEN", "WD_HINWEIS_FARM", "WD_HINWEIS_EXT", "WD_HINWEIS_ARCHIV", "WD_PAYOUT_NACH_MIN", "WD_KONTO_ABSTAND_S")
FEHLER = []


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "threading": threading, "time": time}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


DUBAI = timezone(timedelta(hours=4))
REG = {"tz": "Asia/Dubai", "start_hhmm": "04:00", "bis_hhmm": "16:30"}
K, K2, U = "aaaaaaaa-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000002", "uuuuuuuu-0000-0000-0000-000000000001"
P = "pppppppp-0000-0000-0000-000000000001"


def dub(h, m=0, tag=4):
    return datetime(2026, 11, tag, h, m, tzinfo=DUBAI).astimezone(timezone.utc)


def iso(d):
    return d.isoformat().replace("+00:00", "Z")


def zeile(tag, konten, **x):
    konten = [dict({"ext": "EXT-PLATZHALTER", "farm": True}, **k) for k in konten]
    return dict({"tag": tag, "user_id": U, "status": "geplant", "start_um": None, "richtung": None, "reihenfolge": 1, "updated_at": "t0",
                 "konten": konten}, **x)


def main():
    ns = lade()
    ab, HP, HM = ns["wd_payout_abgleich"], ns["WD_HINWEIS_PAYOUT"], ns["WD_HINWEIS_PAYOUT_MORGEN"]
    fest = lambda: 0.5   # noqa: E731 — Zufall fest: Start jetzt + 15 min

    # 1) Anfrage 02:00 Dubai, Zeile heute gewürfelt (Block 08:00), Plan geplant + nie geclaimt → zurückgezogen, raus; morgen ebenfalls raus
    heute = zeile("2026-11-04", [{"id": K, "aktiv": True, "hinweis": "", "plan_id": P, "status": "planned"},
                                 {"id": K2, "aktiv": True, "hinweis": ""}], start_um=iso(dub(8)), richtung="buy")
    morgen = zeile("2026-11-05", [{"id": K, "aktiv": True, "hinweis": ""}])
    plan = {"id": P, "master_account_id": K, "status": "planned", "start_um_gestartet_at": None, "started_at": None, "orbit_gesendet_at": None,
            "created_at": iso(dub(0, 15))}
    up = ab([heute, morgen], {K}, [plan], dub(2), REG, fest)
    u0 = next((u for u in up if u["tag"] == "2026-11-04"), None)
    k0 = next(k for k in (u0 or {"felder": {"konten": []}})["felder"]["konten"] if k["id"] == K) if u0 else {}
    check(u0 is not None and u0["loeschen"] == [P], "Anfrage 02:00: geplanter, nie geclaimter WD-Plan wird zurückgezogen")
    check(k0.get("aktiv") is False and k0.get("hinweis") == HP and not k0.get("plan_id"), "Anfrage 02:00: Konto heute raus, Hinweis „Payout angefragt“")
    k2 = next(k for k in u0["felder"]["konten"] if k["id"] == K2)
    check(k2.get("aktiv") is True and "status" not in u0["felder"], "das zweite Konto der ID fährt weiter, Zeile bleibt geplant")
    u1 = next((u for u in up if u["tag"] == "2026-11-05"), None)
    check(u1 is not None and u1["felder"]["konten"][0]["aktiv"] is False and u1["felder"]["konten"][0]["hinweis"] == HP and not u1["loeschen"],
          "Anfrage: Folgetag ebenfalls raus (Nachtlauf plant es nicht ein)")
    check(not ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}])], {K}, [], dub(3), REG, fest), "schon raus → nichts zu schreiben")

    # 2) Laufender Trade bleibt (geclaimt bzw. offen) — nichts gelöscht, Konto unverändert
    for name, extra in (("geclaimt", {"start_um_gestartet_at": iso(dub(8))}), ("offen", {"status": "open", "started_at": iso(dub(8))})):
        p2 = dict(plan, **extra)
        r = ab([zeile("2026-11-04", [{"id": K, "aktiv": True, "hinweis": "", "plan_id": P, "status": p2["status"]}], start_um=iso(dub(8)))],
               {K}, [p2], dub(8, 5), REG, fest)
        check(r == [], f"laufender Trade ({name}) bleibt unangetastet")
    r = ab([zeile("2026-11-04", [{"id": K, "aktiv": True, "hinweis": "", "plan_id": P}])], {K}, [], dub(9), REG, fest)
    check(r == [], "Plan nicht gelesen → Konto nicht anfassen")

    # 3) Abhaken 12:00 Dubai → heute wieder rein mit eigener Startzeit; Block (08:00) vorbei, Zeile „fertig" → „geplant"
    z = zeile("2026-11-04", [{"id": K2, "aktiv": True, "plan_id": "x", "status": "completed"}, {"id": K, "aktiv": False, "hinweis": HP}],
              status="fertig", start_um=iso(dub(8)), richtung="sell")
    r = ab([z], set(), [], dub(12), REG, fest)
    k = next(k for k in r[0]["felder"]["konten"] if k["id"] == K) if r else {}
    check(k.get("aktiv") is True and k.get("hinweis") == "" and k.get("nach_start") == iso(dub(12, 15)), "Abhaken 12:00: heute rein, Start 12:15 Dubai")
    check(r and r[0]["felder"].get("status") == "geplant" and "start_um" not in r[0]["felder"], "Abhaken 12:00: Zeile „fertig“ → „geplant“, Block bleibt")
    # ohne Block (nie gewürfelt, Fall Aurel) → Zeile bekommt Start + Richtung + Reihenfolge
    z = zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], reihenfolge=None)
    r = ab([z, zeile("2026-11-04", [], user_id="andere", reihenfolge=7)], set(), [], dub(12), REG, fest)
    f = r[0]["felder"] if r else {}
    check(f.get("start_um") == iso(dub(12, 15)) and f.get("richtung") in ("buy", "sell") and f.get("reihenfolge") == 8,
          "Abhaken 12:00 ohne Block: Zeile bekommt Start 12:15, Richtung, Reihenfolge hinten")
    # Block liegt noch vor uns (14:00) → fährt mit dem Block, kein nach_start
    z = zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], start_um=iso(dub(14)), richtung="buy")
    r = ab([z], set(), [], dub(12), REG, fest)
    k = r[0]["felder"]["konten"][0] if r else {}
    check(k.get("aktiv") is True and "nach_start" not in k, "Abhaken 12:00, Block 14:00: Konto fährt mit seinem Block")
    # vor dem Fenster (03:00) → frühestens Fensterbeginn 04:00
    z = zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], start_um=iso(dub(3)), status="verpasst")
    r = ab([z], set(), [], dub(3, 30), REG, fest)
    check(r and r[0]["felder"]["konten"][0].get("nach_start") == iso(dub(4)), "Abhaken 03:30: Start frühestens zum Fenster 04:00")

    # 4) Abhaken 17:00 Dubai → Fenster zu: heute „ab morgen", morgen rein
    z = zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], start_um=iso(dub(8)), status="fertig")
    zm = zeile("2026-11-05", [{"id": K, "aktiv": False, "hinweis": HP}])
    r = ab([z, zm], set(), [], dub(17), REG, fest)
    kh = next(u for u in r if u["tag"] == "2026-11-04")["felder"]["konten"][0]
    km = next(u for u in r if u["tag"] == "2026-11-05")["felder"]["konten"][0]
    check(kh.get("aktiv") is False and kh.get("hinweis") == HM and "status" not in next(u for u in r if u["tag"] == "2026-11-04")["felder"],
          "Abhaken 17:00: heute „ab morgen wieder drin“, Zeile bleibt fertig")
    check(km.get("aktiv") is True and km.get("hinweis") == "", "Abhaken 17:00: Folgetag wieder drin")
    check(ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HM}])], set(), [], dub(17, 5), REG, fest) == [], "„ab morgen“ bleibt heute stehen")
    # 16:20 → Start wäre 16:35 > 16:30 − 1 min → ab morgen
    r = ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], start_um=iso(dub(8)))], set(), [], dub(16, 20), REG, fest)
    check(r and r[0]["felder"]["konten"][0]["hinweis"] == HM, "Abhaken 16:20: Start passt nicht mehr ins Fenster → ab morgen")

    # 5) heute schon getradet (Start im CME-Tag) → ab morgen, nie ein zweiter Trade
    pt = {"id": "q", "master_account_id": K, "status": "completed", "started_at": iso(dub(7)), "created_at": iso(dub(1))}
    r = ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], start_um=iso(dub(8)))], set(), [pt], dub(12), REG, fest)
    check(r and r[0]["felder"]["konten"][0]["hinweis"] == HM, "heute schon getradet → ab morgen")
    # gestern getradet zählt nicht
    pg = dict(pt, started_at=iso(dub(9, tag=3)), created_at=iso(dub(1, tag=3)))
    r = ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], start_um=iso(dub(8)))], set(), [pg], dub(12), REG, fest)
    check(r and r[0]["felder"]["konten"][0].get("nach_start"), "gestern getradet → heute wieder rein")

    # 6) Konten ohne Payout-Hinweis bleiben, wie sie sind; Zeilen von gestern werden nicht angefasst
    check(ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": "Ziel schon voll"}])], set(), [], dub(12), REG, fest) == [],
          "fremder Hinweis (Ziel schon voll) bleibt")
    check(ab([zeile("2026-11-03", [{"id": K, "aktiv": True}])], {K}, [], dub(12), REG, fest) == [], "Zeile von gestern bleibt")
    # 7) Gegenprüfung W1: Grund bleibt, 80 s Abstand, Folgetag „leer", vor dem Fenster, Plan gibt es nicht mehr
    r = ab([zeile("2026-11-05", [{"id": K, "aktiv": False, "hinweis": HP, "farm": False}])], set(), [], dub(12), REG, fest)
    check(r and r[0]["felder"]["konten"][0]["aktiv"] is False and r[0]["felder"]["konten"][0]["hinweis"] == ns["WD_HINWEIS_FARM"],
          "Haken aus bleibt beim Wieder-Rein draußen (mit seinem Grund)")
    r = ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}, {"id": K2, "aktiv": False, "hinweis": HP}], start_um=iso(dub(8)))],
           set(), [], dub(12), REG, fest)
    ks = r[0]["felder"]["konten"] if r else []
    t1, t2 = (datetime.fromisoformat(k["nach_start"].replace("Z", "+00:00")) for k in ks) if len(ks) == 2 else (None, None)
    check(t1 and t2 and abs((t2 - t1).total_seconds()) >= 80, "zwei Konten derselben ID: Startzeiten ≥ 80 s auseinander")
    r = ab([zeile("2026-11-05", [{"id": K, "aktiv": False, "hinweis": HP}], status="leer")], set(), [], dub(12), REG, fest)
    check(r and r[0]["felder"].get("status") == "geplant", "Folgetag „leer“ → „geplant“ (sonst würfelt der Tageslauf nicht)")
    r = ab([zeile("2026-11-04", [{"id": K, "aktiv": False, "hinweis": HP}], status="leer")], set(), [], dub(0, 5), REG, fest)
    check(r and "start_um" not in r[0]["felder"] and "nach_start" not in r[0]["felder"]["konten"][0] and r[0]["felder"].get("status") == "geplant",
          "Abhaken 00:05, Zeile ungewürfelt: kein fester Start, der Tageslauf würfelt")
    r = ab([zeile("2026-11-04", [{"id": K, "aktiv": True, "hinweis": "", "plan_id": P}])], {K}, [], dub(9), REG, fest, geprueft=[P])
    check(r and r[0]["felder"]["konten"][0]["plan_id"] is None and r[0]["felder"]["konten"][0]["hinweis"] == HP and not r[0]["loeschen"],
          "Plan per ID gelesen und weg → Verweis raus, Konto raus")
    # 8) PC-Tab (S2-Stopp zu 445103b7): bei offenem Payout löscht der Tab nie; jedes Löschen eines abgewählten Kontos nur mit DB-Guard
    html = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
    i = html.index("        if(!wdAktiv(k)){\n          // PAYOUT OFFEN (S2-Stopp")
    blk = html[i:html.index("          continue\n        }", i)]
    check(blk.index("if(wdPayoutHinweis(k.hinweis)) continue") < blk.index(".delete()"), "Tab: Payout-Hinweis → weiter, bevor gelöscht wird")
    check(re.search(r"\.delete\(\)\.eq\('id', plan\.id\)\.eq\('status', 'planned'\)\s*\.is\('start_um_gestartet_at', null\)\.is\('started_at', null\)"
                    r"\.is\('orbit_gesendet_at', null\)\.select\('id'\)", blk) is not None, "Tab: Löschen nur geplant, nie geclaimt/gestartet/gesendet")
    check(blk.index("if(!eWeg && weg && weg.length)") < blk.index("set(k, 'plan_id', null)"), "Tab: plan_id nur leeren, wenn wirklich gelöscht")
    check(html.count(".from('trade_plans').delete().eq('id', plan.id)\n") == 0, "kein ungesichertes Löschen per plan.id mehr im Farmer")
    j = html.index("function suStartetNichtWeil(")
    check("wdPayoutOffen(p.masterAccountId)) return WD_HINWEIS_PAYOUT" in html[j:j + 3000], "Start-Wächter: Farmer-Plan mit offenem Payout startet nicht")
    if FEHLER:
        print(f"\n{len(FEHLER)} Fehler")
        sys.exit(1)
    print("\nalle grün")


if __name__ == "__main__":
    main()
