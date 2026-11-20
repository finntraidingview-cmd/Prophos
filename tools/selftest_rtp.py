"""Selbsttest: Responsible Trader Programm (RTP) für Topstep (TS1, Finn 20.11.2026) — rein rechnend, ohne DB und ohne app.py (Modul rtp_topstep.py).
Beispiele A/B/C aus .claude/master/berichte/2026-11-20_TS1_topstep_rtp_konstrukt.md. Aufruf: python3 tools/selftest_rtp.py → „OK …“ bzw. Exit 1.
Basis-Seed wird ausgegeben (nachstellen: RTP_SEED=<zahl> python3 tools/selftest_rtp.py)."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rtp_topstep as rtp  # noqa: E402

CFG = rtp.rtp_cfg(None)
BASIS = int(os.environ.get("RTP_SEED") or random.randrange(10 ** 6))
SEEDS = 300
fehler = []


def pruef(bed, text):
    if not bed:
        fehler.append(text)


def lauf(z, ergebnis=None, netto=0.0, tage=None, max_tage=20):
    """Tag für Tag: Plan → Ergebnis (Standard: TP getroffen; ergebnis(i, plan) darf etwas anderes liefern). → (Pläne, netto, tage)."""
    tage = dict(tage or {})
    pl = []
    for i in range(max_tage):
        p = rtp.rtp_tag_tp(CFG, z, netto, tage)
        if p["aktion"] == "ziel":
            break
        e = ergebnis(i, p) if ergebnis else None
        e = p["tp"] if e is None else e
        pl.append(dict(p, pl=e))
        netto = round(netto + e, 2)
        tage[f"t{len(tage) + 1:02d}"] = e
    return pl, netto, tage


# A · Z 29.000: 11.600 / 11.600 / 5.800 → 29.000, bester Tag 40,0 %
pl, netto, tage = lauf(29000)
pruef([p["tp"] for p in pl] == [11600, 11600, 5800] and abs(netto - 29000) < 0.005, f"A: {[p['tp'] for p in pl]} → {netto}")
pruef([p["art"] for p in pl] == ["tag1", "pump", "rest"], f"A Arten: {[p['art'] for p in pl]}")
pruef(abs(max(tage.values()) / netto - 0.40) < 1e-9, f"A bester Tag {max(tage.values()) / netto}")

# B · Z 29.000, Tag 1 −2.700 (SL): Rest 31.700 → 11.600 / 11.600 / 8.500 → 29.000
pl, netto, tage = lauf(29000, ergebnis=lambda i, p: -2700.0 if i == 0 else None)
pruef([p["tp"] for p in pl[1:]] == [11600, 11600, 8500] and abs(netto - 29000) < 0.005 and abs(pl[1]["rest"] - 31700) < 0.005,
      f"B: {[p['tp'] for p in pl]} → {netto}")
pruef(abs(max(tage.values()) / netto - 0.40) < 1e-9, f"B bester Tag {max(tage.values()) / netto}")

# C · Z 28.000: 11.200 / 11.200 / 5.600
pl, netto, tage = lauf(28000)
pruef([p["tp"] for p in pl] == [11200, 11200, 5600] and abs(netto - 28000) < 0.005, f"C: {[p['tp'] for p in pl]} → {netto}")

# Ziel je Konto: fest (gleiche ID → gleiches Z), in 28.000–30.000, ganze 100 $, gestreut
zs = [rtp.rtp_ziel(CFG, f"konto-{i}") for i in range(400)]
pruef(all(28000 <= z <= 30000 and z % 100 == 0 for z in zs), "Ziel außerhalb 28–30k oder nicht auf 100 $")
pruef(len(set(zs)) > 10 and rtp.rtp_ziel(CFG, "konto-7") == rtp.rtp_ziel(CFG, "konto-7"), "Ziel nicht gestreut bzw. nicht fest je Konto")

for s in range(SEEDS):
    rnd = random.Random(s * 7919 + BASIS)
    z = rtp.rtp_ziel(CFG, f"k{s}")
    # zufällige Verluste (SL 2.500–3.000) und Schlupf → Ziel innerhalb der Toleranz, nie ein Trade über dem Deckel, nie TP < 100
    def erg(i, p):
        if rnd.random() < 0.25:
            return -round(rnd.uniform(2500, 3000), 2)
        return round(p["tp"] - rnd.uniform(0, 80), 2)
    pl, netto, tage = lauf(z, ergebnis=erg, max_tage=60)
    c = 0.4 * z
    pruef(z - 300 - 1e-6 <= netto <= z + 1e-6, f"seed {s}: Ende {netto} statt {z} (Toleranz 300)")
    pruef(all(p["tp"] <= c + 1e-6 and p["tp"] > 300 - 1e-6 for p in pl), f"seed {s}: TP {[p['tp'] for p in pl]} (Deckel {c}, kein Mini-Trade ≤ 300)")
    pruef(max(tage.values()) <= c + 1e-6, f"seed {s}: bester Tag {max(tage.values())} > Deckel {c}")
    pruef(pl[0]["art"] == "tag1" and abs(pl[0]["tp"] - c) < 0.005, f"seed {s}: Tag 1 {pl[0]}")

    # SL: 150K 2.500–2.900 (DLL 3.000 − 100 Puffer), 100K anteilig ≤ 1.900, 50K ≤ 900; heutiger Verlust mindert; nah an der Liq gedeckelt
    s150, _ = rtp.rtp_sl(CFG, 3000, 20000, 0, rnd)
    pruef(s150 is not None and 2500 <= s150 <= 2900, f"SL 150K {s150}")
    s100, _ = rtp.rtp_sl(CFG, 2000, 20000, 0, rnd)
    pruef(s100 is not None and 1666 <= s100 <= 1900, f"SL 100K {s100}")
    s50, _ = rtp.rtp_sl(CFG, 1000, 20000, 0, rnd)
    pruef(s50 is not None and 833 <= s50 <= 900, f"SL 50K {s50}")
    sv, _ = rtp.rtp_sl(CFG, 3000, 20000, 1500, rnd)
    pruef(sv is not None and sv <= 1400, f"SL nach −1.500 heute: {sv}")
    sl_liq, _ = rtp.rtp_sl(CFG, 3000, 1200, 0, rnd)
    pruef(sl_liq is not None and sl_liq <= 1150, f"SL an der Liq: {sl_liq}")
    kt = rtp.rtp_kontrakte(CFG, rnd)
    pruef(kt in (2, 3), f"Kontrakte {kt}")

pruef(rtp.rtp_sl(CFG, 3000, 20000, 2950, random.Random(1))[0] is None, "DLL heute erreicht → kein Trade")
pruef(rtp.rtp_sl(CFG, 3000, 120, 0, random.Random(1))[0] is None, "zu nah an der Liq → kein Trade")
pruef(rtp.rtp_sl(CFG, None, 20000, 0, random.Random(1))[0] is None, "ohne DLL → kein Trade (fail-closed)")
pruef(rtp.rtp_tag_tp(CFG, 29000, 28950.0, {"a": 11600, "b": 11600, "c": 5750})["aktion"] == "ziel", "Rest 50 $ → Ziel erreicht")
pruef(rtp.rtp_tag_tp(CFG, 29000, 28720.0, {"a": 11600, "b": 11600, "c": 5520})["aktion"] == "ziel", "Rest 280 $ (Schlupf 3 NQ) → Ziel erreicht")
pruef(rtp.rtp_tag_tp(CFG, 29000, 29400.0, {"a": 11600, "b": 11600, "c": 6200})["aktion"] == "ziel", "über Ziel → Ziel erreicht")
p = rtp.rtp_tag_tp(CFG, 29000, 28600.0, {"a": 11600, "b": 11600, "c": 5400})
pruef(p["art"] == "rest" and p["tp"] == 400, f"Rest 400 → TP 400: {p}")
p = rtp.rtp_tag_tp(CFG, 29000, 11600.0, {"a": 11600})
pruef(p["bester_pct"] == 100.0 and p["tage_n"] == 1, f"bester_pct in % vom Netto: {p}")
pruef(rtp.rtp_cfg({"ziel": [30000, 32000], "unbekannt": 1})["ziel"] == [30000, 32000] and "unbekannt" not in rtp.rtp_cfg({"unbekannt": 1}),
      "Einstellung überschreibt nur bekannte Schlüssel")

if fehler:
    print("FEHLER:\n  " + "\n  ".join(fehler[:20]) + (f"\n  … {len(fehler)} insgesamt" if len(fehler) > 20 else ""))
    print(f"Basis-Seed {BASIS} (nachstellen: RTP_SEED={BASIS} python3 tools/selftest_rtp.py)")
    raise SystemExit(1)
print(f"OK selftest_rtp (Seed {BASIS}): A/B/C, Ziel je Konto, {SEEDS} Seeds mit Verlusten + Schlupf, SL je Größe/DLL/Liq, Toleranz")
