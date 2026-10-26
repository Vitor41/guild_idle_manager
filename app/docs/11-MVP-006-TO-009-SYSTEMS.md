# 11 - MVP 006 to 009 Systems

## Objetivo

Consolidar as próximas evoluções estruturais do Guild Idle Manager em um único documento técnico.

Este documento cobre os sistemas dos MVPs 006 a 009:

* MVP-006: Guild Buildings and Upgrades
* MVP-007: Advanced Missions and Party Size
* MVP-008: Dungeons Foundation
* MVP-009: Equipment Tiers and Item Rarity

O objetivo é evoluir o jogo de um loop básico de missão para um loop mais completo de progressão, decisão estratégica, uso de recursos e conteúdo de maior valor.

## Estado atual do jogo

O jogo já possui:

* autenticação;
* sessão;
* usuário;
* guilda;
* recursos;
* mercenários;
* recrutamento;
* level up;
* missões;
* timer;
* loot manual;
* itens globais;
* inventário;
* drops;
* equipamentos únicos;
* RNG em equipamentos;
* nível mínimo para equipar;
* poder total do mercenário;
* chance de missão baseada em poder total;
* admin parametrizável.

## Direção geral

A partir deste ponto, o jogo deve evoluir em quatro pilares:

1. Usar recursos para melhorar a guilda.
2. Fazer missões aceitarem grupos de mercenários.
3. Criar dungeons como conteúdo mais valioso que missões.
4. Melhorar tiers, raridades e RNG dos equipamentos.

## MVP-006 - Guild Buildings and Upgrades

### Objetivo

Criar construções da guilda para transformar recursos em progressão permanente.

Construções devem dar uso para ouro, madeira, minério, cristais e materiais.

### Conceito

Cada guilda pode evoluir construções próprias.

Templates de construções são globais.

Progressão das construções pertence à guilda.

Fluxo:

```text
building_templates -> global
guild_buildings -> por guilda
```

### Construções iniciais

Criar as construções iniciais:

```text
Alojamento
Campo de Treino
Ferreiro
Armazém
Escritório de Contratos
Exploradores
```

### Efeitos iniciais

#### Alojamento

Aumenta limite de mercenários da guilda.

Exemplo:

```text
level 1: limite 5 mercenários
level 2: limite 7 mercenários
level 3: limite 10 mercenários
```

#### Campo de Treino

Aumenta XP ganho em missões.

Exemplo:

```text
+5% XP por nível
```

#### Ferreiro

Aumenta chance de drop de equipamento ou melhora chance de encontrar equipamento.

Exemplo:

```text
+2% chance de drop de equipamento por nível
```

#### Armazém

Bônus futuro de capacidade/recursos.

No MVP, pode aumentar recompensa de materiais.

Exemplo:

```text
+5% quantidade de materiais por nível
```

#### Escritório de Contratos

Libera missões com maior tamanho de grupo ou maior recompensa.

No MVP, pode liberar missões com party size maior.

#### Exploradores

Libera dungeons ou melhora acesso a dungeons.

No MVP, pode ser requisito para ver/entrar em dungeons.

### Tabela building_templates

Tabela global.

Campos sugeridos:

```text
id
name
description
effect_type
base_upgrade_gold_cost
base_upgrade_wood_cost
base_upgrade_ore_cost
base_upgrade_crystals_cost
max_level
is_active
created_at
updated_at
```

### Tabela guild_buildings

Tabela por guilda.

Campos sugeridos:

```text
id
guild_id
building_template_id
level
created_at
updated_at
```

Regras:

* toda guilda deve possuir registros iniciais das construções ativas;
* se a construção não existir para a guilda, criar ao acessar a tela de construções;
* `level` inicial = 1;
* upgrade consome recursos;
* upgrade não pode passar de `max_level`;
* upgrade deve validar recursos da guilda.

### Custo de upgrade

Fórmula simples:

```text
cost = base_cost * current_level
```

Exemplo:

```text
base gold = 100
level atual = 2
custo para level 3 = 200
```

### Admin de construções

O admin deve conseguir editar:

```text
name
description
effect_type
base_upgrade_gold_cost
base_upgrade_wood_cost
base_upgrade_ore_cost
base_upgrade_crystals_cost
max_level
is_active
```

Seeds não devem sobrescrever alterações do admin.

## MVP-007 - Advanced Missions and Party Size

### Objetivo

Evoluir missões para aceitar mais de um mercenário e criar requisitos mais estratégicos.

### Alterações em mission_templates

Adicionar ou garantir campos:

```text
min_party_size
max_party_size
required_guild_level
required_min_mercenary_level
required_building_type
required_building_level
```

Campos podem ser opcionais quando não houver requisito.

### Party size

Missões devem permitir enviar múltiplos mercenários.

Regras:

* usuário seleciona de 1 até `max_party_size` mercenários;
* precisa respeitar `min_party_size`;
* todos os mercenários precisam pertencer à guilda;
* todos precisam estar `available`;
* todos ficam `busy` ao iniciar;
* todos voltam para `available` ao receber loot;
* XP deve ser aplicado aos mercenários participantes.

### Poder total do grupo

Missões com grupo devem calcular poder do grupo.

Regra recomendada:

```text
party_power_score = soma do mercenary_total_power_score dos participantes
bonus_chance = floor(party_power_score / 20)
final_success_chance = base_success_chance + bonus_chance
```

Aplicar limite:

```text
mínimo = 5
máximo = 95
```

### Exibição em tela

Ao selecionar mercenários, a tela deve exibir ou atualizar:

```text
chance base
bônus estimado do grupo
chance final estimada
```

Se for mais simples, exibir uma estimativa por mercenário e cálculo final no backend.

O backend sempre é fonte de verdade.

### Recompensa em grupo

No MVP:

* ouro vai para a guilda uma única vez;
* drops vão para a guilda;
* XP vai para todos os mercenários participantes.

Exemplo:

```text
mission_template.base_xp_reward = 30
3 mercenários participaram
cada mercenário recebe 30 XP em caso de sucesso
```

Em caso de falha:

```text
cada mercenário recebe floor(base_xp_reward * 0.25)
```

### Admin de missões avançadas

O admin deve conseguir editar:

```text
min_party_size
max_party_size
required_guild_level
required_min_mercenary_level
required_building_type
required_building_level
```

## MVP-008 - Dungeons Foundation

### Objetivo

Criar dungeons como conteúdo mais valioso que missões.

Missões são conteúdo básico.

Dungeons são conteúdo de maior duração, maior risco e melhores recompensas.

### Diferença entre missões e dungeons

#### Missões

```text
farm básico
duração menor
risco baixo/médio
ouro básico
XP básico
materiais
equipamentos comuns
```

#### Dungeons

```text
conteúdo mais difícil
duração maior
risco maior
maior recompensa
melhores equipamentos
melhores chances de raridade
exigem grupo
podem exigir nível/construção
```

### Tabela dungeon_templates

Tabela global.

Campos sugeridos:

```text
id
name
description
duration_seconds
base_gold_reward
base_xp_reward
base_success_chance
min_party_size
max_party_size
required_guild_level
required_min_mercenary_level
required_building_type
required_building_level
is_active
created_at
updated_at
```

### Tabela dungeon_runs

Tabela por guilda.

Campos sugeridos:

```text
id
guild_id
dungeon_template_id
status
started_at
ends_at
resolved_at
success
gold_reward
xp_reward
created_at
updated_at
```

Status:

```text
in_progress
completed
failed
```

### Tabela dungeon_run_members

Campos sugeridos:

```text
id
dungeon_run_id
mercenary_id
created_at
```

### Tela de dungeons

Criar rota:

```text
GET /dungeons
```

Deve exibir:

* dungeons disponíveis;
* requisitos;
* duração;
* recompensa;
* chance base;
* seleção de mercenários;
* dungeons em andamento;
* dungeons prontas para receber loot;
* histórico simples, se for produtivo.

### Iniciar dungeon

Rota sugerida:

```text
POST /dungeons/start
```

Regras:

* usuário autenticado;
* guilda obrigatória;
* dungeon ativa;
* requisitos atendidos;
* party size válida;
* mercenários disponíveis;
* mercenários pertencem à guilda;
* mercenários ficam busy;
* cria dungeon_run e dungeon_run_members.

### Receber loot de dungeon

Rota sugerida:

```text
POST /dungeons/{dungeon_run_id}/claim
```

Regras:

* validar guild_id;
* validar `now >= ends_at`;
* calcular sucesso/falha;
* liberar mercenários;
* aplicar ouro;
* aplicar XP;
* processar drops específicos de dungeon.

### Drops de dungeon

Criar tabela global/configurável:

```text
dungeon_template_item_drops
```

Campos:

```text
id
dungeon_template_id
item_template_id
drop_chance
min_quantity
max_quantity
is_active
created_at
updated_at
```

Dungeons podem dropar materiais e equipamentos.

Dungeons devem ter chance maior de equipamentos e raridades melhores que missões.

### Seeds iniciais de dungeon

Criar pelo menos uma dungeon inicial:

```text
Covil dos Lobos
description = Uma toca ocupada por lobos alfa e criaturas agressivas.
duration_seconds = 1800
base_gold_reward = 150
base_xp_reward = 80
base_success_chance = 60
min_party_size = 2
max_party_size = 3
required_guild_level = 1
required_min_mercenary_level = 2
is_active = true
```

### Admin de dungeons

O admin deve conseguir criar/editar:

```text
name
description
duration_seconds
base_gold_reward
base_xp_reward
base_success_chance
min_party_size
max_party_size
required_guild_level
required_min_mercenary_level
required_building_type
required_building_level
is_active
```

Admin também deve conseguir criar/editar drops de dungeon.

## MVP-009 - Equipment Tiers and Item Rarity

### Objetivo

Melhorar a itemização com tiers, raridade e RNG mais escalável.

### Campos em item_templates

Adicionar ou garantir campos:

```text
item_level
tier
rarity
```

Raridades:

```text
common
uncommon
rare
epic
legendary
```

Tiers:

```text
1
2
3
4
5
```

### Impacto da raridade no RNG

A raridade deve influenciar o RNG do equipamento.

Regra inicial:

```text
common: rng_bonus_min 1, rng_bonus_max 1
uncommon: rng_bonus_min 1, rng_bonus_max 2
rare: rng_bonus_min 2, rng_bonus_max 4
epic: rng_bonus_min 4, rng_bonus_max 6
legendary: rng_bonus_min 6, rng_bonus_max 10
```

Se o template já tiver RNG configurado manualmente pelo admin, respeitar o template.

Não sobrescrever valores admin por seed.

### Impacto do tier

Tier deve representar patamar do item.

Regras iniciais:

* item tier maior deve ter `required_level` maior;
* item tier maior pode ter bônus base maior;
* dungeons devem dropar tiers melhores que missões.

Exemplo:

```text
Tier 1: required_level 1
Tier 2: required_level 5
Tier 3: required_level 10
Tier 4: required_level 20
Tier 5: required_level 35
```

### Exibição

Inventário e mercenário devem exibir:

```text
raridade
tier
nível mínimo
bônus base
bônus RNG
```

### Admin de raridade/tier

O admin deve conseguir editar:

```text
item_level
tier
rarity
required_level
rng_bonus_min
rng_bonus_max
bônus base
```

## Multi-tenancy obrigatório

Tudo que for progresso do jogador precisa respeitar guild_id.

Dados globais:

```text
building_templates
mission_templates
dungeon_templates
item_templates
mission_template_item_drops
dungeon_template_item_drops
```

Dados por guilda:

```text
guild_buildings
mission_runs
dungeon_runs
mercenaries
guild_inventory_items
guild_item_instances
```

Nunca aceitar `guild_id` vindo do frontend.

## Seeds

Seeds devem ser idempotentes.

Regras:

* criar apenas se não existir;
* não duplicar;
* não sobrescrever alterações feitas pelo admin;
* não quebrar startup se algum registro relacionado ainda não existir.

## Admin parametrizável

Todos os conteúdos globais novos devem ter tela admin ou reaproveitar admin existente:

```text
construções
missões avançadas
dungeons
drops de dungeon
itens/tiers/raridades
```

## Fora do escopo

Não implementar ainda:

```text
mudança de classe
taberna
missões de classe
árvore de talentos
skills ativas
combate visual
crafting
refino
loja
trade entre jogadores
monetização
UX final
```

Mudança de classe, taberna e missão para mudar de classe serão refinadas depois no MVP-010.

UX final será tratada no MVP-011.
