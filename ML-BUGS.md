# Registro de Melhorias e Bugs

Registro das anotações de gameplay e acompanhamento das correções, iniciado em 2026-11-01. Evidências e critérios originais foram preservados; o status abaixo reflete implementação e validação automatizada.

## Resumo

- 11 anotações investigadas.
- 11 melhorias registradas: `ML-001` a `ML-011`.
- 1 inconsistência de implementação registrada: `BUG-001`.
- 12 correções implementadas no ramo `fix/ml-bugs-followup`; validação automatizada aprovada nos testes direcionados e simulação descritos abaixo.
- Build, instalação e revisão visual do aplicativo instalado não foram realizados nesta rodada.

## Melhorias

### ML-001 — Aumentar a atividade das guildas CPU

- **Origem:** anotação 1.
- **Status:** Validada; simulação de 100 Vigílias aprovada. A cadência inicial das quatro guildas CPU da região do jogador aumentou de cerca de 1,25 para 1,43 ações esperadas por Vigília.
- **Implementação/evidência:** `app/services/regional_cycle_service.py` (`CPU_ACTION_PROBABILITY_BY_PROFILE`, `regional_cpu_action_probability` e `_cpu_plan_for_guild`). Probabilidades ajustadas para 31% (forte), 29% (média) e 26% (nova), com teto de 40%; a composição inicial produz aproximadamente 1,43 ações CPU esperadas por Vigília.
- **Impacto:** relatórios podem mostrar pouca atividade; a região pode demorar mais para acumular ameaça e gerar eventos. É necessário simular cadências antes de escolher novos valores.

### ML-002 — Mostrar somente os cinco relatórios regionais mais recentes

- **Origem:** anotação 2.
- **Status:** Validada; a consulta de relatórios regionais está limitada aos cinco fechamentos mais recentes.
- **Problema:** a tela exibe até oito fechamentos, enquanto o pedido é limitar a cinco.
- **Implementação/evidência:** `app/services/regional_cycle_service.py`, `get_regional_board()` limita a lista a cinco relatórios; `app/templates/regional/index.html` renderiza a lista recebida.

### ML-003 — Ajustar frequência e janela da oferta especial da Taverna

- **Origem:** anotação 3.
- **Status:** Validada; novas configurações usam 12 horas entre tentativas e 3 horas de duração. A migração ajusta os valores legados padrão sem reescrever `next_special_check_at` nem `available_until` já persistidos.
- **Pedido:** tentar gerar oferta a cada 12 horas e mantê-la disponível por 3 horas.
- **Implementação/evidência:** configuração padrão é 12 horas para intervalo e 3 horas para duração. O serviço agenda tentativa e expiração pelos valores configurados.
- **Evidência:** `app/models/tavern.py` (`special_spawn_cooldown_hours`, `special_offer_duration_hours`) e `app/services/tavern_service.py` (`_advance_special_offer`/agendamento, `available_until`). Os timestamps de tentativas e ofertas existentes são persistidos; alterar a configuração não reescreve retroativamente timers já gravados.

### ML-004 — Manter a guilda do jogador visível fora do Top 10

- **Origem:** anotação 4.
- **Status:** Validada; o Top 10 mantém uma linha separada para a guilda do jogador quando ela está abaixo da décima posição.
- **Problema:** o ranking renderiza apenas as dez primeiras guildas. Se a guilda do jogador ficar abaixo da décima posição, ela desaparece da tabela.
- **Implementação/evidência:** `app/services/regional_cycle_service.py` fornece os dados do jogador separadamente quando sua posição está abaixo do Top 10; a tela preserva a linha “Sua guilda”.

### ML-005 — Criar navegação de regiões e visão macro das guildas

- **Origem:** anotação 5.
- **Status:** Validada; o teste HTTP cobre a nova rota de detalhes regionais; o mapa abre uma página por região com navegação, indicadores e resumo comparável de patrimônio, elenco, contratos, masmorras, chefes e eventos.
- **Pedido:** navegar entre regiões e consultar resumos comparáveis por guilda, incluindo patrimônio, elenco/tiers, resultados de contratos, masmorras, chefes e eventos.
- **Implementação/evidência:** `app/routes/regional_routes.py` e `app/templates/regional/detail.html` oferecem navegação pelas regiões, indicadores e atualização; o resumo compara patrimônio, níveis/tiers do elenco e resultados persistidos por tipo de oferta.
- **Observação:** parte dos dados de atividade pode ser agregada dos planos e resultados persistidos; o escopo e a retenção desses agregados precisam ser definidos na implementação.

### ML-006 — Limitar histórico de missões a cinco e acrescentar indicadores

- **Origem:** anotação 6.
- **Status:** Validada; o histórico mostra cinco resultados e calcula missões concluídas, sucessos, falhas e taxa de sucesso sobre o histórico completo.
- **Pedido:** mostrar cinco resultados recentes e indicadores de total de missões, sucessos e taxa de sucesso.
- **Implementação/evidência:** `app/services/mission_service.py` limita a lista recente a cinco e calcula os indicadores sobre o histórico completo; `app/templates/missions/index.html` apresenta os quatro KPIs.

### ML-007 — Permitir coleta programada por quantidade

- **Origem:** anotação 7.
- **Status:** Validada; testes de serviço aprovados para metas finitas; designações aceitam meta opcional de 1 a 100.000 unidades, contam ciclos de 60 segundos e liberam o mercenário ao cumprir a meta, inclusive durante processamento offline.
- **Pedido:** além da coleta contínua, permitir informar uma quantidade, contar ciclos de 60 segundos, parar ao atingir a meta e liberar o mercenário.
- **Implementação/evidência:** `GatheringAssignment.target_quantity` e `quantity_collected` guardam a meta e o progresso; `advance_assignment` termina a designação ao atingir a quantidade, em avanço online ou offline. Testes direcionados cobrem metas finitas.

### ML-008 — Unificar Cristais e remover Cristais Especiais

- **Origem:** anotação 8.
- **Status:** Validada; há um único saldo visível de Cristais. Testes cobrem migração e persistência; o prêmio offline e drops raros de contratos, masmorras e chefes A–S entram no mesmo saldo, sem consumir capacidade do Armazém.
- **Regra confirmada:** existe apenas o recurso `Cristais`. Ao completar 8 horas offline, o jogador recebe Cristais normais; além disso, Cristais devem ser escassos, com chance de drop em chefes e masmorras de Rank A–S. Não existe uma categoria separada de “Cristais especiais”.
- **Implementação/evidência:** `app/models/guild.py`, `app/templates/components/treasury.html`, `app/services/offline_progress_service.py`, `app/desktop/clock_guard.py` e migração `c7d8e9f0a1b2`. O teste de migração verifica preservação do saldo total e dos timers legados da Taverna; teste do clock guard verifica a persistência do saldo unificado. O teto offline continua em 8h; drops A/S são raros.

### ML-009 — Atualizar os totalizadores de recursos sem recarregar a página

- **Origem:** anotação 9.
- **Status:** Validada; teste da rota confirma os totais; endpoint autenticado publica recursos e a interface sincroniza tesouro, painel geral e contadores compartilhados a cada 15 segundos e após carregamento.
- **Pedido:** tesouro, visão geral e demais componentes devem refletir alterações de recursos durante o jogo aberto sem refresh manual ou forçado.
- **Implementação/evidência:** `app/routes/dashboard_routes.py` fornece `/api/resources` autenticado; `app/static/js/main.js` sincroniza os nós marcados a cada 15 segundos e no carregamento. `tests/test_ml_followup_routes.py` cobre a resposta com inventário e reserva de Cristais.

### ML-010 — Exibir tamanho mínimo e máximo do grupo nas ofertas regionais

- **Origem:** anotação 10 (continuação da pergunta sobre a oferta Rank D).
- **Status:** Validada; testes da rota regional cobrem início pelo snapshot; card e diálogo mostram grupo mínimo–máximo e nível mínimo da guilda.
- **Pedido:** mostrar no card/modal quantos mercenários são exigidos, por exemplo, “Equipe: 2–4”.
- **Implementação/evidência:** card e diálogo mostram intervalo mínimo–máximo e nível da guilda; o serviço usa os snapshots congelados ao iniciar a oferta. Coberto pelo teste de fluxo regional e pelo teste que altera os requisitos do template depois da criação.

### ML-011 — Exibir o nível mínimo da guilda nas missões/ofertas

- **Origem:** anotação 11 (mensagem “Nível da guilda insuficiente para esta missão”).
- **Status:** Validada; teste regional cobre os requisitos congelados; ofertas exibem o nível mínimo, mantêm o requisito do template e bloqueiam a ação com o motivo visível até que a guilda seja elegível.
- **Pedido:** informar o nível mínimo exigido antes da tentativa de iniciar.
- **Implementação/evidência:** `RegionalOffer.required_guild_level_snapshot` congela o requisito; ofertas inelegíveis permanecem visíveis com requisito e ação desabilitada. A criação de ofertas não descarta conteúdo apenas por nível, e a contagem de ofertas abertas considera a elegibilidade.

## Bugs / Inconsistências

### BUG-001 — Requisitos da oferta regional não são aplicados a partir do snapshot

- **Origem:** evidência encontrada ao investigar as anotações 10 e 11.
- **Status:** Validado; testes de serviço e rota aprovados para início de contrato/masmorra regional com tamanho do grupo e nível mínimo da guilda congelados na oferta.
- **Problema:** cada `RegionalOffer` congela mínimo/máximo de grupo, mas o início da execução delega para `start_mission()`, que consulta os requisitos atuais do `MissionTemplate`. O nível mínimo da guilda nem sequer tem campo snapshot na oferta e também é lido do template ativo.
- **Consequência:** se um admin alterar esses requisitos durante uma Vigília, uma oferta já criada pode ser exibida/interpretada segundo os requisitos antigos, mas iniciar segundo os novos. Além de causar mensagens inesperadas, isso contradiz a persistência do snapshot de grupo da oferta.
- **Evidência:** `app/models/regional.py` (`RegionalOffer.min_party_size_snapshot` e `max_party_size_snapshot`); `app/services/regional_cycle_service.py` (`_add_offer`); `app/routes/regional_routes.py` (`start_offer` chama `start_mission`); `app/services/mission_service.py` (`validate_mission_requirements` e validação de `min_party_size`/`max_party_size`).
- **Validação:** testes de serviço/rota aprovados: alterar requisitos do template depois da oferta e iniciar usando os valores congelados.

## Validação desta rodada

- `compileall` de `app`, `scripts` e `tests`: aprovado.
- Parse dos templates Jinja: aprovado.
- Testes direcionados de balanço PRD2, coleta, rotas de recursos e serviço regional: aprovados.
- Simulação regional determinística de 100 Vigílias, incluindo economia e isolamento de campanhas: aprovada.
- Testes de migração, timers da Taverna, persistência de Cristais no clock guard e versão de save: aprovados.
- Teste HTTP desktop de páginas e mutações, incluindo detalhes regionais: aprovado (`tests.test_desktop_http_smoke`, 1 teste).
- `alembic heads`: uma única cabeça, `c7d8e9f0a1b2`.
- `git diff --check`: aprovado.
- Build, instalação e revisão visual do aplicativo instalado: não realizados conforme a decisão do usuário.

### Matriz de critérios e evidências

| Item | Critério verificado | Evidência automatizada / implementação |
|---|---|---|
| ML-001 | Maior cadência rival e isolamento de campanhas | `test_cpu_action_cadence_is_above_initial_baseline`; `test_seeded_cpu_simulation_100_cycles_and_campaign_isolation` |
| ML-002 | Painel regional limita relatórios a cinco | `get_regional_board()` aplica limite 5; página regional exercitada em `test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions` |
| ML-003 | Configuração 12h/3h preservando timers existentes | `test_upgrade_unifies_crystals_without_changing_total_save_balance` verifica configuração migrada e timestamps preservados |
| ML-004 | Posição da guilda do jogador permanece visível abaixo do Top 10 | Contexto de ranking inclui linha e posição do jogador; fluxo da página regional coberto pelo teste HTTP desktop |
| ML-005 | Navegação e resumo comparável por região | Rota `/regional/regions/{region_code}` incluída no teste HTTP desktop; template `app/templates/regional/detail.html` |
| ML-006 | Cinco resultados recentes e indicadores do histórico completo | Contexto `get_missions_page_context()` limita a cinco e calcula total, sucessos, falhas e taxa; página exercitada pelo teste HTTP desktop |
| ML-007 | Meta finita encerra coleta e libera trabalhador | `test_finite_assignment_stops_at_target_and_releases_worker`; `test_finite_assignment_rejects_nonpositive_target` |
| ML-008 | Saldo unificado, prêmio offline no teto e persistência | `test_upgrade_unifies_crystals_without_changing_total_save_balance`; `test_crystal_only_at_effective_cap`; `test_crystal_is_granted_once_at_cap_and_survives_reopen` |
| ML-009 | Totais atuais autenticados disponíveis para atualização | `test_authenticated_route_returns_current_single_crystal_balance`; atualização periódica nos nós `data-resource-total` em `app/static/js/main.js` |
| ML-010 | Intervalo de grupo visível e usado ao iniciar oferta | `test_regional_run_uses_frozen_duration_chance_and_rewards`; rota regional exercitada pelo teste HTTP desktop |
| ML-011 | Nível mínimo visível e ação bloqueada sem elegibilidade | Snapshot persistido em `RegionalOffer`; início usa `regional_required_guild_level`; cobertura de fluxo regional pelo teste HTTP desktop |
| BUG-001 | Alterações posteriores do template não mudam os requisitos congelados | `test_regional_run_uses_frozen_duration_chance_and_rewards` altera requisitos após a oferta e inicia pelo snapshot |

### Reteste após revisão independente

- **Segurança de ML-011/BUG-001:** `start_offer` rejeita nível inferior ao snapshot antes de reservar oferta, inclusive no caminho comum a ofertas de rebelião; serviços de missão e masmorra mantêm validação defensiva. `test_requirement_overrides_remain_defensive_in_services` e o smoke HTTP exercitam o bloqueio sem reserva, o grupo abaixo do snapshot e o início elegível após o template mudar para nível 99 e grupo 1–1.
- **Cristais em contratos:** contratos regionais Rank A/S usam chance rara de 2%/1% e gravam um Cristal no saldo `crystals` e em `crystal_reserve`. `test_regional_run_uses_frozen_duration_chance_and_rewards` força sucesso Rank A, sucesso Rank C e falha Rank A para verificar drop somente no primeiro cenário.
- **Meta finita com Armazém:** `test_finite_assignment_counts_only_stored_units_and_completes_after_capacity_resume` força bônus extra com uma vaga restante, confirma que só a unidade armazenada conta, libera espaço e verifica a conclusão/liberação do mercenário ao encher o Armazém no ciclo final.
- **Comandos de reteste:** os três testes focados de serviços passaram; `tests.test_desktop_http_smoke` passou (1 teste, 65,955 s); `git diff --check` passou. A aprovação final do CR ainda está pendente.

## Convenção de status

- **Aberta:** registrada, ainda não implementada.
- **Em andamento:** correção em desenvolvimento.
- **Corrigida:** mudança implementada, aguardando validação.
- **Validada:** critérios de aceitação e regressão aprovados.
- **Descartada:** decisão documentada para não implementar.

Ao concluir ou alterar qualquer item, atualizar este documento com evidência, commit/versão quando aplicável e resultado de validação. Não remover itens encerrados; preservar o histórico de status.
