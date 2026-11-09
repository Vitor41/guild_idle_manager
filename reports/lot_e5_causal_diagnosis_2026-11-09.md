# E5 — diagnóstico causal e proposta

## Evidência

- **Portal:** o evento consulta somente chefes ativos do bioma `portal`. O catálogo atual tem três: níveis 240/290/339; todos pedem grupo de 5, mercenários níveis 232/282/335, poder total 15.360/19.358/23.560, guilda nível 30/37/43, equipamento Tier 5/6/7 e Exploradores (scouts) nível 1. Nenhuma destas equipes aparece na simulação CPU de 100 Vigílias. Além disso, o planner CPU descarta qualquer chefe com requisito de construção e aplica uma rolagem independente de 25% antes de criar a oferta. O fluxo jogador de portal valida nível da guilda, tamanho do grupo, nível dos mercenários, poder e composição/equipamento; não valida esse campo de construção.
- Há conteúdo ativo de baixo nível que pode ser usado pelo mesmo fluxo para ambos: Varkun (nível 1, poder 60, grupo 1–5, mercenário/guilda nível 1, sem tier, 39 minutos). Hoje ele fica fora da seleção porque seu bioma é `fortress`.
- **Rebelião:** E4 observou 1.035 região-ciclos elegíveis e 220 rolagens selecionadas; 714 elegibilidades foram vetadas pelo cooldown regional de cinco Vigílias e 9 por evento global ativo. A 2% por rolagem selecionada, a expectativa é 4,4 aberturas; foram 6. A taxa não é o erro: a maioria das Vigílias elegíveis não recebe a rolagem. O máximo observado foi uma região vulnerável e uma rebelião ativa por vez.
- **Escolha CPU:** o grupo respeita disponibilidade, tamanho, nível mínimo e requisitos declarados, mas contratos têm poder total requerido igual a zero. O planner ordena primeiro pelo Rank do contrato; não estima a chance com o poder do grupo escolhido. A resolução ainda usa o cálculo de poder normal. O planner não compra nem aplica suprimentos, então sua comparação deve assumir chance/recompensa sem suprimento.

## Mudanças implementadas

1. O planner CPU ordena ações viáveis pelo valor esperado de XP/ouro por duração, usando chance calculada do poder, formação, bônus de classe e risco já congelados. Preferência de arquétipo desempata. Fórmula de resolução, Rank, recompensas e custos não mudaram; o planner não supõe nem compra suprimentos.
2. O sorteio do portal considera chefes ativos do bioma `portal` cujo nível de guilda requerido cabe no estágio atual da campanha, além do chefe introdutório ativo de nível recomendado 1. Evento congela o encontro e o loot no mesmo snapshot para jogador e CPU. O filtro CPU exclusivo para construção foi removido, mantendo equivalência com o fluxo jogador; os requisitos que esse fluxo valida, o limite de 25% de participação CPU e o prazo de 3h seguem em vigor. A regra especial de acesso do chefe introdutório (sem checagem avançada de poder/composição/equipamento) agora também vale para CPU; nível mínimo e tamanho do grupo continuam obrigatórios.
3. Uma Vigília com uma ou mais regiões elegíveis agora escolhe uma para um único sorteio de 2%; sem cooldown regional. A trava global continua permitindo no máximo uma rebelião ativa. O GDD foi alinhado.

Isso amplia a rota de portal sem baixar os chefes existentes nem alterar o contrato Rank C18. A referência Rank C nível 18/grupo 2 continua exigindo poder 144. O bônus de sinergia de formação de +200 poder conta na verificação de requisito de equipe tanto para CPU como para jogador; não altera a chance de resolução CPU nem concede bônus oculto.

## Invariantes e testes do lote

- Chance de resolução CPU segue a mesma função de poder/classe/risco; seleção só muda qual ação e grupo a CPU escolhe.
- CPU nunca inicia com grupo indisponível, fora dos requisitos do snapshot ou que não termina antes do prazo de entrada do portal.
- Um portal usa um único snapshot comum para jogador e CPU; a entrada CPU só gera participação ligada a uma ação resolvida. Sem suprimento implícito.
- Rebelião mantém 2% por tentativa elegível, máximo uma região sorteada por Vigília e máximo uma rebelião ativa.
- Regressões: seleção de contrato/grupo por chance esperada e disponibilidade; entrada em portal de baixo nível versus chefe alto inviável; paridade dos requisitos jogador/CPU; `Rank C18 = poder 144`; chance/cap global de rebelião; e comparação integrada de 20 seeds × 100 Vigílias com os gates E5.

## Validação integrada

Runner de serviços reais com 20 campanhas SQLite descartáveis, seeds `2026110301–2026110320`, 100 Vigílias cada e nenhuma ação do jogador: [resumo detalhado da simulação E5](lot_e5_cpu_strategy_event_2026-11-09.md), com resultados compactos por seed em [CSV](lot_e5_cpu_strategy_event_2026-11-09.csv). Comparação E4 pareada usa as mesmas seeds e os totais integrados E4 já registrados.

| Indicador | E4 | E5 | Resultado |
|---|---:|---:|---:|
| Campanhas com rebelião | 6/20 | 17/20 | Gate >10/20 atingido |
| Rebeliões abertas | 6 | 23 | 978 rolagens selecionadas ×2%; 19,56 esperadas |
| Rebeliões simultâneas máximas | 1 | 1 | Cap preservado |
| Entradas CPU em portal | 0 | 142 | 87 sucessos e 55 falhas |
| XP líquido CPU | 24.555.686 | 25.944.801 | +5,65% |
| Sucesso CPU | 52,64% | 52,31% | −0,33 ponto percentual |
| Portais abertos | 125 | 122 | −3; entradas CPU habilitadas |

No E5 houve 1.016 região-ciclos elegíveis; 978 tiveram rolagem selecionada e 38 foram bloqueados pela rebelião global ativa. Nenhum foi bloqueado por cooldown regional. Testes focados de eventos, funil, Rank C18, política CPU de oferta e requisito de equipamento passaram 32/32. A regressão de campanha completa 100 Vigílias confirmou IDs de ação distintos por guilda, reservas de equipe sem sobreposição e respeito ao prazo de portal; esse teste também foi repetido com as alterações finais de equivalência CPU/jogador. A execução no Windows usou SQLite temporário com `temp_store=MEMORY` e o override local de `platform.machine` para contornar WMI; essas adaptações ficaram fora do código do jogo.
