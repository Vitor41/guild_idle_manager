# Registro de Melhorias e Bugs

Registro das anotações de gameplay e acompanhamento das correções, iniciado em 2026-11-01. Evidências e critérios originais foram preservados; o status abaixo reflete implementação e validação automatizada.

## Resumo

- 11 anotações investigadas.
- 11 melhorias registradas: `ML-001` a `ML-011`.
- 1 inconsistência de implementação registrada: `BUG-001`.
- 12 correções implementadas no ramo `fix/ml-bugs-followup`; validação automatizada aprovada nos testes direcionados e simulação descritos abaixo.
- Build, instalação e revisão visual do aplicativo instalado não foram realizados nesta rodada.

## Incremento solicitado antes da publicação DEV 0.5.0

- **Critérios:** toda oferta especial da Taverna gera mercenário no nível 1, preservando raridade, classe, atributos, nome, preço e janela existentes; o badge da oferta usa a classe/cor da raridade do mercenário (por exemplo, Raro azul também no tema desktop).
- **Implementação/evidência:** `app/services/tavern_service.py` fixa o nível da oferta gerada em 1; `app/static/css/desktop-theme.css` mantém o fundo escuro sem substituir cor e borda definidas por tier em `main.css`. A tela da Taverna renderiza `rarity-badge rarity-rare` para uma oferta rara.
- **Regressões:** `tests.test_tavern_special_offers` verifica geração nível 1 e preservação de raridade, classe, atributos, custo e prazo; `tests.test_desktop_art` protege a classe e a cor do badge; `tests.test_desktop_http_smoke` verifica o badge na página real.
- **Status:** implementação e testes direcionados aprovados; aguardando revisão CR. É incremento da release DEV 0.5.0, sem alteração de versão/tag ou schema, sem migração.

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

### ML-012 — Explicar claramente quando a preparação de suprimento está indisponível

- **Origem:** nova anotação 1 e captura enviada em 2026-11-02.
- **Status:** Validada; a cotação mostra kits, bônus aplicável e motivo de indisponibilidade; preparações regionais debita kit atomicamente com a reserva. Portais iniciados imediatamente continuam usando ouro, e a tela informa isso antes do envio.
- **Pedido:** deixar explícito no card/modal por que o preparo não pode ser iniciado e qual condição falta, em vez de uma mensagem econômica vaga.
- **Evidência observada:** contrato Rank E “Vigiar Acampamento Inimigo em Estrada do Carvalho”; mercenário Vitão nível 3 selecionado; a preparação aparece marcada, mas o botão “Preparar para missão” fica desabilitado e a mensagem diz “O retorno esperado do bônus ainda não cobre 1 ouro.”
- **Explicação técnica preliminar:** o custo mínimo é 1 ouro e a cotação usa apenas o valor esperado de ouro, arredondado para baixo; XP e drops não sustentam o custo. O bônus efetivo também pode ser menor que 5 pontos percentuais quando a chance final do grupo já está próxima do teto de 95%. Neste caso, a mensagem indica que o valor incremental calculado ficou abaixo de 1 ouro. O rótulo genérico “+5 pontos percentuais” não mostra essa redução, contribuindo para a confusão.
- **Implementação/evidência:** `app/services/supply_preparation_service.py` (`quote_supply`) calcula `applied_bonus_pp` com o espaço restante até 95% e desabilita a cotação se o valor esperado em ouro não cobre 1 ouro. `app/routes/regional_routes.py` calcula a chance efetiva após selecionar o grupo.
- **Critério para investigação:** expor o bônus realmente aplicável, explicar o motivo exato do bloqueio e indicar o que o jogador pode mudar; cobrir chance no teto, chance parcial, saldo insuficiente e cotação disponível em teste.

### ML-013 — Revisar o ouro das missões Rank E no início da campanha

- **Origem:** nova anotação 2.
- **Status:** Validada sem buff. Auditoria isolada com 20.000 sequências, Taverna 1, Alojamento 1 e Aprendiz real: 30 ouro iniciais, custo do segundo recrutamento 53, custo do Alojamento nível 2 200; 100% alcançam o ouro do recrutamento e 99,68% o ouro do alojamento em até cinco Vigílias. Ver `reports/ml013_early_rank_e_economy_v0.5.0.md`; madeira continua requisito separado.
- **Pedido:** avaliar se as recompensas de ouro Rank E são baixas no early game, considerando restrições de elenco/alojamento para executar atividades em paralelo e os vários custos que drenam ouro.
- **Critério para investigação:** simular progressão inicial e fontes/drenos de ouro antes de propor buff, verificando que recrutamento, alojamento e demais custos essenciais continuam alcançáveis sem tornar a economia trivial.

### ML-014 — Mostrar o nível do próximo marco nos Escritórios de Missões e Exploradores

- **Origem:** nova anotação 3.
- **Status:** Validada; Escritório de Contratos e Exploradores mostram o próximo marco em múltiplos de 5, sem mudar o efeito de gameplay. Coberto por `test_contract_office_and_scouts_show_the_next_effect_breakpoint`.
- **Pedido:** os cards de Escritório de Missões e Exploradores devem informar o nível da construção em que ocorre o próximo marco e o benefício correspondente, seguindo o padrão já exibido pela Taverna.
- **Critério para investigação:** conferir níveis atuais, marcos configurados e mensagem exibida para ambos os prédios; apresentar o próximo nível e o efeito correto sem alterar os marcos de gameplay.

### ML-015 — Preparar o módulo expansível de Oficinas

- **Origem:** proposta de evolução feita em 2026-11-02 durante o refinamento da preparação de contratos.
- **Status:** Validada no escopo inicial aprovado: área expansível “Oficinas”, uma Oficina de Suprimentos funcional e receita de 3 Carnes + 2 Ervas = 1 Kit. Estoques somados entre tiers são debitados corretamente na mesma transação; receita insuficiente não consome parcialmente. A fabricação no Armazém cheio usa a capacidade líquida pós-receita, sem ultrapassar o limite. Custo regional é coberto; demais oficinas permanecem futuras.
- **Proposta:** criar uma área/menu “Oficinas” que possa abrigar oficinas especializadas, começando pela Oficina de Suprimentos e permitindo futuras áreas como Serralheria e Joalheria. A primeira oficina poderá transformar materiais coletados em itens utilizáveis; exemplo inicial em discussão: 3 Carnes + 2 Ervas = 1 Kit de Suprimentos.
- **Limite atual da decisão:** não implementar ainda todas as oficinas, receitas, profissionais ou desbloqueios. Preservar uma estrutura expansível sem construir conteúdo futuro sem necessidade.
- **Critério para refinamento:** definir navegação, desbloqueio, profissionais, receitas e consumo do kit na preparação antes de iniciar implementação. A quantidade por Rank permanece proposta e sujeita a balanceamento.

### ML-016 — Reavaliar a atividade das guildas CPU com evidência de campanha real

- **Origem:** nova evidência de jogo, relacionada à ML-001.
- **Status:** Validada por instrumentação da campanha. Novos ciclos registram ações planejadas, elegíveis, iniciadas e resolvidas; ciclos legados exibem “não registrado”, pois só persistiam o total final `actions`. A simulação de 100 ciclos mede cadência média inicial de pelo menos 0,70 ação iniciada por guilda elegível e confirma que as ações iniciadas foram resolvidas.
- **Problema observado:** no relatório do ciclo 12 do Bosque de Âmbar, as ações CPU aparecem como `0 sucessos · 0 falhas`, com `Contratos: 0 ações`, `Exploração: 0 ações` e `Segurança: 0 ações`; ao mesmo tempo, a guilda do jogador registrou oito sucessos e uma falha. A guilda do jogador está em primeiro no ranking apesar de estar no início da campanha, com dois mercenários e nível 2.
- **Evidência:** capturas `codex-clipboard-92e626bf-426e-4367-854c-cec300906e17.png` e `codex-clipboard-ecfb16b2-d1e7-417b-8b1c-33a8e2be8455.png`, enviadas em 2026-11-02.
- **Pedido:** tornar as guildas CPU suficientemente ativas para criar competição e evolução regional, considerando que o jogador humano tende a realizar mais ações. A simulação anterior não deve ser tratada como prova suficiente de atividade perceptível na campanha.
- **Critério para investigação:** rastrear quantas ações são planejadas, elegíveis, iniciadas e resolvidas por guilda CPU em cada Vigília; comparar resultados reais de vários ciclos e verificar se o planejamento se perde por indisponibilidade de mercenários, duração, limite, seleção de oferta ou falha de resolução. Propor ajuste com evidência e manter diversidade de perfis sem permitir que o jogador seja sistematicamente ultrapassado por simulação injusta.

### ML-017 — Diferenciar o valor de venda de equipamentos por tipo e raridade

- **Origem:** nova anotação e captura do Mercado enviadas em 2026-11-02.
- **Status:** Validada. Tabela Comum por espaço e acréscimos Common→Mythic estritamente crescentes para mesmo tipo, nível e refino nos Mercados nível 1 e 100; 1.700 equipamentos e 20 comparações auditados. Diferença máxima Common→Mythic do mesmo tipo: 38 ouro no Mercado 1 e 49 no nível 100. Preços administrativos customizados permanecem preservados; ver `reports/ml017_equipment_price_audit_v0.5.0.md`.
- **Problema observado:** equipamentos de raridades diferentes aparecem com o mesmo preço de venda. Na captura, um Brinco Incomum e itens Comuns semelhantes aparecem por 23 ouro.
- **Direção solicitada:** definir valores-base para equipamentos Comuns, diferenciando-os pelo tipo do item; equipamentos semelhantes de raridade superior devem receber acréscimo progressivo de ouro.
- **Critério para investigação:** auditar todos os equipamentos e o cálculo do preço efetivo (valor-base, raridade, nível do item, refino e bônus do Mercado); propor uma tabela explícita de base por tipo e incrementos por raridade, verificando que cada raridade superior tenha preço estritamente maior para itens comparáveis e que não quebre a economia.

### ML-018 — Adicionar atalho MAX à seleção de quantidade no Mercado

- **Origem:** nova anotação do Mercado enviada em 2026-11-02.
- **Status:** Validada. MAX usa `min(estoque, cota restante)` para materiais e fica em zero sem espaço de venda; a cota continua sendo revalidada no servidor. Equipamentos seguem limitados a uma unidade por instância, e a rota agora rejeita uma segunda listagem da mesma instância. Coberto por `tests.test_market_max_quantity`.
- **Pedido:** disponibilizar um botão `MAX` para preencher a maior quantidade que o jogador pode anunciar para venda.
- **Critério para investigação:** calcular o máximo respeitando estoque próprio, limite de quantidade por anúncio e espaços disponíveis no Mercado; não oferecer quantidade acima do permitido. Equipamentos únicos devem continuar limitados à unidade disponível por instância.

### ML-019 — Remover temporariamente a cota de venda de materiais

- **Origem:** anotação do usuário após esclarecer o funcionamento do MAX no Mercado.
- **Status:** Validada; a cota móvel foi removida da regra de venda, da tela do Mercado e do guia.
- **Regra solicitada:** não limitar a quantidade de materiais vendida por janela móvel de 24 horas. A venda continua limitada pelo estoque disponível e pelas regras normais do Mercado, como espaços de anúncio; o botão MAX deve refletir esses limites, sem aplicar cota diária.
- **Contexto:** a cota atual começa em 25 unidades por 24 horas no Mercado nível 1 e cresce com o nível da construção. Não foi identificada evidência de teste de exploit que justificasse essa restrição; não tratar o valor atual como balanceamento validado.
- **Critério de conclusão:** remover a cota do cálculo de quantidade máxima e da validação do servidor, mantendo a validação de estoque, a remoção correta das unidades anunciadas e os limites de espaços do Mercado. Confirmar que materiais de tipos diferentes podem ser vendidos sem cota compartilhada e que o MAX seleciona todo o estoque vendável permitido.
- **Implementação/evidência:** `app/services/market_service.py` calcula MAX pelo estoque e pelos espaços, e não valida cota; mantém checagem e débito de estoque sob lock. Testes separados em `tests.test_market_max_quantity` cobrem MAX 80, venda de 60, venda de 70 unidades em dois materiais, estoque insuficiente e equipamento único. `tests.test_stage5_runtime_validation` confirma que vendas concorrentes não podem exceder o estoque restante. `tests.test_stage5_service_journey_runner` cobre venda de 70 unidades pelo simulador, preserva reserva de 30 e confirma ausência de política/saída de cota. Interface, guia e texto administrativo cobertos em `tests.test_stage5_ui_contracts`.

### ML-020 — Completar os ícones do menu e tornar a sidebar elástica

- **Origem:** captura e solicitação do usuário em 2026-11-02.
- **Status:** Implementada e validada estruturalmente; cobertura visual integrada para todos os 22 links via mapa canônico do manifesto.
- **Pedido:** a DA deve criar/entregar sprites para todos os itens de navegação que ainda não possuem ícone, seguindo a identidade visual desktop já aprovada. Nenhum menu deve aparecer sem ícone. A sidebar deve preencher dinamicamente a altura disponível e manter o fundo contínuo até a base, independentemente da quantidade de menus ou seções adicionadas.
- **Critérios de conclusão:** inventariar todos os links e cabeçalhos da navegação e comprovar cobertura por sprite; integrar os novos assets no manifesto/mapeamento existente sem fallback genérico para entradas sem arte; ajustar o layout para crescer com a altura da janela e com o conteúdo, sem área de fundo interrompida, sobreposição ou perda de rolagem; documentar caminhos dos assets e apresentar evidência de teste responsivo/estrutural. Sem mudança de regras de jogo ou banco de dados.
- **Implementação/evidência:** a DA entregou `docs/art_direction/ML020_DESKTOP_NAV_SPRITES.md`, três famílias de sprites e as 22 entradas `manifest.navigation`; `app/static/js/desktop-art.js` consome esse mapa e marca falha com superfície neutra, sem glyph de fallback. `app/static/css/desktop-sidebar-layout.css` mantém a sidebar na altura da janela, rolagem do conteúdo, menus responsivos e ícones com largura fixa. `tests.test_desktop_art` compara as 22 rotas e sprites locais, verifica altura/rolagem para janela curta e zoom, foco de teclado, ausência de glyph e contraste WCAG AA dos estados de texto/foco. Os dois rótulos de seção são texto, não links, conforme o inventário da DA.

## Bugs / Inconsistências

### BUG-001 — Requisitos da oferta regional não são aplicados a partir do snapshot

- **Origem:** evidência encontrada ao investigar as anotações 10 e 11.
- **Status:** Validado; testes de serviço e rota aprovados para início de contrato/masmorra regional com tamanho do grupo e nível mínimo da guilda congelados na oferta.
- **Problema:** cada `RegionalOffer` congela mínimo/máximo de grupo, mas o início da execução delega para `start_mission()`, que consulta os requisitos atuais do `MissionTemplate`. O nível mínimo da guilda nem sequer tem campo snapshot na oferta e também é lido do template ativo.
- **Consequência:** se um admin alterar esses requisitos durante uma Vigília, uma oferta já criada pode ser exibida/interpretada segundo os requisitos antigos, mas iniciar segundo os novos. Além de causar mensagens inesperadas, isso contradiz a persistência do snapshot de grupo da oferta.
- **Evidência:** `app/models/regional.py` (`RegionalOffer.min_party_size_snapshot` e `max_party_size_snapshot`); `app/services/regional_cycle_service.py` (`_add_offer`); `app/routes/regional_routes.py` (`start_offer` chama `start_mission`); `app/services/mission_service.py` (`validate_mission_requirements` e validação de `min_party_size`/`max_party_size`).
- **Validação:** testes de serviço/rota aprovados: alterar requisitos do template depois da oferta e iniciar usando os valores congelados.

### BUG-002 — Atividades da guilda retornam erro interno sem registro útil no log

- **Origem:** relato do usuário e captura de tela enviados em 2026-11-02.
- **Status:** Corrigida e validada. A exceção reportada foi identificada nos logs e reproduzida com dados de resultado em campanha descartável; a rota renderiza os resultados após a correção.
- **Problema observado:** ao abrir as atividades da guilda, a janela do jogo exibe apenas `Internal Server Error` em uma página em branco.
- **Problema de diagnóstico:** o arquivo `%LOCALAPPDATA%\GuildIdleManager\logs\gameplay-actions.log` não registrava a falha correspondente, impedindo identificar a rota, ação e exceção que causaram o erro.
- **Evidência original:** captura `codex-clipboard-fe81c85d-1fe1-4c69-a0d7-fe9acfd0411f.png` e logs desktop enviados pelo usuário em 2026-11-02; `GET /regional/regions/{region_code}` e a exceção `TypeError` foram identificados no stack trace.
- **Causa raiz:** em `app/routes/regional_routes.py`, a consulta `db.scalars(select(RegionalRunOutcome, RegionalOffer))` retornava somente `RegionalRunOutcome`; o loop tentava desempacotar cada entidade como `(outcome, offer)`, causando `TypeError: cannot unpack non-iterable RegionalRunOutcome object` quando havia resultados registrados.
- **Correção:** a consulta agora usa `db.execute(...).all()`, preservando ambas as entidades por linha.
- **Regressão/evidência:** `tests.test_desktop_http_smoke` cria uma `RegionalRunOutcome` vinculada a uma `RegionalOffer`, abre a rota real `/regional/regions/{region_code}` e confere os contadores renderizados para a guilda. O smoke passou também para `/regional` em campanha nova e migrada; a sonda da falha GET confirma referência e stack trace correlacionados em `desktop.log`.
- **Verificação de padrão semelhante:** busca em rotas/serviços regionais encontrou apenas essa consulta `scalars(select(A, B))`; as demais consultas `scalars()` selecionam entidade ou coluna única.
- **Gate de integração/release:** nenhuma integração, publicação ou release foi realizada. Aguardam-se revisão CR e o gate humano de integração/release. Não declarar a entrega v0.5.0 completa nesta rodada.

### BUG-003 — O handoff de atualização fecha o jogo sem abrir o Setup nem registrar a causa

- **Origem:** relato do usuário, captura do diálogo de confirmação e `desktop.log` enviados em 2026-11-02, durante a atualização de 0.4.1 para 0.5.0.
- **Status:** Em andamento; a versão 0.4.1 fecha a janela, mas o Setup não aparece e o aplicativo continua em 0.4.1.
- **Evidência:** `desktop.log` contém somente o encerramento do Uvicorn; nenhuma etapa do launcher ou do processo auxiliar é registrada. A captura confirma que a versão 0.5.0 foi validada e que a ação de instalação foi confirmada.
- **Comportamento confirmado no código:** o launcher dispara um PowerShell oculto para aguardar o PID do jogo e executar o Setup. O PowerShell espera indefinidamente (`WaitForExit()` sem limite), não registra o progresso em arquivo e só apresenta erro quando captura uma exceção; a limpeza pode apagar o staging após um retorno não zero do instalador.
- **Critérios para correção:** limitar a espera pelo processo do jogo e fornecer diagnóstico explícito caso não encerre; registrar a requisição/fechamento em `desktop.log` e o início do helper, PID, início/fim do Setup, código de saída e stdout/stderr em `%LOCALAPPDATA%\GuildIdleManager\logs\update-handoff.log`; preservar o Setup e staging em qualquer falha ou retorno não zero; cobrir os caminhos de sucesso, timeout e erro em testes.
- **Nota de distribuição:** a instalação 0.4.1 não pode corrigir a si própria se o próprio handoff não inicia o Setup. Depois da correção, poderá ser necessário instalar manualmente uma primeira versão corrigida; isso deve ser explicado ao usuário se confirmado.

### BUG-004 — Coleta de Carne pode consumir ciclos sem produzir item quando falta template ativo

- **Origem:** relato do usuário de que a coleta de Carne não aparece no inventário; imagem de inventário enviada em 2026-11-02.
- **Status:** Correção implementada e testes direcionados aprovados; causa exata no save do usuário permanece não confirmada, pois os logs enviados não registravam a família nem o resultado dos ciclos.
- **Evidência:** inventário mostra Armazém em `435 / 1540`, portanto não estava cheio, e não lista Carne. O log anterior registra requisições/redirects, mas não a família coletada nem unidades produzidas/armazenadas.
- **Falha confirmada no código:** `advance_assignment()` avançava o checkpoint mesmo quando `_material_template()` não encontrava item ativo daquela família, descartando o tempo acumulado sem erro ou aviso. Campanhas com marcador do catálogo já aplicado também não reparavam templates materiais ausentes.
- **Correção:** catálogo elevado para versão 5 e materiais gerados são reconciliados aditivamente antes do retorno por marcador, sem sobrescrever templates existentes; coleta impede nova designação sem item ativo, preserva o checkpoint de designações antigas e mostra aviso se o catálogo estiver incompleto.
- **Diagnóstico adicionado:** `gameplay-actions.log` registra família, ciclos, unidades produzidas/armazenadas/descartadas, ocupação do Armazém e rejeições/liberações de coleta.
- **Regressões:** `tests.test_gathering_service` verifica coleta de Carne, rejeição sem template e preservação do ciclo; `tests.test_campaign_content_versioning` verifica Carne em campanha nova e reparo aditivo de campanha legada preservando o item customizado.
- **Risco residual:** necessário confirmar em versão atualizada que a campanha afetada recebe Carne e que um ciclo aparece no inventário; nenhum save real foi aberto ou alterado durante a correção.

## Validação desta rodada

- BUG-004: `tests.test_gathering_service` + `tests.test_campaign_content_versioning` passaram (14 testes); `compileall` e `git diff --check` passaram. A suíte completa não foi executada.

- Regras de design confirmadas: chance de rebelião de 2% por Vigília elegível; prazos de portal avançam durante catch-up offline.
- Testes direcionados de oficina, coleta/couro+carne, preços, suprimento, marcos de construção e MAX do Mercado: aprovados (27 testes antes da cobertura extra de equipamento único).
- `tests.test_stage5_ui_contracts` + `tests.test_stage5_runtime_validation`: aprovados (33 testes no conjunto).
- Retestes direcionados de `tests.test_regional_cycle_service`, `tests.test_campaign_service` e `tests.test_campaign_content_versioning`: simulação de 100 Vigílias e migração de saves cobertas; cinco testes de migração/campanha, quatro testes de descoberta/compatibilidade e dois casos regionais anteriormente divergentes aprovados após atualizar as expectativas do head e permitir que probabilidade zero desative ações CPU. `test_cpu_stage_counts_remain_unknown_when_upgrading_a_legacy_cycle` confirma estágios `NULL` após migração, e `test_legacy_cpu_report_labels_unmeasured_activity_stages` verifica a apresentação “não registrado”.
- `tests.test_desktop_http_smoke`: página e mutações HTTP desktop aprovadas após ajustar fixtures de inventário sem duplicar linhas; inclui regressão de log/erro GET, renderização de outcome na rota regional, oficinas, cotação e débito regional.
- BUG-002: causa raiz identificada nos logs, corrigida e coberta por regressão da rota real com `RegionalRunOutcome` e `RegionalOffer`; smoke aprovado. A integração/release ainda aguarda revisão CR e gate humano.
- Auditoria ML-013: 20.000 sequências reproduzíveis em campanha descartável; sem abrir saves do jogador.
- Auditoria ML-017: 1.700 equipamentos, 20 comparações tipo/raridade/Mercado, monotonicidade estrita e faixa econômica documentadas.
- `alembic heads`: uma única cabeça, `d9e0f1a2b3c4`.
- Build e instalação não realizados conforme pedido explícito do usuário; não houve acesso ao perfil de saves instalado.

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
| ML-012 / ML-015 | Cotação clara, custo por kit e consumo só na confirmação da preparação; oficina soma stacks entre tiers, preserva rollback e calcula espaço líquido do resultado | `tests.test_workshop_service`; smoke HTTP regional compara cotação, ouro preservado e kit debitado; portal imediato informa custo em ouro |
| ML-013 | Decisão de manter recompensas Rank E com fluxo inicial suficiente em ouro, sem ignorar custo de materiais | `reports/ml013_early_rank_e_economy_v0.5.0.json` e `.md` (20.000 sequências) |
| ML-014 | Próximo marco apresentado no próximo nível configurado | `test_contract_office_and_scouts_show_the_next_effect_breakpoint` |
| ML-016 | Novas ações CPU têm estágios medidos; saves legados preservam desconhecido em vez de inventar contagens | `test_cpu_action_cadence_is_above_initial_baseline`; `test_seeded_cpu_simulation_100_cycles_and_campaign_isolation`; `test_cpu_stage_counts_remain_unknown_when_upgrading_a_legacy_cycle`; `test_legacy_cpu_report_labels_unmeasured_activity_stages` |
| ML-017 | Preço por espaço e raridade, monotônico no Market 1/100 com tipo/nível/refino comparáveis | `reports/ml017_equipment_price_audit_v0.5.0.json` e `.md`; `tests.test_equipment_pricing` |
| ML-018 | MAX por estoque/cota, bloqueio sem espaço e equipamento único por instância | `tests.test_market_max_quantity` |
| BUG-002 | Resultados regionais renderizam com outcome e oferta registrados; erro de desempacotamento corrigido | `tests.test_desktop_http_smoke`: cria `RegionalRunOutcome` + `RegionalOffer`, abre `/regional/regions/{region_code}` e valida contagens; consulta usa `db.execute(...).all()` |
| BUG-004 | Carne presente/recuperada em catálogo novo e legado; coleta não perde ciclos sem item; diagnóstico de produção registrado | `tests.test_gathering_service`; `tests.test_campaign_content_versioning`; `PACK_VERSION = 5` |

### Reteste após revisão independente

- **Segurança de ML-011/BUG-001:** `start_offer` rejeita nível inferior ao snapshot antes de reservar oferta, inclusive no caminho comum a ofertas de rebelião; serviços de missão e masmorra mantêm validação defensiva. `test_requirement_overrides_remain_defensive_in_services` e o smoke HTTP exercitam o bloqueio sem reserva, o grupo abaixo do snapshot e o início elegível após o template mudar para nível 99 e grupo 1–1.
- **Cristais em contratos:** contratos regionais Rank A/S usam chance rara de 2%/1% e gravam um Cristal no saldo `crystals` e em `crystal_reserve`. `test_regional_run_uses_frozen_duration_chance_and_rewards` força sucesso Rank A, sucesso Rank C e falha Rank A para verificar drop somente no primeiro cenário.
- **Meta finita com Armazém:** `test_finite_assignment_counts_only_stored_units_and_completes_after_capacity_resume` força bônus extra com uma vaga restante, confirma que só a unidade armazenada conta, libera espaço e verifica a conclusão/liberação do mercenário ao encher o Armazém no ciclo final.
- **Comandos/evidências finais:** os testes focados de serviços passaram; `tests.test_gathering_service` passou (9 testes); `tests.test_desktop_http_smoke` passou (1 teste, 65,955 s); `compileall` e `git diff --check` passaram. O smoke HTTP cobre a rejeição sem reserva por nível, os limites de grupo congelados e início após alteração do template.
- **Revisão independente:** CR aprovou tecnicamente o commit `05797a1811a189292c635e1492e7951503f6c855`.
- **Riscos/limitações restantes:** a suíte completa não foi executada; validação visual não foi realizada. Build e instalação também não foram realizados conforme a decisão do usuário.

## Convenção de status

- **Aberta:** registrada, ainda não implementada.
- **Em andamento:** correção em desenvolvimento.
- **Corrigida:** mudança implementada, aguardando validação.
- **Validada:** critérios de aceitação e regressão aprovados.
- **Descartada:** decisão documentada para não implementar.

Ao concluir ou alterar qualquer item, atualizar este documento com evidência, commit/versão quando aplicável e resultado de validação. Não remover itens encerrados; preservar o histórico de status.
