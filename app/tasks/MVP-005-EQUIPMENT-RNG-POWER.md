# MVP-005 - Equipment, RNG and Mercenary Power

## Contexto

O MVP-000 ao MVP-004 já foram validados.

A aplicação já possui:

* autenticação;
* sessão;
* guilda;
* recursos;
* mercenários;
* level up;
* missões;
* timer;
* loot manual;
* itens globais;
* inventário da guilda;
* drops de itens;
* admin parametrizável para missões, itens e drops;
* isolamento multi-tenant por usuário/guilda.

Agora o jogo precisa evoluir os itens para permitir equipamentos com atributos próprios, nível mínimo e bônus aleatório por instância.

## Objetivo

Implementar a primeira versão da mecânica de equipamentos.

Equipamentos devem:

* ser itens únicos por instância;
* ter nível mínimo para equipar;
* ter atributos base configuráveis;
* ter bônus RNG gerado quando o item entra na guilda;
* poder ser equipados e desequipados por mercenários;
* impactar o poder total do mercenário;
* impactar a chance final de sucesso das missões;
* exibir na tela o bônus de chance gerado pelo mercenário/equipamentos.

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
* `tasks/MVP-005-EQUIPMENT-RNG-POWER.md`

Consultar também o código atual para manter o padrão já implementado.

## Escopo

Implementar:

* expansão de `item_templates` para suportar equipamentos;
* tabela de instâncias únicas de equipamento;
* geração de bônus RNG ao criar equipamento para a guilda;
* equipamento como drop de missão;
* tela/listagem de equipamentos no inventário;
* equipar item em mercenário;
* desequipar item;
* validação de nível mínimo;
* validação de slot único;
* cálculo de atributos totais do mercenário;
* cálculo de poder total do mercenário;
* chance de missão baseada em poder total;
* exibição do bônus de chance ao selecionar/listar mercenários em missões;
* admin parametrizável para campos de equipamento;
* seeds iniciais de equipamentos simples;
* seeds iniciais de drops de equipamento simples.

## Fora do escopo

Não implementar nesta task:

* refino;
* upgrade de equipamento;
* crafting;
* loja;
* trade;
* set bonus;
* durabilidade;
* encantamento manual;
* gemas;
* comparação avançada;
* combate real;
* dungeons;
* bosses;
* ranking;
* auditoria admin.

## Alterações em item_templates

Expandir `item_templates` com campos para equipamentos.

Campos sugeridos:

```text
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
```

Regras:

* `equipment_slot` pode ser nulo para itens não equipamento;
* `required_level` pode ser nulo ou 1 para itens não equipamento;
* bônus devem iniciar em 0;
* `rng_bonus_min` deve iniciar em 0;
* `rng_bonus_max` deve iniciar em 0;
* para `item_type = equipment`, `equipment_slot` é obrigatório;
* para `item_type = equipment`, `required_level >= 1`.

Slots iniciais:

```text
weapon
armor
accessory
```

Atributos RNG possíveis:

```text
power
vitality
agility
intelligence
luck
armor
```

## Tabela guild_item_instances

Criar tabela para equipamentos únicos da guilda.

Campos mínimos:

```text
id
guild_id
item_template_id
equipped_to_mercenary_id
equipment_slot
required_level
bonus_power
bonus_vitality
bonus_agility
bonus_intelligence
bonus_luck
bonus_armor
rng_bonus_attribute
rng_bonus_value
created_at
updated_at
```

Regras:

* `guild_id` referencia `guilds.id`;
* `item_template_id` referencia `item_templates.id`;
* `equipped_to_mercenary_id` referencia `mercenaries.id` e pode ser nulo;
* copiar atributos base do template ao criar instância;
* gerar RNG uma única vez ao criar instância;
* não recalcular RNG ao renderizar tela;
* não recalcular RNG ao equipar;
* não recalcular RNG ao desequipar;
* item equipado continua pertencendo à guilda.

## Geração de instância de equipamento

Quando um equipamento for dropado ou criado para a guilda:

1. Buscar `item_template`.
2. Validar `item_type = equipment`.
3. Criar `guild_item_instances`.
4. Copiar atributos base do template.
5. Sortear `rng_bonus_attribute`.
6. Sortear `rng_bonus_value` entre `rng_bonus_min` e `rng_bonus_max`.
7. Salvar a instância.

Se `rng_bonus_max = 0`, pode criar sem bônus RNG:

```text
rng_bonus_attribute = null
rng_bonus_value = 0
```

## Seeds iniciais de equipamentos

Criar seeds idempotentes para equipamentos simples.

Exemplos:

### Espada Enferrujada

```text
item_type = equipment
equipment_slot = weapon
required_level = 1
rarity = common
bonus_power = 2
bonus_vitality = 0
bonus_agility = 0
bonus_intelligence = 0
bonus_luck = 0
bonus_armor = 0
rng_bonus_min = 1
rng_bonus_max = 1
```

### Armadura de Couro

```text
item_type = equipment
equipment_slot = armor
required_level = 1
rarity = common
bonus_power = 0
bonus_vitality = 3
bonus_agility = 0
bonus_intelligence = 0
bonus_luck = 0
bonus_armor = 1
rng_bonus_min = 1
rng_bonus_max = 1
```

### Anel Simples

```text
item_type = equipment
equipment_slot = accessory
required_level = 1
rarity = common
bonus_power = 0
bonus_vitality = 0
bonus_agility = 0
bonus_intelligence = 0
bonus_luck = 2
bonus_armor = 0
rng_bonus_min = 1
rng_bonus_max = 1
```

Não sobrescrever alterações feitas pelo admin.

## Drops de equipamento

Permitir que `mission_template_item_drops` também gere equipamentos.

Regra:

* se o item dropado não for equipment, acumular em `guild_inventory_items`;
* se o item dropado for equipment, criar instância em `guild_item_instances`.

Para equipment, ignorar quantidade agregada.

Se a configuração de drop tiver `min_quantity` e `max_quantity` maior que 1, criar uma instância para cada unidade sorteada.

Exemplo:

```text
dropou Espada Enferrujada quantidade 2
criar 2 linhas em guild_item_instances
cada uma com RNG próprio
```

## Seeds de drops de equipamentos

Adicionar drops simples de equipamentos nas missões existentes.

Sugestão:

### Caçar lobos

```text
Armadura de Couro
drop_chance = 10
min_quantity = 1
max_quantity = 1
```

### Patrulhar estrada

```text
Espada Enferrujada
drop_chance = 10
min_quantity = 1
max_quantity = 1
```

### Escoltar comerciante

```text
Anel Simples
drop_chance = 10
min_quantity = 1
max_quantity = 1
```

Seed deve ser idempotente e não sobrescrever alterações admin.

## Tela de inventário

Atualizar `/inventory` para separar:

```text
Materiais / Itens acumuláveis
Equipamentos
```

Para equipamentos, exibir:

```text
nome
slot
nível mínimo
raridade
bônus base
bônus RNG
status equipado/livre
mercenário equipado, se houver
```

## Tela de mercenários

Atualizar tela/listagem de mercenários para exibir:

```text
atributos base
bônus de equipamentos
atributos totais
poder total
equipamentos atuais
ações de equipar/desequipar
```

Se preferir por produtividade, criar tela de detalhe do mercenário:

```text
GET /mercenaries/{mercenary_id}
```

Nessa tela, permitir:

* ver detalhes;
* ver equipamentos equipados;
* equipar equipamento disponível;
* desequipar equipamento.

Todas as consultas devem validar `guild_id`.

## Equipar item

Rota sugerida:

```text
POST /mercenaries/{mercenary_id}/equip
```

Campos:

```text
item_instance_id
```

Regras:

* usuário precisa estar autenticado;
* mercenário precisa pertencer à guilda do usuário;
* item instance precisa pertencer à mesma guilda;
* item precisa estar livre;
* item precisa ser equipment;
* mercenário precisa ter nível >= required_level;
* mercenário não pode ter outro item no mesmo slot;
* ao equipar, preencher `equipped_to_mercenary_id`.

Mensagem se nível insuficiente:

```text
Mercenário não possui nível suficiente para equipar este item.
```

Mensagem se slot ocupado:

```text
Este slot já possui um equipamento. Desequipe o item atual antes de equipar outro.
```

## Desequipar item

Rota sugerida:

```text
POST /mercenaries/{mercenary_id}/unequip
```

Campos:

```text
item_instance_id
```

Regras:

* usuário precisa estar autenticado;
* mercenário precisa pertencer à guilda;
* item precisa estar equipado no mercenário informado;
* ao desequipar, limpar `equipped_to_mercenary_id`.

## Cálculo de atributos totais

Calcular:

```text
total_power = mercenary.power + equipment_bonus_power + rng_power
total_vitality = mercenary.vitality + equipment_bonus_vitality + rng_vitality
total_agility = mercenary.agility + equipment_bonus_agility + rng_agility
total_intelligence = mercenary.intelligence + equipment_bonus_intelligence + rng_intelligence
total_luck = mercenary.luck + equipment_bonus_luck + rng_luck
total_armor = equipment_bonus_armor + rng_armor
```

Observação:

`armor` pode existir apenas como bônus de equipamento neste MVP.

## Cálculo de poder total

Criar função centralizada para calcular poder total.

Sugestão:

```text
mercenary_total_power_score =
total_power
+ floor(total_vitality / 2)
+ floor(total_agility / 2)
+ floor(total_intelligence / 2)
+ floor(total_luck / 3)
+ floor(total_armor / 2)
```

Evitar duplicar essa fórmula em vários lugares.

## Chance final da missão

Atualizar cálculo da chance de missão.

Regra sugerida:

```text
bonus_chance = floor(mercenary_total_power_score / 10)
final_success_chance = mission_template.base_success_chance + bonus_chance
```

Aplicar limites:

```text
mínimo = 5
máximo = 95
```

Essa regra substitui a fórmula anterior baseada apenas em `mercenary.power`.

## Exibição de chance em missões

Na tela `/missions`, ao listar mercenários disponíveis para iniciar missão, exibir chance estimada.

Exemplo:

```text
Guerra - Poder total: 42 - Chance estimada: 74% (+4%)
```

Para cada missão disponível, o sistema deve calcular:

```text
chance base da missão
bônus do mercenário/equipamentos
chance final estimada
```

Se a UI atual usar select simples, pode exibir o texto no option.

Exemplo:

```text
Guerra | Poder 42 | 74% (+4%)
```

O backend deve recalcular tudo ao iniciar/receber loot.

A tela é apenas informativa.

## Receber Loot

Atualizar o cálculo de sucesso ao receber loot para usar o novo poder total.

A recompensa continua seguindo a regra atual:

* sucesso: ouro + XP + drops;
* falha: XP reduzido;
* drops apenas em sucesso.

## Admin de itens

Atualizar admin de itens para permitir configurar campos de equipamento:

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
```

Validações:

```text
equipment_slot obrigatório se item_type = equipment
required_level >= 1 se item_type = equipment
bônus >= 0
rng_bonus_min >= 0
rng_bonus_max >= rng_bonus_min
```

## Multi-tenancy obrigatório

Todas as operações de equipamento devem validar `guild_id`.

Errado:

```sql
SELECT * FROM guild_item_instances WHERE id = :item_instance_id;
```

Correto:

```sql
SELECT *
FROM guild_item_instances
WHERE id = :item_instance_id
AND guild_id = :current_guild_id;
```

Ao equipar, validar:

```text
mercenary.guild_id == current_guild_id
item_instance.guild_id == current_guild_id
```

Não aceitar `guild_id` no frontend.

## Migration

Criar migration Alembic para:

```text
novos campos em item_templates
guild_item_instances
```

Aplicar com:

```bash
alembic upgrade head
```

## Seeds

Criar seeds idempotentes para:

```text
Espada Enferrujada
Armadura de Couro
Anel Simples
drops iniciais desses equipamentos
```

Regras:

* não duplicar;
* não sobrescrever alteração feita pelo admin;
* não quebrar se missão/item não existir.

## Como testar manualmente

Após implementar:

1. Rodar migration.
2. Logar com usuário admin.
3. Acessar admin de itens.
4. Confirmar campos de equipamento editáveis.
5. Confirmar existência dos equipamentos iniciais.
6. Acessar admin de drops.
7. Confirmar drops de equipamento em missões.
8. Logar com usuário com guilda e mercenário.
9. Rodar missão até dropar equipamento, ou aumentar chance no admin para testar.
10. Acessar `/inventory`.
11. Confirmar equipamento único com bônus RNG.
12. Acessar mercenário.
13. Equipar item.
14. Confirmar nível mínimo.
15. Confirmar slot único.
16. Ver atributos totais e poder total atualizados.
17. Acessar `/missions`.
18. Confirmar chance estimada com bônus do mercenário/equipamento.
19. Iniciar missão.
20. Receber loot.
21. Confirmar que cálculo usa poder total.
22. Desequipar item.
23. Confirmar que item volta a ficar livre.
24. Logar com outro usuário e confirmar que não acessa equipamentos da primeira guilda.

## Critérios de conclusão

Considerar concluído quando:

* `item_templates` suportar campos de equipamento;
* equipamentos forem instâncias únicas em tabela própria;
* equipamentos tiverem bônus base;
* equipamentos tiverem bônus RNG gerado uma única vez;
* equipamentos tiverem nível mínimo;
* inventário separar acumuláveis e equipamentos;
* mercenário puder equipar item;
* mercenário puder desequipar item;
* sistema impedir equipar se nível for insuficiente;
* sistema impedir dois itens no mesmo slot;
* atributos totais considerarem equipamentos;
* poder total for calculado;
* chance de missão usar poder total;
* tela de missões exibir bônus/chance estimada;
* admin permitir parametrizar campos de equipamento;
* drops de equipamento criarem instâncias únicas;
* multi-tenancy for respeitado;
* aplicação continuar rodando com `uvicorn app.main:app --reload`.
