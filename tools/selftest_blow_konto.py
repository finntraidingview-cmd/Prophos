#!/usr/bin/env python3
"""Selbsttest: GEBLOWTE KONTEN AUS „BRAUCHT DICH" VON SELBST ARCHIVIEREN (app.py ap_blow_konto_boden + ap_blow_konto_pruefen, Finn 26.10.2026:
„Der Current Balance unter dem Max Loss. Deswegen einfach hier automatisch wegblowen, fertig."). Rein rechnend, Funktionen per Quelltext aus
app.py (wie selftest_apex_geblowt). Aufruf: python3 tools/selftest_blow_konto.py"""
import os
import re
import sys
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    konst = [re.search(rf"^{k} = .*$", src, re.M).group(0).split("  #")[0] for k in ("AP_BLOW_KONTO_RE", "AP_BLOW_KONTO_QUELLEN")]
    exec("\n".join(konst + [block(f) for f in ("_wd_num", "_wd_konto_groesse", "ist_topstep_express", "_ap_iso_ts",
                                                 "ap_blow_konto_boden", "ap_blow_konto_pruefen")]), ns)
    return ns


def main():
    ns = lade()
    pruefen, boden = ns["ap_blow_konto_pruefen"], ns["ap_blow_konto_boden"]
    # Fall wie am 26.10.2026: Topstep 150k Challenge, Planer-Grund „Balance auf/unter dem Boden — geblowt?", Puls-Lesung nach dem letzten Trade
    zeile = {"konto_id": "k1", "user_id": "u1", "konto": "150k 150KTC-000000-00000000 → Challenge", "grund": "Balance auf/unter dem Boden — geblowt?",
             "boden": 145500.0, "boden_min": 145500.0}
    acc = {"id": "k1", "user_id": "u1", "name": zeile["konto"], "firm": "Topstep", "account_type": "challenge", "external_id": "150KTC-000000-00000000",
           "tv_balance": 145447.2, "tv_balance_at": "2026-10-26T12:20:37.316+00:00", "tv_balance_quelle": "puls"}
    plaene = [{"id": "p1", "status": "completed", "ended_at": "2026-10-15T23:02:00+00:00"}]
    k = pruefen(zeile, acc, plaene)
    check(bool(k) and k["balance"] == 145447.2 and k["boden"] == 145500.0, f"Lesung 145.447 ≤ Boden 145.500 → archivieren ({k})")
    check(bool(pruefen(zeile, dict(acc, tv_balance=145500.0), plaene)), "Lesung genau auf dem Boden → archivieren")
    check(pruefen(zeile, dict(acc, tv_balance=145500.01), plaene) is None, "Lesung über dem Boden → bleibt")
    check(pruefen(zeile, acc, plaene, archiviert=True) is None, "schon archiviert → nichts")
    check(pruefen(zeile, None, plaene) is None, "Konto nicht gefunden → nichts")
    check(pruefen(dict(zeile, konto_id="k2"), acc, plaene) is None, "Zeile gehört zu einem anderen Konto → nichts")
    check(pruefen(dict(zeile, grund="Balance nicht live (seit dem letzten Trade nicht nachgelesen)"), acc, plaene) is None, "kein Geblowt-Grund → nichts")
    check(bool(pruefen(dict(zeile, grund="letzter Trade -4.480 $ (≥ 95 % des Drawdowns 4.500 $) — geblowt?"), acc, plaene)), "Grund „letzter Trade … geblowt?“ zählt")
    check(bool(pruefen(dict(zeile, grund="Polster aufgebraucht"), acc, plaene)), "Grund „Polster aufgebraucht“ zählt (wie istBlow)")
    # nur echte, frische Lesung
    check(pruefen(zeile, dict(acc, tv_balance_quelle="dashboard"), plaene) is None, "Dashboard-Übernahme → bleibt")
    check(bool(pruefen(zeile, dict(acc, tv_balance_quelle=None), plaene)), "Quelle null (Puls vor F11) zählt")
    check(bool(pruefen(zeile, dict(acc, tv_balance_quelle="mt5"), plaene)), "MT5-Lesung zählt")
    check(pruefen(zeile, dict(acc, tv_balance_at="2026-10-15T22:00:00+00:00"), plaene) is None, "Lesung älter als der letzte Trade → bleibt")
    check(pruefen(zeile, dict(acc, tv_balance_at="2026-10-15T23:02:00+00:00"), plaene) is None, "Lesung genau zum Trade-Ende → bleibt")
    check(pruefen(zeile, dict(acc, tv_balance_at=None), plaene) is None, "Lesung ohne Zeitstempel → bleibt")
    check(pruefen(zeile, dict(acc, tv_balance=None), plaene) is None, "ohne Balance → bleibt")
    check(pruefen(zeile, acc, []) is None, "Konto ohne beendeten Trade → bleibt")
    check(pruefen(zeile, acc, plaene + [{"id": "p2", "status": "open"}]) is None, "Trade läuft → bleibt")
    check(pruefen(zeile, acc, plaene + [{"id": "p2", "status": "review", "ended_at": "2026-10-16T10:00:00+00:00"}]) is None, "Trade in „Überprüfen“ → bleibt (Radar)")
    check(bool(pruefen(zeile, acc, plaene + [{"id": "p3", "status": "planned"}])), "geplanter Trade hält nicht auf (räumt der Sweep)")
    check(pruefen(zeile, dict(acc, account_type="funded"), plaene) is None, "Topstep Express/Funded liest 0-basiert → nie")
    check(pruefen(zeile, dict(acc, name="150k XFA-000000"), plaene) is None, "Kennung XFA → nie")
    # Boden wie tplBlowBoden
    check(boden({"boden": 145500, "boden_min": 145000}, None) == 145500, "boden schlägt boden_min")
    check(boden({"boden": None, "boden_min": 145000}, None) == 145000, "ohne boden → boden_min")
    check(boden({"grund": "letzter Trade -4.400 $ (≥ 95 % des Drawdowns 4.500 $) — geblowt?", "konto": "150k Test"}, None) == 145500, "Größe 150k − DD 4.500 aus dem Grund")
    check(boden({"grund": "letzter Trade -2.900 $ (≥ 95 % des Drawdowns 3.000 $) — geblowt?", "konto": "Test"}, {"starting_balance": 100000}) == 97000,
          "Größe aus starting_balance, wenn der Name keine hat")
    check(boden({"grund": "Balance auf/unter dem Boden — geblowt?", "konto": "150k Test"}, None) is None, "ohne Boden-Felder und ohne DD → unbekannt")
    check(pruefen(dict(zeile, boden=None, boden_min=None), acc, plaene) is None, "Boden unbekannt → bleibt (Finn entscheidet)")
    if FEHLER:
        print(f"\n✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("\n✓ alle Prüfungen grün")


if __name__ == "__main__":
    main()
