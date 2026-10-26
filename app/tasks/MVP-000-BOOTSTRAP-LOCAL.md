# MVP-000 - Bootstrap Local

## Contexto

Este é o primeiro desenvolvimento do projeto.

A raiz do projeto estará vazia ou praticamente vazia.

O objetivo é criar uma aplicação web local usando Phyton, FastAPI, Jinja2, SQLAlchemy, Alembic e PostgreSQL.

O projeto será desenvolvido primeiro em ambiente local. Deploy em Oracle Cloud Free será avaliado futuramente e não faz parte desta task.

## Objetivo

Criar a estrutura inicial do projeto, instalar dependências, configurar ambiente local e deixar uma aplicação FastAPI funcional renderizando uma página inicial simples.

Não implementar ainda o jogo completo.

Não implementar ainda autenticação completa.

Não implementar ainda missões, mercenários, recompensas ou dashboard real.

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/02-TECHNICAL-BOOTSTRAP.md`
* `docs/03-MULTI-TENANCY.md`

Não ler documentos de balanceamento, missões, mercenários ou game loop neste momento, salvo se forem criados no futuro e a task for alterada.

## Escopo da task

Criar:

* ambiente virtual Python;
* arquivo `requirements.txt`;
* arquivo `.env.example`;
* arquivo `.gitignore`;
* estrutura de pastas do projeto;
* aplicação FastAPI mínima;
* configuração Jinja2;
* configuração de arquivos estáticos;
* configuração SQLAlchemy;
* configuração inicial do Alembic;
* README com instruções locais;
* página inicial simples.

## Stack obrigatória

Usar:

* Python
* FastAPI
* Uvicorn
* Jinja2
* SQLAlchemy
* Alembic
* PostgreSQL
* psycopg2 ou psycopg2-binary
* python-dotenv
* passlib ou bcrypt, se preparar estrutura de segurança
* HTML
* CSS
* JavaScript simples

## Fora do escopo

Não implementar nesta task:

* cadastro;
* login;
* logout;
* sessão real;
* criação de guilda;
* mercenários;
* missões;
* cálculo idle;
* recompensas;
* ranking;
* painel admin;
* deploy;
* Docker;
* Celery;
* Redis;
* React;
* Vue;
* Angular;
* worker;
* scheduler.

## Estrutura esperada

Criar estrutura semelhante a:

```text
app/
  __init__.py
  main.py

  core/
    __init__.py
    config.py
    security.py

  database/
    __init__.py
    connection.py

  models/
    __init__.py

  repositories/
    __init__.py

  services/
    __init__.py

  routes/
    __init__.py
    home_routes.py

  templates/
    base.html
    home.html

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

A estrutura pode ser ajustada se houver motivo técnico, mas deve manter separação clara entre:

* `routes`;
* `services`;
* `repositories`;
* `models`;
* `templates`;
* `static`;
* `database`;
* `core`.

## Configuração de ambiente

Criar `.env.example` com:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/guild_idle_manager
SECRET_KEY=change-this-secret
APP_ENV=local
DEBUG=true
```

Não criar `.env` com credenciais reais.

O usuário poderá copiar `.env.example` para `.env` manualmente.

## Banco local

Preparar o projeto para conectar em PostgreSQL local.

Não é obrigatório criar o banco automaticamente via código.

O README deve instruir o usuário a criar o banco local, por exemplo:

```sql
CREATE DATABASE guild_idle_manager;
```

## SQLAlchemy

Criar arquivo de conexão com:

* engine;
* SessionLocal;
* Base;
* dependency para obter sessão do banco, se aplicável.

A estrutura deve permitir models futuros usando:

```python
from app.database.connection import Base
```

Ou padrão equivalente definido pelo próprio projeto.

Manter consistência.

## Alembic

Configurar Alembic para o projeto.

A configuração deve permitir gerar migrations futuras por autogenerate.

O Alembic deve importar o metadata dos models.

Como ainda não há models de domínio nesta task, pode não haver migration útil neste momento.

Mesmo assim, a estrutura deve estar preparada.

## FastAPI

Criar aplicação em `app/main.py`.

A aplicação deve:

* inicializar FastAPI;
* configurar templates;
* configurar static files;
* registrar rota inicial;
* renderizar página home.

## Rota inicial

Criar rota:

```text
GET /
```

Essa rota deve renderizar `home.html`.

A página deve mostrar uma mensagem simples, como:

```text
Guild Idle Manager
Aplicação local em execução.
```

Também pode exibir:

* stack usada;
* status "local";
* aviso de que o jogo ainda está em bootstrap.

## Templates

Criar `base.html` com layout base.

Criar `home.html` estendendo `base.html`.

Não criar visual complexo agora.

O layout deve ser limpo, responsivo básico e fácil de evoluir.

## Static

Criar `main.css` com estilos mínimos.

Criar `main.js` vazio ou com comentário simples.

Não usar bibliotecas externas pesadas.

## README

Criar README contendo:

* descrição curta do projeto;
* stack;
* pré-requisitos;
* como criar ambiente virtual;
* como ativar ambiente virtual;
* como instalar dependências;
* como configurar `.env`;
* como criar banco local;
* como rodar Alembic;
* como iniciar servidor local;
* URL local para acessar a aplicação.

Exemplo de comandos esperados:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/Mac:

```bash
source venv/bin/activate
```

Instalação:

```bash
pip install -r requirements.txt
```

Execução:

```bash
uvicorn app.main:app --reload
```

## Gitignore

Criar `.gitignore` incluindo:

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

Pode incluir outros padrões úteis.

## Validações esperadas

Após concluir, deve ser possível:

1. Criar e ativar venv.
2. Instalar dependências.
3. Configurar `.env`.
4. Criar banco PostgreSQL local.
5. Rodar aplicação com Uvicorn.
6. Acessar a página inicial no navegador.
7. Ter Alembic configurado para migrations futuras.

## Regras de implementação

* Não copiar código de domínio de outros projetos.
* Não criar regras de negócio do jogo nesta task.
* Não criar tabelas finais sem necessidade.
* Não criar models de mercenário, missão ou guilda ainda.
* Não criar autenticação real ainda.
* Não introduzir dependências sem uso claro.
* Não usar frontend SPA.
* Não criar estrutura excessivamente complexa.

## Resultado esperado

Ao final da task, o projeto deve estar tecnicamente inicializado e pronto para receber as próximas tasks.

A entrega esperada é uma aplicação FastAPI local, limpa, organizada e preparada para evoluir para autenticação, multi-tenancy e mecânicas de jogo.

## Critério de conclusão

Considerar a task concluída quando:

* `requirements.txt` existir;
* `.env.example` existir;
* `.gitignore` existir;
* `README.md` existir;
* estrutura `app/` existir;
* `app/main.py` inicializar FastAPI;
* templates estiverem funcionando;
* static estiver funcionando;
* conexão com PostgreSQL estiver preparada;
* Alembic estiver configurado;
* rota `/` renderizar página inicial;
* projeto rodar localmente com `uvicorn app.main:app --reload`.
