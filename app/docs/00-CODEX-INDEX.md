# 00 - Codex Index

Este projeto é um jogo web idle/manager de guilda e mercenários.

Leia este arquivo primeiro antes de qualquer desenvolvimento.

## Objetivo deste índice

Orientar o Codex sobre quais documentos ler de acordo com a tarefa atual, evitando leitura desnecessária de arquivos longos.

O Codex deve ler apenas os documentos relevantes para a tarefa em execução.

## Regra principal

Antes de alterar código, entenda:

* qual é o objetivo da tarefa;
* quais arquivos de documentação são relevantes;
* quais partes do sistema podem ser impactadas;
* se a alteração envolve autenticação, multi-tenancy, banco, regra de jogo ou visual.

Não implemente soluções genéricas sem consultar a documentação relevante.

## Quando a tarefa for criar a estrutura inicial do projeto

Leia:

* `docs/01-PRODUCT-CONTEXT.md`
* `docs/02-TECHNICAL-BOOTSTRAP.md`
* `tasks/MVP-000-BOOTSTRAP-LOCAL.md`

Não leia ainda:

* `docs/08-BALANCE-RULES.md`
* tasks de missões, recompensas, dashboard ou mercenários.

Pare de ler quando souber:

* qual stack usar;
* qual estrutura de pastas criar;
* como configurar o ambiente local;
* qual é o escopo exato do bootstrap.

## Quando a tarefa envolver autenticação ou usuário logado

Leia:

* `docs/03-MULTI-TENANCY.md`
* `docs/05-DATABASE-MODEL.md`
* `tasks/MVP-001-AUTH-USERS.md`

Pare de ler quando souber:

* como identificar o usuário logado;
* como criar sessão;
* como buscar a guilda vinculada ao usuário;
* como impedir acesso a dados de outro usuário.

## Quando a tarefa envolver guilda

Leia:

* `docs/03-MULTI-TENANCY.md`
* `docs/05-DATABASE-MODEL.md`
* `tasks/MVP-002-GUILD-CREATION.md`

Pare de ler quando souber:

* como criar a guilda inicial;
* como vincular guilda ao usuário;
* quais dados iniciais a guilda deve receber.

## Quando a tarefa envolver mercenários

Leia:

* `docs/03-MULTI-TENANCY.md`
* `docs/05-DATABASE-MODEL.md`
* `tasks/MVP-003-MERCENARIES.md`

Leia `docs/08-BALANCE-RULES.md` somente se a tarefa envolver atributos, raridade, força, evolução ou cálculo de poder.

## Quando a tarefa envolver missões

Leia:

* `docs/03-MULTI-TENANCY.md`
* `docs/04-GAME-LOOP.md`
* `docs/05-DATABASE-MODEL.md`
* `tasks/MVP-004-MISSIONS.md`

Leia `docs/08-BALANCE-RULES.md` somente se a tarefa envolver chance de sucesso, recompensa, duração, risco ou balanceamento.

## Quando a tarefa envolver cálculo idle

Leia:

* `docs/04-GAME-LOOP.md`
* `docs/05-DATABASE-MODEL.md`
* `docs/08-BALANCE-RULES.md`
* `tasks/MVP-005-IDLE-CALCULATION.md`

Pare de ler quando souber:

* como identificar missões vencidas;
* quando calcular resultado;
* como atualizar status da missão;
* como liberar recompensa;
* como atualizar status dos mercenários.

## Quando a tarefa envolver visual, tela ou layout

Leia:

* `docs/07-UI-UX-STANDARDS.md`
* a task específica relacionada à tela.

Não altere regras de negócio apenas por necessidade visual.

## Quando a tarefa envolver banco de dados

Leia:

* `docs/05-DATABASE-MODEL.md`
* a task específica da funcionalidade.

Se a alteração envolver dados do jogador, leia também:

* `docs/03-MULTI-TENANCY.md`

## Regras para desenvolvimento

* Não criar funcionalidades fora do escopo da task atual.
* Não criar multiplayer em tempo real.
* Não criar worker ou scheduler no MVP inicial.
* Não criar monetização.
* Não criar sistema de pagamento.
* Não criar arte complexa.
* Não copiar regras, nomes ou estrutura de domínio de outros projetos.
* Não usar clubes, jogadores, marcas, escudos ou propriedades licenciadas.
* Não criar dados globais como se fossem dados do usuário.
* Não criar dados do usuário sem vínculo com `user_id` ou `guild_id`.

## Stack prevista

* Python
* FastAPI
* Jinja2
* SQLAlchemy
* Alembic
* PostgreSQL
* HTML
* CSS
* JavaScript simples
* Ambiente local no início
* Deploy futuro opcional em Oracle Cloud Free

## Filosofia do projeto

O jogo deve ser simples, incremental e evolutivo.

O jogador gerencia uma guilda, contrata mercenários, envia grupos para missões, coleta recompensas, evolui personagens e melhora a estrutura da guilda.

O jogo deve funcionar bem de forma assíncrona. O progresso idle deve ser calculado quando o usuário retorna ao jogo, sem necessidade de processamento contínuo em background no MVP.
