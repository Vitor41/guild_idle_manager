# MVP-004 - Progression, Items, Inventory and Admin Configuration

## Contexto

O MVP-000, MVP-001, MVP-002 e MVP-003 já foram validados.

A aplicação já possui:

* bootstrap local;
* autenticação;
* sessão;
* guilda;
* recursos;
* dashboard;
* mercenários;
* recrutamento;
* missões;
* timer;
* receber loot por ação do usuário;
* cálculo básico de sucesso/falha;
* ganho de ouro e XP;
* liberação de mercenário;
* admin inicial;
* edição de duração de missões;
* isolamento multi-tenant por usuário/guilda.

Agora o projeto precisa evoluir o loop de recompensa.

A missão deve passar a gerar progressão real de personagem e chance de itens básicos no inventário da guilda.

Também deve ser consolidado o padrão de admin parametrizável.

## Objetivo

Implementar:

* level up automático de mercenários;
* aumento básico de atributos;
* templates globais de itens;
* inventário da guilda;
* drops básicos em missões;
* resultado detalhado da missão;
* admin parametrizável para missões;
* admin para itens;
* admin para drops de itens por missão.

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/03-MULTI-TENANCY.md`
* `docs/04-GAME-LOOP.md`
* `docs/05-DATABASE-MODEL.md`
* `docs/08-BALANCE-RULES.md`
* `docs/09-ADMIN-CONFIGURATION.md`
* `tasks/MVP-004-PROGRESSION-ITEMS-INVENTORY-ADMIN.md`

Consultar também o código atual para manter o padrão já implementado.

## Escopo

Implementar:

* fórmula de XP necessário por nível;
* level up automático ao receber XP;
* aumento de atributos por level up;
* tabela global `item_templates`;
* tabela de inventário `guild_inventory_items`;
* tabela de configuração de drops `mission_template_item_drops`;
* seed inicial de itens básicos;
* seed inicial de drops para missões existentes;
* sorteio de drops ao receber loot de missão;
* atualização do inventário da guilda;
* tela de inventário;
* resultado detalhado da missão;
* admin de missões editando todos os campos relevantes;
* admin de itens;
* admin de drops por missão;
* dashboard com resumo de inventário/progressão.

## Fora do escopo

Não implementar nesta task:

* equipamentos;
* equipar item no mercenário;
* consumíveis funcionais;
* crafting;
* loja;
* marketplace;
* dungeons;
* bosses;
* raridade avançada funcional;
* level cap avançado;
* reset/prestígio;
* ranking;
* auditoria admin;
* balanceamento complexo;
* sinergia de grupo;
* notificações push;
* worker/scheduler.

## Progressão de mercenário

Ao receber XP, o sistema deve verificar se o mercenário sobe de nível.

Fórmula:

```text
xp_required = level atual * 100
```

Regra:

* XP ganho é somado ao XP atual.
* Enquanto `xp >= xp_required`, o mercenário sobe 1 nível.
* Ao subir, subtrair o XP necessário.
* Recalcular o XP necessário para o novo nível.
* Permitir múltiplos níveis no mesmo recebimento se houver XP suficiente.

Exemplo:

```text
level = 1
xp = 90
xp ganho = 250

total = 340

level 1 precisa 100
sobe para level 2
xp restante = 240

level 2 precisa 200
sobe para level 3
xp restante = 40
```

Resultado final:

```text
level = 3
xp = 40
```

## Atributos por level up

Ao subir 1 nível, aplicar:

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

Arqueiro sobe 1 nível:

```text
power +1
vitality +1
agility +1
```

Se a classe não for reconhecida, aplicar fallback:

```text
+1 power
+1 vitality
```

## Resultado detalhado da missão

Ao clicar em "Receber Loot", a tela deve exibir mensagem clara com:

```text
sucesso ou falha
ouro ganho
XP ganho
mercenários que receberam XP
level ups ocorridos
itens obtidos
```

Exemplo de sucesso:

```text
Missão concluída com sucesso.
Ouro ganho: 25
XP ganho: 10
Guerra recebeu 10 XP.
Itens obtidos: Pele de Lobo x1.
```

Exemplo com level up:

```text
Guerra subiu para o nível 2.
```

Exemplo de falha:

```text
A missão falhou.
Ouro ganho: 0
XP ganho: 2
Nenhum item encontrado.
```

## Tabela item_templates

Tabela global.

Representa itens disponíveis no jogo.

Não deve ter `user_id`.

Não deve ter `guild_id`.

Campos mínimos:

```text
id
name
description
item_type
rarity
is_active
created_at
updated_at
```

Valores iniciais para `item_type`:

```text
material
consumable
misc
```

Valores iniciais para `rarity`:

```text
common
uncommon
rare
epic
legendary
```

No MVP, itens serão apenas acumuláveis no inventário.

Não implementar uso/equipamento.

## Itens iniciais

Criar seed idempotente para:

```text
Pele de Lobo
Garra de Lobo
Erva Medicinal
Fragmento de Minério
Madeira Rústica
```

Sugestão:

```text
Pele de Lobo
item_type = material
rarity = common

Garra de Lobo
item_type = material
rarity = common

Erva Medicinal
item_type = material
rarity = common

Fragmento de Minério
item_type = material
rarity = common

Madeira Rústica
item_type = material
rarity = common
```

## Tabela guild_inventory_items

Tabela por guilda.

Representa itens acumulados no inventário da guilda.

Deve ter `guild_id`.

Campos mínimos:

```text
id
guild_id
item_template_id
quantity
created_at
updated_at
```

Regras:

* `guild_id` referencia `guilds.id`;
* `item_template_id` referencia `item_templates.id`;
* combinação `guild_id + item_template_id` deve ser única;
* quantidade deve iniciar maior que zero;
* ao ganhar item já existente, somar quantidade.

## Tabela mission_template_item_drops

Tabela global/configurável.

Relaciona missões globais com itens globais.

Não deve ter `user_id`.

Não deve ter `guild_id`.

Campos mínimos:

```text
id
mission_template_id
item_template_id
drop_chance
min_quantity
max_quantity
is_active
created_at
updated_at
```

Regras:

* `mission_template_id` referencia `mission_templates.id`;
* `item_template_id` referencia `item_templates.id`;
* `drop_chance` deve estar entre 0 e 100;
* `min_quantity` deve ser >= 1;
* `max_quantity` deve ser >= `min_quantity`;
* apenas drops ativos devem ser considerados.

## Seed inicial de drops

Criar seed idempotente para drops básicos.

Sugestão:

### Caçar lobos

```text
Pele de Lobo
drop_chance = 50
min_quantity = 1
max_quantity = 2

Garra de Lobo
drop_chance = 20
min_quantity = 1
max_quantity = 1
```

### Patrulhar estrada

```text
Erva Medicinal
drop_chance = 30
min_quantity = 1
max_quantity = 2

Madeira Rústica
drop_chance = 25
min_quantity = 1
max_quantity = 2
```

### Escoltar comerciante

```text
Fragmento de Minério
drop_chance = 25
min_quantity = 1
max_quantity = 2

Erva Medicinal
drop_chance = 20
min_quantity = 1
max_quantity = 1
```

Se alguma missão ou item não existir, não quebrar startup. Apenas ignorar ou registrar de forma segura.

## Regra de drop

Drops só ocorrem em caso de sucesso da missão.

Para cada drop ativo configurado para a missão:

1. Sortear número de 1 a 100.
2. Se número <= `drop_chance`, item dropa.
3. Sortear quantidade entre `min_quantity` e `max_quantity`.
4. Adicionar ao inventário da guilda.

Se a missão falhar:

```text
sem drops
```

## Tela de inventário

Criar rota:

```text
GET /inventory
```

Regras:

* apenas usuário autenticado pode acessar;
* usuário precisa ter guilda;
* listar apenas itens da guilda do usuário logado;
* não aceitar `guild_id` vindo do frontend.

Informações mínimas:

```text
nome do item
descrição
tipo
raridade
quantidade
```

Se inventário estiver vazio:

```text
Sua guilda ainda não possui itens.
```

## Dashboard

Atualizar dashboard com:

```text
Total de itens diferentes no inventário
Quantidade total de itens
Mercenário de maior nível
```

Adicionar link para:

```text
Inventário
```

## Admin parametrizável - regra geral

A partir desta task, o admin deve conseguir alterar os campos relevantes das configurações globais implementadas.

Não deixar apenas uma parte do template editável quando os demais campos são claramente de balanceamento.

## Admin de missões

Atualizar admin de missões para permitir editar:

```text
name
description
duration_seconds
base_gold_reward
base_xp_reward
base_success_chance
is_active
```

Validações:

```text
name obrigatório
description opcional
duration_seconds > 0
base_gold_reward >= 0
base_xp_reward >= 0
base_success_chance entre 1 e 100
is_active boolean
```

Alterações afetam apenas novas execuções.

Missões já iniciadas preservam os dados gravados em `mission_runs`.

## Admin de itens

Criar telas admin para itens.

Rotas sugeridas:

```text
GET /admin/items
GET /admin/items/create
POST /admin/items/create
GET /admin/items/{item_template_id}/edit
POST /admin/items/{item_template_id}/edit
```

Campos editáveis:

```text
name
description
item_type
rarity
is_active
```

Validações:

```text
name obrigatório
item_type obrigatório
rarity obrigatório
is_active boolean
```

Não precisa permitir exclusão física.

Para desativar item, usar `is_active = false`.

## Admin de drops

Criar telas admin para drops de missão.

Rotas sugeridas:

```text
GET /admin/mission-drops
GET /admin/mission-drops/create
POST /admin/mission-drops/create
GET /admin/mission-drops/{drop_id}/edit
POST /admin/mission-drops/{drop_id}/edit
```

Campos editáveis:

```text
mission_template_id
item_template_id
drop_chance
min_quantity
max_quantity
is_active
```

Validações:

```text
mission_template_id obrigatório
item_template_id obrigatório
drop_chance entre 0 e 100
min_quantity >= 1
max_quantity >= min_quantity
is_active boolean
```

Não precisa permitir exclusão física.

Para desativar drop, usar `is_active = false`.

## Multi-tenancy obrigatório

Inventário pertence à guilda.

Toda consulta de inventário deve filtrar por `guild_id`.

Errado:

```sql
SELECT * FROM guild_inventory_items;
```

Correto:

```sql
SELECT *
FROM guild_inventory_items
WHERE guild_id = :current_guild_id;
```

Ao atualizar inventário, sempre usar `guild_id` da guilda atual da missão.

Não aceitar `guild_id` do frontend.

## Organização esperada

Manter o padrão atual do projeto:

```text
models
repositories
services
routes
templates
static
core
database
```

Sugestão de arquivos possíveis:

```text
app/models/item.py
app/models/inventory.py

app/repositories/item_repository.py
app/repositories/inventory_repository.py
app/repositories/drop_repository.py

app/services/progression_service.py
app/services/inventory_service.py
app/services/drop_service.py

app/routes/inventory_routes.py
app/routes/admin_item_routes.py
app/routes/admin_drop_routes.py

app/templates/inventory/index.html
app/templates/admin/items.html
app/templates/admin/item_form.html
app/templates/admin/mission_drops.html
app/templates/admin/mission_drop_form.html
```

A estrutura pode ser ajustada conforme o padrão atual.

## Migration

Criar migration Alembic para:

```text
item_templates
guild_inventory_items
mission_template_item_drops
```

Também alterar estruturas existentes se necessário para suportar resultado detalhado.

Aplicar com:

```bash
alembic upgrade head
```

## Seeds

Criar seeds idempotentes para:

```text
item_templates
mission_template_item_drops
```

Regras:

* não duplicar registros;
* não sobrescrever alterações feitas pelo admin;
* se registro já existir, manter como está.

## Como testar manualmente

Após implementar:

1. Rodar migration.
2. Logar com usuário admin.
3. Acessar admin de missões.
4. Confirmar que todos os campos relevantes da missão são editáveis.
5. Acessar admin de itens.
6. Criar ou editar item.
7. Acessar admin de drops.
8. Configurar drop de item para "Caçar lobos".
9. Logar com usuário comum ou admin.
10. Acessar `/missions`.
11. Iniciar missão.
12. Aguardar timer.
13. Clicar em "Receber Loot".
14. Confirmar resultado detalhado.
15. Confirmar XP no mercenário.
16. Confirmar level up se XP suficiente.
17. Confirmar item no inventário se dropado.
18. Acessar `/inventory`.
19. Confirmar que os itens pertencem apenas à guilda atual.
20. Logar com outro usuário e confirmar inventário isolado.

## Critérios de conclusão

Considerar concluído quando:

* level up automático funcionar;
* XP necessário seguir `level atual * 100`;
* atributos subirem ao evoluir;
* resultado da missão mostrar ouro, XP, level up e itens;
* `item_templates` existir;
* `guild_inventory_items` existir;
* `mission_template_item_drops` existir;
* seeds de itens existirem sem duplicar;
* seeds de drops existirem sem duplicar;
* drops ocorrerem apenas em sucesso;
* itens acumularem no inventário da guilda;
* tela `/inventory` funcionar;
* inventário respeitar `guild_id`;
* dashboard mostrar resumo de inventário/progressão;
* admin de missões editar todos os campos relevantes;
* admin de itens funcionar;
* admin de drops funcionar;
* usuário comum não acessar admin;
* alterações admin não forem sobrescritas por seed;
* outro usuário não enxergar inventário da primeira guilda;
* aplicação continuar rodando com `uvicorn app.main:app --reload`.
