# MVP-001 - Auth and Guild Foundation

## Contexto

O bootstrap local do projeto já foi validado.

A aplicação FastAPI roda localmente, conecta no PostgreSQL, possui Alembic configurado e renderiza uma página inicial simples.

Agora o projeto precisa receber a primeira fundação real de produto:

* usuário;
* autenticação;
* sessão;
* criação da guilda;
* recursos iniciais;
* dashboard autenticado básico;
* isolamento inicial por usuário/guilda.

Essa task junta autenticação e fundação de guilda para validar o fluxo multi-tenant desde o início.

## Objetivo

Permitir que um usuário crie conta, faça login, crie sua guilda e acesse um dashboard básico da própria guilda.

Um segundo usuário deve começar zerado, sem acessar nenhum dado do primeiro usuário.

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/03-MULTI-TENANCY.md`
* `docs/05-DATABASE-MODEL.md`
* `tasks/MVP-001-AUTH-AND-GUILD-FOUNDATION.md`

Consultar também o código atual do bootstrap para manter o padrão já implementado.

Não ler documentos de missões, mercenários, recompensas, balanceamento ou game loop nesta task.

## Escopo

Implementar:

* model `User`;
* model `Guild`;
* model `GuildResources`;
* migration Alembic;
* cadastro de usuário;
* login;
* logout;
* sessão autenticada;
* helper/dependency para usuário atual;
* helper/dependency para guilda atual;
* fluxo de primeiro acesso sem guilda;
* criação da guilda;
* criação dos recursos iniciais da guilda;
* dashboard básico autenticado;
* proteção de rotas autenticadas;
* header simples com usuário/guilda/logout;
* mensagens simples de erro e validação.

## Fora do escopo

Não implementar nesta task:

* mercenários;
* missões;
* cálculo idle;
* recompensas;
* level up;
* inventário;
* itens;
* construções;
* ranking;
* admin;
* recuperação de senha;
* confirmação de e-mail;
* OAuth;
* multiplayer;
* monetização;
* APIs públicas;
* React/Vue/Angular;
* worker/scheduler.

## Fluxo esperado

### Usuário não autenticado

Ao acessar `/`, se não estiver autenticado, o sistema deve exibir uma tela inicial simples com opções de login e cadastro, ou redirecionar para `/login`.

A decisão visual fica a critério da implementação, desde que o fluxo seja claro.

### Cadastro

Rota esperada:

```text
GET /register
POST /register
```

Campos mínimos:

```text
username
email opcional
password
confirm_password
```

Regras:

* `username` obrigatório;
* `password` obrigatório;
* `confirm_password` obrigatório;
* senha e confirmação devem ser iguais;
* username não pode duplicar;
* email, se informado, não pode duplicar;
* salvar apenas `password_hash`;
* após cadastro, redirecionar para login ou autenticar automaticamente.

Preferência para MVP:

```text
após cadastro, redirecionar para /login
```

### Login

Rota esperada:

```text
GET /login
POST /login
```

Campos mínimos:

```text
username
password
```

Regras:

* validar usuário e senha;
* se inválido, exibir mensagem genérica;
* se válido, salvar `user_id` na sessão;
* após login, verificar se o usuário possui guilda.

Fluxo após login:

```text
se usuário não tem guilda -> /guild/create
se usuário tem guilda -> /dashboard
```

### Logout

Rota esperada:

```text
POST /logout
```

ou:

```text
GET /logout
```

Para MVP, `GET /logout` é aceitável pela simplicidade.

Regras:

* limpar sessão;
* redirecionar para login ou home pública.

### Criação da guilda

Rota esperada:

```text
GET /guild/create
POST /guild/create
```

Regras:

* apenas usuário autenticado pode acessar;
* se usuário já tiver guilda, redirecionar para `/dashboard`;
* nome da guilda é obrigatório;
* criar registro em `guilds`;
* criar registro em `guild_resources`;
* cada usuário pode ter apenas uma guilda no MVP;
* após criar guilda, redirecionar para `/dashboard`.

Valores iniciais:

```text
guild.level = 1
guild.reputation = 0
guild_resources.gold = 100
guild_resources.wood = 0
guild_resources.ore = 0
guild_resources.crystals = 0
```

### Dashboard

Rota esperada:

```text
GET /dashboard
```

Regras:

* apenas usuário autenticado pode acessar;
* se usuário não tiver guilda, redirecionar para `/guild/create`;
* exibir dados básicos da guilda do usuário logado;
* exibir recursos iniciais da guilda;
* não carregar dados de nenhuma outra guilda.

Informações mínimas na tela:

```text
nome da guilda
nível da guilda
reputação
ouro
madeira
minério
cristais
username logado
ação de logout
```

Também exibir placeholders simples para funcionalidades futuras:

```text
Mercenários: em breve
Missões: em breve
Expedições idle: em breve
```

## Multi-tenancy obrigatório

A guilda deve sempre ser buscada pelo usuário logado.

Não aceitar `guild_id` vindo do frontend.

Não criar rota que permita acessar guilda por ID livre nesta task.

Errado:

```text
/dashboard?guild_id=1
```

Correto:

```text
/dashboard
```

O backend deve descobrir a guilda usando o `user_id` da sessão.

## Segurança de senha

Nunca salvar senha em texto puro.

Usar `bcrypt` ou mecanismo equivalente para hash e verificação de senha.

O código deve ter funções centralizadas, como:

```python
hash_password(password)
verify_password(plain_password, password_hash)
```

Essas funções devem ficar em local adequado, como:

```text
app/core/security.py
```

## Sessão

Usar sessão simples via middleware adequado do FastAPI/Starlette.

A `SECRET_KEY` deve vir do `.env`.

A sessão deve armazenar apenas:

```text
user_id
```

Não armazenar dados sensíveis.

## Organização esperada

Manter separação entre:

```text
models
routes
services
repositories
templates
static
core
database
```

Sugestão de arquivos possíveis:

```text
app/models/user.py
app/models/guild.py

app/repositories/user_repository.py
app/repositories/guild_repository.py

app/services/auth_service.py
app/services/guild_service.py

app/routes/auth_routes.py
app/routes/guild_routes.py
app/routes/dashboard_routes.py

app/templates/auth/login.html
app/templates/auth/register.html
app/templates/guild/create.html
app/templates/dashboard.html
```

A estrutura pode ser ajustada se o bootstrap já tiver outro padrão, mas a separação de responsabilidade deve ser preservada.

## Repositories

Repositories devem concentrar acesso ao banco.

Exemplos conceituais:

```python
get_user_by_username(db, username)
get_user_by_email(db, email)
create_user(db, ...)
get_guild_by_user_id(db, user_id)
create_guild_for_user(db, user_id, name)
get_resources_by_guild_id(db, guild_id)
```

## Services

Services devem concentrar regra de negócio.

Exemplos conceituais:

```python
register_user(db, username, email, password)
authenticate_user(db, username, password)
create_initial_guild(db, user_id, guild_name)
get_current_guild_context(db, user_id)
```

## Routes

Routes devem lidar com:

* request;
* forms;
* session;
* redirects;
* renderização de templates;
* chamadas para services.

Evitar regra de negócio pesada diretamente em routes.

## Templates

Criar telas simples, limpas e funcionais.

Não precisa visual final.

Reaproveitar `base.html`.

Criar feedbacks simples para erros.

Exemplos:

```text
Usuário ou senha inválidos.
Nome da guilda é obrigatório.
Este usuário já existe.
Este e-mail já está em uso.
```

## Home

A rota `/` pode seguir uma das opções:

Opção A:

* se usuário não logado, mostrar landing simples com links para login/cadastro;
* se usuário logado com guilda, redirecionar para `/dashboard`;
* se usuário logado sem guilda, redirecionar para `/guild/create`.

Opção B:

* redirecionar usuário não logado diretamente para `/login`.

Escolher a opção mais coerente com o código atual.

## Migration

Criar migration Alembic para:

```text
users
guilds
guild_resources
```

Depois aplicar:

```bash
alembic upgrade head
```

A migration deve ser gerada corretamente por autogenerate ou criada manualmente se necessário.

## Requirements

Se for necessário adicionar dependência para senha ou sessão, atualizar `requirements.txt`.

Não adicionar dependências sem necessidade.

## Validação manual esperada

Após implementar, deve ser possível:

1. Acessar `/register`.
2. Criar usuário `VITAO`.
3. Fazer login com `VITAO`.
4. Ser direcionado para criação da guilda.
5. Criar uma guilda.
6. Acessar `/dashboard`.
7. Ver dados da guilda e recursos iniciais.
8. Fazer logout.
9. Criar usuário `VITAO02`.
10. Logar com `VITAO02`.
11. Ver que `VITAO02` não tem guilda.
12. Criar guilda própria para `VITAO02`.
13. Confirmar que `VITAO02` não enxerga dados de `VITAO`.

## Critérios de conclusão

Considerar concluído quando:

* cadastro funcionar;
* login funcionar;
* logout funcionar;
* senha for salva como hash;
* sessão armazenar usuário logado;
* rotas protegidas bloquearem usuário anônimo;
* usuário sem guilda for enviado para criação de guilda;
* usuário com guilda for enviado para dashboard;
* guilda for criada vinculada ao usuário;
* recursos iniciais forem criados vinculados à guilda;
* dashboard exibir apenas dados da guilda do usuário logado;
* migration Alembic estiver criada e aplicada;
* `requirements.txt` estiver atualizado;
* aplicação rodar com `uvicorn app.main:app --reload`.
