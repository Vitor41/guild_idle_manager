# 03 - Multi-tenancy

## Objetivo

Definir como o projeto deve isolar os dados de cada usuário.

O jogo deve funcionar como um sistema multi-tenant por usuário/guilda.

Cada usuário deve acessar apenas os dados da própria guilda.

## Conceito principal

O usuário é o dono da conta.

A guilda é o núcleo do progresso do jogador.

A maioria dos dados do jogo deve estar vinculada à guilda, não diretamente ao usuário.

Fluxo conceitual:

```text
user -> guild -> dados do jogo
```

Exemplo:

```text
users
  id = 1
  username = VITAO

guilds
  id = 10
  user_id = 1
  name = Guilda do Vitão

mercenaries
  id = 100
  guild_id = 10
  name = Arkon

mission_runs
  id = 500
  guild_id = 10
  mission_id = 3
```

Quando o usuário `VITAO` logar, o sistema deve buscar a guilda vinculada ao `user_id` dele e carregar apenas dados relacionados a essa guilda.

Se um novo usuário `VITAO02` logar e ainda não tiver guilda, o sistema deve iniciar zerado e direcionar para criação da guilda.

## Regra obrigatória

Nenhuma tela autenticada pode carregar dados de progresso sem filtrar pela guilda do usuário logado.

Toda consulta de dados do jogador deve partir de:

```text
current_user -> guild -> dados da guilda
```

## Tabelas globais

Tabelas globais são compartilhadas por todos os usuários.

Elas representam regras, catálogos, templates ou configurações do jogo.

Essas tabelas não devem ter `user_id` nem `guild_id`.

Exemplos:

```text
mercenary_classes
mission_templates
item_templates
building_templates
rarity_rules
balance_parameters
```

Exemplo prático:

A missão "Caçar Lobos" existe uma vez em `mission_templates`.

Todos os jogadores podem visualizar essa missão se ela estiver liberada pelas regras do jogo.

## Tabelas por guilda

Tabelas por guilda representam progresso individual do jogador.

Essas tabelas devem ter `guild_id`.

Exemplos:

```text
guilds
guild_resources
mercenaries
mission_runs
mission_run_members
inventory_items
guild_buildings
reward_logs
```

Exemplo prático:

O template global define que a missão "Caçar Lobos" dura 5 minutos.

A tabela `mission_runs` registra que a guilda do usuário iniciou essa missão em determinado horário.

## Quando usar user_id

Usar `user_id` diretamente apenas em tabelas ligadas à conta, autenticação ou propriedade principal.

Exemplos:

```text
users
guilds
user_sessions
password_reset_tokens
```

A tabela `guilds` deve ter `user_id`.

As demais tabelas de progresso devem preferencialmente usar `guild_id`.

## Quando usar guild_id

Usar `guild_id` em dados de jogo pertencentes à guilda.

Exemplos:

```text
mercenaries.guild_id
mission_runs.guild_id
guild_resources.guild_id
inventory_items.guild_id
guild_buildings.guild_id
reward_logs.guild_id
```

Isso evita duplicar `user_id` em todas as tabelas e mantém a modelagem mais limpa.

## Regra para queries

Errado:

```sql
SELECT *
FROM mercenaries;
```

Errado:

```sql
SELECT *
FROM mercenaries
WHERE id = :mercenary_id;
```

Correto:

```sql
SELECT *
FROM mercenaries
WHERE guild_id = :current_guild_id;
```

Correto para buscar um registro específico:

```sql
SELECT *
FROM mercenaries
WHERE id = :mercenary_id
AND guild_id = :current_guild_id;
```

Toda ação que altere dados deve validar posse pela guilda.

## Regra para rotas

Rotas autenticadas devem:

1. Identificar o usuário logado.
2. Buscar a guilda do usuário.
3. Usar o `guild_id` dessa guilda nas consultas.
4. Impedir acesso se a guilda não existir, exceto nas rotas de criação de guilda.
5. Nunca aceitar `guild_id` livre vindo do frontend como fonte confiável.

O frontend não deve decidir qual guilda está ativa.

A guilda ativa deve ser determinada no backend a partir do usuário logado.

## Regra sobre parâmetros recebidos

O backend pode receber IDs de entidades, como:

```text
mercenary_id
mission_template_id
mission_run_id
```

Mas sempre deve validar se a entidade pertence à guilda do usuário quando for dado de progresso.

Exemplo:

Se o usuário tentar acessar:

```text
/missions/run/55
```

O sistema deve buscar:

```sql
SELECT *
FROM mission_runs
WHERE id = 55
AND guild_id = :current_guild_id;
```

Se não encontrar, retornar erro ou redirecionar.

Nunca buscar apenas por `id`.

## Guilda inicial

Cada usuário deve ter no máximo uma guilda no MVP inicial.

Regra:

```text
1 user -> 0 ou 1 guild
```

Se o usuário não tiver guilda, deve ser enviado para o fluxo de criação da guilda.

No futuro pode existir múltiplas guildas por usuário, mas isso está fora do MVP inicial.

## Primeiro acesso

Fluxo esperado:

1. Usuário cria conta.
2. Usuário faz login.
3. Sistema verifica se existe guilda para `user_id`.
4. Se não existir, redireciona para criação de guilda.
5. Usuário informa nome da guilda.
6. Sistema cria:

   * guilda nível 1;
   * recursos iniciais;
   * mercenários iniciais, se a task exigir;
   * dados básicos de progresso.

## Segurança

O isolamento de dados deve ser backend-first.

Não confiar em filtros no frontend.

Não confiar em campos escondidos no HTML.

Não confiar em `guild_id` enviado por formulário.

Não expor dados de outra guilda em templates, APIs, logs ou mensagens de erro.

## Serviços recomendados

Criar ou manter uma função central para obter a guilda atual.

Exemplo conceitual:

```python
def get_current_guild(db, current_user):
    return db.query(Guild).filter(Guild.user_id == current_user.id).first()
```

Essa função deve ser reutilizada nas rotas autenticadas.

## Repositórios

Repositories que acessam dados de progresso devem receber `guild_id`.

Exemplo conceitual:

```python
def list_mercenaries_by_guild(db, guild_id):
    return db.query(Mercenary).filter(Mercenary.guild_id == guild_id).all()
```

Evitar repositories que retornem dados de progresso sem escopo.

## Services

Services devem receber o contexto da guilda ou buscar a guilda a partir do usuário logado.

Exemplo:

```python
mission_service.start_mission(
    db=db,
    guild_id=current_guild.id,
    mission_template_id=mission_template_id,
    mercenary_ids=mercenary_ids
)
```

## Templates

Templates devem renderizar apenas dados já filtrados pelo backend.

Templates não devem aplicar regra de segurança.

## Regras de erro

Se o usuário tentar acessar dado que não pertence a ele, o sistema deve:

* retornar 404, ou
* redirecionar com mensagem genérica.

Não informar que o dado existe em outra guilda.

Mensagem aceitável:

```text
Registro não encontrado ou indisponível.
```

Mensagem não aceitável:

```text
Essa missão pertence a outra guilda.
```

## Critério de aceite técnico

A implementação respeita multi-tenancy quando:

* cada usuário tem dados isolados;
* novo usuário começa sem progresso;
* dados de guilda são carregados por `guild_id`;
* dados globais não possuem `guild_id`;
* dados de progresso possuem `guild_id`;
* rotas autenticadas não aceitam `guild_id` livre do frontend;
* queries de alteração validam posse pela guilda;
* não existe consulta solta retornando dados de todos os usuários;
* a guilda atual é obtida pelo usuário logado.
