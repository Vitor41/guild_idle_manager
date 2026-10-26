# 04 - Game Loop

## Objetivo

Definir o loop principal do jogo e a regra de funcionamento das missões no MVP.

Este documento orienta como o jogo deve funcionar do ponto de vista de experiência, progressão e execução técnica.

## Loop principal

O loop principal do jogador é:

1. Entrar no jogo.
2. Ver status da guilda.
3. Ver mercenários disponíveis.
4. Escolher uma missão.
5. Enviar mercenário para missão.
6. Acompanhar o tempo restante.
7. Receber loot quando a missão terminar.
8. Evoluir recursos/personagens.
9. Iniciar novas missões.

## Papel das missões

Missões são conteúdos básicos e recorrentes.

No MVP, missões servem para:

* ganhar ouro;
* ganhar XP básico para mercenários;
* futuramente ganhar itens básicos;
* manter o jogador em progressão curta e frequente.

Missões não são o conteúdo mais valioso do jogo.

Conteúdos futuros como dungeons, bosses, expedições raras e eventos poderão entregar recompensas mais importantes.

## Missões x Dungeons

### Missões

Missões são atividades simples, de baixo risco e curta/média duração.

Exemplos:

* Caçar lobos;
* Escoltar comerciante;
* Patrulhar estrada;
* Limpar caverna pequena;
* Entregar suprimentos.

Recompensas esperadas:

* pouco ouro;
* XP básico;
* itens básicos futuramente.

### Dungeons

Dungeons ficam fora do MVP atual.

No futuro, dungeons poderão ter:

* maior duração;
* maior dificuldade;
* melhores recompensas;
* itens raros;
* chefes;
* risco maior;
* necessidade de grupo;
* regras especiais.

Não implementar dungeons no MVP-003.

## Regra principal das missões

O cálculo da recompensa deve acontecer por ação do usuário.

Não calcular loot automaticamente no momento em que o tempo terminar.

Fluxo correto:

```text
1. Usuário inicia missão.
2. Sistema grava started_at e ends_at.
3. Mercenário fica ocupado.
4. Tela mostra contagem regressiva.
5. Botão "Receber Loot" fica desabilitado enquanto a missão não venceu.
6. Quando o tempo termina, botão fica disponível.
7. Usuário clica em "Receber Loot".
8. Backend valida se a missão realmente terminou.
9. Backend calcula resultado e recompensa.
10. Backend atualiza recursos, XP e status da missão.
11. Mercenário volta a ficar disponível.
```

## Timer na tela

A tela de missões deve exibir contagem regressiva para missões em andamento.

Enquanto a missão estiver em andamento:

```text
Receber Loot: desabilitado
Tempo restante: 04:32
```

Quando o tempo terminar:

```text
Receber Loot: habilitado
Tempo restante: Concluída
```

Se o usuário estiver logado e com a tela aberta, o frontend pode:

* atualizar o timer a cada segundo;
* habilitar o botão ao chegar em zero;
* opcionalmente executar refresh da página.

Para o MVP, a solução mais simples aceitável é:

* timer em JavaScript;
* ao chegar em zero, habilitar botão ou atualizar a página.

## Validação backend

O frontend nunca deve ser fonte de verdade.

Mesmo que o botão esteja habilitado na tela, o backend deve validar:

```text
now >= mission_run.ends_at
```

Se o usuário tentar receber loot antes da hora, o backend deve impedir.

Mensagem sugerida:

```text
A missão ainda não foi concluída.
```

## Usuário offline

Se o usuário sair do jogo antes da missão terminar, nada precisa acontecer em background.

Quando o usuário voltar, o sistema deve identificar missões vencidas e exibir aviso visual.

Exemplo:

```text
Você possui missões concluídas aguardando coleta.
```

O botão "Receber Loot" deve estar disponível para missões cujo `ends_at` já passou.

## Não usar worker no MVP

Não implementar:

* Celery;
* Redis;
* scheduler;
* background job;
* processamento automático contínuo.

O MVP deve funcionar sem processo paralelo.

## Estados da missão

Status recomendados para `mission_runs`:

```text
in_progress
completed
claimed
failed
```

Uso esperado:

### in_progress

Missão iniciada e ainda não recebida.

Pode estar com tempo em andamento ou já vencida aguardando coleta.

### completed

Missão concluída com sucesso, após o usuário clicar em receber loot.

### failed

Missão concluída com falha, após o usuário clicar em receber loot.

### claimed

Opcional no MVP.

Se a implementação preferir separar conclusão de coleta, pode usar `claimed`.

Para simplificar, no MVP é aceitável tratar `completed` e `failed` como estados finais após o clique em receber loot.

## Recomendação para o MVP

Para evitar complexidade, usar:

```text
in_progress
completed
failed
```

A missão fica `in_progress` até o usuário clicar em "Receber Loot".

Ao clicar:

* se sucesso, muda para `completed`;
* se falha, muda para `failed`.

## Missões vencidas

Uma missão vencida é uma missão com:

```text
status = in_progress
ends_at <= now
```

Missões vencidas devem aparecer como prontas para coleta.

## Mercenários em missão

Ao iniciar uma missão, os mercenários selecionados devem ficar:

```text
status = busy
```

Ao receber loot, independentemente de sucesso ou falha, os mercenários devem voltar para:

```text
status = available
```

## Cálculo básico de sucesso

No MVP, usar cálculo simples.

Cada missão pode ter uma chance base de sucesso.

Exemplo:

```text
base_success_chance = 80
```

A força do mercenário pode influenciar a chance final.

Exemplo conceitual:

```text
success_chance = base_success_chance + bonus_por_atributos
```

Para o MVP, manter simples e fácil de ajustar.

A regra exata pode ficar na task da funcionalidade.

## Cálculo básico de loot

No MVP, missões devem premiar principalmente:

* ouro;
* XP básico.

Exemplo:

```text
Caçar lobos
Duração: 5 minutos
Ouro base: 25
XP base: 10
Chance de sucesso: 80%
```

Se sucesso:

```text
guild_resources.gold += reward_gold
mercenary.xp += reward_xp
```

Se falha:

```text
sem ouro
xp reduzido opcional
```

Para o MVP, falha pode conceder XP reduzido.

Exemplo:

```text
failed_xp = floor(reward_xp * 0.25)
```

## Configuração administrativa

A duração das missões deve ser configurável pelo admin.

Isso permite testar missões com tempos curtos durante o desenvolvimento.

O admin deve conseguir ajustar, no mínimo:

```text
duration_seconds
```

A configuração de duração deve afetar novas missões iniciadas após a alteração.

Missões já iniciadas devem manter o `ends_at` original.

## Regra importante sobre alteração de duração

Se o admin alterar a duração da missão "Caçar lobos" de 5 minutos para 30 segundos:

* novas execuções devem usar 30 segundos;
* execuções já iniciadas continuam com o tempo calculado anteriormente.

## Multi-tenancy

Templates globais de missão são compartilhados por todos os usuários.

Execuções de missão pertencem à guilda.

Exemplo:

```text
mission_templates -> global
mission_runs -> guild_id
mission_run_members -> guild_id indireto via mission_run
```

O usuário nunca deve informar `guild_id` no frontend.

O backend deve obter a guilda pela sessão do usuário.

## Critério do loop funcional

O loop de missões estará funcional quando:

* o usuário consegue ver missões disponíveis;
* o usuário consegue iniciar missão com mercenário disponível;
* o mercenário fica ocupado;
* a tela mostra timer;
* o botão de loot fica bloqueado antes do tempo;
* o botão de loot libera após o tempo;
* o backend impede coleta antecipada;
* o usuário recebe ouro/XP ao coletar;
* o mercenário volta a ficar disponível;
* outro usuário não enxerga missões em andamento da primeira guilda;
* admin consegue alterar duração de missão;
* alteração de duração afeta apenas novas missões.
