#!/usr/bin/env python3
"""Selbsttest LOGIN-ORT VOR DEM SIGNAL (app.py mt5_login_ort / mt5_login_ort_text / _mt5_ort_fehler, 08.10.2026, Slave-Terminal 4 —
Finn: „Ich lade gerade ein Terminal bei Chris neu, es lädt seit 5 Minuten nichts"; mt5_balance für einen Login ohne lebende Instanz
verfiel nach 180 s ohne Hinweis). Ohne Netz, Platzhalter-Logins/PCs. Aufruf: python3 tools/selftest_mt5_login_ort.py
Geprüft: Login nur in altem Eintrag → weg + Zuletzt; Login live (master_login) → da; nur master_expected → da; nie gesehen → weg ohne
Zuletzt; kein lebender PC → unklar; lebende Instanz ohne bekannten Login (alter Build) → unklar; Zeilen None (DB-Fehler) → unklar;
Text mit Dubai-Zeit; _mt5_ort_fehler schluckt DB-Fehler (None) und fragt nur die ID ab; beide Routen fragen vor dem Insert."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    src = open(APP, encoding="utf-8").read()
    teile = [re.search(r"^MT5_ORT_FRISCH_S = .*$", src, re.M).group(0)]
    for fn in ("mt5_login_ort", "mt5_login_ort_text", "_mt5_ort_fehler", "_ap_tz"):
        i = src.index(f"\ndef {fn}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    ns = {"datetime": datetime, "timezone": timezone}
    exec("\n\n\n".join(teile), ns)
    return ns, src


def main():
    a, src = lade()
    ort, text = a["mt5_login_ort"], a["mt5_login_ort_text"]
    jetzt = datetime(2026, 10, 8, 4, 40, tzinfo=timezone.utc)
    iso = lambda d: d.isoformat()
    live = {"pc_name": "pc-xxxxxx", "instance": "100kfirma10000002", "master_login": "10000002", "master_expected": "10000002",
            "updated_at": iso(jetzt - timedelta(seconds=20))}
    alt = {"pc_name": "pc-xxxxxx", "instance": "100kfirma1000000", "master_login": "10000001", "master_expected": None,
           "updated_at": "2026-10-05T16:38:12+00:00"}
    r = ort("10000001", [live, alt], jetzt)
    check(r[0] == "weg" and r[1] and r[1]["instanz"] == "100kfirma1000000", f"1 Login nur im alten Eintrag → weg + Zuletzt ({r})")
    t = text("10000001", r[1])
    check("05.10., 20:38" in t and "100kfirma1000000" in t and "Echo" in t, f"   Text mit Dubai-Zeit ({t})")
    check(ort("10000002", [live, alt], jetzt) == ("da", None), "2 Login live (master_login) → da")
    nie = dict(live, master_login="", master_expected="10000003")
    check(ort("10000003", [nie], jetzt) == ("da", None), "3 nur master_expected (Terminal nie gelesen) → da")
    r4 = ort("10000009", [live, alt], jetzt)
    check(r4 == ("weg", None) and "Direkt in Echo einrichten" in text("10000009", None), f"4 nie gesehen → weg ohne Zuletzt ({r4})")
    tot = dict(live, updated_at=iso(jetzt - timedelta(minutes=5)))
    check(ort("10000001", [tot, alt], jetzt) == (None, None), "5 kein lebender PC der ID → unklar (Signal wie bisher)")
    altbuild = dict(live, instance="neu", master_login="", master_expected=None)
    check(ort("10000001", [live, altbuild], jetzt) == (None, None), "6 lebende Instanz ohne bekannten Login (alter Build) → unklar")
    check(ort("10000001", None, jetzt) == (None, None), "7 Zeilen None (DB-Fehler) → unklar")
    check(ort("", [live], jetzt) == (None, None), "8 ohne Login → unklar")
    # _mt5_ort_fehler: DB-Fehler → None; Abfrage nur die ID
    gefragt = {}

    def sb_kaputt(tab, q):
        raise RuntimeError("db")

    def sb_ok(tab, q):
        gefragt.update(q, tab=tab)
        return [dict(live, updated_at=datetime.now(timezone.utc).isoformat()), alt]   # _mt5_ort_fehler rechnet mit der echten Uhr
    a["sb_select"] = sb_kaputt
    check(a["_mt5_ort_fehler"]("u-test", "10000001") is None, "9 _mt5_ort_fehler: DB-Fehler → None (Signal wie bisher)")
    a["sb_select"] = sb_ok
    m = a["_mt5_ort_fehler"]("u-test", "10000001")
    check(m and "10000001" in m and gefragt.get("tab") == "mt5_live" and gefragt.get("status->>user_id") == "eq.u-test",
          f"10 _mt5_ort_fehler: nur mt5_live der ID, Klartext ({gefragt.get('status->>user_id')})")
    # Quelltext: beide Routen fragen vor dem Insert
    w = src.index('if daten.get("aktion") == "balance":')
    k = src.index('weg, x = balance_lese_weg(konto.get("firm")')
    check(src.index("_mt5_ort_fehler(", w) < src.index('sb_insert("order_signale", zeile)', w), "11 /admin/wd-plaene balance prüft vor dem Insert")
    check(src.index("_mt5_ort_fehler(", k) < src.index('sb_insert("order_signale", konto_balance_signal(', k), "12 /admin/konto-balance-lesen prüft vor dem Insert")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
