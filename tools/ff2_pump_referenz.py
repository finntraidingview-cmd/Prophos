"""FF2 „Pump in 2 Trades“ — REFERENZ-UMSETZUNG der rein rechnenden Funktionen für app.py (Slave 3, 11.11.2026). Wird NICHT importiert: beim Bau
nach app.py übernehmen (dort gibt es _wd_num und FDP_LIQ_PUFFER schon), danach muss tools/selftest_ff2_pump.py gegen app.py grün sein.
Prüfen vor dem Einbau:  SELFTEST_APP=tools/ff2_pump_referenz.py python3 tools/selftest_ff2_pump.py
Schnittstelle + Planer-Logik: side-session-notes 2026-11-11_FF2_schnittstelle_backend.md."""
import hashlib
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo


# FF2 Referenz-Umsetzung (Slave 3, 11.11.2026) — rein rechnende Funktionen für app.py, Selbsttest tools/selftest_ff2_pump.py (SELFTEST_APP=diese Datei).
# Im Einbau entfallen _wd_num und FDP_LIQ_PUFFER (gibt es in app.py schon).
def _wd_num(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


FDP_LIQ_PUFFER = 50
FDP_PUMP_TP_TOL_USD = 100                 # Trade 1 gilt als am TP, wenn E1 ≥ TP − 100 (Schlupf am Fill)
FDP_PUMP_BLOW_TOL_USD = 50                # Ende ≤ Liq + 50 = geblowt
FDP_PUMP_TZ = "Asia/Dubai"
FDP_PUMP_T2_MIN_TP_USD = 500             # bliebe für Trade 2 weniger Rest, ist es ein Trade bis zum Ziel (kein Mini-Trade 2)
FDP_PUMP_TAG_AB_H = 3                     # CME-Tag beginnt im Winter 03:00 Dubai — ein Ende davor gehört zum alten Tag (dann kein Trade 2)


def _fdp_pump_u(*teile):
    """0..1 fest aus den Teilen (sha256) — gleiche Eingabe, gleicher Wert (kein Hin und Her zwischen den 5-min-Takten)."""
    return int(hashlib.sha256("|".join(str(t) for t in teile).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _fdp_pump_spanne(sp, u):
    if not (isinstance(sp, (list, tuple)) and len(sp) == 2):
        return None
    lo, hi = float(sp[0]), float(sp[1])
    return lo + (hi - lo) * u if hi > lo else lo


def _fdp_pump_kt(kt, rnd):
    """Kontrakte aus {Anzahl: Anteil} gewürfelt (aufsteigend kumuliert)."""
    z = sorted((int(k), float(v)) for k, v in (kt or {}).items() if float(v) > 0)
    if not z:
        return None
    x, s = rnd.random() * sum(v for _k, v in z), 0.0
    for k, v in z:
        s += v
        if x < s:
            return k
    return z[-1][0]


def fdp_pump_tag_wurf(jg, konto_id, zyklus, tag):
    """REIN RECHNEND: Weg und Ziel eines Pump-Tags, fest je Konto × Zyklus × CME-Tag → {weg, ziel_gewinn}."""
    pct = _wd_num((jg or {}).get("pump2_pct"))
    pct = 30.0 if pct is None else max(0.0, min(100.0, pct))
    weg = "zwei" if _fdp_pump_u("pump-weg", konto_id, zyklus, tag) * 100 < pct else "ein"
    zg = _fdp_pump_spanne((jg or {}).get("ziel_gewinn"), _fdp_pump_u("pump-ziel", konto_id, zyklus, tag))
    if zg is None:
        zg = _wd_num((jg or {}).get("ziel_gewinn")) or 0.0
    return {"weg": weg, "ziel_gewinn": float(round(zg))}


def fdp_pump_hedge(jg, risiko):
    """REIN RECHNEND: Fusion-Hedge € = hedge_eur ÷ hedge_auf_usd × Risiko; Satz fehlt → None."""
    he, auf = _wd_num((jg or {}).get("hedge_eur")), _wd_num((jg or {}).get("hedge_auf_usd"))
    if not (he and he > 0 and auf and auf > 0) or risiko is None or risiko <= 0:
        return None
    return round(he / auf * float(risiko), 2)


def _fdp_pump_sl(jg, schluessel, balance, liq, daily_rest, rnd, kein_pct):
    """SL-Würfel → (sl | None, risiko). Risiko = SL; ohne SL bzw. SL hinter der Liq = Liq-Abstand; mit Daily-Rest höchstens der."""
    abstand = balance - liq
    grenze = min(abstand, daily_rest) if daily_rest is not None else abstand
    if rnd.random() * 100 < kein_pct:
        return None, grenze
    sl = _fdp_pump_spanne((jg or {}).get(schluessel), rnd.random())
    if sl is None:
        return None, grenze
    if daily_rest is not None:
        sl = min(sl, daily_rest)
    if not (jg or {}).get("sl_hinter_liq"):
        sl = min(sl, abstand - FDP_LIQ_PUFFER)
    sl = float(int(sl))
    return sl, min(sl, grenze)


def fdp_pump_trade1(jg, weg, balance, start, liq, ziel, rnd, tag_verlust=0.0):
    """REIN RECHNEND: Ein-Trade-Weg bzw. Trade 1 eines Pump-Tags → {aktion: planen, tp, sl, risiko, kontrakte, hedge_eur, kette} | {aktion: aus, grund}."""
    if balance is None or liq is None or balance - liq <= FDP_LIQ_PUFFER:
        return {"aktion": "aus", "grund": "zu nah an der Liquidation"}
    rest = round(ziel - balance, 2)
    if rest <= 0.005:
        return {"aktion": "ziel", "grund": "Ziel erreicht → Winning Days"}
    d = _wd_num((jg or {}).get("daily_usd"))
    daily_rest = (d - max(0.0, float(tag_verlust or 0))) if d else None
    if daily_rest is not None and daily_rest <= FDP_LIQ_PUFFER:
        return {"aktion": "aus", "grund": "Daily Loss heute schon erreicht"}
    kein = _wd_num((jg or {}).get("sl_kein_pct"))
    kein = 50.0 if kein is None else kein
    if weg == "zwei":
        tp = _fdp_pump_spanne((jg or {}).get("t1_tp"), rnd.random())
        tp = min(float(round(tp)), rest) if tp else rest
        kt, slk, kette = _fdp_pump_kt((jg or {}).get("t1_kontrakte"), rnd), "t1_sl", {"von": 2, "nr": 1, "rolle": "haupt"}
        if rest - tp < FDP_PUMP_T2_MIN_TP_USD:   # Trade 2 hätte fast nichts mehr zu tun → ein Trade bis zum Ziel, ohne kette
            tp, kette = rest, None
    else:
        tp, kt, slk, kette = rest, _fdp_pump_kt((jg or {}).get("ein_kontrakte"), rnd), "ein_sl", None
    sl, risiko = _fdp_pump_sl(jg, slk, balance, liq, daily_rest, rnd, kein)
    h = fdp_pump_hedge(jg, risiko)
    if h is None:
        return {"aktion": "aus", "grund": "Hedge-Satz fehlt (Fusion-Hedge je Master-Risiko in den Einstellungen)"}
    return {"aktion": "planen", "tp": tp, "sl": sl, "risiko": round(risiko, 2), "kontrakte": kt, "hedge_eur": h, "kette": kette}


def fdp_pump_trade2(jg, t1, balance_start, balance_end, liq_eod, ziel, rnd):
    """REIN RECHNEND: Trade 2 aus dem GENAU gelesenen Ergebnis von Trade 1 → (werte, None) | (None, grund). liq_eod = Liq nach Tagesend-Logik (liq_peak eod=True).
    balance_start = Balance beim Start von Trade 1 = Tagesstart (Trade 1 ist der erste Trade des Pump-Tags) — darum gilt bei Daily Loss: Verlust höchstens E1 + daily_usd."""
    e1 = round(float(balance_end) - float(balance_start), 2)
    if balance_end <= liq_eod + FDP_PUMP_BLOW_TOL_USD:
        return None, f"Trade 1 hat das Konto geblowt ({e1:+.0f} $) — kein Trade 2"
    if balance_end >= ziel - 0.005:
        return None, "Ziel schon mit Trade 1 erreicht — kein Trade 2"
    tp1 = _wd_num((t1 or {}).get("tp"))
    if tp1 is None or e1 < tp1 - FDP_PUMP_TP_TOL_USD:
        return None, f"Trade 1 endete nicht am TP ({e1:+.0f} $) — Tag zu, morgen neu"
    be = _wd_num((jg or {}).get("t2_sl_be_pct"))
    be = 50.0 if be is None else be
    sl = float(e1) if rnd.random() * 100 < be else None
    abstand = balance_end - liq_eod
    d = _wd_num((jg or {}).get("daily_usd"))
    grenze = min(abstand, e1 + d) if d else abstand     # Lucid: Tagesverlust ab Tagesstart → höchstens E1 + Daily Loss
    risiko = min(sl, grenze) if sl is not None else grenze
    h = fdp_pump_hedge(jg, risiko)
    if h is None:
        return None, "Hedge-Satz fehlt — kein Trade 2"
    return {"tp": round(ziel - balance_end, 2), "sl": sl, "risiko": round(risiko, 2), "kontrakte": _fdp_pump_kt((jg or {}).get("t2_kontrakte"), rnd),
            "hedge_eur": h, "e1": e1, "kette": {"von": 2, "nr": 2, "rolle": "haupt", "e_bisher": e1}}, None


def fdp_pump_t2_start(jg, t1_ende_utc, rnd):
    """REIN RECHNEND: Startzeit von Trade 2 (UTC) gleichverteilt in [Ende + t2_abstand_min, t2_bis Dubai am selben Dubai-Tag]; Fenster < t2_min_fenster_min → None."""
    tz = ZoneInfo(FDP_PUMP_TZ)
    ende = (t1_ende_utc if t1_ende_utc.tzinfo else t1_ende_utc.replace(tzinfo=timezone.utc)).astimezone(tz)   # ohne Zone = UTC (nie Ortszeit des Rechners)
    if ende.hour < FDP_PUMP_TAG_AB_H:
        return None   # Trade 1 lief über Mitternacht Dubai — der Pump-Tag ist vorbei
    ab = ende + timedelta(minutes=_fdp_pump_spanne((jg or {}).get("t2_abstand_min") or [2, 5], rnd.random()) or 2)
    hh, mm = (int(x) for x in str((jg or {}).get("t2_bis") or "18:30").split(":"))
    bis = ende.replace(hour=hh, minute=mm, second=0, microsecond=0)
    mindest = _wd_num((jg or {}).get("t2_min_fenster_min"))
    if (bis - ab).total_seconds() / 60.0 < (10.0 if mindest is None else mindest):
        return None
    return (ab + (bis - ab) * rnd.random()).astimezone(timezone.utc)


# Ende FF2-Referenz
