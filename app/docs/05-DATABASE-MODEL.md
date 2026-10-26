# 05 - Database Model

## Objetivo

Definir o modelo inicial de banco de dados do projeto.

Este documento deve orientar a criação das primeiras tabelas reais do jogo, começando por autenticação, usuário, guilda e recursos iniciais.

## Princípio principal

O jogo deve funcionar com isolamento de dados por usuário/guilda.

O usuário representa a conta.

A guilda representa o progresso do jogador.

A maior parte dos dados futuros do jogo deve se relacionar com `guild_id`.

Fluxo base:

```text
users -> guilds -> dados do jogo
```

## Padrão técnico

Usar SQLAlchemy ORM.

Os models devem importar o `Base` a partir do padrão definido no projeto, preferencialmente:

```python
from app.database.connection import Base
```

Se o projeto já tiver adotado outro padrão no bootstrap, manter consistência com o padrão existente.

## Convenções

Usar nomes de tabelas no plural.

Exemplos:

```text
users
guilds
guild_resources
```

Usar `created_at` e `updated_at` nas tabelas principais.

Usar timezone-aware datetime quando possível.

Usar constraints e relacionamentos claros.

Não criar tabelas sem necessidade para o escopo da task atual.

## Tipos de ID

Para o MVP inicial, usar IDs inteiros autoincrementais.

Exemplo:

```text
id integer primary key
```

Não usar UUID no MVP inicial, salvo se já houver decisão técnica forte no projeto.

## Tabela users

Representa a conta do jogador.

Campos mínimos:

```text
id
username
email
password_hash
is_active
created_at
updated_at
```

Regras:

* `username` deve ser obrigatório.
* `username` deve ser único.
* `email` pode ser opcional no MVP.
* `email`, se informado, deve ser único.
* `password_hash` deve ser obrigatório.
* Nunca salvar senha em texto puro.
* `is_active` deve iniciar como `true`.

Exemplo conceitual:

```text
users
- id: integer, primary key
- username: string, unique, not null
- email: string, unique, nullable
- password_hash: string, not null
- is_active: boolean, default true
- created_at: datetime
- updated_at: datetime
```

## Tabela guilds

Representa a guilda do jogador.

No MVP inicial, cada usuário pode ter no máximo uma guilda.

Relação:

```text
1 user -> 0 ou 1 guild
```

Campos mínimos:

```text
id
user_id
name
level
reputation
created_at
updated_at
```

Regras:

* `user_id` deve referenciar `users.id`.
* `user_id` deve ser único para garantir uma guilda por usuário no MVP.
* `name` deve ser obrigatório.
* `level` deve iniciar em `1`.
* `reputation` deve iniciar em `0`.

Exemplo conceitual:

```text
guilds
- id: integer, primary key
- user_id: integer, foreign key users.id, unique, not null
- name: string, not null
- level: integer, default 1
- reputation: integer, default 0
- created_at: datetime
- updated_at: datetime
```

## Tabela guild_resources

Representa os recursos da guilda.

Relação:

```text
1 guild -> 1 guild_resources
```

Campos mínimos:

```text
id
guild_id
gold
wood
ore
crystals
created_at
updated_at
```

Regras:

* `guild_id` deve referenciar `guilds.id`.
* `guild_id` deve ser único.
* Recursos devem iniciar com valores definidos pela task de criação da guilda.
* No MVP inicial, usar números inteiros.

Valores iniciais recomendados:

```text
gold = 100
wood = 0
ore = 0
crystals = 0
```

Exemplo conceitual:

```text
guild_resources
- id: integer, primary key
- guild_id: integer, foreign key guilds.id, unique, not null
- gold: integer, default 100
- wood: integer, default 0
- ore: integer, default 0
- crystals: integer, default 0
- created_at: datetime
- updated_at: datetime
```

## Tabelas globais futuras

Tabelas globais representam catálogos e regras compartilhadas por todos os jogadores.

Não criar ainda se não forem necessárias para a task atual.

Exemplos futuros:

```text
mercenary_classes
mission_templates
item_templates
building_templates
balance_parameters
```

Essas tabelas não devem ter `user_id` nem `guild_id`.

## Tabelas por guilda futuras

Tabelas de progresso individual devem ter `guild_id`.

Exemplos futuros:

```text
mercenaries
mission_runs
mission_run_members
inventory_items
guild_buildings
reward_logs
```

Essas tabelas serão criadas em tasks futuras.

Não criar no MVP-001, salvo se a task for alterada explicitamente.

## Regra de isolamento

Toda consulta de progresso do jogador deve respeitar a guilda do usuário logado.

Errado:

```sql
SELECT * FROM guilds;
```

Correto:

```sql
SELECT * FROM guilds WHERE user_id = :current_user_id;
```

Errado:

```sql
SELECT * FROM guild_resources WHERE id = :resource_id;
```

Correto:

```sql
SELECT gr.*
FROM guild_resources gr
JOIN guilds g ON g.id = gr.guild_id
WHERE gr.id = :resource_id
AND g.user_id = :current_user_id;
```

## Sessão

No MVP inicial, a sessão pode ser baseada em cookie assinado via middleware do FastAPI/Starlette.

Não é obrigatório criar tabela de sessões.

A sessão deve armazenar apenas o necessário, como:

```text
user_id
```

Não armazenar senha, hash de senha ou dados sensíveis na sessão.

## Migrations

Toda alteração de schema deve ser feita via Alembic.

Após criar ou alterar models, gerar migration com:

```bash
alembic revision --autogenerate -m "create auth and guild foundation"
```

Depois aplicar com:

```bash
alembic upgrade head
```

Não editar o banco manualmente para criar tabelas finais do projeto.

## Critério técnico

O modelo inicial estará correto quando:

* existir tabela `users`;
* existir tabela `guilds`;
* existir tabela `guild_resources`;
* `guilds.user_id` for chave estrangeira para `users.id`;
* `guilds.user_id` for único;
* `guild_resources.guild_id` for chave estrangeira para `guilds.id`;
* `guild_resources.guild_id` for único;
* senha for salva apenas como hash;
* novo usuário puder existir sem guilda;
* usuário com guilda puder carregar apenas a própria guilda;
* dados de progresso forem acessados via guilda do usuário logado.
