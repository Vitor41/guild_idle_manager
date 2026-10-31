# Aceite — lote de melhorias 2

Branch `melhorias-lote-2`, baseada em `melhorias-lote-1`. Save real, janela nativa, build e instalador não foram abertos ou executados. Todos os testes deste lote usam fixtures temporárias. A inspeção visual final continua com o usuário.

## Quatro problemas reportados

| Item | Comportamento e arquivos/rotas | Evidência executada | Resultado |
|---|---|---|---|
| Designar trabalhador de coleta | `POST /gathering/assign` chama `assign_worker`, grava a tarefa, redireciona com feedback; formulário em `app/templates/gathering/index.html`. | `tests.test_desktop_http_smoke`: POST HTTP em campanha descartável e consulta do vínculo salvo. `tests.test_gathering_service`: exclusividade, ciclos idempotentes e pausa por capacidade. | Corrigido e coberto em HTTP/serviço. Aparência nativa não inspecionada. |
| Preparar ou iniciar contrato sem suprimento | `app/static/js/regional-supply.js` mantém o checkbox habilitado sem equipe e durante a cotação; somente Preparar depende de cotação disponível. A ação sem suprimento desmarca explicitamente o checkbox. Os endpoints `/regional/offers/{id}/prepare` e `/start` revalidam no servidor. | `tests.test_stage5_ui_contracts`: estado selecionável, prevenção de envio com suprimento inválido e revalidação no servidor; `tests.test_desktop_http_smoke` renderiza as páginas regionais. | Correção cliente/contrato verificada. Não houve ensaio visual ou instalação. |
| Índice do Guia de Classes | `app/templates/classes/index.html`, `app/static/css/main.css`, `app/static/js/main.js`; chips compartilham a forma do Guia do Jogo, foco destacado, seis destinos nomeados, estado ativo por seção e movimento reduzido. | `test_gathering_assignment_feedback_and_accessible_offline_and_class_guides` verifica as seis âncoras e os estados. | Estrutura e estilo em código cobertos; visual manual pendente. |
| Ajuda de estamina do Modo Offline | `CampaignInfo` carrega o saldo e o progresso confirmado; checkpoint de 30 s atualiza o resumo. A barra mostra saldo/teto e a ajuda descreve taxa, próxima recarga, limite de ausência e retorno à seleção. Mouse, teclado, toque e Escape. | `tests.test_desktop_http_smoke` confere o saldo/taxa renderizados numa campanha temporária; contrato de UI verifica descrição e estado de foco. | Dados reais e texto cobertos; hover/foco/viewport nativo aguardam conferência manual. |
| Vigília aparentava durar mais de seis horas | `CYCLE_SECONDS = 6 * 60 * 60`; datas SQLite sem offset são tratadas como UTC em `main.js`, `evolution-dialogs.js`, `mission_timers.js` e `regional-supply.js`. A página regional e convites de rebelião serializam timestamps com offset UTC. | `tests.test_time`, teste de contrato UTC e `tests.test_regional_cycle_service` passaram dentro do conjunto focado. | A interpretação de fuso foi corrigida; seis horas não foram alteradas. |

## Auditoria dos 16 itens anteriores

| # | Item a conservar | Arquivo/rota ou teste de referência | Situação nesta rodada |
|---:|---|---|---|
| 1 | Ranking regional em tabela | `app/templates/regional/index.html`, `.evolution-ranking-table`; `tests.test_desktop_http_smoke` | Renderizado em smoke HTTP; aparência/viewport manual pendente. |
| 2 | Menu Vigília abre no topo | Link `/regional` com `data-async-navigation` e `data-scroll-top` em `app/templates/base.html`; navegação assíncrona no JS | Mantido; smoke HTTP cobre a rota, sem medição visual de scroll. |
| 3 | Missões e Masmorras refletem as operações da Vigília | `/regional/offers/{id}/start` usa `start_mission`/`start_dungeon` e encaminha à página correspondente | Fluxo comum preservado; smoke HTTP cobre ambas as páginas. Participação natural em evento continua fora deste lote. |
| 4 | Ciclo regional de seis horas | `app/services/regional_cycle_service.py:CYCLE_SECONDS`; `tests.test_regional_cycle_service` | Regra é 21.600 s; correção deste lote só ajusta serialização/interpretação UTC. |
| 5 | Inventário compacto | `app/templates/inventory/index.html`, `app/static/css/desktop-theme.css` | Estrutura e regras responsivas existentes; conferência visual continua pendente. |
| 6 | Efeitos dos prédios Contratos e Exploradores | `app/services/building_balance_service.py`; testes de balanço/capacidade de prédios | Gates de início regionais removidos em lotes anteriores e mantidos; efeitos econômicos específicos não foram alterados nesta rodada. |
| 7 | Oito famílias de coleta | `app/services/gathering_service.py:RESOURCE_FAMILIES`; formulário por família | Atribuição HTTP por Madeira e cobertura de serviço passaram; catálogo permanece dirigido pelo mapa de famílias. |
| 8 | Barra animada de coleta | `app/static/js/gathering-cycle.js`; `data-gathering-cycle` em `app/templates/gathering/index.html` | Código preservado; animação visual não foi aberta no navegador. |
| 9 | Âncoras do Guia de Classes | `app/templates/classes/index.html`; teste novo em `tests.test_stage5_ui_contracts` | Seis destinos e seção de Classes nomeada; verificação estrutural passou. |
| 10 | Sinergia de formação até +200 poder | Serviço de composição/sinergia e testes de missão/grupo | Sem alteração nesta rodada; validação visual não aplicável. |
| 11 | Preparação de suprimento | `app/static/js/regional-supply.js`; rotas de cotação/preparo/início | Checkbox não é mais bloqueado sem equipe/cotação; botão de preparo continua protegido por cotação válida. Teste estrutural passou. |
| 12 | Iniciar conteúdo sem gate de construção | `validate_mission_requirements`, `start_mission`, `start_dungeon`; `are_dungeons_available` | Sem gate residual nos inícios regionais; outras validações de equipe e conteúdo permanecem. |
| 13 | Guia de raridade de Comum a Mítico, sem T1–T8 | `app/templates/tiers`; `app/services/display_service.py` | Conteúdo anterior preservado; não houve mudança nesta rodada. |
| 14 | Nomes de itens sem códigos internos | `display_name` e `rarity_label` em inventário/Códex | Conteúdo anterior preservado; testes de UI existentes cobrem vazamento de identificadores. |
| 15 | Recompensas tardias sem duplicação | Claims transacionais/idempotentes em `app/services/achievement_service.py`; `tests.test_achievement_milestones` | Nenhuma lógica de recompensa alterada nesta rodada; regressão da suíte permanece necessária. |
| 16 | Atualização e versão | `app/core/version.py`, `docs/UPDATE_ARCHITECTURE.md`, `docs/CHANGELOG.md` | Versão funcional incrementada de `0.2.0` para `0.3.0`; instrução de uso da versão DEV consta no documento de atualização. Não foi gerado instalador a pedido do usuário. |

## Testes desta rodada

| Conjunto | Resultado |
|---|---|
| `tests.test_stage5_ui_contracts`, `tests.test_time`, `tests.test_gathering_service`, `tests.test_gathering_online_offline_parity`, `tests.test_regional_cycle_service`, `tests.test_supply_preparation`, `tests.test_achievement_milestones` | **34 testes passaram em 131,959 s**, SQLite/fixtures descartáveis. |
| `tests.test_campaign_service` | **16 testes passaram em 142,643 s**. Atualizadas expectativas de revisão antiga para o head presente `b1c2d3e4f5a6`; exportação/migração/isolamento foram repetidos. |
| `tests.test_stage5_ui_contracts`, `tests.test_time`, coleta e `tests.test_desktop_http_smoke` | **25 testes passaram em 54,451 s**. O smoke HTTP enviou o POST de coleta e verificou atribuição salva, saldo real renderizado e offset UTC da Vigília em campanha temporária. |

Stage 5 e aceite visual do jogo permanecem abertos conforme `docs/work3_acceptance_matrix_2026-10-29.md`. Não foram executados build, instalador, navegador de inspeção ou GUI. O usuário pediu que a rodada terminasse sem instalação.
