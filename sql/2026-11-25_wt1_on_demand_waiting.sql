-- WT1 (Finn 25.11.2026 „bei On Demand“): Waiting for Payout erst ab dem Mindest-Profit — FundedNext On Demand 2 % der Kontogröße (100k = 2.000 $), ohne Toleranz.
-- NICHT eingespielt — Master spielt ein. On Demand = Flag on_demand ODER ein „ · “-Teil des Namens genau „On Demand“ (wie der Code ab WT1, fcp_ist_on_demand).
-- Stand 25.11.2026: ein On-Demand-Konto steht auf Waiting — Ina · FundedNext 100k …0774 · HT, Gewinn 2.152,54 ≥ 2.000 → bleibt. Die Datei ändert heute also
-- nichts; sie nimmt beim Einspielen jedes On-Demand-Waiting heraus, das dann unter 2 % liegt (Aurel …7785 hat der Master schon zurückgesetzt).
-- Nicht-On-Demand-Konten bleiben unberührt (Finn: „normaler Zyklus mit Termin bleibt wie bisher“).

create table if not exists wt1_od_waiting_20261125 as
  select id, name, waiting_payout_since, tv_balance, now() as gesichert_at
    from accounts
   where account_type = 'funded_cfd' and waiting_payout_since is not null and deaktiviert_at is null
     and firm ilike '%fundednext%' and (on_demand is true or name ~* '(^|·)\s*on[\s-]*demand\s*($|·)');
alter table wt1_od_waiting_20261125 enable row level security;
revoke all on wt1_od_waiting_20261125 from anon, authenticated;

-- Guard: nur gesicherte Zeilen mit unverändertem Waiting-Zeitpunkt; Größe aus dem Namen („100k …“), sonst account_size; Gewinn = tv_balance − Größe
update accounts a set waiting_payout_since = null
  from wt1_od_waiting_20261125 s
 where a.id = s.id
   and a.waiting_payout_since = s.waiting_payout_since
   and a.tv_balance is not null
   and a.tv_balance - coalesce(nullif(regexp_replace(substring(a.name from '(\d{2,3})\s*k'), '\D', '', 'g'), '')::numeric * 1000, a.account_size)
       < 0.02 * coalesce(nullif(regexp_replace(substring(a.name from '(\d{2,3})\s*k'), '\D', '', 'g'), '')::numeric * 1000, a.account_size);

-- Kontrolle
select a.id, a.name, a.tv_balance, a.waiting_payout_since from accounts a join wt1_od_waiting_20261125 s on s.id = a.id;

-- Zurück (nur falls nötig):
-- update accounts a set waiting_payout_since = s.waiting_payout_since from wt1_od_waiting_20261125 s where a.id = s.id and a.waiting_payout_since is null;
