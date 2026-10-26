# MVP-002 - Mercenaries Foundation

## Contexto

O MVP-000 e o MVP-001 já foram validados.

A aplicação já possui:

* bootstrap local;
* conexão PostgreSQL;
* Alembic;
* autenticação;
* cadastro;
* login;
* logout;
* sessão;
* usuário logado;
* guilda vinculada ao usuário;
* recursos iniciais da guilda;
* dashboard autenticado;
* isolamento multi-tenant por usuário/guilda.

Agora o projeto precisa criar a primeira entidade real de jogo: mercenários.

Mercenários serão a base para missões, expedições idle, recompensas, evolução e progressão futura.

## Objetivo

Permitir que a guilda do usuário possua mercenários próprios.

O usuário autenticado deve conseguir acessar uma tela de mercenários, visualizar seus mercenários e recrutar novos mercenários básicos usando ouro da guilda.

Cada mercenário deve pertencer exclusivamente à guilda do usuário logado.

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/03-MULTI-TENANCY.md`
* `docs/05-DATABASE-MODEL.md`
* `tasks/MVP-002-MERCENARIES-FOUNDATION.md`

Consultar também o código atual para manter o padrão já implementado em:

* models;
* repositories;
* services;
* routes;
* templates;
* migrations.

Não ler documentos de missões, idle calculation, recompensas ou balanceamento avançado nesta task.

## Escopo

Implementar:

* tabela global de classes de mercenários;
* tabela de mercenários da guilda;
* migration Alembic;
* seed simples das classes iniciais;
* tela de mercenários;
* listagem dos mercenários da guilda;
* ação para recrutar mercenário básico;
* desconto de ouro da guilda ao recrutar;
* validações básicas;
* atualização do dashboard com resumo de mercenários;
* menu/link para acessar Mercenários.

## Fora do escopo

Não implementar nesta task:

* missões;
* envio de mercenários para missão;
* cálculo idle;
* recompensas;
* level up real;
* equipamentos;
* inventário;
* raridade avançada;
* mercado complexo;
* contratação aleatória avançada;
* loja;
* ranking;
* admin;
* balanceamento complexo;
* morte permanente;
* lesões;
* sinergia de grupo.

## Modelo de dados

### Tabela mercenary_classes

Tabela global.

Representa as classes disponíveis no jogo.

Não deve ter `user_id`.

Não deve ter `guild_id`.

Campos mínimos:

```text
id
name
description
base_power
base_vitality
base_agility
base_intelligence
base_luck
is_active
created_at
updated_at
```

Classes iniciais:

```text
Guerreiro
Arqueiro
Ladino
Mago
Clérigo
```

Sugestão de atributos base:

```text
Guerreiro
power = 8
vitality = 8
agility = 4
intelligence = 2
luck = 3

Arqueiro
power = 6
vitality = 4
agility = 8
intelligence = 3
luck = 4

Ladino
power = 5
vitality = 4
agility = 9
intelligence = 3
luck = 6

Mago
power = 7
vitality = 3
agility = 3
intelligence = 9
luck = 4

Clérigo
power = 4
vitality = 5
agility = 3
intelligence = 8
luck = 5
```

### Tabela mercenaries

Tabela por guilda.

Representa os mercenários recrutados pela guilda.

Deve ter `guild_id`.

Campos mínimos:

```text
id
guild_id
class_id
name
level
xp
status
rarity
power
vitality
agility
intelligence
luck
created_at
updated_at
```

Regras:

* `guild_id` referencia `guilds.id`;
* `class_id` referencia `mercenary_classes.id`;
* `level` inicia em `1`;
* `xp` inicia em `0`;
* `status` inicia como `available`;
* `rarity` inicia como `common`;
* atributos iniciais devem ser copiados da classe escolhida;
* todo mercenário pertence à guilda do usuário logado.

Status possíveis no MVP:

```text
available
busy
```

Nesta task, todo mercenário novo deve iniciar como:

```text
available
```

O status `busy` será usado futuramente em missões.

## Recrutamento

Criar ação para recrutar mercenário.

Rota sugerida:

```text
POST /mercenaries/recruit
```

Regras:

* apenas usuário autenticado pode recrutar;
* usuário precisa ter guilda;
* usar a guilda do usuário logado;
* não aceitar `guild_id` vindo do frontend;
* recrutar apenas classes ativas;
* descontar ouro da guilda;
* criar mercenário vinculado à guilda;
* redirecionar para tela de mercenários após sucesso.

Custo inicial de recrutamento:

```text
50 gold
```

Se a guilda não tiver ouro suficiente, exibir mensagem simples:

```text
Ouro insuficiente para recrutar.
```

## Escolha de classe no recrutamento

Para o MVP, o usuário pode escolher a classe em um select simples.

Não implementar sorteio aleatório ainda.

Campos do formulário:

```text
name
class_id
```

Regras:

* nome do mercenário é obrigatório;
* classe é obrigatória;
* classe precisa existir e estar ativa;
* nome pode repetir no MVP;
* nome deve pertencer apenas ao mercenário criado, sem validação global.

## Tela de mercenários

Rota sugerida:

```text
GET /mercenaries
```

Regras:

* apenas usuário autenticado pode acessar;
* se usuário não tiver guilda, redirecionar para `/guild/create`;
* listar apenas mercenários da guilda do usuário logado;
* exibir formulário de recrutamento;
* exibir ouro atual da guilda;
* exibir custo de recrutamento.

Informações mínimas na listagem:

```text
nome
classe
nível
xp
status
raridade
força
vitalidade
agilidade
inteligência
sorte
```

Se não houver mercenários, exibir:

```text
Sua guilda ainda não possui mercenários.
```

## Dashboard

Atualizar o dashboard para exibir resumo simples de mercenários:

```text
Mercenários totais
Mercenários disponíveis
Mercenários ocupados
```

Como ainda não há missões, todos devem estar disponíveis.

Também adicionar link ou botão para:

```text
Ver mercenários
```

## Seed das classes

Garantir que as classes iniciais existam.

Pode ser feito por migration, script simples ou função idempotente no startup, desde que o padrão escolhido seja claro e não duplique dados.

Preferência:

* seed idempotente;
* se a classe já existir, não criar duplicada.

As classes iniciais devem estar disponíveis após rodar o projeto/migration.

## Multi-tenancy obrigatório

Toda consulta de mercenários deve filtrar por `guild_id` da guilda do usuário logado.

Errado:

```sql
SELECT * FROM mercenaries;
```

Correto:

```sql
SELECT * FROM mercenaries WHERE guild_id = :current_guild_id;
```

Ao buscar um mercenário específico futuramente, sempre validar:

```sql
WHERE id = :mercenary_id
AND guild_id = :current_guild_id
```

Não aceitar `guild_id` vindo do frontend.

## Organização esperada

Manter o padrão já existente no projeto.

Sugestão de arquivos possíveis:

```text
app/models/mercenary.py

app/repositories/mercenary_repository.py
app/repositories/mercenary_class_repository.py

app/services/mercenary_service.py

app/routes/mercenary_routes.py

app/templates/mercenaries/index.html
```

A estrutura pode ser ajustada conforme o padrão atual do projeto, mas a separação deve ser mantida:

* model define tabela;
* repository acessa banco;
* service concentra regra de negócio;
* route trata request, form, redirect e template;
* template apenas renderiza dados já filtrados.

## Validações esperadas

Após implementar, deve ser possível:

1. Fazer login com usuário existente.
2. Acessar `/mercenaries`.
3. Ver tela de mercenários da própria guilda.
4. Ver ouro atual.
5. Ver formulário de recrutamento.
6. Recrutar um mercenário gastando 50 de ouro.
7. Ver o mercenário listado.
8. Ver ouro reduzido.
9. Tentar recrutar sem ouro suficiente e receber mensagem de erro.
10. Fazer logout.
11. Logar com outro usuário.
12. Confirmar que o outro usuário não vê mercenários da primeira guilda.

## Migration

Criar migration Alembic para:

```text
mercenary_classes
mercenaries
```

Aplicar com:

```bash
alembic upgrade head
```

## Requirements

Atualizar `requirements.txt` somente se alguma dependência nova for realmente necessária.

Não adicionar bibliotecas sem necessidade.

## Critérios de conclusão

Considerar concluído quando:

* tabela `mercenary_classes` existir;
* tabela `mercenaries` existir;
* classes iniciais estiverem disponíveis;
* tela `/mercenaries` funcionar;
* usuário autenticado conseguir recrutar mercenário;
* recrutamento descontar 50 de ouro;
* mercenário for criado com `guild_id` correto;
* mercenário iniciar com `level = 1`;
* mercenário iniciar com `xp = 0`;
* mercenário iniciar com `status = available`;
* mercenário iniciar com `rarity = common`;
* atributos forem preenchidos com base na classe;
* dashboard exibir resumo de mercenários;
* outro usuário não enxergar mercenários da primeira guilda;
* migration Alembic estiver criada e aplicada;
* aplicação continuar rodando com `uvicorn app.main:app --reload`.
