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

### ML-021 — Aumentar a cadência real das guildas CPU na Vigília

- **Origem:** relato do usuário após jogar a versão 0.5.4; no ciclo 15 da região natal houve 2 sucessos e 2 falhas da CPU, enquanto uma única guilda humana com um mercenário consegue fazer 3 a 4 contratos por ciclo.
- **Status:** Validada na estratégia integrada E5, mantendo chance de rebelião em 2% por Vigília elegível. A simulação pareada corrigida registrou rebelião em 15/20 campanhas (19 aberturas), XP líquido CPU de 31.652.945 (+4,42% vs baseline) e sucesso de 65,13% (−7,73 p.p. vs baseline), dentro dos gates documentados. E5 foi aprovada pelo CR em `fd37dc8`; ver `reports/lot_e5_cpu_strategy_event_2026-11-09.md`. As candidatas parciais E1/E4 estão preservadas como histórico; `vigilia-v7` remove o cooldown regional da rolagem sem aumentar a chance, enquanto `vigilia-v6` conserva a regra legada de cinco Vigílias.
- **Problema observado:** a simulação atual permite no máximo 2 ações planejadas para uma guilda CPU forte e apenas 1 para cada guilda média ou nova. A probabilidade por perfil afeta somente a ação adicional da forte; as demais não podem escalar a cadência mesmo quando têm mercenários disponíveis. O relatório também lista guildas de todas as regiões, de modo que o total global não equivale às quatro rivais da região natal.
- **Pedido:** tornar as rivais mais ativas e competitivas, proporcionalmente ao tamanho e disponibilidade de seus elencos, sem monopolizar as dez ofertas da região nem simular ações sem mercenários ou requisitos atendidos.
- **Implementação/evidência:** regras `vigilia-v6` deixam o throughput depender de ofertas elegíveis, elenco e duração, sem teto global/regional/de perfil, e iniciam CPU após a prioridade humana de 1h. A pressão ambiental atual escolhe por risco uma região por janela de 19 Vigílias e aplica recuperação fora da janela; essa janela não foi alterada. Contratos, masmorras, chefes e entradas de portal usam requisitos congelados, equipes ocupadas até o fim da duração e contadores planejado/elegível/iniciado/resolvido por guilda e região. Portal tem ação própria de 25%, cooldown local de 24 Vigílias e prazo offline de 3h; rebelião usa chance de 2% e no máximo uma região selecionada por ciclo, com limite global de evento ativo. `vigilia-v7` usa cooldown regional de rolagem zero; `vigilia-v6` retém cinco Vigílias por compatibilidade. Os resultados parciais do E1/E4 permanecem nos relatórios históricos: E4 teve 6/20 campanhas com rebelião e reduziu sucesso/XP; a estratégia CPU corrigida E5 foi reavaliada sobre 20 campanhas e registrou 15/20 campanhas com rebelião, dentro dos gates de XP e sucesso frente ao baseline. Ver [diagnóstico causal e matriz por Vigília/região](reports/lot_e1_cpu_pressure_2026-11-08.md), [decisão histórica de calibração](reports/lot_e1_calibration_decision_2026-11-08.md) e [simulação pareada E5](reports/lot_e5_cpu_strategy_event_2026-11-09.md). Parâmetros e limites atuais estão em `docs/GDD_EVOLUCAO_GAMEPLAY.md` §14.

### ML-022 — Produzir Kits de Suprimentos em lote com tempo de fabricação

- **Origem:** anotação do usuário e tela de Oficinas enviadas em 2026-11-04.
- **Status:** Implementada e coberta por regressões isoladas no Lote C (`5f783db`, final `074e019`). A fabricação em lote persiste quantidade/custo/prazo, debita uma vez, impede duplicidade e credita a saída após `5 s × quantidade`, com reserva de capacidade. Testes em `tests.test_workshop_service` e `tests.test_material_source_manifest`; revisão de integração final pendente.
- **Situação atual:** a Oficina de Suprimentos permite fabricar apenas um Kit por ação e a fabricação não apresenta o trabalho temporizado solicitado.
- **Pedido:** calcular quantos Kits podem ser feitos com os estoques disponíveis da receita atual (3 Carnes + 2 Ervas por Kit), permitir escolher uma quantidade até esse máximo e concluir a fabricação após 5 segundos por Kit. Exemplo: 10 Kits levam 50 segundos.
- **Critérios para refinamento/implementação:** o máximo deve considerar estoques somados entre tiers e capacidade líquida do Armazém; o servidor deve revalidar ingredientes e quantidade ao iniciar, reservar/debitar materiais uma única vez e impedir produção duplicada ou ganho antecipado. Definir e testar persistência do trabalho em andamento, conclusão após reabrir a campanha, coleta ou entrega do resultado, cancelamento e comportamento quando o Armazém estiver cheio. Mostrar quantidade, custo em materiais, duração e progresso de forma clara na Oficina.

### ML-023 — Remover contadores legados dos cabeçalhos de Missões e Masmorras

- **Origem:** anotação do usuário e capturas dos cabeçalhos enviadas em 2026-11-04.
- **Status:** Validada na `main` pelo commit `9c89f95` (#14); não foi duplicada na integração. `tests.test_stage5_ui_contracts.test_legacy_header_counters_are_removed_and_contextual_actions_remain` cobre a remoção e as ações contextuais.
- **Problema observado:** os cabeçalhos ainda exibem “Opções/Desafios nesta faixa” e “Aguardando coleta”, números vinculados à apresentação anterior e que não ajudam a entender as ofertas da Vigília Regional.
- **Pedido:** remover somente esses contadores dos cabeçalhos de Missões e Masmorras, incluindo Chefes quando apresentados nessa tela. Preservar título, imagem, texto contextual e navegação para ofertas da Vigília.
- **Critério de conclusão:** conferir ambas as telas em campanha nova e existente, sem deixar espaço vazio ou desalinhamento no cabeçalho; não alterar as contagens e estados necessários nas listas, no histórico ou na lógica de coleta.
- **Implementação/evidência:** removidos o bloco `desktop-operations-intro__counts` e o contador “opções nesta faixa” dos cabeçalhos de `app/templates/missions/index.html` e `app/templates/dungeons/index.html`; o cabeçalho desktop passou a uma coluna em `app/static/css/desktop-theme.css`. Títulos, textos contextuais, links da Vigília, filtros, listas, histórico, atalho de recompensas e botões de coleta foram preservados. Sem alteração de regras, banco, migrações, dependências ou outras telas.

## Bugs / Inconsistências

### ML-024 — Permitir cancelar uma venda em andamento no Mercado

- **Origem:** anotação do usuário em 2026-11-05.
- **Status:** Corrigida no Lote B; revisado e aprovado pelo CR no commit `5dacb5c`. Cancelamento atômico, devolução exata e testes em `tests.test_lot_b_materials_market` e `tests.test_desktop_http_smoke`. Commit local: `64f4954a2f32e7e7496926f84e3b75f3ad6ab550`. Achado P2 de CR sobre estimativa após atualização parcial corrigido em `5dacb5ca653d2c2de32e9ced4b7fcdf3ecb32920`; revisão final aprovada pelo CR.
- **Pedido:** oferecer uma ação de cancelar a venda após criar o anúncio, permitindo corrigir quantidade ou desistir da negociação.
- **Critérios para refinamento/implementação:** definir até quando o cancelamento é permitido, devolver exatamente os itens ou a instância anunciada uma única vez, liberar o espaço de venda e não conceder ouro por uma venda cancelada. Validar o estado e a posse da guilda no servidor, inclusive contra cancelamento e coleta simultâneos; exibir uma confirmação clara na interface.

### ML-025 — Documentar no Guia do Jogo as fontes e chances dos materiais e equipamentos

- **Origem:** pedido do usuário após dúvida sobre a origem dos ingredientes mostrados nas Receitas do Ferreiro, em 2026-11-05.
- **Status:** Implementada no Lote D (`029416d`, ajuste final `a818bfc`) com catálogo construído das fontes ativas. Testes verificam fontes, chances e quantidades por conteúdo, itens sem fonte e exclusão de compras que o runtime não consegue alcançar; 58 testes direcionados de integração passaram. Critérios automatizados cobertos; aceite visual manual permanece pendente. Revisão final da integração pendente.
- **Objetivo:** permitir que o jogador descubra onde obter cada ingrediente de receita e quais recompensas possíveis existem em cada atividade, sem precisar adivinhar nem depender de uma lista estática que fique desatualizada após mudanças do Admin.
- **Como receitas escolhem ingredientes hoje:** as receitas iniciais usam ingredientes definidos no código. As receitas geradas podem escolher quaisquer materiais ativos do catálogo com tier menor ou igual ao tier do equipamento produzido; duas matérias-primas são selecionadas por fórmula determinística baseada nos IDs do catálogo/receita. A rotação de receitas muda com o nível do Ferreiro e o ciclo vigente. O catálogo massivo define 447 materiais em 13 famílias: madeira (40), minério (50), pedra (30), couro (35), fibra (35), erva (45), carne (12), essência (40), gema (35), parte de criatura (35), relíquia (40), catalisador (30) e insígnia (20). Assim, a origem não pode ser inferida somente pelo nome ou pela receita exibida.
- **Mapa de fontes identificado no código:**
  - **Coleta contínua:** famílias madeira, minério, couro, essência, gema, erva, relíquia, fibra e carne têm postos. O ciclo-base é 60 segundos, gera uma unidade e pode gerar uma unidade extra pela chance da profissão, limitada a 45 pontos percentuais. O template específico é escolhido pelo nível da guilda entre os materiais ativos da família. Isso não significa que cada variante/tier da família seja selecionável ao mesmo tempo.
  - **Missões:** os drops de material de coleta usam chance-base de 88%. Outros drops de material usam `max(28%, 58% - 3 p.p. por tier)`. A quantidade é definida por faixa de tier. Os templates de drop são associados a materiais por família/faixa e podem mudar por edição administrativa; a chance é por entrada de drop, não uma promessa de obter todo material em toda missão.
  - **Masmorras e chefes:** a chance-base de material segue a faixa: masmorra `62% + 3 p.p. por faixa`, chefe `18 p.p. acima`, limitada a 92%. A quantidade é tier–tier+3 em masmorra e 2×tier–(2×tier+7) em chefe. Cada desafio tem entradas específicas de drop; a tabela precisa mostrar o material efetivamente associado à oferta ativa, não generalizar a fórmula como se todos os materiais caíssem em qualquer desafio.
  - **Docas:** materiais com oferta cadastrada podem ser comprados; isso não é drop e deve ser rotulado como compra. O catálogo-seed atual cria 1.200 associações de oferta usando uma lista de 447 materiais + 1.700 equipamentos; pela fórmula determinística, somente 267 dos 447 materiais recebem associação às Docas nesse seed. A oferta ainda depende do nível mínimo de catálogo, mercante/rotação e estoque; portanto, não se deve afirmar que qualquer material pode ser comprado ou estará presente em toda rotação.
  - **Desmontagem no Ferreiro:** equipamento convertido em um material da família determinada pelo grupo/slot do ícone; o resultado dá RNG de 1–3 unidades por equipamento e é limitado por tier/nível do item. A tabela de compatibilidade cobre madeira, fibra, couro, minério e gema; não cobre todas as 13 famílias. Desmontagem é uma fonte indireta de algumas famílias, não um drop de receita garantido.
  - **Cristais offline:** a recompensa de retorno offline pode conceder 1 Cristal ao completar o teto de 8 horas; não é uma fonte geral para os ingredientes das receitas. A renda passiva atual não deve ser descrita como produção de materiais.
- **Lacunas e cuidado de comunicação:** há 13 famílias elegíveis como ingrediente, 9 famílias com coleta contínua, 5 famílias cobertas pelo mapeamento de desmontagem e cobertura parcial de materiais nas Docas. Missões e masmorras/chefes possuem drops por template, mas a investigação não deve transformar suas fórmulas em afirmação de cobertura garantida para cada um dos 447 itens. A origem e a taxa efetiva de cada item precisam ser cruzadas com os registros ativos da campanha e configurações de Admin; o catálogo pode variar entre campanhas/versões e ser alterado por administradores.
- **Correção de lacuna obrigatória para o DEV nesta entrega:** auditar ingrediente por ingrediente todas as receitas que podem aparecer e garantir que cada material ativo usado por uma receita tenha ao menos uma fonte realmente acessível no jogo. Cobrir todas as famílias e faixas de tier; se as fontes atuais (coleta, drops ou Docas) não cobrirem algum material, criar uma rota de obtenção apropriada, como novos postos/expedições de coleta, drops de atividades ou ofertas de Docas. A decisão de fonte e balanceamento pode variar por família/tier, mas não deixar ingrediente fabricável apenas em teoria, sem origem alcançável. Não basta listar a família: validar o `ItemTemplate` exato, campanha nova e receitas rotativas.
- **Entrega explícita no Guia do Jogo:** criar dentro da tela **Guia do Jogo** uma nova aba/seção própria chamada **Equipamentos e Materiais**. Dentro dela, criar subseções para **Missões**, **Masmorras**, **Chefes**, **Coleta**, **Docas**, **Desmontagem** e outras fontes especiais existentes. Em cada subseção de atividade, listar os itens que aquela fonte/atividade pode conceder e a chance de cada item; também informar quantidade mínima–máxima quando houver. Não basta explicar genericamente que há drops: o jogador deve conseguir consultar qual item pode vir de qual conteúdo e sua taxa.
- **Apresentação e dados da seção:** incluir filtros de família/tipo, tier/faixa e fonte, além de busca pelo nome limpo do item. Mostrar ícone de grupo, nome, raridade/tier quando aplicável, requisitos e natureza da fonte (drop, compra, coleta ou processamento). Para missões, masmorras e chefes, agrupar pelo conteúdo específico que concede o item, sem lista de loot desconectada de sua origem. Docas devem mostrar ofertas/condições como comércio, nunca como drop.
- **Critérios de implementação/aceite:** 1) a nova aba/seção fica acessível dentro do Guia do Jogo e contém as subseções por fonte descritas acima; 2) usar templates e associações efetivamente ativos na campanha, incluindo edições do Admin, sem manter uma segunda tabela de probabilidades hardcoded na interface; 3) em cada missão, masmorra e chefe, exibir os itens possíveis, chance por item e faixa de quantidade exatamente como configuradas/aplicadas no servidor; 4) distinguir chance de obter o item da quantidade sorteada após o drop; 5) representar Docas como estoque/oferta rotativa e informar nível mínimo/estoque quando disponível, sem chamar isso de drop; 6) documentar coleta como ciclo-base e chance de unidade extra separadamente; 7) garantir que todo ingrediente possível das receitas tenha pelo menos uma fonte ativa e alcançável, criando fontes para qualquer lacuna encontrada; 8) sinalizar “sem fonte disponível” como erro de conteúdo e impedir que novas receitas publiquem esse ingrediente até corrigir a origem; 9) respeitar catálogo e isolamento da campanha, sem revelar dados de outras campanhas; 10) validar todas as 13 famílias e faixas de tier, inclusive variantes exatas, receitas rotativas, campanha nova, drops e alterações administrativas, antes de declarar a wiki completa.

### ML-026 — Pesquisar e exportar o Guia do Jogo em Markdown

- **Origem:** solicitação do usuário em 2026-11-05; separada do ML-025 para manter o escopo de fontes e chances de itens independente.
- **Status:** Implementada no Lote D (`029416d`, ajuste final `a818bfc`): busca global normalizada, filtros combinados e Markdown exportado do mesmo conteúdo explicativo e catálogo vivo, sem estado privado da campanha. Testes de rota e frontend passaram (5 de rota/manifesto registrados no checkpoint, 4 de utilitários e integração atual); aceite visual manual permanece pendente. Revisão final da integração pendente.
- **Objetivo:** tornar o Guia do Jogo pesquisável durante a partida e permitir que o jogador baixe uma cópia `.md` atualizada para consultar ou fornecer como fonte a um agente de IA.
- **Busca global:** incluir no Guia um campo de pesquisa que examine o conteúdo completo da tela/guia, não apenas uma aba ou catálogo específico. O jogador confirma por Enter ou pelo botão de busca; o sistema leva à primeira ocorrência encontrada, rola a seção correspondente para a área visível e destaca o texto correspondente sem recarregar a página. A busca deve ignorar diferenças de maiúsculas/minúsculas e espaços excedentes. Sem resultados, exibir uma mensagem clara e manter o Guia utilizável; uma nova busca deve substituir o destaque anterior.
- **Exportação:** disponibilizar no Guia uma ação explícita para baixar a wiki em `.md`, com nome de arquivo claro e conteúdo PT-BR legível fora do jogo. O documento deve identificar versão do jogo e data de geração, incluir o conteúdo explicativo vigente do Guia e, quando aplicável, as informações dinâmicas documentadas em outros MLs (como fontes e chances de obtenção), sem expor saves, dados privados da campanha ou conteúdo exclusivo do Admin.
- **Fonte de verdade:** preferir gerar o arquivo sob demanda a partir da mesma fonte canônica usada para renderizar o Guia, incluindo os dados atuais de gameplay que o Guia apresenta. Não manter um Markdown manual duplicado e independente. Se a implementação exigir Markdown canônico, a tela do Guia e o download devem consumir esse mesmo arquivo, atualizado no mesmo commit de cada mudança documental.
- **Manutenção contínua:** qualquer entrega futura que mude regras, conteúdo, requisitos, recompensas ou fluxos descritos no Guia deve revisar a fonte do `.md` na mesma entrega; quando a mudança não afetar o Guia, registrar essa avaliação no handoff. O processo obrigatório está detalhado em `AGENTS.md`, seção “Guia do Jogo e documentação exportável”.
- **Critérios de implementação/aceite:** 1) buscar uma palavra presente em outra seção/aba do Guia e confirmar por Enter e pelo botão navega até a primeira ocorrência correta, com destaque visível e sem reload; 2) buscas sem correspondência e buscas sucessivas têm estados claros e não deixam destaques obsoletos; 3) o download produz um `.md` válido, abre como texto simples, informa versão/data e corresponde à fonte atual do Guia; 4) conteúdo dinâmico documentado reflete as configurações/catálogo que o jogo efetivamente utiliza, sem duplicar probabilidades em texto hardcoded; 5) testes cobrem codificação PT-BR, navegação por teclado, ausência de resultado, geração/download e sincronização entre Guia e exportação; 6) o CR verifica a fonte única, atualização no mesmo commit e ausência de dados privados no arquivo.

### ML-027 — Calcular o tempo de venda somente por raridade e quantidade

- **Origem:** esclarecimento do usuário sobre a tabela de duração do Mercado, em 2026-11-05.
- **Status:** Corrigida no Lote B; revisado e aprovado pelo CR no commit `5dacb5c`. Duração por raridade × quantidade, com redução existente e piso de 5 s; coberta por `tests.test_lot_b_materials_market` e `tests.test_desktop_http_smoke`. Commit local: `64f4954a2f32e7e7496926f84e3b75f3ad6ab550`. Achado P2 de CR sobre estimativa após atualização parcial corrigido em `5dacb5ca653d2c2de32e9ced4b7fcdf3ecb32920`; revisão final aprovada pelo CR.
- **Problema:** o cálculo atual multiplica a duração-base da raridade pelo campo técnico legado `ItemTemplate.tier` (T1–T8) e pela quantidade. O usuário esclareceu que, nesse contexto, “tier” significa raridade; T1–T8 não deve influenciar a duração nem aparecer na tabela apresentada ao jogador.
- **Regra desejada:** duração-base por unidade, definida exclusivamente pela raridade: Comum 10 s; Incomum 25 s; Raro 60 s; Épico 180 s; Lendário 600 s; Mítico 1.200 s. Duração antes dos bônus = tempo-base da raridade × quantidade anunciada. Em seguida, aplicar a redução de tempo do Mercado já existente e manter o mínimo técnico atual de 5 segundos.
- **Apresentação:** tabela enxuta com as colunas **Raridade** e **Tempo**; não exibir T1, T1–T8, nível interno do item ou qualquer faixa técnica como fator temporal.
- **Critérios de implementação/aceite:** 1) itens de raridades diferentes usam exatamente os tempos-base definidos acima; 2) para a mesma raridade e quantidade, variar `tier`/`item_level` não altera o tempo; 3) quantidade anunciada multiplica o tempo-base antes da redução do Mercado; 4) a redução por nível do Mercado e o mínimo de 5 segundos continuam funcionando; 5) testes cobrem venda de equipamento único e pilha acumulável, incluindo quantidade maior que 1 e raridades Comum a Mítico; 6) tabela/UI comunica apenas Raridade e Tempo e não contradiz o cálculo do servidor.

### ML-028 — Notificar eventos regionais com pop-ups temáticos e animados

- **Origem:** solicitação do usuário em 2026-11-06 após observar uma rebelião sem ação de aceite visível.
- **Status:** Implementado em desktop; testes de markup/rota/estado aprovados. A inspeção visual final do aplicativo fica pendente para o aceite do usuário.
- **Objetivo:** ao entrar na Vigília Regional, chamar a atenção para eventos ativos ainda sem ação da guilda, usando os materiais visuais específicos de portais e rebeliões já criados pela DA. A comunicação atual em cards não aproveita essas artes nem destaca suficientemente eventos com prazo.
- **Rebelião:** exibir um pop-up temático com animação/arte da rebelião enquanto o convite ainda estiver pendente. Oferecer **Aceitar convite** e **Delegar à CPU**, informar o prazo restante da prioridade de 1h e explicar de forma breve a janela de atividade de 12h. Fechar o pop-up não deve equivaler a aceitar ou delegar; o convite continua acessível na Vigília e pode reaparecer na próxima entrada enquanto estiver pendente.
- **Portal:** não criar um passo de aceite/delegação. O fluxo atual é entrada direta com **Enviar equipe**, limitada a uma entrada por guilda. O pop-up deve apresentar o chefe/desafio, o prazo de entrada e um CTA para ver/preparar a equipe na Vigília. Fechar o pop-up não consome a entrada; pode reaparecer na próxima entrada enquanto o portal estiver aberto e a guilda ainda não tiver participado.
- **Direção de arte:** reutilizar as artes específicas de portal e rebelião entregues pela DA, com animação leve e coerente com a identidade visual; não substituir a arte por modal genérico. Preservar estados de movimento reduzido e não bloquear o acesso ao restante do jogo depois de fechar o aviso.
- **Critérios de implementação/aceite:** 1) pop-up aparece ao entrar na Vigília quando há portal aberto sem entrada ou convite de rebelião pendente; 2) cada tipo usa a arte correta e tem animação temática; 3) ações e prazos correspondem ao estado do evento; 4) fechar o pop-up não registra participação, recusa nem entrada; 5) evento continua acessível no painel persistente da Vigília; 6) convite respondido, portal expirado ou portal já utilizado não volta a ser anunciado como pendente; 7) teclado, foco, leitor de tela, movimento reduzido e telas menores permanecem utilizáveis; 8) testes cobrem entrada, fechamento sem ação, reabertura, decisão/entrada, expiração e isolamento entre campanhas.
- **Implementação/evidência:** `app/core/dependencies.py` expõe apenas convite de rebelião ainda `invited` e portal ativo sem participante; `base.html` apresenta cada aviso somente em `/regional`, com as cenas/emblemas fornecidos pela DA. Fechar usa `method=dialog` e não grava estado; ao voltar à Vigília, o aviso elegível reaparece. `evolution-dialogs.js` enfileira avisos depois do resumo offline e ordena prazos iguais por vencimento; o CSS inclui entrada curta e movimento reduzido. A navegação parcial sincroniza os diálogos novos. O smoke HTTP verifica pendente, aceito, portal disponível/usado/expirado e os CTAs; teste estrutural cobre fila, imagens e acessibilidade. A validação visual em janela do aplicativo permanece para aceite do usuário.

### ML-029 — Balancear poder recomendado de missões pela progressão e pelo Rank

- **Origem:** solicitação do usuário em 2026-11-06; uma missão Rank C de nível recomendado 18 exibia poder recomendado 49 e grupo 1–2, enquanto mercenários Comuns de nível 10–12 já apresentavam poder total 52–89. A missão podia ser enfrentada por um único mercenário muito acima do recomendado, e a chance chegava ao teto de 95%, tornando o suprimento sem efeito.
- **Status:** Implementada e calibrada em E2, preservada na integração E5. O relatório pareado corrigido atende aos gates de XP e sucesso CPU; a fórmula limita-se a snapshots de novas ofertas regionais de combate. E5 foi aprovada pelo CR em `fd37dc8`; a revisão final deste hash de integração ainda está pendente. Ver estudo reproduzível e calibração final em `reports/lot_e2_ml029_balance_study_2026-11-08.md` e `reports/lot_e5_cpu_strategy_event_2026-11-09.md`.
- **Objetivo:** criar uma referência reproduzível da progressão de poder de um mercenário Comum e usar essa curva para tornar o poder recomendado coerente com o nível, o Rank da missão e o tamanho máximo do grupo.
- **Curva de referência:** identificar no código o maior conjunto de atributos permitido para um mercenário Comum recém-contratado no nível 1 (o valor 15 mencionado pelo usuário é uma hipótese a confirmar, não uma constante presumida). Simular os ganhos reais de atributos e o cálculo atual de poder do nível 1 ao 350, sem equipamento, profissão, bônus temporários ou outras fontes externas. Registrar poder e atributos em cada nível e explicitar como classe/evolução afeta ou não essa referência; não simplificar a curva para uma fórmula linear se a progressão real tiver marcos ou bônus.
- **Fórmula candidata para poder recomendado:** `poder_recomendado = poder_Comum_no_nível_recomendado × multiplicador_do_Rank × tamanho_máximo_do_grupo`. O grupo 1–2 usa fator 2, conforme a intenção do usuário de dimensionar o desafio pelo grupo máximo anunciado. Arredondamento, limites mínimos e exceções devem ser definidos e testados com a curva real.
- **Multiplicadores iniciais para simulação, não aprovados como balanceamento final:** Rank E `1,00`; D `1,15`; C `1,30`; B `1,50`; A `1,75`; S `2,00`. Comparar alternativas por simulação antes de escolher os valores definitivos, mantendo progressão monotônica entre Ranks e evitando que a curva torne conteúdo impossível ou trivial.
- **Escopo de aplicação:** avaliar primeiro contratos de combate Rank E–S. Não aplicar automaticamente a coleta, missões de chance fixa/longa, masmorras ou chefes: medir cada família separadamente e registrar a decisão para evitar que regras de desafio incompatíveis sejam alteradas em conjunto.
- **Interação com chance e suprimentos:** simular poder individual e total do grupo contra o poder recomendado, a chance-base, o bônus de Rank/classe/raridade/habilidades/equipamentos e o teto de chance. Confirmar que equipes abaixo do tamanho máximo não atinjam o teto trivialmente e que suprimentos possam ter efeito real quando a chance ainda não estiver limitada; não mudar o bônus/custo dos suprimentos sem evidência de que a nova curva exige isso.
- **Compatibilidade:** respeitar requisitos de nível, guilda e tamanho de grupo já configurados pelo admin. Não sobrescrever ajustes administrativos por seeds. Ofertas regionais já geradas devem manter seus snapshots e campanhas existentes não devem ter seus desafios em andamento recalculados; definir como novos valores passam a valer para novas ofertas e, se necessário, uma migração explícita e segura para conteúdo futuro.
- **Critérios de implementação/aceite:** 1) relatório reproduzível com atributos e poder Comum para todos os níveis 1–350; 2) simulações cobrindo Ranks E–S, níveis inicial/intermediário/final e tamanhos mínimo/máximo de grupo; 3) poder recomendado cresce monotonicamente com nível, Rank e tamanho máximo do grupo; 4) comparação documentada entre poder atual e candidato, incluindo o caso Rank C, nível 18, grupo 1–2; 5) análise de chance para solo e grupo completo, com e sem suprimento, demonstrando risco adequado sem cap trivial; 6) testes verificam fórmula, arredondamento, exceções, snapshots e preservação de configurações do admin; 7) revisão de balanceamento registra os valores finais e as limitações conhecidas antes de publicar.

### ML-030 — Padronizar os bônus de equipamentos por raridade

- **Origem:** solicitação do usuário em 2026-11-08 após observar equipamentos Comuns com mais bônus que equipamentos Incomuns; o mesmo tipo de inversão pode ocorrer entre raridades superiores.
- **Status:** Implementada em E3 (`e256bb6`) com correção de compatibilidade de slots em `804106c`. A auditoria reporta 1.706 templates e zero inversões nos 195 pares comparáveis após a correção; a suíte focal ML-030 passou. A inspeção visual final e a revisão da integração permanecem pendentes. Ver `reports/lot_e3_ml030_checkpoint_2026-11-09.md`.
- **Objetivo:** auditar todos os bônus de equipamentos e fechar a geração aleatória por raridade, para que raridades superiores tenham mais variedade de atributos e valores maiores, eliminando inversões injustificadas entre itens comparáveis.
- **Faixas desejadas por equipamento:**

  | Raridade | Quantidade de tipos de bônus distintos | Pontos por bônus normal sorteado |
  | --- | ---: | ---: |
  | Comum | 1–2 | 1–2 |
  | Incomum | 2–3 | 2–3 |
  | Raro | 3–4 | 3–4 |
  | Épico | 4–5 | 4–5 |
  | Lendário | 5–7 | 5–7 |
  | Mítico | 8–10 | 8–10 |

- **Interpretação da faixa:** o intervalo controla o total de tipos de bônus distintos no item, contando os tipos FORTE dentro desse total, não além dele. Cada bônus normal usa a faixa de pontos da raridade; cada bônus FORTE usa a faixa especial de 10–20. Um mesmo tipo não conta duas vezes como variedade; bônus devem ser persistidos e exibidos explicitamente, sem duplicatas ocultas.
- **Bônus FORTE:** existem quatro tipos especiais, `FORTE FOR`, `FORTE VIT`, `FORTE AGI` e `FORTE INT`. Cada um acrescenta pontos ao atributo principal correspondente, além do bônus normal: por exemplo, `FOR +8` junto de `FORTE FOR +15` concede `+23 FOR` no total. FORTE só pode aparecer a partir da raridade Lendário e cada bônus FORTE sorteado começa com faixa de **10–20 pontos**; essa faixa é provisória para testes e poderá ser rebalanceada.
- **Garantias de FORTE:** um Lendário com a quantidade máxima de 7 tipos de bônus deve ter pelo menos 1 tipo FORTE. Todo Mítico deve ter pelo menos 2 tipos FORTE; se vier com os 10 tipos de bônus, deve conter os quatro tipos FORTE. Exemplos de distribuição ou valores não substituem essas garantias.
- **Apresentação:** destacar cada bônus FORTE com badge de cor própria e estrela no card/detalhe do item, mantendo a borda e a badge de raridade originais. O Guia do Jogo deve explicar o que significa FORTE, quais raridades podem recebê-lo e como ele se soma ao atributo normal.
- **Auditoria obrigatória:** mapear bônus-base dos templates, bônus RNG da instância e qualquer outra origem de atributo em sementes, catálogo, admin, criação de equipamento, drops de missão/masmorra/chefe, Docas, Taverna, conquistas, fabricação e refino. Identificar todos os caminhos de criação e garantir que a raridade governe os limites de geração em cada caminho aplicável, sem rerrolar RNG ao renderizar, equipar ou desequipar.
- **Comparação justa:** construir verificações para itens comparáveis por nível mínimo, slot/tipo e refino. Medir quantidade de atributos positivos, pontos totais e poder efetivo segundo a fórmula de combate. O RNG ainda pode criar variação dentro da mesma raridade, mas não deve permitir que um item de raridade inferior ultrapasse a faixa de bônus da raridade imediatamente superior em comparações equivalentes; se as faixas propostas permitirem sobreposição, definir uma regra determinística de piso/teto ou rerrolagem e demonstrá-la por simulação.
- **Compatibilidade técnica:** o domínio atual possui seis bônus normais (`power`, `vitality`, `agility`, `intelligence`, `luck` e `armor`); os quatro tipos FORTE completam o conjunto de dez tipos distintos exigido pelas faixas superiores. FORTE não é um novo atributo de combate separado: soma ao atributo principal correspondente. A implementação deve persistir múltiplos bônus por instância (o modelo atual de um único bônus RNG pode não bastar), calcular o total efetivo sem duplicar aplicação e manter compatibilidade de saves; escolher o formato/modelo de persistência após inspecionar o schema e criar migração somente se necessária.
- **Compatibilidade e integridade:** preservar bônus e RNG já gravados nas instâncias existentes; não recalcular equipamentos de campanhas/saves existentes. Mudanças em templates devem afetar apenas novas instâncias, salvo plano explícito e reversível aprovado. Preservar edições administrativas e não sobrescrevê-las por seeds. Atualizar o Guia do Jogo na mesma entrega para explicar FORTE.
- **Critérios de implementação/aceite:** 1) inventário completo dos caminhos de bônus e resultados da auditoria registrados; 2) testes provam quantidade de tipos distintos, garantias FORTE e faixas de pontos por raridade; 3) simulações cobrem slots/tipos, níveis e raridades Comum a Mítico, sem inversão de faixa entre itens comparáveis; 4) bônus FORTE são persistidos, exibidos, somados ao atributo correspondente e considerados no poder exatamente uma vez; 5) Guia do Jogo documenta FORTE e está sincronizado com a interface; 6) RNG da instância é gerado uma vez e permanece estável em renderização/equipar/desequipar; 7) equipamentos já existentes, saves e ajustes de admin permanecem intactos; 8) testes cobrem drops, fabricação/refino e demais fontes aplicáveis; 9) revisão de balanceamento documenta distribuição, extremos, exceções e limitações antes da publicação.

### BUG-001 — Requisitos da oferta regional não são aplicados a partir do snapshot

- **Origem:** evidência encontrada ao investigar as anotações 10 e 11.
- **Status:** Validado e revisado pelo CR no commit `05797a1`; testes de serviço/rota cobrem grupo e nível da guilda congelados na oferta e validação sem reserva. O hash está incluído nesta linha de integração.
- **Problema:** cada `RegionalOffer` congela mínimo/máximo de grupo, mas o início da execução delega para `start_mission()`, que consulta os requisitos atuais do `MissionTemplate`. O nível mínimo da guilda nem sequer tem campo snapshot na oferta e também é lido do template ativo.
- **Consequência:** se um admin alterar esses requisitos durante uma Vigília, uma oferta já criada pode ser exibida/interpretada segundo os requisitos antigos, mas iniciar segundo os novos. Além de causar mensagens inesperadas, isso contradiz a persistência do snapshot de grupo da oferta.
- **Evidência:** `app/models/regional.py` (`RegionalOffer.min_party_size_snapshot` e `max_party_size_snapshot`); `app/services/regional_cycle_service.py` (`_add_offer`); `app/routes/regional_routes.py` (`start_offer` chama `start_mission`); `app/services/mission_service.py` (`validate_mission_requirements` e validação de `min_party_size`/`max_party_size`).
- **Validação:** testes de serviço/rota aprovados: alterar requisitos do template depois da oferta e iniciar usando os valores congelados.

### BUG-002 — Atividades da guilda retornam erro interno sem registro útil no log

- **Origem:** relato do usuário e captura de tela enviados em 2026-11-02.
- **Status:** Corrigida e validada; cenário reproduzido com dados descartáveis, e a rota renderiza o resultado após a correção. Evidência executável permanece no smoke HTTP desktop; sem atribuir a este item o hash de correção de BUG-004.
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
- **Status:** Correção e regressão isolada implementadas em `33f47a2`; o fluxo usa handoff serializado e regressão simulada no launcher. Nenhuma instalação real ou validação final do Setup foi realizada nesta rodada; portanto, não marcar como validada em execução real.
- **Evidência:** `desktop.log` contém somente o encerramento do Uvicorn; nenhuma etapa do launcher ou do processo auxiliar é registrada. A captura confirma que a versão 0.5.0 foi validada e que a ação de instalação foi confirmada.
- **Comportamento confirmado no código:** o launcher dispara um PowerShell oculto para aguardar o PID do jogo e executar o Setup. O PowerShell espera indefinidamente (`WaitForExit()` sem limite), não registra o progresso em arquivo e só apresenta erro quando captura uma exceção; a limpeza pode apagar o staging após um retorno não zero do instalador.
- **Critérios para correção:** limitar a espera pelo processo do jogo e fornecer diagnóstico explícito caso não encerre; registrar a requisição/fechamento em `desktop.log` e o início do helper, PID, início/fim do Setup, código de saída e stdout/stderr em `%LOCALAPPDATA%\GuildIdleManager\logs\update-handoff.log`; preservar o Setup e staging em qualquer falha ou retorno não zero; cobrir os caminhos de sucesso, timeout e erro em testes.
- **Nota de distribuição:** a instalação 0.4.1 não pode corrigir a si própria se o próprio handoff não inicia o Setup. Depois da correção, poderá ser necessário instalar manualmente uma primeira versão corrigida; isso deve ser explicado ao usuário se confirmado.
- **Correção/evidência desta rodada:** o helper usa um bloqueio exclusivo no staging do Setup para impedir dois handoffs concorrentes de abrir o mesmo arquivo; um helper duplicado registra o motivo e encerra sem iniciar outra cópia. `tests.test_desktop_launcher.DesktopLauncherUnitTests.test_verified_update_handoff_logs_helper_and_preserves_failed_setup` executa helpers simultâneos com um Setup falso que retorna erro, confirma uma única abertura, registro do duplicado e preservação do pacote. Nenhum instalador ou perfil de usuário foi usado.

### BUG-004 — Coleta de Carne pode consumir ciclos sem produzir item quando falta template ativo

- **Origem:** relato do usuário de que a coleta de Carne não aparece no inventário; imagem de inventário enviada em 2026-11-02.
- **Status:** Corrigida e aprovada pelo CR no commit `5ba0c43`; testes direcionados de coleta e versionamento cobrem catálogo novo/legado e capacidade. A causa específica no save do usuário não foi confirmada e nenhum save real foi consultado.
- **Evidência:** inventário mostra Armazém em `435 / 1540`, portanto não estava cheio, e não lista Carne. O log anterior registra requisições/redirects, mas não a família coletada nem unidades produzidas/armazenadas.
- **Falha confirmada no código:** `advance_assignment()` avançava o checkpoint mesmo quando `_material_template()` não encontrava item ativo daquela família, descartando o tempo acumulado sem erro ou aviso. Campanhas com marcador do catálogo já aplicado também não reparavam templates materiais ausentes.
- **Correção:** catálogo elevado para versão 5 e materiais gerados são reconciliados aditivamente antes do retorno por marcador, sem sobrescrever templates existentes; coleta impede nova designação sem item ativo, preserva o checkpoint de designações antigas e mostra aviso se o catálogo estiver incompleto.
- **Diagnóstico adicionado:** `gameplay-actions.log` registra família, ciclos, unidades produzidas/armazenadas/descartadas, ocupação do Armazém e rejeições/liberações de coleta.
- **Regressões:** `tests.test_gathering_service` verifica coleta de Carne, rejeição sem template e preservação do ciclo; `tests.test_campaign_content_versioning` verifica Carne em campanha nova e reparo aditivo de campanha legada preservando o item customizado.
- **Risco residual:** necessário confirmar em versão atualizada que a campanha afetada recebe Carne e que um ciclo aparece no inventário; nenhum save real foi aberto ou alterado durante a correção.
- **Ajuste após revisão CR:** na migração de campanha antiga, reativar somente `material_meat_1_001` quando ele ainda for o material canônico do pacote; preservar campos customizados e os demais materiais desativados. A rota `/regional` agora usa o mesmo registrador de produção da rota `/gathering`, com família, ciclos, quantidades, capacidade e estado; o smoke verifica uma única linha para o avanço regional. O CR aprovou o commit `5ba0c438c785ad489a8e58c86105edd3b8072af4`, sem achados acionáveis.

### BUG-005 — Comparativo regional não acompanha as atividades das guildas

- **Origem:** relato do usuário e captura da tabela da região enviados em 2026-11-04.
- **Status:** Implementado no commit `c1ddfed`; smoke HTTP local cobre guilda do jogador/CPU, atualização após mudança persistida e isolamento entre campanhas descartáveis.
- **Problema observado:** patrimônio, elenco e contadores de Contratos, Masmorras, Chefes, sucessos e falhas parecem parados na tela de atividades das guildas, mesmo quando as rivais atuam em novas Vigílias. A tela também não atualiza os valores enquanto permanece aberta.
- **Causa técnica preliminar:** `app/routes/regional_routes.py` monta `results_by_state` exclusivamente a partir de `RegionalRunOutcome`, mas a simulação das guildas CPU persiste suas ações em `RegionalCpuCyclePlan` (`outcomes_json`, `successes`, `failures`). Assim, os resultados CPU são apresentados como zero apesar de haver ações resolvidas. O template `app/templates/regional/detail.html` renderiza um snapshot no GET e não dispõe de atualização periódica. Os demais valores precisam ser auditados para distinguir atualização no fechamento da Vigília de atualização contínua legítima.
- **Critérios de conclusão:** consolidar as atividades CPU e da guilda do jogador pelas fontes corretas, sem duplicação; contar Contratos, Masmorras e Chefes conforme o tipo efetivamente resolvido; preservar separação por campanha e região e representar ciclos legados sem inventar dados. Atualizar a tabela sem recarga completa da página, com intervalo moderado e sem sobrescrever o estado de navegação, mantendo o servidor como fonte de verdade. Testar uma campanha em que a CPU conclui atividades, a guilda do jogador conclui uma atividade, a página permanece aberta durante mudança de estado e outra campanha não vê esses números.
- **Implementação/evidência:** `app/routes/regional_routes.py` consolida `RegionalRunOutcome` da campanha/região e `RegionalCpuCyclePlan.outcomes_json` das guildas CPU, valida o tipo da oferta e exclui tipos desconhecidos/portal da classificação. Para planos legados sem detalhe, mantém apenas sucessos/falhas agregados, sem inventar categoria. `/regional/regions/{region_code}/comparison` publica os valores atuais; `app/static/js/main.js` atualiza a tabela a cada 30 s, apenas com a página visível, sem reload completo. `tests.test_desktop_http_smoke` valida CPU/jogador, atualização da resposta após mutação persistida e isolamento de campanha.

### BUG-006 — Ícones somem após ações que recarregam a tela

- **Origem:** anotação do usuário em 2026-11-05; observado em Construções ao comprar ou evoluir um prédio, com possível ocorrência em outras telas como Inventário.
- **Status:** Correção integrada no Lote A (`0c8f403`, ajuste `c1dc871`), com reaplicação idempotente dos ícones em navegação parcial; regressão `tests.test_desktop_art` passou. Lote A aprovado pelo CR; inspeção visual manual final não foi reivindicada nesta matriz.
- **Problema observado:** os ícones não relacionados às imagens dos itens aparecem na primeira entrada da tela, mas desaparecem após uma ação que atualiza ou recarrega o conteúdo.
- **Critérios de investigação/conclusão:** reproduzir compra/evolução em Construções e ações equivalentes nas demais telas, identificar se o problema é caminho de asset, inicialização de componente ou substituição parcial do DOM; garantir que os mesmos ícones carreguem na entrada inicial e após cada ação, sem alterar os ícones dos itens que já funcionam.
- **Causa e correção:** `replaceGameContent()` substituía `.game-shell` sem reaplicar `desktop-art.js`; `applyDesktopArt(root)` agora pode reaplicar arte de forma idempotente ao conteúdo recém-substituído. A reaplicação preserva o guard contra duplicação e ocorre depois da troca de rota. Coberto por `tests.test_desktop_art`.

### BUG-007 — Convite de rebelião pode não exibir ações de resposta

- **Origem:** relato do usuário em 2026-11-06, após uma rebelião surgir sem botão de aceite visível.
- **Status:** Implementado em campanha descartável no Lote A (`0c8f403`, ajuste `c1dc871`); testes de rota/estado e `tests.test_desktop_art` cobrem convite pendente/respondido, portal disponível/usado/expirado e reapresentação na Vigília. Lote A aprovado pelo CR; nenhum save real foi lido ou alterado.
- **Comportamento esperado:** enquanto o evento estiver ativo e o convite estiver pendente dentro da prioridade de 1h, a Vigília deve exibir **Aceitar convite** e **Delegar à CPU**. A falta de ofertas livres pode ocultar as atividades da rebelião, mas não deve ocultar essas ações de decisão.
- **Condição atual no código:** `app/templates/regional/index.html` renderiza os botões apenas quando o evento está `active` e não existe participante ou o participante está `invited`. `expire_due_events()` em `app/services/regional_event_service.py` delega automaticamente à CPU quando a prioridade termina sem resposta, altera o participante para `declined` e, corretamente, não oferece mais aceite. O middleware só abre o pop-up automático enquanto encontra participante `invited`.
- **Investigação necessária:** verificar, em campanha descartável, se o evento recém-criado recebe participante `invited`, se a prioridade ainda está vigente e se a rota `/regional` apresenta ambos os botões. Cobrir também convite expirado/auto-delegado, já aceito, explicitamente delegado, evento resolvido e ausência de `RegionalGuildState`. Não ler nem alterar o save real do usuário.
- **Auditoria de portais:** portal não tem aceite/delegação segundo as regras atuais; a ação é **Enviar equipe**, uma entrada por guilda. `app/templates/regional/index.html` mostra esse formulário para portal ativo, ainda não utilizado e com template disponível; `app/routes/regional_routes.py` valida evento ativo, região natal, template e entrada única antes de iniciar a expedição. Isso não caracteriza falta de botão de aceite; a melhoria ML-028 cobre o aviso temático que conduz à ação direta.
- **Critérios de conclusão:** identificar e corrigir por que a ação de convite não aparece no estado pendente; garantir que aceite/delegação sejam submetidos e persistidos uma única vez; explicar claramente quando o convite já expirou ou foi respondido; manter o fluxo direto de portal sem introduzir aceite não especificado; adicionar regressões de rota/template para os estados pendente, respondido, expirado e portal não utilizado/já utilizado.
- **Implementação/evidência:** convite `invited` em `/regional` mostra os dois formulários persistentes de decisão e o aviso pode ser dispensado sem POST; aceite é persistido pela rota existente e o convite deixa de ser anunciado. Portal aberto sem participante recebe aviso com CTA para a Vigília; participante existente ou evento expirado não recebe aviso. `tests.test_desktop_http_smoke` e `tests.test_regional_event_service` cobrem esses fluxos, sem acrescentar regras de entrada.

### BUG-008 — Coleta desbloqueia materiais e raridades fora da progressão esperada

- **Origem:** relato do usuário em 2026-11-06: ao chegar à guilda nível 7, a coleta passou de Madeira Bruta para Madeira Arcana e de minério comum para Minério de Mithril incomum.
- **Status:** Corrigida no Lote B; revisado e aprovado pelo CR no commit `5dacb5c`. Seed versionado, progressão por família, alvo de coleta persistido e migração compatível; coberta por `tests.test_lot_b_materials_market` e `tests.test_desktop_http_smoke`. Commit local: `64f4954a2f32e7e7496926f84e3b75f3ad6ab550`. Achado P2 de CR sobre estimativa após atualização parcial corrigido em `5dacb5ca653d2c2de32e9ced4b7fcdf3ecb32920`; revisão final aprovada pelo CR.
- **Comportamento atual:** `app/services/gathering_service.py::_material_template()` seleciona, a cada avanço da coleta, o material ativo da família cujo `item_level` seja menor ou igual ao nível da guilda, priorizando o maior `item_level`. O item de saída não é congelado quando o trabalhador é designado, então uma mudança de nível pode mudar o material produzido por uma coleta já em andamento.
- **Causa confirmada no catálogo gerado:** `app/seeds/massive_content.py::_material_rows()` deriva o nome/variante por `local_index // len(BANDS)`, mas deriva faixa, tier e `item_level` por `_band_for_index(local_index)` e pelo resto do próprio índice. Com isso, registros de variantes semanticamente avançadas podem receber níveis iniciais: por exemplo, os registros gerados `Madeira Arcana 1-25` e `Minério de Mithril 1-25` recebem `item_level` 5 e tier 1. O seletor passa a aceitá-los para guilda nível 5 ou superior, mesmo que o nome sugira progressão posterior. A raridade também é determinada pela posição global do registro (`_rarity(global_index)`), não por uma curva de desbloqueio coerente com a família; o exemplo de Mithril pode resultar incomum enquanto materiais vizinhos da mesma faixa têm raridades diferentes.
- **Impacto principal observado:** o problema não é simplesmente o ouro unitário maior, que o usuário não considera prejudicial. O salto de raridade antecipa o tempo longo de venda no Mercado durante o early game. Na captura, 500 unidades de Madeira Arcana a 4 ouro/unidade totalizam 2.000 ouro, mas ficam anunciadas por cerca de 8h20. O cálculo atual usa `raridade × tier × quantidade` (`app/services/market_service.py::_sale_duration_seconds()`); 500 unidades Raras a 60 s/unidade e tier 1 correspondem a 30.000 s, antes das reduções. A regra futura de tempo por raridade/quantidade está especificada separadamente em ML-027; corrigir este bug não deve alterar preços ou tempos de raridade por inferência.
- **Regra desejada:** a progressão de materiais coletáveis deve ser explícita e coerente: nível/faixa de desbloqueio, família, nome, tier técnico e raridade não podem divergir por posição incidental no gerador. Guilda nível 7 não deve receber automaticamente uma variante avançada ou rara apenas porque um registro mal classificado tem `item_level` baixo. A raridade deve seguir uma distribuição/progressão deliberada e documentada, não a ordem global de inserção.
- **Estabilidade da coleta:** ao designar um trabalhador, o material-alvo deve permanecer estável durante aquela designação; subir o nível da guilda não deve trocar silenciosamente o item que será produzido. Uma mudança de alvo deve ocorrer apenas ao liberar e designar novamente, ou por uma regra explícita equivalente, compatível com campanhas existentes.
- **Compatibilidade e preservação:** corrigir o mapeamento sem apagar inventário, histórico, templates editados pelo Admin ou materiais de campanhas existentes. Se for necessário persistir o template-alvo da designação, planejar migration aditiva e preservar atribuições ativas; não reescrever quantidades nem converter itens já armazenados.
- **Critérios de conclusão:** 1) documentar uma matriz de desbloqueio por nível/faixa para madeira, minério e demais famílias coletáveis, com nome, raridade e item level coerentes; 2) guilda nível 7 e outros marcos de progressão selecionam o material esperado, sem saltar para uma variante avançada por causa do índice do seed; 3) raridade segue a curva aprovada e não depende da posição global incidental; 4) coleta em andamento mantém o material-alvo ao evoluir a guilda; 5) coletar e vender materiais não muda seu valor ou duração fora das regras explicitamente aprovadas em ML-027; 6) seeds/migrações são idempotentes e preservam customizações administrativas, inventário, históricos e campanhas existentes; 7) testes cobrem catálogo novo, catálogo legado, limites de desbloqueio, mudança de nível durante coleta, raridade e compatibilidade de dados.

## Validação desta rodada

- Integração local dos lotes aprovados: branch `integration/approved-lots-2026-11-09`, baseada em E5 `fd37dc8aa79806108b252cf0fda78b8598515be3`; A/B/C/D/E1/E3/E4 são ancestrais, ML-023 já está em `main` (`9c89f95`) e não foi duplicada. A matriz atualizada item a item, commits-fonte e limites visuais está em `reports/integration_approved_lots_2026-11-09.md`. Testes focados: 58/58; interface: 19/19; arte desktop: 26/26; smoke HTTP: 1/1; frontend Guia: 4/4. Suíte ampla interrompida após 300 s ainda executando testes/migrações em SQLite temporário, sem resultado final conclusivo. Nenhuma build, instalação, push, PR ou merge foi feita.
- Reteste após CR do candidato `1195125c`: corrigida a descrição do cooldown regional de rebelião e a regressão do smoke que restringia indevidamente atributos duplicados entre bônus normais e FORTE; `tests.test_ml030_equipment_bonus_rules`, `tests.test_regional_cycle_service` e `tests.test_stage5_ui_contracts` passaram (39/39), os testes direcionados do cooldown atual/legado passaram (2/2), e `tests.test_desktop_http_smoke` passou (1/1). Logs dos retestes estão no relatório da integração. A revisão final do novo hash segue pendente.

- BUG-004: `tests.test_gathering_service` + `tests.test_campaign_content_versioning` passaram (14 testes); `compileall` e `git diff --check` passaram. A suíte completa não foi executada.

- Regras de design confirmadas: chance de rebelião de 2% por Vigília elegível; prazos de portal avançam durante catch-up offline.
- Testes direcionados de oficina, coleta/couro+carne, preços, suprimento, marcos de construção e MAX do Mercado: aprovados (27 testes antes da cobertura extra de equipamento único).
- `tests.test_stage5_ui_contracts` + `tests.test_stage5_runtime_validation`: aprovados (33 testes no conjunto).
- Retestes direcionados de `tests.test_regional_cycle_service`, `tests.test_campaign_service` e `tests.test_campaign_content_versioning`: simulação de 100 Vigílias e migração de saves cobertas; cinco testes de migração/campanha, quatro testes de descoberta/compatibilidade e dois casos regionais anteriormente divergentes aprovados após atualizar as expectativas do head e permitir que probabilidade zero desative ações CPU. `test_cpu_stage_counts_remain_unknown_when_upgrading_a_legacy_cycle` confirma estágios `NULL` após migração, e `test_legacy_cpu_report_labels_unmeasured_activity_stages` verifica a apresentação “não registrado”.
- `tests.test_desktop_http_smoke`: página e mutações HTTP desktop aprovadas após ajustar fixtures de inventário sem duplicar linhas; inclui regressão de log/erro GET, renderização de outcome na rota regional, oficinas, cotação e débito regional.
- BUG-004/diagnóstico regional: `tests.test_campaign_content_versioning` (3 testes), `tests.test_gathering_service` (12 testes) e `tests.test_desktop_http_smoke` (1 teste) passaram em SQLite isolado; o smoke confirmou exatamente um registro de produção para o avanço via `/regional`. `compileall` e `git diff --check` passaram. Reteste independente CR aprovado no commit `5ba0c438c785ad489a8e58c86105edd3b8072af4`, sem achados acionáveis. Nenhuma build/instalação foi feita.
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
