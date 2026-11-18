# Candidate 0.10.0 — matriz de retestes direcionados

**Branch:** `feature/vigilia-backlog-batch`  
**SHA do código testado:** `45467f0e1fccd3a70915ff325b459db1dd5e67d6`  
**Base de comparação do candidato:** `14631be0efd62e7a03a1e67562afc81edf421a64`

## Como interpretar

A primeira execução integrada continua sendo `FAILED (failures=10, errors=11, skipped=4)` em 383 testes. Depois das correções, cada uma das **21 ocorrências** registradas foi repetida em seu grupo direcionado e passou. A suíte integrada completa não foi repetida; portanto, este relatório não a declara aprovada. A triagem original, com nomes, stacks e hashes dos logs de origem, permanece em [candidate_010_initial_failures_2026-11-18.md](candidate_010_initial_failures_2026-11-18.md), SHA-256 `668F353AFE3B256F703FF5237101D1D4D82EB0CCC00A437CBA4A47D4BB67A316`.

Os retestes usaram `C:\Users\vitor\Guild Idle Manager\.venv\Scripts\python.exe`, dependências de `.venv-desktop\Lib\site-packages` e `TEMP`, `TMP` e `LOCALAPPDATA` fictícios sob `C:\Users\vitor\Guild Idle Manager\.candidate-010-validation-retest\final-2026-11-18`, fora de `App GIM`. Nenhum save real, perfil normal, build de distribuição ou instalador foi usado.

## Retestes das 21 ocorrências iniciais

| Grupo inicial | Cobertura repetida | Resultado | Log versionado e SHA-256 |
| --- | --- | --- | --- |
| Cryptography, 10 ocorrências (E05–E11, F01, F07, F08) | 49 testes passaram: os sete módulos antes sem import, a Home ASGI sem campanha e o bloqueio cross-origin. O F07, smoke HTTP via subprocesso, está no log próprio abaixo. | 49/49 + 1/1 | [A1-import-and-subprocess.log](candidate_010_retests_2026-11-18/A1-import-and-subprocess.log) — `E3DAEE002147795D14FE09D877772867C10FDE8CDA136E98ED1CD89D800F6C67` |
| Paths temporários/exportação/relógio/logs, 4 ocorrências (E01–E04) | `test_campaign_export_import_restore_backup_and_delete_lifecycle`; `test_import_initializes_new_anchor_without_crediting_pre_import_time`; `test_gameplay_log_is_in_stable_user_data_outside_install_and_saves`; `test_gameplay_log_survives_campaign_migration_and_regional_production`. | 4/4 | [A2-temp-export-clock-logs.log](candidate_010_retests_2026-11-18/A2-temp-export-clock-logs.log) — `8E3271981FB0AB2AE451EF64960E7EA88AD2DF5BE28947A994B41B478DF960CF` |
| Head Alembic esperado f7 vs atual e9, 5 ocorrências (F02–F06) | Isolamento/abertura de campanhas; upgrade de revisão anterior; preservação de Cristais; upgrade pré-evento com backup; upgrade do head Work One com pausa de coleta. | 5/5 | [A3-alembic-head-five-cases.log](candidate_010_retests_2026-11-18/A3-alembic-head-five-cases.log) — `0FABF3C3437339A80C486FCCB44ABF1A2A029C1C3E9399E9ABE68D30A0AB35DB` |
| Lot B, 1 ocorrência (F09) | Módulo completo `tests.test_lot_b_materials_market`, incluindo congelamento do alvo legado antes de subir de nível. | 11/11 | [A4-lot-b-materials-market.log](candidate_010_retests_2026-11-18/A4-lot-b-materials-market.log) — `4647C7F4F289CBC35DE62F7453B1B2A36E6E9F45F1F578037C820A4027489FAB` |
| Viabilidade pública da CPU, 1 ocorrência (F10) | Módulo completo `tests.test_ml050_cpu_internal_contract`; `test_public_viability_at_planner_start_prevents_later_internal_fallback` passou com a oferta pública viável no início do planejamento. | 4/4 | [A5-ml050-cpu-internal-contract.log](candidate_010_retests_2026-11-18/A5-ml050-cpu-internal-contract.log) — `3DF82B1C613D815B144A42787F93285AD61F65B29ADA3A5DFA581B9B8915FFB8` |

O log A1 inclui duas mensagens `ERROR [gim.requests]` emitidas durante os casos de diagnóstico da Oficina; o processo `unittest` encerrou com código 0 e `OK`. A linha `PASS: packaged launcher entry` é saída de teste de contrato; não representa build de distribuição ou execução de instalador.

## Regressões adicionais e gates

| Verificação | Resultado | Log versionado e SHA-256 |
| --- | --- | --- |
| Smoke HTTP desktop completo (`test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions`), incluindo a asserção do Guia atualizada | 1/1 | [P2-desktop-http-smoke.log](candidate_010_retests_2026-11-18/P2-desktop-http-smoke.log) — `EC39EE5B3437DD07ED89A460A2D79E8032F5F97AFB31C04307B7AC0244E27E0C` |
| Guia + cinco regressões de campanha/head, incluindo a versão exportada 0.10.0 | 12/12 | [Guide-and-five-campaign-regressions.log](candidate_010_retests_2026-11-18/Guide-and-five-campaign-regressions.log) — `F6BFF2CB084604A407B63E90CB0FE708D267F16D88961F8B5D9932FA8DE96AFB` |
| SSR da rota de reset: aviso preserva quantidade, não oferece link para `/updates`, e outros bloqueios mantêm atalhos; testes JS de confirmação/retry/foco | Python 1/1; Node 4/4 | [ML046-reset-route-and-js.log](candidate_010_retests_2026-11-18/ML046-reset-route-and-js.log) — `CA4FF008B631CA9595D139AD3A7C9A6F6FB9F0FDB0927DE7B7D004546509315B` |
| P1 do ledger legado | Aprovado independentemente pelo CR em `505b448d2c78adeddabea989599a7fec9370ac69`: 13 testes; campanha abre sem materiais comuns, estimativa permanece pendente e só o reset fica bloqueado. Após restaurar o catálogo, reembolso exato de 60 unidades e retry sem duplicação. | Parecer CR; sem log local separado |
| Delta de mensagem/link do reset | Aprovado pela DA e pelo CR, sem achados, em `4ec7ae65dfe54d0297629b04d89b7ee69ca98824`. | Parecer DA/CR; teste de rota e log Node acima |
| Checagem do diff | `git diff --check` passou após os deltas. | Sem log separado |

## Limites restantes

- O resultado integrado inicial permanece vermelho no histórico. Só as 21 ocorrências afetadas foram repetidas; não houve nova execução dos 383 testes como uma suíte única.
- Os quatro skips da execução inicial continuam sem identificação nominal. A triagem inicial contém os motivos candidatos, sem os tratar como comprovados.
- Não foram feitos build de distribuição, instalação nem smoke de janela nativa. Esses gates não fazem parte dos retestes acima.
- O código do jogo e os testes deste relatório correspondem ao SHA `45467f0e1fccd3a70915ff325b459db1dd5e67d6`; o commit que versiona este relatório apenas acrescenta evidências e documentação.
