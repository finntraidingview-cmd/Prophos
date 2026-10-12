-- Namensregel-Nachzügler (Finn 12.10.2026 ~23:34): zwei FundedNext-Futures-Konten, kurz vor .1472 per Bulk-Add angelegt —
-- die alte Name-Vorlage „{size} {firm} {ex}" ergab „150k FundedNext Futures FNFT…" statt „150k FNFT… → Challenge".
-- Seit .1472 baut das Bulk-Add den Namen selbst nach der Regel; das hier ist nur die Nachbesserung der beiden Bestandszeilen.
update accounts set name = '150k FNFTCHFINNSAMUELHERM88778 → Challenge', updated_at = now() where id = '5b776de9-40cc-41a0-96e2-a6f0757670af';
update accounts set name = '150k FNFTCHFINNSAMUELHERM50682 → Challenge', updated_at = now() where id = '7cd83686-1fb2-481f-8eea-4759346ccffb';
