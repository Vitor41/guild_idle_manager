# Integração local dos lotes aprovados — 2026-11-09

## Base e composição

- Branch local: `integration/approved-lots-2026-11-09`, criada no checkout existente `App GIM`, inicialmente apontando para `fd37dc8aa79806108b252cf0fda78b8598515be3`.
- Base: `main` (`f34b00fa9139e5046730ab422ebb6fcf9df1dd93`), ancestral do candidato.
- A integração aproveita a cadeia já presente em E5; não precisou de cherry-pick. A/B/C/D e E1/E3/E4/E5 são ancestrais do candidato E5. O conteúdo final relevante de E2 já está presente em E5: os dois arquivos finais do estudo/calibração conferidos contra `ba731a1` são idênticos, embora o tip documental de E2 não seja ancestral. ML-023 já está em `main` (`9c89f95`) e não foi duplicada.
- Heads aprovados usados como evidência: A `c1dc871`; B `b7806123` (correção funcional `64f4954a`, reteste CR `5dacb5c`); C `074e019` (implementação `5f783db`); D `a818bfc` (implementação `029416d`); E5 `fd37dc8`. ML-030 vem da implementação E3 `e256bb6` com compatibilidade de aliases corrigida em `804106c`.
- `AGENTS.md` e os arquivos não rastreados preexistentes foram preservados sem staging. A alteração local existente em `ML-BUGS.md` foi lida e mantida; este commit acrescenta a reconciliação explicitamente solicitada. Nenhum save ou perfil real foi consultado.

## Matriz do backlog

| Item | Estado na integração | Critério/evidência e limitação |
|---|---|---|
| ML-021 | Validada no gate integrado E5 | 15/20 campanhas tiveram rebelião (19 aberturas); chance permanece 2% por Vigília elegível. `vigilia-v7` usa cooldown regional zero; `vigilia-v6` retém cinco Vigílias por compatibilidade. XP líquido CPU +4,42% e sucesso −7,73 p.p. vs baseline, ambos dentro dos gates. Evidência: `reports/lot_e5_cpu_strategy_event_2026-11-09.md`; E5 aprovado pelo CR em `fd37dc8`. |
| ML-022 | Implementada no Lote C | Migração aditiva, produção em lote `5 s × quantidade`, débito único, idempotência, reserva de capacidade e regressões de reinício/prazo. Testes em serviço e manifesto; review final da integração pendente. |
| ML-023 | Validada na `main` | `9c89f95` remove contadores dos cabeçalhos preservando ações contextuais; regressão `test_legacy_header_counters_are_removed_and_contextual_actions_remain`. Nenhuma alteração duplicada. |
| ML-025 | Implementada no Lote D | Catálogo usa fontes ativas, com chances/faixas/requisitos e lacunas; teste de paridade e exclusão de fontes inalcançáveis. Aceite visual manual permanece pendente. |
| ML-026 | Implementada no Lote D | Busca global e filtros; exportação Markdown deriva do Guia e do catálogo ativo e exclui estado privado. Testes de rota e frontend passaram. Aceite visual manual permanece pendente. |
| ML-029 | Implementada/calibrada em E2 e avaliada em E5 | Fórmula somente para snapshots de novos contratos de combate; Rank C nível 18 recomenda poder 144. E5 passou gates de XP/sucesso para a CPU; review final deste hash de integração pendente. |
| ML-030 | Implementada em E3 | Faixas por raridade e múltiplos bônus; auditoria de 1.706 templates, zero inversões em 195 pares comparáveis após correção de aliases. Aceite visual manual e review final da integração pendentes. |
| BUG-001 | Validado | `05797a1`; testes cobrem snapshot de grupo/nível e bloqueio antes de reservar oferta. |
| BUG-002 | Corrigido e validado | Rota reproduzida com campanha descartável; smoke HTTP verifica resultados regionais renderizados. Não se atribui a ele o hash específico de BUG-004. |
| BUG-003 | Correção e regressão isolada implementadas | `33f47a2`; não houve execução de Setup/instalação nesta integração, então o fluxo não está validado em instalação real. |
| BUG-004 | Corrigido e aprovado pelo CR | `5ba0c43`; testes de coleta, versionamento e diagnóstico em campanhas descartáveis. Nenhum save real consultado. |
| BUG-005 | Implementado | `c1ddfed`; smoke cobre dados do jogador/CPU, atualização após persistência e isolamento entre campanhas. |
| BUG-006 | Implementado em A | `0c8f403` + `c1dc871`; reaplicação idempotente em navegação parcial, coberta por `tests.test_desktop_art`. Aceite visual manual não reivindicado. |
| BUG-007 | Implementado em A | `0c8f403` + `c1dc871`; estado pendente/respondido, expiração, portal disponível/usado e reentrada cobertos por testes. Sem acesso a saves reais. |
| BUG-008 | Corrigido e aprovado pelo CR | `64f4954a`, reteste `5dacb5c`; seed/migração aditiva, alvo de coleta persistido e progressão preservada. |

## Validação executada

- `tests.test_lot_b_materials_market`, `tests.test_market_max_quantity`, `tests.test_workshop_service`, `tests.test_material_source_manifest`, `tests.test_guide_routes`, `tests.test_ml030_equipment_bonus_rules`, `tests.test_ml029_mission_power`, `tests.test_regional_cycle_service`, `tests.test_regional_cpu_simulation`, `tests.test_campaign_content_versioning`: **58/58 passaram**. Abrange migrações e dados legados em SQLite temporário.
- `tests.test_stage5_ui_contracts`: **19/19 passaram**; atualizado para refletir cache atual de assets e fila de avisos regionais com prazo.
- `tests.test_desktop_art`: **26/26 passaram**.
- `tests.test_desktop_http_smoke`: **1/1 passou** com campanha descartável. O runner usa `PYTHONPATH` apontando ao pacote `cryptography` já existente em `.venv-desktop`; nenhum pacote foi instalado. A asserção de bônus foi atualizada para conferir snapshots multibônus pela regra E3 por raridade.
- `node --test tests/guide_frontend_utils.test.js`: **4/4 passaram**; `node --check` para `guide.js` e `guide-utils.js`, `compileall` em `app tests scripts`, `git diff --check` e `python -m alembic heads`: passaram; uma cabeça, `0a1b2c3d4e5f`.
- Suíte ampla `python -m unittest discover -s tests -p 'test*.py'`, com limite de 300 s: continuava executando testes/migrações SQLite isolados ao atingir o limite e foi interrompida sem resultado final conclusivo. O teste `desktop_art` isolado passou 26/26; não foi a causa do limite.
- Reteste dos dois P2 do CR no candidato anterior `1195125c`: corrigido o status do cooldown regional (zero em `vigilia-v7`, cinco em `vigilia-v6`) e a verificação de bônus para validar unicidade por `(tipo, atributo)` com limites FORTE corretos. `tests.test_ml030_equipment_bonus_rules`, `tests.test_regional_cycle_service` e `tests.test_stage5_ui_contracts`: **39/39 passaram**; testes diretos do cooldown atual/legado: **2/2 passaram**; smoke HTTP desktop, novamente com campanha descartável e ambiente do venv desktop: **1/1 passou**. Logs: `integration_cr_p2_retest_2026-11-09.txt`, `integration_cr_p2_event_rules_2026-11-09.txt` e `integration_cr_p2_http_retest_2026-11-09.txt`.

Logs reproduzíveis: `integration_core_tests_2026-11-09.txt`, `integration_stage5_ui_retest_2026-11-09.txt`, `integration_focused_followup_2026-11-09.txt`, `integration_http_smoke_desktop_venv_2026-11-09.txt`, `integration_cr_p2_retest_2026-11-09.txt`, `integration_cr_p2_event_rules_2026-11-09.txt`, `integration_cr_p2_http_retest_2026-11-09.txt`, `integration_static_checks_2026-11-09.txt` e `integration_full_suite_2026-11-09.txt`.

## Limites da rodada

Sem build de distribuição, instalação, push, PR, merge remoto ou validação visual final. O commit desta branch é local e segue para revisão independente do CR.
