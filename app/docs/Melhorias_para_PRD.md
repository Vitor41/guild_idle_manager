# Melhorias para PRD — Guild Idle Manager

> Versão atualizada com ajustes de Alojamento, melhorias de UX global, seleção de mercenários, missões longas, filtros de coleta, bônus de profissão, conquistas, histórico de loot e rework do Armazém.


## Contexto

Este documento é um backlog vivo de melhorias para preparação do Guild Idle Manager para PRD.

O usuário iniciará um teste de aproximadamente 1 semana começando o jogo do zero. Durante esse período, novos pontos de melhoria serão identificados, refinados e adicionados a este documento.

A última entrega considerada como concluída e funcional é:

```text
MVP-034 — Validação final de conteúdo, QA e balanceamento de massa
```

Portanto, este documento deve ser tratado como uma nova frente de refinamento pós-MVP-034, focada em:

- Corrigir problemas identificados em teste real.
- Melhorar clareza de progressão.
- Reduzir níveis sem ganho.
- Tornar construções mais relevantes.
- Melhorar a experiência de contratação na Taverna.
- Ajustar custos, ganhos e benefícios antes de PRD.
- Garantir que o jogador tenha motivos reais para evoluir cada sistema.

---

# Objetivo geral

Preparar o jogo para PRD com ajustes de balanceamento, UX e regras de progressão, evitando que o usuário:

- Invista em construções sem entender o benefício.
- Evolua construções por muitos níveis sem ganho real.
- Veja informações divergentes entre backend e interface.
- Sinta que a Taverna não compensa o investimento.
- Sinta que contratar mercenários fica punitivo demais sem nenhuma forma de mitigação.
- Gaste gold apenas por obrigação, sem percepção clara de recompensa.
- Precise abrir a Visão Geral para conferir materiais básicos da guilda.
- Tenha dificuldade para identificar nível, profissão e função de mercenários em telas de seleção.
- Fique sem opção de missão longa para períodos idle.
- Veja histórico de loot com textos técnicos, termos em inglês ou labels como `RNG`.

---

# Diretrizes gerais para o Codex

## 1. Este documento deve ser tratado como fonte de verdade para melhorias PRD

O Codex deve implementar as melhorias aqui descritas respeitando o estado atual do jogo após a MVP-034.

Antes de alterar código, deve vasculhar o projeto e localizar:

- Models.
- Services.
- Routes.
- Templates.
- Seeds.
- Configurações.
- Cálculos de custo.
- Cálculos de benefício.
- Telas de construções.
- Tela da Taverna.
- Tela de contratação.
- Tela de Admin, se aplicável.

## 2. Priorizar helpers centralizados para regra exibida e regra aplicada

Sempre que uma regra afetar cálculo, bônus, drop, tooltip, card ou histórico, o Codex deve criar ou reutilizar um helper/service único.

A regra não pode ser implementada apenas no template.

Exemplos obrigatórios:

- Chances efetivas da Taverna.
- Bônus de profissão em coleta.
- Bônus fixo do Armazém em materiais.
- Benefícios das construções por marco.
- Formatação de atributos e bônus de equipamentos em Português BR.

## 3. Não criar mecânicas paralelas desnecessárias

Sempre que já existir serviço, helper, cálculo ou template relacionado ao tema, deve reutilizar e centralizar.

Evitar duplicar regra em múltiplos arquivos.

## 4. Toda regra exibida na tela deve ser a regra efetiva

Nenhuma tela deve exibir valor base se o jogador está recebendo um valor efetivo modificado por construção, bônus, skill ou melhoria.

Exemplo:

```text
Errado:
Exibir Comum 90% / Incomum 10% na Taverna mesmo com Taverna nível 100.

Correto:
Exibir Comum 70% / Incomum 30% se este for o valor efetivo após bônus da Taverna.
```

## 5. O jogador precisa entender por que deve evoluir cada construção

Toda construção deve ter:

- Benefício atual visível.
- Próximo benefício visível.
- Marco de evolução relevante.
- Custo do próximo nível.
- Explicação objetiva do ganho.

## 6. Evitar níveis mortos

Não deve existir uma sequência grande de níveis sem ganho real.

Se o nível máximo for reduzido para 50, os ganhos devem ser redistribuídos para que a progressão fique mais densa e legível.

---

# MVP-035 — Correção de UX da Taverna: chances efetivas de contratação

## Objetivo

Corrigir a divergência entre a regra aplicada no backend e o que a tela da Taverna exibe para o usuário.

## Problema identificado

Atualmente, a regra de bônus da Taverna existe no backend para geração/contratação de Aprendizes, mas a interface exibe os percentuais base da configuração.

Exemplo atual observado:

```text
Configuração base:
Comum: 90%
Incomum: 10%

Com Taverna nível 100 pela regra atual:
Comum efetivo: 80%
Incomum efetivo: 20%

Tela ainda mostra:
Comum: 90%
Incomum: 10%
```

Isso causa percepção de que evoluir a Taverna não tem efeito.

## Regra de negócio

A tela da Taverna deve sempre exibir as chances efetivas, considerando o nível atual da construção.

A interface deve deixar claro:

- Chance base.
- Bônus da Taverna.
- Chance final.
- Nível atual da Taverna.
- Próximo marco de melhoria.

## Regras técnicas

Criar um helper único para cálculo de chances efetivas da Taverna.

Exemplo conceitual:

```python
def get_tavern_apprentice_chances(tavern_level, config):
    # Implementar regra final definida no MVP-037.
    # Retornar sempre valores efetivos, não apenas base.
    return {
        "common_base": ...,
        "uncommon_base": ...,
        "common_final": ...,
        "uncommon_final": ...,
        "bonus_uncommon_percentage_points": ...,
        "next_milestone_level": ...,
        "next_milestone_bonus": ...,
    }
```

Este helper deve ser usado em:

- Preview de Aprendiz.
- Contratação individual.
- Contratação em massa.
- Tela da Taverna.
- Resumo da construção Taverna.
- Qualquer endpoint/API que exponha dados da Taverna.

## Regra de invalidação de preview

Se existir preview de candidato salvo em sessão, cache ou estado temporário, ele deve ser invalidado quando:

- O nível da Taverna mudar.
- As configurações base de chance mudarem.
- O jogador realizar upgrade da Taverna.
- O usuário trocar de guilda/ambiente, se aplicável.

## Critérios de aceite

- Exibir na Taverna a chance efetiva de Aprendiz Comum.
- Exibir na Taverna a chance efetiva de Aprendiz Incomum.
- Exibir o bônus da Taverna em pontos percentuais.
- Exibir o próximo marco de melhoria.
- Usar o mesmo cálculo para interface e contratação real.
- Impedir divergência entre chance exibida e chance usada no backend.
- Invalidar preview de candidato quando a Taverna for evoluída.
- Garantir que Admin continue exibindo configuração base quando estiver editando configuração global, mas a tela do jogador deve exibir valor efetivo.
- Garantir que todos os textos estejam em Português BR.

---

# MVP-036 — Redução do nível máximo das construções para 50

## Objetivo

Reduzir o nível máximo das construções de 100 para 50, diminuindo buracos de progressão e tornando cada upgrade mais relevante.

## Justificativa

Hoje existem muitas construções com níveis altos sem ganho real.

Exemplos identificados:

- Escritório de Missões tem ganho relevante muito antes do nível 100.
- Exploradores tem ganho relevante muito antes do nível 100.
- Docas possui trechos finais com pouco ou nenhum ganho.
- Taverna chega ao nível 100 com ganho baixo demais.
- Alojamento tem níveis finais sem ganho efetivo.

O nível máximo 100 está alongando artificialmente a progressão sem entregar benefício proporcional.

## Decisão de produto

Reduzir o nível máximo de construções para:

```text
Nível máximo: 50
```

## Regra crítica

Não basta alterar `max_level = 100` para `max_level = 50`.

Todos os benefícios devem ser redistribuídos para que o nível 50 represente o novo pico funcional da construção.

## Marcos recomendados

As construções devem ter ganhos claros nos seguintes marcos:

```text
1, 5, 10, 15, 20, 25, 30, 35, 40, 45 e 50
```

Também podem existir ganhos menores por nível, desde que os marcos sejam claramente comunicados.

## Regras de migração

Se já existir banco com construções acima do nível 50:

- Construções acima de 50 devem ser limitadas para 50.
- O sistema não deve quebrar ao carregar construções antigas nível 100.
- Criar migração segura, se aplicável.
- Se necessário, criar script administrativo para normalizar dados existentes.
- Não permitir novo upgrade acima do nível 50.
- Exibir mensagem amigável quando construção estiver no nível máximo.

## Critérios de aceite

- Impedir construção acima do nível 50.
- Atualizar validações backend para máximo 50.
- Atualizar templates que mencionam nível máximo.
- Atualizar textos, tooltips e barras de progresso.
- Atualizar cálculo de requisitos de guilda, se existir.
- Atualizar seeds/configurações de construções.
- Criar migração segura para dados legados acima do nível 50.
- Garantir que nenhuma tela exiba progresso para nível 51.
- Garantir que cada construção tenha benefício relevante até o nível 50.

---

# MVP-037 — Rebalanceamento da Taverna

## Objetivo

Tornar a Taverna uma construção realmente estratégica, com ganho perceptível ao evoluir e impacto direto na contratação de mercenários.

## Problema atual

A Taverna custa muito para evoluir e entrega pouco.

Pela regra anterior, no nível 100, ela apenas aumentava a chance de Aprendiz Incomum de 10% para 20%.

Esse ganho é baixo para o investimento exigido.

## Nova regra de produto

Com o novo nível máximo 50, a Taverna deve entregar no nível máximo:

```text
Comum: 70%
Incomum: 30%
Desconto no custo de contratação: 20%
```

## Progressão recomendada

| Nível da Taverna | Comum | Incomum | Desconto no custo de contratação |
|---:|---:|---:|---:|
| 1 | 90% | 10% | 0% |
| 5 | 88% | 12% | 2% |
| 10 | 86% | 14% | 4% |
| 15 | 84% | 16% | 6% |
| 20 | 82% | 18% | 8% |
| 25 | 80% | 20% | 10% |
| 30 | 78% | 22% | 12% |
| 35 | 76% | 24% | 14% |
| 40 | 74% | 26% | 16% |
| 45 | 72% | 28% | 18% |
| 50 | 70% | 30% | 20% |

## Fórmula recomendada

A cada 5 níveis:

```text
+2 pontos percentuais de chance de Incomum
-2 pontos percentuais de chance de Comum
+2% de desconto no custo de contratação
```

Com teto em:

```text
+20 p.p. Incomum
-20 p.p. Comum
20% desconto
```

## Regra técnica sugerida

```python
def get_tavern_bonus_step(tavern_level: int) -> int:
    return min(10, max(0, tavern_level // 5))

def get_tavern_uncommon_bonus(tavern_level: int) -> int:
    return get_tavern_bonus_step(tavern_level) * 2

def get_tavern_hire_discount_percent(tavern_level: int) -> int:
    return get_tavern_bonus_step(tavern_level) * 2
```

## Cálculo de chance efetiva

```python
common_final = max(0, common_base - tavern_uncommon_bonus)
uncommon_final = min(100, uncommon_base + tavern_uncommon_bonus)
```

## Cálculo de custo efetivo

O custo interno de contratação deve continuar escalando para manter o gold sink.

O desconto da Taverna deve reduzir o custo pago pelo jogador, não apagar a progressão interna.

```python
final_cost = ceil(base_cost * (1 - hire_discount_percent / 100))
```

## Regra para contratação em massa

Na contratação de 10 mercenários, o desconto deve ser aplicado em cada contratação simulada individualmente.

Não aplicar desconto apenas no total final se isso gerar diferença relevante.

Fluxo esperado:

```text
1. Simular contratação 1.
2. Calcular custo base da contratação 1.
3. Aplicar desconto da Taverna.
4. Somar custo final.
5. Avançar o contador interno de contratação.
6. Repetir até 10 contratações.
```

## Interface esperada

A tela da Taverna deve mostrar:

```text
Taverna nível 35

Chance efetiva de contratação:
Comum: 76%
Incomum: 24%

Bônus atual:
+14 p.p. de chance de Aprendiz Incomum
-14% no custo de contratação

Próximo marco:
Nível 40
Comum: 74%
Incomum: 26%
Desconto: 16%
```

Na contratação, mostrar:

```text
Custo base: 6.542 ouro
Desconto da Taverna: -20%
Custo final: 5.234 ouro
```

## Critérios de aceite

- Aplicar nova progressão da Taverna até nível 50.
- Fazer Taverna nível 50 entregar 30% de chance de Incomum.
- Fazer Taverna nível 50 entregar 20% de desconto na contratação.
- Manter custo interno escalável para preservar gold sink.
- Aplicar desconto em contratação individual.
- Aplicar desconto em contratação em massa.
- Exibir custo base, desconto e custo final.
- Exibir chance efetiva, não apenas chance base.
- Exibir próximo marco de melhoria.
- Garantir que a regra seja centralizada em helper/service único.
- Garantir que backend e UX usem o mesmo helper.
- Criar testes unitários para as faixas 1, 5, 10, 25 e 50.

---

# MVP-038 — Rebalanceamento geral de construções nível 1–50

## Objetivo

Revisar todas as construções para garantir que cada uma tenha benefícios claros e úteis até o nível 50.

## Construções conhecidas

As construções atuais identificadas são:

- Alojamento.
- Campo de Treino.
- Ferreiro.
- Armazém.
- Escritório de Missões.
- Exploradores.
- Taverna.
- Mercado.
- Docas.

## Regra geral

Toda construção deve ter pelo menos:

- Um benefício principal.
- Um benefício secundário ou marco relevante.
- Descrição clara do ganho atual.
- Descrição clara do próximo ganho.
- Ganhos distribuídos ao longo de 50 níveis.

## Diretriz por construção

### Alojamento

Deve impactar:

- Limite máximo de mercenários.
- Progressão inicial mais confortável para o jogador novo.
- Possível redução leve de custo de manutenção futura, se existir.
- Possível melhoria de recuperação/descanso, se existir sistema relacionado.

Regra ajustada específica para Alojamento:

```text
Apenas o Alojamento deve ter ganho de espaço de mercenário nos 3 primeiros níveis.
Depois do nível 3, o crescimento volta a seguir os marcos gerais definidos para construções: 5, 10, 15, 20, 25, 30, 35, 40, 45 e 50.
```

Diretriz de progressão recomendada:

| Nível do Alojamento | Ganho esperado | Observação |
|---:|---|---|
| 1 | +1 espaço de mercenário | Ganho inicial obrigatório |
| 2 | +1 espaço de mercenário | Ganho inicial obrigatório |
| 3 | +1 espaço de mercenário | Ganho inicial obrigatório |
| 5 | Próximo ganho de espaço | Retoma regra por marco |
| 10 | Próximo ganho de espaço | Marco padrão |
| 15 | Próximo ganho de espaço | Marco padrão |
| 20 | Próximo ganho de espaço | Marco padrão |
| 25 | Próximo ganho de espaço | Marco padrão |
| 30 | Próximo ganho de espaço | Marco padrão |
| 35 | Próximo ganho de espaço | Marco padrão |
| 40 | Próximo ganho de espaço | Marco padrão |
| 45 | Próximo ganho de espaço | Marco padrão |
| 50 | Último ganho ou pico de capacidade | Nível máximo |

Regras de negócio:

- Esse ajuste vale somente para Alojamento.
- Nenhuma outra construção deve receber exceção nos níveis 1, 2 e 3 por causa deste item.
- O objetivo é evitar que o jogador novo fique preso por falta de espaço logo no início.
- O ganho dos níveis 1, 2 e 3 deve ser exibido claramente no card da construção.
- O próximo marco do Alojamento deve considerar a regra especial. Exemplo: se estiver no nível 2, o próximo benefício é nível 3; se estiver no nível 3, o próximo benefício é nível 5.

Regra mínima:

```text
Deve existir ganho de limite de mercenários até o nível 50.
Não pode ficar com níveis finais sem ganho.
Os níveis 1, 2 e 3 do Alojamento devem obrigatoriamente liberar espaço de mercenário.
```

### Campo de Treino

Deve impactar:

- Bônus de XP de mercenários.
- Eficiência de evolução.
- Requisitos de evolução de classe, quando aplicável.

Regra mínima:

```text
No nível 50, deve entregar o bônus máximo planejado de XP.
```

Sugestão:

```text
Nível 50 = 50% bônus de XP
```

### Ferreiro

Deve impactar:

- Chance de drop de equipamentos.
- Qualidade/crafting/refino, se aplicável.
- Receitas disponíveis.

Regra mínima:

```text
No nível 50, deve entregar o pico de benefício do Ferreiro.
```

Sugestão:

```text
Nível 50 = 25% bônus de drop/equipamento ou equivalente.
```

### Armazém

Deve impactar:

- Bônus de materiais.
- Capacidade/estoque, se existir.
- Gold passivo/offline, se aplicável.

Regra mínima:

```text
No nível 50, deve entregar o pico de bônus de materiais.
```

Sugestão:

```text
Nível 50 = 50% bônus de materiais
```

### Escritório de Missões

Deve impactar:

- Quantidade de missões disponíveis.
- Tamanho máximo de grupo.
- Qualidade/recompensa de missões.
- Desbloqueio de faixas de missão.

Problema atual:

```text
O ganho relevante acaba cedo demais.
```

Sugestão de marcos:

| Nível | Benefício sugerido |
|---:|---|
| 1 | Missões básicas desbloqueadas |
| 5 | +1 slot de missão disponível |
| 10 | Grupo maior ou nova faixa |
| 15 | Melhor rotação de missões |
| 20 | Missões intermediárias melhores |
| 25 | +1 slot de missão disponível |
| 30 | Bônus leve de recompensa |
| 35 | Missões avançadas melhores |
| 40 | Melhor chance de missão rara |
| 45 | Redução leve de tempo |
| 50 | Pico de eficiência de missões |

### Exploradores

Deve impactar:

- Desbloqueio de Dungeons.
- Qualidade de Dungeons encontradas.
- Chance de Dungeons raras.
- Eficiência de exploração.

Problema atual:

```text
O ganho relevante acaba cedo demais.
```

Sugestão de marcos:

| Nível | Benefício sugerido |
|---:|---|
| 1 | Dungeons básicas desbloqueadas |
| 5 | +chance de encontrar Dungeon melhor |
| 10 | Redução leve no tempo de exploração |
| 15 | Dungeons intermediárias |
| 20 | +chance de recompensa extra |
| 25 | Dungeons avançadas |
| 30 | Melhor chance de boss/elite |
| 35 | Melhor qualidade de loot |
| 40 | Dungeons raras |
| 45 | Bônus contra falha |
| 50 | Pico de exploração |

### Taverna

Deve seguir a regra da MVP-037.

### Mercado

Deve impactar:

- Slots de venda.
- Tempo de venda.
- Valor de venda.
- XP de guilda por venda, se aplicável.

Regra mínima:

```text
Deve haver ganho relevante até o nível 50.
```

### Docas

Deve impactar:

- Quantidade de mercantes.
- Slots de oferta.
- Qualidade dos itens ofertados.
- Chance de mercante raro.
- Redução de tempo de rotação.

Problema atual:

```text
Parte dos ganhos termina antes do nível máximo.
```

Sugestão de marcos:

| Nível | Benefício sugerido |
|---:|---|
| 1 | 1 mercante básico |
| 5 | +1 slot de oferta |
| 10 | Melhor rotação |
| 15 | Chance de material incomum |
| 20 | +1 mercante |
| 25 | Chance de material raro |
| 30 | +1 slot de oferta |
| 35 | Chance de equipamento incomum/raro |
| 40 | Chance de mercante especial |
| 45 | Redução de rotação |
| 50 | Melhor qualidade máxima de ofertas |

## Critérios de aceite

- Redefinir benefícios de todas as construções para nível máximo 50.
- Remover grandes faixas sem ganho.
- Exibir benefício atual e próximo benefício.
- Garantir que cada construção tenha papel claro no loop do jogo.
- Atualizar cálculos de custo para nova curva 1–50.
- Garantir que a progressão de guilda suporte a evolução das construções.
- Criar testes de benefício por nível/marco.
- Atualizar textos e tooltips.
- Garantir que a tela de construções mostre o valor real dos bônus.

---

# MVP-039 — Revisão da curva de custo das construções

## Objetivo

Rebalancear os custos de evolução das construções considerando o novo nível máximo 50.

## Problema

A curva atual foi analisada com nível máximo 100.

Se o nível máximo cair para 50, os custos precisam ser recalculados para manter:

- Progressão justa.
- Gold sink relevante.
- Uso de materiais.
- Sensação de evolução.
- Evitar grind excessivo cedo demais.
- Evitar baratear demais o endgame.

## Diretriz

O custo total até o nível 50 deve ser relevante, mas não deve equivaler automaticamente ao custo antigo até o nível 100.

O jogo precisa ficar mais denso, não apenas comprimido.

## Regras de balanceamento

Codex deve revisar os custos considerando:

- Gold médio obtido por faixa de nível.
- Gold médio gasto com contratação.
- Gold médio gasto com Mercado/Docas/Ferreiro.
- Materiais obtidos por missões de coleta.
- Materiais comprados nas Docas.
- Necessidade de múltiplas construções competindo pelo mesmo recurso.

## Critérios de custo

O custo deve fazer o usuário escolher onde investir.

Não pode permitir que o usuário maximize todas as construções cedo demais.

Mas também não pode impedir evolução básica por falta extrema de recurso.

## Sugestão de abordagem

Criar fórmula por construção:

```text
custo_nível = custo_base × multiplicador_construção × curva_nível
```

Onde:

```text
curva_nível pode ser linear leve até 10,
moderada de 11 a 30,
mais pesada de 31 a 50.
```

## Faixas sugeridas

| Faixa | Intenção |
|---|---|
| 1–10 | Evolução inicial acessível |
| 11–25 | Escolha de prioridade |
| 26–40 | Investimento relevante |
| 41–50 | Endgame de construção |

## Critérios de aceite

- Recalcular custos até nível 50.
- Validar custo acumulado por construção.
- Validar custo acumulado para maximizar todas as construções.
- Garantir que ouro e materiais tenham uso constante.
- Evitar que uma construção consuma recurso de forma desproporcional sem benefício.
- Criar documentação no código ou seed explicando a curva.
- Criar simulação simples para custo acumulado por nível 10, 25 e 50.
- Garantir que a UI mostre corretamente os recursos exigidos.

---

# MVP-040 — Painel/Tooltip de benefícios das construções

## Objetivo

Melhorar a clareza para o jogador sobre o que ele ganha ao evoluir cada construção.

## Problema

Hoje o jogador pode investir em construção sem entender claramente:

- O que ganhou.
- O que ganhará no próximo nível.
- Qual é o próximo marco relevante.
- Se aquela construção impacta Taverna, Missões, Dungeons, Mercado, Docas ou outros sistemas.

## Solução

Adicionar em cada card/tela de construção uma área de benefício.

## Conteúdo mínimo por construção

Cada construção deve exibir:

```text
Nível atual
Nível máximo
Benefício atual
Próximo benefício
Próximo marco relevante
Custo do próximo nível
Sistemas impactados
```

## Exemplo para Taverna

```text
Taverna — Nível 35/50

Benefícios atuais:
- Chance de Aprendiz Incomum: 24%
- Chance de Aprendiz Comum: 76%
- Desconto em contratação: 14%

Próximo marco:
Nível 40
- Chance de Aprendiz Incomum: 26%
- Desconto em contratação: 16%
```

## Exemplo para Docas

```text
Docas — Nível 25/50

Benefícios atuais:
- 2 mercantes ativos
- 5 ofertas disponíveis
- Chance de materiais raros nas ofertas

Próximo marco:
Nível 30
- +1 slot de oferta
```

## Critérios de aceite

- Exibir benefícios reais, não textos genéricos.
- Exibir próximo marco quando houver.
- Exibir “nível máximo atingido” quando a construção estiver no 50.
- Garantir que a informação venha do mesmo serviço/helper que calcula o efeito.
- Evitar divergência entre regra visual e regra backend.
- Manter layout compatível com UX/UI medieval atual.
- Garantir responsividade.
- Manter textos em Português BR.

---

# MVP-041 — QA de construções e benefícios

## Objetivo

Criar validações para impedir que construções fiquem com níveis sem ganho, regras invisíveis ou divergência entre backend e tela.

## Regras de QA

Criar testes ou scripts de diagnóstico para validar:

- Nenhuma construção ultrapassa nível 50.
- Cada construção possui benefício definido.
- Cada construção possui pelo menos um ganho relevante entre os marcos.
- O benefício exibido na tela é o mesmo calculado pelo backend.
- A Taverna nível 50 exibe e aplica 30% Incomum.
- A Taverna nível 50 exibe e aplica 20% desconto.
- Não existem referências antigas a nível 100 na UI.
- Não existem textos incorretos como “nível máximo 100”.
- Não existem regras duplicadas conflitantes.

## Critérios de aceite

- Criar teste automatizado ou script executável de diagnóstico.
- O script deve listar construções com níveis mortos.
- O script deve listar construções sem benefício no nível máximo.
- O script deve listar divergências entre helper e template, se possível.
- Corrigir todos os problemas encontrados antes de considerar a entrega finalizada.

---


# MVP-042 — Tesouro da Guilda no cabeçalho global

## Objetivo

Permitir que o jogador visualize os principais recursos da guilda em qualquer tela, sem precisar voltar para a Visão Geral.

## Problema identificado

Hoje a visão dos materiais e recursos da guilda fica concentrada na Visão Geral. Durante missões, masmorras, chefes, inventário, construções, Docas, Mercado, Ferreiro e Taverna, o jogador precisa trocar de tela para conferir se possui recursos suficientes.

Isso prejudica tomada de decisão, principalmente quando o jogador está:

- Evoluindo construções.
- Comprando materiais nas Docas.
- Criando/refinando equipamentos.
- Analisando custo de contratação.
- Validando se vale farmar madeira, minério, cristais ou outros materiais.

## Regra de negócio

Adicionar uma área fixa/compacta no label superior/header global com o resumo do Tesouro da Guilda.

O Tesouro da Guilda deve aparecer em todas as telas principais do jogo autenticado.

Conteúdo mínimo:

```text
Ouro
Madeira
Minério
Cristais
Materiais principais existentes no jogo, se houver suporte visual sem poluir a UI
```

Se o número de materiais for alto, exibir no topo apenas os recursos principais e criar um tooltip/dropdown compacto chamado `Tesouro da Guilda`.

## Diretriz de UX

A solução deve manter a identidade medieval/fantasia atual.

Sugestão visual:

```text
Tesouro da Guilda: 🪙 12.500 | Madeira 320 | Minério 180 | Cristal 24
```

Não precisa usar emoji se o sistema já tiver ícones próprios. Preferir ícones/assets atuais do jogo.

## Regras técnicas

- Criar componente/template parcial reutilizável para o header.
- Não duplicar código em cada template.
- Buscar os recursos pelo mesmo serviço usado na Visão Geral.
- Garantir atualização após ações que alteram recursos.
- Se houver cache/sessão, invalidar ou atualizar após compra, coleta, upgrade, crafting, venda e contratação.
- Em mobile/responsivo, permitir colapsar a visão em botão/tooltip.

## Critérios de aceite

- Exibir Tesouro da Guilda no topo das telas principais.
- Exibir ouro e materiais principais.
- Usar a mesma fonte de dados da Visão Geral.
- Atualizar valores após ações que consumam ou gerem recursos.
- Manter layout responsivo.
- Manter textos em Português BR.
- Não poluir telas com excesso de informação.

---

# MVP-043 — Melhorias nas telas de seleção de mercenários

## Objetivo

Melhorar a leitura dos cards de mercenários nas telas de seleção para missões, masmorras e chefes.

## Problemas identificados

Nas telas onde o jogador seleciona mercenários, o nível nem sempre aparece ao lado do nome, obrigando o jogador a sair da tela ou interpretar outras informações para saber se aquele mercenário serve para o conteúdo.

Além disso, nas missões de coleta, a profissão do mercenário precisa ficar mais visual, pois a tela já contém muita informação textual.

## Regra 1 — Exibir nível ao lado do nome

Em todas as telas de seleção de mercenários para:

- Missões.
- Missões de coleta.
- Masmorras.
- Chefes.
- Qualquer outro conteúdo que exija seleção de mercenários.

O nome deve seguir o padrão:

```text
Nome do Mercenário Nv. X
```

Exemplos:

```text
Kenshin Nv. 18
Yusuke Nv. 42
Erza Nv. 101
```

## Regra 2 — Marcador visual de profissão

Na tela de seleção de mercenários para missões de coleta, cada card de mercenário deve ter um marcador visual de profissão.

Formato sugerido:

```text
Bolinha pequena no canto inferior direito do card do mercenário.
```

Esse marcador deve usar cor associada à profissão.

O label da missão que mostra `Profissão: xxx` deve usar a mesma cor da profissão, para criar ligação visual entre requisito/afinidade da missão e mercenário.

## Diretriz de cores por profissão

O Codex deve escolher cores que combinem com o contexto medieval/fantasia e mantenham boa legibilidade.

Sugestão inicial:

| Profissão | Cor sugerida | Contexto |
|---|---|---|
| Lenhador | Verde musgo | Madeira/floresta |
| Minerador | Cinza metálico | Minérios/pedra |
| Herbalista | Verde claro | Ervas/natureza |
| Caçador | Marrom couro | Caça/rastreamento |
| Pescador | Azul água | Pesca/rios |
| Escavador | Ocre/terra | Escavação/relíquias |
| Alquimista | Roxo | Essências/cristais |
| Forrageador | Amarelo queimado | Coleta geral |

Se as profissões atuais tiverem nomes diferentes, adaptar mantendo a lógica visual.

## Regra 3 — Tela de Profissões

Na tela de Profissões, cada card/bloco de profissão deve ter a borda na cor correspondente ao marcador.

Não exagerar em preenchimento de cor. Usar preferencialmente:

```text
Borda colorida + pequeno marcador + tooltip/label
```

## Critérios de aceite

- Exibir `Nome Nv. X` em todos os cards de seleção de mercenário.
- Aplicar marcador de profissão em missões de coleta.
- Usar a mesma cor no label da profissão exigida/indicada pela missão.
- Atualizar tela de Profissões com bordas coloridas por profissão.
- Garantir boa leitura em tema medieval atual.
- Não substituir informação textual essencial apenas por cor.
- Manter acessibilidade mínima com tooltip/nome da profissão.

---

# MVP-044 — Missões longas idle por faixa de nível

## Objetivo

Criar uma opção de missão longa em cada faixa de nível para permitir que o jogador deixe mercenários ocupados durante períodos offline/idle, sem quebrar a economia.

## Justificativa

O jogador novo pode querer deixar uma missão rodando antes de sair do jogo. Jogadores mid/late game também precisam de uma opção para ocupar mercenários por longos períodos.

A missão longa deve ser útil, mas não pode ser melhor do que jogar ativamente.

## Regra de conteúdo

Criar exatamente 1 missão longa por faixa de nível.

Faixas esperadas:

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

Se o jogo usa faixas diferentes, adaptar às faixas reais existentes, mantendo 1 missão longa por faixa.

## Tema/narrativa das missões

Os nomes devem representar proteção, vigia, escolta ou patrulha nos arredores da guilda.

Exemplos:

| Faixa | Nome sugerido |
|---|---|
| 1–20 | Patrulha Noturna dos Arredores |
| 21–50 | Vigia da Estrada Velha |
| 51–100 | Ronda nos Bosques da Guilda |
| 101–130 | Guarda dos Portões Externos |
| 131–200 | Patrulha Contra Saqueadores |
| 201–250 | Vigia das Ruínas Distantes |
| 251–300 | Sentinela da Fronteira Sombria |
| 301–350 | Patrulha Final Contra Invasões |

O Codex pode criar nomes melhores, desde que mantenha esse contexto.

## Regras de negócio

Cada missão longa deve ter:

```text
Duração: 8 horas
Chance fixa de sucesso: 60%
Mercenários exigidos: 1
Nível mínimo: menor nível da faixa
Limite global simultâneo: no máximo 3 missões longas ativas ao mesmo tempo
```

Exemplo:

```text
Faixa 1–20
Nível mínimo: 1
Duração: 8h
Chance: 60%
Mercenários: 1
```

## Regra de limite simultâneo

O jogador só pode manter no máximo 3 missões longas ativas ao mesmo tempo.

Essa regra deve contar apenas missões marcadas como `long_idle` ou equivalente.

Não deve bloquear missões comuns, coleta, masmorras ou chefes.

Motivo: evitar que jogador late game com muitos mercenários envie 20 mercenários em missões longas e transforme isso na melhor fonte passiva de XP/gold.

## Fórmula de recompensa

Para cada faixa de nível, calcular o máximo aproximado de ouro e XP que o jogador consegue ganhar em 1 hora jogando ativamente naquela faixa.

Depois aplicar:

```text
recompensa_missão_longa = máximo_ativo_por_hora × 0,5 × 8
```

Ou seja:

```text
Missão longa de 8h deve pagar aproximadamente 50% da eficiência ativa por hora.
```

Exemplo conceitual:

```text
Máximo ativo 1–20 = 1.000 ouro/h e 1.000 XP/h
Recompensa longa = 1.000 × 0,5 × 8 = 4.000 ouro e 4.000 XP
```

Como a chance é 60%, o valor esperado real será:

```text
4.000 × 60% = 2.400 de valor esperado
```

Isso mantém a missão útil, mas inferior ao farm ativo.

## Loot e materiais

Missões longas podem ter loot, mas deve ser controlado.

Diretriz:

- Não dropar itens raros em excesso.
- Não substituir missões de coleta.
- Pode ter pequena chance de material comum/incomum da faixa.
- Pode ter chance baixa de item temático.
- Não deve ser a melhor fonte de progressão.

## Critérios de aceite

- Criar 1 missão longa por faixa de nível.
- Definir duração de 8 horas.
- Definir chance fixa de 60%.
- Exigir apenas 1 mercenário.
- Usar nível mínimo da faixa como requisito.
- Limitar a 3 missões longas ativas simultaneamente.
- Calcular recompensa com base em 50% do ganho ativo por hora × 8.
- Garantir que falha não entregue recompensa principal.
- Exibir claramente que é uma missão longa/idle.
- Exibir limite de 3 missões longas ativas.
- Criar testes para o limite simultâneo.

---

# MVP-045 — Filtros e correções de UX na tela de Missões

## Objetivo

Melhorar a usabilidade da tela de Missões, principalmente para coleta de materiais e filtro de faixa de nível.

## Melhoria 1 — Filtro específico para missões de coleta

Adicionar filtro para missões de coleta por material.

Materiais mínimos esperados:

```text
Madeira
Minério
Cristais
Ervas
Couro
Essências
Outros materiais existentes no jogo
```

A lista deve ser dinâmica, baseada nos materiais que existem nas missões de coleta seedadas/cadastradas.

## Comportamento esperado

O jogador deve conseguir filtrar:

```text
Todas as missões de coleta
Coleta de Madeira
Coleta de Minério
Coleta de Cristais
Coleta de Ervas
...
```

Se não houver missão para determinado material, não exibir opção vazia.

## Melhoria 2 — Corrigir select de filtro de nível

Problema observado:

```text
Ao selecionar um nível/faixa no filtro de missões, mesmo clicando fora do select, ele permanece aberto.
```

Regra:

- O select/dropdown deve fechar ao selecionar uma opção.
- O select/dropdown deve fechar ao clicar fora.
- O comportamento deve funcionar em desktop e mobile.
- Não deve prender foco visual indevidamente.

## Critérios de aceite

- Criar filtro de coleta por material.
- Exibir apenas materiais existentes em missões de coleta.
- Permitir combinar filtro de faixa de nível com filtro de material, se a tela já suportar múltiplos filtros.
- Corrigir dropdown/select de faixa de nível para fechar corretamente.
- Manter UX/UI medieval atual.
- Garantir responsividade.

---

# MVP-046 — Correção do bônus de profissão em missões de coleta

## Objetivo

Garantir que a profissão do mercenário aplique corretamente bônus de 15% nas missões de coleta compatíveis.

## Problema identificado

Aparentemente, a profissão não está gerando o bônus esperado de 15% nos materiais.

A regra esperada é que o bônus afete diretamente a chance de drop do material principal da missão.

## Regra de negócio

Se uma missão de coleta possui material principal e uma profissão associada, mercenários com a profissão correta devem receber +15 pontos percentuais na chance de drop desse material.

Exemplo:

```text
Missão: Coletar Madeira
Chance base de dropar Madeira: 85%
Mercenário com profissão Lenhador: +15 p.p.
Chance final: 100%
```

A chance final nunca deve passar de 100%.

## Regra técnica

Usar pontos percentuais, não multiplicador relativo.

Correto:

```text
85% + 15 p.p. = 100%
```

Evitar interpretação como:

```text
85% × 1,15 = 97,75%
```

A regra definida para PRD é bônus direto em pontos percentuais.

## Escopo do bônus

O bônus de profissão deve afetar:

- Material principal da missão de coleta.
- Materiais secundários apenas se a missão explicitamente indicar que a profissão também se aplica a eles.

Por padrão, aplicar somente ao material principal para não inflar loot sem controle.

## Interface

Na tela da missão, quando o mercenário selecionado tiver profissão compatível, exibir algo como:

```text
Bônus de Profissão ativo: +15 p.p. na chance de Madeira
```

Se a UI estiver poluída, usar tooltip discreto.

## Critérios de aceite

- Aplicar +15 p.p. na chance de drop do material principal quando a profissão for compatível.
- Limitar chance final a 100%.
- Não aplicar bônus em missão incompatível.
- Exibir indicação visual de bônus ativo.
- Criar testes com chance base 85% + profissão = 100%.
- Criar testes com chance base 40% + profissão = 55%.
- Criar testes garantindo que profissão errada não aplica bônus.

---

# MVP-047 — Expansão de conquistas para early, mid e late game

## Objetivo

Criar uma gama maior de conquistas para orientar e recompensar o jogador ao longo da progressão.

## Justificativa

Conquistas ajudam especialmente o jogador novo, pois funcionam como metas guiadas. No mid/late game, continuam úteis como objetivos secundários, mesmo que não sejam a principal fonte de progressão.

## Diretriz

Criar conquistas em quantidade suficiente para cobrir:

- Primeiro contato com o jogo.
- Primeiras contratações.
- Primeiras missões.
- Primeiras coletas.
- Evolução inicial de construções.
- Evolução de mercenários.
- Primeira troca de classe.
- Primeiras masmorras.
- Primeiros chefes.
- Uso de Docas, Mercado, Ferreiro e Taverna.
- Progressão até late game.

## Categorias sugeridas

| Categoria | Exemplos de conquistas |
|---|---|
| Tutorial/Primeiros passos | Contratar 1 mercenário, concluir 1 missão, coletar primeiro loot |
| Taverna | Contratar 10, 50, 100, 250 mercenários |
| Missões | Concluir 10, 50, 100, 500 missões |
| Coleta | Coletar 100 madeira, 100 minério, 100 cristais |
| Construções | Evoluir qualquer construção para 5, 10, 25, 50 |
| Classes | Evoluir para primeira classe, especialização, classe final |
| Masmorras | Concluir primeira masmorra, 10 masmorras, masmorra difícil |
| Chefes | Derrotar primeiro chefe, 10 chefes, chefe endgame |
| Economia | Acumular gold, gastar gold, vender itens, comprar nas Docas |
| Equipamentos | Dropar, equipar, refinar ou criar equipamentos |
| Profissões | Usar bônus de profissão, concluir coleta com profissão correta |

## Regras de recompensa

Conquistas early game podem dar recompensas mais úteis para reduzir atrito inicial.

Exemplos:

- Pequena quantidade de gold.
- Pequena quantidade de madeira/minério.
- Materiais comuns.
- XP de guilda moderada.

Conquistas mid/late game devem ter recompensas mais simbólicas ou proporcionais, sem quebrar economia.

## Critérios de aceite

- Criar conquistas adicionais para early game.
- Criar conquistas adicionais para mid game.
- Criar conquistas adicionais para late game.
- Garantir que conquistas ajudem o jogador novo a entender progressão.
- Não criar recompensas que quebrem economia.
- Exibir conquistas com texto em Português BR.
- Garantir que conquistas sejam idempotentes e não possam ser resgatadas múltiplas vezes indevidamente.

---

# MVP-048 — Correção de histórico de loot e tradução de atributos

## Objetivo

Corrigir textos técnicos e termos em inglês exibidos no histórico de missões, masmorras e chefes.

## Problema identificado

Na tela de histórico das missões, equipamentos dropados aparecem com textos como:

```text
RNG + xxx
STR
AGI
INT
VIT
```

O esperado para PRD é comunicação em Português BR e sem termos técnicos desnecessários.

Possivelmente o mesmo problema existe em masmorras e chefes.

## Regra de negócio

Substituir `RNG` por `Bônus` em histórico, cards e qualquer exibição de atributo gerado aleatoriamente.

Traduzir atributos para Português BR conforme padrão do jogo.

Sugestão:

| Interno | Exibição PT-BR |
|---|---|
| STR | FOR |
| AGI | AGI |
| INT | INT |
| VIT | VIT |
| LUCK | SOR |
| CRIT | Crítico |
| DEF | Defesa |
| ATK | Ataque |
| MAGIC | Magia |
| SPEED | Velocidade |

Se o jogo já tiver um dicionário oficial de atributos, usar o dicionário existente.

## Escopo

Corrigir em:

- Histórico de missões.
- Histórico de coleta.
- Histórico de masmorras.
- Histórico de chefes.
- Cards de loot.
- Tooltip de equipamento.
- Modal de resultado.
- Qualquer tela que exiba bônus de equipamento.

## Regra técnica

Criar helper único de formatação de atributo e bônus.

Exemplo conceitual:

```python
def format_equipment_bonus(attribute_key, value):
    label = translate_attribute(attribute_key)
    return f"Bônus: +{value} {label}"
```

Não formatar manualmente em cada template.

## Critérios de aceite

- Remover `RNG` da exibição para o usuário.
- Exibir `Bônus` no lugar de `RNG`.
- Traduzir atributos para Português BR.
- Corrigir histórico de missões.
- Corrigir histórico de masmorras.
- Corrigir histórico de chefes.
- Criar helper centralizado de tradução/formatação.
- Garantir acentuação correta.

---

# MVP-049 — Rework do Armazém: bônus fixo de materiais

## Objetivo

Alterar a lógica da construção Armazém para entregar bônus fixo de quantidade de materiais, substituindo o bônus percentual atual.

## Problema identificado

O Armazém comunica aumento percentual de materiais dropados, mas esse percentual não está surtindo efeito de forma clara/perceptível.

A percepção de ganho é baixa e o jogador não entende exatamente quanto recebeu a mais.

## Nova regra de produto

O Armazém deve deixar de dar bônus percentual e passar a dar quantidade fixa adicional de materiais.

No nível máximo, o Armazém deve entregar até:

```text
+20 materiais adicionais
```

## Progressão recomendada

Como o novo nível máximo de construções é 50, o ganho deve escalar por marcos.

Sugestão inicial:

| Nível do Armazém | Bônus fixo de materiais |
|---:|---:|
| 1 | +1 |
| 5 | +2 |
| 10 | +4 |
| 15 | +6 |
| 20 | +8 |
| 25 | +10 |
| 30 | +12 |
| 35 | +14 |
| 40 | +16 |
| 45 | +18 |
| 50 | +20 |

## Regra de aplicação

O bônus fixo deve ser aplicado ao material recebido quando houver sucesso no drop/coleta.

Exemplo:

```text
Missão concede 3 Madeiras.
Armazém nível 25 concede +10 materiais.
Total recebido: 13 Madeiras.
```

## Regra de controle

Para não quebrar o early game, o Codex deve avaliar se o bônus fixo deve aplicar:

- Apenas ao material principal da missão/coleta.
- Ou a cada tipo de material dropado.

Diretriz recomendada para PRD:

```text
Aplicar o bônus fixo somente ao material principal da recompensa, salvo quando o conteúdo definir explicitamente múltiplos materiais principais.
```

## Interação com bônus de profissão

A profissão altera a chance de dropar o material.

O Armazém altera a quantidade recebida após o drop acontecer.

Ordem correta:

```text
1. Calcular chance base de drop.
2. Aplicar bônus de profissão em pontos percentuais, se houver.
3. Resolver se o drop ocorreu.
4. Se ocorreu, calcular quantidade base.
5. Aplicar bônus fixo do Armazém.
6. Aplicar outros bônus de quantidade, se existirem, respeitando regra centralizada.
```

Exemplo:

```text
Chance base Madeira: 85%
Lenhador: +15 p.p.
Chance final: 100%
Quantidade base: 3
Armazém nível 25: +10
Total: 13 Madeiras
```

## Atualização de comunicação

Substituir textos como:

```text
+X% materiais
```

Por:

```text
+X materiais adicionais
```

Isso deve ser corrigido em:

- Tela de Construções.
- Tooltip do Armazém.
- Missões.
- Missões de coleta.
- Masmorras.
- Chefes.
- Histórico de loot.
- Resultado de missão.
- Qualquer tela que comunique o bônus do Armazém.

## Critérios de aceite

- Remover lógica percentual do Armazém para materiais.
- Implementar bônus fixo por marco até +20 no nível 50.
- Aplicar bônus fixo após confirmação do drop.
- Aplicar bônus preferencialmente ao material principal.
- Atualizar comunicação visual para `+X materiais adicionais`.
- Corrigir missões, masmorras e chefes para mostrar bônus fixo.
- Criar testes para Armazém níveis 1, 25 e 50.
- Garantir que profissão e Armazém funcionem juntos sem duplicidade indevida.

---

# MVP-050 — QA integrado de PRD: UX, loot, profissões e recursos

## Objetivo

Criar uma validação integrada para garantir que as melhorias novas não gerem divergência entre regra aplicada, regra exibida e histórico.

## Escopo de QA

Validar automaticamente ou por script diagnóstico:

- Tesouro da Guilda aparece nas telas principais.
- Cards de seleção exibem `Nome Nv. X`.
- Profissões possuem cor configurada.
- Missões de coleta mostram cor da profissão associada.
- Bônus de profissão soma +15 p.p. na chance do material principal.
- Missões longas existem em todas as faixas.
- Só podem existir 3 missões longas ativas ao mesmo tempo.
- Filtro de coleta por material funciona.
- Select de faixa de nível fecha corretamente.
- Histórico não exibe `RNG`.
- Atributos aparecem em Português BR.
- Armazém usa bônus fixo, não percentual.
- Armazém comunica `+X materiais adicionais`.
- Alojamento libera espaço nos níveis 1, 2 e 3.
- Alojamento volta aos marcos 5, 10, 15... após nível 3.

## Critérios de aceite

- Criar checklist de QA manual para as telas alteradas.
- Criar testes automatizados sempre que o projeto permitir.
- Não deixar regra apenas validada visualmente.
- Corrigir qualquer divergência encontrada antes de considerar a entrega pronta.
- Manter todos os textos em Português BR.

---

# Priorização recomendada

A ordem recomendada de implementação é:

```text
MVP-035 — Correção de UX da Taverna: chances efetivas de contratação
MVP-037 — Rebalanceamento da Taverna
MVP-036 — Redução do nível máximo das construções para 50
MVP-038 — Rebalanceamento geral de construções nível 1–50
MVP-039 — Revisão da curva de custo das construções
MVP-040 — Painel/Tooltip de benefícios das construções
MVP-041 — QA de construções e benefícios
MVP-042 — Tesouro da Guilda no cabeçalho global
MVP-043 — Melhorias nas telas de seleção de mercenários
MVP-044 — Missões longas idle por faixa de nível
MVP-045 — Filtros e correções de UX na tela de Missões
MVP-046 — Correção do bônus de profissão em missões de coleta
MVP-047 — Expansão de conquistas para early, mid e late game
MVP-048 — Correção de histórico de loot e tradução de atributos
MVP-049 — Rework do Armazém: bônus fixo de materiais
MVP-050 — QA integrado de PRD: UX, loot, profissões e recursos
```

Observação: a MVP-036 e MVP-038 podem ser feitas juntas, desde que o Codex garanta que a redução para 50 não seja apenas uma alteração superficial.

---

# Checklist de implementação para o Codex

Antes de finalizar, validar:

- [ ] Taverna mostra chance efetiva, não chance base.
- [ ] Taverna aplica chance efetiva na contratação real.
- [ ] Taverna aplica desconto no custo individual.
- [ ] Taverna aplica desconto na contratação em massa.
- [ ] Taverna nível 50 entrega 30% Incomum.
- [ ] Taverna nível 50 entrega 20% desconto.
- [ ] Construções não passam do nível 50.
- [ ] UI não menciona nível 100.
- [ ] Todas as construções têm ganho até o nível 50.
- [ ] Cards de construção mostram benefício atual e próximo marco.
- [ ] Custos foram recalculados para 50 níveis.
- [ ] Dados legados acima de nível 50 são tratados.
- [ ] Existe teste/script de QA para construções.
- [ ] Alojamento libera espaço nos níveis 1, 2 e 3.
- [ ] Alojamento mantém crescimento pelos marcos 5, 10, 15... depois do nível 3.
- [ ] Tesouro da Guilda aparece no cabeçalho global.
- [ ] Seleção de mercenários exibe `Nome Nv. X`.
- [ ] Profissões possuem marcadores visuais por cor.
- [ ] Tela de Profissões usa bordas com as cores correspondentes.
- [ ] Existe 1 missão longa por faixa de nível.
- [ ] Missões longas duram 8 horas, têm 60% de chance e limite simultâneo de 3.
- [ ] Missões de coleta possuem filtro por material.
- [ ] Select/dropdown de faixa de nível fecha corretamente.
- [ ] Bônus de profissão aplica +15 p.p. na chance de drop do material principal.
- [ ] Conquistas foram expandidas para early, mid e late game.
- [ ] Histórico de missões, masmorras e chefes não exibe `RNG`.
- [ ] Atributos e bônus de equipamentos aparecem em Português BR.
- [ ] Armazém usa bônus fixo de materiais, não percentual.
- [ ] Comunicação do Armazém mostra `+X materiais adicionais`.
- [ ] Textos estão em Português BR.
- [ ] Acentuação está correta.
- [ ] Visual segue a UX/UI medieval atual.

---

# Melhorias futuras a adicionar durante teste semanal

Adicionar novos achados abaixo conforme o teste do zero avançar.

## Achado 001

```text
Status: Aguardando teste
Área:
Problema:
Impacto:
Sugestão:
Prioridade:
```

## Achado 002

```text
Status: Aguardando teste
Área:
Problema:
Impacto:
Sugestão:
Prioridade:
```

## Achado 003

```text
Status: Aguardando teste
Área:
Problema:
Impacto:
Sugestão:
Prioridade:
```

---

# Observação final

Este documento não deve ser tratado como refinamento cosmético.

As melhorias aqui descritas impactam diretamente a preparação para PRD, pois resolvem problemas de:

- Progressão.
- Percepção de recompensa.
- Clareza de investimento.
- Balanceamento de gold.
- Relevância das construções.
- Confiabilidade entre regra aplicada e regra exibida.
- Clareza de recursos disponíveis em qualquer tela.
- Legibilidade na seleção de mercenários.
- Progressão idle controlada por missões longas.
- Correção de bônus de profissão e Armazém.
- Padronização de histórico, loot e atributos em Português BR.

O objetivo é que o jogador entenda claramente onde investir, por que investir, qual retorno esperar de cada construção e como progredir sem depender de tentativa e erro fora do jogo.
