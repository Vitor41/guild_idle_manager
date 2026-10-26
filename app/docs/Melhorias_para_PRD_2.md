# Melhorias para PRD 2 — Guild Idle Manager

## Contexto

Este documento consolida melhorias identificadas após aproximadamente 3 dias de teste jogando do zero.

O documento anterior, `Melhorias para PRD`, já tratava ajustes estruturais de construções, Taverna, nível máximo 50, benefícios visíveis, Alojamento, Tesouro da Guilda, UI de missões, profissões, missões longas de 8h, filtros, histórico, Armazenamento e QA de construções.

Este novo documento deve ser tratado como uma continuação da frente de preparação para PRD, com foco em experiência real de early game, progressão, farm, coleta, idle, loot, qualidade de vida e validação end-to-end.

A última entrega considerada no documento anterior foi:

```text
MVP-050 — Revisão do Armazém/Armazenamento para bônus fixo de materiais
```

Portanto, este documento inicia a partir da:

```text
MVP-051
```

---

# Objetivo geral

Melhorar a experiência real do jogador nos primeiros dias de jogo, evitando que ele:

- Fique preso farmando apenas missões de coleta.
- Ignore missões normais por falta de relevância no early game.
- Não veja vantagem em equipamentos nos níveis 1–20.
- Sinta falta de alternativas para períodos idle.
- Tenha excesso de missões repetidas com pouco valor prático.
- Sinta dificuldade excessiva para obter materiais básicos.
- Tenha esforço operacional desnecessário para coletar múltiplos loots.
- Receba drops de equipamento com chances pouco naturais por raridade.
- Avance sem uma validação real da progressão early, mid e late game.

O objetivo não é facilitar demais o jogo. O objetivo é deixar a progressão mais coerente, com escolhas reais entre:

```text
Farm ativo de XP/gold
Farm de materiais
Missões longas idle
Progressão offline
Busca por equipamentos
Evolução de construções
```

---

# Diretrizes gerais para o Codex

## 1. Tratar este documento como backlog complementar de PRD

O Codex deve implementar estas melhorias considerando que o jogo já possui:

- Missões normais.
- Missões de coleta.
- Dungeons/Masmorras.
- Chefes, se já estiverem ativos.
- Sistema de loot.
- Sistema de profissões.
- Sistema de idle offline.
- Sistema de construções.
- Armazém/Armazenamento com bônus fixo de materiais, conforme documento PRD anterior.
- Limite de missões longas, conforme documento PRD anterior.

## 2. Não criar sistemas paralelos

Sempre que possível, usar serviços, models, enums e seeds existentes.

Se já existir estrutura para:

- Mission.
- MissionReward.
- MissionLoot.
- Dungeon.
- IdleReward.
- ProfessionBonus.
- EquipmentDrop.
- GuildMaterial.

Então o Codex deve reaproveitar e expandir essas estruturas.

## 3. Tudo precisa ser validável por simulação

Toda alteração de progressão, XP, gold, material e loot precisa ter suporte de simulação ou relatório.

O Codex deve criar scripts ou comandos de QA capazes de responder:

- Quanto tempo leva para um mercenário ir do nível 1 ao 20?
- Quantas missões de coleta são necessárias para evoluir construções básicas?
- Qual é a melhor rota de farm no early game?
- As missões normais competem minimamente com as missões de coleta?
- O idle offline ajuda sem substituir o farm ativo?
- O loot de equipamento está coerente por raridade?

## 4. O jogo deve continuar exigindo escolha

As melhorias não devem transformar o jogo em recompensa automática.

Regras importantes:

- Coleta deve continuar sendo a melhor rota para materiais.
- Missões normais devem ser melhores para XP/gold e equipamentos.
- Missões longas idle devem ser úteis, mas inferiores ao farm ativo.
- Idle offline deve ajudar, mas não substituir coleta ativa.
- Equipamentos comuns podem aparecer cedo, mas tiers altos devem continuar raros.

---

# MVP-051 — Rebalanceamento do early game entre missões normais e missões de coleta

## Objetivo

Corrigir o comportamento observado no teste em que o jogador tende a usar quase exclusivamente missões de coleta no início do jogo, mesmo com XP e gold inferiores, porque os materiais básicos são mais necessários para evoluir construções.

## Problema identificado

Durante o teste inicial, o jogador percebeu que:

- Materiais básicos são difíceis de obter.
- Evoluir construções depende fortemente desses materiais.
- As missões de coleta acabam sendo feitas repetidamente.
- Mesmo com XP/gold menos favoráveis, as missões de coleta sobem bastante o nível dos mercenários por repetição.
- Missões normais com recompensa de equipamentos não parecem necessárias no nível 1–20.
- Equipamentos no early game ainda não geram urgência suficiente para competir com materiais.

## Decisão de produto

As missões de coleta devem continuar sendo importantes, mas não devem engolir o loop inteiro do early game.

O jogador deve perceber três caminhos claros:

```text
Missões de coleta = materiais para construção
Missões normais = XP, gold e equipamentos
Missões longas = progresso idle controlado
```

## Regras de negócio

- Missões de coleta devem ter XP/gold inferiores às missões normais equivalentes.
- Missões normais devem ter XP/gold suficientemente melhores para serem atrativas.
- Missões normais early game devem dropar equipamentos comuns com chance relevante.
- Equipamentos comuns early game devem ter impacto perceptível, mesmo que pequeno.
- Materiais básicos não devem ser tão escassos a ponto de invalidar missões normais.
- O jogador deve conseguir alternar entre coleta e missões normais sem sentir que está perdendo progresso.

## Diretriz de balanceamento

Para cada faixa de nível, o Codex deve comparar:

```text
XP/hora de missão normal
Gold/hora de missão normal
Material/hora de missão de coleta
XP/hora de missão de coleta
Gold/hora de missão de coleta
Valor esperado de equipamento/hora
```

Regra sugerida:

```text
Missão normal deve entregar de 20% a 40% mais XP/hora do que coleta equivalente.
Missão normal deve entregar de 20% a 50% mais gold/hora do que coleta equivalente.
Coleta deve entregar materiais de forma superior e previsível.
```

## Ajuste esperado no early game

Na faixa 1–20:

- Coleta continua sendo necessária.
- Missões normais devem ser a melhor opção para subir nível e juntar gold.
- Equipamentos comuns devem começar a fazer diferença em chance de sucesso, atributos ou poder total.
- O jogador deve ter motivo para fazer missões normais antes de desbloquear conteúdos mais difíceis.

## Critérios de aceite

- Revisar recompensas das missões normais e de coleta na faixa 1–20.
- Garantir que missões normais sejam competitivas em XP/gold.
- Garantir que coleta continue sendo a principal fonte de materiais.
- Garantir que equipamentos comuns early game tenham utilidade mínima real.
- Criar relatório comparando XP/h, gold/h e materiais/h nas rotas de early game.
- Evitar que a melhor estratégia absoluta seja repetir apenas coleta o tempo todo.
- Manter textos em Português BR.

---

# MVP-052 — Revisão da massa de missões de coleta e remoção de duplicidades por nível/material

## Objetivo

Refinar missões de coleta para reduzir duplicidade, manter gaps de nível interessantes e melhorar a progressão linear sem excesso de missões redundantes.

## Problema identificado

Foi observado que existem múltiplas missões de coleta do mesmo material no mesmo nível ou muito próximas, o que pode gerar sensação de conteúdo repetido sem necessidade.

Exemplo observado:

```text
Coleta de madeira com missões nos níveis 1, 5, 9, 13 e 17.
Em alguns níveis existem 2 missões parecidas para o mesmo material.
```

O conceito de gaps de nível foi considerado positivo, porque força o jogador a usar missões inferiores até alcançar o próximo marco. Porém, duplicar missão do mesmo nível/material parece desperdício.

## Decisão de produto

Manter gaps de nível nas missões de coleta, mas remover duplicidades desnecessárias.

## Regras de negócio

- Não deve existir mais de uma missão de coleta pura para o mesmo material no mesmo nível/faixa, salvo justificativa clara.
- Se houver duas missões parecidas, elas devem ter função diferente.
- Uma missão pode ser mantida se tiver material + chance de equipamento.
- Missões repetidas que só mudam nome ou número devem ser removidas ou fundidas.
- A progressão deve manter gaps planejados entre níveis de coleta.

## Regra de diversidade

Em vez de duas missões iguais, usar variações com propósito:

```text
Coleta pura de madeira = foco em madeira
Exploração do bosque = madeira + chance baixa de equipamento comum
Patrulha no bosque = XP/gold melhor + chance baixa de madeira
```

Mas evitar criar 5 missões equivalentes que entregam quase a mesma coisa.

## Diretriz para distribuição por material

Para cada material básico, manter uma cadência parecida com:

```text
Nível 1
Nível 3 ou 5
Nível 8 ou 10
Nível 13 ou 15
Nível 17 ou 20
```

O Codex pode ajustar os níveis conforme a estrutura atual, desde que:

- Não haja buracos grandes demais no early game.
- Não haja excesso de duplicidade.
- Cada missão tenha motivo claro para existir.

## Critérios de aceite

- Identificar missões de coleta duplicadas por material e nível.
- Remover, fundir ou transformar duplicidades em variações com propósito real.
- Manter gaps de progressão entre missões de coleta.
- Garantir que cada material básico tenha rota clara de obtenção.
- Garantir que missões de coleta com equipamento tenham chance menor de drop do que missões normais.
- Gerar relatório listando missões removidas, mantidas e ajustadas.

---

# MVP-053 — Progressão ilusória de XP nas missões de coleta nível 1–9

## Objetivo

Melhorar a percepção de progressão no early game, criando pequenos aumentos de XP entre níveis 1 e 9, mesmo que o balanceamento total continue próximo do atual.

## Problema identificado

Foi observado que algumas missões de coleta entre níveis 1 e 5 dão praticamente o mesmo XP, aumentando apenas um pouco o gold. O XP só parece mudar de forma mais clara perto do nível 10.

Isso reduz a sensação de crescimento nos primeiros níveis.

## Decisão de produto

Criar pequenos aumentos graduais de XP nas missões de coleta entre níveis 1 e 9.

Se necessário, reduzir um pouco o XP das missões nível 1 para permitir crescimento gradual sem inflar demais a progressão.

## Regra de negócio

- Missões de coleta nível 1 devem ter XP menor que missões nível 5.
- Missões de coleta nível 5 devem ter XP menor que missões nível 9.
- A diferença pode ser pequena, mas deve existir.
- O objetivo é gerar sensação de evolução sem acelerar demais o leveling.

## Exemplo conceitual

Se hoje as missões nível 1 e 5 entregam 80 XP, ajustar para algo próximo de:

```text
Nível 1: 65 XP
Nível 3: 70 XP
Nível 5: 75 XP
Nível 9: 85 XP
```

Os valores reais devem ser calculados pelo Codex com base na curva atual.

## Regra para não quebrar a progressão

O XP/hora das missões de coleta deve continuar inferior ao XP/hora das missões normais equivalentes.

## Critérios de aceite

- Revisar XP das missões de coleta de nível 1 a 9.
- Criar crescimento gradual e perceptível de XP.
- Evitar salto brusco apenas no nível 10.
- Garantir que coleta não vire melhor fonte de XP que missão normal.
- Criar simulação de quantas coletas são necessárias para ir do nível 1 ao 10.
- Criar simulação de quantas missões normais são necessárias para ir do nível 1 ao 10.

---

# MVP-054 — Missões longas idle de 1h, 3h e 8h por faixa de nível

## Objetivo

Criar alternativas de missões longas para momentos em que o jogador ficará ocioso, sem substituir o farm ativo e sem banalizar loot.

## Problema identificado

Durante o teste, foi sentida falta de missões mais longas. O jogador nem sempre estará ativo para repetir missões curtas, e precisa ter uma forma de deixar mercenários ocupados por períodos maiores.

## Decisão de produto

Criar missões longas de:

```text
1 hora
3 horas
8 horas
```

em cada faixa de nível relevante.

Essas missões devem funcionar como opção idle manual, não como melhor rota de farm.

## Regras de chance fixa

As chances dessas missões devem ser fixas, não escaladas por poder total como missões normais.

```text
Missão longa 1h: 75% de chance de sucesso
Missão longa 3h: 70% de chance de sucesso
Missão longa 8h: 60% de chance de sucesso
```

## Regras de recompensa

Missões longas devem recompensar apenas:

```text
XP
Gold
```

Não devem dropar:

```text
Equipamentos
Materiais
Cristais
Itens raros
```

Motivo: não banalizar o farm ativo, coleta, dungeons, chefes, Docas ou Mercado.

## Fórmula de recompensa

Para cada faixa de nível, calcular:

```text
max_gold_ativo_por_hora_da_faixa
max_xp_ativo_por_hora_da_faixa
```

A recompensa máxima de sucesso da missão longa deve ser:

```text
recompensa_gold = floor(max_gold_ativo_por_hora_da_faixa × 0.5 × duração_horas)
recompensa_xp = floor(max_xp_ativo_por_hora_da_faixa × 0.5 × duração_horas)
```

Exemplo:

```text
Se a faixa 1–20 permite ganhar no máximo 1.000 gold/h e 1.000 XP/h ativamente:

Missão 8h:
Gold = 1.000 × 0.5 × 8 = 4.000
XP = 1.000 × 0.5 × 8 = 4.000
Chance = 60%
```

## Regra de limite simultâneo

Deve existir limite global por guilda:

```text
Máximo de 3 missões longas simultâneas
```

Esse limite vale somando todas as durações:

```text
1h + 3h + 8h = todas contam para o limite de 3
```

## Regra de participação

Cada missão longa deve exigir apenas:

```text
1 mercenário
```

O jogador pode enviar até 3 mercenários separadamente, respeitando o limite global.

## Requisito de nível

Cada missão longa deve exigir o nível mais baixo da respectiva faixa.

Exemplo:

```text
Faixa 1–20: nível mínimo 1
Faixa 21–50: nível mínimo 21
Faixa 51–100: nível mínimo 51
```

## Nome e narrativa

Os nomes devem seguir a ideia de defesa, patrulha, vigia ou proteção da guilda.

Exemplos:

```text
Vigia dos Portões
Patrulha Noturna
Ronda dos Arredores
Guarda da Estrada Norte
Sentinela da Muralha
Vigília da Guilda
Patrulha do Bosque Externo
Ronda contra Invasores
```

Evitar nomes genéricos com sufixos numéricos.

## Critérios de aceite

- Criar missões longas de 1h, 3h e 8h por faixa de nível.
- Aplicar chances fixas de 75%, 70% e 60%.
- Aplicar limite máximo de 3 missões longas simultâneas por guilda.
- Exigir 1 mercenário por missão longa.
- Não permitir loot de item/material nessas missões.
- Calcular recompensa com base em 50% do melhor farm ativo por hora da faixa.
- Criar relatório com cálculo de XP/gold por faixa e duração.
- Exibir claramente na UI que a missão longa não possui loot.
- Exibir claramente o limite de 3 missões longas simultâneas.
- Manter nomes narrativos sem numeração sequencial.

---

# MVP-055 — Recompensas de materiais no idle offline deslogado

## Objetivo

Adicionar ganho controlado de materiais básicos ao idle offline deslogado, sem substituir missões de coleta.

## Problema identificado

No early game, o jogador sente dificuldade em obter materiais básicos para evoluir construções. O idle offline atualmente recompensa ouro, mas não ajuda com madeira, minério e cristais.

## Decisão de produto

O idle offline deve gerar também:

```text
Madeira
Minério
Cristal, apenas em caso específico
```

A recompensa de materiais deve escalar junto com o ouro/hora, mas em quantidade menor e controlada.

## Regra de cálculo

Usar o gold/hora efetivo do idle como base.

```text
madeira_por_hora = floor(gold_por_hora × 0.60)
minerio_por_hora = floor(gold_por_hora × 0.40)
```

Exemplo:

```text
Gold/hora: 20
Madeira/hora: 12
Minério/hora: 8
```

Para 8 horas:

```text
Gold: 160
Madeira: 96
Minério: 64
```

## Regra de cristal

Cristal deve ser extremamente controlado no idle offline.

Regra:

```text
Se o jogador atingir o limite máximo de 8h de idle offline efetivo:
    ganha 1 cristal
Caso contrário:
    ganha 0 cristal
```

Se o limite configurado futuramente for diferente, a regra deve considerar o limite máximo configurado, não um número fixo espalhado no código.

## Interação com Armazém/Armazenamento

O Codex deve revisar a interação com o Armazém.

Se o Armazém já gera bônus fixo de materiais, o idle offline deve usar uma regra clara para evitar duplicidade excessiva.

Diretriz recomendada:

```text
Idle offline calcula materiais base.
Depois aplica bônus fixo de Armazém, se essa for a regra efetiva atual.
O bônus deve ser exibido separadamente no resumo.
```

Exemplo de UI:

```text
Resumo offline:
Tempo ausente: 8h
Ouro: +160
Madeira base: +96
Bônus do Armazém: +X
Madeira total: +96 + X
Minério base: +64
Bônus do Armazém: +Y
Minério total: +64 + Y
Cristal: +1
```

## Restrições

- Idle offline não deve gerar equipamentos.
- Idle offline não deve gerar materiais raros além de cristal pela regra especial.
- Idle offline não deve gerar loot de dungeon.
- Idle offline não deve substituir missões de coleta.

## Critérios de aceite

- Fazer idle offline gerar madeira e minério.
- Fazer madeira escalar com 60% do gold/hora.
- Fazer minério escalar com 40% do gold/hora.
- Fazer cristal gerar apenas 1 unidade ao atingir o limite máximo de idle efetivo.
- Exibir materiais no resumo de retorno offline.
- Exibir bônus do Armazém separadamente, se aplicado.
- Garantir que materiais de idle sejam inferiores ao farm ativo de coleta.
- Criar testes para idle de 1h, 3h e 8h.
- Criar teste específico validando cristal apenas no limite máximo.

---

# MVP-056 — Botão “Receber todos os loots” nas telas com coleta de recompensa

## Objetivo

Adicionar melhoria de qualidade de vida para coletar todos os loots disponíveis em telas que possuem fluxo de recebimento de recompensa.

## Problema identificado

O jogador sente falta de um botão para receber todos os loots disponíveis de uma vez, especialmente quando há várias missões concluídas.

## Decisão de produto

Criar botão global/contextual:

```text
Receber todos os loots
```

ou, se o termo visual do sistema estiver usando “Coletar”:

```text
Coletar todos
```

## Telas impactadas

O Codex deve localizar todas as telas que possuem fluxo de recompensa pendente, incluindo, se existirem:

- Missões.
- Missões de coleta.
- Missões longas.
- Dungeons/Masmorras.
- Chefes.
- Mercado, se houver coleta de venda concluída.
- Docas, se houver coleta/compra pendente.
- Qualquer outra fila de loot.

## Regras de negócio

- O botão deve coletar apenas recompensas já concluídas.
- Não deve coletar missões em andamento.
- Não deve ignorar validações de inventário, limite ou erro.
- Se alguma coleta falhar, o sistema deve coletar as válidas e informar as falhas.
- Deve exibir resumo consolidado do que foi recebido.

## Exemplo de resumo

```text
Recompensas coletadas:
Ouro: +1.250
XP distribuído: +840
Madeira: +32
Minério: +18
Equipamentos: 2
Missões com falha ao coletar: 1
```

## Diretriz técnica

Criar endpoint/service específico para coleta em massa.

Evitar apenas simular múltiplos cliques pelo frontend.

O serviço deve:

- Buscar recompensas pendentes.
- Validar conclusão.
- Aplicar recompensas em transação segura.
- Marcar como coletadas.
- Retornar resumo estruturado.

## Critérios de aceite

- Exibir botão “Receber todos os loots” ou “Coletar todos”.
- Coletar todas as recompensas concluídas da tela atual.
- Não coletar recompensas em andamento.
- Exibir resumo consolidado.
- Tratar falhas parciais com mensagem clara.
- Garantir operação transacional sempre que possível.
- Manter UX/UI medieval atual.
- Manter textos em Português BR.

---

# MVP-057 — Rebalanceamento da taxa de drop de equipamentos por raridade

## Objetivo

Corrigir a falta de diversidade nas taxas de drop de equipamentos, fazendo itens comuns droparem mais e tiers altos droparem menos.

## Problema identificado

Nas missões normais, a taxa de drop de equipamentos parece igual independentemente do tier, por exemplo 11% para diferentes raridades.

Isso reduz a sensação de raridade e compromete o balanceamento de progressão.

## Decisão de produto

A chance de drop deve variar por raridade.

Itens comuns devem ser mais fáceis.
Itens raros, épicos e lendários devem ser progressivamente mais difíceis.

## Regras para missões normais

Sugestão inicial de drop por raridade em missões normais:

| Raridade | Chance base sugerida |
|---|---:|
| Comum | 40% |
| Incomum | 25% |
| Raro | 12% |
| Épico | 5% |
| Lendário | 1% |
| Mítico, se existir | 0,25% |

O Codex pode ajustar os valores por faixa de nível, mas deve manter o princípio:

```text
Comum > Incomum > Raro > Épico > Lendário > Mítico
```

## Regras para missões de coleta

Missões de coleta podem dropar equipamentos, mas não devem ter isso como foco.

Sugestão inicial:

| Raridade | Chance base sugerida em coleta |
|---|---:|
| Comum | 20% |
| Incomum | 10% |
| Raro | 4% |
| Épico | 1% |
| Lendário | 0,25% |
| Mítico, se existir | 0,05% |

## Regras para Dungeons/Masmorras e Chefes

O Codex deve revisar também Dungeons/Masmorras e Chefes.

Diretriz:

- Dungeons devem ter chance maior de equipamentos raros que missões normais.
- Chefes devem ter chance ainda maior de equipamentos raros, épicos e lendários.
- Mesmo assim, itens de tier alto não devem ser triviais.

Sugestão conceitual:

```text
Missão normal = melhor para XP/gold/equipamento comum
Coleta = melhor para material, baixa chance de equipamento
Dungeon = melhor para equipamento raro
Chefe = melhor para equipamento épico/lendário
```

## Interação com Ferreiro

Se o Ferreiro aumenta chance de drop ou qualidade de equipamento, o bônus deve ser aplicado de forma clara e exibida na UI.

Exemplo:

```text
Chance base de item comum: 40%
Bônus do Ferreiro: +5 p.p.
Chance final: 45%
```

Não exibir apenas a chance base se o jogador possui bônus ativo.

## Critérios de aceite

- Implementar chance de drop diferente por raridade.
- Missões normais devem ter comum em torno de 40% no early game, salvo ajuste justificado.
- Missões de coleta devem ter comum em torno de 20%, mantendo foco em materiais.
- Dungeons devem ser melhores para equipamentos raros.
- Chefes devem ser melhores para equipamentos de tier alto.
- Garantir que UI exiba chance efetiva quando aplicável.
- Criar simulação de 1.000 execuções por tipo de conteúdo para validar distribuição.
- Gerar relatório de distribuição esperada por raridade.
- Garantir nomes e raridades em Português BR.

---

# MVP-058 — Revisão end-to-end de progressão early, mid e late game com relatório QA

## Objetivo

Executar QA end-to-end usando os scripts e validações já desenvolvidos para identificar gargalos, conteúdos desnecessários, falhas de progressão e pontos nocivos à experiência do jogo.

## Problema identificado

O jogo já possui muita massa de dados. Agora é necessário validar se essa massa realmente sustenta uma progressão linear, interessante e sem excesso inútil.

## Decisão de produto

Criar uma rodada formal de QA de progressão simulando o jogo desde o early até o late game.

O resultado final deve ser um relatório `.md` gerado pelo Codex com achados, métricas e recomendações.

## Escopos obrigatórios da validação

O QA deve avaliar:

- Progressão de mercenários do nível 1 ao 350.
- Progressão da guilda.
- Evolução de construções até o nível máximo atual.
- Farm de gold.
- Farm de materiais.
- Uso de missões normais.
- Uso de missões de coleta.
- Uso de missões longas.
- Idle offline.
- Dungeons/Masmorras.
- Chefes.
- Drops de equipamentos.
- Utilidade de equipamentos por faixa.
- Gargalos de materiais básicos.
- Gargalos de minério/cristal.
- Gargalos de gold.
- Missões redundantes ou inúteis.
- Dungeons redundantes ou inúteis.
- Conteúdos com recompensa irrelevante.
- Conteúdos com recompensa exagerada.

## Perfis de simulação

Criar pelo menos três perfis:

### Jogador ativo

```text
Faz muitas missões curtas.
Coleta loot com frequência.
Prioriza eficiência de XP/gold.
```

### Jogador híbrido

```text
Alterna missões curtas, coleta, missões longas e idle offline.
Representa o jogador mais provável.
```

### Jogador casual/idle

```text
Usa mais missões longas e idle offline.
Faz menos sessões ativas.
Deve progredir, mas mais lentamente.
```

## Métricas mínimas do relatório

O relatório deve conter:

```text
Tempo estimado para nível 20
Tempo estimado para nível 50
Tempo estimado para nível 100
Tempo estimado para nível 200
Tempo estimado para nível 350
Quantidade média de missões por faixa
Gold médio ganho por faixa
Gold médio gasto por faixa
Materiais médios ganhos por faixa
Materiais médios gastos por faixa
Construções que travam progressão
Missões mais usadas
Missões ignoradas
Dungeons mais usadas
Dungeons ignoradas
Equipamentos obtidos por raridade
Pontos de excesso de grind
Pontos de progressão rápida demais
```

## Regras de decisão

O relatório deve classificar achados em:

```text
Crítico
Alto
Médio
Baixo
Observação
```

Exemplos:

```text
Crítico: progressão trava por falta de madeira antes do nível 10.
Alto: missões normais são sempre piores que coleta no early game.
Médio: dungeon X nunca é a melhor opção de farm.
Baixo: recompensa de gold levemente abaixo do esperado.
Observação: conteúdo existe, mas é mais narrativo do que eficiente.
```

## Saída esperada

Gerar arquivo:

```text
relatorio_qa_progressao_end_to_end.md
```

O relatório deve conter:

- Sumário executivo.
- Tabelas por faixa de nível.
- Principais gargalos.
- Conteúdos redundantes.
- Recomendações objetivas.
- Itens sugeridos para remoção, ajuste ou manutenção.
- Evidências dos cálculos/simulações.

## Critérios de aceite

- Criar ou reaproveitar scripts de QA existentes.
- Simular progressão early, mid e late game.
- Gerar relatório `.md` com resultados.
- Identificar gargalos de gold, XP e materiais.
- Identificar missões/dungeons desnecessárias.
- Propor ajustes objetivos com base nos dados.
- Validar se o jogador comum consegue progredir sem ficar preso por falta de conteúdo.
- Validar se o jogador não consegue trivializar o jogo só com idle.
- Validar se o farm ativo continua tendo valor.

---

# Priorização recomendada

A ordem recomendada de implementação é:

```text
MVP-051 — Rebalanceamento do early game entre missões normais e missões de coleta
MVP-052 — Revisão da massa de missões de coleta e remoção de duplicidades por nível/material
MVP-053 — Progressão ilusória de XP nas missões de coleta nível 1–9
MVP-054 — Missões longas idle de 1h, 3h e 8h por faixa de nível
MVP-055 — Recompensas de materiais no idle offline deslogado
MVP-056 — Botão “Receber todos os loots” nas telas com coleta de recompensa
MVP-057 — Rebalanceamento da taxa de drop de equipamentos por raridade
MVP-058 — Revisão end-to-end de progressão early, mid e late game com relatório QA
```

## Observação de prioridade

As MVPs 051, 052, 053 e 057 impactam diretamente o equilíbrio do early game.

A MVP-056 é qualidade de vida e pode ser feita em paralelo.

A MVP-058 deve vir depois dos principais ajustes, porque ela precisa validar o jogo já com as novas regras aplicadas.

---

# Checklist de implementação para o Codex

Antes de finalizar este pacote, validar:

- [ ] Missões de coleta não são a única escolha eficiente no early game.
- [ ] Missões normais têm vantagem clara em XP/gold.
- [ ] Missões de coleta mantêm vantagem clara em materiais.
- [ ] Equipamentos comuns têm utilidade mínima no nível 1–20.
- [ ] Missões de coleta duplicadas foram removidas, fundidas ou diferenciadas.
- [ ] Gaps de nível nas coletas foram mantidos de forma intencional.
- [ ] XP das coletas nível 1–9 possui progressão gradual.
- [ ] Missões longas de 1h, 3h e 8h existem por faixa.
- [ ] Missões longas têm chances fixas de 75%, 70% e 60%.
- [ ] Missões longas não dropam loot/material.
- [ ] Limite de 3 missões longas simultâneas foi aplicado.
- [ ] Idle offline gera madeira e minério.
- [ ] Idle offline gera 1 cristal apenas ao atingir o limite máximo.
- [ ] Idle offline exibe resumo claro de materiais.
- [ ] Botão “Receber todos os loots” foi criado.
- [ ] Coleta em massa respeita validações e transações.
- [ ] Drop de equipamento varia por raridade.
- [ ] Missões normais têm maior chance de equipamento comum que coletas.
- [ ] Dungeons e chefes têm papel claro no farm de equipamentos melhores.
- [ ] Relatório QA end-to-end é gerado em `.md`.
- [ ] Textos estão em Português BR.
- [ ] Acentuação está correta.
- [ ] UI mantém identidade medieval/fantasia atual.

---

# Observação final

Este documento não deve ser interpretado como pedido para facilitar o jogo indiscriminadamente.

A intenção é corrigir a experiência real observada no início do jogo:

```text
materiais são necessários demais,
coleta fica dominante demais,
missões normais perdem relevância cedo,
idle offline ajuda pouco na progressão material,
loot de equipamento precisa ter raridade mais natural,
e o jogo precisa de validação end-to-end com dados.
```

O resultado esperado é uma progressão mais saudável, onde o jogador entende por que escolher cada tipo de conteúdo e sente que sempre há algo útil para fazer, seja ativo ou idle.
