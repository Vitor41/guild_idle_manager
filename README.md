# Guild Idle Manager

Projeto web idle/manager de guilda e mercenarios. O estado atual possui bootstrap local, cadastro, login, sessao autenticada, criacao da primeira guilda, recursos iniciais, mercenarios, missoes com timer, coleta manual de loot, progressao basica, inventario e painel admin para configurar missoes, itens e drops.

## Stack

- Python
- FastAPI
- Uvicorn
- Jinja2
- SQLAlchemy
- Alembic
- PostgreSQL
- python-dotenv
- HTML, CSS e JavaScript simples

## Pre-requisitos

- Python 3.11 ou superior
- PostgreSQL local

## Criar ambiente virtual

```bash
python -m venv venv
```

Ativar no Windows:

```bash
venv\Scripts\activate
```

Ativar no Linux/Mac:

```bash
source venv/bin/activate
```

## Instalar dependencias

```bash
pip install -r requirements.txt
```

## Configurar ambiente

Copie o arquivo de exemplo:

```bash
copy .env.example .env
```

No Linux/Mac:

```bash
cp .env.example .env
```

Ajuste `DATABASE_URL` e `SECRET_KEY` no `.env` conforme seu ambiente local.

## Criar banco PostgreSQL local

No PostgreSQL, crie o banco usado pelo projeto:

```sql
CREATE DATABASE guild_idle_manager;
```

## Rodar migrations

O Alembic esta configurado para importar o metadata dos models do projeto. Para gerar novas migrations apos alterar models:

```bash
alembic revision --autogenerate -m "initial schema"
```

Aplique migrations com:

```bash
alembic upgrade head
```

## Iniciar servidor local

```bash
uvicorn app.main:app --reload
```

## Conteúdo massivo

O pacote de conteúdo dos MVPs 027 a 034 é aplicado de forma idempotente na inicialização. Para executar e validar manualmente:

```powershell
.\.venv\Scripts\python.exe scripts\seed_massive_content.py
```

Administradores também podem consultar a cobertura em `/admin/content-report`.

## Sessão e progresso offline

- A sessão é encerrada após 5 horas, mesmo com atividade.
- Uma hora sem interação encerra a sessão por inatividade.
- Ouro offline só é calculado entre o logout/expiração e o próximo login.
- Os tempos podem ser ajustados com `SESSION_GLOBAL_SECONDS` e `SESSION_IDLE_SECONDS`.

Acesse:

```text
http://127.0.0.1:8000
```

A rota `/` deve renderizar uma pagina simples informando que o Guild Idle Manager esta em execucao local.

## Fluxo atual

- `/register`: cria conta de usuario.
- `/login`: autentica usuario e inicia sessao.
- `/guild/create`: cria a primeira guilda do usuario autenticado.
- `/dashboard`: exibe apenas a guilda e os recursos do usuario logado.
- `/mercenaries`: lista mercenarios da guilda e permite recrutar.
- `/missions`: lista missoes, permite iniciar com mercenario disponivel e receber loot quando o timer termina.
- `/inventory`: lista itens acumulados pela guilda.
- `/admin`: painel admin para configurar missoes, itens e drops.
- `/logout`: limpa a sessao.

## Promover admin localmente

Para permitir acesso ao painel admin:

```sql
UPDATE users
SET is_admin = true
WHERE username = 'vitao';
```
