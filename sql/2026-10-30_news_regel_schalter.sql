-- NEWS-REGEL FUNDED CFD: Schalter (S8 30.10.2026, Frontend 8427eda9 — Funded-CFD-Starts rund um rote USD-News sperren; leerer Kalender =
-- fail-closed). true = Regel an (Standard, wie ohne Spalte). app.py /news/calendar liefert ihn als news_regel (60 s gemerkt, Lesefehler = an),
-- POST /admin/funded-cfd-plan/einstellung {news_regel} setzt ihn (nur Admin, gilt für alle Gruppen). Idempotent.
alter table public.funded_cfd_plan_regeln add column if not exists news_regel boolean not null default true;
