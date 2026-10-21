-- Nachfolger für Marc Topstep 150k …33341330 (bestanden 21.10.2026, siehe sql/2026-10-21_marc_topstep_33341330_bestanden.sql):
-- Express-Konto EXPRESS-V2-DLL-697339-62007238, Aktivierungsgebühr 0 (Finn 21.10.2026 ~16:45 Dubai: „Nachfolger anlegen, hier ist die
-- External ID, Aktivierungsgebühr 0"). Felder wie der Nachfolger-Assistent (successorConfirm): Name nach Konto-Namensregel, Firma, Typ funded,
-- purchase_cost, max_drawdown 4.500 wie die Express-Konten der anderen IDs; Vorgänger im Archiv von passed_pending → passed + successorId.
with neu as (
  insert into accounts (user_id, name, firm, account_type, external_id, purchase_cost, max_drawdown)
  select '6c206a34-c4a7-4352-8097-bb17366bcea1', '150k EXPRESS-V2-DLL-697339-62007238 → Funded', 'Topstep', 'funded',
         'EXPRESS-V2-DLL-697339-62007238', 0, 4500
   where not exists (select 1 from accounts where external_id = 'EXPRESS-V2-DLL-697339-62007238')
  returning id
)
update user_settings s
   set value = s.value || jsonb_build_object('85b52f34-f80e-4bdd-b700-3164fd22589b',
                 jsonb_build_object('archived', true, 'reason', 'passed', 'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                                    'successorId', (select id from neu))),
       updated_at = now()
 where s.user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1' and s.key = 'archive'
   and exists (select 1 from neu);
