# 08-BALANCE-RULES.md

## Objetivo

Definir as regras iniciais de balanceamento do jogo.

Este documento deve orientar fórmulas de XP, level up, atributos, recompensas, drops e progressão básica.

As regras aqui devem começar simples e evoluir conforme o jogo crescer.

## Princípio principal

O balanceamento deve ser configurável sempre que fizer sentido.

Evitar valores hardcoded espalhados no código.

Valores como duração de missão, recompensa, XP, chance de sucesso e chance de drop devem ser armazenados em banco quando forem configuráveis pelo admin.

## Progressão dos mercenários

Mercenários possuem:

```text
level
xp
power
vitality
agility
intelligence
luck
```

No MVP inicial, o level up deve ser automático ao receber XP.

## Fórmula de XP

Usar fórmula simples:

```text
xp_required = level atual * 100
```

Exemplos:

```text
Level 1 -> precisa de 100 XP para ir ao level 2
Level 2 -> precisa de 200 XP para ir ao level 3
Level 3 -> precisa de 300 XP para ir ao level 4
```

Ao receber XP, se o mercenário ultrapassar o necessário, ele deve subir de nível.

Se houver XP suficiente para múltiplos níveis, pode subir múltiplos níveis no mesmo recebimento.

Exemplo:

```text
Mercenário level 1 com 90 XP recebe 250 XP.
Total = 340 XP.

Sobe para level 2 consumindo 100 XP.
Restam 240 XP.
Para level 3 precisa de 200 XP.
Sobe para level 3.
Restam 40 XP.
```

## Aumento de atributos por level up

No MVP, ao subir 1 nível, aplicar:

```text
+1 power
+1 vitality
+1 atributo principal da classe
```

Atributo principal por classe:

```text
Guerreiro -> power
Arqueiro -> agility
Ladino -> luck
Mago -> intelligence
Clérigo -> intelligence
```

Exemplo:

Guerreiro sobe 1 nível:

```text
power +2
vitality +1
```

Mago sobe 1 nível:

```text
power +1
vitality +1
intelligence +1
```

## Limite de level

Para o MVP, não precisa implementar limite máximo.

Se for necessário criar um limite temporário, usar:

```text
max_level = 100
```

Mas não bloquear a implementação se o limite ainda não existir.

## Missões

Missões são conteúdo básico.

Recompensam:

```text
ouro
XP
chance de item básico
```

Missões não devem entregar itens raros, equipamentos avançados ou recompensas de alto valor no MVP.

## Sucesso da missão

Regra atual recomendada:

```text
success_chance = mission_template.base_success_chance + floor(mercenary.power / 5)
```

Aplicar limites:

```text
mínimo = 5
máximo = 95
```

Exemplo:

```text
base_success_chance = 80
mercenary.power = 8
bonus = floor(8 / 5) = 1
success_chance = 81
```

## Recompensa de ouro

Se sucesso:

```text
gold_reward = mission_template.base_gold_reward
```

Se falha:

```text
gold_reward = 0
```

## Recompensa de XP

Se sucesso:

```text
xp_reward = mission_template.base_xp_reward
```

Se falha:

```text
xp_reward = floor(mission_template.base_xp_reward * 0.25)
```

Falha ainda dá XP reduzido, porque o mercenário aprendeu com a tentativa.

## Itens básicos

Itens básicos são recompensas simples e acumuláveis no inventário da guilda.

Itens básicos não são equipamentos.

Itens básicos podem representar materiais, troféus, recursos simples ou ingredientes.

Exemplos:

```text
Pele de Lobo
Garra de Lobo
Erva Medicinal
Fragmento de Minério
Madeira Rústica
```

## Drops de itens

Drops devem ser configuráveis por missão.

Uma missão pode ter zero, um ou vários possíveis drops.

Exemplo:

```text
Missão: Caçar lobos

Drop possível:
- Pele de Lobo, 50%
- Garra de Lobo, 20%
```

No MVP, cada item de drop pode ter:

```text
drop_chance
min_quantity
max_quantity
```

Exemplo:

```text
Pele de Lobo
drop_chance = 50
min_quantity = 1
max_quantity = 2
```

Se o drop for sorteado, o sistema gera uma quantidade entre `min_quantity` e `max_quantity`.

## Drop apenas em sucesso

No MVP, itens devem dropar apenas em caso de sucesso da missão.

Falhas dão apenas XP reduzido.

## Inventário

O inventário pertence à guilda.

Itens iguais devem acumular quantidade.

Exemplo:

```text
guild_id = 1
item_template_id = 3
quantity = 10
```

Se a guilda ganhar mais 2 unidades do mesmo item, atualizar para:

```text
quantity = 12
```

Não criar múltiplas linhas duplicadas para o mesmo item da mesma guilda.

## Resultado da missão

Ao receber loot, o resultado deve mostrar:

```text
sucesso ou falha
ouro ganho
XP ganho
level ups ocorridos
itens obtidos
```

Se não ganhar item, mostrar mensagem simples:

```text
Nenhum item encontrado.
```

## Balanceamento via admin

Valores configuráveis devem ser alteráveis pelo admin quando fizer sentido.

Exemplos:

```text
duration_seconds
base_gold_reward
base_xp_reward
base_success_chance
drop_chance
min_quantity
max_quantity
is_active
```

Não deixar esses valores fixos apenas no código quando já existirem tabelas para eles.

## Fora do escopo de balanceamento atual

Não implementar ainda:

```text
equipamentos
raridade avançada
dano
defesa
HP
cura
lesão
morte permanente
sinergia de grupo
dungeons
bosses
crafting
economia avançada
mercado entre jogadores
```

---
