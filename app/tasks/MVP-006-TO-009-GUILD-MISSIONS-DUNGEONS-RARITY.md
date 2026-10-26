# MVP-006 to MVP-009 - Guild Upgrades, Advanced Missions, Dungeons and Rarity

## Contexto

O MVP-000 ao MVP-005 já foram validados.

O jogo possui:

* autenticação;
* guilda;
* recursos;
* mercenários;
* level up;
* missões;
* timer;
* loot manual;
* itens;
* inventário;
* equipamentos únicos;
* RNG de equipamento;
* nível mínimo para equipar;
* poder total;
* chance de missão baseada em poder total;
* admin parametrizável.

Agora o projeto deve avançar em uma entrega maior, consolidando os MVPs 006 a 009.

## Objetivo

Implementar em uma única entrega:

* construções e upgrades da guilda;
* missões avançadas com party size;
* dungeons como conteúdo de maior valor;
* tiers, raridades e melhorias na itemização;
* admin parametrizável para os novos conteúdos.

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/03-MULTI-TENANCY.md`
* `docs/04-GAME-LOOP.md`
* `docs/05-DATABASE-MODEL.md`
* `docs/08-BALANCE-RULES.md`
* `docs/09-ADMIN-CONFIGURATION.md`
* `docs/10-EQUIPMENT-RNG.md`
* `docs/11-MVP-006-TO-009-SYSTEMS.md`
* `tasks/MVP-006-TO-009-GUILD-MISSIONS-DUNGEONS-RARITY.md`

Consultar o código atual para manter padrões já implementados.

## Escopo macro

Implementar:

```text
MVP-006: Guild Buildings and Upgrades
MVP-007: Advanced Missions and Party Size
MVP-008: Dungeons Foundation
MVP-009: Equipment Tiers and Item Rarity
```

## MVP-006 - Guild Buildings and Upgrades

### Implementar

* tabela global `building_templates`;
* tabela por guilda `guild_buildings`;
* seed inicial de construções;
* tela `/buildings`;
* upgrade de construção;
* custo de upgrade consumindo recursos;
* efeitos básicos de construção;
* dashboard com resumo de construções;
* admin de construções.

### Construções iniciais

Criar:

```text
Alojamento
Campo de Treino
Ferreiro
Armazém
Escritório de Contratos
Exploradores
```

### Efeitos mínimos obrigatórios

Implementar pelo menos estes efeitos funcionais:

#### Alojamento

Aumenta limite de mercenários.

Regra:

```text
mercenary_limit = 5 + ((alojamento_level - 1) * 2)
```

O recrutamento deve respeitar esse limite.

#### Campo de Treino

Aumenta XP ganho.

Regra:

```text
xp_bonus_percent = (campo_treino_level - 1) * 5
```

Aplicar em missões e dungeons.

#### Ferreiro

Aumenta chance de drop de equipamentos.

Regra:

```text
equipment_drop_bonus_percent = (ferreiro_level - 1) * 2
```

Aplicar apenas em drops cujo item seja equipamento.

#### Armazém

Aumenta quantidade de materiais dropados.

Regra:

```text
material_quantity_bonus_percent = (armazem_level - 1) * 5
```

Se gerar decimal, arredondar para baixo, mínimo mantendo quantidade original.

#### Escritório de Contratos

Pode liberar missões com party size maior.

Regra simples:

```text
max_allowed_mission_party_size = 1 + escritorio_contratos_level
```

#### Exploradores

Pode liberar dungeons.

Regra simples:

```text
dungeons_available = exploradores_level >= 1
```

### Upgrade

Rota sugerida:

```text
POST /buildings/{guild_building_id}/upgrade
```

Regras:

* usuário autenticado;
* building pertence à guilda do usuário;
* validar recursos;
* consumir recursos;
* aumentar level;
* não passar de max_level;
* não aceitar guild_id do frontend.

## MVP-007 - Advanced Missions and Party Size

### Implementar

* missão com múltiplos mercenários;
* campos avançados em mission_templates;
* seleção de party;
* cálculo de chance por poder total do grupo;
* XP aplicado a todos os participantes;
* status busy para todos;
* liberação de todos ao receber loot;
* admin para campos avançados de missão.

### Campos em mission_templates

Adicionar:

```text
min_party_size
max_party_size
required_guild_level
required_min_mercenary_level
required_building_type
required_building_level
```

### Regras

* respeitar min_party_size e max_party_size;
* respeitar limite do Escritório de Contratos;
* validar nível mínimo dos mercenários;
* validar requisitos de guilda/construção;
* todos os mercenários precisam estar available;
* todos precisam pertencer à guilda.

### Chance de sucesso por grupo

Regra:

```text
party_power_score = soma do mercenary_total_power_score
bonus_chance = floor(party_power_score / 20)
final_success_chance = base_success_chance + bonus_chance
```

Limites:

```text
min 5
max 95
```

### Recompensa

* ouro uma vez para guilda;
* drops uma vez para guilda;
* XP para todos os participantes;
* XP recebe bônus do Campo de Treino.

## MVP-008 - Dungeons Foundation

### Implementar

* tabela `dungeon_templates`;
* tabela `dungeon_runs`;
* tabela `dungeon_run_members`;
* tabela `dungeon_template_item_drops`;
* tela `/dungeons`;
* iniciar dungeon;
* timer;
* receber loot manual;
* cálculo de sucesso/falha;
* drops de dungeon;
* admin de dungeons;
* admin de drops de dungeon;
* dashboard com resumo de dungeons.

### Dungeon inicial

Criar seed:

```text
Covil dos Lobos
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

### Regras de dungeon

* dungeons exigem grupo;
* dungeons usam poder total do grupo;
* dungeons podem dropar materiais e equipamentos;
* dungeons têm chance maior de equipamentos;
* dungeons dão mais XP e ouro que missões;
* dungeons usam timer e loot manual igual missões;
* backend valida `now >= ends_at`.

### Cálculo de chance

Usar mesma lógica das missões avançadas:

```text
party_power_score = soma do mercenary_total_power_score
bonus_chance = floor(party_power_score / 20)
final_success_chance = base_success_chance + bonus_chance
```

### Recompensa

* sucesso: ouro, XP, drops;
* falha: XP reduzido;
* XP aplica bônus do Campo de Treino;
* drops de equipamento aplicam bônus do Ferreiro;
* materiais aplicam bônus do Armazém.

## MVP-009 - Equipment Tiers and Item Rarity

### Implementar

* campos `item_level` e `tier` em `item_templates`, se ainda não existirem;
* uso mais claro de `rarity`;
* exibição de tier e raridade no inventário/equipamentos;
* admin editando tier, item_level, rarity e ranges de RNG;
* seed de equipamentos tier/raridade inicial;
* dungeons dropando equipamentos melhores que missões.

### Regras de tier

```text
Tier 1: required_level 1
Tier 2: required_level 5
Tier 3: required_level 10
Tier 4: required_level 20
Tier 5: required_level 35
```

### Regra de RNG por raridade

Usar como referência, sem sobrescrever admin:

```text
common: 1 a 1
uncommon: 1 a 2
rare: 2 a 4
epic: 4 a 6
legendary: 6 a 10
```

### Seeds sugeridas

Criar alguns equipamentos melhores para dungeon:

```text
Espada de Ferro
tier = 2
rarity = uncommon
required_level = 5
slot = weapon

Armadura Reforçada
tier = 2
rarity = uncommon
required_level = 5
slot = armor

Amuleto do Caçador
tier = 2
rarity = uncommon
required_level = 5
slot = accessory
```

Esses equipamentos devem ser mais fortes que os equipamentos comuns.

## Admin obrigatório

Criar ou atualizar admin para:

```text
construções
missões avançadas
dungeons
drops de dungeon
itens/equipamentos/tier/raridade
```

Admin deve ser protegido por `is_admin`.

Usuário comum não acessa admin.

## Menu/Header

Adicionar links conforme aplicável:

```text
Dashboard
Mercenários
Missões
Dungeons
Construções
Inventário
Admin
Logout
```

Admin só aparece para usuário admin.

## Dashboard

Atualizar dashboard com resumo de:

```text
construções
limite de mercenários
missões em andamento/prontas
dungeons em andamento/prontas
mercenário de maior nível
total de itens
equipamentos obtidos
```

## Multi-tenancy obrigatório

Nunca aceitar `guild_id` do frontend.

Validar guild_id em:

```text
guild_buildings
mission_runs
dungeon_runs
mercenaries
guild_inventory_items
guild_item_instances
```

Dados globais não têm guild_id.

## Seeds

Seeds devem:

* ser idempotentes;
* não duplicar;
* não sobrescrever alterações admin;
* não quebrar se dependências não existirem.

## Migration

Criar migrations Alembic para todas as tabelas/campos necessários:

```text
building_templates
guild_buildings
campos avançados em mission_templates
dungeon_templates
dungeon_runs
dungeon_run_members
dungeon_template_item_drops
item_templates.item_level
item_templates.tier
ajustes necessários em item_templates
```

Aplicar com:

```bash
alembic upgrade head
```

## Fora do escopo

Não implementar agora:

```text
taberna
mudança de classe
missão para mudar de classe
árvore de talentos
skills
crafting
refino
loja
trade
monetização
UX final
```

Taberna, classes e mudança de classe serão MVP-010.

UX final será MVP-011.

## Como testar manualmente

Após implementar:

1. Rodar migrations.
2. Logar com usuário admin.
3. Validar admin de construções.
4. Validar admin de missões com party size.
5. Validar admin de dungeons.
6. Validar admin de drops de dungeon.
7. Validar admin de itens com tier/raridade.
8. Logar com usuário comum.
9. Validar tela de construções.
10. Fazer upgrade de construção.
11. Confirmar consumo de recursos.
12. Confirmar limite de mercenários pelo Alojamento.
13. Confirmar missão com múltiplos mercenários.
14. Confirmar chance calculada por poder do grupo.
15. Confirmar XP para todos os participantes.
16. Confirmar dungeons disponíveis.
17. Iniciar dungeon com grupo.
18. Aguardar timer ou ajustar duração via admin para teste.
19. Receber loot da dungeon.
20. Confirmar drops e XP.
21. Confirmar tier/raridade dos equipamentos.
22. Confirmar inventário/equipamentos.
23. Logar com outro usuário e validar isolamento de dados.

## Critérios de conclusão

Considerar concluído quando:

* construções existirem;
* guilda conseguir evoluir construções;
* upgrades consumirem recursos;
* Alojamento limitar mercenários;
* Campo de Treino aumentar XP;
* Ferreiro aumentar chance de equipamento;
* Armazém aumentar quantidade de materiais;
* Escritório de Contratos limitar/liberar party size;
* missões aceitarem múltiplos mercenários;
* chance de missão usar poder do grupo;
* todos os membros receberem XP;
* dungeons existirem;
* dungeons usarem timer e loot manual;
* dungeons tiverem drops próprios;
* dungeons forem mais recompensadoras que missões;
* item tier e rarity forem exibidos e editáveis;
* equipamentos melhores puderem dropar em dungeons;
* admin parametrizar os novos conteúdos;
* seeds não sobrescreverem admin;
* multi-tenancy for respeitado;
* aplicação continuar rodando localmente.
