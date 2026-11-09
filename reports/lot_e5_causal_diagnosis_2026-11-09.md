# E5 — diagnóstico causal e proposta

## Evidência

- **Portal:** o evento consulta somente chefes ativos do bioma `portal`. O catálogo atual tem três: níveis 240/290/339; todos pedem grupo de 5, mercenários níveis 232/282/335, poder total 15.360/19.358/23.560, guilda nível 30/37/43, equipamento Tier 5/6/7 e Exploradores (scouts) nível 1. Nenhuma destas equipes aparece na simulação CPU de 100 Vigílias. Além disso, o planner CPU descarta qualquer chefe com requisito de construção e aplica uma rolagem independente de 25% antes de criar a oferta. O fluxo jogador de portal valida nível da guilda, tamanho do grupo, nível dos mercenários, poder e composição/equipamento; não valida esse campo de construção.
- Há conteúdo ativo de baixo nível que pode ser usado pelo mesmo fluxo para ambos: Varkun (nível 1, poder 60, grupo 1–5, mercenário/guilda nível 1, sem tier, 39 minutos). Hoje ele fica fora da seleção porque seu bioma é `fortress`.
- **Rebelião:** E4 observou 1.035 região-ciclos elegíveis e 220 rolagens selecionadas; 714 elegibilidades foram vetadas pelo cooldown regional de cinco Vigílias e 9 por evento global ativo. A 2% por rolagem selecionada, a expectativa é 4,4 aberturas; foram 6. A taxa não é o erro: a maioria das Vigílias elegíveis não recebe a rolagem. O máximo observado foi uma região vulnerável e uma rebelião ativa por vez.
- **Escolha CPU:** o grupo respeita disponibilidade, tamanho, nível mínimo e requisitos declarados, mas contratos têm poder total requerido igual a zero. O planner ordena primeiro pelo Rank do contrato; não estima a chance com o poder do grupo escolhido. A resolução ainda usa o cálculo de poder normal. O planner não compra nem aplica suprimentos, então sua comparação deve assumir chance/recompensa sem suprimento.

## Menor proposta estrutural

1. Priorizar ofertas CPU pelo valor esperado de XP/recursos por duração, calculado com o poder, composição, disponibilidade e a mesma chance já usada na resolução. Não mudar fórmula, Rank, recompensa, bônus ou custo; não supor suprimento.
2. Manter chefes `portal` atuais e incluir o catálogo ativo de chefes níveis 1–20 no sorteio do boss congelado do portal. CPU e jogador recebem o mesmo snapshot e enfrentam os mesmos requisitos. Remover apenas o filtro CPU de construção que o fluxo jogador não aplica; preservar a rolagem de participação de 25%, os requisitos restantes e o prazo de 3h. A ação continua sujeita ao grupo real e à duração antes do prazo.
3. Rolar 2% em cada região-ciclo elegível, removendo o cooldown regional que impede a tentativa. Preservar no máximo uma região escolhida por Vigília e no máximo uma rebelião ativa global. Esta alteração exige alinhar o trecho correspondente do GDD.

Isso amplia uma rota de portal sem baixar os chefes existentes nem alterar o contrato Rank C18. A referência Rank C nível 18/grupo 2 continua exigindo poder 144. Nenhum bônus escondido será dado à CPU.

## Invariantes e testes do lote

- Chance de resolução CPU segue a mesma função de poder/classe/risco; seleção só muda qual ação e grupo a CPU escolhe.
- CPU nunca inicia com grupo indisponível, fora dos requisitos do snapshot ou que não termina antes do prazo de entrada do portal.
- Um portal usa um único snapshot comum para jogador e CPU; a entrada CPU só gera participação ligada a uma ação resolvida. Sem suprimento implícito.
- Rebelião mantém 2% por tentativa elegível, máximo uma região sorteada por Vigília e máximo uma rebelião ativa.
- Regressões: seleção de contrato/grupo por chance esperada e disponibilidade; entrada em portal de baixo nível versus chefe alto inviável; paridade dos requisitos jogador/CPU; `Rank C18 = poder 144`; chance/cap global de rebelião; e comparação integrada de 20 seeds × 100 Vigílias com os gates E5.
