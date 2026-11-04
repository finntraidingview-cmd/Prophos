#!/usr/bin/env python3
"""Selbsttest KONTO-LISTE VON PULS (L6, 04.11.2026, Finn: „Puls klickt bei jedem Trade ins Konto-Dropdown — erkennt er ein neues Konto,
soll es in Prophos ‚zu bestätigen‘ auftauchen"). Puls (mt5-copier/order_bot.py _tv_konten_melden, aus _cdp_konto_sichern) schickt die Namen
der Liste, die er selbst geöffnet hat, an den lokalen Reader (tv-reader/reader-server.py POST /tv-konten → Merker _TVK). Ohne Windows,
ohne Railway: echter Reader-Handler auf einem freien Port. Aufruf: python3 tools/selftest_tv_konten_puls.py"""
import importlib.util
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade_reader():
    spec = importlib.util.spec_from_file_location("rs_l6", os.path.join(WURZEL, "tv-reader", "reader-server.py"))
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    return rs


def lade_bot(basis):
    src = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
    teile = [re.search(r"^TVK_NAME_RE = .*$", src, re.M).group(0)]
    for fn in ("def tv_konten_aus_texten(", "def _tv_konten_melden("):
        i = src.index("\n" + fn) + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    ns = {"re": re, "json": json, "_TV_BASIS": basis}
    exec("\n\n\n".join(teile), ns)
    return ns, src


def post(url, daten):
    req = urllib.request.Request(url, data=json.dumps(daten).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=3)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def freier_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    rs = lade_reader()
    port = freier_port()
    srv = rs.ExklusiverServer(("127.0.0.1", port), rs.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{port}"
    try:
        rs._TVK["namen"].clear()
        # Reader: Endpunkt nimmt nur volle Kennungen, quelle immer dropdown, zählt neue
        st, a = post(basis + "/tv-konten", {"konten": [{"name": "APEX6780960000017", "quelle": "umschalter"}, {"name": "FTDFYSLX1502279877…"},
                                                       {"name": "x"}, "kaputt", {"name": "tdfysl150557805753"}]})
        check(st == 200 and a.get("ok") and a.get("neu") == 2 and sorted(rs._TVK["namen"]) == ["APEX6780960000017", "TDFYSL150557805753"]
              and all(e["quelle"] == "dropdown" for e in rs._TVK["namen"].values()), f"Reader /tv-konten: 2 neue volle Namen, quelle dropdown ({a})")
        st, a = post(basis + "/tv-konten", {"konten": [{"name": "APEX6780960000017"}]})
        check(st == 200 and a.get("neu") == 0 and a.get("namen") == 2, "Reader: bekannter Name zählt nicht neu")
        st, _ = post(basis + "/tv-konten", {"liste": []})
        check(st == 400, "Reader: ohne Feld 'konten' → 400")
        senden, paket = rs.tv_konten_entscheid(rs._TVK, time.time())
        check(senden and {k["name"] for k in paket["konten"]} == {"APEX6780960000017", "TDFYSL150557805753"},
              "Reader: gemerkte Namen gehen wie bisher an Railway (tv_konten_entscheid)")

        # Puls: Einträge der eigenen Liste (Form aus den Spuren 27.10.2026) → Reader
        rs._TVK["namen"].clear()
        ns, src = lade_bot(basis)
        spur = []
        eintr = [{"text": "APEX6780960000001 USD"}, {"text": "PAAPEX6780960000005 USD"}, {"text": "FTDFYSLX1507984146… 158,418.22 USD"},
                 {"text": "TDFYSL150000000000156,981.20USD"}, {"text": "Paper Trading"}, {"text": "APEX6780960000001 USD"}, "kaputt", {}]
        t0 = time.time()
        n = ns["_tv_konten_melden"](eintr, spur)
        dauer = time.time() - t0
        for _ in range(40):
            if len(rs._TVK["namen"]) >= 2:
                break
            time.sleep(0.05)
        check(n == 2 and sorted(rs._TVK["namen"]) == ["APEX6780960000001", "PAAPEX6780960000005"],
              f"Puls: nur volle Namen (gekürzt/angeklebte Balance/Paper Trading/Dublette raus) kommen im Reader an ({n}, {sorted(rs._TVK['namen'])})")
        check(dauer < 0.2 and spur and "2 Name(n)" in spur[-1], f"Puls: wartet nicht auf den Reader ({dauer * 1000:.0f} ms), eine Spur-Zeile")
        check(ns["_tv_konten_melden"]([{"text": "Paper Trading"}], spur) == 0 and ns["_tv_konten_melden"](None) == 0, "Puls: ohne Namen nichts senden")
    finally:
        srv.shutdown()
        srv.server_close()

    # Reader nicht erreichbar → still, kein Fehler, kein Warten
    ns2, _ = lade_bot(f"http://127.0.0.1:{freier_port()}")
    t0 = time.time()
    try:
        n2 = ns2["_tv_konten_melden"]([{"text": "APEX6780960000001 USD"}])
        ok2 = n2 == 1
    except Exception as e:
        ok2 = False
        print(e)
    check(ok2 and time.time() - t0 < 0.2, "Puls: Reader aus → keine Ausnahme, kein Warten")

    # Einbau: einmal je Lauf, nur im Zweig der EIGENEN offenen Liste (fremde Listen enden vorher mit Esc)
    i = src.index("\ndef _cdp_konto_sichern(")
    teil = src[i:src.find("\n\n\n", i + 1)]
    j_fremd = teil.index('if ko.get("liste_offen") and not geklickt_umschalter:')
    j_eigen = teil.index('        if ko.get("liste_offen"):\n            if not tvk_gemeldet:')
    check(teil.count("_tv_konten_melden(") == 1 and "tvk_gemeldet = False" in teil and j_fremd < j_eigen,
          "Einbau: _cdp_konto_sichern meldet einmal, erst im Zweig der eigenen Liste")
    if FEHLER:
        print(f"\n{len(FEHLER)} Fehler")
        sys.exit(1)
    print("\nalle grün")


if __name__ == "__main__":
    main()
