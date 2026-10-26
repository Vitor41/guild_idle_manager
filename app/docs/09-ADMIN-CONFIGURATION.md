# 09-ADMIN-CONFIGURATION.md

## Objetivo

Definir o padrão de configuração administrativa do projeto.

A partir deste ponto, toda funcionalidade configurável deve seguir um fluxo administrativo claro.

O admin deve conseguir parametrizar conteúdos globais do jogo sem depender de alteração direta no código.

## Princípio principal

Configurações globais do jogo devem ser editáveis pelo admin quando forem parte do balanceamento ou do catálogo do jogo.

Evitar hardcode de valores de gameplay.

Exemplos de valores que devem ser configuráveis:

```text
duração de missão
recompensa de ouro
recompensa de XP
chance de sucesso
status ativo/inativo
chance de drop
quantidade mínima de drop
quantidade máxima de drop
nome e descrição de templates globais
```

## O que é configuração global

Configuração global é algo compartilhado por todos os usuários.

Exemplos:

```text
mission_templates
item_templates
mission_template_item_drops
mercenary_classes
building_templates
balance_parameters
```

Essas tabelas não devem ter `user_id` nem `guild_id`.

## O que não é configuração global

Dados de progresso do jogador não são configuração global.

Exemplos:

```text
guilds
guild_resources
mercenaries
mission_runs
guild_inventory_items
```

Esses dados pertencem ao jogador/guilda e não devem ser editados por telas comuns de admin de balanceamento neste momento.

## Regra para telas admin

Toda tela admin deve:

```text
exigir usuário autenticado
exigir is_admin = true
validar dados no backend
exibir mensagens claras
evitar alteração fora do escopo
manter trilha visual simples
```

Usuário não admin não deve acessar rotas admin.

## Padrão de rotas admin

Usar padrão previsível:

```text
/admin
/admin/missions
/admin/missions/{id}/edit
/admin/items
/admin/items/{id}/edit
/admin/mission-drops
/admin/mission-drops/{id}/edit
```

Rotas podem ser ajustadas conforme a estrutura do projeto, mas devem ser claras.

## Admin de missões

O admin deve conseguir alterar todos os campos relevantes de `mission_templates`.

Campos editáveis:

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
duration_seconds > 0
base_gold_reward >= 0
base_xp_reward >= 0
base_success_chance entre 1 e 100
is_active boolean
```

Alterar uma missão deve afetar apenas novas execuções.

Missões já iniciadas mantêm `started_at`, `ends_at` e condições gravadas no momento da execução.

## Admin de itens

O admin deve conseguir alterar itens globais.

Campos recomendados para `item_templates`:

```text
name
description
item_type
rarity
is_active
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

No MVP, usar principalmente:

```text
material
common
```

Validações:

```text
name obrigatório
item_type obrigatório
rarity obrigatório
is_active boolean
```

## Admin de drops

Drops ligam missões globais a itens globais.

Tabela sugerida:

```text
mission_template_item_drops
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

## Seed e edição admin

Seeds devem criar dados iniciais.

O admin deve conseguir alterar os dados depois.

Seeds não devem duplicar registros.

Seeds não devem sobrescrever alterações administrativas a cada startup.

Regra:

```text
Se o registro não existe, criar.
Se já existe, não recriar nem sobrescrever.
```

## Evitar conflito com alterações do admin

Se o admin alterar "Caçar lobos" para 30 segundos, o seed não pode voltar para 300 segundos automaticamente.

Seeds precisam ser idempotentes e não destrutivos.

## Logs administrativos

No MVP, não é obrigatório criar auditoria administrativa.

No futuro, pode existir tabela para histórico de alterações.

Não implementar auditoria nesta fase, salvo se explicitamente solicitado.

## UX admin

As telas admin podem ser simples.

Priorizar:

```text
clareza
campos editáveis
botões salvar/cancelar
mensagens de erro
mensagens de sucesso
links de navegação
```

Não precisa visual final.

## Critério de aceite do padrão admin

O padrão estará correto quando:

```text
admin consegue editar todos os campos relevantes de templates globais
validações acontecem no backend
usuário comum não acessa admin
seeds não sobrescrevem alterações do admin
alterações em templates afetam novas execuções futuras
dados de progresso dos usuários continuam isolados por guilda
```
