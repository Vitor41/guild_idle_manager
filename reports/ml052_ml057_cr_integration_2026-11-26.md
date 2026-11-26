# ML-052–057 — integração técnica CR e retestes

Consolidado em 2026-11-26; execuções de integração e retestes em 2026-11-25. Versão sanitizada para inclusão futura no repositório. Não constitui aprovação visual, aceite manual nem autorização de publicação.

## Parecer e fontes fixadas

- Base do pacote: `986b6b7c885c3a2bc8564ebc61514c3e0099223e`, branch `feature/anomalies-ui-audit`.
- Aprovação técnica integrada B0–B6: `604cad188d66918e30f3e06ac530a2f1c1fc01d9`.
- Extensão técnica para versão 0.11.0/CHANGELOG/testes: `ad381ab230a5b10aeb6c7169d5b0d3dc9ba6c0e3`.
- Revisão documental separada: `47b7ec3af6fc2b1195e3fffcc283e9964f509170`. Runtime intacto; referências de evidência locais ainda precisam acompanhar o checkpoint versionado.
- Nenhum achado técnico de runtime permanece aberto após os retestes descritos abaixo. B7/zoom nativo e aceite do usuário continuam pendentes. Nenhum push, PR, merge, build, instalação ou publicação foi executado nesta revisão.

## Método e isolamento

Fontes extraídas por `git archive` dos SHAs revisados, em cópias descartáveis. Nenhum save real, arquivo runtime em edição ou simulador preexistente dirty foi consumido. Objetos Git conferidos; conversão CRLF de exportação foi distinguida de mudança de conteúdo. Na fonte principal havia 1.454 arquivos; no cumulativo 604cad1, 1.455. Nenhuma divergência além dessa conversão textual.

264 arquivos Python foram compilados em memória e 15 scripts passaram `node --check`. O diff-check permaneceu limpo. Cabeça Alembic única: `f8a9b0c1d2e3`. Ambiente de testes do projeto com allowlist temporária de crypto/cffi/backend; perfis e temporários externos ao checkout. Nenhuma dependência foi instalada para obter resultado verde.

A execução Python usou um coletor externo sobre `unittest.defaultTestLoader.loadTestsFromNames` e `TextTestRunner`. Os comandos no final são formas portáteis equivalentes dos seletores efetivamente executados, sem incluir caminhos de máquina ou ferramentas locais de coleta. Não representam uma alegação de invocação literal de `-m unittest` no lugar do coletor original.

## Resultados e história preservada

| Passagem | Fonte | Resultado | Limite |
| --- | --- | --- | --- |
| B2/B3 decisões, produção e 056/057 | 78d43630 | 150/150 Python, zero skips | Reusados por identidade dos blobs de negócio nos deltas posteriores |
| B4 política/eventos/central/catch-up | 78d43630 | 65/72 Python, zero skips | Sete contratos/fixtures antigos falharam; não foi declarada aprovação nessa passagem |
| B5 smoke HTTP | 78d43630 | 0/1 | Interrompido por título antigo esperado no Códex |
| B6 Guia/exportação/privacidade/clock/migrações | 78d43630 | 46/46 Python, zero skips | Inclui seis regressões de migração/backup/rollback |
| Releases, funções com mocks | 78d43630 | 5/6, zero skips | Uma função exigia orientação antiga removida da tela |
| B1 JS inicial | 78d43630 | 75/75, zero skips | Jornada complementar descobriu corrida real de navegação |
| Acessibilidade CSS focal | 0ba1066 | 5/5 Python + 5/5 JS | Aprovação técnica dos contratos CSS; não é medição visual |
| Política corrigida | 0907cae | 13/13, zero skips; 4,203 s | Atores persistidos reais de fixture e negativo sem RNG/stack |
| Smoke HTTP corrigido completo | 0907cae | 1/1, zero skips; 78,437 s | Inclui GET sem claim → POST legítimo → resgatada |
| Releases corrigido | 0907cae | 6/6 funções, zero skips | Execução direta com mocks e temporários; não pytest; sem rede/instalação/reinício |
| B1 JS final | 8bead5b | 80/80, zero skips | Artefato Node registrou exit 0 |
| Complementos CR de navegação | 8bead5b | 13/13 | Nove casos repetidos do arquivo real e quatro adicionais independentes; não somar como 13 novos aos 80 |
| Jornada real headless | 8bead5b | 16 registros aprovados, zero exceções JS | Perfil descartável; mesmo documento; sem POST de gameplay nessa jornada de consulta |
| Cache do JS corrigido | 604cad1 | HTML 200 + asset 200 | URL versão 10 e bytes idênticos ao JS corrigido |
| Versão/Guia | ad381ab | 7/7, zero skips; 45,188 s | Paridade API/HTML/Markdown e privacidade |
| Versão/HTTP completo | ad381ab | 1/1, zero skips; 78,453 s | Atualizações renderiza e informa 0.11.0 |
| Versão/Updates JS | ad381ab | 2/2, zero skips | Inicialização direta/parcial e retry |

Na primeira passagem houve 269 unittest: 261 aprovados e oito não aprovados. Os resultados históricos não foram reescritos como verdes. As sete falhas de política, o smoke e a função Releases foram fechados em novos SHAs; o P2 funcional foi corrigido separadamente.

Tentativas iniciais do coletor com importação incorreta não coletaram testes e não entram nas contagens. A primeira impressão do resultado Node final falhou por encoding do console depois de gravar o resultado; o processo Node havia concluído com exit 0. Esses problemas de coleta não foram atribuídos ao produto.

## Achados fechados e integridade das correções

### Política de spawn

As fixtures antigas usavam a versão atual de ciclo sem criar jogador/CPU nativo elegível. A produção bloqueava corretamente antes do RNG. Em `0907cae150dd8e48e8423e2aea394248bade2880`, as fixtures persistem guilda CPU, elenco e classe nos modelos reais e respeitam a elegibilidade real; somente o RNG determinístico é controlado como antes. A composição é sintética de teste unitário, não medição de CPU semeada ou progredida.

Mantidos os asserts de stack, reset, retry após reload, CD24h, entrada12h, rollback, isolamento e concorrência em duas sessões. Os motivos antigos foram adaptados especificamente à regra v9. O negativo de elenco incapaz exige `no_eligible_content`, nenhum evento, zero stack e nenhuma chamada RNG. Nenhuma regra/template de produção foi relaxado.

### Códex e Updates

O smoke agora prova estado pronto com um único selo, GET preservando saldo e ausência de resgate, POST legítimo e estado Resgatada com crédito exato. Não foi apenas troca de texto esperado. Updates mantém consulta apenas, `download=False` e ausência dos controles/endpoints de instalação e reinício. As seis funções de Releases foram executadas diretamente com `ExitStack`, `patch.object` e diretórios temporários; não houve coleta unittest vazia contada como sucesso.

### Navegação fora de ordem

Repro original: GET da Vigília atrasado em 1,2 s, seguido de GET da Central; a Central aparecia e depois era sobrescrita pela primeira resposta. Reproduzido em navegador real no mesmo documento, sem POST de gameplay.

`8bead5bc6e2670815a185fabe7341f29d1ba050e` verifica revisão, root e rota antes de aplicar headers/corpo, resultado contextual ou fallback. Resposta e erro obsoletos são descartados; POST já enviado não é abortado ou reenviado. Testes adicionais isolam corpo atrasado após headers, troca somente do root, troca somente da rota com erro antigo e POST atual enviado uma vez. O fluxo atual de troca de campanha usa navegação completa, substituindo o documento.

A corrida original passou no navegador: após a resposta atrasada, URL e conteúdo permanecem na Central. A jornada cobriu Oficina, Coleta, Vigília, Central, Inventário, Mercado, Docas, Classes, Guia, Updates e retorno; busca do Guia após reentrada, detalhe de equipamento/Escape/foco e MAX bloqueado por slots cheios foram conferidos. O total positivo e a venda persistida são evidência dos testes de serviço, não foram fabricados nessa jornada com slots ocupados.

Foram usadas âncoras sintéticas com o marcador de navegação parcial para exercitar o handler real em todas as rotas; isso não afirma que todas as âncoras originais usam navegação parcial. Execução Chrome headless em perfil novo e renderização CPU, com sandbox interno desativado somente nessa instância descartável de localhost. Não é prova visual, WebView2 nem teste de segurança do navegador. Tentativas anteriores falharam na inicialização GPU/DevTools ou na limpeza de banco temporário; os ajustes foram apenas do ambiente de coleta. A execução final concluiu as verificações e encerrou com exit 0.

`604cad188d66918e30f3e06ac530a2f1c1fc01d9` altera somente a URL para `main.js?v=20261125-10`. HTML e asset foram servidos por HTTP loopback com template e StaticFiles reais. SHA-256 do JS servido: `4733efed08d299ff392736435a954e46470f5219420582b08a868d6f1380b21a`. Uma tentativa com TestClient não executou por dependência ausente; substituída por HTTP real sem instalar pacotes.

## Reuso proporcional e versão

Desde o backend aprovado `043cb5eceac1bc160c76350cf3a4b628bac2f200`, serviço de eventos, modelos regionais e teste CPU permanecem iguais. No serviço de ciclo, a única definição alterada era `get_regional_board`, para preload/anotação de apresentação. Definições de planejamento, execução e efeitos CPU permanecem iguais. Os cinco focais reais de prioridade/reserva, sucesso/falha antes/due/retry, catch-up e snapshots foram repetidos e passaram. Não houve repetição da simulação de 100 ciclos por cosmética.

Política central, script da simulação de spawn e catálogo medidos em `4999670d79ec08d8573702a19e80eea5020a1e6e` permanecem iguais. Os serviços/modelos mudaram em 055; portanto o estudo ML054 é reutilizado como evidência estatística histórica da fórmula, não como simulação nova do pool nativo v9 ou de combate/recompensas. O estudo usa64seeds×5regiões×180dias×níveis1/15/30/50×scouts0/5. +5p.p. em todas as regiões é sensibilidade; a janela perdida depende da presença ilustrativa20–22UTC. CPUs semeadas não são CPUs progredidas.

Após a aprovação604cad1, `ad381ab230a5b10aeb6c7169d5b0d3dc9ba6c0e3` alterou somente APP_VERSION, CHANGELOG e três testes. Gameplay/JS/CSS idênticos. A constante única, app.version, exportação do Guia e Atualizações em memória/disco indicam0.11.0. O CHANGELOG é restrito ao pacote052–057 e os testes preservam as assertivas anteriores.

## Matriz de cobertura técnica F01–F36

Cada linha corresponde ao gate focal anterior reconciliado com os grupos integrados. Não significa aprovação visual universal de todos os conteúdos/estados.

| Achado | Lote | Escopo | Grupos |
| --- | --- | --- | --- |
| F01 | 057 | Shell, identidade e formatos | B1 + B2/B3 |
| F02 | 057 | Campanhas e launcher | B1 + B6 |
| F03 | 057 | Cabeçalho, recursos e estamina | B1 + B6 |
| F04 | 057 | Âncoras e offsets | B1 + B2/B3 |
| F05 | 057 | Popovers e foco | B1 + B2/B3 |
| F06 | 057 | Resumo de ausência | B1 + B6 |
| F07 | 057 | CTAs e destinos | B1 + B2/B3 |
| F08 | 056 | Taverna, capacidade e saldo | B1 + B2/B3 |
| F09 | 056 | Elenco e classe canônica | B1 + B2/B3 |
| F10 | 056 | Equipamento, consulta e remoção | B1 + B2/B3 |
| F11 | 056 | Resultados e histórico | B1 + B2/B3 |
| F12 | 056 | Estados de Coleta | B1 + B2/B3 |
| F13 | 056 | Oficina e Profissões | B1 + B2/B3 |
| F14 | 057 | Ofertas e grade útil | B1 + B4 |
| F15 | 052 | Drops compartilhados | B1 + B4 |
| F16 | 056/057 | Preparados, reforços e modal | B1 + B4 |
| F17 | 057 | Comparação regional | B1 + B4 |
| F18 | 056 | Rótulos e raridades regionais | B1 + B4 |
| F19 | 057 | Resultados e diagnóstico regional | B1 + B4 |
| F20 | 056 | Designações e polling | B1 + B2/B3 |
| F21 | 055 | Central de eventos | B1 + B4 |
| F22 | 056 | Inventário e Códex | B1 + B2/B3 |
| F23 | 056 | Ferreiro e Desmontagem | B1 + B2/B3 |
| F24 | 056 | Mercado e preço efetivo | B1 + B2/B3 |
| F25 | 056 | Docas e consulta | B1 + B2/B3 |
| F26 | 056 | Construções e Progresso | B1 + B2/B3 |
| F27 | 056 | Reset e proveniência | B1 + B2/B3 |
| F28 | 056 | Requisitos de classe | B1 + B2/B3 |
| F29 | 056 | Profissões e disponibilidade | B1 + B2/B3 |
| F30 | 057 | Guia de Classes | B1 + B2/B3 |
| F31 | 057 | Raridades | B1 + B2/B3 |
| F32 | 056/057 | Estados e retorno do Códex | B1 + B2/B3 |
| F33 | 056 | Descrição canônica | B1 + B2/B3 |
| F34 | 057 | Guia, loader, busca e exportação | B1 + B6 |
| F35 | 057 | Tutorial | B1 + B6 |
| F36 | 057 | Atualizações sem instalar | B1 + B6 |

## Reprodução das baterias

As listas seguintes preservam os seletores executados e permitem reprodução com unittest padrão. Usar fonte isolada no SHA indicado e dependências do projeto. Os testes funcionais de Releases exigem pytest ou execução direta com os mocks/temporários explicitados; não contam por simples importação em unittest.

```text
node --test tests/js/*.mjs tests/frontend/*.js tests/guide_frontend_utils.test.js
node --test tests/js/updates-check.test.mjs
python -B -m alembic heads
git diff --check 986b6b7 604cad1
```

### B2_B3

```text
python -B -m unittest tests.test_workshop_service tests.test_workshop_route_diagnostics tests.test_salvage_balance tests.test_market_max_quantity tests.test_dock_pricing tests.test_ml048_dock_offers tests.test_equipment_pricing tests.test_ml056_roster_result_views tests.test_ml056_inventory_dock_market_views tests.test_stage5_ui_contracts tests.test_tavern_apprentice_search tests.test_building_gate_contract tests.test_building_template_caps tests.test_building_reset_service tests.test_class_change_presentation tests.test_achievement_milestones tests.test_codex_canonical_presentation tests.test_ml056_state_views tests.test_gathering_service tests.test_gathering_polling_contract tests.test_ml057_remaining_views tests.test_ml057_residual_contracts tests.test_ml057_f01_followup
```

### B4

```text
python -B -m unittest tests.test_regional_portal_spawn_policy tests.test_regional_event_service tests.test_navigation_work_status tests.test_regional_route_access tests.test_regional_selection_authority tests.test_supply_preparation tests.test_regional_display_labels tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_cpu_busy_until_keeps_the_longer_priority_or_portal_reservation tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_v9_public_planner_defers_portal_effects_until_due_for_success_and_failure tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_v9_portal_catchup_matches_7_12_14_hour_visits_and_reserves_party tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_regional_run_uses_frozen_duration_chance_and_rewards tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_contract_cutover_preserves_existing_in_progress_offer_snapshot
```

### B5

```text
python -B -m unittest tests.test_desktop_http_smoke
```

### B6

```text
python -B -m unittest tests.test_guide_routes tests.test_desktop_security tests.test_gameplay_diagnostics tests.test_launcher_ui_contracts tests.test_desktop_bridge tests.test_clock_guard tests.test_campaign_service.CampaignServiceTests.test_legacy_building_reset_migration_allows_open_without_common_material_catalog tests.test_campaign_service.CampaignServiceTests.test_upgrade_from_previous_alembic_revision_keeps_data_and_makes_backup tests.test_campaign_service.CampaignServiceTests.test_upgrade_unifies_crystals_without_changing_total_save_balance tests.test_campaign_service.CampaignServiceTests.test_upgrade_from_pre_event_revision_preserves_campaign_regional_run_and_backup tests.test_campaign_service.CampaignServiceTests.test_upgrade_from_work_one_head_adds_pause_state_and_updates_schema_version tests.test_campaign_service.CampaignServiceTests.test_failed_migration_restores_original_schema_and_keeps_backup
```

### Retestes direcionados

```text
python -B -m unittest tests.test_regional_portal_spawn_policy
python -B -m unittest tests.test_desktop_http_smoke
python -B -m unittest tests.test_guide_routes
```

Releases: executar as seis funções `test_` de `tests/test_github_releases.py`, com `monkeypatch.setattr` equivalente a `ExitStack`/`patch.object` e `tmp_path` em diretório temporário, mantendo isolamento por função. Os cenários de assinatura/hash usam respostas falsas e nunca executam o instalador. O teste adicional de navegação usou os helpers/handlers reais extraídos do arquivo testado; o código auxiliar local não faz parte do produto nem é pré-requisito do gate.

## Limites e documentação pré-B7

B0–B6 aprovados tecnicamente em604cad1 e estendidos a ad381ab. B7 visual/zoom real permanece aguardando autorização na conversa DA; reflow equivalente200% não é zoom nativo WebView2. Login/admin e catálogo inteiro não foram auditados visualmente nesta integração. As observações do save real pertencem ao levantamento DA previamente autorizado; nenhum save real foi usado pelo CR.

A revisão documental47b7ec3 contém36/36linhas, preserva história e distingue aprovações técnicas, focais DA, B7 e aceite manual. Foram encontrados quatro relatórios citados expressamente no checkpoint mas ausentes da árvore desse commit:

- `reports/ml057_f01_f07_da_4daf88e_2026-11-25.md`
- `reports/ml057_f03_f06_da_d44be94_2026-11-25.md`
- `reports/ml056_f13_s01_da_2374edc_2026-11-25.md`
- `reports/ml056_final_views_da_78d4363_2026-11-25.md`

Também são relevantes ao fechamento das declarações finais as evidências locais `reports/ml056_f22_f24_f25_f33_da_0434c60_2026-11-25.md` e `reports/ml056_a01_a03_da_0ba1066_2026-11-25.md`, além dos fechamentos focais de elenco, Coleta e restante057. Incluir versões textuais sanitizadas e os links necessários em checkpoint separado; não incluir capturas, perfis ou dados brutos privados. A existência local e a revisão das conclusões não tornam esses arquivos parte do commit revisado.

A lacuna documental não revoga o gate de runtime ad381ab, mas precisa ser reconciliada antes de declarar a evidência versionada completa. Este relatório não concede aprovação global, de DA ou de publicação. Não houve staging/commit pelo CR.
