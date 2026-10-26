# Melhorias para PRD 3 — Curadoria, QA e Balanceamento de Masmorras e Chefes

## Contexto

Este documento complementa os ajustes já tratados nos documentos anteriores de Melhorias para PRD e Melhorias para PRD 2.

A última análise end-to-end apontou que o jogo já possui uma massa ampla de conteúdo para missões, coletas, missões longas, masmorras e chefes. O pacote PRD 2 melhorou a progressão geral, mas também evidenciou um novo ponto de atenção:

```text
Existem muitas masmorras ativas e parte delas tende a ser ignorada por eficiência semelhante, redundância de recompensa ou falta de identidade clara.
```

Este documento deve ser tratado como uma frente específica para estudar, revisar e corrigir o conteúdo de:

- Masmorras.
- Chefes.
- Loot de masmorras.
- Loot de chefes.
- Progressão de dificuldade.
- Progressão de XP, ouro e materiais.
- Relevância por faixa de nível.
- Curadoria de conteúdo redundante.
- Relatório final de QA.

---

# Objetivo geral

Realizar um estudo end-to-end semelhante ao QA de progressão, porém focado exclusivamente em masmorras e chefes, para garantir que esse conteúdo tenha progressão linear, identidade própria, recompensas coerentes e relevância real durante todo o jogo.

O objetivo não é apenas testar. O Codex deve:

```text
Auditar → Simular → Identificar gargalos → Corrigir → Repopular/ajustar seeds → Gerar relatório final .md
```

---

# Diretrizes gerais para o Codex

## 1. Tratar masmorras e chefes como conteúdo de progressão, não apenas conteúdo extra

Masmorras e chefes precisam ter papel claro no loop do jogo.

Masmorras devem ser uma camada acima das missões comuns, entregando:

- Mais dificuldade.
- Melhor chance de equipamentos.
- Melhor chance de raridades intermediárias e altas.
- Recompensas mais atrativas, mas não triviais.
- Uso relevante de composição de mercenários.
- Uso relevante de nível, poder total, classe e profissão quando aplicável.

Chefes devem ser uma camada acima das masmorras, entregando:

- Maior exigência.
- Maior risco.
- Maior chance de recompensas raras.
- Itens mais relevantes.
- Progressão aspiracional.
- Conteúdo que justifique evolução de mercenários melhores, raridades maiores e classes especializadas.

## 2. Não deixar conteúdo redundante ativo sem função

Se existirem várias masmorras ou chefes com:

- Mesmo nível.
- Mesmo tempo.
- Mesma chance de sucesso.
- Mesma recompensa.
- Mesmo tipo de loot.
- Mesmo requisito.
- Mesmo impacto prático.

O Codex deve tomar uma decisão:

```text
Manter e diferenciar
ou
Desativar
ou
Rebalancear
ou
Reposicionar em outra faixa de nível
```

Não deve manter conteúdo duplicado apenas para inflar quantidade.

## 3. Conteúdo pode ser reduzido, mas não deve ficar escasso

O jogo precisa continuar com boa quantidade de masmorras e chefes. Porém, quantidade não pode ser maior que utilidade.

Diretriz:

```text
É melhor ter menos masmorras bem diferenciadas do que centenas de masmorras equivalentes que o jogador nunca usará.
```

## 4. Toda faixa de nível precisa ter função clara

As faixas de progressão consideradas devem seguir o padrão atual do jogo:

```text
1–20
21–50
51–100
101–130
131–200
201–250
251–300
301–350
```

Para cada faixa, validar:

- Quantidade de masmorras ativas.
- Quantidade de chefes ativos.
- Tempo médio.
- XP/h esperado.
- Ouro/h esperado.
- Chance média de sucesso.
- Recompensa média por sucesso.
- Recompensa média ponderada por chance de sucesso.
- Materiais possíveis.
- Equipamentos possíveis.
- Raridades possíveis.
- Conteúdos mais eficientes.
- Conteúdos ignoráveis.
- Conteúdos redundantes.

---

# MVP-059 — Auditoria estrutural de masmorras e chefes

## Objetivo

Mapear todo o conteúdo ativo de masmorras e chefes, entendendo volume, distribuição por faixa, requisitos, recompensas, dificuldade e redundância.

## Escopo

O Codex deve localizar no projeto:

- Models de masmorras.
- Models de chefes.
- Services relacionados.
- Seeds de conteúdo.
- Tabelas de loot.
- Tabelas de recompensas.
- Regras de dificuldade.
- Regras de chance de sucesso.
- Templates/telas de masmorras.
- Templates/telas de chefes.
- Histórico de execuções.
- Scripts de QA existentes.

## Dados mínimos a extrair

Para cada masmorra:

```text
ID
Nome
Status ativo/inativo
Faixa de nível
Nível mínimo
Nível recomendado
Nível máximo, se existir
Tempo de execução
Chance base de sucesso
Requisito de mercenários
Requisito de poder total
Requisito de classe, se existir
Requisito de construção, se existir
XP por sucesso
XP por falha
Ouro por sucesso
Ouro por falha
Materiais possíveis
Equipamentos possíveis
Raridades possíveis
Peso/chance de drop
```

Para cada chefe:

```text
ID
Nome
Status ativo/inativo
Faixa de nível
Nível mínimo
Nível recomendado
Tempo de execução
Chance base de sucesso
Requisito de mercenários
Requisito de poder total
Requisito de classe/composição, se existir
Requisito de construção, se existir
XP por sucesso
XP por falha
Ouro por sucesso
Ouro por falha
Materiais possíveis
Equipamentos possíveis
Raridades possíveis
Peso/chance de drop
Possível item especial, se existir
```

## Critérios de aceite

- Gerar mapa completo de masmorras ativas por faixa.
- Gerar mapa completo de chefes ativos por faixa.
- Identificar conteúdos duplicados ou equivalentes.
- Identificar conteúdos sem recompensa relevante.
- Identificar conteúdos com recompensa desproporcional.
- Identificar conteúdos com chance de sucesso incompatível com a faixa.
- Identificar conteúdos com tempo incompatível com a recompensa.
- Identificar conteúdos que competem mal contra missões normais.
- Identificar conteúdos que competem mal contra coletas.
- Identificar conteúdos que banalizam loot raro.

---

# MVP-060 — Simulação de eficiência de masmorras e chefes

## Objetivo

Simular o desempenho real de masmorras e chefes por faixa para entender quais conteúdos serão usados, ignorados ou abusados pelo jogador.

## Regras da simulação

A simulação deve considerar pelo menos três perfis:

```text
Ativo
Híbrido
Casual/idle
```

Também deve considerar ao menos três cenários de força do grupo:

```text
Grupo fraco: mercenários comuns, baixo equipamento, poder próximo ao mínimo.
Grupo médio: mistura de comum/incomum/raro, equipamentos medianos.
Grupo forte: mercenários de tiers melhores, classes adequadas, equipamentos bons.
```

## Métricas obrigatórias

Para cada masmorra e chefe, calcular:

```text
XP/h bruto
XP/h ponderado pela chance de sucesso
Ouro/h bruto
Ouro/h ponderado pela chance de sucesso
Materiais/h esperado
Equipamentos/h esperado
Valor esperado de loot por execução
Valor esperado de loot por hora
Tempo médio para obter 1 item raro+
Tempo médio para obter 1 item épico+
Tempo médio para obter 1 item lendário+
Taxa de falha esperada
Custo de oportunidade contra missões comuns
Custo de oportunidade contra coleta
```

## Fórmulas conceituais

```text
XP esperado = (XP sucesso × chance sucesso) + (XP falha × chance falha)
Ouro esperado = (Ouro sucesso × chance sucesso) + (Ouro falha × chance falha)
XP/h esperado = XP esperado / duração em horas
Ouro/h esperado = Ouro esperado / duração em horas
Drop esperado = chance de drop × quantidade esperada
Valor esperado = soma ponderada das recompensas possíveis
```

## Comparativos obrigatórios

Para cada faixa, comparar:

- Melhor missão normal da faixa.
- Melhor coleta da faixa.
- Melhor masmorra da faixa.
- Melhor chefe da faixa.
- Melhor rota para XP.
- Melhor rota para ouro.
- Melhor rota para equipamento comum/incomum.
- Melhor rota para equipamento raro+.
- Melhor rota para material.

## Critérios de aceite

- Gerar tabela de eficiência por faixa.
- Gerar ranking de masmorras por XP/h.
- Gerar ranking de masmorras por ouro/h.
- Gerar ranking de masmorras por loot esperado.
- Gerar ranking de chefes por XP/h.
- Gerar ranking de chefes por ouro/h.
- Gerar ranking de chefes por loot esperado.
- Identificar conteúdos dominantes demais.
- Identificar conteúdos inúteis demais.
- Identificar conteúdos equivalentes demais.
- Criar relatório intermediário com recomendações de ajuste.

---

# MVP-061 — Curadoria e redução de redundância em masmorras

## Objetivo

Revisar a massa de masmorras para remover ou corrigir conteúdos redundantes, garantindo diversidade real de uso.

## Problema esperado

A massa atual de masmorras é grande. Parte pode ter eficiência parecida, recompensa parecida ou função parecida.

Isso causa três problemas:

```text
1. O jogador ignora grande parte do conteúdo.
2. O conteúdo parece grande, mas não parece significativo.
3. A manutenção e balanceamento ficam mais difíceis.
```

## Regra de negócio

Cada masmorra ativa deve ter pelo menos uma característica clara de diferenciação:

- Melhor XP.
- Melhor ouro.
- Melhor chance de equipamento.
- Melhor chance de raridade específica.
- Material específico.
- Requisito de classe/composição.
- Menor tempo.
- Maior tempo com recompensa melhor.
- Menor chance, recompensa maior.
- Maior chance, recompensa menor.
- Conteúdo de transição para próxima faixa.
- Conteúdo de farm específico.

## Quantidade sugerida por faixa

A quantidade final não precisa ser exatamente esta, mas deve seguir uma lógica próxima:

| Faixa | Masmorras recomendadas ativas | Observação |
|---|---:|---|
| 1–20 | 8–12 | Introdução simples, baixa complexidade. |
| 21–50 | 12–18 | Começa diversidade de recompensa. |
| 51–100 | 18–25 | Mais tipos de loot e requisitos. |
| 101–130 | 12–18 | Faixa curta, não precisa inflar conteúdo. |
| 131–200 | 25–35 | Faixa longa, precisa variedade real. |
| 201–250 | 18–25 | Conteúdo avançado. |
| 251–300 | 18–25 | Conteúdo pré-endgame. |
| 301–350 | 20–30 | Endgame, variedade e loot relevante. |

## Regras de desativação

Desativar ou substituir masmorras que tenham:

- Mesmo nível e mesma recompensa de outra masmorra.
- Mesmo tempo e mesma chance de sucesso sem diferencial.
- Mesmo loot com eficiência inferior.
- Nome genérico ou repetitivo.
- Baixa chance e baixa recompensa.
- Alta duração sem recompensa proporcional.
- Requisito alto sem retorno proporcional.

## Regras de diferenciação

Quando optar por manter uma masmorra, diferenciar por:

```text
Tema
Tempo
Risco
Recompensa
Loot
Material
Raridade
Classe recomendada
Composição recomendada
Requisito de construção
```

## Exemplos de arquétipos de masmorra

Cada faixa pode conter combinações destes arquétipos:

```text
Masmorra de XP
Masmorra de ouro
Masmorra de equipamento comum/incomum
Masmorra de equipamento raro
Masmorra de material específico
Masmorra curta de baixo risco
Masmorra média equilibrada
Masmorra longa de alto risco
Masmorra de transição para próxima faixa
Masmorra com requisito de classe
Masmorra com chance de item especial
```

## Critérios de aceite

- Reduzir redundância de masmorras ativas.
- Garantir que cada faixa tenha variedade suficiente.
- Garantir que cada masmorra ativa tenha função clara.
- Garantir que nenhuma faixa fique pobre de conteúdo.
- Garantir nomes únicos, naturais e sem sufixos técnicos.
- Atualizar seeds mantendo idempotência.
- Não apagar histórico do jogador de forma destrutiva; preferir desativar conteúdo antigo quando necessário.
- Atualizar relatório de conteúdos desativados.

---

# MVP-062 — Curadoria e progressão de chefes

## Objetivo

Revisar chefes para garantir que sejam conteúdos especiais, relevantes e com recompensa proporcional ao risco.

## Regra de produto

Chefes não devem parecer apenas uma missão com nome diferente.

Chefes devem representar:

```text
Teste de força
Teste de composição
Teste de progressão
Chance melhor de recompensa rara
Motivo para evoluir mercenários e equipamentos
```

## Quantidade sugerida por faixa

| Faixa | Chefes recomendados ativos | Observação |
|---|---:|---|
| 1–20 | 1–2 | Introdução ao conceito. |
| 21–50 | 2–3 | Primeiros desafios reais. |
| 51–100 | 3–5 | Começa variedade. |
| 101–130 | 2–3 | Faixa curta. |
| 131–200 | 5–8 | Faixa longa. |
| 201–250 | 4–6 | Conteúdo avançado. |
| 251–300 | 4–6 | Pré-endgame. |
| 301–350 | 6–10 | Endgame. |

## Regras de diferenciação de chefes

Cada chefe deve ter identidade clara:

- Chefe focado em dano físico.
- Chefe focado em dano mágico.
- Chefe resistente.
- Chefe rápido.
- Chefe que favorece grupo equilibrado.
- Chefe que favorece classe específica.
- Chefe que exige nível alto.
- Chefe que exige poder total alto.
- Chefe de farm de material raro.
- Chefe de chance de equipamento raro+.
- Chefe de progressão/endgame.

## Recompensas de chefe

Chefes devem ter chance maior de:

- Equipamentos raros.
- Equipamentos épicos.
- Equipamentos lendários em faixas altas.
- Materiais raros.
- Cristais.
- Itens especiais, se existirem.

Mas não devem banalizar raridades.

## Regras de chance por raridade

Os valores exatos devem ser calibrados pelo Codex usando simulação, mas seguir esta intenção:

| Conteúdo | Comum | Incomum | Raro | Épico | Lendário | Mítico |
|---|---:|---:|---:|---:|---:|---:|
| Missão normal | Alta | Média | Baixa | Muito baixa | Quase nula | Raríssima |
| Coleta | Média | Baixa | Muito baixa | Quase nula | Nula | Nula |
| Masmorra | Média | Média | Média/baixa | Baixa | Muito baixa | Raríssima |
| Chefe | Média | Média | Alta relativa | Baixa/média | Baixa | Raríssima |

## Critérios de aceite

- Garantir que chefes tenham identidade própria.
- Garantir que chefes tenham recompensa superior a masmorras em raridades altas.
- Garantir que chefes não sejam melhores para tudo ao mesmo tempo.
- Garantir que chefes tenham risco proporcional ao retorno.
- Garantir que chefes tenham nomes únicos e temáticos.
- Garantir que chefes estejam distribuídos por faixa.
- Garantir que cada faixa tenha chefes úteis, mas não excessivos.
- Atualizar seeds de chefes com idempotência.
- Gerar relatório de chefes mantidos, alterados e desativados.

---

# MVP-063 — Rebalanceamento de loot de masmorras e chefes

## Objetivo

Revisar drops de masmorras e chefes para garantir diversidade, progressão por faixa e motivo real para enfrentar conteúdos mais difíceis.

## Problema

Se a taxa de drop for muito parecida entre masmorras, chefes e missões, o jogador vai escolher apenas o conteúdo mais eficiente por tempo.

Se chefes droparem itens bons demais cedo, o jogador pode trivializar a progressão.

Se masmorras não droparem nada relevante, serão ignoradas.

## Regra de negócio

Masmorras devem ser a melhor rota para equipamentos intermediários e bons.

Chefes devem ser a melhor rota para equipamentos raros e superiores.

Missões normais devem continuar úteis para XP, ouro e equipamentos básicos.

Coletas devem continuar focadas em materiais.

## Diretrizes por faixa

### 1–20

- Masmorras devem apresentar o conceito de loot melhor.
- Chefes devem existir como desafio introdutório.
- Não banalizar equipamentos fortes.
- Comum e incomum devem dominar.
- Raro deve ser possível, mas pouco frequente.

### 21–50

- Raro começa a aparecer com mais consistência.
- Chefes podem ter chance moderada de raro.
- Épico ainda deve ser raro.

### 51–100

- Masmorras podem ser boa fonte de raro.
- Chefes podem abrir chance real de épico.
- Lendário ainda deve ser muito raro.

### 101–200

- Épico passa a ser parte da progressão.
- Chefes podem entregar lendário em chance baixa.
- Materiais raros devem ganhar importância.

### 201–350

- Chefes viram principal fonte de itens de alto tier.
- Masmorras continuam relevantes para farm intermediário.
- Mítico deve continuar raríssimo.
- Conteúdo endgame deve exigir mercenários melhores e composições mais fortes.

## Regra de valor esperado

O Codex deve calcular o valor esperado dos drops e validar que:

```text
Valor esperado de Chefe > Valor esperado de Masmorra > Valor esperado de Missão normal > Valor esperado de Coleta
```

Mas sem fazer chefe ser melhor em XP/h e ouro/h ao mesmo tempo.

## Critérios de aceite

- Rebalancear chance de drop por tipo de conteúdo.
- Rebalancear chance de drop por faixa de nível.
- Garantir que masmorras sejam relevantes para equipamentos.
- Garantir que chefes sejam relevantes para raridades altas.
- Garantir que coletas não virem fonte principal de equipamentos.
- Garantir que missões normais ainda possam dropar equipamentos básicos.
- Gerar simulação de 1000 execuções por conteúdo/tipo/faixa.
- Comparar distribuição final contra a distribuição anterior.
- Gerar relatório final em `.md`.

---

# MVP-064 — Rebalanceamento de tempo, chance e dificuldade

## Objetivo

Ajustar tempo, chance de sucesso e dificuldade de masmorras e chefes para que o conteúdo seja justo, arriscado e útil.

## Regra geral

Conteúdos mais difíceis podem ser mais recompensadores, mas não podem ser a melhor escolha universal.

## Diretrizes

### Masmorras

Masmorras devem ter:

- Tempo maior que missões normais, na maioria dos casos.
- Recompensa melhor em loot.
- XP e ouro competitivos, mas não sempre superiores.
- Chance de sucesso coerente com o nível recomendado.
- Requisitos que façam sentido.

### Chefes

Chefes devem ter:

- Tempo relevante.
- Chance de sucesso menor que masmorras equivalentes.
- Recompensa melhor em loot raro.
- Menor eficiência em farm básico.
- Requisito mais claro de nível, poder ou composição.

## Faixas de chance sugeridas

| Tipo | Early | Mid | Late | Endgame |
|---|---:|---:|---:|---:|
| Masmorra fácil | 80–90% | 75–85% | 70–80% | 65–75% |
| Masmorra média | 70–80% | 65–75% | 60–70% | 55–65% |
| Masmorra difícil | 60–70% | 55–65% | 50–60% | 45–55% |
| Chefe introdutório | 65–75% | 60–70% | 55–65% | 50–60% |
| Chefe difícil | 50–60% | 45–55% | 40–50% | 35–45% |
| Chefe endgame | — | — | 35–45% | 30–40% |

## Critérios de aceite

- Ajustar duração de masmorras redundantes.
- Ajustar chance de sucesso por faixa.
- Ajustar dificuldade para grupos fracos, médios e fortes.
- Garantir que grupo comum consiga avançar, mas sofra no endgame.
- Garantir que endgame incentive mercenários de tiers melhores.
- Garantir que chefes não sejam farm trivial.
- Garantir que falha não seja punitiva demais, mas também não seja irrelevante.
- Simular taxa de sucesso esperada por perfil de grupo.

---

# MVP-065 — Curadoria de nomes, temas e identidade narrativa

## Objetivo

Garantir que masmorras e chefes tenham nomes naturais, temáticos e sem marcadores técnicos ou sequenciais.

## Regras de nomenclatura

Não usar nomes como:

```text
Masmorra 001
Cripta 013
Chefe 024
Caverna 1-001
Ruínas 1-014
```

Usar nomes naturais e variados, como:

```text
Cripta dos Sinos Partidos
Covil do Vigia Rubro
Ruínas da Ordem Cinzenta
Fenda do Carvalho Sombrio
Torre do Juramento Quebrado
Ninho da Serpente Antiga
Câmara do Rei Afogado
Abismo da Aurora Extinta
```

## Regras para chefes

Chefes devem ter nomes com identidade:

```text
Varkun, o Guardião Cinzento
Morgath, o Devorador de Relíquias
A Serpente de Vidro
Brakka, Capitão dos Ossos
Elyra, Voz da Névoa
Tharok, o Martelo Antigo
```

## Critérios de aceite

- Remover sufixos sequenciais visíveis.
- Garantir nomes únicos.
- Garantir nomes coerentes com a faixa de nível.
- Garantir que nomes de chefes tenham peso narrativo.
- Garantir que nomes estejam em Português BR.
- Garantir acentuação correta.
- Evitar nomes longos demais para os cards.
- Atualizar seeds com nomes finais.

---

# MVP-066 — UX e comunicação de masmorras e chefes

## Objetivo

Melhorar a clareza das telas de masmorras e chefes para que o jogador entenda por que vale executar aquele conteúdo.

## Problema

Se masmorra e chefe aparecem apenas como listas com recompensa, o jogador tende a escolher o maior número aparente ou repetir sempre o mais eficiente.

A tela precisa comunicar:

- Risco.
- Função.
- Recompensa principal.
- Chance de loot raro.
- Requisitos.
- Perfil recomendado.

## Melhorias esperadas

Cada card de masmorra deve exibir:

```text
Nome
Faixa de nível
Tempo
Chance de sucesso
XP esperado
Ouro esperado
Recompensa principal
Possíveis drops
Raridade máxima possível
Perfil recomendado
```

Cada card de chefe deve exibir:

```text
Nome do chefe
Descrição curta
Faixa de nível
Tempo
Chance de sucesso
Requisito mínimo
Recomendação de poder
Recompensa principal
Chance de raridade alta
Drops principais
Aviso de risco
```

## Labels recomendados

Usar labels como:

```text
Melhor para XP
Melhor para ouro
Bom para equipamentos
Chance de item raro
Desafio de chefe
Risco alto
Recompensa alta
Conteúdo de transição
Farm de material raro
```

## Critérios de aceite

- Exibir função principal do conteúdo.
- Exibir risco de forma clara.
- Exibir loot potencial sem poluir a tela.
- Exibir raridade máxima possível.
- Exibir perfil recomendado.
- Garantir que textos estejam em Português BR.
- Garantir layout compatível com UX/UI medieval atual.
- Garantir responsividade.

---

# MVP-067 — QA automatizado e relatório final de masmorras e chefes

## Objetivo

Criar um QA automatizado específico para masmorras e chefes, gerando um relatório final `.md` com diagnóstico, alterações e resultados da simulação.

## Escopo do QA

O script deve validar:

- Quantidade de masmorras por faixa.
- Quantidade de chefes por faixa.
- Conteúdos duplicados.
- Conteúdos equivalentes.
- Conteúdos sem diferencial.
- Conteúdos com recompensa baixa demais.
- Conteúdos com recompensa alta demais.
- Conteúdos com chance incompatível.
- Conteúdos com duração incompatível.
- Conteúdos com nomes técnicos/sequenciais.
- Distribuição de raridade por tipo de conteúdo.
- Eficiência de XP/h.
- Eficiência de ouro/h.
- Valor esperado de loot.
- Comparação contra missões e coletas.

## Relatório final obrigatório

Gerar arquivo:

```text
relatorio_qa_masmorras_chefes.md
```

O relatório deve conter:

```text
Sumário executivo
Quantidade antes/depois
Masmorras por faixa
Chefes por faixa
Conteúdos desativados
Conteúdos alterados
Conteúdos mantidos
Ranking de eficiência por faixa
Distribuição de loot simulada
Análise de redundância
Análise de gargalos
Recomendações finais
Pendências futuras
```

## Critérios de aceite

- Criar script de QA executável.
- Gerar relatório `.md` automaticamente ou via comando documentado.
- Rodar simulação antes e depois dos ajustes.
- Evidenciar reduções de redundância.
- Evidenciar melhora de diferenciação.
- Evidenciar que chefes possuem função distinta de masmorras.
- Evidenciar que masmorras possuem função distinta de missões normais.
- Garantir que o relatório seja salvo no projeto.

---

# Priorização recomendada

A ordem recomendada de execução é:

```text
MVP-059 — Auditoria estrutural de masmorras e chefes
MVP-060 — Simulação de eficiência de masmorras e chefes
MVP-061 — Curadoria e redução de redundância em masmorras
MVP-062 — Curadoria e progressão de chefes
MVP-063 — Rebalanceamento de loot de masmorras e chefes
MVP-064 — Rebalanceamento de tempo, chance e dificuldade
MVP-065 — Curadoria de nomes, temas e identidade narrativa
MVP-066 — UX e comunicação de masmorras e chefes
MVP-067 — QA automatizado e relatório final de masmorras e chefes
```

Observação: MVP-061, MVP-062, MVP-063, MVP-064 e MVP-065 podem ser implementadas no mesmo pacote, desde que o Codex gere relatório antes/depois e não faça alterações cegas.

---

# Checklist final para o Codex

Antes de finalizar, validar:

- [ ] Existe auditoria completa de masmorras.
- [ ] Existe auditoria completa de chefes.
- [ ] Existe simulação de eficiência por faixa.
- [ ] Existem rankings de XP/h, ouro/h e loot esperado.
- [ ] Masmorras redundantes foram diferenciadas ou desativadas.
- [ ] Chefes redundantes foram diferenciados ou desativados.
- [ ] Cada faixa possui quantidade saudável de masmorras.
- [ ] Cada faixa possui quantidade saudável de chefes.
- [ ] Masmorras têm função diferente de missões normais.
- [ ] Chefes têm função diferente de masmorras.
- [ ] Loot de chefe é melhor para raridades altas.
- [ ] Loot de masmorra é melhor para equipamentos intermediários.
- [ ] Coleta continua focada em materiais.
- [ ] Missão normal continua relevante para XP/ouro/equipamento básico.
- [ ] Nomes técnicos/sequenciais foram removidos.
- [ ] Textos estão em Português BR.
- [ ] Acentuação está correta.
- [ ] UI mostra risco, recompensa e função do conteúdo.
- [ ] Foi gerado `relatorio_qa_masmorras_chefes.md`.

---

# Definição de pronto

A entrega só deve ser considerada pronta quando:

```text
1. O conteúdo de masmorras e chefes tiver sido auditado.
2. A eficiência tiver sido simulada.
3. Redundâncias tiverem sido corrigidas.
4. Recompensas tiverem sido rebalanceadas.
5. Nomes técnicos tiverem sido removidos.
6. A UI comunicar função, risco e recompensa.
7. O relatório final .md tiver sido gerado.
```

O resultado esperado é que o jogador tenha motivo real para usar masmorras e chefes durante toda a progressão, sem depender apenas de missões normais ou coletas, e sem encontrar uma massa grande de conteúdo aparentemente diferente, mas funcionalmente igual.
