-- Futures-Puls Neuaufbau, Schritt 2 (21.09.2026) — Tradovate-Username pro Firma
--
-- Finn 21.09.2026: "jede Prop-Firm hat bei TradingView ihren eigenen Username.
-- Dann wuerde ich so machen, dass ich in den Einstellungen bei den Prop-Firms
-- den jeweiligen TradingView-Username hinterlege … der Puls-Bot weiss dann
-- automatisch, welchen TradingView-Account er auswaehlen muss."
--
-- Gemeint ist der Tradovate-LOGIN der Firma (der Name, den Chrome im
-- Tradovate-Anmeldefenster als Autofill-Vorschlag zeigt). Bewusst NUR der
-- Username: das Passwort liegt in Chromes Passwort-Manager und wird von dort
-- eingesetzt — es steht nie in der DB, nie in einer Config, nie im Bot.
--
-- Pro Login und Firma (firm_specs ist schon unique user_id+name, RLS steht).
-- Additiv, nullable, mehrfach ausfuehrbar.

alter table public.firm_specs
  add column if not exists tv_username text;

comment on column public.firm_specs.tv_username is
  'Tradovate-Login-Username dieser Firma fuer den TradingView-Broker-Login (Futures-Puls). Nur der Name — nie ein Passwort.';
