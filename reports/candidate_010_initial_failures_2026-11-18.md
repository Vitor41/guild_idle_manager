# Candidate 010 - Triagem inicial da rodada integrada

## Escopo e integridade

Triagem SOMENTE de leitura e relatorio, em2026-11-18. Nenhum teste, runtime, script de validacao, comando Git/branch, instalacao, UI ou save real foi executado/alterado. Apenas este arquivo novo foi escrito. Nao houve rerun da suite nem das100Vigilias.

Fonte primaria, relativa a `C:\Users\vitor\Guild Idle Manager\App GIM`:

```text
.candidate-010-validation-87774a241f3f4791bdf91fc954e1df2e/python-suite.log
SHA256: 73c4ed6edc4eeec559fd5406a44eebc865b54b3160c9ae4605633bbdd47550ba
Tamanho: 361662 bytes; 2583 linhas
```

Hash conferido antes e depois da leitura; log original nao editado. As referencias `Lxxxx` abaixo sao linhas desse log, nao numeros de linha do codigo-fonte. As stacks conservam os numeros de fonte da execucao. Leituras pontuais dos arquivos citados foram estaticas; o checkout atual e compartilhado com o DEV e nao constitui baseline imutavel.

Fonte secundaria contextual: `.candidate-010-validation-87774a241f3f4791bdf91fc954e1df2e/node-suite.log`, SHA256 `486b8666a9dafc5acb64c39718fc02c1d5722e617c01b653cb168df323ecd495`:33testes,33pass,0fail,0skip. Esse resultado Node nao corrige nem substitui o Python.

## Resultado e contagem

Python: `Ran 383 tests in 1886.559s` (L2580), `FAILED (failures=10, errors=11, skipped=4)` (L2582). A suite integrada **nao passou**. A contagem inclui placeholders `_FailedTest` de modulos que nao importaram; nao significa que todos os casos internos desses modulos tenham sido executados.

| Grupo | Errors | Failures | Total | Estado da causa |
| --- | ---: | ---: | ---: | --- |
| Dependencia `cryptography` indisponivel na importacao | 7 | 3 | 10 | Comprovada nas stacks, inclusive nos subprocessos |
| Temporarios/dados de teste dentro de App GIM | 4 | 0 | 4 | Tres guards explicitos; quarto e arquivo de log ausente, compativel com a mesma configuracao e com o tratamento de erro do logger |
| Head Alembic esperado hardcoded f7, obtido e9 | 0 | 5 | 5 | Assercao de teste desatualizada comprovada |
| Lot B: `first["stored"]` zero em vez de um | 0 | 1 | 1 | Divergencia observada; causa raiz nao provada |
| CPU: lista `decisions` vazia em vez de uma acao | 0 | 1 | 1 | Divergencia observada; causa raiz nao provada |
| **Total** | **11** | **10** | **21** | Sem baseline comparativo |

Nao classificar qualquer ocorrencia como "preexistente": nenhuma execucao-base equivalente foi fornecida/comparada nesta tarefa. Separar falha ambiental de assert funcional nao equivale a provar sua antiguidade ou inocuidade.

A coordenacao informou que100ciclos passaram. O log contem `REGIONAL_SIMULATION_METRICS` emL2583, com progresso1..100, fases de3+17+30+50ciclos e ranking final de25guildas. A linha de metricas confirma a coleta regional produzida; nao torna a suite toda verde e nao identifica, no formato nao verboso, o nome de cada teste aprovado. Nao se atribui esse resultado positivo ao teste CPU que falhou emF10.

## Acoes de triagem

- **A1 - Ambiente/imports:** disponibilizar `cryptography` no interpretador e caminho de importacao efetivamente usados pela rodada e pelos filhos; conferir executavel, heranca do ambiente e dependencias declaradas. O log prova a indisponibilidade ao importar, nao qual instalacao/configuracao a causou. Nao substituir assinaturas reais por mocks nem editar o produto para contornar a dependencia. Nenhuma instalacao foi feita nesta triagem.
- **A2 - Ambiente/paths:** configurar TEMP/TMP ANTES de iniciar o processo Python em diretorio exclusivo **fora de App GIM**, por exemplo `C:\Users\vitor\Guild Idle Manager\.candidate-010-env-<id>\tmp`. Usar LOCALAPPDATA FICTICIO tambem fora de App GIM, sem usar o perfil real. Os testes que criam LOCALAPPDATA sob TemporaryDirectory herdam a localizacao de TEMP; corrigir so LOCALAPPDATA externo pode nao bastar. Manter os logs originais onde estao. **Nao remover/relaxar `_assert_outside_checkout` ou `user_data_directory`** para acomodar um TEMP incorreto.
- **A3 - Teste/head:** alinhar `CURRENT_ALEMBIC_HEAD` do teste ao head aprovado desta candidata (`e9f8a7b6c5d4` no log), ou ao mecanismo de resolucao de head adotado pelo projeto. Preservar verificacoes de backup, dados e versao; nao rebaixar o schema real a f7 para satisfazer o literal antigo. Essa correcao de expectativa nao comprova que todas as regras de migracao estejam corretas.
- **A4 - Lot B, investigar:** conservar a fixture e capturar, em futura verificacao direcionada do DEV, retorno completo de `advance_assignment`, alvo efetivo, estado de catalogo/pausa, intervalo/checkpoint e conteudo da fixture. O assert isolado nao mostra por que `stored` ficou zero. Nao trocar1por0 nem atribuir automaticamente a ML048/reset sem evidencia.
- **A5 - CPU, investigar:** capturar elegibilidade completa da oferta publica, roster/equipamento/roles, horario livre/prazo, `prepared_start` e motivos de rejeicao. A fixture reduz requisito de guilda/duracao de uma oferta, mas isso por si so nao comprova todos os requisitos de viabilidade. Nao atribuir a RNG, fallback interno, migracao ou TEMP apenas pela lista vazia.

As acoes sao handoff para o DEV/coord; nenhuma foi executada aqui. Primeiro corrigir ambiente e expectativa isolada, depois retestes dirigidos conforme autorizacao, sem pedir uma nova rodada longa apenas para esta triagem.

## Cada ERROR - nomes exatos e evidencia

**E01 - ERROR / ValueError - A2**

`test_campaign_service.CampaignServiceTests.test_campaign_export_import_restore_backup_and_delete_lifecycle`

L2275..2287: teste em`tests/test_campaign_service.py:727` -> helper`:743` -> `campaigns.export_campaign` -> `app/services/campaign_service.py:471` -> `_assert_outside_checkout`:129. Excecao exige campanha/backups/exportacoes fora da pasta do aplicativo. Causa imediata: destino rejeitado pelo guard, nao falha demonstrada de exportacao de dados. Acao:A2, preservar guard.

**E02 - ERROR / ValueError - A2**

`test_clock_guard.ClockGuardTests.test_import_initializes_new_anchor_without_crediting_pre_import_time`

L2290..2300: `tests/test_clock_guard.py:413`, `export_campaign` -> servico`:471` -> guard`:129`, mesma excecao de caminho. Para antes de demonstrar a regra de credito/reancoragem de importacao. Acao:A2; nao alterar o clock guard para mascarar path invalido.

**E03 - ERROR / RuntimeError - A2**

`test_gameplay_diagnostics.GameplayDiagnosticsTests.test_gameplay_log_is_in_stable_user_data_outside_install_and_saves`

L2303..2317: teste`:68` -> `gameplay_log_path` em`app/desktop/gameplay_diagnostics.py:29` -> `user_log_directory` em`app/desktop/paths.py:19` -> `user_data_directory`:14. Mensagem: pasta de dados nao pode ficar dentro da pasta do aplicativo. O teste cria LOCALAPPDATA sob TemporaryDirectory. Acao:A2, corrigir origem dos temporarios, nao o guard de instalacao.

**E04 - ERROR / FileNotFoundError - A2, com confirmacao dirigida posterior**

`test_gameplay_diagnostics.GameplayDiagnosticsTests.test_gameplay_log_survives_campaign_migration_and_regional_production`

L2320..2332: teste`:40`, `gameplay_log.read_text` -> pathlib:1027/1013 -> `io.open`. Arquivo ausente:

```text
App GIM\.candidate-010-validation-87774a241f3f4791bdf91fc954e1df2e\tmp\tmp5wq4h1ox\LocalAppData\GuildIdleManager\logs\gameplay-actions.log
```

O path invalido esta explicito na stack. Leitura estatica do teste mostra o patch de LOCALAPPDATA nesse diretorio; `log_gameplay_action` captura OSError/RuntimeError e retorna sem bloquear gameplay. Isso explica por que um guard pode resultar em arquivo nao criado sem sua excecao original aparecer aqui. **A stack desta ocorrencia prova apenas o arquivo ausente**, nao registra diretamente a excecao engolida; classificar como efeito ambiental consistente com E03, a confirmar apos A2, nao como prova de perda de log por migracao. Acao:A2 antes de investigar persistencia do logger.

**E05 - ERROR / ImportError de modulo, causa ModuleNotFoundError - A1**

`unittest.loader._FailedTest.test_github_releases`

L2335..2346: loader396/339 -> `tests/test_github_releases.py:7` -> `cryptography.hazmat.primitives.serialization`; `No module named 'cryptography'`. Nenhum caso interno do modulo foi validado. Acao:A1.

**E06 - ERROR / ImportError de modulo, causa ModuleNotFoundError - A1**

`unittest.loader._FailedTest.test_launcher_ui_contracts`

L2350..2365: loader -> teste`:4` -> `app/desktop/update_launcher.py:19` -> `app/services/github_releases.py:20` -> `cryptography.exceptions.InvalidSignature`. Causa: dependencia ausente, nao assert de contrato de UI. Acao:A1.

**E07 - ERROR / ImportError de modulo, causa ModuleNotFoundError - A1**

`unittest.loader._FailedTest.test_launcher_update_flow`

L2369..2380: loader -> `tests/test_launcher_update_flow.py:11` -> `cryptography.hazmat.primitives.serialization`. Acao:A1; fluxo de atualizacao nao foi exercitado por esse modulo.

**E08 - ERROR / ImportError de modulo, causa ModuleNotFoundError - A1**

`unittest.loader._FailedTest.test_publish_dev_release_workflow`

L2384..2395: loader -> `tests/test_publish_dev_release_workflow.py:12` -> `cryptography.hazmat.primitives.serialization`. Acao:A1; nao e evidencia de falha do workflow publicado.

**E09 - ERROR / ImportError de modulo, causa ModuleNotFoundError - A1**

`unittest.loader._FailedTest.test_release_signing_tool`

L2399..2410: loader -> `tests/test_release_signing_tool.py:11` -> `cryptography.hazmat.primitives.serialization`. Acao:A1; nao demonstra assinatura incorreta do produto.

**E10 - ERROR / ImportError de modulo, causa ModuleNotFoundError - A1**

`unittest.loader._FailedTest.test_tavern_apprentice_search`

L2414..2431: teste`:15` -> `app/main.py:17` -> `app/routes/update_routes.py:12` -> `github_releases.py:20` -> `cryptography.exceptions.InvalidSignature`. Acao:A1; nao classificar como regra de busca da Taverna quebrada, pois o modulo nao chegou a executar casos.

**E11 - ERROR / ImportError de modulo, causa ModuleNotFoundError - A1**

`unittest.loader._FailedTest.test_workshop_route_diagnostics`

L2435..2452: teste`:18`, importa`protect_desktop_loopback` -> `app/main.py:17` -> `update_routes.py:12` -> `github_releases.py:20` -> `cryptography.exceptions.InvalidSignature`. Acao:A1; diagnostico de rota da Oficina nao foi alcancado.

## Cada FAILURE - nomes exatos e evidencia

**F01 - FAIL / AssertionError por retorno1em vez de0; filho com ModuleNotFoundError - A1**

`test_campaign_service.CampaignServiceTests.test_desktop_home_without_campaign_uses_asgi_and_omits_session_expiry`

L2456..2469: teste`:112`, `assertEqual(result.returncode,0,result.stderr)`. Filho`<string>:3` -> `app/main.py:17` -> `update_routes.py:12` -> `github_releases.py:20` -> `cryptography`. O processo retorna1 antes da verificacao funcional da Home/ASGI. Acao:A1; nao corrigir a expectativa de retorno para1.

**F02 - FAIL / AssertionError de head Alembic - A3**

`test_campaign_service.CampaignServiceTests.test_two_campaigns_create_open_and_persist_in_isolation`

L2473..2483: teste`:117` -> helper`:175`, compara `SELECT version_num FROM alembic_version` a`CURRENT_ALEMBIC_HEAD`; obtido`e9f8a7b6c5d4`, esperado`f7a8b9c0d1e2`. Leitura estatica confirma literal f7 em`tests/test_campaign_service.py:59`. Acao:A3; nao concluir falta de isolamento a partir desse assert de revisao.

**F03 - FAIL / AssertionError de head Alembic - A3**

`test_campaign_service.CampaignServiceTests.test_upgrade_from_pre_event_revision_preserves_campaign_regional_run_and_backup`

L2486..2494: teste`:594`, `migration.current_revision` obtido e9 vs literal f7. Acao:A3, preservando validacoes de campanha, atividade regional e backup; o assert nao demonstra sozinho perda desses dados.

**F04 - FAIL / AssertionError de head Alembic - A3**

`test_campaign_service.CampaignServiceTests.test_upgrade_from_previous_alembic_revision_keeps_data_and_makes_backup`

L2497..2505: teste`:456`, revisao obtida e9 vs f7. Acao:A3; nao reclassificar como erro de importacao ou migracao missing-common do CR.

**F05 - FAIL / AssertionError de head Alembic - A3**

`test_campaign_service.CampaignServiceTests.test_upgrade_from_work_one_head_adds_pause_state_and_updates_schema_version`

L2508..2516: teste`:668`, `migration.current_revision` e9 vs f7. Acao:A3; preservar asserts especificos de pause state/schema que vierem depois.

**F06 - FAIL / AssertionError de head Alembic - A3**

`test_campaign_service.CampaignServiceTests.test_upgrade_unifies_crystals_without_changing_total_save_balance`

L2519..2527: teste`:498`, `migration.current_revision` e9 vs f7. Acao:A3; esse ponto de parada nao comprova alteracao indevida do saldo de cristais.

**F07 - FAIL / AssertionError por retorno1em vez de0; filho com ModuleNotFoundError - A1**

`test_desktop_http_smoke.DesktopHttpSmokeTests.test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions`

L2530..2544: teste`:2038`, compara retorno do filho; `desktop_http_smoke_child.py:9` importa`app.main` -> `update_routes` -> `github_releases` -> `cryptography`. Acao:A1 primeiro. **Nao e a assercao antiga do Guia informada pelo CR**: a execucao registrada aqui nem terminou a importacao da app no filho.

**F08 - FAIL / AssertionError por retorno1em vez de0; filho com ModuleNotFoundError - A1**

`test_desktop_security.DesktopSecurityTests.test_loopback_allowlist_fails_closed_and_rejects_cross_origin_requests`

L2547..2560: teste`:56`, retorno1; filho`<string>:3` -> `app.main` -> `update_routes` -> `github_releases` -> `cryptography`. Acao:A1; nao indica que o allowlist aceitou uma origem proibida, pois o fluxo nao chegou a esse assert funcional.

**F09 - FAIL / AssertionError funcional, causa raiz ABERTA - A4**

`test_lot_b_materials_market.LotBMaterialProgressionTests.test_assignment_freezes_legacy_fallback_before_level_up_and_keeps_target_on_live_advance`

L2564..2569: teste`:136`, `self.assertEqual(first["stored"],1)`, obtido0. Leitura estatica: fixture cria Madeira Bruta common, atribuicao sem alvo explicito, e chama`advance_assignment` apos1minuto; para no primeiro stored, antes do trecho posterior de subir nivel/conferir congelamento do alvo. O log nao inclui retorno completo, catalog_missing, pausa ou selecao de material. Acao:A4. Nao confundir o sintoma com o P1 missing-common: esta fixture contem um template common, e nao ha stack demonstrando que o problema seja reset/migracao.

**F10 - FAIL / AssertionError funcional, causa raiz ABERTA - A5**

`test_ml050_cpu_internal_contract.CpuInternalContractTests.test_public_viability_at_planner_start_prevents_later_internal_fallback`

L2572..2577: teste`:266`, `self.assertEqual(len(decisions),1,decisions)`, obtido0 e`decisions=[]`. Leitura estatica: prepara inicio regional com uma CPU strong ativa, torna uma oferta publica de contrato acessivel por requisito de guilda1/duracao60, chama`_prepare_cpu_region_cycle_start` e`_cpu_plan_for_guild_v6(prepared_start=...)`. O log nao mostra os demais requisitos/roster nem rejeicoes do planejador. Para antes dos asserts posteriores sobre tipo/publico e ausencia de contrato interno. Acao:A5. Nao concluir que o fallback interno foi criado ou que nao havia equipe elegivel sem evidencia adicional.

## Quatro skips

L2582 registra`skipped=4`, mas o log nao verboso nao informa seus nomes ou motivos. Busca textual de`skip` retorna somente o resumo, nao linhas individuais de justificativa. **S01,S02,S03,S04: identidade indisponivel; motivo nao registrado neste log.** Nao inferir plataforma, dependencia opcional ou justificativa a partir de decorators do checkout atual. O motivo so podera ser atribuido com uma evidencia de execucao que efetivamente o contenha; nao se fez rerun para obte-lo.

## Candidatos estaticos - nao identificacao executada

Complemento somente de leitura: busca por decorators `skip/skipIf/skipUnless`, `self.skipTest`, `SkipTest`, marcacoes pytest e hooks de descoberta em `tests/test_*.py`. Nenhum modulo de teste/runtime foi importado ou executado; nao se avaliou decorator. O comando exato de descoberta, filtros, variaveis da execucao e nomes dos skips nao constam dos logs consultados. Fontes atuais nao sao prova de identidade com as fontes da rodada.

Ha evidencia adicional de POSICAO, nao de nome: L1354 contem `...Fss..s.WARNI [root] ...`; L1355 comeca com `...........sF...`. Sao os quatro marcadores `s`. Sob ordem alfabetica padrao de unittest e fontes iguais, `ss..s` coincide com os cinco metodos do instalador: backup-cleanup e first-install pulados, foreign-folder e junction executados, post-copy pulado. Os doze metodos atuais de launcher cabem entre esse bloco e o `sF` compativel com runtime opt-in seguido de desktop-security. Sem mapa de execucao nominal, isso **nao permite converter os candidatos abaixo em identificacao comprovada**.

| Prioridade estatica | Nome exato candidato | Condicao e motivo literal no fonte | Gate possivelmente sem evidencia |
| --- | --- | --- | --- |
| C1, compativel com primeiro `s` do bloco | `test_desktop_installer.DesktopInstallerSafetyTests.test_backup_cleanup_failure_after_success_keeps_new_install_and_backup` | `tests/test_desktop_installer.py:183`: `skipUnless(BUILT_PACKAGE.is_dir(), "Build the DEV package before testing backup cleanup failure")` | Falha de limpeza apos sucesso, preservacao do novo app e backup |
| C2, compativel com segundo `s` | `test_desktop_installer.DesktopInstallerSafetyTests.test_first_install_and_managed_update_preserve_saves_and_replace_app_files` | `tests/test_desktop_installer.py:113`: `skipUnless(BUILT_PACKAGE.is_dir(), "Build the DEV package before testing first install and update")` | Instalacao inicial/update e preservacao dos saves de fixture |
| C3, compativel com terceiro `s` | `test_desktop_installer.DesktopInstallerSafetyTests.test_post_copy_failure_restores_previous_install_and_preserves_save` | `tests/test_desktop_installer.py:143`: `skipUnless(BUILT_PACKAGE.is_dir(), "Build the DEV package before testing rollback after copy")` | Rollback apos substituicao de arquivos, preservacao de save |
| C4, compativel com ultimo `s` | `test_desktop_runtime.DesktopRuntimeSmokeTests.test_window_create_return_close_stops_server_and_closes_campaign` | Decorator de classe em `tests/test_desktop_runtime.py:21`: `os.name == "nt" and RUNTIME_SMOKE_ENABLED`; motivo `Set GIM_RUN_DESKTOP_RUNTIME_SMOKE=1 on Windows to run the native window smoke.` | Janela nativa real/pywebview, parada do servidor e fechamento da campanha |

`BUILT_PACKAGE` vem de `GIM_TEST_BUILT_PACKAGE` ou `App GIM/dist/GuildIdleManager-DEV` (fonte:14..18). `RUNTIME_SMOKE_ENABLED` exige `GIM_RUN_DESKTOP_RUNTIME_SMOKE == "1"` (fonte:18). O log nao registra os valores historicos dessas variaveis nem se o pacote existia naquele instante. Verificar o disco/PATH/ambiente atual nao provaria seu estado na rodada; isso nao foi usado para declarar quais skips ocorreram.

Outros sitios estaticos encontrados, sem omitir alternativas:

- `test_desktop_installer.DesktopInstallerSafetyTests` inteiro tem guard em`:21`, motivo `Requires Windows PowerShell` se nao Windows ou sem `powershell.exe`. Com os cinco metodos atuais e descoberta integral, esse guard sozinho produziria cinco skips, nao quatro; por isso nao explica o total sob essas premissas. `test_junction_install_target_is_refused_without_touching_target` pode executar `self.skipTest` em`:105`, motivo `Could not create a test junction: {created.stderr}`; nao ha stderr nominal dessa condicao no log.
- `test_desktop_art.DesktopArtIntegrationTests.test_initial_and_partial_regional_notices_are_sorted_before_opening` (`:19`), `test_regional_notice_replaces_a_different_event_of_the_same_type` (`:76`) e `test_market_estimates_initialize_for_replaced_game_content` (`:98`) exigem `shutil.which("node")`; motivos, respectivamente: `Node.js is required for the JavaScript queue regression.`, `Node.js is required for the JavaScript identity regression.`, `Node.js is required for the market estimate regression.`
- `test_regional_supply_js.RegionalSupplyScriptTests.test_prepared_supply_skips_inventory_quote_and_keeps_new_preparation_guard` tem guard de classe em`:10`, condicionado a `NODE=shutil.which("node")`, motivo `Node.js is needed for the regional supply browser-script regression`. Os33passes Node do log separado nao provam o PATH do processo Python de descoberta; estes quatro guards Node sao alternativas estaticas, embora a posicao dos `s` favoreca C1..C4 sob a ordem padrao.
- `test_desktop_launcher.DesktopLauncherUnitTests` tem quatro guards `os.name == "nt"`: `test_hidden_powershell_helper_executes_with_create_no_window` (`:69`, `The update helper uses Windows process creation flags.`), `test_verified_update_handoff_logs_helper_and_preserves_failed_setup` (`:95`) e `test_verified_update_handoff_logs_synchronous_helper_start_failure` (`:355`, ambos `Verified release handoff uses Windows PowerShell.`), e `test_named_mutex_rejects_second_launcher_for_same_data_profile` (`:633`, `Named Windows mutex is only available on Windows.`). Sao condicionais de plataforma, nao prova de que rodaram ou foram pulados; o log/ambiente informado e Windows, sem metadados nominais desses casos.
- **Excluidos como origem dos skips nesta rodada:** `test_publish_dev_release_workflow.PublishDevReleaseWorkflowTests.test_tag_fetch_refspec_expands_to_matching_remote_and_local_refs` (`:40`, `PowerShell is unavailable for evaluating the workflow interpolation`) e `test_signer_sidecar_resolution_matches_the_built_package_layout` (`:159`, `PowerShell is unavailable for evaluating the build and workflow paths`). Esses dois `self.skipTest` exigiriam executar os metodos, mas L2384..2395 prova que o modulo falhou no import de `cryptography`, antes de chegar a eles. Sao falta de cobertura por ERROR, nao dois dos quatro SKIP.

**Conclusao para gate:** os quatro nomes C1..C4 sao uma explicacao estatica forte e coerente com a posicao dos marcadores, mas continuam candidatos. Nao ha prova nominal para nomear os quatro skips como executados. Nao considerar comprovados por esta rodada os gates de janela nativa, instalacao/update, rollback e limpeza segura; nao declarar esses skips inofensivos. Para fechar a atribuicao sem novo ensaio, seria necessario um registro ja existente de `skipped=[(test_id,reason)]`, saida verbosa ou metadados historicos equivalentes; os dois arquivos de log consultados nao o fornecem. Nenhum gate foi reexecutado ou alterado aqui.

## Cruzamento com CR sem misturar causas

| Achado informado pela coordenacao | Relacao com esta rodada | Handoff |
| --- | --- | --- |
| **P1 reset/migracao missing-common**, DEV corrigindo | Achado independente de integridade. Nao aparece como tal entre as21stacks; asserts de head e Lot B stored0 nao demonstram sua causa. Nao o desconsiderar porque o log tambem tem problemas ambientais. | Manter correcao/regressao dirigida com o DEV e evidencia separada do CR. Esta triagem nao a implementa nem certifica. |
| **P2 smoke Guia, assercao antiga** | Pode afetar o mesmo smoke em uma execucao que alcance o Guia, mas F07 falhou antes, no import de`cryptography` do subprocesso. A stack desta rodada nao executou/confirmou aquele assert. | Corrigir/alinhar a assercao do Guia conforme CR; apos A1, verificar o smoke sem confundir eventual novo ponto de parada com a causa inicial registrada aqui. |

## Handoff curto

1. Ambiente: A1 para7modulos nao importados e3filhos; A2 para caminhos temporarios/LOCALAPPDATA fora de App GIM, sem enfraquecer guards.
2. Expectativa: A3 para os5asserts de head f7 vs e9, sem mascarar verificacoes de dados/backup.
3. Investigacao ainda necessaria: A4 Lot B stored0 e A5 CPU decisions vazia; nenhuma causa raiz declarada sem prova.
4. CR independente: P1 missing-common e P2 Guia continuam itens proprios;4skips sem motivo publicado;100ciclos/Node positivos nao liberam a suite integrada.

Relatorio preserva o resultado inicial da rodada; nao afirma estado apos os fixes que o DEV esta produzindo em paralelo.
