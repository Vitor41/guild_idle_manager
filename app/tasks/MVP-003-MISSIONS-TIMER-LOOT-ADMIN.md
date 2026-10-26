# MVP-003 - Missions, Timer, Loot Claim and Admin

## Contexto

O MVP-000, MVP-001 e MVP-002 já foram validados.

A aplicação já possui:

* bootstrap local;
* autenticação;
* sessão;
* usuário logado;
* guilda;
* recursos iniciais;
* dashboard;
* mercenários;
* classes de mercenários;
* recrutamento;
* isolamento multi-tenant por usuário/guilda.

Agora o projeto precisa implementar o primeiro loop jogável completo:

```text
mercenário disponível -> iniciar missão -> aguardar timer -> receber loot -> ganhar ouro/XP -> mercenário disponível novamente
```

Também será criado um acesso administrativo simples para configurar missões, começando pela duração.

## Objetivo

Implementar missões básicas com timer, recebimento manual de loot e painel admin inicial para configuração da duração das missões.

O usuário deve conseguir iniciar uma missão, acompanhar a contagem regressiva e receber loot quando o tempo terminar.

O cálculo do resultado e do loot deve acontecer apenas quando o usuário clicar em "Receber Loot".

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/03-MULTI-TENANCY.md`
* `docs/04-GAME-LOOP.md`
* `docs/05-DATABASE-MODEL.md`
* `tasks/MVP-003-MISSIONS-TIMER-LOOT-ADMIN.md`

Consultar também o código atual para manter o padrão já implementado em:

* models;
* repositories;
* services;
* routes;
* templates;
* migrations;
* autenticação;
* guilda atual;
* mercenários;
* dashboard.

## Escopo

Implementar:

* role/admin simples no usuário;
* proteção de rotas admin;
* painel admin básico;
* listagem admin de missões globais;
* edição da duração das missões;
* tabela global de templates de missão;
* tabela de execuções de missão por guilda;
* tabela de membros da missão;
* seed inicial de missões;
* tela de missões para o jogador;
* início de missão com mercenário disponível;
* timer regressivo na tela;
* botão "Receber Loot" desabilitado até o tempo terminar;
* validação backend para impedir coleta antecipada;
* cálculo básico de sucesso/falha;
* recompensa básica em ouro;
* XP básico para mercenários;
* liberação dos mercenários após receber loot;
* aviso de missões concluídas aguardando coleta;
* dashboard atualizado com resumo de missões.

## Fora do escopo

Não implementar nesta task:

* dungeons;
* bosses;
* expedições raras;
* itens reais;
* inventário;
* equipamentos;
* level up completo;
* lesões;
* morte permanente;
* sinergia de classes;
* party complexa;
* ranking;
* notificações push;
* e-mail;
* websocket;
* worker;
* scheduler;
* Celery;
* Redis;
* monetização;
* painel admin completo.

## Role admin

Adicionar controle simples de admin.

Sugestão:

Adicionar campo em `users`:

```text
is_admin boolean default false
```

Rotas admin devem exigir:

```text
usuário autenticado
is_admin = true
```

Se usuário não admin tentar acessar admin, redirecionar ou retornar 403.

## Como definir usuário admin localmente

Para o MVP, é aceitável definir o admin via banco.

Após a migration, o usuário poderá rodar manualmente:

```sql
UPDATE users
SET is_admin = true
WHERE username = 'vitao';
```

Não criar tela para promover admin nesta task.

Não criar gestão completa de usuários.

## Rotas admin esperadas

Criar uma área admin simples.

Rotas sugeridas:

```text
GET /admin
GET /admin/missions
GET /admin/missions/{mission_template_id}/edit
POST /admin/missions/{mission_template_id}/edit
```

O painel `/admin` pode exibir links simples.

A tela `/admin/missions` deve listar templates globais de missão.

A edição deve permitir alterar, no mínimo:

```text
duration_seconds
```

Pode permitir também editar campos simples se for produtivo:

```text
name
description
base_gold_reward
base_xp_reward
base_success_chance
is_active
```

Mas o foco obrigatório é `duration_seconds`.

## Regra sobre alteração de duração

Alterar duração no admin deve afetar apenas novas execuções de missão.

Não recalcular `ends_at` de missões já iniciadas.

Motivo:

A execução da missão deve guardar seu próprio `started_at` e `ends_at`.

## Tabela mission_templates

Tabela global.

Representa as missões disponíveis no jogo.

Não deve ter `user_id`.

Não deve ter `guild_id`.

Campos mínimos:

```text
id
name
description
duration_seconds
base_gold_reward
base_xp_reward
base_success_chance
is_active
created_at
updated_at
```

Missões iniciais sugeridas:

### Caçar lobos

```text
name = Caçar lobos
description = Elimine lobos que ameaçam as estradas próximas.
duration_seconds = 300
base_gold_reward = 25
base_xp_reward = 10
base_success_chance = 80
is_active = true
```

### Patrulhar estrada

```text
name = Patrulhar estrada
description = Vigie a rota comercial e afaste pequenas ameaças.
duration_seconds = 600
base_gold_reward = 40
base_xp_reward = 15
base_success_chance = 75
is_active = true
```

### Escoltar comerciante

```text
name = Escoltar comerciante
description = Proteja um comerciante durante uma viagem curta.
duration_seconds = 900
base_gold_reward = 60
base_xp_reward = 20
base_success_chance = 70
is_active = true
```

## Tabela mission_runs

Tabela por guilda.

Representa uma execução de missão iniciada por uma guilda.

Deve ter `guild_id`.

Campos mínimos:

```text
id
guild_id
mission_template_id
status
started_at
ends_at
resolved_at
success
gold_reward
xp_reward
created_at
updated_at
```

Regras:

* `guild_id` referencia `guilds.id`;
* `mission_template_id` referencia `mission_templates.id`;
* `status` inicia como `in_progress`;
* `started_at` deve ser o horário de início;
* `ends_at` deve ser calculado no início com base em `duration_seconds`;
* `resolved_at` fica vazio até o usuário receber loot;
* `success` fica vazio até o usuário receber loot;
* `gold_reward` e `xp_reward` podem ser preenchidos no final.

Status possíveis:

```text
in_progress
completed
failed
```

## Tabela mission_run_members

Representa os mercenários enviados em uma execução de missão.

Campos mínimos:

```text
id
mission_run_id
mercenary_id
created_at
```

Regras:

* `mission_run_id` referencia `mission_runs.id`;
* `mercenary_id` referencia `mercenaries.id`;
* a validação de posse deve garantir que o mercenário pertence à mesma guilda da missão;
* no MVP, permitir iniciar missão com 1 mercenário;
* deixar a estrutura preparada para múltiplos mercenários no futuro, se possível.

## Tela de missões do jogador

Rota sugerida:

```text
GET /missions
```

Regras:

* apenas usuário autenticado pode acessar;
* se usuário não tiver guilda, redirecionar para `/guild/create`;
* listar missões ativas;
* listar mercenários disponíveis;
* listar missões em andamento;
* listar missões vencidas aguardando loot;
* listar histórico simples de missões finalizadas, se for simples.

Informações mínimas das missões disponíveis:

```text
nome
descrição
duração
recompensa base em ouro
XP base
chance de sucesso base
botão/form para iniciar
```

## Iniciar missão

Rota sugerida:

```text
POST /missions/start
```

Campos do formulário:

```text
mission_template_id
mercenary_id
```

Regras:

* usuário precisa estar autenticado;
* usuário precisa ter guilda;
* `mission_template_id` precisa existir e estar ativo;
* `mercenary_id` precisa pertencer à guilda do usuário logado;
* mercenário precisa estar com `status = available`;
* criar `mission_run`;
* criar `mission_run_member`;
* atualizar mercenário para `status = busy`;
* calcular `ends_at` usando `duration_seconds` atual do template;
* redirecionar para `/missions`.

Não aceitar `guild_id` no formulário.

## Timer

Na tela de missões, para cada missão em andamento, exibir:

```text
Tempo restante: MM:SS
```

O timer deve ser atualizado em tela via JavaScript simples.

Enquanto a missão não terminou:

```text
botão Receber Loot desabilitado
```

Quando o timer chegar a zero:

```text
botão Receber Loot habilitado
```

Opcionalmente, ao timer chegar a zero, a página pode executar refresh para atualizar o estado visual.

Não usar websocket.

Não usar processo em background.

## Receber Loot

Rota sugerida:

```text
POST /missions/{mission_run_id}/claim
```

Regras:

* usuário precisa estar autenticado;
* buscar a missão por `mission_run_id` e `guild_id` da guilda do usuário logado;
* se não encontrar, retornar erro genérico;
* missão precisa estar com `status = in_progress`;
* validar no backend se `now >= ends_at`;
* se ainda não terminou, impedir coleta;
* calcular sucesso/falha;
* calcular recompensa;
* atualizar recursos da guilda;
* atualizar XP dos mercenários;
* liberar mercenários para `available`;
* atualizar `resolved_at`;
* atualizar `status` para `completed` ou `failed`;
* redirecionar para `/missions` com mensagem de resultado.

Não confiar no frontend para definir se a missão terminou.

## Cálculo de sucesso

Usar cálculo simples no MVP.

Sugestão:

```text
success_chance = mission_template.base_success_chance + floor(mercenary.power / 5)
```

Limitar chance entre:

```text
5 e 95
```

Exemplo:

```text
base_success_chance = 80
mercenary.power = 8
bonus = floor(8 / 5) = 1
success_chance = 81
```

Usar número aleatório de 1 a 100.

Se rolagem <= success_chance:

```text
sucesso
```

Caso contrário:

```text
falha
```

## Cálculo de recompensa

Se sucesso:

```text
gold_reward = mission_template.base_gold_reward
xp_reward = mission_template.base_xp_reward
```

Se falha:

```text
gold_reward = 0
xp_reward = floor(mission_template.base_xp_reward * 0.25)
```

No MVP, falha ainda concede XP reduzido.

## XP

Adicionar XP ao mercenário participante.

Não implementar level up completo nesta task.

Se o XP passar de algum limite, não precisa subir nível ainda.

Level up será task futura.

## Recursos

Ao receber loot com sucesso, adicionar ouro à guilda:

```text
guild_resources.gold += gold_reward
```

Não adicionar madeira, minério ou cristais nesta task.

## Notificação/Aviso de missão vencida

Quando o usuário acessar dashboard ou missões, se houver missão com:

```text
status = in_progress
ends_at <= now
```

Exibir aviso simples:

```text
Você possui missões concluídas aguardando coleta.
```

Não implementar push notification.

Não implementar notificação por e-mail.

## Dashboard

Atualizar dashboard com resumo simples:

```text
Missões em andamento
Missões aguardando loot
Missões concluídas
```

Adicionar link para:

```text
Ver missões
```

Se houver missão aguardando loot, destacar aviso simples.

## Menu/Header

Adicionar link para:

```text
Mercenários
Missões
```

Se usuário for admin, exibir também:

```text
Admin
```

## Admin - Missões

Tela admin deve permitir editar a duração das missões.

Campos obrigatórios na edição:

```text
duration_seconds
```

Validações:

* duração obrigatória;
* duração deve ser maior que zero;
* duração deve ser número inteiro;
* se valor inválido, exibir mensagem de erro.

Campos opcionais que podem ser editáveis se simples:

```text
name
description
base_gold_reward
base_xp_reward
base_success_chance
is_active
```

Se implementar edição desses campos, validar:

```text
base_gold_reward >= 0
base_xp_reward >= 0
base_success_chance entre 1 e 100
```

## Seed de missões

Garantir que as missões iniciais existam.

O seed deve ser idempotente:

* se a missão já existir, não duplicar;
* se não existir, criar.

Pode ser por migration, script ou startup, seguindo o padrão já usado para classes de mercenários.

## Multi-tenancy obrigatório

Templates de missão são globais.

Execuções de missão pertencem à guilda.

Toda consulta de `mission_runs` deve filtrar por `guild_id`.

Errado:

```sql
SELECT * FROM mission_runs WHERE id = :mission_run_id;
```

Correto:

```sql
SELECT *
FROM mission_runs
WHERE id = :mission_run_id
AND guild_id = :current_guild_id;
```

Mercenário enviado deve ser validado por `guild_id`.

Não aceitar `guild_id` no frontend.

## Organização esperada

Manter o padrão atual do projeto.

Sugestão de arquivos possíveis:

```text
app/models/mission.py

app/repositories/mission_repository.py
app/repositories/admin_repository.py

app/services/mission_service.py
app/services/admin_service.py

app/routes/mission_routes.py
app/routes/admin_routes.py

app/templates/missions/index.html
app/templates/admin/index.html
app/templates/admin/missions.html
app/templates/admin/edit_mission.html

app/static/js/mission_timers.js
```

A estrutura pode ser ajustada conforme o padrão atual, mas manter separação de responsabilidade.

## Migration

Criar migration Alembic para:

```text
users.is_admin
mission_templates
mission_runs
mission_run_members
```

Aplicar com:

```bash
alembic upgrade head
```

## Como testar manualmente

Após implementar:

1. Rodar migration.
2. Promover usuário local para admin:

```sql
UPDATE users
SET is_admin = true
WHERE username = 'vitao';
```

3. Logar com usuário admin.
4. Acessar `/admin`.
5. Acessar admin de missões.
6. Alterar duração de "Caçar lobos" para 30 segundos.
7. Ir para `/missions`.
8. Escolher mercenário disponível.
9. Iniciar missão "Caçar lobos".
10. Ver mercenário ficar ocupado.
11. Ver timer regressivo.
12. Confirmar botão "Receber Loot" desabilitado antes do fim.
13. Aguardar timer.
14. Confirmar botão habilitado ou página atualizada.
15. Clicar em "Receber Loot".
16. Ver resultado da missão.
17. Ver ouro/XP atualizado.
18. Ver mercenário disponível novamente.
19. Logar com outro usuário e confirmar que não enxerga missões da primeira guilda.

## Critérios de conclusão

Considerar concluído quando:

* campo `is_admin` existir em `users`;
* rotas admin estiverem protegidas por `is_admin`;
* admin conseguir editar duração de missões;
* tabela `mission_templates` existir;
* tabela `mission_runs` existir;
* tabela `mission_run_members` existir;
* missões iniciais existirem;
* tela `/missions` listar missões disponíveis;
* usuário conseguir iniciar missão com mercenário disponível;
* mercenário ficar `busy` ao iniciar missão;
* timer aparecer na tela;
* botão "Receber Loot" ficar bloqueado antes do fim;
* backend impedir coleta antecipada;
* botão liberar após o tempo;
* loot ser calculado ao clicar em receber;
* sucesso adicionar ouro e XP;
* falha adicionar apenas XP reduzido;
* mercenário voltar para `available`;
* dashboard exibir resumo de missões;
* usuário ver aviso quando houver missão aguardando loot;
* outro usuário não acessar missões da primeira guilda;
* aplicação continuar rodando com `uvicorn app.main:app --reload`.
