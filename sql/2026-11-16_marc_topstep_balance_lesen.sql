-- TS3b (16.11.2026): Würfel-Ausnahme Marc × Topstep heute ist eingespielt, trotzdem 0 neue Pläne. Befund Slave 6:
-- Der Nachplan-Takt plant nur Kandidaten (auto_plan_lauf.ergebnis.nur_konten = neue Konten bzw. Konten mit frischer Balance, Railway-Wecker
-- „frische Balance → Nachplanen jetzt“). Marcs 4 aktive Topstep-Challenges haben ihre letzte Lesung vom 12.11. (…45479457 von 16.11. 00:33 UTC),
-- kamen seit dem Nachtlauf nie in nur_konten und wurden darum nie neu gewürfelt/geplant.
-- Weg wie der Bot selbst: je Konto ein Balance-Lese-Signal (dieselbe Form wie die auto_planer-Signale: plan_id 'konto:<id>', aktion konto_balance,
-- von auto_planer, Status wartet). Marcs PC (TopstepX-Login gefixt) liest, tv_balance_at wird frisch, der Wecker nimmt die Konten ins Nachplanen;
-- dort gilt die Würfel-Ausnahme, alle übrigen Regeln bleiben. Nur Lesen am Konto, keine Order. Doppel-Schutz: kein zweites offenes Signal je Konto.
-- …20719220 (b5307bc8) fehlt bewusst: Plan afecd411 steht in „Überprüfen“ → erst abhaken.
insert into public.order_signale (user_id, plan_id, params)
select a.user_id, 'konto:' || a.id,
       jsonb_build_object('von', 'auto_planer', 'firm', a.firm, 'name', a.name, 'aktion', 'konto_balance',
                          'account_id', a.id::text, 'external_id', a.external_id)
from public.accounts a
where a.id in ('57750c95-b096-4716-a85b-db96419253c1',   -- …22631094
               'f0bdaa81-e6b9-4852-839b-e1448b9888f5',   -- …45479457
               'cd1f20fc-4a16-4ca2-aa1e-52b9082504b7',   -- …48456381
               '1b6cc3cd-165c-4cf2-9ecd-ad3ea861d993')   -- …80376187
  and a.user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'
  and not exists (select 1 from public.order_signale o
                  where o.plan_id = 'konto:' || a.id and o.status = 'wartet');
