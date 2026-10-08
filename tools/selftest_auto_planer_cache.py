#!/usr/bin/env python3
"""Selbsttest: 60-s-Cache für auto_plan_regeln.user_ids (app.py _ap_planer_ids / _ap_im_planer / _ap_planer_cache_leeren, 08.10.2026,
Slave 2: /delta fragte je Admin-Tab alle paar Sekunden ungecacht). Rein rechnend, DB und Uhr nachgebaut.
Aufruf: python3 tools/selftest_auto_planer_cache.py"""
import os
import re
import sys
import threading

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


class Uhr:
    t = 1000.0

    def time(self):
        return self.t


def lade():
    src = open(APP, encoding="utf-8").read()
    uhr = Uhr()
    ns = {"time": uhr, "_kurz_cache_lock": threading.Lock()}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("AUTH_LISTE_CACHE_S", "_ap_planer_cache")]
    for name in ("_ap_planer_ids", "_ap_planer_cache_leeren", "_ap_im_planer"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns, uhr


def main():
    ns, uhr = lade()
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    abfragen = []
    db = {"ids": ["u-ina", "u-fp"], "kaputt": False}

    def sb_select(table, params):
        abfragen.append(table)
        if db["kaputt"]:
            raise ConnectionError("PostgREST weg")
        return [{"user_ids": list(db["ids"])}]
    ns["sb_select"] = sb_select
    im = ns["_ap_im_planer"]

    check(im("u-ina") is True and im("u-fp") is True and im("u-ez") is False and len(abfragen) == 1,
          f"drei Prüfungen in derselben Sekunde → eine Abfrage ({len(abfragen)})")
    uhr.t += 59
    db["ids"] = ["u-ina"]
    check(im("u-fp") is True and len(abfragen) == 1, "nach 59 s noch aus dem Cache (alte Liste)")
    uhr.t += 2
    check(im("u-fp") is False and len(abfragen) == 2, "nach 61 s neu gelesen (u-fp ist raus)")
    db["ids"] = ["u-ina", "u-ez"]
    ns["_ap_planer_cache_leeren"]()
    check(im("u-ez") is True and len(abfragen) == 3, "POST /ids leert den Cache → neue Planer-ID gilt sofort")
    ns["_ap_planer_cache_leeren"]()
    db["kaputt"] = True
    check(im("u-ina") is False and len(abfragen) == 4, "nicht lesbar → gesperrt (False)")
    check(im("u-ina") is False and len(abfragen) == 5, "Fehler wird nicht gemerkt — nächste Anfrage liest wieder")
    db["kaputt"] = False
    check(im("u-ina") is True and len(abfragen) == 6, "DB wieder da → sofort wieder richtig")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
