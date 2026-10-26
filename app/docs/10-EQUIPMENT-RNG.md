# 10 - Equipment and RNG

## Objetivo

Definir a mecânica inicial de equipamentos, atributos aleatórios e impacto no poder dos mercenários.

Esta mecânica deve permitir que equipamentos iguais tenham variações diferentes, incentivando o jogador a repetir missões para buscar versões melhores do mesmo item.

## Conceito principal

Itens comuns de inventário podem continuar acumuláveis.

Equipamentos não devem ser tratados apenas como quantidade acumulada, porque cada equipamento pode ter atributos próprios.

Exemplo:

```text
Armadura de Couro A
base: +3 vitality, +1 armor
rng: +1 power

Armadura de Couro B
base: +3 vitality, +1 armor
rng: +1 luck
```

Mesmo sendo o mesmo template de item, são duas instâncias diferentes.

## Tipos de item

O projeto já possui `item_templates`.

A partir desta mecânica, os itens devem poder ser classificados como:

```text
material
consumable
misc
equipment
```

Itens do tipo `equipment` devem gerar instâncias únicas.

Itens do tipo `material`, `consumable` e `misc` podem continuar acumuláveis no inventário da guilda.

## Item template x item instance

### item_templates

Representa o modelo global do item.

É configurável pelo admin.

Exemplo:

```text
Armadura de Couro
tipo = equipment
slot = armor
nível mínimo = 1
base vitality = 3
base armor = 1
random bonus min = 1
random bonus max = 1
```

### guild_item_instances

Representa o item real que pertence à guilda.

Cada equipamento dropado ou criado deve gerar uma nova instância.

Exemplo:

```text
guild_id = 1
item_template_id = Armadura de Couro
bonus_vitality = 3
bonus_armor = 1
rng_bonus_attribute = power
rng_bonus_value = 1
equipped_to_mercenary_id = null
```

## Inventário acumulável x equipamentos únicos

Usar dois conceitos:

### Itens acumuláveis

Continuam em tabela agregada, como:

```text
guild_inventory_items
```

Usado para materiais, consumíveis e misc.

Exemplo:

```text
Pele de Lobo x10
```

### Equipamentos únicos

Devem ficar em tabela própria, como:

```text
guild_item_instances
```

Usado para equipamentos.

Exemplo:

```text
Espada Enferrujada +1 power
Espada Enferrujada +1 agility
Espada Enferrujada +1 luck
```

## Slots de equipamento

Slots iniciais:

```text
weapon
armor
accessory
```

Cada mercenário pode ter apenas um equipamento por slot.

Exemplo:

```text
1 weapon
1 armor
1 accessory
```

## Nível mínimo

Todo equipamento deve poder ter nível mínimo.

Campo sugerido no template:

```text
required_level
```

Regra:

```text
mercenary.level >= item.required_level
```

Se o mercenário não tiver nível suficiente, o sistema deve impedir equipar.

Mensagem sugerida:

```text
Mercenário não possui nível suficiente para equipar este item.
```

## Atributos de equipamento

Atributos iniciais recomendados:

```text
bonus_power
bonus_vitality
bonus_agility
bonus_intelligence
bonus_luck
bonus_armor
```

Observação:

`bonus_armor` pode existir desde já como atributo de equipamento, mesmo que ainda não exista combate avançado. No MVP, ele pode contribuir no cálculo de poder total com peso simples.

## RNG de equipamento

Todo equipamento gerado para a guilda deve poder receber bônus aleatório.

O RNG deve ocorrer no momento em que a instância do item é criada.

Não sortear RNG toda vez que renderizar tela.

Não recalcular RNG ao equipar.

Não recalcular RNG ao desequipar.

Atributos possíveis para RNG inicial:

```text
power
vitality
agility
intelligence
luck
armor
```

Campos sugeridos no template:

```text
rng_bonus_min
rng_bonus_max
```

Campos sugeridos na instância:

```text
rng_bonus_attribute
rng_bonus_value
```

Exemplo:

```text
template:
Armadura de Couro
bonus_vitality = 3
bonus_armor = 1
rng_bonus_min = 1
rng_bonus_max = 1

instância gerada:
rng_bonus_attribute = luck
rng_bonus_value = 1
```

Resultado final:

```text
+3 vitality
+1 armor
+1 luck
```

## Escala futura do RNG

No futuro, o RNG pode escalar por:

```text
nível do item
raridade
dungeon
boss
tier
qualidade
```

No MVP, manter simples:

```text
rng_bonus_value = número aleatório entre rng_bonus_min e rng_bonus_max
```

## Equipar item

Regra:

* usuário precisa estar autenticado;
* usuário precisa ter guilda;
* mercenário precisa pertencer à guilda do usuário;
* item instance precisa pertencer à guilda do usuário;
* item precisa ser do tipo `equipment`;
* mercenário precisa atender o `required_level`;
* mercenário só pode ter um item por slot;
* se já houver item no mesmo slot, bloquear ou substituir de forma controlada.

Para o MVP, preferir bloquear:

```text
Este slot já possui um equipamento. Desequipe o item atual antes de equipar outro.
```

## Desequipar item

Regra:

* usuário precisa estar autenticado;
* item precisa estar equipado em mercenário da própria guilda;
* ao desequipar, limpar `equipped_to_mercenary_id`;
* item volta a ficar disponível no inventário de equipamentos.

## Poder total do mercenário

Separar:

```text
atributos base do mercenário
bônus de equipamentos
atributos totais
```

Exemplo:

```text
power base = 10
bonus power = 3
power total = 13
```

A tela de mercenário deve mostrar, sempre que possível:

```text
base
bônus
total
```

## Total power

Criar um cálculo simples para poder total.

Sugestão:

```text
total_power =
power_total
+ floor(vitality_total / 2)
+ floor(agility_total / 2)
+ floor(intelligence_total / 2)
+ floor(luck_total / 3)
+ floor(armor_total / 2)
```

O cálculo pode ser ajustado no futuro.

O objetivo do MVP é permitir que equipamento impacte a força geral do mercenário.

## Chance de sucesso em missão

A chance de sucesso deve considerar o poder total do mercenário.

Regra sugerida:

```text
success_chance = mission_template.base_success_chance + floor(total_power / 10)
```

Aplicar limite:

```text
mínimo 5
máximo 95
```

A fórmula anterior baseada apenas em `mercenary.power` deve ser substituída por cálculo baseado no poder total.

## Exibição da chance na tela

Ao selecionar um mercenário para missão, a tela deve deixar claro o impacto do mercenário/equipamentos na chance.

Exemplo:

```text
Chance base da missão: 70%
Bônus do mercenário/equipamentos: +5%
Chance final estimada: 75%
```

Se for mais simples no MVP, pode exibir essa informação ao lado de cada mercenário no select/listagem:

```text
Guerra - Chance estimada: 75% (+5%)
```

O backend continua sendo a fonte de verdade para o cálculo final.

## Admin

Configurações de equipamentos devem seguir o padrão admin parametrizável.

O admin deve conseguir configurar em `item_templates`:

```text
item_type
equipment_slot
required_level
bonus_power
bonus_vitality
bonus_agility
bonus_intelligence
bonus_luck
bonus_armor
rng_bonus_min
rng_bonus_max
is_active
```

Validações:

```text
equipment_slot obrigatório quando item_type = equipment
required_level >= 1 para equipment
bônus não podem ser negativos no MVP
rng_bonus_min >= 0
rng_bonus_max >= rng_bonus_min
```

## Fora do escopo

Não implementar ainda:

```text
refino
upgrade de equipamento
durabilidade
set bonus
pedras/gemas
encantamento manual
crafting
loja
trade entre jogadores
comparador avançado
dano/defesa de combate real
```

## Critério de aceite

A mecânica estará correta quando:

```text
equipamentos forem instâncias únicas
itens acumuláveis continuarem acumuláveis
equipamento tiver nível mínimo
equipamento tiver bônus base
equipamento tiver bônus RNG gerado uma única vez
mercenário puder equipar e desequipar
slot impedir duplicidade
atributos totais considerarem equipamentos
chance de missão considerar poder total
tela mostrar impacto na chance de missão
admin conseguir parametrizar equipamentos
dados respeitarem guild_id
```
