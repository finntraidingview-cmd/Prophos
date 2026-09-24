-- 2026-09-25: Docht-Schutz für tv_kurs_1m — das Hoch einer Minute sinkt nie, das Tief steigt nie.
-- Finns Kernanforderung: „war NQ auch nur eine Millisekunde bei TP + 8 Ticks, muss Fusion schließen" — der Wächter
-- prüft dafür High/Low der Minutenkerzen seit dem Hedge-Open. BEFUND (Prüfauftrag der Koordinations-Session):
-- die Brücke upsertet auf (wurzel, minute) OHNE pc im Schlüssel und übernimmt h/l blind. h konnte SINKEN, sobald eine
-- schwächere Quelle dieselbe Minute schrieb: (a) Reader-Neustart mitten in der Minute → Kerzen aus Quote-Ticks
-- ('ws-tick', nur die 250-ms-Stichproben von lp) überschreiben eine exakte Chart-Serien-Kerze ('ws') — live belegt:
-- NQ auf pc-usq1i6 seit dem Neustart auf Reader 0.9.0 nur noch 'ws-tick'; (b) zweiter Tab mit verzögertem
-- TradingView-Konto liefert die laufende Minute als Teil-Bar; (c) zweiter PC schreibt dieselben Minuten.
-- REGEL (BEFORE UPDATE, greift auch beim Upsert der Brücke):
--   h = greatest(alt, neu), l = least(alt, neu) — IMMER. Sicher, weil keine Quelle ein High über dem echten liefern
--       kann: Tick-lp sind echte Trades der Minute, Teil-Bars liegen innerhalb der vollen Bar. Einzige Grenze: der
--       Kontraktwechsel am Rollover-Tag, wenn verschiedene Kontrakte in dieselbe Wurzel schreiben (dann einmalig).
--   o = neu nur, wenn die neue Kerze eine Chart-Serie ist ('ws' = exakte Eröffnung), sonst bleibt die alte (erste
--       Öffnung der Minute).
--   c = neu (letzter Kurs).
--   quelle = 'ws', sobald irgendeine Fassung der Minute aus der Chart-Serie kam.
-- ENTSCHEIDUNG gegenüber „ws-tick über ws verwerfen": die Tick-Fassung wird NICHT verworfen, sondern darf h/l nur
-- erweitern. Grund: stirbt die Chart-Serie mitten in der Minute (Tab geschlossen, Neustart), liefern nur noch die
-- Ticks — ein später echter Ausschlag derselben Minute ginge beim Verwerfen verloren. Eine exakte Kerze wird dabei nie
-- verkleinert, genau das war das Ziel.
-- INSERT ist nicht betroffen (erste Fassung einer Minute bleibt wie geliefert).
create or replace function public.tv_kurs_1m_hl_halten()
returns trigger language plpgsql set search_path = '' as $$
begin
  if old.h is not null and new.h is not null then new.h := greatest(old.h, new.h); end if;
  if old.h is not null and new.h is null then new.h := old.h; end if;
  if old.l is not null and new.l is not null then new.l := least(old.l, new.l); end if;
  if old.l is not null and new.l is null then new.l := old.l; end if;
  if coalesce(new.quelle, '') <> 'ws' then new.o := coalesce(old.o, new.o); end if;
  if old.quelle = 'ws' or new.quelle = 'ws' then new.quelle := 'ws'; end if;
  return new;
end $$;

drop trigger if exists tv_kurs_1m_hl_halten on public.tv_kurs_1m;
create trigger tv_kurs_1m_hl_halten before update on public.tv_kurs_1m
  for each row execute function public.tv_kurs_1m_hl_halten();

comment on function public.tv_kurs_1m_hl_halten() is
  'Docht-Schutz (25.09.2026): h nie kleiner, l nie größer; o nur aus Chart-Serie neu; quelle bleibt ws, sobald ws beteiligt';
