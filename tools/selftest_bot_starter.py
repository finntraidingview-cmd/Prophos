#!/usr/bin/env python3
"""Selbsttest SW1b — Order-Bot vorkompiliert starten (BOT_STARTER_CODE / bot_argv in panel.py und order_bot.py). Echte Prozesse, ohne Windows, ohne Netz:
 a) derselbe Aufruf liefert dasselbe Ergebnis (stdout + Exit-Code) wie `python order_bot.py …` — ohne Argumente, kaputtes JSON, unvollständiger Befehl
 b) Prozess-Umgebung wie beim Skriptstart: sys.argv, sys.path[0], __main__.__file__ (Fehlerfoto-Hülle), Rückgabewert von main()
 c) Update: geänderte order_bot.py wird neu übersetzt — auch bei GLEICHER Größe und GLEICHEM Zeitstempel (checked-hash-.pyc), nie ein altes .pyc
 d) Rückfall: __pycache__ nicht beschreibbar → läuft trotzdem; Import scheitert → alter Weg (runpy, __main__); Fehler in main() läuft genau EINMAL
 e) bot_ohne_cache.flag → alter Aufruf; Starter in panel.py und order_bot.py gleich; alle Bot-Starts laufen über bot_argv
 f) Startzeit alt/neu (gedruckt)
Aufruf: python3 tools/selftest_bot_starter.py"""
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MC = os.path.join(W, "mt5-copier")
PANEL = open(os.path.join(MC, "panel.py"), encoding="utf-8").read()
BOT = open(os.path.join(MC, "order_bot.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(src):
    i = src.index("BOT_STARTER_CODE = (")
    return src[i:src.index("\n\n\n", src.index("def bot_argv("))]


ns = {"os": os, "sys": sys}
exec(block(PANEL), ns)
argv, CODE = ns["bot_argv"], ns["BOT_STARTER_CODE"]


def lauf(cmd):
    t = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout.strip(), p.stderr.strip(), time.perf_counter() - t


def neu(bot, *a):
    return lauf(argv(bot) + list(a))


def alt(bot, *a):
    return lauf([sys.executable, bot] + list(a))


with tempfile.TemporaryDirectory() as d:
    # a) echter Bot (Kopie, damit das Repo kein __pycache__ bekommt)
    bot = os.path.join(d, "order_bot.py")
    shutil.copy(os.path.join(MC, "order_bot.py"), bot)
    cfg = os.path.join(d, "config-x.json")
    open(cfg, "w").write("{}")
    faelle = [(), (cfg, "{kaputt"), (cfg, '{"symbol": "NAS100"}')]
    for f in faelle:
        a_, n_ = alt(bot, *f), neu(bot, *f)
        check(a_[:2] == n_[:2] and a_[0] != 0, f"gleiches Ergebnis {f[1:] or '(ohne Argumente)'}: Exit {n_[0]}, {n_[1][:70]}")
    pyc = importlib.util.cache_from_source(bot)
    check(os.path.exists(pyc) and int.from_bytes(open(pyc, "rb").read(16)[4:8], "little") == 3, "__pycache__/order_bot.*.pyc liegt, checked-hash (Flags 3)")

    # f) Zeit
    ta = sorted(alt(bot)[3] for _ in range(5))[2]
    tn = sorted(neu(bot)[3] for _ in range(5))[2]
    print(f"  Startzeit (Median aus 5, Aufruf ohne Argumente): alt {ta:.3f} s → neu {tn:.3f} s ({(1 - tn / ta) * 100:.0f} % weniger)")
    check(tn < ta * 0.6, "vorkompiliert deutlich schneller (< 60 % der alten Zeit)")

    # b) Umgebung wie beim Skriptstart (eigener Mini-Bot)
    mini = os.path.join(d, "mini_bot.py")
    open(mini, "w").write(
        "import sys, os, json\n"
        "def main():\n"
        "    m = sys.modules.get('__main__')\n"
        "    print(json.dumps({'argv': sys.argv, 'p0': os.path.abspath(sys.path[0]), 'mf': os.path.abspath(getattr(m, '__file__', '') or ''),"
        " 'bot': os.path.abspath(__file__)}))\n"
        "    return 7\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(main())\n")
    import json
    a_, n_ = alt(mini, "modus", '{"x": 1}'), neu(mini, "modus", '{"x": 1}')
    ja, jn = json.loads(a_[1]), json.loads(n_[1])
    check(a_[0] == n_[0] == 7, "Rückgabewert von main() = Exit-Code (7)")
    check(ja["argv"][1:] == jn["argv"][1:] == ["modus", '{"x": 1}'] and os.path.abspath(jn["argv"][0]) == os.path.abspath(mini), "sys.argv wie beim Skriptstart")
    check(os.path.realpath(ja["p0"]) == os.path.realpath(jn["p0"]) == os.path.realpath(d), "sys.path[0] = Bot-Ordner")
    check(os.path.realpath(ja["mf"]) == os.path.realpath(jn["mf"]) == os.path.realpath(jn["bot"]) == os.path.realpath(mini) and jn["mf"] == jn["bot"], "__main__.__file__ = Bot-Datei (fehlerfoto_huelle_einbauen erkennt den Bot-Prozess)")

    # c) Update bei gleicher Größe und gleichem Zeitstempel
    st0 = os.stat(bot)
    txt = open(bot, encoding="utf-8").read()
    alt_text, neu_text = '"msg": "Aufruf: order_bot.py <config.json>', '"msg": "AUFRUF: order_bot.py <config.json>'   # genau die ausgegebene Meldung
    check(len(alt_text) == len(neu_text) and alt_text in txt, "Teständerung hat dieselbe Länge")
    open(bot, "w", encoding="utf-8").write(txt.replace(alt_text, neu_text, 1))
    os.utime(bot, ns=(st0.st_atime_ns, st0.st_mtime_ns))
    check(os.stat(bot).st_size == st0.st_size and os.stat(bot).st_mtime_ns == st0.st_mtime_ns, "neue order_bot.py: gleiche Größe, gleicher Zeitstempel")
    n2 = neu(bot)
    check("AUFRUF: order_bot.py <config.json>" in n2[1] and "Aufruf: order_bot.py <config.json>" not in n2[1], f"geänderte Datei wird neu übersetzt (Hash statt Zeitstempel): {n2[1][:60]}")
    # .pyc vom normalen Import (Zeitstempel-Art, wie die -c-Aufrufe des Panels) → der Starter ersetzt es durch checked-hash
    import py_compile
    py_compile.compile(bot, cfile=pyc, doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    neu(bot)
    check(int.from_bytes(open(pyc, "rb").read(16)[4:8], "little") == 3, "Zeitstempel-.pyc (vom -c-Import) wird beim nächsten Start durch checked-hash ersetzt")

    # d) Rückfälle
    pc = os.path.dirname(pyc)
    shutil.rmtree(pc)
    os.makedirs(pc)
    os.chmod(pc, stat.S_IRUSR | stat.S_IXUSR)
    try:
        n3, a3 = neu(bot), alt(bot)
        check(n3[:2] == a3[:2] and not os.listdir(pc), "__pycache__ nicht beschreibbar → läuft trotzdem, gleiches Ergebnis (wie früher, ohne Cache)")
    finally:
        os.chmod(pc, stat.S_IRWXU)
    # kaputtes .pyc mit heilem Kopf (Flags 3, z. B. Strom weg beim Schreiben) → Rückfall einmal, .pyc gelöscht, nächster Start übersetzt neu (Gegenprüfung H1)
    neu(bot)
    roh = open(pyc, "rb").read()
    open(pyc, "wb").write(roh[:16] + b"\x00kaputt" * 50)
    n6, a6 = neu(bot), alt(bot)
    ok6 = n6[:2] == a6[:2] and not os.path.exists(pyc)
    n7 = neu(bot)
    check(ok6 and n7[:2] == a6[:2] and os.path.exists(pyc) and int.from_bytes(open(pyc, "rb").read(16)[4:8], "little") == 3,
          "kaputtes .pyc → gleiches Ergebnis über den alten Weg, .pyc gelöscht, nächster Start legt ein heiles an")
    kaputt = os.path.join(d, "kaputt_bot.py")
    open(kaputt, "w").write(
        "import sys\n"
        "if __name__ != '__main__':\n"
        "    raise ImportError('nur als Skript')\n"
        "def main():\n"
        "    print('lauf als skript'); return 3\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(main())\n")
    n4 = neu(kaputt)
    check(n4[0] == 3 and n4[1] == "lauf als skript", "Import scheitert → alter Weg (runpy als __main__), main läuft einmal")
    einmal = os.path.join(d, "einmal_bot.py")
    open(einmal, "w").write(
        "import sys\n"
        "def main():\n"
        "    print('main lief')\n"
        "    raise RuntimeError('Fehler in main')\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(main())\n")
    n5 = neu(einmal)
    check(n5[1].count("main lief") == 1 and n5[0] != 0 and "RuntimeError" in n5[2], "Fehler IN main() → kein Rückfall, main läuft genau einmal (keine zweite Order)")

    # e) Schalter + Gleichheit + Verdrahtung
    open(os.path.join(d, "bot_ohne_cache.flag"), "w").write("")
    check(argv(bot) == [sys.executable, bot], "bot_ohne_cache.flag → alter Aufruf [python, order_bot.py]")
    os.remove(os.path.join(d, "bot_ohne_cache.flag"))
    check(argv(bot)[:2] == [sys.executable, "-c"] and argv(bot)[-1] == bot, "ohne Schalter → [python, -c, Starter, bot]")

check(block(PANEL) == block(BOT), "Starter in panel.py und order_bot.py zeichengleich")
check("subprocess.run([sys.executable, bot, " not in PANEL and PANEL.count("subprocess.run([*bot_argv(bot), ") == 16, "panel.py: alle 16 Bot-Starts über bot_argv (F-A 11.11.2026: + /api/vorflug)")
check("subprocess.Popen([sys.executable, os.path.abspath(__file__), " not in BOT and BOT.count("subprocess.Popen([*bot_argv(os.path.abspath(__file__)), ") == 4,
      "order_bot.py: Selbststarts (fehlerfoto, nachreichen, augen, tsxbleiben) über bot_argv")
check("py_compile.PycInvalidationMode.CHECKED_HASH" in CODE and "runpy.run_path(bot, run_name='__main__')" in CODE
      and CODE.index("_ob = None") < CODE.index("runpy.run_path") < CODE.index("sys.exit(_ob.main())"), "Starter: checked-hash, Rückfall nur VOR main()")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
