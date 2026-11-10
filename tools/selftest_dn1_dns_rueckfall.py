#!/usr/bin/env python3
"""Selbsttest DN1 (10.11.2026, Master; Fehler-Muster „getaddrinfo failed“, PC von Marco pc-t8wg97): DNS-Rückfall über DNS-over-HTTPS in panel.py,
order_bot.py und copier.py. Scheitert die System-Namensauflösung für einen unserer Hosts, kommen die IPv4 per DoH (1.1.1.1/8.8.8.8 per IP); sonst bleibt
alles bitgleich. Ohne Netz: getaddrinfo und DoH nachgebaut (simulierter getaddrinfo-Fehler).
Aufruf: python3 tools/selftest_dn1_dns_rueckfall.py"""
import os
import socket
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
MT5 = os.path.join(os.path.dirname(HIER), "mt5-copier")
sys.path.insert(0, MT5)
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


ECHT = socket.getaddrinfo
print("1) Ein Block, drei Dateien (jede kommt über einen eigenen Update-Weg auf den PC)")
bloecke = {}
for f in ("panel.py", "order_bot.py", "copier.py"):
    s = open(os.path.join(MT5, f), encoding="utf-8").read()
    i, j = s.find("# ── DN1 DNS-RÜCKFALL"), s.find("# ── Ende DN1 DNS-RÜCKFALL ──")
    bloecke[f] = s[i:j] if 0 <= i < j else None
    check(bloecke[f] is not None and s.count("dns_rueckfall_einbauen()\n") == 1 and "verify=False" not in bloecke[f]
          and "CERT_NONE" not in bloecke[f] and "check_hostname" not in bloecke[f] and "print(" not in bloecke[f],
          f"{f}: Block da, einmal eingebaut, kein Abschalten der Zertifikatsprüfung, kein print (stdout = JSON des Bots)")
check(len({b for b in bloecke.values()}) == 1, "panel.py, order_bot.py, copier.py tragen denselben Block")
for f in ("panel.py", "order_bot.py", "copier.py"):
    s = open(os.path.join(MT5, f), encoding="utf-8").read()
    i = s.find("# ── DN1 DNS-RÜCKFALL")
    check(all(s.find(f"\nimport {m}\n") < i for m in ("json", "sys", "time")) and min(s.find(f"\nimport {m}\n") for m in ("json", "sys", "time")) > 0,
          f"{f}: json/sys/time stehen vor dem Block")

import panel as P  # noqa: E402  (baut beim Import ein)
check(getattr(socket.getaddrinfo, "_prophos_dns_rueckfall", False) and P.dns_rueckfall_einbauen() is False,
      "Import baut genau einmal ein (Merker am Wrapper, zweiter Aufruf tut nichts)")
socket.getaddrinfo = ECHT

print("2) DoH-Antwort lesen")
I = P.dns_doh_ips
ok_a = {"Status": 0, "Answer": [{"name": "x.", "type": 5, "TTL": 50, "data": "y."}, {"type": 1, "TTL": 120, "data": "66.33.22.1"},
                                 {"type": 1, "TTL": 90, "data": "66.33.22.2"}, {"type": 1, "TTL": 90, "data": "66.33.22.2"}, {"type": 28, "data": "::1"}]}
check(I(ok_a) == (["66.33.22.1", "66.33.22.2"], 90), f"nur A-Sätze, ohne Doppel, kleinstes TTL ({I(ok_a)})")
check(I({"Status": 0, "Answer": [{"type": 1, "TTL": 5, "data": "1.2.3.4"}]})[1] == 30 and I({"Status": 0, "Answer": [{"type": 1, "TTL": 9999, "data": "1.2.3.4"}]})[1] == 300,
      "TTL auf 30–300 s begrenzt")
check(I({"Status": 3}) == ([], 0) and I({"Status": 0, "Answer": [{"type": 1, "data": "kaputt"}]}) == ([], 0) and I(None) == ([], 0) and I("x") == ([], 0),
      "NXDOMAIN, kaputte IP, Unsinn → nichts")

print("3) getaddrinfo-Einträge")
E = P.dns_rueckfall_eintraege
check(E(["1.2.3.4"], 443, 0, socket.SOCK_STREAM) == [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("1.2.3.4", 443))]
      and E(["1.2.3.4"], "https")[0][4] == ("1.2.3.4", 443) and E(["1.2.3.4"], b"8080")[0][4] == ("1.2.3.4", 8080) and E(["1.2.3.4"], None)[0][4] == ("1.2.3.4", 0),
      "Port als Zahl, Name, Bytes, None; Typ Stream + TCP")
check(E(["1.2.3.4"], 443, socket.AF_INET6) == [], "nur IPv6 verlangt → kein IPv4-Ersatz")

print("4) Rückfall mit simuliertem getaddrinfo-Fehler")
HOST = P.DNS_RUECKFALL_HOSTS[0]
aufrufe = {"sys": 0, "doh": 0}
fehl_dns = {HOST, HOST.upper() + ".", "fremd.example"}


def fake_sys(host, port, family=0, type=0, proto=0, flags=0):
    aufrufe["sys"] += 1
    if host in fehl_dns:
        raise socket.gaierror(11001, "getaddrinfo failed")
    if host == "kaputt.example":
        raise OSError("anderer Fehler")
    return [("SYS", host, port)]


doh = {"antwort": (["66.33.22.1"], 60)}


def fake_doh(host, timeout=4.0):
    aufrufe["doh"] += 1
    return doh["antwort"]


alt_doh, alt_cache = P._dns_doh_holen, dict(P._DNS_RUECK)
socket.getaddrinfo = fake_sys
P._dns_doh_holen = fake_doh
P._DNS_RUECK.update(cache={}, fehl={}, log={})
try:
    check(P.dns_rueckfall_einbauen() is True, "Wrapper um die System-Auflösung gelegt")
    G = socket.getaddrinfo
    r = G("anders.example", 443, 0, socket.SOCK_STREAM)
    check(r == [("SYS", "anders.example", 443)] and aufrufe["doh"] == 0, "Normalweg: Ergebnis der System-Auflösung unverändert, kein DoH")
    try:
        G("fremd.example", 443)
        check(False, "fremder Host bei DNS-Fehler muss scheitern")
    except socket.gaierror as e:
        check(e.args[0] == 11001 and aufrufe["doh"] == 0, "fremder Host: derselbe getaddrinfo-Fehler, kein DoH (nur unsere Hosts)")
    try:
        G("kaputt.example", 443)
        check(False, "anderer Fehler muss durchgehen")
    except OSError as e:
        check(not isinstance(e, socket.gaierror) and str(e) == "anderer Fehler", "andere Fehler als gaierror unverändert")
    r = G(HOST, 443, 0, socket.SOCK_STREAM)
    check(r == [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("66.33.22.1", 443))] and aufrufe["doh"] == 1,
          f"unser Host, System-DNS stumm → IPv4 per DoH ({r})")
    r2 = G(HOST.upper() + ".", "443")
    check(r2[0][4] == ("66.33.22.1", 443) and aufrufe["doh"] == 1, "Großschreibung/Punkt am Ende gleich, zweiter Aufruf aus dem Cache")
    P._DNS_RUECK["cache"][HOST] = (("66.33.22.1",), __import__("time").time() - 10)   # seit 10 s abgelaufen
    doh["antwort"] = ([], 0)
    r3 = G(HOST, 443)
    check(r3[0][4] == ("66.33.22.1", 443) and aufrufe["doh"] == 2, "DoH gescheitert → letzte gute Antwort als Notnagel (< 1 h)")
    r4 = G(HOST, 443)
    check(aufrufe["doh"] == 2 and r4[0][4] == ("66.33.22.1", 443), "nach gescheitertem DoH 60 s keine neue Abfrage (kein Stau je Aufruf)")
    P._DNS_RUECK.update(fehl={})
    P._DNS_RUECK["cache"][HOST] = (("66.33.22.1",), __import__("time").time() - 3700)   # seit über 1 h abgelaufen
    try:
        G(HOST, 443)
        check(False, "Notnagel älter als 1 h darf nicht greifen")
    except socket.gaierror:
        check(aufrufe["doh"] == 3, "Notnagel älter als 1 h: nicht mehr benutzt, ursprünglicher Fehler")
    P._DNS_RUECK.update(cache={}, fehl={})
    doh["antwort"] = (["66.33.22.5"], 60)
    r5 = G(host=HOST, port=443, family=0, type=socket.SOCK_STREAM, proto=0, flags=0)
    check(r5[0][4] == ("66.33.22.5", 443), "Aufruf mit Keyword-Argumenten wie socket.getaddrinfo")
    import inspect as _ins
    check(list(_ins.signature(G).parameters) == ["host", "port", "family", "type", "proto", "flags"], "Signatur gleich socket.getaddrinfo")
    try:
        G(HOST, 443, 0, 0, 0, socket.AI_NUMERICHOST)
        check(False, "AI_NUMERICHOST darf keinen Rückfall bekommen")
    except socket.gaierror:
        check(True, "AI_NUMERICHOST (nur Zahlen-Adressen): kein Rückfall, ursprünglicher Fehler")
    n = aufrufe["doh"]
    fehl_dns.add("1.1.1.1")
    try:
        G("1.1.1.1", 443)
    except socket.gaierror:
        pass
    fehl_dns.discard("1.1.1.1")
    check(aufrufe["doh"] == n, "keine Rekursion: scheitert die Auflösung des DoH-Servers selbst, gibt es keinen Rückfall dafür")
    P._DNS_RUECK.update(cache={}, fehl={})
    P._DNS_RUECK["laeuft"][HOST] = object()                    # ein anderer Thread fragt gerade
    try:
        G(HOST, 443)
        check(False, "zweiter Thread ohne Cache muss sofort scheitern")
    except socket.gaierror:
        check(aufrufe["doh"] == n, "läuft schon eine DoH-Abfrage: kein zweiter Thread wartet, sofort der alte Fehler")
    P._DNS_RUECK["laeuft"].clear()
    P._DNS_RUECK.update(cache={}, fehl={})
    doh["antwort"] = ([], 0)
    try:
        G(HOST, 443)
        check(False, "ohne DoH-Antwort und ohne Cache muss es scheitern")
    except socket.gaierror as e:
        check(e.args[0] == 11001, "ohne DoH und ohne Cache: der ursprüngliche getaddrinfo-Fehler (fail wie bisher)")
    P._DNS_RUECK.update(cache={}, fehl={})
    doh["antwort"] = (["66.33.22.9"], 60)
    try:
        G(HOST, 443, socket.AF_INET6)
        check(False, "nur IPv6 verlangt muss scheitern")
    except socket.gaierror:
        check(True, "nur IPv6 verlangt: ursprünglicher Fehler")
    n = aufrufe["sys"]
    G("anders.example", 80)
    check(aufrufe["sys"] == n + 1, "System-Auflösung immer zuerst (je Aufruf genau einmal)")
finally:
    socket.getaddrinfo = ECHT
    P._dns_doh_holen = alt_doh
    P._DNS_RUECK.clear()
    P._DNS_RUECK.update(alt_cache)

print("5) DoH-Abfrage: per IP, Zertifikat an, nur unsere Hosts")
import inspect  # noqa: E402
q = inspect.getsource(P._dns_doh_holen)
check("min(timeout, rest)" in q and P.DNS_RUECKFALL_FRIST_S <= 4 and "timeout=2.0" in q, "Zeitdeckel: je Server 2 s, zusammen ≤ DNS_RUECKFALL_FRIST_S")
check(all(v.startswith("https://1.1.1.1/") or v.startswith("https://8.8.8.8/") for v in P.DNS_RUECKFALL_DOH) and "context=" not in q and "ssl" not in q,
      "DoH-Server per IP über HTTPS mit Standard-Kontext (Zertifikat wird geprüft)")
check(set(P.DNS_RUECKFALL_HOSTS) == {"web-production-bec81.up.railway.app", "gxhkannmzpyuepxlepta.supabase.co"},
      "Rückfall nur für Railway-Backend und Supabase")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
