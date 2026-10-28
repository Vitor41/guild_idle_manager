# GDD — Evolução da Gameplay do Guild Idle Manager

**Estado:** proposta de produto e especificação de evolução; não autoriza implementação por si só.  
**Base auditada:** checkout desktop `App GIM`, branch `main`, em 27/10/2026.  
**Plataforma-alvo:** campanha single-player offline para Windows, conforme `docs/GDD_DESKTOP_OFFLINE.md`.  
**Marco prioritário:** campanha jogável e balanceada até mercenários nível 50.  
**Classificação:** Confirmada = decisão estabelecida; Proposta = desenho recomendado; Hipótese de balanceamento = precisa de simulação; Expansão futura = não entra no primeiro corte; Dependência técnica = precisa de decisão/implementação prévia.

> Esta auditoria não alterou código, saves, banco, migrations, relatórios existentes ou os GDD originais. Este arquivo é a única entrega persistente desta etapa. Fórmulas apresentadas como atuais foram conferidas nos módulos citados; números históricos de relatórios não são tratados como resultados atuais certificados.

## 1. Resumo executivo e visão do produto

O Guild Idle Manager já tem uma base ampla de RPG de gestão: campanha local, guilda, mercenários, progressão, classes, profissões, construções, contratos/missões temporizadas, coleta por missão, masmorras, chefes, equipamentos, crafting, refino, desmontagem, mercado, taverna, docas, skills, conquistas e Codex. O gargalo de experiência não é falta de sistemas; é que a maior parte do jogo se organiza em iniciar repetidamente uma atividade temporizada, esperar, coletar e repetir. Há sistemas com pouca interação entre si, um catálogo muito grande e materiais cujo propósito não está sempre evidente.

**Visão:** fazer da alocação de elenco e recursos o centro do idle manager. O jogador distribui mercenários entre produção, contratos, preparação e defesa; escolhe onde investir; e vê uma simulação regional persistente reagir às decisões da guilda. O jogador deve poder jogar em sessões curtas ou deixar uma atividade previamente designada avançar offline, sem materiais passivos duplicados.

**Confirmada:** manter desktop offline, campanha single-player, a arquitetura Python/FastAPI/Jinja2/SQLAlchemy/SQLite e a maioria dos serviços existentes. **Proposta:** substituir repetição sem contexto por contratos rotativos e ciclos regionais; introduzir coleta atribuída a mercenários; simular rivais CPU de forma determinística e explicável. Não haverá rede, geração de conteúdo por IA, novo motor ou economia online neste escopo.

## 2. Diagnóstico completo da gameplay atual

### Evidências da auditoria

- As missões são templates persistentes e runs individuais: `app/models/mission.py`, `app/services/mission_service.py`. O catálogo é separado em faixas de nível e tipo. A lista atual filtra templates ativos por faixa/nível; missões longas têm limite de três runs ativas e são ordenadas ao final no serviço.
- Uma missão trava todos os participantes como ocupados. Resultado, ouro, XP e drops são resolvidos somente quando o jogador coleta após o timer (`claim_mission_loot`). Falha de conteúdo comum concede uma fração de XP; loot depende do resultado conforme o serviço. O multiplicador altera duração e recompensas/quantidades, não a chance.
- Coletas atuais são missões do tipo gathering; não há uma fila contínua de produção nem uma entidade de atribuição de trabalhador. Profissões são treinadas em `ProfessionTraining`, ficam associadas ao mercenário e aumentam em pontos percentuais a chance de drop da família compatível (`profession_service.py`).
- O retorno offline da campanha desktop passa pelo `ClockGuard`, mas reutiliza `get_passive_gold_rate` e `calculate_offline_material_rewards`: há ouro, madeira, minério e um cristal ao atingir o teto. O bônus do Armazém é aplicado aos materiais. Isso conflita com a diretriz deste GDD de não gerar recursos de coleta passivamente e torna prioritário evitar fontes duplicadas ao adicionar trabalhadores offline.
- Existe proteção contra regressão de relógio e replay acidental com high-water mark local protegido por DPAPI, limite de 8 horas e crédito somente em encerramento limpo. Não existe proteção absoluta contra manipulação deliberada de arquivos/relógio em jogo puramente offline; o GDD desktop descreve corretamente essa limitação.
- Construções produzem efeitos reais, mas `BUILDING_MAX_LEVEL` é 50 em `app/services/building_balance_service.py`, embora conteúdo/seeds históricos ainda usem referências até 100. Housing chega a 20 vagas no nível 50. O Campo de Treino concede +1% de XP por nível; outras construções afetam loot, grupos, contratação, mercado, docas e exploração.
- O Ferreiro já tem receitas rotativas por campanha e nível: nível 1 libera 3 receitas; o limite cresce até 8; raridade máxima e duração de rotação avançam até Mítico/4h no nível 50. Refino exige nível 10; desmontagem tem 1/2/3 espaços nos níveis 1/25/50.
- Masmorras e chefes possuem requisitos de grupo, papéis, poder, edifício, item e bloqueio de entrada por template enquanto há run ativa. A entrada de conteúdo e o loot são resolvidos em `dungeon_service.py`; dungeons e chefes têm tabelas e drops próprios.
- O sistema de crafting/refino, Mercado, Docas e desmontagem oferece conversões econômicas existentes; comprar para desmontar é um vetor de arbitragem que exige simulação antes de alterar rendimento.
- Ranks E–S, Vigília Regional, regiões persistentes, guildas rivais CPU e eventos regionais encadeados não estão implementados no código examinado.

### Diagnóstico de experiência

O ciclo de missão coleta → recurso → construção pode se tornar uma rotina de cliques sem escolha de oportunidade. Coleta e combate competem pelo mesmo elenco, mas hoje sem fila produtiva dedicada ou planejamento de escala. A produção passiva de materiais no idle desktop também reduz a clareza sobre qual atividade originou o recurso. O grande número de templates gerados amplia variedade nominal, mas muitos nomes e diferenças podem ser procedurais e não comunicar uma decisão tática distinta. A solução recomendada é dar contexto, rotações, custo de oportunidade e feedback regional às atividades existentes, não simplesmente acrescentar centenas de telas e recursos.

**Limite da auditoria:** houve inspeção dirigida dos principais modelos, serviços, regras, documentação, relatórios e testes listados neste GDD; não se afirma leitura manual de cada linha de todo asset/conteúdo ou execução de uma campanha completa. A campanha real do usuário e o banco de outro checkout não foram usados em experimento.

## 3. Inventário dos sistemas existentes

| Sistema | Funcionamento confirmado | Módulos/modelos relevantes | Reuso / lacuna |
|---|---|---|---|
| Campanhas e saves | SQLite por campanha, metadata, migração e backups | `campaign_service.py`, `desktop/clock_guard.py`, `models/campaign.py` | Reusar; qualquer estado regional deve pertencer à campanha e migrar sem perda. |
| Guilda/tesouro | nível, XP, recursos numéricos e reputação histórica | `models/guild.py`, `guild_progression_service.py` | Reusar progressão; distinguir reputação de segurança/ameaça/influência. |
| Mercenários | contratação, demissão, nível, raridade, classe, profissão e estado busy | `models/mercenary.py`, `tavern_service.py`, `progression_service.py` | Reusar identidade e exclusividade de ocupação; criar tipo de atividade atribuída de modo extensível. |
| Classes e sinergia | caminhos de classe, atributos, habilidade/classe e composição | `models/mercenary.py`, `models/class_change.py`, `skill_service.py`, `balance_service.py` | Reusar em contratos e especializações; simular risco de bônus sobrepostos. |
| XP e poder | XP requerida = nível atual × 100; poder deriva dos atributos | `balance_service.py`, `progression_service.py`, `equipment_service.py` | Preservar inicialmente e avaliar curva total até 50. Fórmula exata consta na seção 22. |
| Profissões | treinamento temporizado e bônus de drop compatível | `models/content.py`, `profession_service.py` | Reusar catálogo; adaptar bônus para eficiência da nova coleta sem duplicar bônus de drop. |
| Inventário e equipamentos | acumuláveis agregados e instâncias únicas com RNG persistido | `models/item.py`, `equipment_service.py`, `item_repository.py` | Reusar; resolver fonte canônica de totais de recursos e semântica de tier. |
| Construções | níveis e efeitos centralizados, custo de upgrade, requisitos | `models/building.py`, `building_service.py`, `building_balance_service.py` | Reusar gates, adicionar efeitos só mediante objetivo mensurável. Máximo atual real: 50. |
| Missões/coletas | template + run + membros + timer + coleta manual | `models/mission.py`, `mission_service.py` | Reusar resultado e locks; transformar catálogo ativo em oferta/rotação sem apagar catálogo. |
| Masmorras/chefes | templates, runs, grupos, requisitos e drops | `models/dungeon.py`, `dungeon_service.py` | Reusar encontro e coleta manual; ligá-los a ameaças/portais regionais gradualmente. |
| Taverna | aprendizes, ofertas, custo escalável e mercenário especial | `models/tavern.py`, `tavern_service.py` | Reusar; recrutamento deve disputar ouro e alojamento com atividades. |
| Ferreiro | receitas rotativas, criação, refino e desmontagem | `models/crafting.py`, `models/salvage.py`, `crafting_service.py`, `salvage_service.py` | Reusar; integrar materiais, ferramentas e mercado com margens controladas. |
| Mercado/Docas | venda temporizada, coleta e rotação de estoque | `models/market.py`, `models/dock.py`, `market_service.py`, `dock_service.py` | Reusar como escoamento e fonte de compra; limitar arbitragem de materiais. |
| Habilidades/conquistas/Codex | skill effects, estatísticas, unlocks e claims | `models/skill.py`, `models/achievement.py`, `skill_service.py`, `achievement_service.py` | Reusar como telemetria e metas; não inflar bônus antes da simulação. |
| Admin e seeds | conteúdo e balance pass em origens diferentes | `app/seeds/`, serviços `seed_*` | No desktop, seeds versionados; não reaplicar patches em campanha aberta. |
| Interface e guias | Jinja2, páginas server-rendered, tema/sprites locais | `app/templates/`, `app/static/`, `guide_routes.py` | Reusar; guiar por desbloqueios e comunicar fonte/uso do recurso. |

## 4. Problemas identificados e oportunidades

1. **Fontes de materiais ambíguas:** o idle atual credita madeira/minério além do ouro e de atividade de coleta. A atribuição proposta exige que essa fonte seja removida, substituída ou explicitamente preservada por decisão; recomendação é removê-la quando coleta contínua entrar.
2. **Não há trabalho de coleta contínuo:** profession training não é produção; coleta é missão. Uma mecânica nova precisa permitir designação, duração/ciclos, ocupação e coleta offline idempotente.
3. **Sem mundo reativo:** não há ciclo global da campanha, regiões ou guildas concorrentes. Ranks e vigílias não devem apenas renomear templates; precisam modificar disponibilidade, estado regional e recompensas de modo compreensível.
4. **Reputação sobrecarregada:** existe campo histórico de reputação, mas segurança, ameaça e influência regionais ainda não existem como eixos separados.
5. **Catálogo e economia de conteúdo massivo:** `massive_content.py` gera templates com faixas/tier 1–8 e nomes com sufixos numéricos; isso é progressão/catalogação de conteúdo, não raridade. Um total grande de opções não garante diversidade mecânica.
6. **Confusão de tier (observação da auditoria):** `ItemTemplate` mantém raridade, `tier` e `item_level`. A raridade é Comum–Mítico. Decisão posterior: a interface não exibe T1–T8; mostra raridade, refino `+N` e nível mínimo quando aplicável. Campos técnicos permanecem até plano de migração.
7. **Balanceamento de construção divergente (observação da auditoria):** código central limita nível a 50, mas seeds usam `min(100, ...)`. Decisão posterior: o teto planejado é 100; implementação deve padronizar limite, custos e marcos.
8. **Atribuição e elegibilidade:** a quantidade de mercenários é limitada pelo Alojamento, e trabalhos competirão com contratos. A interface deve mostrar custo de oportunidade e não punir uma equipe pequena com muitas demandas simultâneas.
9. **Falta de resultados atuais reproduzíveis:** relatórios estáticos de junho de 2026 usam banco/conteúdo do momento em que foram gerados. Reexecutar benchmark em fixture reproduzível antes de fixar valores.

Oportunidade central: criar um quadro diário/cíclico que conecta a especialização existente a produção, cada produção a receitas/construções, e os contratos a alteração de segurança/ameaça, preservando resultado manual e runs transacionais.

## 5. Nova filosofia de gameplay

- O jogador escolhe prioridades, não apenas a próxima ação de maior XP/h.
- Todo material central tem fonte, dreno, transformação e uma explicação visível.
- Todo mercenário ocupado representa uma escolha temporária real, com duração e retorno demonstrável.
- O idle é continuação do último plano deliberado (trabalho atribuído), nunca uma fonte passiva paralela sem tarefa.
- Conteúdo acima do recomendado pode ser arriscado, mas não deve bloquear o jogador sem motivo legível.
- Atividades não precisam ser todas feitas em cada ciclo. A guilda deve escolher uma fração de ofertas compatível com seu elenco.
- A simulação CPU precisa ser determinística por campanha/ciclo, auditável em histórico e barata de executar.
- Um ciclo adiciona variedade à rotina sem exigir login, internet, serviço remoto ou IA generativa.

## 6. Novo ciclo principal do jogo

**Proposta de loop de sessão:**

1. Abrir campanha e receber uma única prestação de contas de tempo/produção/eventos pendentes.
2. Ver estado da região, metas da guilda, elenco disponível e ofertas do ciclo.
3. Comparar contratos, coleta, preparação, crafting e investimentos, vendo recompensas, risco, duração e custo de oportunidade.
4. Atribuir mercenários a uma ou mais atividades compatíveis com exclusividade de estado.
5. Usar mercenários restantes para contratos, masmorras ou chefes; escolher equipe, suprimentos/tática se desbloqueados.
6. Enquanto offline, somente atividades explicitamente atribuídas progridem; calcular ciclos concluídos até o teto uma vez.
7. Coletar resultados manualmente onde a regra atual exige; processar resoluções pendentes ao abrir sem repetir recompensas.
8. Atualizar região, reputação, ameaças e ofertas; explicar causalidade no resumo/histórico.
9. Reinvestir em mercenários, profissão, construção, receitas e equipamentos.

**Decisão refinada:** Vigília Regional de 6h fixas. Ao retornar após várias vigílias, processar todos os ciclos vencidos em lote, cada qual exatamente uma vez. A vigília não obriga o usuário a estar presente.

### Identidade de campanha e save

- A criação de save solicita somente o nome da guilda; remover o campo separado “Nome da campanha” da experiência do jogador.
- O título visível do save é o nome da guilda. Abaixo, exibir a região natal sorteada para a campanha, para distinguir saves e ajudar o jogador a lembrar seu contexto.
- A campanha mantém `campaign_id`/identificador técnico próprio internamente; não expor um segundo nome editável que duplique a identidade da guilda.

## 7. Economia, recursos e profissões

### Recursos

**Decisão refinada:** ouro como moeda; madeira, minério e couro como materiais essenciais da economia. Cristais são especiais e raros, não parte da coleta principal. O catálogo contém ainda pedra, tecido, erva, essência, gema, material de besta, relíquia, catalisador e insígnia; não promover materiais secundários a essenciais até mapear drenos reais por faixa.

| Recurso/família atual | Fontes já existentes | Drenos existentes ou candidatos | Recomendação |
|---|---|---|---|
| Madeira | coleta/drop, Docas, desmontagem e idle atual | construções e receitas | Tornar coleta designada fonte principal; tábuas são proposta. |
| Minério | coleta/drop, Docas, desmontagem e idle atual | construções, crafting e refino | Barras são proposta; receita deve competir com upgrade. |
| Couro/peles | drops, Docas e desmontagem de famílias compatíveis | crafting e equipamento | Fonte primária via coleta/monstros; couro tratado é proposta. |
| Cristais/gemas | loot/Docas/desmontagem e 1 cristal no teto offline | refino e conteúdo avançado | Cristal é recurso especial; gema é material distinto para crafting/loot. |
| Erva/tecido/pedra/essência e outros | catálogo/drop/Docas | receitas/conteúdo dependente do item | Cada item habilitado deve declarar ao menos um dreno atual. |

### Cadeias produtivas

**Propostas:** madeira → tábua → arco/ferramenta; minério → barra → arma/armadura; pele/couro bruto → couro tratado → armadura/acessório. Reusar `CraftingRecipe`/`CraftingRecipeMaterial` e a rotação do Ferreiro, evitando uma tela/engine de crafting paralela. Definir perdas, custo de ouro e slots de processamento antes de produzir em massa.

### Profissões

Profissões existentes cobrem famílias como madeira, minério, ervas, couro, tecido, gemas, relíquias e essências. Proposta: cada profissão concede **um** eixo principal de eficiência na coleta (velocidade OU chance de unidade extra OU acesso a nó especial) e, no máximo, um benefício secundário em conteúdo compatível. Não acumular simultaneamente velocidade, produção extra e acesso raro sem simulação. O bônus atual de drop em missões deve ser mantido até uma migração explícita, depois convertido para a fonte nova para evitar double dip.

## 8. Coleta e ocupação de mercenários

### Regras refinadas e comportamento proposto

- Atividades iniciais: madeira, minério e couro. No máximo uma atividade ativa por tipo de material; cada atividade aceita exatamente um mercenário. No estágio inicial podem coletar até três mercenários, um por material.
- A coleta continua até o inventário compartilhado encher ou o jogador retirar o mercenário. Quando lota, a produção pausa sem liberar o mercenário e retoma quando houver espaço.
- O mercenário designado fica ocupado e não pode entrar em missão, masmorra, chefe, treinamento ou outra tarefa incompatível.
- Criar nós/atividades de coleta versionados por conteúdo, família, região, faixa, duração de ciclo, rendimento base, requisito e desbloqueio.
- Ritmo-base para teste: 1 unidade a cada 60 segundos. A cada ciclo há uma rolagem de até 45% para uma unidade extra, conforme bônus agregados. Números sujeitos a simulação.
- Cada trabalho tem `started_at`, `next_cycle_at`, `last_processed_at`, estado, multiplicador de eficiência congelado/definido na entrada e versão da regra. A saída deve ser idempotente por ciclo ou por checkpoint.
- Conceder materiais em lotes ao retorno, sem simular milhares de eventos: `ciclos elegíveis = floor(tempo reconhecido / 60s)`. O RNG precisa ser reproduzível por campanha/trabalho/ciclo ou por amostragem equivalente com seed persistida; definir técnica antes de implementar.
- Para tarefas indefinidas, permitir suspender/trocar em transação sem apagar ciclos já processados. Exibir previsão por hora e teto offline.
- A representação visual (personagem genérico, ferramenta, barra e contador) é feedback, não autoridade da regra.
- Se a produção exceder o espaço restante, armazenar apenas o que couber e descartar o excedente daquele ciclo; nunca ultrapassar a capacidade.

### Equilíbrio inicial

O valor inicialmente discutido de 1 unidade a cada 5s foi substituído por **1 unidade a cada 60s**: até 480 unidades-base por trabalhador no teto de 8h offline. Com três recursos e um trabalhador por atividade, são até 1.440 unidades-base; a capacidade inicial selecionada de 1.500 serve como hipótese inicial antes de bônus e outras fontes. A chance de extra de até 45% pode lotar o Armazém antes. Validar tudo por simulação.

**Regra refinada:** cada ciclo concede 1 unidade-base e rola independentemente uma unidade extra, com chance final somada em pontos percentuais e limitada a 45%. Profissão, ferramenta e construção não alteram a unidade-base nem a duração. Persistir resultado/checkpoint de forma reproduzível.

## 9. Produção online e offline

### Regras refinadas e modo offline manual

1. A estamina é vinculada a cada save/campanha. Um save novo começa com 8 horas disponíveis. Depois do primeiro uso, cada hora online elegível carrega 2 horas de estamina, até o teto de 8 horas. Enquanto o jogador está com uma campanha aberta, as tarefas atribuídas avançam até o limite do Armazém.
2. O jogador inicia o período offline por um botão explícito “Modo Offline” dentro do jogo. A ação salva a campanha com segurança, registra a âncora de tempo pelo ClockGuard e retorna à tela de seleção de saves, onde o jogador pode abrir outro save ou fechar o aplicativo.
3. Somente esse comando inicia o período offline elegível. Fechar a janela, deixar o aplicativo aberto na seleção de saves, crash ou queda de energia não iniciam nem concedem progresso offline. O ClockGuard continua protegendo contra retrocesso/replay, agora limitado também pela estamina disponível.
4. Ao reabrir o save, processar no máximo o menor valor entre tempo transcorrido reconhecido, estamina disponível, teto offline de 8h e limite técnico seguro. Consumir estamina pelo tempo offline efetivamente processado. A taxa inicial é 2h de estamina por hora online; o teto offline permanece 8h.
5. Remover madeira e minério do idle passivo. Manter o cálculo atual do ouro passivo (base por hora + nível da guilda + quantidade de mercenários contratados + Armazém), sujeito a balanceamento. Ao completar 8h offline reconhecidas, conceder no máximo 1 cristal especial por retorno, preservando a regra refinada anteriormente.
6. Ouro e o cristal especial não ocupam capacidade do Armazém.
7. Capacidade inicial compartilhada: 1.500 unidades acumuláveis; cada unidade conta 1. Equipamentos únicos ficam fora. Aumenta principalmente por marcos do Armazém (preferência por intervalos de 5 níveis) e, em menor grau, por nível da guilda. Valores por marco precisam ser definidos em balanceamento.
8. Ao lotar, tarefas de coleta pausam sem liberar trabalhadores e retomam quando houver espaço.
9. Processar cada intervalo uma vez com ledger/checkpoint transacional. Online e offline usam o mesmo motor de ciclo.
10. Se o save for restaurado/copiado para outro perfil, seguir o GDD Desktop: nova âncora e nenhum crédito retroativo anterior à importação.

### Relatório de retorno

Ao voltar a um save que acumulou tempo offline, apresentar obrigatoriamente um resumo modal antes de entrar no jogo. O resumo inclui tempo ausente/reconhecido, estamina consumida/restante, gold passivo, produção por tarefa/família, bônus aplicado, ciclos/eventos e alertas do ClockGuard. Não depender de um aviso discreto no dashboard. Persistir o resumo como pendente até ele ser exibido e confirmado; garantir entrega única, sem duplicar recompensas, e manter registro no histórico. Não esconder bônus do Armazém nem somá-lo visualmente sem identificar a base.

### Limite de confiança

O clock guard atual reduz abuso acidental e retrocesso simples; não pode impedir usuário deliberado de restaurar save/backup, alterar arquivos protegidos enquanto controla o Windows ou avançar relógio em intervalos. Nenhuma recompensa deve ser prometida como anti-cheat absoluta offline.

## 10. Equipamentos, atributos e especializações

**Confirmado no código:**

- A XP para próximo nível é `nível atual × 100`.
- `calculate_power_score` soma poder + metade arredondada para baixo de vitalidade, agilidade, inteligência e armadura + sorte/3 arredondada para baixo. Atributos de equipamento entram no resumo total de mercenário.
- Mercenário recebe bônus de progressão baseado em raridade: Comum 0%, Incomum 1%, Raro 2%, Épico 3%, Lendário 4%, Mítico 5% (`balance_service.py`).
- Equipamentos são instâncias únicas; bônus aleatórios são rolados ao criar a instância, não em cada render/equip. Slots e restrições de classe estão em `equipment_service.py`.
- Chance real usa desvio de poder contra o recomendado, bônus de classe, composição, habilidade, raridade (em faixas superiores) e bônus de conteúdo/edifício, com limites. Não reduzir a chance a uma fórmula antiga do GDD web.

**Proposta de gameplay:** ferramentas de coleta podem ser itens de equipamento/instrumento que aumentem eficiência de uma família; preparar ferramenta disputa recursos e uso do Ferreiro contra arma/armadura. Especializações de classe/profissão são complementares: classe para função de combate e profissão para produção. Não adotar bônus de produção sem conferir o poder de combate e o peso do mercenário fora do grupo.

**Decisão de produto/UX:** exibir raridade Comum–Mítico, refino `+N` e nível mínimo de uso quando aplicável; remover T1–T8 da interface. Não confundir `item_level` (nível mínimo/base) com refino. Campos técnicos persistidos `tier`/`item_level` não devem ser apagados sem plano de migração; qualquer faixa interna remanescente fica oculta e não representa raridade.

## 11. Construções e benefícios estratégicos

Reutilizar Alojamento, Campo de Treino, Ferreiro, Armazém, Escritório, Exploradores, Taverna, Mercado e Docas; níveis e benefícios ficam em `building_balance_service.py`. Construções devem oferecer escolhas reais e degraus compreensíveis, não somente somar percentuais pouco visíveis.

| Construção | Efeito central atual conferido | Papel sugerido no loop novo |
|---|---|---|
| Alojamento | capacidade por marcos; máximo 20 no nível 50 | limite de mão de obra disponível. |
| Campo de Treino | bônus XP mercenário +1 p.p. por nível; troca classe desbloqueada a partir do marco atual | formar equipe e reduzir custo de oportunidade de progressão. |
| Ferreiro | chance de equipamento, receita/rotação, refino nível 10 e desmontagem | converter matérias e habilitar ferramentas. |
| Armazém | bônus em materiais e gold/h no idle atual | armazenagem/eficiência, mas evitar duplicar fontes passivas. |
| Escritório de Contratos | party size por faixa, recompensa e duração | ampliar opções por ciclo sem exigir que todas sejam concluídas. |
| Exploradores | multiplicadores, duração, drops e bônus de exploração | desbloquear expedições, portais e conteúdo de risco. |
| Taverna | probabilidade/desconto e ofertas | investimento em mão de obra versus crafting/produção. |
| Mercado | slots, tempo e valor de venda | escoar excedente e participar de economia local simulada sem comércio online. |
| Docas | mercadores, ofertas, rotação, nível de catálogo | compra de recurso como conveniência cara, não método dominante de farm. |

**Decisão de progressão:** construções podem chegar ao nível 100. Como `BUILDING_MAX_LEVEL=50` limita o código atual e alguns seeds já usam requisitos até 100, a implementação deve ampliar o limite com migração/compatibilidade e recalibrar custos e marcos. A progressão de construções até 100 não obriga todas as estruturas a liberar conteúdo em cada nível.

## 12. Contratos, masmorras e chefes por rank

### Quadro de Contratos

**Proposta:** oferta limitada e renovável por ciclo, com Rank E–S como eixo de classificação e nível/poder como recomendação. Reaproveitar `MissionTemplate`, `MissionRun`, `MissionRunMember`, drops, timer e coleta manual. Acrescentar rank/dados de oferta apenas se o modelo atual não puder representar ciclo e disponibilidade com segurança. Ranks não substituem faixas de nível nem alteram atributo de template silenciosamente.

Oferta pode incluir objetivos variados (caça, escolta, levantamento, coleta, defesa) e um modificador de região. A guilda escolhe quais aceitar; não há obrigação de completar 10. Manter `LONG_IDLE_LIMIT=3` enquanto decisão; missões longas são tipo separado, não devem ser misturadas ao board padrão sem política explícita.

No late game, a meta inicial é que 5–6 das 10 ofertas de contrato sejam ranks B–S, mantendo o limite de até 3 ocorrências por rank. A curva deve continuar permitindo ranks baixos para escolha e variedade.

Masmorras e chefes recebem distribuição de ranks própria, sem o teto de três por rank dos contratos. Masmorras usam os pesos regionais com leve viés para cima; o chefe tende ao rank mais alto da rodada. Em falha de contrato, masmorra ou chefe regional ranqueado, o grupo recebe 25% do XP normal, sem ouro nem loot.

### Masmorras e chefes

Reusar `DungeonTemplate`/`DungeonRun` e validações. Rank igual não implica dificuldade igual: masmorra pode oferecer vários encontros/drops e chefe tem risco concentrado. Chefes podem pedir formação/equipamento por faixa, mas Rank E inicial precisa ser concluível pelo elenco inicial. Conteúdo acima do recomendado permanece risco opcional, salvo requisito narrativo/técnico declarado.

Loot deve preservar raridade baixa frequente e itens excelentes raros; medir probabilidade de ao menos um equipamento, valor esperado e pity/ausência de progresso antes de introduzir proteção. Aumentar quantidade de linhas de drop não equivale automaticamente a recompensas melhores: revisar chance independente e chance agregada.

### Rotação e persistência

Ofertas devem ser snapshots por ciclo. A oferta não pode mudar no reload; um ciclo com resultado simulado precisa registrar seed/inputs e não rerrolar em reabertura. Runs ativas não são removidas ao expirar oferta. Uma atividade não ocupada pode expirar ou persistir conforme decisão do board.

## 13. Vigília Regional

**Decisão refinada:** ciclo fixo de 6h. Cada rodada calcula ofertas, simula guildas CPU, atualiza indicadores e publica relatório. O mundo avança ao abrir/consultar a campanha, sem scheduler/worker e sem exigir sessão ativa. A campanha terá 5 regiões e 5 guildas por região, contando a guilda do jogador na região natal. A região natal será sorteada ao criar a campanha.

### Sequência determinística

1. Fixar `cycle_id`, intervalo, versão de conteúdo e seed determinística.
2. Congelar snapshot de guildas, equipes CPU, estado regional e ofertas.
3. Resolver atividades de jogador vencidas/claimadas seguindo regras atuais; distinguir “timer terminou” de “resultado coletado”.
4. Simular plano de cada guilda CPU com orçamento, equipe e risco definidos.
5. Agregar resultados e calcular segurança, ameaça, reputação e influência por regra versionada.
6. Avaliar limiares/eventos uma vez, registrar evento e impactos previstos.
7. Abrir próximo ciclo e apresentar resumo com explicações causais.

**Decisões refinadas:** cada Vigília oferece 10 contratos, 3 masmorras e 1 chefe por região. O limite de até 3 ocorrências de um mesmo rank vale somente para os contratos; masmorras e chefes terão distribuição e limites próprios. Ranks são sorteados por RNG com pesos influenciados gradualmente pelo nível da guilda e pela força total do elenco. Rank S começa com referência de 1% por espaço de contrato, antes dos bônus de progressão; seus pesos crescem com a progressão. A distribuição tende a E/D/C no início, mistura ranks no meio e favorece ranks altos no late game. Probabilidades exatas ficam ocultas, mas o Guia do Jogo explicará os fatores. A masmorra de portal é conteúdo extra, além das três ofertas regulares. Em ausências, processar todas as Vigílias vencidas uma vez; a estamina offline do jogador limita suas recompensas, não o calendário regional nem a progressão da CPU. Testar idempotência e custo da simulação.

### Rebeliões e acesso entre regiões

- A guilda atua somente em sua região natal, exceto durante uma rebelião ativa que convide ajuda externa.
- Uma rebelião é um evento cooperativo raro, gerado quando a ameaça está alta e a região tem controle insuficiente; RNG determina o momento. No máximo uma rebelião global pode estar ativa.
- O evento só surge enquanto a campanha está aberta e apresenta uma notificação temática com ações equivalentes a “participar” ou “recusar”. A recusa delega a resolução à CPU.
- Ao aceitar, inicia-se um prazo de 1h de prioridade para o jogador organizar e enviar mercenários. Após essa hora, a CPU pode ocupar atividades/vagas restantes. O prazo geral do evento é de 12h; os timers continuam offline após a decisão.
- Sem resposta ao convite por 1h, considerar recusa e iniciar a simulação CPU de 12h. Ao recusar explicitamente, a CPU também executa durante 12h. Resultados aparecem no encerramento.
- Cada guilda pode assumir várias atividades até o limite de mercenários disponíveis e requisitos: contratos, portais/masmorras e chefes. Atividades ocupam os mercenários envolvidos; resultados de sucesso/falha são agregados no fechamento.
- Várias guildas podem participar. Cada uma recebe recompensa e influência proporcional à contribuição; a recompensa pode ser ligeiramente mais lucrativa que conteúdo da região natal, mas permanece moderada e ajustada pelo rank. O cálculo final exige simulação para não tornar rebelião a única atividade ótima.
- A participação também concede bônus/influência à região natal da guilda visitante. O resumo mostra separadamente o resultado agregado e a condição final da região rebelde.
- O resultado positivo reduz ameaça e aumenta segurança; falha aumenta ameaça modestamente. Não permitir rebeliões simultâneas em várias regiões.
- Notificação inicial e acesso persistente a evento ativo devem permanecer no jogo; depois de resolvido, o painel/evento ativo desaparece, mas o histórico permanece.

### Persistência proposta

Entidades conceituais novas prováveis: `Region`, `RegionalCycle`, `RegionalOffer`, `RegionalGuildState`, `RivalGuildProfile`, `RivalCycleResult`, `RegionalEvent`, `RegionalHistoryEntry`. Não criar todas antecipadamente; mínimo viável deve salvar ciclo, região, estado inicial/final, resultados agregados, seed/versões e marcador idempotente. Escopo por `campaign_id`; não introduzir dependência online nem compartilhar mundo entre saves.

### Distribuição inicial das guildas

- Cada região contém 5 guildas. A região natal é escolhida aleatoriamente e a guilda do jogador ocupa uma vaga de perfil recém-criado.
- Na região natal ficam, além do jogador, 1 rival forte, 1 rival médio e 2 recém-criados. Nas demais regiões ficam 1 forte, 1 médio e 3 recém-criados.
- A força inicial dos rivais é definida pelo estágio da região/campanha, não copiada do poder atual do jogador. O rival forte consegue manter a região calma por um período, mas não indefinidamente.

## 14. Guildas CPU e competição regional

**Decisão refinada:** simular rivais como jogadores completos, com mercenários, recursos, profissões e decisões individuais, sem IA generativa. Cada rival tem arquétipo fixo (expansão, segurança, contratos ou exploração) com pequenas variações por RNG e estado próprio. Elenco inicial por perfil: forte 5 mercenários, médio 3, recém-criado 1. Perfis são dimensionados pelo estágio da região, não pelo poder atual do jogador. A CPU progride também enquanto o jogo está fechado; ao retornar, o sistema simula todo o tempo transcorrido e os ciclos vencidos, não apenas uma Vigília e sem ser limitada pela estamina offline do jogador. A simulação deve ser determinística, idempotente e processada em lotes para manter saves e carregamento eficientes.

Para sorteio de ranks e portais, a força da guilda do jogador é a soma do poder total de todos os mercenários contratados e não demitidos, incluindo equipamentos equipados, disponíveis ou ocupados. Mercenários demitidos nunca entram no cálculo.

Guildas CPU também mantêm estado completo e podem participar de rebeliões/portais. As atividades disponíveis não devem ser consumidas pela CPU antes de expirar a janela de prioridade humana de 1h; após essa janela, CPU e jogador podem ocupar atividades elegíveis sem repetir a mesma atividade reservada.

**Proposta de transparência:** mostrar no histórico ações resumidas da CPU (“priorizou patrulhas e reduziu ameaça”), não expor milhares de rolagens. Um mesmo save/ciclo/versão deve produzir os mesmos resultados para QA e para retomar campanha. Atualizações de algoritmo podem mudar ciclos futuros, nunca reescrever histórico encerrado.

O ranking global é persistente e atualiza a cada Vigília, sem reset durante a campanha. Pontuação inicial: 50% influência, 25% reputação e 25% vitórias em eventos. Vitórias pontuam por sucesso e contribuição, ponderadas pelo rank. Pesos são configuração de balanceamento e podem ser revistos após simulações.

**Não incluir:** multiplayer, comércio entre jogadores, contas, servidores, torneio em tempo real ou modelo generativo.

## 15. Reputação, segurança, ameaça e influência

Manter quatro conceitos separados:

- **Reputação da guilda:** confiança/renome obtido por contratos cumpridos, falhas, eventos e comportamento; pode afetar ofertas ou acesso com limites suaves.
- **Segurança regional:** condição de patrulha/estabilidade, reduzida por ameaças e elevada por atividades defensivas.
- **Ameaça regional:** pressão de inimigos, incidentes e portais; eleva risco e pode gerar evento se permanecer alta.
- **Influência:** presença relativa das guildas na região por participação e sucessos, sem ser sinônimo de reputação.

Os modelos atuais têm `Guild.reputation`, não há eixos regionais equivalentes. Recomendação: manter reputação histórica, introduzir estado por região separado; não reaproveitar um inteiro para quatro significados.

**Decisões refinadas para o primeiro balanceamento:** segurança, ameaça e influência usam escala de 0 a 100; reputação continua separada. Sem ações regionais em uma Vigília, a referência é ameaça +1 e segurança -1. Sucessos e falhas alteram ameaça/segurança com impacto crescente pelo rank: sucesso reduz ameaça e aumenta segurança; falha faz o inverso. Reputação aumenta em sucessos e diminui em falhas, com peso por rank e contribuição. Influência cresce por participação/contribuição e sucessos, ponderada pelo rank e pela contribuição.

Com ameaça a partir de 70, cada Vigília tem chance inicial de portal de 5%, crescendo gradualmente até o teto de 25% quando a ameaça chega a 100. O gatilho de rebelião exige ameaça de pelo menos 85 e segurança de no máximo 25, além da rolagem de RNG e das regras globais do evento. Estes valores são parâmetros de partida para simulação, não fórmulas finais imutáveis.

**Hipótese de escala para simulação:** indicadores 0–100 podem ser convenientes para UX, mas escala, decaimento, ganhos e limites estão pendentes. Evitar acumuladores sem teto, reputação que chega a 100 inevitavelmente, queda irreversível ou evento cascata sem oportunidade de recuperação. Mudanças no resumo devem citar causas e ações contribuintes.

## 16. Eventos regionais e contratos encadeados

**Decisões refinadas e proposta:** portais dimensionais aparecem por RNG com peso crescente conforme ameaça regional; no máximo um portal fica ativo por região. O portal oferece uma masmorra especial que culmina em chefe, com tabela exclusiva e melhores chances de itens raros, sem equipamento garantido. O jogador tem 3h para iniciar; cada guilda tem uma entrada. Depois que envia equipe, os mercenários ficam ocupados até conclusão; duração depende de rank/perigo e nunca é menor que 1h. Sucesso/falha encerra e remove o portal. Guildas CPU também podem entrar e seus resultados são simulados.

Portais podem fazer parte de rebeliões, que permitem guildas visitantes participarem de múltiplas atividades na região afetada. Fora da rebelião, cada guilda permanece restrita à sua região natal.

Contratos bem-sucedidos podem desbloquear passo seguinte; falhas ou ignorar podem alterar risco futuro, sem punir ausência com perda inevitável. Chefes têm vínculo com ameaça/boss regional.

Evento tem gatilho versionado, duração/condição, escopo regional, capacidade de participação, recompensa, sucesso/falha e consequência reversível. Um evento só se resolve uma vez e seu gatilho precisa ser explicável. Rebelião só pode ser criada quando a campanha está aberta; depois de escolhida participação/recusa, seus prazos avançam também enquanto o jogo está fechado. Eventos sazonais reais e conteúdo dependente de relógio externo ficam fora do escopo offline.

## 17. Preparação de contratos

Na primeira versão regional, a preparação oferece uma escolha simples de suprimento por grupo, consumido ao iniciar a expedição. Ela concede +5 pontos percentuais de chance de sucesso. Custo em ouro/recursos e esforço cresce conforme o rank (E mais barato; S relativamente caro). O custo não pode superar o valor econômico de uma vitória naquele rank; simulações devem comparar o custo com o valor esperado incremental do bônus de 5 p.p., para que a preparação seja uma escolha justa e nunca uma armadilha econômica. Não haverá loadout de várias táticas nesta etapa; o efeito fica registrado no snapshot da expedição.

O inventário acumulável e equipamento único são reaproveitáveis. O suprimento simples entra no primeiro loop regional; loadouts extensos e táticas ficam como expansão posterior. Cada item consumido e efeito deve ser registrado no snapshot da run para auditoria.

## 18. Histórico e ranking de guildas

No single-player, “ranking” é comparação com rivais CPU dentro da campanha, não classificação online. Mostrar guilda, reputação, influência, região e desempenho de ciclos; incluir janela temporal recente e tendência em vez de apenas placar vitalício.

O histórico deve registrar ciclo encerrado, contrato/missão relevante, sucesso/falha, mudança de indicadores, chefe/portal, evento e consequência seguinte. Reusar timestamps e snapshots das runs, mas adicionar eventos regionais explícitos. Resumos pessoais e regionais devem ser distintos; a mesma recompensa não pode reaparecer como pendente em ambos.

## 19. Progressão e desbloqueios

Mercenários até nível 50 são o primeiro arco de validação, não teto permanente. O jogador deve experimentar, antes do nível 50, contratação, coleta designada, especialização, equipamento, criação/refino, masmorra, chefe, contratos por rank e um ciclo regional completo. Conteúdo não deve exigir subir todas as construções simultaneamente.

Mostrar conteúdo futuro em estado bloqueado com requisito e benefício, usando o padrão existente de link para Construções/Guia. Metas são recomendações opcionais: novo mercenário, primeiro coletor, primeiro item fabricado, novo rank etc. Evitar obrigatoriedade linear e recompensas diárias que penalizem ausência.

## 20. Experiência inicial, tutoriais e guias

### Conquistas e recompensas

Expandir o catálogo de Conquistas com objetivos variados de progressão, mercenários, classes, profissões, construções, economia, coleção, contratos, masmorras, chefes e eventos regionais. Deve haver volume suficiente de metas graduais e recompensas resgatáveis ao longo da campanha, sem exigir login diário nem punir ausência. Incluir conquistas de late game com equipamentos Lendários como recompensa; requisitos devem representar marcos raros de progressão/conquista. Claims precisam ser idempotentes, e equipamentos concedidos devem ser instâncias únicas registradas no save.

#### Catálogo proposto para a campanha

As metas abaixo complementam o catálogo atual, evitando apenas repetir contadores já existentes. Recompensas econômicas são faixas iniciais de design, não valores finais de balanceamento. Cada conquista é resgatável uma vez por save; requisitos secretos podem permanecer ocultos até serem descobertos.

| Trilha | Conquista | Requisito | Recompensa proposta |
|---|---|---|---|
| Elenco | Companhia Completa | Manter 20 mercenários ativos simultaneamente | Ouro e XP da guilda |
| Elenco | Cinco Caminhos | Manter ao menos um mercenário de cada classe inicial | Ouro e materiais diversos |
| Elenco | Sangue de Elite | Contratar 5 mercenários Raros ou superiores | Ouro e XP da guilda |
| Elenco | Mãos Especializadas | Ter 5 mercenários ativos com profissões diferentes | Materiais de coleta |
| Contratos | Caçadores de Elite | Concluir 25 contratos de Rank A ou superior | Ouro e XP da guilda |
| Contratos | Lenda da Vigília | Concluir 10 contratos de Rank S | Cristal especial e XP da guilda |
| Contratos | Companhia em Marcha | Concluir 100 contratos com grupo de 3 ou mais mercenários | Ouro e materiais |
| Coleta | Três Fontes | Completar 50 ciclos de coleta em cada família: madeira, minério e couro | Materiais e XP da guilda |
| Construções | Centro de Poder | Elevar 5 construções ao nível 25 | Ouro e materiais |
| Construções | Obra-Prima | Elevar uma construção ao nível 100 | Cristal especial e XP da guilda |
| Masmorras | Além do Véu | Concluir 5 portais dimensionais | Ouro, materiais raros e influência |
| Chefes | Quebra-Coroas | Derrotar 25 chefes de Rank A ou superior | Ouro e XP da guilda |
| Chefes | O Último Desafio | Derrotar 10 chefes de Rank S | Equipamento Lendário: arma, instância única |
| Região | Guardiões da Pátria | Reduzir a ameaça regional acumulada em 25 pontos por ações da guilda | Influência e reputação |
| Região | Fim da Rebelião | Contribuir para uma rebelião regional bem-sucedida | Ouro, influência e reputação |
| Região | Guilda sem Fronteiras | Contribuir com sucesso em rebeliões de 3 regiões distintas | Equipamento Lendário: armadura de peito, instância única |
| Ferreiro | Mestre do Refino | Refinar 6 equipamentos distintos até +10 | Materiais raros e XP da guilda |
| Códex | Catálogo de Guerra | Descobrir 100 registros de equipamentos no Códex | Ouro e cristal especial |
| Códex | Relíquias Reunidas | Descobrir 10 equipamentos Lendários distintos | Equipamento Lendário: acessório, instância única |
| Legado | Maior Guilda de Mercenários | Alcançar nível 50 de guilda e concluir 50 contratos de Rank S | Equipamento Lendário: elmo, instância única, e reputação |

Os requisitos de região, rank, composição, diversidade de classe/profissão, ciclos e itens distintos devem usar estatísticas persistidas e auditáveis no save. Não inferir progresso de texto de histórico nem de dados que possam ser apagados ao vender/desmontar um item. A recompensa Lendária deve apontar para um template global válido; ao resgatar, criar uma única instância no inventário daquela guilda, gerar seus bônus aleatórios uma única vez e gravar o claim na mesma transação. Repetir uma requisição, restaurar a tela ou reabrir o save não pode duplicar a peça. Seeds de conteúdo são aditivas e não sobrescrevem claims nem progresso existente.

### Tela inicial e saves

A criação de campanha pede somente o nome da guilda. Na lista de saves, cada entrada mostra o nome da guilda como título e, logo abaixo, a região natal sorteada. Remover o nome de campanha duplicado da interface.

### Retorno offline

O botão “Modo Offline” encerra a sessão atual da campanha com salvamento limpo e devolve o jogador à seleção de saves. Ao retomar o save, um pop-up de prestação de contas offline é obrigatório antes da tela principal; deve explicar ganhos, duração processada e estamina restante. A tela inicial não pode confundir trocar de save com encerrar o aplicativo.

Reusar tutorial, Guia do Jogo e o padrão de cards/atalhos existentes. Explicações curtas no contexto: origem e uso de madeira, minério, couro e cristal especial; diferença entre profissão e atividade de coleta; risco versus chance; rank; ciclo regional; por que mercenários ficam busy; capacidade compartilhada do Armazém; e cálculo da ausência.

Backlog consultado: Guia de Classes precisa usar índice visual funcional igual ao Guia do Jogo; Guia de Tiers deve apresentar Comum–Mítico como raridades para mercenários/equipamentos, sem representar T1–T8 na interface. Equipamentos devem comunicar refino `+N` e nível mínimo de uso quando aplicável.

Introdução recomendada: primeira sessão guiada por 2–3 objetivos opcionais e uma recomendação de próxima decisão. Não criar tutorial extenso antes de validar se o fluxo de coleta/contratos é intuitivo.

## 21. Progressão do nível 1 ao 50

| Faixa | Experiência que deve ser apresentada | Marco verificável (proposta) |
|---|---|---|
| 1–10 | guilda, contratação, primeiros upgrades, coleta e contrato simples | designar o primeiro coletor e perceber mercenário busy; adquirir primeiro material com fonte identificada. |
| 11–20 | profissões, equipamentos, crafting/refino inicial, equipe e masmorra | produzir ou melhorar equipamento e concluir conteúdo de grupo de forma acessível. |
| 21–30 | classe/especialização, materiais intermediários e composição | primeira escolha de investimento econômico contra combate. |
| 31–40 | ranks intermediários, rivais e influência | ver região reagir a mais de um ciclo e escolher atividade prioritária. |
| 41–50 | chefes/dungeons de alto risco, equipamento refinado e eventos | completar ciclo regional de ponta a ponta com resultado explicável. |

Esses marcos não substituem requisito de gameplay já existente e não são resultado de playtest. Em cada faixa medir tempo real por perfis, percentual de atividades possíveis, escassez líquida por material e primeira ocorrência de decisão estratégica.

## 22. Fórmulas e parâmetros de balanceamento

### Fórmulas atuais confirmadas

| Regra | Implementação atual observada | Arquivo |
|---|---|---|
| XP próximo nível mercenário | `xp_required = max(1, level) × 100` | `app/services/balance_service.py` |
| Poder base | `power + floor(vitality/2) + floor(agility/2) + floor(intelligence/2) + floor(luck/3) + floor(armor/2)`; resumo com equipamento agrega atributos equipados | `app/services/balance_service.py`, `equipment_service.py` |
| Bônus de progressão por raridade | Common 0%, Uncommon 1%, Rare 2%, Epic 3%, Legendary 4%, Mythic 5% | `balance_service.py` |
| Chance por poder | ajuste por razão poder/recomendado; acima do recomendado até +15; abaixo pode penalizar até -40; depois combina classe/equipe/skills/raridade/construção e limites por conteúdo | `balance_service.py`, `equipment_service.py`, `mission_service.py`, `dungeon_service.py` |
| Bônus Campo de Treino | XP mercenário + nível %, clamp no nível máximo atual | `building_balance_service.py` |
| Escritório | grupo 1/2/3/4/5 por marcos; bônus recompensa máximo 10%; redução duração máximo 10% | `building_balance_service.py` |
| Exploradores | multiplicador x1 antes do nível 5, x2 a partir de 5, x3 a partir de 10; bônus loot máx. +10 p.p.; duração máx. -15% | `building_balance_service.py` |
| Offline desktop | mínimo 300s, teto 28.800s; base gold 5/h; gold acrescenta nível guilda−1, mercenários×2 e Armazém//5 por hora; atualmente materiais derivados de 60%/40% da taxa e Armazém adiciona quantidade | `game_balance.py`, `offline_progress_service.py`, `desktop/clock_guard.py` |
| Guilda | XP de próximo nível `120 + (level−1)×30`, teto 100 | `game_balance.py`, `guild_progression_service.py` |
| Construções | clamp nível 0–50; curva de custo por blocos em `building_cost_factor` | `building_balance_service.py` |
| Crafting | 12 receitas geradas por raridade; desbloqueios Common1, Uncommon5, Rare15, Epic25, Legendary40, Mythic50; slots 3+level//10 até 8; rotação 24h→4h | `crafting_service.py` |
| Refino | disponível Ferreiro nível 10; caps por raridade 3/5/7/10/12/15; custo base 100 gold e 5 minério multiplicado por upgrade e tier | `game_balance.py`, `crafting_service.py` |
| Desmontagem | espaços Ferreiro 1/25/50; fee por espaço 50/150/300 por unidade; tempo reutiliza raridade×tier×quantidade; 1–3 materiais RNG por item | `salvage_service.py` |
| Mercado | duração base por raridade: 10/25/60/180/600/1200s × tier × quantidade, reduzida por Mercado | `game_balance.py`, `market_service.py` |

### Revisões necessárias antes de alterar

- Rebalancear idle passivo quando coleta atribuída entrar; calcular renda total de gold separada de materiais.
- Recalibrar quantidade/tempo da coleta usando demanda por upgrade/receita e teto offline, não valor isolado por segundo.
- Verificar `GuildResources` versus `GuildInventoryItem`/material canônico e sincronização para evitar tesouro e inventário divergirem.
- Verificar stack de bônus de loot e chance em mission/dungeon (profissão, skill, edifício, raridade, equipamento) para evitar overcap e double dip.
- Reexecutar balanceamento das faixas 1–50 com conteúdo da campanha de teste, mudanças atuais e perfil de equipamento; regra antiga de `08-BALANCE-RULES.md` para chance é obsoleta frente ao serviço atual.
- Medir o valor esperado de equipamento por run e a chance agregada com múltiplos drops, especialmente chefes.

Nenhum valor novo de produção, ciclo, chance regional ou frequência de eventos está aprovado neste GDD.

## 23. Simulações e indicadores de validação

### Ferramentas e evidência disponível

- `app/services/progression_simulation_service.py`, scripts em `scripts/` e `tests/` oferecem base para estudos de progressão/conteúdo; confirmá-los contra schema e regras atuais antes de usar.
- `reports/content_balance_report.md`, `relatorio_qa_progressao_end_to_end.md`, `estudo_balanceamento_masmorras_chefes.md` e JSONs foram atualizados em junho de 2026. São fotografias históricas. Por exemplo, o relatório antigo estima 54 missões e 78 coletas para nível 1–10 e estima renda/tempo; isso não foi reexecutado nesta auditoria, não é meta validada e pode depender de conteúdo antigo.
- Testes existentes incluem estudos de balance e desmontagem, mas executar uma suíte não foi parte desta entrega documental.

### Matriz de simulação futura

Para cada parâmetro comparar seed atual e proposta, com 1.000+ trajetórias ou intervalo de confiança apropriado, seed reproduzível e banco-fixture versionado:

1. Níveis 1–50 em 5 faixas, com chance de falha e multiplicadores reais.
2. Produção por mercenário/hora online e até 8h offline efetivamente disponíveis pela estamina, com/sem profissão, ferramenta, Armazém e número de trabalhadores.
3. Balanço material: estoque inicial + fontes − construção/crafting/refino/desmontagem/mercado por hora e por marco.
4. Ouro: contratos, idle, contratação, upgrade, Mercado e Docas; tempo de recuperação após despesa.
5. Contratos por ciclo: sessões de 1, 3, 5 mercenários e elenco máximo; número de runs concluídas, falhas e espera.
6. CPU: distribuição de resultados por perfil; vantagem de jogador e dispersão de reputação/influência após 10/50/100 ciclos.
7. Eventos: incidência, duração, recuperação e probabilidade de eventos repetidos/cadeia infinita.
8. Drops: P(any equipment), P(rarity), quantidade/material por ciclo e efeito de skill/building/multiplicador.

### Perfis e métricas

Perfis: muito ativo (várias sessões/dia), casual (sessões curtas/dia), offline predominante (retorno após até 8h de estamina), produtor (prioriza trabalhos) e combate (prioriza contratos). Métricas: tempo até segundo mercenário, primeiro upgrade, primeiro equipamento produzido, primeira masmorra e primeiro evento; materiais/h por família; gold líquido; taxa de ocupação; runs concluídas por vigília; chance de crise; dispersão de progressão; ações obrigatórias/decisões relevantes por sessão; ganho e consumo de estamina.

**Critério:** publicar artefatos de resultados em etapa futura, com data, commit, versão do conteúdo, inputs e seed. Sem isso, números permanecem hipóteses.

## 24. Riscos e estratégias de mitigação

| Risco | Mitigação / verificação |
|---|---|
| Produção material excessiva | teto de horas/ciclos, taxa vinculada a demanda, simular com 1/3/5/20 coletores, retirar idle de materiais. |
| Material sem uso | bloquear ativação de recurso no conteúdo até haver fonte, dreno e explicação visível; dashboard de supply/demand. |
| Inflação de ouro / conversão Docas→desmontagem | medir margens de compra, desmontagem e venda; limitar preço/custo/quantidade; não dar lucro esperado garantido ao desmontar compra. |
| Cristal abundante ou impossível | fonte com limite diário/ciclo e drenos claros; validar distribuições em perfis. |
| Poucos mercenários no início | coleta opcional, não ocupar toda a escala; manter ao menos uma rota de combate e objetivo inicial acessível. |
| Profissão sem impacto ou bônus acumulado | uma vantagem principal, teste pareado com mercenário sem profissão e cap explícito. |
| Equipamento irrelevante | comparar chance/poder e taxa de conclusão com/sem item; garantir exibição do efeito. |
| Falhas frustrantes | chance estimada honesta, garantia de XP de falha conforme regra, conteúdo de recuperação e análise de streak. |
| Excesso de ofertas/ciclos | limitar opções úteis por região e apresentar recomendação/filtros; não exigir completar a lista. |
| Rivais CPU idênticas/fortes demais | perfis, seeds determinísticas, bandas de dificuldade por estágio e teste de dominância. |
| Reputação sempre 100 ou em queda irreversível | ganho/decay limitado, recuperação, múltiplos estilos de contribuição; simular 100 ciclos. |
| Invasões consecutivas | cooldown, controle de risco e teto de eventos simultâneos; evento não pode apagar progresso. |
| Manipulação de relógio/save | reutilizar ClockGuard, ledger idempotente, backups e explicar limite offline; nunca alegar invulnerabilidade. |
| Vigília 6h x teto offline de 8h | processamento de múltiplos ciclos em ordem, snapshot/ledger por ciclo e clamp pela estamina; teste 6h/8h/24h. |
| Crash/duplicação | transação única para reward+cursor+evento; retries com chave única por campanha/ciclo/tarefa. |
| Saves legados | migration SQLite segura, backup prévio, compatibilidade e teste de rollback/restauração. |
| Catálogo muito grande/consulta lenta | ofertas materializadas por ciclo, filtros SQL por faixa, índices e limite do board; profile antes/depois. |
| UI sobrecarregada | dashboard de tarefa/risco/retorno, drill-down contextual, evitar expor todas as métricas ao novato. |

## 25. Impactos técnicos e persistência

### Arquitetura a preservar

Python, FastAPI local, Jinja2, SQLAlchemy, SQLite por campanha, Alembic e serviços de domínio. Nenhum worker/scheduler externo: o ciclo regional é lazy-evaluated ao abrir/usar campanha. Dados globais de catálogo continuam versionados por pacote; estado de jogador/CPU/região fica no save da campanha.

### Modelagem conceitual (não é migration pronta)

- `GatheringNodeTemplate` ou extensão de conteúdo versionado: família, região, faixa, ciclo e requisitos.
- `GuildWorkAssignment` + `GuildWorkMember`: ocupação, alvo, início, último checkpoint/ciclo resolvido, resultado e estado.
- `ResourceLedgerEntry`: campanha/guilda, source, ref, período, família/quantidade, idempotency key e versão da regra.
- `RegionalCycle`, `RegionState`, `RegionalOffer`, `RivalProfile`, `RivalCycleResult`, `RegionalEvent`, `RegionalHistoryEntry` conforme menor recorte utilizável.
- Snapshot de oferta/run: rank, chance/recomendação, recompensas, conteúdo/versão, participantes e modificadores. Mudança futura de balance não altera runs abertas nem histórico encerrado.

### Invariantes

1. Uma instância de mercenário pertence a no máximo uma atividade incompatível por vez.
2. Uma recompensa por chave de ciclo/atividade/período só pode ser registrada uma vez.
3. Totais apresentados no tesouro e inventário devem vir de uma fonte canônica ou ser sincronizados por uma transação documentada.
4. RNG de campanha simulado deve ser reprodutível em QA sem rerrolar runs antigas.
5. `campaign_id` delimita todos os dados de mundo e não é aceito como autorização do cliente sem resolução no servidor local.
6. Seeds de conteúdo não sobrescrevem configuração persistida/estado de campanha.
7. Alterações de schema/content têm versionamento, backup, compatibilidade e recuperação.

### Módulos prováveis

`app/models`, `repositories`, `services` (offline, clock guard, gathering, regional cycle, mission/dungeon, guild progression, inventory), rotas/templates de Coleta/Quadro/Região/Histórico, `core/game_balance.py`, `seeds/`, scripts de balance e testes. Não começar pela UI antes dos invariantes e dos serviços transacionais.

## 26. Roadmap incremental

### Etapa 0 — Auditoria executável e baseline

- **Objetivo:** congelar situação atual e resolver semântica de recursos/tier/nível de construção.
- **Reuso:** serviços, campanhas e testes atuais.
- **Escopo:** fixture offline; inventário das fontes/drain; baseline de balance 1–50 e contratos/drops; confirmar versão de relatórios; corrigir backlog de guias quando priorizado.
- **Dependências:** nenhum novo modelo de gameplay.
- **Riscos:** baseline dependente de conteúdo atual e muitas seeds.
- **Aceite:** simulações reproduzíveis; dicionário de recursos; decisão explícita sobre max de construção e termos tier/item level.
- **QA:** validar fixtures sem abrir saves reais; snapshots de outputs e seeds.
- **Valor ao jogador:** clareza do estado e promessa de progressão validada antes de adicionar sistemas.

### Etapa 1 — Economia essencial e Coleta designada

- **Objetivo:** trabalhador designado ser fonte principal de materiais e conectar profissões, equipamentos e Ferreiro.
- **Reuso:** busy/status de mercenário, profissão, inventário, construção, ClockGuard, receitas.
- **Novas funções:** nós de coleta, atividade persistida, ciclos idempotentes, interface de designação e resumo offline.
- **Dependências:** baseline; decisão sobre retirar passivo wood/ore, couro/cristal e fonte canônica de inventário.
- **Riscos:** inflação e bloquear elenco todo.
- **Aceite:** exclusividade; produção online/offline mesma regra; comando explícito para iniciar modo offline; taxa/cap de estamina; uma concessão por período; ferramentas/profissão não multiplicam indevidamente; sem fonte passiva duplicada.
- **QA:** iniciar pelo botão, retornar à seleção, retomar save e receber resumo; fechar sem botão, crash/reabrir, rollback de relógio, 5m/6h/8h/24h, estamina insuficiente, múltiplos trabalhadores, arredondamento e transação.
- **Valor:** escolher entre produzir materiais e executar contratos com cada mercenário.

### Etapa 2 — Quadro de Contratos e ranks

- **Objetivo:** reduzir repetição sem perder conteúdo/run.
- **Reuso:** MissionTemplate/Run/members, filtros por faixa, drops e claim manual.
- **Novas funções:** ofertas por ciclo, ranks E–S, snapshot, expiração/renovação.
- **Dependências:** parâmetros de rank, catálogo curado, ligação de faixa com recomendação.
- **Riscos:** board vazio, ranking sem diferença de recompensa, conteúdo acima do nível inacessível.
- **Aceite:** vários estilos de contrato; ofertas estáveis no ciclo; sem run duplicada; oferta não obriga completude; chance e loot exibidos com clareza.
- **QA:** expiração com run ativa, reload, save migration, seed determinística, idioma e filtros.
- **Valor:** escolha contextual por recompensa/risco, não procurar entre centenas de templates.

### Etapa 3 — Vigília e Estado Regional básico

- **Objetivo:** mundo atualiza em ciclo e explica mudança.
- **Reuso:** runs já concluídas, reputação atual, resumo/histórico, ClockGuard.
- **Novas funções:** um ciclo lazy, uma região, segurança/ameaça/reputação/influência e histórico.
- **Dependências:** calendário e regra idempotente; etapa de board.
- **Riscos:** ciclo 6h incompatível com timeout, atualização repetida ou perda quando jogador ausente.
- **Aceite:** abrir depois de 6/8/24h processa ciclos em ordem uma única vez; resumo inclui causas; ausência não perde recompensas já iniciadas.
- **QA:** dois ciclos sem abrir, relógio alterado, crash entre snapshots, repetição e performance.
- **Valor:** impacto persistente de atividades da guilda.

### Etapa 4 — Rivais CPU, portais e eventos

- **Objetivo:** competição regional comparável e eventos com consequências reversíveis.
- **Reuso:** composição, chance, dungeon/boss e catálogos.
- **Novas funções:** perfis CPU, alocação/resultado, eventos e contratos encadeados.
- **Dependências:** etapa 3 estável e perfil de equilíbrio.
- **Riscos:** vantagem CPU artificial, cascata de crise e custo de simulação.
- **Aceite:** perfis claramente distintos; seed/replay estável; rival não domina sistematicamente; evento surge e se resolve uma vez.
- **QA:** 10/50/100 ciclos, runs Monte Carlo e estabilidade de save.
- **Valor:** região responde e oferece objetivos novos sem multiplayer.

### Etapa 5 — Progressão, preparação e balance até 50

- **Objetivo:** validar campanha completa com múltiplas atividades e decisões.
- **Reuso:** construção, skill, crafting, refino, mercado, Docas, Codex e tutorial.
- **Novas funções:** só melhorias justificadas pelas simulações (preparação e encadeamentos são candidatas, não obrigação).
- **Dependências:** etapas 1–4 e resultados reproduzíveis.
- **Riscos:** escopo excessivo e crescimento de menus.
- **Aceite:** perfis ativo/casual/offline/produtor/combate alcançam marcos sem rota única obrigatória; economia estável; fricção e metas documentadas.
- **QA:** campanha automatizada 1–50, inspeção manual e migração de save anterior.
- **Valor:** campanha com loop coerente, progressão visível e motivos para alternar atividades.

## 27. Critérios de aceite por etapa

| Gate | Critérios transversais de aceite |
|---|---|
| 0 | Cada regra tem fonte, dreno, métrica e classificação; baseline reproduzível; ambiguidades de tier e nível decididas. |
| 1 | Atribuição persiste; status busy correto; matemática online/offline compartilhada; reward ledger idempotente; sem materiais de idle passivo redundantes. |
| 2 | Board faz snapshot; rank e recomendação distintos; filtro consulta somente oferta ativa; missões longas e run em andamento não quebram. |
| 3 | Ciclo processado sem worker, ordenado e idempotente; save nunca retrocede; resumo regional explica deltas. |
| 4 | CPU determinística, perfilada e limitada; rivalidade não exige internet; eventos testados para repetição e recuperação. |
| 5 | Tabela de balance reporta os cinco perfis e faixa 1–50; sem economia infinita; UI não exige sessão longa; testes de regressão/campanha passam. |

Todos os gates incluem: testes unitários e integração SQLite; validação de migração com save antigo e backup; transações em sucesso/falha; PT-BR; acessibilidade visual básica; logs diagnósticos sem segredo/save pessoal; teste de não regressão das mecânicas desktop existentes.

## 28. Pendências e decisões de design

### Decisões refinadas nesta rodada

Estas decisões substituem hipóteses conflitantes registradas nas seções anteriores:

- Idle: manter ouro passivo com a fórmula existente (base + guilda + mercenários contratados + Armazém), removendo madeira/minério passivos. Ao completar 8h offline reconhecidas: 1 cristal especial no máximo por retorno. Cristal e ouro não ocupam capacidade.
- Coleta inicial: madeira, minério e couro; uma atividade por material, um mercenário por atividade. A coleta continua até retirada ou Armazém cheio; ao lotar pausa mantendo o mercenário ocupado e retoma quando abrir espaço.
- Ritmo de coleta para teste: 1 unidade-base por minuto; bônus de profissão, ferramenta e construção somam chance de unidade extra, limitada a 45% por ciclo. Produção excedente ao espaço restante é perdida. Valores ainda exigem simulação.
- Progresso: online contínuo até a capacidade; offline iniciado apenas pelo botão “Modo Offline”, limitado pela estamina e pelo teto de 8h. Fechar/crash/queda de energia não inicia progresso offline.
- Armazém: capacidade inicial compartilhada de 1.500 unidades acumuláveis; cada unidade conta 1. Equipamentos únicos ficam fora. Armazém aumenta capacidade por marcos (preferência a cada 5 níveis) e nível da guilda dá bônus menor. Números dos marcos pendentes.
- Mundo/Vigília: 5 regiões com 5 guildas cada, região natal aleatória. Na região do jogador: jogador + 1 rival forte + 1 médio + 2 novos; nas demais: 1 forte + 1 médio + 3 novos. Rivais são dimensionados pelo estágio da região, e o forte estabiliza sua região apenas por tempo limitado.
- Ofertas por Vigília de 6h: 10 contratos, 3 masmorras e 1 chefe por região. O limite de 3 por rank aplica-se somente aos contratos. Meta inicial de late game: 5–6 contratos B–S por painel de 10. Masmorra de portal é adicional. Rank S parte de 1% por espaço de contrato no início e cresce por pesos graduais conforme nível da guilda e força do elenco. Odds permanecem ocultas, com explicação no Guia do Jogo.
- Indicadores regionais: escala 0–100; sem ações em uma Vigília, ameaça +1 e segurança -1. Sucesso/falha altera indicadores por rank e contribuição. Reputação sobe com sucesso e cai com falha; influência reflete participação/sucesso ponderados pelo rank.
- Eventos regionais: portal pode surgir a partir de ameaça 70, com 5% de chance inicial por Vigília e crescimento gradual até 25% em ameaça 100. Rebelião pode ser sorteada com ameaça ≥85 e segurança ≤25.
- CPU e ausência: rivais evoluem offline. Ao reabrir, simular todo o tempo transcorrido e processar cada Vigília vencida uma única vez; a estamina/teto offline do jogador não limita a CPU. Fazer catch-up determinístico e em lote.
- Ranking global: pontuação persistente de 50% influência, 25% reputação e 25% vitórias em eventos. Eventos pontuam por sucesso e contribuição ponderados pelo rank. Atualizar a cada Vigília, sem reset na campanha.
- Falhas regionais: contratos, masmorras e chefes concedem 25% do XP normal, sem ouro nem loot.
- Masmorras/chefes: distribuição própria; masmorras usam pesos regionais com leve viés para cima e o chefe tende ao rank mais alto da rodada.
- Suprimento: uma escolha consumível por grupo dá +5 pontos percentuais de chance de sucesso. Custo/recursos/esforço escalam do rank E ao S, não superam o valor econômico da vitória e devem ser testados contra o retorno esperado incremental.
- Equipamentos: interface mostra raridade Comum–Mítico, refino `+N` e nível mínimo quando aplicável; T1–T8 não aparece como tier/raridade. Cristal é recurso especial e gema é material distinto.
- Construções: teto planejado de nível 100; revisar limite central, custos e marcos para compatibilidade.
- Catálogo em campanha existente: preservar saves, histórico e ofertas/runs já geradas. Conteúdo novo entra nas próximas Vigílias, sem rerrolar atividade atual; mudanças de catálogo afetam apenas novas gerações.
- Força da guilda: soma do poder total de todo mercenário contratado e não demitido, equipado ou não quando equipamento afeta seu poder; ocupado ou disponível. Demitidos são excluídos.
- Rivais CPU: simulação de jogador completo com mercenários, recursos, profissões e decisões individuais; sem IA generativa. Arquétipos fixos de expansão, segurança, contratos e exploração, com variação pequena por RNG; elenco inicial: forte 5, médio 3, novo 1.
- Ranks altos: nível da guilda e força total contribuem juntos, elevando gradualmente os pesos; proporções serão calibradas por simulação, sem marcos rígidos de desbloqueio.
- Portais: ameaça aumenta a chance de surgimento e RNG define o momento; uma masmorra especial culmina em chefe, dura 3h para iniciar, aceita uma entrada por guilda e tem execução por rank/perigo (mínimo 1h). No máximo um por região; loot exclusivo com chances melhores, não garantido.
- Rebelião: ameaça alta + controle regional insuficiente e RNG; duração 12h, no máximo uma no mundo. Surge apenas com campanha aberta. Ao aceitar, jogador tem 1h de prioridade; timers de prioridade e evento avançam offline. Sem resposta em 1h ou recusa explícita delega à CPU por 12h.
- Rebelião cooperativa: várias guildas podem ajudar com várias atividades, limitadas por mercenários/requisitos. Resultados agregados por sucesso/falha; recompensas e influência proporcionais à contribuição, moderadas e por rank, potencialmente um pouco melhores que atividade natal. Visitantes também recebem influência para a região natal; relatório exibe o estado final da região afetada.
- Campanhas/saves: pedir apenas o nome da guilda; o save usa esse nome como título e mostra a região natal sorteada abaixo.
- Modo offline: save novo começa com 8h de estamina. Após o primeiro uso, cada hora online carrega 2h até o teto de 8h. Exigir botão explícito dentro da campanha; o botão salva e retorna à seleção de saves. Retomar mostra um resumo modal obrigatório uma única vez; fechar/crash não iniciam progresso.
- Conquistas: catálogo proposto com 20 metas complementares de elenco, contratos, coleta, construções, masmorras, chefes, região, Ferreiro, Códex e legado. Quatro marcos tardios concedem equipamento Lendário único; métricas persistidas, claims transacionais/idempotentes e seeds aditivas.

### Decisões ainda abertas

1. Fórmula/curvas completas dos pesos E–S e thresholds de força/nível para atingir, entre outras metas, 5–6 ofertas B–S no late game; curva entre os pontos de chance de portal já escolhidos.
2. Magnitudes por rank/contribuição para mudanças de segurança, ameaça, reputação e influência; pontos de partida precisam de simulação.
3. Perfis/economia detalhados da CPU e orçamento máximo de processamento/save para catch-up offline.
4. Custos e quantidades concretos dos suprimentos por rank; validar +5 p.p. contra retorno esperado e limite de custo definido.
5. Equilíbrio de loot por rank; simular chefes e chances agregadas de drops independentes. XP em falha já está definido como 25%.
6. Implementar teto de construções em 100, recalibrar custos/marcos e validar compatibilidade com saves existentes.
7. Implementar versionamento do catálogo: novos dados afetam apenas ofertas futuras; validar campanhas antigas e snapshots.
8. O GDD do RPG Medieval não foi localizado; decisões atuais seguem este documento e podem ser comparadas quando a referência estiver disponível.
9. Validar benchmarks e selecionar conceitos úteis sem copiar números/regras.

## 29. Sugestões adicionais da auditoria

| Problema observado | Sugestão | Benefício | Complexidade | Dependências | Prioridade |
|---|---|---|---|---|---|
| Tesouro numérico e inventário podem ter espelho de materiais | ledger/resource balance checker e fonte canônica para wood/ore/crystal | evita divergência de saldo e facilita QA/economia | Média | baseline e inventário | P0 antes da coleta |
| Catálogo amplo e nomes com sufixos de sequência | seleção curada por região/ciclo usando templates existentes, preservar ID de conteúdo | variedade mecânica legível e menos ruído de UI | Média | board/cycle | P1 |
| Desmontagem pode virar compra de material por ouro | teste de arbitragem Docas→desmontagem→venda; ajustar retorno esperado para abaixo do custo líquido | protege economia sem remover escolha de reciclar | Baixa para auditoria, média ajuste | simulação de preços | P0 |
| Ferreiro tem receitas e rotação que podem ser entrada da produção | ferramentas de coleta como output de crafting e sink de materiais | cria ligação profissão–coleta–Ferreiro | Média | etapa 1, economia | P2 |
| Recompensa de missão é resolvida ao claim, ciclos do mundo não | separar explicitamente timer, resultado resolvido e prêmio coletado no ledger | reduz duplicidade e esclarece ausência | Média | modelo de execução/ciclo | P0 |
| Bonuses de chance e drop vêm de várias camadas | painel de contribuição explicável e cap por fonte/efeito centralizado | decisões comparáveis e menos bugs de stacking | Média | baseline de fórmulas | P1 |
| Metas podem virar checklist obrigatório | objetivos opcionais por recomendação contextual com ignorable state | orienta sem transformar gestão em trilho | Baixa | tutorial/guias | P2 |
| Nível de construção em seed difere do clamp | verificador de catálogo que detecta requisito inalcançável e defaults fora do range | impede conteúdo bloqueado por dado impossível | Baixa | decisão nível max | P0 |
| Runs e templates têm versões de regra distintas | persistir snapshot/versionamento em execução e ciclo | updates não alteram runs antigas | Média | modelo de save | P1 |

Benchmarks conceituais: em Melvor Idle, olhar para separação de habilidades de coleta/processamento e cadeias, não para seus números; fontes públicas consultadas incluem a wiki de habilidades/Harvesting. Em Idle Clans, a referência útil é que tarefas/skills persistem offline com limite e que produção se integra a melhorias de clan, mas seu formato é multiplayer e não deve ser copiado. Em Milky Way Idle, filas/ações repetíveis e distinção entre coleta e processamento ajudam a pensar em fallback e cadeia. Em Legends of IdleOn, distribuição paralela de personagens por atividade é inspiração para custo de oportunidade, mas GIM tem elenco pequeno e gestão por guilda, não múltiplos avatares individuais.

Referências consultadas em 27/10/2026: [Melvor Idle — Harvesting](https://wiki.melvoridle.com/w/Harvesting), [Idle Clans — site oficial](https://www.idleclans.com/idle-mmorpg/), [Idle Clans — press kit](https://www.idleclans.com/press), [Milky Way Idle — Skills](https://milkywayidle.wiki.gg/wiki/Skills), [Milky Way Idle — Gathering](https://milkywayidle.wiki.gg/wiki/Gathering). São referências de conceitos públicos; não servem para afirmar dados internos nem para replicar regras.

## 30. Matriz de rastreabilidade de requisitos e ideias

| Ideia ou funcionalidade | Origem | Estado atual | Mudança proposta | Etapa |
|---|---|---|---|---|
| Campanha desktop, offline, SQLite e janela própria | GDD Guild Idle Manager (`docs/GDD_DESKTOP_OFFLINE.md`) | Implementado segundo auditoria de aceite; limites de plataforma documentados | Preservar arquitetura, saves e ClockGuard | Todas |
| Guildas CPU | GDD RPG Medieval descrito no pedido | Não localizado/implementado | Perfis determinísticos por campanha; sem IA generativa | 4 |
| Regiões e territórios | GDD RPG Medieval descrito no pedido | Ausente | Estado regional persistente por campanha | 3–4 |
| Contratos Rank E–S | GDD RPG Medieval + Diretriz | Ausente como rank; missions/templates existem | Snapshot/board rotativo por rank, nível/poder recomendado | 2 |
| Reputação | Código atual + GDD RPG Medieval | Existe valor `Guild.reputation`; consequência regional não confirmada | Preservar e conectar a contratos/ciclo sem reutilizar para outros eixos | 3 |
| Segurança regional | GDD RPG Medieval + Diretriz | Ausente | Estado regional separado | 3 |
| Ameaça regional | GDD RPG Medieval + Diretriz | Ausente | Ameaça alimenta eventos e ofertas | 3–4 |
| Simulação de sucesso/falha de contratos CPU | GDD RPG Medieval | Ausente | Simulação determinística, com perfil/risco, por ciclo | 4 |
| Portais dimensionais | GDD RPG Medieval | Ausente | Eventos de ameaça podem abrir masmorra limitada no ciclo | 4 |
| Chefes ligados às ameaças | GDD RPG Medieval | Chefes existem, ligação regional ausente | Ligar boss/evento ao estado de ameaça e registrar causa | 4 |
| Eventos provocados pelo desempenho | GDD RPG Medieval + Diretriz | Ausente | Gatilhos explícitos, reversíveis e versionados | 4 |
| Progressão de classes/atributos/equipamentos | GDD RPG Medieval + Código atual | Classes, stats, raridade, gear já existem | Reusar; balancear efeito integrado no conteúdo | 5 |
| Consequências persistentes de personagens | GDD RPG Medieval | Parcial: XP, busy, classe/equipamento persistem; consequência regional não | Estado e histórico de atividade persistentes, sem permadeath proposto | 1–4 |
| Recursos madeira, minério, couro, cristais; ouro | Diretriz | Famílias de itens e ouro existem; couro/cristal não consolidado como núcleo | Definir fontes/drenos e unificar vocabulário/totais | 0–1 |
| Secundários com utilidade real | Diretriz | Muitas famílias no catálogo; utilidade varia | Só habilitar família com fonte e dreno explícitos | 0–1 |
| Cadeias wood→planks→gear | Diretriz + Benchmark | Crafting existe; cadeia de tábuas não confirmada | Expandir receitas existentes, não novo motor | 1,5 |
| Ore→bars→weapons/armor | Diretriz + Benchmark | Crafting/refino existem; cadeia explícita não confirmada | Receita de barras com custo de oportunidade | 1,5 |
| Raw leather→treated leather→gear | Diretriz + Benchmark | couro e crafting existem; transformação específica não confirmada | Expandir receitas do Ferreiro | 1,5 |
| Nova área de coleta | Diretriz | Gathering é missão; sem assignment contínuo | Nós e tela de gestão de coleta | 1 |
| Mercenários designados à coleta | Diretriz | Status busy existe, sem assignment | Tarefa persistente e exclusividade | 1 |
| Representação visual de coleta | Diretriz | UI atual usa cards/ícones; animação de produção não confirmada | animação simples opcional, contador/barra sem autoridade própria | 1 |
| Produção `1 unidade/5s` | Diretriz (hipótese explícita) | Não implementada como ciclo | Não adotar sem simulação; valor equivale a 720/h por trabalhador | 0–1 |
| Bônus de profissão | Código atual + Diretriz | bônus percentual de drop por família em missões | Converter/conservar em eficiência de coleta com uma dimensão principal | 1 |
| Idle gold/crystal limitado | Diretriz | Desktop dá gold, wood, ore e 1 crystal no cap | Decidir manter gold/crystal; remover materiais passivos ao lançar coleta | 1 |
| Modo offline manual com estamina | Nova decisão do usuário | Offline atual não depende de comando explícito nem estamina | Botão Modo Offline; +2h estamina por hora online; teto de 8h; retornar à seleção de saves | 1 |
| Atividade designada continua offline | Diretriz | Não há coleta contínua atribuída | processar ciclos até o menor valor entre tempo reconhecido, estamina e teto de 8h, usando ClockGuard e ledger | 1 |
| Estatística offline sem milhares de operações | Diretriz | Offline atual é fórmula direta | fórmula agregada/reproduzível e testável | 1 |
| Resumo offline obrigatório | Nova decisão do usuário + código atual | há resumo de retorno/clock warning, mas não apareceu no teste informado | modal obrigatório ao retomar, pendente até exibição, idempotente e detalhado | 1 |
| Identidade dos saves | Nova decisão do usuário | formulário pede nome de campanha e nome de guilda | usar nome da guilda como título e mostrar região natal abaixo; remover nome duplicado de campanha | 0 |
| Conquistas com recompensas de late game | Nova decisão do usuário | catálogo atual precisa de expansão | variedade de metas resgatáveis; algumas conquistas tardias entregam equipamento Lendário único | 5 |
| Integridade contra alteração de relógio | GDD Guild Idle Manager | ClockGuard DPAPI/high-water/min/cap existente | Reusar; documentar limite e testar com novo ledger | 1,3 |
| Quadro rotativo em vez de repetir catálogo amplo | Diretriz | Templates e filtros por faixa existem | Ofertas materializadas por ciclo; manter conteúdo como catálogo | 2 |
| Ranks para masmorras/chefes | Diretriz | conteúdo e dificuldade existem; rank ausente | rank compartilhado, dificuldade própria de atividade | 2 |
| Reaproveitar nomes, descrições, recompensas, inimigos, timers | Código atual + Diretriz | catálogo existe | Curadoria/rotação, não descarte total | 2 |
| Ciclo de Vigília a cada ~6h | Diretriz (hipótese) | Ausente | lazy evaluation por campanha, duração por parâmetro | 3 |
| Exemplo de 10 contratos/3 dungeons/1 boss | Diretriz (exemplo) | Ausente | tratar como teto candidato, calibrar por disponibilidade | 0,3 |
| Guilda iniciante não precisa completar tudo | Diretriz | Sem ciclo para comparar | ofertas variadas, objetivos opcionais, risco/recomendação | 2–3 |
| Relatório de fechamento da vigília | Diretriz | Histórico de runs existe; relatório regional não | resumo agregado e histórico explicativo | 3 |
| Distribuição por tamanho de elenco | Diretriz | capacidade de alojamento e grupo existem | simular participação possível com 1/3/5+ mercenários | 0–3 |
| CPU com perfis de estratégia | Diretriz + RPG Medieval | Ausente | perfis declarativos, seed/replay | 4 |
| Reputação/segurança/ameaça/influência separados | RPG Medieval + Diretriz | só reputação de guilda, sem estado regional | eixos distintos por região | 3 |
| Eventos e invasões graduais | Diretriz | ausente | gatilho, risco, cooldown, recuperação e histórico | 4 |
| Preparação, suprimentos e táticas | Diretriz | não há snapshot geral de preparação | adicionar depois do loop regional básico | 5 (opcional) |
| Ranking/histórico CPU | Diretriz | Codex/achievements e runs; ranking regional ausente | comparação single-player por período e explicações | 3–4 |
| Mostrar conteúdo futuro sem sobrecarregar | Diretriz + Backlog | Guias e links existem | gates compactos, metas opcionais e dicas contextuais | 1–5 |
| Guia Classes e Guia Tiers | Backlog | pendente no `docs/USER_FEEDBACK_BACKLOG.md` | corrigir índice/âncoras; Common–Mythic, distinguir tier e item level | 0 |
| Benchmark Melvor Idle | Benchmark | não incorporado | estudar coleta/processamento/cadeias, sem copiar valores | 0–1 |
| Benchmark Idle Clans | Benchmark | não incorporado | observar progressão offline delimitada e upgrades comunitários; adaptar a offline single-player | 0–1 |
| Benchmark Milky Way Idle | Benchmark | não incorporado | observar ações repetíveis, filas e fallback, sem copiar conteúdo | 0–1 |
| Benchmark Legends of IdleOn | Benchmark | não incorporado | inspiração para distribuir personagens paralelamente, reduzir escala para roster GIM | 0 |
| Campanha até nível 50 em cinco faixas | Diretriz | jogo vai além de 50; reports antigos cobrem bandas maiores | testar marcos 1–10…41–50 como primeira campanha integrada | 0,5 |
| Perfis ativo/casual/offline/produtor/combate | Diretriz | report passado tem perfil, não necessariamente coleta nova | padronizar harness e resultados reproduzíveis | 0 |
| Riscos de inflação, exploração e crise | Diretriz | economia existente com pontos de arbitragem | métricas e guardrails listados na seção 24 | Todas |
| Roadmap incremental e critérios verificáveis | Diretriz | GDDs anteriores focam MVP de sistemas | usar etapas 0–5 deste GDD e gate de QA | Todas |
| Arquitectura/expansão sem outro motor | GDD Guild Idle Manager + Diretriz | serviços Python/Jinja/SQLAlchemy e campanha SQLite existem | adicionar módulos por domínio e migrations seguras | Todas |
| Salvar tier e RNG por instância | Código atual + Backlog | raridade, tier, item_level e bônus persistem | não recalcular; corrigir vocabulário e validar histórico | 0,5 |
| Testes e relatórios como evidência datada | Diretriz | scripts/relatórios existentes, alguns históricos | incluir seed, commit, data e versão de conteúdo em próxima rodada | 0 |
| Sugestão: ledger de recursos | Sugestão adicional da auditoria | sincronização por repositório existe; risco de duplicação ao expandir | ledger idempotente para fontes/drenos, sem reescrever tudo | 0–1 |
| Sugestão: desmontagem e Docas | Sugestão adicional da auditoria | ambos implementados | avaliar arbitragem antes de ajustar rendimento | 0 |
| Sugestão: snapshots/versionamento das runs | Sugestão adicional da auditoria | templates persistentes e runs; snapshot integral a verificar | congelar parâmetros do ciclo/run para estabilidade | 2–3 |

## Referências internas auditadas

- `docs/GDD_DESKTOP_OFFLINE.md`, `docs/GDD_ACCEPTANCE_AUDIT.md`, `docs/USER_FEEDBACK_BACKLOG.md`, `docs/DEV_DESKTOP.md`.
- `app/docs/01-PRODUCT-CONTEXT.md`, `04-GAME-LOOP.md`, `05-DATABASE-MODEL.md`, `08-BALANCE-RULES.md`, `09-ADMIN-CONFIGURATION.md`, `10-EQUIPMENT-RNG.md`, `14-MVP-020-TO-026-BALANCE-PASS.md`, roteiros PRD e MVP disponíveis.
- Modelos em `app/models/`; regras principalmente em `app/services/`; parâmetros em `app/core/game_balance.py`; conteúdo em `app/seeds/`; testes em `tests/`; scripts em `scripts/`.
- Relatórios: `reports/content_balance_report.md`, `relatorio_qa_progressao_end_to_end.md`, `estudo_balanceamento_masmorras_chefes.md`, `reports/*.json`.

## Declaração de escopo e limitações

- Não foi implementado nenhum sistema, regra, seed, migration ou alteração de save.
- Não foram executados testes automatizados nem simulações durante esta etapa documental; relatórios existentes estão datados e identificados como históricos.
- O banco de dados de campanha não foi alterado nem usado para experimento; conclusões sobre fórmulas vieram de serviços, configuração, modelos e documentação versionada.
- O GDD do projeto “RPG Medieval” não foi encontrado no checkout `App GIM` nem nos documentos locais identificados. Foram usados somente os conceitos descritos pelo usuário na solicitação, sem inventar regras daquele projeto.
- Benchmark consultado é conceitual. Fontes públicas: Melvor Idle wiki, Idle Clans site/press kit e Milky Way Idle wiki. Legends of IdleOn foi avaliado apenas pelo conceito listado no pedido, sem verificação de fonte primária nesta etapa.
- Aprovar este GDD não torna números hipotéticos definitivos. Antes de implementar, concluir as pendências da seção 28 e o Gate da etapa 0.

