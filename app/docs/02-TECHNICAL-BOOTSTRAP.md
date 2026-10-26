# 02 - Technical Bootstrap

## Objetivo

Definir a base técnica inicial do projeto.

Este projeto deve começar em ambiente local.

O Codex deve criar a estrutura do projeto, instalar dependências, configurar ambiente virtual, configurar banco local e preparar a aplicação para desenvolvimento.

## Ambiente inicial

O projeto será executado inicialmente em ambiente local. Utilizando VENV do Phyton para subir a aplicação.

Deploy em Oracle Cloud Free poderá acontecer no futuro, mas não deve ser considerado no MVP-000.

## Stack obrigatória

Usar:

* Python
* FastAPI
* Jinja2
* SQLAlchemy
* Alembic
* PostgreSQL
* Uvicorn
* python-dotenv
* passlib ou bcrypt para hash de senha
* itsdangerous ou mecanismo equivalente para sessão segura
* HTML
* CSS
* JavaScript simples

## Stack não desejada no início

Não usar no MVP inicial:

* React
* Vue
* Angular
* Next.js
* Celery
* Redis
* Docker obrigatório
* Kubernetes
* filas
* workers
* scheduler
* microserviços
* banco NoSQL
* dependências pesadas sem necessidade

## Estrutura esperada

Criar uma estrutura semelhante a:

```text
app/
  main.py

  core/
    config.py
    security.py

  database/
    connection.py

  models/
    __init__.py

  repositories/
    __init__.py

  services/
    __init__.py

  routes/
    __init__.py

  templates/
    base.html

  static/
    css/
      main.css
    js/
      main.js

alembic/
docs/
tasks/
.env.example
.gitignore
requirements.txt
README.md
```

A estrutura pode ser ajustada se houver justificativa técnica, mas deve manter separação clara entre:

* models;
* routes;
* services;
* repositories;
* templates;
* static;
* database;
* config.

## Regras de organização

Routes devem lidar com entrada HTTP, validações simples e renderização ou redirecionamento.

Services devem concentrar regras de negócio.

Repositories devem concentrar acesso ao banco de dados.

Models devem representar tabelas SQLAlchemy.

Templates devem conter HTML/Jinja2.

Static deve conter CSS e JavaScript.

Configurações sensíveis devem vir de `.env`.

Não hardcodar credenciais no código.

## Banco de dados local

Usar PostgreSQL local.

Criar configuração por variável de ambiente.

Exemplo esperado no `.env.example`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/guild_idle_manager
SECRET_KEY=change-this-secret
APP_ENV=local
DEBUG=true
```

O nome do banco pode ser ajustado, mas deve ser específico do projeto.

## Alembic

Configurar Alembic desde o início.

O projeto deve permitir:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

A configuração do Alembic deve apontar para os models do projeto.

Não reaproveitar migrations de outros projetos.

## Execução local

O projeto deve rodar localmente com comando semelhante a:

```bash
uvicorn app.main:app --reload
```

A aplicação deve abrir no navegador e renderizar uma página inicial simples.

## Página inicial no bootstrap

No MVP-000, criar apenas uma página inicial simples para validar que o projeto está funcionando.

Essa página pode conter:

* nome provisório do projeto;
* status da aplicação;
* link futuro para login;
* indicação de ambiente local.

Não implementar o jogo completo no bootstrap.

## Autenticação

A autenticação será implementada em task própria.

No bootstrap, preparar estrutura para autenticação, mas não implementar todo o fluxo se a task atual for apenas MVP-000.

## Multi-tenancy

O projeto deve ser preparado para multi-tenancy por usuário/guilda.

A implementação detalhada estará em documento próprio.

Desde o início, evitar decisões que dificultem isolamento de dados por usuário.

## Dependências

Criar `requirements.txt` com as dependências necessárias para o bootstrap.

Não instalar dependências sem uso claro.

## Gitignore

Criar `.gitignore` incluindo, no mínimo:

```text
venv/
__pycache__/
*.pyc
.env
.DS_Store
.idea/
.vscode/
*.log
```

## README inicial

Criar README com:

* descrição curta do projeto;
* stack;
* como criar venv;
* como instalar dependências;
* como configurar `.env`;
* como rodar localmente;
* como rodar migrations.

## Critério de conclusão do bootstrap

O bootstrap estará concluído quando:

* ambiente virtual estiver documentado;
* dependências estiverem em `requirements.txt`;
* estrutura base estiver criada;
* FastAPI estiver rodando;
* Jinja2 estiver configurado;
* static estiver configurado;
* conexão com PostgreSQL estiver preparada;
* Alembic estiver configurado;
* `.env.example` estiver criado;
* README inicial estiver criado;
* página inicial simples estiver acessível.
