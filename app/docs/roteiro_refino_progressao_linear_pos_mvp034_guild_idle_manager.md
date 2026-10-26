# Roteiro — Refino de Progressão Linear e Conteúdo Pós-MVP-034

## Contexto

A última entrega considerada como concluída é a **MVP-034 — Validação final de conteúdo, QA e balanceamento de massa**.

O sistema já possui grande massa de conteúdo: missões, dungeons, itens, materiais, armas, habilidades, classes, progressão, recompensas e conteúdos de coleta. A etapa atual não é criar mais volume de forma bruta. A etapa atual é transformar esse volume em uma progressão coerente, linear, jogável e compreensível.

O objetivo deste documento é orientar o Codex a revisar a massa de dados existente e reorganizar a progressão do jogo como um todo: evolução de mercenários, evolução da guilda, farm de gold, farm de materiais, drops, dungeons, skills, raridade de mercenários, itens, refino, construções e experiência do usuário.

A regra principal é: o jogador pode se sentir travado porque ainda não entendeu o melhor caminho de progressão, mas não pode se sentir travado por falta de conteúdo, falta de clareza, recompensas mal distribuídas ou nomes confusos.

---

## Objetivo macro

Refinar todo o conteúdo massivo já criado para que o Guild Idle Manager tenha uma curva de progressão linear, clara e sustentável até o nível 350.

Essa curva deve considerar:

- Evolução de mercenários.
- Progressão da guilda.
- Farm de gold.
- Farm de materiais.
- Drops de armas, equipamentos e itens.
- Missões normais.
- Missões de coleta.
- Dungeons.
- Skills.
- Classes base, especializações e classes finais.
- Raridade dos mercenários.
- Dreno de gold.
- Necessidade gradual de mercenários melhores no mid/endgame.
- Clareza visual para o usuário saber onde farmar, quando coletar loot e como progredir.

---

## Princípios obrigatórios

### 1. Conteúdo massivo não pode parecer conteúdo duplicado

O jogo pode ter milhares de missões, dungeons e itens, mas isso não pode aparecer para o jogador como uma lista artificial de cópias.

Não devem existir nomes visuais como:

- `Minas 1-001`
- `Minas 1-013`
- `Floresta 2-004`
- `Dungeon 3-087`
- `Missão de coleta - 025`

Esse tipo de marcador sequencial é aceitável apenas internamente, em `slug`, `internal_code` ou chave técnica. Nunca deve aparecer em tela.

Exemplo ruim:

```text
Minas 1-001
Minas 1-013
```

Exemplo correto:

```text
Explorar Mina de Cobre
Mapear Galeria de Ferro
Investigar Veio de Prata
Proteger Caravana dos Mineiros
Coletar Fragmentos de Cristal Bruto
```

O jogador deve sentir que existem variações reais de objetivo, local, recurso, risco e recompensa.

---

### 2. Progressão deve ser simulada, não chutada

O Codex deve criar ou ajustar scripts de simulação para validar a progressão.

Não basta olhar visualmente para XP, tempo, ouro e loot. É obrigatório simular cenários.

A simulação deve responder perguntas como:

- Quantas missões em média um mercenário precisa concluir para ir do nível 1 ao 20?
- Quantas missões no pior caso razoável ele precisa concluir, considerando falhas?
- Quanto tempo real ou idle isso representa?
- Quanto gold ele ganha nesse caminho?
- Esse gold é suficiente para contratar, evoluir, refinar, comprar materiais e evoluir construções?
- A quantidade de missões disponíveis em cada faixa é suficiente para não repetir sempre a mesma coisa? Tudo bem repetir, mas não por ser obrigado, mas sim por ser necessario farmar algo.
- Uma party com mercenários comuns consegue avançar até onde?
- Em que ponto mercenários incomuns, raros, épicos ou lendários começam a fazer diferença real?
- Dungeons estão recompensando mais risco com mais valor?
- Missões de coleta estão eficientes sem serem mais lucrativas do que missões principais?

---

### 3. Progressão linear não significa tudo igual

A curva deve crescer de forma lógica.

O nível 1–20 deve ser simples, rápido e didático.
O nível 21–50 deve começar a exigir escolha de classe e melhor uso de mercenários.
O nível 51–100 deve introduzir necessidade de composição, equipamentos e materiais.
O nível 101–130 deve consolidar especializações.
O nível 131–200 deve começar a punir composição ruim.
O nível 201–350 deve exigir planejamento, bons equipamentos, mercenários melhores e uso correto de skills.
Após o nivel maximo, entendo que o conteudo seriam alguns missões que sem o nivel maximo ficaria impossivel de concluir, DG's e Bosses também nessa logica.

---

### 4. Gold precisa ter fonte e dreno claros

Tudo que compra com gold precisa estar conectado com uma fonte viável de farm.

O Codex deve revisar:

- Gold recebido em missões.
- Gold recebido em dungeons.
- Gold recebido em venda de itens.
- Gold passivo/idle.
- Gold gasto em contratação.
- Gold gasto em refresh da Taverna.
- Gold gasto em Docas/Mercantes.
- Gold gasto em evolução de construções.
- Gold gasto em crafting.
- Gold gasto em refino.
- Gold gasto em evolução ou manutenção de sistemas futuros.

Não pode existir um custo relevante sem uma rota razoável de farm associada.
Também não pode existir uma fonte de gold tão forte que invalide as outras.

---

### 5. Mercenários comuns podem zerar, mas não devem ser a rota eficiente do endgame

Um jogador pode tentar zerar o jogo apenas com mercenários comuns. Isso deve ser possível em teoria, mas difícil e ineficiente no endgame.

Diretriz de balanceamento:

- Early game: mercenários comuns devem funcionar bem.
- Mid game: comuns ainda funcionam, mas começam a perder eficiência para incomuns e raros.
- Late game: comuns altamente otimizados podem avançar, mas com esforço, equipamentos bons e mais tempo.
- Endgame: conteúdo avançado deve incentivar fortemente o farm de mercenários de tiers melhores.

A lógica não deve ser um bloqueio seco do tipo “precisa ser raro para entrar”. O ideal é usar soft gates:

- Chance de sucesso menor.
- Tempo maior.
- Mais risco de falha.
- Recompensa menos eficiente por hora.
- Necessidade de equipamento melhor.
- Necessidade de composição mais otimizada.

Dungeons especiais podem ter requisitos mais duros, mas a regra geral deve ser progressão por eficiência, não por bloqueio artificial.

---

### 6. Conteúdo deve ser idempotente e seguro para banco existente

Toda revisão de conteúdo deve respeitar o banco atual.

O Codex deve:

- Usar seeds idempotentes.
- Evitar duplicar registros a cada execução.
- Usar `slug` estável para upsert.
- Separar `display_name` de identificador técnico.
- Criar scripts de migração quando renomear conteúdo existente.
- Não apagar progresso do jogador sem necessidade.
- Se precisar substituir conteúdo antigo, criar rotina de mapeamento ou desativação segura.

Campos recomendados para conteúdo:

```text
slug
internal_code
display_name
description
content_family
content_type
level_min
level_max
difficulty_tier
rarity_tier
biome_or_source
primary_reward_type
reward_profile
is_active
is_seeded
version_tag
```

---

# Entregas recomendadas pós-MVP-034

## MVP-035 — Auditoria semântica e renomeação de missões/dungeons

### Objetivo

Remover nomes artificiais, sequenciais ou duplicados da interface e transformar missões/dungeons em conteúdo semanticamente distinto.

### Problema atual

Existem missões e dungeons aparecendo com nomes como `Minas 1-001`, `Minas 1-013` ou variações muito parecidas. Isso passa a sensação de conteúdo gerado em massa sem curadoria.

Mesmo que internamente existam centenas ou milhares de registros, o jogador não deve ver marcadores numéricos ou nomes repetidos.

### Diretrizes de renomeação

O Codex deve revisar todos os registros de missões, missões de coleta e dungeons que aparecem na interface.

Deve remover do `display_name`:

- Sufixos numéricos.
- Códigos sequenciais.
- Marcadores `001`, `002`, `013`, etc.
- Marcadores de faixa como `1-001`, `2-050`, etc.
- Nomes duplicados sem variação real.

Pode manter códigos técnicos apenas em campos internos.

### Regra de nome visual

Todo nome visível deve ter significado narrativo.

Padrões recomendados para missões normais:

```text
[Verbo] + [Local/Alvo]
[Verbo] + [Local/Alvo] + [Qualificador]
[Objetivo] + [Recurso/Inimigo/Região]
```

Exemplos:

```text
Explorar Mina de Cobre
Mapear Galeria de Ferro
Proteger a Entrada da Floresta
Caçar Batedores Goblins
Recuperar Suprimentos Perdidos
Investigar Ruínas Antigas
Escoltar Caravana dos Mercadores
Limpar Acampamento de Salteadores
Rastrear Pegadas no Pântano
Patrulhar Estrada da Guilda
```

Padrões recomendados para missões de coleta:

```text
Coletar Madeira de Carvalho
Extrair Minério de Cobre
Colher Ervas do Bosque
Garimpar Cristais Brutos
Raspar Couro de Fera Selvagem
Separar Fibras de Linho
Buscar Resina Antiga
Recolher Cogumelos Luminosos
```

Padrões recomendados para dungeons:

```text
Cripta dos Ossos Frios
Ruínas da Lua Quebrada
Fortaleza dos Salteadores
Santuário da Chama Pálida
Caverna do Eco Profundo
Torre do Vigia Caído
Abismo das Correntes Negras
Catacumbas do Rei Esquecido
Covil do Dragão Cinzento
Templo do Eclipse Vermelho
```

### Variação semântica obrigatória

Se existirem múltiplas missões da mesma família, elas devem variar por pelo menos um dos fatores abaixo:

- Recurso principal.
- Região.
- Bioma.
- Tipo de inimigo.
- Objetivo.
- Nível recomendado.
- Risco.
- Recompensa.
- Duração.
- Requisito de construção.
- Classe recomendada.

Exemplo correto para família `Minas`:

```text
Explorar Mina de Cobre
Mapear Galeria de Ferro
Extrair Prata da Encosta
Investigar Veio de Ouro Antigo
Eliminar Morcegos da Mina Abandonada
Reforçar Túneis Instáveis
Recuperar Picaretas Perdidas
Proteger Mineiros da Guilda
```

### Detecção de duplicidade

O Codex deve criar uma rotina de auditoria para detectar conteúdos visualmente duplicados.

Critérios de duplicidade:

- Mesmo nome normalizado.
- Mesmo tipo de missão.
- Mesma faixa de nível.
- Mesmo objetivo principal.
- Mesmo loot principal.
- Mesma dificuldade.
- Mesma duração aproximada.

Se dois registros forem muito parecidos, um deles deve ser:

- Renomeado com variação real.
- Ajustado em loot/dificuldade/duração.
- Movido para outra faixa.
- Desativado, se for redundante.

### Regras de negócio

- O usuário nunca deve ver código sequencial em nome de missão ou dungeon.
- `display_name` deve ser sempre limpo e narrativo.
- `slug` pode manter identificador técnico.
- Nomes devem estar em Português BR com acentuação correta.
- Não usar nomes em inglês.
- Não gerar cinco missões praticamente iguais para dropar o mesmo item.
- Se uma missão parece igual a outra, ela deve ter justificativa mecânica clara.

### Critérios de aceite

- Nenhuma missão aparece em tela com sufixo `-001`, `-002`, `1-013` ou equivalente.
- Nenhuma dungeon aparece em tela com marcador sequencial artificial.
- Missões de uma mesma família possuem variação real de objetivo, loot, duração, dificuldade ou região.
- Conteúdos técnicos continuam rastreáveis por `slug` ou `internal_code`.
- A interface exibe nomes naturais e coerentes com fantasia medieval.

---

## MVP-036 — Simulador de progressão de XP, gold e tempo

### Objetivo

Criar uma base de simulação para transformar a progressão do jogo em algo mensurável.

### Justificativa

Antes de alterar XP, ouro, tempo, drops e quantidade de missões, é necessário entender numericamente como um jogador progride.

A pergunta central é:

> Considerando chance de sucesso, tempo, XP e gold, quantas missões/dungeons o jogador precisa executar para evoluir em cada faixa de nível?

### Escopo técnico

Criar script, service ou comando administrativo para simular progressão.

Sugestão de caminho:

```text
scripts/balance/simulate_progression.py
scripts/balance/simulate_dungeons.py
scripts/balance/simulate_material_farm.py
scripts/balance/generate_balance_report.py
```

O script deve ler a configuração real do jogo e gerar relatório.

### Entradas mínimas da simulação

Para missões:

```text
level_start
level_end
xp_curve
mission_xp_reward
mission_gold_reward
mission_duration
success_chance
failure_xp_reward
failure_gold_reward
party_power
class_bonus
rarity_bonus
equipment_bonus
skill_bonus
```

Para dungeons:

```text
level_start
level_end
dungeon_xp_reward
dungeon_gold_reward
dungeon_duration
success_chance
failure_penalty
loot_value_expected
required_power
recommended_rarity
recommended_classes
```

Para coleta:

```text
material_type
material_rarity
quantity_expected
mission_duration
success_chance
profession_bonus
market_gold_value
crafting_demand
building_demand
refinement_demand
```

### Cálculos obrigatórios

Para cada faixa de nível, calcular:

- XP total necessária.
- XP média por missão.
- XP esperada considerando falha.
- Número esperado de missões para subir de faixa.
- Número pessimista de missões usando percentil 75, 90 e 95.
- Tempo total estimado.
- Gold total esperado.
- Gold por hora.
- Materiais esperados por hora.
- Quantidade de dungeons necessárias, quando aplicável.
- Quantidade recomendada de missões distintas na faixa.
- Quantidade recomendada de dungeons distintas na faixa.
- Quantidade recomendada de missões de coleta por família de material.

Fórmula base sugerida:

```text
xp_esperada_por_tentativa = (chance_sucesso * xp_sucesso) + ((1 - chance_sucesso) * xp_falha)
missoes_esperadas = xp_necessaria_total / xp_esperada_por_tentativa
```

Para tempo:

```text
tempo_total_esperado = missoes_esperadas * duracao_media_missao
```

Para gold:

```text
gold_esperado_por_tentativa = (chance_sucesso * gold_sucesso) + ((1 - chance_sucesso) * gold_falha)
gold_total_esperado = missoes_esperadas * gold_esperado_por_tentativa
```

### Simulação probabilística

Além do cálculo determinístico, criar simulação Monte Carlo simples.

Executar pelo menos:

```text
1.000 simulações por faixa de nível
```

Relatório deve mostrar:

```text
p50_attempts
p75_attempts
p90_attempts
p95_attempts
p50_time
p90_time
p95_time
p50_gold
p90_gold
```

O p90 deve ser usado como base para definir volume de conteúdo.

### Faixas obrigatórias

Usar as mesmas faixas principais do jogo:

```text
1–20
21–50
51–100
101–130
131–200
201–350
```

Se o sistema já possuir subfaixas internas, manter compatibilidade, mas essas faixas devem existir no relatório final.

### Regra para quantidade mínima de missões por faixa

A quantidade de missões por faixa deve ser baseada na simulação.

Regra sugerida:

```text
missoes_minimas_faixa = max(missoes_minimas_base, ceil(p90_attempts * fator_diversidade))
```

Fator de diversidade recomendado:

```text
1.10 a 1.30
```

Exemplo:

Se a simulação indicar que, no p90, o jogador precisa de 30 missões para ir do nível 1 ao 20, então a faixa 1–20 deve ter pelo menos 33 a 39 missões distintas úteis, considerando fator de diversidade.

A regra pode ser ajustada pelo Codex se o volume ficar excessivo, mas a decisão deve estar registrada no relatório.

### Diretriz inicial de volume por faixa

Estes números são referência inicial, não regra cega. O Codex deve recalcular com base no XP real do jogo.

| Faixa | Perfil | Missões normais | Dungeons | Missões de coleta por família |
|---|---|---:|---:|---:|
| 1–20 | Tutorial e early game | >= p90 * 1.20 | 5–10 | 2–4 |
| 21–50 | Early estruturado | >= p90 * 1.20 | 8–15 | 3–5 |
| 51–100 | Mid game inicial | >= p90 * 1.15 | 12–25 | 3–6 |
| 101–130 | Transição de especialização | >= p90 * 1.15 | 10–20 | 3–6 |
| 131–200 | Mid/late game | >= p90 * 1.10 | 18–35 | 4–8 |
| 201–350 | Endgame | >= p90 * 1.10 | 30–60 | 5–10 |

Importante: missões de coleta não precisam ser tão numerosas quanto missões normais. Elas precisam ser lineares, eficientes e conectadas com a demanda de materiais.

### Critérios de aceite

- Existe script de simulação executável.
- Existe relatório gerado com resultados por faixa de nível.
- XP, gold e tempo das missões são ajustados com base nesse relatório.
- Quantidade de missões/dungeons por faixa é justificada pela simulação.
- O relatório mostra ao menos p50, p75, p90 e p95.
- O conteúdo deixa de ser apenas grande e passa a ter progressão mensurável.

---

## MVP-037 — Rebalanceamento linear de missões, gold, XP e recompensas

### Objetivo

Revisar missões normais para criar uma escala linear de evolução até o nível 350.

### Justificativa

Atualmente existe muito conteúdo, mas XP, gold, tempo e recompensa precisam seguir uma narrativa linear. Outro ponto, quando entra na faixa 1 a 20 todas as missões estão com nivel minimo 1, precisa mudar isso para que exija o up dos mercenarios para ir fazendo outras missões.

A missão do nível 1 não deve parecer aleatória em relação à missão do nível 50. A missão do nível 200 deve ser claramente mais difícil, mais longa, mais lucrativa e mais exigente do que uma missão do nível 20.

### Diretrizes de progressão

As missões devem evoluir em:

- Dificuldade.
- Tempo.
- XP.
- Gold.
- Risco.
- Requisito de poder.
- Recompensa.
- Variedade de loot.
- Dependência de classe/atributo.
- Dependência de raridade no late game.

### Estrutura recomendada por faixa

#### Faixa 1–20

Função: ensinar o jogo e permitir evolução inicial.

Características:

- Missões curtas.
- XP generoso o suficiente para não travar.
- Gold baixo, mas útil.
- Poucos materiais.
- Loot simples.
- Chance de sucesso alta para mercenários comuns.
- Duração baixa.
- Recompensas fáceis de entender.

Diretriz:

```text
Chance média com comum adequado: 80% a 95%
Duração: baixa
Loot: 1 a 2 slots
Quantidade por drop: baixa
Gold: suficiente para primeiras contratações e upgrades simples
```

#### Faixa 21–50

Função: começar a validar classe, atributos e contratação.

Características:

- Missões ainda acessíveis.
- Algumas missões favorecem atributos específicos.
- Começa a diferença entre comum ruim e comum bom.
- Incomuns começam a ser desejáveis.

Diretriz:

```text
Chance média com comum adequado: 70% a 90%
Chance média com incomum adequado: 80% a 95%
Loot: 1 a 3 slots
Gold: começa a alimentar refresh de Taverna e compra simples
```

#### Faixa 51–100

Função: consolidar build e preparar especialização.

Características:

- Missões exigem mais poder.
- Equipamentos começam a importar.
- Missões de coleta ficam relevantes.
- Materiais passam a ser usados em crafting/refino/construções.

Diretriz:

```text
Chance média com comum adequado: 55% a 80%
Chance média com incomum/raros adequados: 75% a 95%
Loot: 2 a 3 slots
Gold: precisa sustentar construções iniciais e equipamentos
```

#### Faixa 101–130

Função: transição pós-especialização.

Características:

- Missões começam a valorizar especializações.
- Bônus de classe e skills precisam aparecer no cálculo.
- Dungeons intermediárias começam a ter valor real.

Diretriz:

```text
Chance média com comum adequado: 45% a 70%
Chance média com incomum/raros adequados: 70% a 90%
Loot: 2 a 4 slots
Gold: sustenta refino inicial e evolução de guilda
```

#### Faixa 131–200

Função: mid/late game.

Características:

- Comuns começam a ficar pouco eficientes.
- Raros e épicos passam a ser desejáveis.
- Composição de party começa a pesar.
- Dungeons passam a ser mais relevantes.

Diretriz:

```text
Chance média com comum adequado: 30% a 60%
Chance média com raro adequado: 70% a 90%
Loot: 3 a 4 slots
Gold: precisa sustentar refino, Docas, Mercado, construções e Taverna
```

#### Faixa 201–350

Função: endgame.

Características:

- Exige planejamento.
- Raridade dos mercenários importa muito.
- Equipamento, skills e composição devem ser decisivos.
- Dungeons são fonte relevante de itens raros.
- O jogador deve sentir necessidade de farmar mercenários melhores.

Diretriz:

```text
Chance média com comum otimizado: 20% a 45%
Chance média com raro/épico adequado: 60% a 85%
Chance média com lendário adequado: 75% a 95%
Loot: 3 a 5 slots
Gold: alto, mas com drenos igualmente altos
```

### Regras para XP

- XP não pode ser aleatória entre faixas.
- XP deve crescer conforme nível mínimo, duração e dificuldade.
- Missões mais longas devem recompensar mais XP total, mas não necessariamente mais XP por minuto.
- Dungeons devem ter melhor XP por tentativa bem-sucedida, mas maior risco/tempo.
- Missões de coleta devem dar XP menor que missões normais, salvo missões especiais.

### Regras para gold

- Gold deve crescer por faixa.
- Gold por hora deve ser controlado.
- Missões normais devem ser fonte estável.
- Dungeons devem ser fonte de picos e loot valioso.
- Coleta deve ser fonte secundária, focada em materiais.
- Idle deve ser fonte complementar.
- Mercado/Docas devem ser drenos, não fonte infinita.

### Critérios de aceite

- Missões possuem progressão clara de XP, gold e tempo.
- A curva é validada pelo simulador.
- A quantidade de missões por faixa é suficiente com base no p90.
- Missões de early game não dropam quantidades exageradas.
- Missões de late game recompensam melhor sem quebrar economia.
- Jogador comum consegue progredir, mas perde eficiência no endgame.

---

## MVP-038 — Rebalanceamento de missões de coleta e materiais

### Objetivo

Refinar missões de coleta para que elas sejam poucas o suficiente para não poluir a lista, mas úteis e eficientes para farmar materiais.

### Justificativa

Missões de coleta não precisam existir em volume igual às missões normais. Elas precisam ser claras: o usuário entra nelas para buscar madeira, minério, ervas, couro, cristais ou outros materiais necessários para craft, refino e construções.

### Famílias de materiais recomendadas

O Codex deve revisar os materiais existentes e organizá-los em famílias.

Famílias sugeridas:

```text
Madeiras
Minérios
Pedras
Cristais
Ervas
Couros
Tecidos/Fibras
Essências
Fragmentos mágicos
Relíquias
Componentes de arma
Componentes de armadura
Componentes de acessório
```

Se o banco já possui outras famílias, manter, mas garantir agrupamento lógico.

### Regras para missões de coleta

Cada família deve ter missões por faixa de nível, mas sem excesso.

Exemplo de distribuição:

| Faixa | Missões por família | Observação |
|---|---:|---|
| 1–20 | 2–4 | Coleta básica e tutorial |
| 21–50 | 3–5 | Introduz variação de raridade |
| 51–100 | 3–6 | Materiais para craft/refino inicial |
| 101–130 | 3–6 | Materiais de especialização |
| 131–200 | 4–8 | Materiais raros e construção |
| 201–350 | 5–10 | Materiais avançados/endgame |

### Quantidade de drop por faixa

Não deve existir drop exagerado no começo do jogo.

Diretriz inicial:

| Faixa | Quantidade comum | Quantidade incomum | Quantidade rara | Observação |
|---|---:|---:|---:|---|
| 1–20 | 1–3 | 0–1 | 0 | Sem explosão de recursos |
| 21–50 | 2–4 | 1–2 | 0–1 | Começa variação |
| 51–100 | 3–6 | 1–3 | 0–2 | Craft/refino inicial |
| 101–130 | 4–7 | 2–4 | 1–2 | Especialização |
| 131–200 | 5–9 | 3–5 | 1–3 | Construções e upgrades |
| 201–350 | 6–12 | 4–7 | 2–5 | Endgame |

Esses valores devem ser ajustados pelo simulador de economia.

### Loot slots

Não fixar todas as missões em exatamente 2 itens.

Diretriz:

```text
Early game: 1–2 slots de loot
Early/mid: 1–3 slots
Mid game: 2–3 slots
Late game: 2–4 slots
Endgame: 3–5 slots
```

Importante: mais slots não significa sempre mais quantidade. Pode significar variedade maior.

### Profissões e bônus de coleta

As profissões devem bonificar missões de coleta, mas sem transformar coleta em fonte quebrada.

Profissões sugeridas:

| Profissão | Bônus principal | Missões favorecidas |
|---|---|---|
| Lenhador | Mais madeira | Coleta de madeira |
| Minerador | Mais minérios e pedras | Coleta de minério |
| Herbalista | Mais ervas e reagentes naturais | Coleta de ervas |
| Coureiro | Mais couro e partes de criaturas | Coleta de couro |
| Tecelão | Mais fibras e tecidos | Coleta de fibras |
| Lapidador | Mais cristais e gemas | Coleta de cristais |
| Arcanista | Mais essências e fragmentos mágicos | Coleta mágica |
| Catador | Pequeno bônus geral | Coletas comuns |

Diretriz de bônus:

```text
Bônus comum de profissão: +5% a +15% de quantidade esperada
Bônus avançado ou raro: +15% a +25%
Nunca permitir que profissão dobre a economia sem custo/limite
```

### Critérios de aceite

- Missões de coleta são organizadas por família de material.
- Não existe excesso de missões iguais para dropar itens parecidos.
- Drops crescem linearmente por faixa.
- Quantidades iniciais são controladas.
- Profissões bonificam coleta de forma simples e clara.
- Materiais farmados são suficientes para construções, craft e refino sem gerar excesso absurdo.

---

## MVP-039 — Rebalanceamento de dungeons e progressão de dificuldade

### Objetivo

Refinar dungeons para que elas tenham quantidade relevante, dificuldade crescente e papel claro na progressão até o nível 350.

### Justificativa

Dungeons devem ser conteúdo mais difícil e mais recompensador. Elas não podem ser apenas missões com outro nome.

### Papel das dungeons

Dungeons devem servir para:

- Testar composição de party.
- Exigir poder maior.
- Valorizar skills.
- Valorizar classes específicas.
- Dar drops melhores.
- Gerar picos de gold e XP.
- Introduzir materiais raros.
- Incentivar farm de mercenários melhores.
- Criar objetivos de médio e longo prazo.

### Diferença entre missão e dungeon

| Aspecto | Missão | Dungeon |
|---|---|---|
| Duração | Baixa/média | Média/alta |
| Risco | Baixo/médio | Médio/alto |
| Recompensa | Estável | Alta, mas menos garantida |
| Composição | Importa gradualmente | Importa bastante |
| Loot | Comum a raro | Incomum a lendário |
| Função | Progressão base | Desafio e farm avançado |

### Distribuição por faixa

Usar simulação para definir quantidade final, mas diretriz inicial:

| Faixa | Quantidade sugerida | Perfil |
|---|---:|---|
| 1–20 | 5–10 | Mini dungeons introdutórias |
| 21–50 | 8–15 | Primeiros desafios reais |
| 51–100 | 12–25 | Dungeons de build |
| 101–130 | 10–20 | Pós-especialização |
| 131–200 | 18–35 | Late game inicial |
| 201–350 | 30–60 | Endgame e farm raro |

### Nomes de dungeons

Dungeons devem ter nomes únicos, sem código sequencial.

Exemplos por faixa:

#### 1–20

```text
Porão dos Ratos Cinzentos
Caverna dos Ecos Fracos
Ruínas do Vigia Antigo
Cripta dos Ossos Secos
Túnel dos Salteadores
```

#### 21–50

```text
Fortaleza dos Bandidos do Norte
Mina Abandonada de Ferro
Santuário da Vela Azul
Covil das Aranhas Negras
Catacumba dos Guardas Caídos
```

#### 51–100

```text
Torre do Feiticeiro Cego
Ruínas do Sol Partido
Templo das Lâminas Velhas
Caverna dos Cristais Partidos
Muralha dos Cavaleiros Mortos
```

#### 101–130

```text
Santuário da Chama Pálida
Cripta dos Juramentos Quebrados
Fenda dos Ecos Arcanos
Bastião do Martelo Negro
Biblioteca dos Magos Perdidos
```

#### 131–200

```text
Abismo das Correntes Negras
Catedral do Sino Afogado
Fortaleza do Rei Sem Coroa
Poço dos Cristais Rubros
Torre da Lua Sangrenta
```

#### 201–350

```text
Trono do Dragão Cinzento
Templo do Eclipse Vermelho
Catacumbas do Imperador Esquecido
Cidadela da Névoa Eterna
Abismo do Primeiro Demônio
Santuário do Fim da Aurora
```

### Recompensas

Dungeons devem ter:

- XP maior por conclusão.
- Gold maior por conclusão.
- Chance de loot raro.
- Materiais especiais.
- Armas/equipamentos melhores.
- Chance de item exclusivo em algumas dungeons.

Mas devem ter:

- Duração maior.
- Chance de falha mais relevante.
- Requisito de party/poder mais exigente.

### Critérios de aceite

- Dungeons possuem nomes únicos e sem sequenciais visuais.
- Dungeons têm progressão clara por faixa.
- Dungeons são mais difíceis e mais recompensadoras que missões equivalentes.
- Dungeons endgame incentivam mercenários de tiers melhores.
- Dungeons são validadas pelo simulador.

---

## MVP-040 — Rebalanceamento de loot, itens, armas e economia de materiais

### Objetivo

Revisar todos os drops para que loot, itens, armas e materiais sustentem craft, refino, construções e progressão sem excesso ou escassez artificial.

### Problema atual

Com a criação massiva de conteúdo, existe risco de:

- Missões demais dropando os mesmos itens.
- Drops muito fixos.
- Drops altos demais no early game.
- Drops baixos demais no late game.
- Itens raros aparecendo cedo demais.
- Materiais não conectados a usos reais.
- Armas/equipamentos sem curva de valor.

### Regras de loot

Cada missão/dungeon deve ter um `reward_profile` coerente.

Tipos sugeridos:

```text
combat_basic
combat_gold
combat_xp
combat_material
combat_equipment
collection_wood
collection_ore
collection_herb
collection_leather
collection_crystal
dungeon_equipment
dungeon_material_rare
dungeon_boss
dungeon_endgame
```

### Regras de raridade por faixa

| Faixa | Comum | Incomum | Raro | Épico | Lendário |
|---|---:|---:|---:|---:|---:|
| 1–20 | Alta | Baixa | Quase zero | Não | Não |
| 21–50 | Alta | Média | Baixa | Quase zero | Não |
| 51–100 | Média | Média | Baixa/média | Baixa | Quase zero |
| 101–130 | Média | Média | Média | Baixa | Muito baixa |
| 131–200 | Média | Média | Média | Baixa/média | Baixa |
| 201–350 | Média | Média | Média | Média | Baixa/média |

A chance exata deve ser simulada e ajustada.

### Regras para armas e equipamentos

- Armas do early game devem ser simples.
- Armas de mid game devem começar a direcionar builds.
- Armas de late game devem ter identidade de classe.
- Armas endgame devem ser desejáveis e raras.
- Equipamentos não devem invalidar completamente a raridade do mercenário.
- Equipamentos devem ajudar comuns a avançar, mas não igualar facilmente um raro/épico bem equipado.

### Regras para materiais

Todo material deve ter pelo menos um uso claro:

- Construção.
- Upgrade de construção.
- Craft.
- Refino.
- Compra/troca.
- Venda no mercado.
- Requisito de dungeon/evento.

Material sem uso deve ser:

- Conectado a uma receita.
- Conectado a construção.
- Removido/desativado.
- Transformado em item vendável.

### Validação de demanda x oferta

O Codex deve comparar:

```text
materiais_gerados_por_hora
materiais_exigidos_por_craft
materiais_exigidos_por_refino
materiais_exigidos_por_construcao
materiais_consumidos_por_progressao_media
```

Objetivo:

- Evitar escassez extrema.
- Evitar estoque infinito sem uso.
- Evitar que jogador precise repetir uma única missão centenas de vezes.
- Evitar que comprar material nas Docas seja sempre melhor que farmar.

### Critérios de aceite

- Todo item/material tem uso claro.
- Drops crescem por faixa de forma linear.
- Loot inicial não entrega quantidades absurdas.
- Loot late game é melhor, mas não quebra economia.
- Armas/equipamentos possuem progressão coerente.
- Conteúdo é validado por relatório de oferta/demanda.

---

## MVP-041 — UX de missões/dungeons e atalho para receber loot

### Objetivo

Melhorar a usabilidade das telas de missões e dungeons, principalmente após a criação de grande massa de conteúdo.

### Problema atual

Com muitas missões e dungeons, o usuário precisa rolar a tela inteira até o fim para receber loot de missões concluídas. Isso é ruim operacionalmente.

### Escopo

Adicionar no topo das telas de missões e dungeons um atalho para ir diretamente ao bloco de recebimento de loot.

### Regra do botão

Criar botão/atalho no início da tela:

```text
Ir para loot disponível
```

Ou:

```text
Receber recompensas
```

Comportamento:

- Se houver loot pendente, o botão deve aparecer destacado.
- Ao clicar, rolar diretamente para a seção de loot/recompensas pendentes.
- Se não houver loot pendente, o botão pode ficar oculto ou desabilitado.
- A seção de destino deve ter âncora clara, como `#loot-disponivel`.
- A rolagem deve ser suave, se possível.

### Melhorias adicionais recomendadas

Na tela de missões:

- Filtro por faixa de nível.
- Filtro por tipo: combate, coleta, gold, XP, equipamento.
- Ordenação por nível, tempo, XP, gold e chance de sucesso.
- Destaque para missões recomendadas.
- Destaque para missões com loot pendente.
- Separação clara entre em andamento, concluídas e disponíveis.

Na tela de dungeons:

- Filtro por faixa.
- Filtro por dificuldade.
- Destaque para requisitos não cumpridos.
- Exibir chance estimada de sucesso.
- Exibir recompensa principal.
- Destaque para dungeons com loot pendente.

### Critérios de aceite

- Usuário não precisa rolar a lista inteira para receber loot.
- Botão aparece no topo quando há recompensa pendente.
- Clique leva diretamente ao bloco de recompensa.
- Missões e dungeons ficam mais navegáveis com grande massa de conteúdo.

---

## MVP-042 — Revisão de skills por classe, diversidade e poder de escolha

### Objetivo

Revisar habilidades criadas para classes secundárias e finais, removendo evolução genérica e criando identidade real por caminho de classe.

### Problema atual

Algumas skills estão aparecendo como evolução direta e genérica, por exemplo:

```text
Contrato Preciso
Contrato Preciso Avançado
Contrato Preciso Superior
```

Isso cria pouca diferença prática entre classes e reduz o poder de escolha do jogador.

### Princípio de design

Cada classe deve ter identidade mecânica própria.

A evolução de classe não deve ser apenas:

```text
mesma habilidade + avançado
```

Ela deve alterar, especializar ou complementar o estilo da classe.

### Tipos de identidade de skill

As skills devem ser distribuídas entre papéis como:

```text
Dano
Defesa
Crítico
Precisão
Velocidade
Redução de tempo
Aumento de XP
Aumento de gold
Melhora de drop
Melhora de coleta
Suporte ao grupo
Redução de falha
Recuperação
Sinergia com classe
Sinergia com profissão
Sinergia com dungeon
```

### Regra de diversidade

Para cada árvore de classe:

- Classe base define identidade principal.
- Especializações devem abrir escolhas diferentes.
- Classe final deve aprofundar uma escolha, não apenas repetir a base.
- Duas classes finais da mesma origem não devem ter o mesmo bônus com nome diferente.
- Skills econômicas/drop/coleta devem existir, mas não dominar todas as árvores.

### Exemplo de revisão — Arqueiro

Em vez de:

```text
Contrato Preciso
Contrato Preciso Avançado
Contrato Preciso Superior
```

Usar algo como:

```text
Arqueiro — Mira Estável
Bônus: aumenta levemente chance de sucesso em missões de combate à distância.

Ranger — Rastreamento Silencioso
Bônus: aumenta chance de encontrar loot adicional em missões de exploração e coleta.

Pistoleiro — Disparo Decisivo
Bônus: aumenta chance crítica e reduz levemente tempo de missões rápidas.
```

### Exemplo de revisão — Ladino

```text
Ladino — Leitura de Brechas
Bônus: usa AGI e INT para aumentar chance de sucesso em missões de infiltração.

Assassino — Golpe Oportunista
Bônus: usa AGI e SOR para aumentar crítico e chance de recompensa rara em alvos únicos.

Ninja — Véu das Sombras
Bônus: usa AGI e INT/SOR para reduzir risco de falha e melhorar missões de infiltração avançada.
```

### Exemplo de revisão — Guerreiro

```text
Guerreiro — Postura de Combate
Bônus: aumenta poder defensivo e chance de sucesso em missões de confronto direto.

Cavaleiro — Guarda de Ferro
Bônus: reduz penalidade de falha da party e melhora resistência em dungeons.

Duelista — Técnica de Lâmina
Bônus: aumenta eficiência contra inimigos únicos e melhora chance crítica com armas leves.
```

### Exemplo de revisão — Mago

```text
Mago — Fluxo Arcano
Bônus: usa INT para aumentar poder mágico em missões arcanas.

Sábio — Conhecimento Antigo
Bônus: aumenta XP recebida e melhora chance de sucesso em ruínas, bibliotecas e dungeons mágicas.

Mentalista — Pressão Psíquica
Bônus: reduz chance de falha em missões contra inimigos inteligentes ou arcanos.
```

### Exemplo de revisão — Clérigo

```text
Clérigo — Prece de Amparo
Bônus: reduz penalidades de falha e melhora estabilidade da party.

Padre — Bênção Serena
Bônus: aumenta recuperação e reduz risco em missões longas.

Paladino — Juramento Sagrado
Bônus: combina VIT/FOR/INT para melhorar combate contra mortos-vivos, demônios e bosses.
```

### Regras de nomenclatura

- Skill deve estar em Português BR.
- Skill deve ter acentuação correta.
- Evitar nomes genéricos demais.
- Evitar apenas adicionar `Avançado`, `Superior`, `Mestre` sem mudar mecânica.
- Pode existir versão evoluída de uma skill, mas precisa ter efeito adicional real.

### Critérios de aceite

- Skills de classes secundárias e finais são revisadas.
- Cada caminho de classe tem identidade própria.
- Não existem árvores inteiras com a mesma skill apenas renomeada como “Avançada”.
- Skills influenciam escolha de classe e composição de party.
- Skills são documentadas no guia de habilidades.

---

## MVP-043 — Revisão de atributos e escalas das classes

### Objetivo

Revisar os atributos principais de cada classe, corrigindo sobreposição entre Ladino e Arqueiro e criando maior diversidade de caminhos.

### Problema atual

O Ladino está escalando com AGI e SOR, igual ao Arqueiro. Isso reduz identidade entre classes.

Ajuste desejado:

- Ladino base deve escalar com **AGI + INT**.
- Arqueiro pode manter escala mais ligada a **AGI + SOR**.
- Especializações do Ladino podem abrir caminhos com AGI + SOR, AGI + INT ou variações.
- Isso cria escolha real e prepara caminhos como Ninja, Assassino e outros.

### Diretriz geral

Classe base deve preparar mais de um caminho futuro.
Especialização deve afunilar a build.
Classe final deve consolidar a escolha.

### Matriz recomendada de atributos por classe

A matriz abaixo deve ser usada como referência inicial. O Codex deve adaptar aos nomes reais existentes no banco.

| Classe | Atributo primário | Atributo secundário | Identidade |
|---|---|---|---|
| Aprendiz | Flexível | Flexível | Base neutra |
| Guerreiro | FOR | VIT | Combate direto e resistência |
| Ladino | AGI | INT | Infiltração, técnica e leitura de risco |
| Mago | INT | SOR | Poder mágico e manipulação arcana |
| Clérigo | INT | VIT | Suporte, estabilidade e proteção |
| Arqueiro | AGI | SOR | Precisão, chance e consistência |

### Especializações sugeridas

| Classe base | Especialização | Escala sugerida | Identidade |
|---|---|---|---|
| Guerreiro | Cavaleiro | VIT + FOR | Defesa e proteção |
| Guerreiro | Duelista | FOR + AGI | Dano técnico e alvo único |
| Ladino | Assassino | AGI + SOR | Crítico, risco e execução |
| Ladino | Ninja | AGI + INT | Infiltração, evasão e controle |
| Mago | Sábio | INT + VIT | Conhecimento, XP e estabilidade |
| Mago | Mentalista | INT + SOR | Controle, dano psíquico e falha reduzida |
| Clérigo | Padre | INT + VIT | Suporte puro e segurança |
| Clérigo | Paladino | VIT + FOR/INT | Defesa sagrada e combate |
| Arqueiro | Ranger | AGI + VIT/SOR | Exploração, coleta e sobrevivência |
| Arqueiro | Pistoleiro | AGI + SOR | Crítico, precisão e velocidade |

### Classes finais

Para classes finais, aplicar a mesma lógica:

- Não copiar escala da classe anterior sem ganho de identidade.
- Cada classe final deve ter atributo primário claro.
- Atributo secundário deve reforçar uma escolha.
- Se houver terceiro atributo, deve ser bônus menor, não eixo principal.

Regra sugerida:

```text
Atributo primário: peso 60%
Atributo secundário: peso 30%
Atributo terciário opcional: peso 10%
```

Exemplo:

```text
Ninja final:
AGI 60%
INT 30%
SOR 10%
```

```text
Assassino final:
AGI 60%
SOR 30%
FOR ou INT 10%
```

### Ajuste do Ladino

Alteração obrigatória:

```text
Ladino deixa de escalar primariamente com AGI + SOR.
Ladino passa a escalar com AGI + INT.
```

Motivo:

- Diferenciar Ladino do Arqueiro.
- Preparar caminho para Ninja.
- Dar valor para INT fora de Mago/Clérigo.
- Criar decisão real de evolução.

### Migração e compatibilidade

Se já existem mercenários criados com Ladino usando AGI + SOR:

- Não resetar mercenários do usuário.
- Recalcular poder de forma compatível.
- Atualizar tooltips, guias e cálculo de recomendação.
- Se necessário, criar aviso ou registro técnico de rebalanceamento.

### Critérios de aceite

- Ladino escala com AGI + INT.
- Arqueiro mantém identidade distinta.
- Especializações possuem escalas diferentes.
- Classes finais não são cópias diretas das anteriores.
- Guia de classes exibe atributos recomendados corretamente.
- Cálculo de poder, chance de sucesso e recomendação consideram nova matriz.

---

## MVP-044 — Guia de habilidades, classes e combinações

### Objetivo

Criar um guia de habilidades para explicar bônus, atributos recomendados e combinações sem entregar uma receita única obrigatória.

### Justificativa

Com skills, classes e especializações, o usuário precisa entender como usar isso a favor dele. O jogo deve ensinar o sistema, mas deixar o jogador decidir.

### Escopo

Criar ou expandir tela de guia com seções:

```text
Guia de Classes
Guia de Habilidades
Guia de Atributos
Guia de Combinações
Guia de Coleta e Profissões
Guia de Dungeons
```

### Conteúdo obrigatório por classe

Cada classe deve exibir:

- Nome.
- Descrição.
- Função principal.
- Atributos recomendados.
- Skills disponíveis.
- Efeito das skills.
- Como a classe ajuda em missões.
- Como a classe ajuda em dungeons.
- Como a classe ajuda em coleta, se aplicável.
- Especializações possíveis.
- Classes finais possíveis.
- Exemplo de uso.

### Conteúdo obrigatório por skill

Cada skill deve exibir:

- Nome.
- Classe vinculada.
- Tipo de bônus.
- Descrição em Português BR.
- Fórmula ou explicação simplificada.
- Onde funciona.
- Onde não funciona.
- Se combina com alguma profissão, classe ou dungeon.

Exemplo:

```text
Mira Estável
Classe: Arqueiro
Tipo: Precisão
Efeito: aumenta a chance de sucesso em missões de combate à distância.
Combina com: Ranger, Pistoleiro, missões de patrulha e dungeons com inimigos voadores.
```

### Guia de combinações

O guia deve dar exemplos, mas sem obrigar meta fechado.

Exemplos:

```text
Composição segura: Guerreiro + Clérigo + Arqueiro
Boa para missões longas e dungeons com risco médio.

Composição de farm: Ranger + Minerador + Herbalista
Boa para missões de coleta e materiais.

Composição agressiva: Duelista + Assassino + Mago
Boa para missões rápidas, mas com maior risco.
```

### Regra de comunicação

O guia não deve falar:

```text
Use sempre esta composição.
```

Deve falar:

```text
Esta composição tende a funcionar melhor quando...
```

### Critérios de aceite

- Guia explica skills de forma clara.
- Guia mostra atributos recomendados por classe.
- Guia ajuda o usuário a entender combinações.
- Guia não força uma única forma de jogar.
- Todas as informações estão em Português BR.

---

## MVP-045 — Rebalanceamento de raridade, party power e endgame

### Objetivo

Garantir que raridade dos mercenários tenha impacto real, principalmente no late game e endgame, sem impedir totalmente jogadores que insistam em mercenários comuns.

### Justificativa

Se mercenários comuns zeram tudo com facilidade, não há motivo para buscar tiers melhores.
Se mercenários comuns não conseguem fazer nada, o jogo vira bloqueio artificial.

O correto é equilíbrio por eficiência.

### Modelo recomendado

Usar cálculo de poder efetivo:

```text
poder_efetivo = atributos_base + bonus_classe + bonus_skill + bonus_equipamento + bonus_raridade + bonus_profissao + bonus_guilda
```

Raridade deve influenciar:

- Teto de atributos.
- Crescimento por nível.
- Eficiência em skills.
- Chance de sucesso.
- Sinergia em party.
- Potencial de late game.

### Diretriz de eficiência por raridade

| Faixa | Comum | Incomum | Raro | Épico | Lendário |
|---|---|---|---|---|---|
| 1–20 | Bom | Muito bom | Excelente | Exagerado | Exagerado |
| 21–50 | Bom | Muito bom | Excelente | Excelente | Excelente |
| 51–100 | Regular/bom | Bom | Muito bom | Excelente | Excelente |
| 101–130 | Regular | Bom | Muito bom | Excelente | Excelente |
| 131–200 | Fraco/regular | Regular/bom | Bom/muito bom | Excelente | Excelente |
| 201–350 | Difícil | Regular | Bom | Muito bom | Excelente |

### Chance de sucesso recomendada

Para conteúdo endgame:

```text
Comum otimizado: 20% a 45%
Incomum otimizado: 35% a 60%
Raro adequado: 55% a 75%
Épico adequado: 70% a 90%
Lendário adequado: 80% a 95%
```

Esses números são referência. O simulador deve validar.

### Soft gates

Preferir soft gates:

- Recomendação de poder.
- Chance de sucesso baixa.
- Duração maior.
- Penalidade de falha.
- Loot menos eficiente por hora.

Evitar hard gates excessivos:

```text
Só entra se for Épico.
```

Hard gates podem existir em conteúdos especiais, mas não na progressão principal.

### Integração com gold e Taverna

O endgame deve incentivar:

- Farmar gold.
- Usar Taverna.
- Contratar em massa.
- Buscar mercenários raros.
- Refinar equipamentos.
- Melhorar construções.
- Comprar materiais nas Docas.

Mas o jogo não pode virar apenas roleta de mercenário. O jogador também deve conseguir melhorar eficiência com equipamentos, skills e guilda.

### Critérios de aceite

- Raridade impacta progressão de forma perceptível.
- Mercenários comuns conseguem avançar, mas perdem eficiência no endgame.
- Conteúdos endgame incentivam tiers melhores.
- Chance de sucesso é validada por simulação.
- Não existem bloqueios artificiais excessivos na progressão principal.

---

## MVP-046 — Rebalanceamento integrado de gold, construções, Docas, Mercado e progressão da guilda

### Objetivo

Revisar a economia completa de gold e progressão da guilda após a criação massiva de conteúdos.

### Justificativa

O sistema possui várias fontes e drenos de gold. Tudo precisa conversar:

- Missões geram gold.
- Dungeons geram gold e itens.
- Mercado vende itens.
- Docas vendem materiais e itens.
- Construções consomem gold e materiais.
- Taverna consome gold.
- Refino consome gold.
- Craft consome gold.

Se uma dessas pontas estiver desbalanceada, a progressão inteira quebra.

### Mapa econômico obrigatório

O Codex deve gerar uma tabela/relatório com:

```text
Fonte de gold
Gold/hora esperado
Faixa de nível
Risco
Requisitos
Dreno relacionado
```

Fontes:

```text
Missões normais
Dungeons
Idle offline
Venda no Mercado
Eventos futuros, se existirem
```

Drenos:

```text
Contratação
Refresh da Taverna
Contratação em massa
Compra nas Docas
Upgrade de construções
Crafting
Refino
Taxas futuras, se existirem
```

### Regras para Docas

Docas devem ser dreno de gold e alternativa de acesso a materiais.

Não devem substituir completamente missões de coleta.

Diretriz:

- Docas ajudam quando o jogador precisa completar material faltante.
- Docas podem vender itens raros ocasionalmente.
- Quanto maior o nível das Docas, mais slots e melhor chance de mercantes raros.
- Preços devem ser altos o suficiente para serem dreno.
- Comprar tudo nas Docas não deve ser sempre mais eficiente do que farmar.

### Regras para Mercado

Mercado deve ser fonte complementar de gold e uso para itens excedentes.

Diretriz:

- Vender itens gera gold.
- Venda leva tempo.
- Slots limitam volume.
- Evolução do Mercado aumenta eficiência.
- XP de guilda por venda deve ser baixa e controlada.

### Regras para construções

Construções devem consumir:

- Gold.
- Materiais comuns.
- Materiais incomuns.
- Materiais raros conforme nível.

Não concentrar todo custo em gold.
Não exigir material raro demais cedo.

### Critérios de aceite

- Existe relatório de fontes e drenos de gold.
- Custos de construções são compatíveis com farm da faixa.
- Docas funcionam como alternativa/dreno, não como substituto completo do farm.
- Mercado funciona como fonte complementar, não como exploit.
- Progressão da guilda está conectada ao avanço de mercenários e missões.

---

## MVP-047 — QA automatizado de conteúdo e balanceamento final pós-refino

### Objetivo

Criar validações automáticas para impedir regressões na massa de conteúdo.

### Justificativa

Com milhares de registros, revisão manual não basta. É necessário validar nomes, faixas, XP, gold, loot, raridade, duplicidade e progressão por script.

### Validadores obrigatórios

Criar script:

```text
scripts/balance/validate_content.py
```

Validar:

- Nomes visíveis sem sequenciais artificiais.
- Nomes em Português BR.
- Ausência de termos em inglês na interface.
- Missões sem duplicidade visual/mecânica.
- Dungeons sem duplicidade visual/mecânica.
- XP crescente por faixa.
- Gold crescente por faixa.
- Duração compatível com recompensa.
- Loot compatível com faixa.
- Drops raros não aparecem cedo demais.
- Quantidade de drop não explode no early game.
- Cada material possui uso.
- Cada item possui origem.
- Cada item possui destino/uso/venda.
- Cada classe possui skill útil.
- Cada skill possui descrição.
- Cada classe possui atributos recomendados.
- Ladino usa AGI + INT.
- Arqueiro não replica a mesma identidade do Ladino.
- Missões por faixa atendem quantidade mínima calculada.
- Dungeons por faixa atendem quantidade mínima calculada.
- Conteúdo endgame incentiva raridades melhores.

### Regex proibido para nomes visuais

Bloquear padrões como:

```regex
.*-\s?\d{3}$
.*\s\d+-\d{3}$
.*_\d{3}$
.*\b00\d\b.*
```

Ajustar regex conforme padrão real encontrado no banco.

### Relatório final

Gerar relatório em Markdown ou JSON:

```text
reports/content_balance_report.md
reports/content_balance_report.json
```

O relatório deve conter:

- Total de missões por faixa.
- Total de dungeons por faixa.
- Total de missões de coleta por família.
- XP médio por faixa.
- Gold médio por faixa.
- Tempo médio por faixa.
- Loot médio por faixa.
- Itens sem uso.
- Materiais sem uso.
- Nomes corrigidos.
- Duplicidades corrigidas.
- Conteúdos desativados.
- Resultado da simulação p50/p90/p95.

### Critérios de aceite

- Existe validação automatizada.
- Existe relatório de balanceamento.
- Não há nomes sequenciais visíveis.
- Não há duplicidade grosseira.
- Progressão está validada por simulação.
- Conteúdo está pronto para nova rodada de teste real.

---

# Gatilhos claros de autonomia para o Codex

O Codex tem autonomia para:

- Renomear missões, dungeons e conteúdos com nomes artificiais.
- Criar variações semânticas de nomes quando necessário.
- Desativar conteúdo redundante, desde que não apague histórico do usuário.
- Reorganizar missões por faixa de nível.
- Ajustar XP, gold, duração e chance de sucesso.
- Ajustar loot e quantidades.
- Ajustar raridade de drops.
- Ajustar requisitos de poder.
- Criar scripts de simulação.
- Criar scripts de validação.
- Criar relatórios de balanceamento.
- Alterar escalas de atributos das classes conforme diretriz.
- Revisar skills para criar diversidade real.
- Criar guia de habilidades e combinações.
- Ajustar progressão de gold e custos quando detectar inconsistência.
- Criar novas missões/dungeons apenas se a simulação mostrar falta de cobertura.
- Reduzir ou desativar conteúdo repetitivo quando houver excesso sem valor.

O Codex não deve:

- Apagar progresso do usuário sem migração.
- Exibir códigos sequenciais em tela.
- Criar nomes em inglês.
- Criar cinco missões iguais com nomes quase iguais.
- Balancear apenas no olho.
- Fazer endgame ser fácil com qualquer mercenário comum mal equipado.
- Bloquear toda progressão principal atrás de raridade específica.
- Criar gold sink sem fonte de farm correspondente.
- Criar material sem uso.
- Criar item sem origem ou destino.

---

# Ordem recomendada das entregas

```text
MVP-035 — Auditoria semântica e renomeação de missões/dungeons
MVP-036 — Simulador de progressão de XP, gold e tempo
MVP-037 — Rebalanceamento linear de missões, gold, XP e recompensas
MVP-038 — Rebalanceamento de missões de coleta e materiais
MVP-039 — Rebalanceamento de dungeons e progressão de dificuldade
MVP-040 — Rebalanceamento de loot, itens, armas e economia de materiais
MVP-041 — UX de missões/dungeons e atalho para receber loot
MVP-042 — Revisão de skills por classe, diversidade e poder de escolha
MVP-043 — Revisão de atributos e escalas das classes
MVP-044 — Guia de habilidades, classes e combinações
MVP-045 — Rebalanceamento de raridade, party power e endgame
MVP-046 — Rebalanceamento integrado de gold, construções, Docas, Mercado e progressão da guilda
MVP-047 — QA automatizado de conteúdo e balanceamento final pós-refino
```

---

# Prioridade prática

A próxima entrega deve ser:

```text
MVP-035 — Auditoria semântica e renomeação de missões/dungeons
```

Motivo: antes de ajustar números, o conteúdo precisa deixar de parecer artificial na interface. Missões e dungeons com sufixos sequenciais quebram a percepção de qualidade.

Depois disso, a entrega mais importante é:

```text
MVP-036 — Simulador de progressão de XP, gold e tempo
```

Motivo: sem simulação, qualquer ajuste de XP, gold, tempo e loot vira chute.

A sequência ideal é:

```text
Limpar nomes → simular progressão → ajustar missões → ajustar coleta → ajustar dungeons → ajustar loot/economia → melhorar UX → revisar skills/classes → validar endgame → gerar QA automatizado
```

---

# Resultado esperado após o ciclo

Ao final dessas entregas, o jogo deve ter:

- Missões com nomes bons e sem códigos sequenciais.
- Dungeons com identidade própria.
- Progressão linear até o nível 350.
- XP, gold e tempo validados por simulação.
- Missões suficientes por faixa, sem excesso inútil.
- Missões de coleta úteis e objetivas.
- Loot variado e coerente.
- Materiais conectados com craft, refino, construções, Docas e Mercado.
- Skills com diversidade real.
- Classes com atributos mais bem definidos.
- Ladino diferenciado do Arqueiro.
- Guia para o usuário entender skills e combinações.
- Endgame que incentiva mercenários de tiers melhores.
- Common-only possível, mas difícil e ineficiente no final.
- Gold com fonte e dreno equilibrados.
- Relatórios de validação para evitar regressão.

