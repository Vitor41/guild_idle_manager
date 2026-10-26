# MVP-010 - Classes, Tavern and Class Change

## Contexto

O MVP-000 ao MVP-009 já foram validados ou estão previstos como base.

O jogo já possui fundação de:

* autenticação;
* guilda;
* recursos;
* mercenários;
* level up;
* missões;
* dungeons;
* inventário;
* equipamentos;
* RNG;
* construções;
* admin parametrizável.

Agora o jogo deve receber sistema de classes, Taverna e missão de troca de classe.

## Objetivo

Implementar:

* árvore de classes;
* todos os mercenários normais começando como Aprendiz;
* Taverna como local de contratação;
* contratação de Aprendizes com RNG de atributos;
* custo escalável de contratação;
* raridade de mercenários;
* mercenários especiais temporários na Taverna;
* missão especial de troca de classe;
* XP e nível da guilda;
* requisitos de guilda/Campo de Treino para troca de classe;
* admin básico para classes e Taverna.

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/03-MULTI-TENANCY.md`
* `docs/04-GAME-LOOP.md`
* `docs/05-DATABASE-MODEL.md`
* `docs/08-BALANCE-RULES.md`
* `docs/09-ADMIN-CONFIGURATION.md`
* `docs/10-EQUIPMENT-RNG.md`
* `docs/11-MVP-006-TO-009-SYSTEMS.md`
* `docs/12-MVP-010-CLASSES-TAVERN.md`
* `tasks/MVP-010-CLASSES-TAVERN-CLASS-CHANGE.md`

Consultar o código atual para manter padrões já implementados.

## Escopo macro

Implementar:

```text
1. Classes e transições
2. Taverna
3. Recrutamento de Aprendizes
4. Mercenário especial temporário
5. Missão de troca de classe
6. XP e nível da guilda
7. Admin de classes/Taverna
```

## Parte 1 - Classes

### Implementar

* evoluir tabela de classes existente ou criar estrutura equivalente;
* criar árvore de classes;
* criar transições válidas;
* atualizar mercenários para suportar classe atual;
* garantir que novas contratações normais nasçam como Aprendiz;
* exibir classe atual nas telas de mercenário, missão, dungeon e dashboard quando aplicável.

### Classes obrigatórias

Criar as classes:

```text
Aprendiz

Guerreiro
Ladino
Mago
Clérigo
Arqueiro

Cavaleiro
Duelista
Assassino
Ninja
Sábio
Mentalista
Padre
Paladino
Ranger
Pistoleiro

Templário
Retalhador
Predador
Shinobi
Arcano
Bruxo
Sacerdote
Sentinela
Patrulheiro
Renegado
```

Códigos internos recomendados:

```text
apprentice

warrior
rogue
mage
cleric
archer

knight
blade
assassin
ninja
wizard
mentalist
priest
paladin
ranger
shooter

templar
reaper
predator
shinobi
arcane
warlock
high_priest
sentinel
patroller
renegade
```

### Árvore obrigatória

```text
Aprendiz
├── Guerreiro
│   ├── Cavaleiro
│   │   └── Templário
│   └── Duelista
│       └── Retalhador
├── Ladino
│   ├── Assassino
│   │   └── Predador
│   └── Ninja
│       └── Shinobi
├── Mago
│   ├── Sábio
│   │   └── Arcano
│   └── Mentalista
│       └── Bruxo
├── Clérigo
│   ├── Padre
│   │   └── Sacerdote
│   └── Paladino
│       └── Sentinela
└── Arqueiro
    ├── Ranger
    │   └── Patrulheiro
    └── Pistoleiro
        └── Renegado
```

### Transições

Criar ou seedar `class_transition_options`.

Cada transição deve indicar:

```text
from_class
to_class
transition_tier
required_mercenary_level
required_guild_level
required_training_field_level
gold_cost
duration_seconds
is_active
```

Duração:

```text
86400 segundos
```

### Requisitos

Primeira classe:

```text
required_mercenary_level = 20
required_guild_level = 5
required_training_field_level = 10
gold_cost = 1000
```

Segunda classe:

```text
required_mercenary_level = 100
required_guild_level = 15
required_training_field_level = 50
gold_cost = 5000
```

Terceira classe:

```text
required_mercenary_level = 350
required_guild_level = 50
required_training_field_level = 100
gold_cost = 10000
```

## Parte 2 - Taverna

### Implementar

* building template `Taverna`;
* estado da Taverna por guilda;
* tela `/tavern`;
* contratação de Aprendizes;
* custo escalável;
* RNG de atributos;
* chance common/uncommon;
* XP de guilda ao contratar;
* link no menu/header.

### Recrutamento antigo

Se ainda existir recrutamento direto em `/mercenaries`, desativar ou redirecionar para `/tavern`.

A contratação principal deve acontecer na Taverna.

### Tabela de estado sugerida

```text
guild_tavern_states
```

Campos:

```text
id
guild_id
apprentice_hire_count
current_apprentice_hire_cost
next_special_check_at
created_at
updated_at
```

### Contratar Aprendiz

Rota sugerida:

```text
POST /tavern/hire-apprentice
```

Regras:

* usuário autenticado;
* guilda obrigatória;
* Taverna existente;
* gold suficiente;
* respeitar limite de mercenários do Alojamento;
* descontar gold;
* gerar raridade;
* gerar atributos RNG;
* criar mercenário como Aprendiz;
* status `available`;
* level 1;
* XP 0;
* adicionar +10 XP para guilda;
* atualizar próximo custo.

### Custo

Custo inicial:

```text
50 gold
```

Regra:

```text
se custo atual < 5000:
  próximo custo = ceil(custo atual * 1.05)

se custo atual >= 5000:
  próximo custo = ceil(custo atual * 1.03)
```

### Raridade de Aprendiz

```text
common = 90%
uncommon = 10%
```

Se existir bônus da Taverna, pode ajustar, mas manter cap.

### Atributos de Aprendiz

Common:

```text
power: 1 a 10
vitality: 1 a 10
agility: 1 a 10
intelligence: 1 a 10
luck: 1 a 10
```

Uncommon:

```text
power: 1 a 15
vitality: 1 a 15
agility: 1 a 15
intelligence: 1 a 15
luck: 1 a 15
```

## Parte 3 - Mercenário especial temporário

### Implementar

* tentativa de surgimento na Taverna;
* oferta temporária;
* contador de próxima tentativa;
* contador de expiração;
* contratação de especial;
* admin/config para parâmetros;
* RNG por classe e raridade.

### Regras

* aparece por sorte;
* pode não aparecer;
* fica disponível por tempo limitado;
* se expirar, some;
* se contratar, vira mercenário real;
* não criar mercenário real antes da contratação.

### Raridades possíveis

```text
rare
epic
legendary
mythic
```

### Classe inicial

Mercenário especial nasce no level 20 em uma das primeiras classes:

```text
warrior
rogue
mage
cleric
archer
```

Não nasce como Aprendiz.

### Caps por raridade

```text
rare = 40
epic = 50
legendary = 70
mythic = 100
```

### RNG orientado por classe

Implementar geração de atributos coerente com a classe:

Guerreiro:

```text
prioridade: power, vitality
```

Ladino:

```text
prioridade: agility, luck
```

Mago:

```text
prioridade: intelligence, luck
```

Clérigo:

```text
prioridade: intelligence, vitality
```

Arqueiro:

```text
prioridade: agility, luck
```

Não gerar atributos completamente aleatórios sem considerar a classe.

### Oferta especial

Tabela sugerida:

```text
tavern_special_offers
```

Campos:

```text
id
guild_id
name
class_id
rarity
level
power
vitality
agility
intelligence
luck
gold_cost
available_from
available_until
status
created_at
updated_at
```

Status:

```text
active
expired
hired
```

### Configuração

Criar ou usar tabela/config admin para:

```text
special_spawn_cooldown_hours
special_offer_duration_hours
special_spawn_chance
special_rare_chance
special_epic_chance
special_legendary_chance
special_mythic_chance
special_rare_cost
special_epic_cost
special_legendary_cost
special_mythic_cost
```

Valores padrão:

```text
special_spawn_cooldown_hours = 8
special_offer_duration_hours = 2
special_spawn_chance = 5
```

Custos iniciais sugeridos:

```text
rare = 5000
epic = 25000
legendary = 100000
mythic = 500000
```

Para teste, admin pode reduzir cooldown e aumentar chance.

## Parte 4 - Missão de troca de classe

### Implementar

* tela `/class-change`;
* listagem de mercenários;
* opções válidas por classe atual;
* validação de requisitos;
* pagamento em gold;
* execução com timer de 24h;
* mercenário busy;
* conclusão manual;
* alteração da classe;
* liberação do mercenário.

### Tabela sugerida

```text
class_change_runs
```

Campos:

```text
id
guild_id
mercenary_id
from_class_id
to_class_id
status
gold_cost
started_at
ends_at
resolved_at
created_at
updated_at
```

Status:

```text
in_progress
completed
cancelled
```

### Rotas sugeridas

```text
GET /class-change
POST /class-change/start
POST /class-change/{run_id}/claim
```

### Regras

* apenas usuário autenticado;
* guilda obrigatória;
* mercenário da guilda;
* mercenário `available`;
* classe destino válida;
* requisitos atendidos;
* gold suficiente;
* descontar gold ao iniciar;
* mercenário fica `busy`;
* backend valida `now >= ends_at` ao concluir;
* classe só muda ao concluir;
* mercenário volta `available`.

### Seleção de classe destino

O select deve filtrar opções conforme classe atual.

Exemplos:

Aprendiz:

```text
Guerreiro
Ladino
Mago
Clérigo
Arqueiro
```

Guerreiro:

```text
Cavaleiro
Duelista
```

Cavaleiro:

```text
Templário
```

Não exibir opções inválidas.

## Parte 5 - XP e nível da guilda

### Implementar

Adicionar XP na guilda, se ainda não existir:

```text
guilds.xp
```

Level máximo:

```text
50
```

Fórmula:

```text
xp_required = guild_level * 100
```

Se a guilda ganhar XP suficiente, subir nível.

### Ganhos de XP

Ações fixas:

```text
contratar mercenário = +10 XP
evoluir construção = +10 XP
iniciar/concluir troca de classe = +10 XP, se fizer sentido
```

Missões e dungeons:

```text
guild_xp = floor(total_mercenary_xp_generated * 0.01)
```

Se houver XP gerado e o resultado for 0:

```text
guild_xp = 1
```

Criar service central:

```text
guild_progression_service.add_guild_xp(...)
```

Usar esse service nas ações relevantes.

## Parte 6 - Construções até level 100

Garantir que construções possam chegar até level 100.

Ajustar templates/seeds/admin se estiverem com max_level menor.

Campo de Treino precisa poder chegar a 100.

Taverna também deve entrar como construção evoluível.

## Parte 7 - Admin

### Admin de classes

Criar/admin ajustar tela para visualizar classes.

Permitir editar, no mínimo:

```text
display_name
description
tier
required_level
allowed_weapon_profile
role_type
is_active
```

Se for simples, permitir também editar bônus básicos.

### Admin da Taverna

Criar tela para editar parâmetros da Taverna.

Campos:

```text
base_apprentice_cost
apprentice_cost_growth_before_5000
apprentice_cost_growth_after_5000
apprentice_cost_threshold
common_apprentice_chance
uncommon_apprentice_chance
special_spawn_cooldown_hours
special_offer_duration_hours
special_spawn_chance
special_rare_chance
special_epic_chance
special_legendary_chance
special_mythic_chance
special_rare_cost
special_epic_cost
special_legendary_cost
special_mythic_cost
```

### Admin de transições

Se for produtivo, criar visualização das transições.

Se for complexo, seedar e manter apenas consulta/admin simples.

## Parte 8 - Telas

### Dashboard

Atualizar dashboard com:

```text
guild level
guild XP
próximo nível da guilda
Taverna
mercenário especial disponível, se houver
troca de classe em andamento, se houver
```

### Mercenários

Atualizar tela de mercenários com:

```text
classe atual
raridade
level
atributos
elegível para troca de classe
```

### Taverna

Criar tela `/tavern`.

### Troca de classe

Criar tela `/class-change`.

### Header/Menu

Adicionar links:

```text
Taverna
Troca de Classe
```

## Migrations

Criar migrations necessárias para:

```text
ajustes em mercenary_classes ou class_templates
class_transition_options
guild_tavern_states
tavern_special_offers
class_change_runs
guilds.xp
Taverna em building_templates
ajustes de max_level em construções
```

Aplicar com:

```bash
alembic upgrade head
```

## Seeds

Criar seeds idempotentes para:

```text
classes
transições de classe
Taverna
configuração inicial da Taverna
```

Regras:

* não duplicar;
* não sobrescrever admin;
* não quebrar se dados já existirem.

## Multi-tenancy obrigatório

Nunca aceitar `guild_id` vindo do frontend.

Validar `guild_id` em:

```text
guild_tavern_states
tavern_special_offers
class_change_runs
mercenaries
guild_resources
guild_buildings
```

## Fora do escopo

Não implementar nesta task:

```text
skills
árvore de talentos
bônus complexos de grupo
roupas específicas por classe
itens finais exclusivos por classe
crafting
refino
loja
trade
monetização
UX final
```

## Validação manual esperada

Após implementar:

1. Rodar migrations.
2. Logar com usuário admin.
3. Validar admin de classes.
4. Validar admin da Taverna.
5. Confirmar Taverna como construção.
6. Acessar `/tavern`.
7. Contratar Aprendiz.
8. Confirmar classe Aprendiz.
9. Confirmar atributos RNG.
10. Confirmar raridade common/uncommon.
11. Confirmar custo subindo.
12. Confirmar XP da guilda subindo.
13. Ajustar spawn especial no admin para teste.
14. Confirmar contador da Taverna.
15. Confirmar oferta especial aparecendo.
16. Contratar especial.
17. Confirmar especial nasce level 20 e em classe base.
18. Confirmar atributos coerentes com classe/raridade.
19. Ajustar mercenário/requisitos se necessário para testar troca.
20. Acessar `/class-change`.
21. Ver opções válidas conforme classe atual.
22. Iniciar missão de troca.
23. Confirmar gold descontado.
24. Confirmar mercenário busy.
25. Após tempo, concluir troca.
26. Confirmar classe alterada.
27. Confirmar mercenário disponível.
28. Logar com outro usuário.
29. Confirmar isolamento de Taverna, especiais e troca de classe.

## Critérios de conclusão

Considerar concluído quando:

* classes estiverem seedadas;
* árvore de classes existir;
* transições válidas existirem;
* Aprendizes forem contratados pela Taverna;
* contratação antiga fora da Taverna não for mais o fluxo principal;
* Aprendiz nascer level 1;
* Aprendiz nascer common/uncommon;
* atributos do Aprendiz forem RNG;
* custo de contratação escalar;
* guilda ganhar XP por contratação;
* guilda tiver XP e level máximo 50;
* construções puderem chegar a level 100;
* Taverna existir como construção;
* mercenário especial temporário funcionar;
* contador de especial aparecer na tela;
* especial puder ser contratado;
* especial nascer level 20 e em classe base;
* especial respeitar raridade e RNG orientado por classe;
* missão de troca de classe funcionar;
* requisitos de guilda, Campo de Treino, nível e gold forem validados;
* mercenário ficar busy durante troca;
* classe mudar apenas ao concluir;
* admin de classes/Taverna existir;
* multi-tenancy for respeitado;
* aplicação continuar rodando localmente.
