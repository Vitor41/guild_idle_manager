# 12 - MVP 010 - Classes, Tavern and Class Change

## Objetivo

Definir os sistemas do MVP-010 do Guild Idle Manager.

Este documento consolida:

* sistema de classes;
* evolução de classes;
* taverna;
* contratação de aprendizes com RNG;
* mercenários especiais temporários;
* missão de troca de classe;
* XP e nível da guilda;
* ajustes em construções;
* preparação para itens e restrições futuras por classe.

## Estado atual esperado

Este MVP assume que os MVPs 000 a 009 já existem ou estão em desenvolvimento:

* autenticação;
* guilda;
* recursos;
* mercenários;
* missões;
* dungeons;
* inventário;
* equipamentos;
* RNG de equipamentos;
* nível mínimo para equipamentos;
* construções;
* party size;
* admin parametrizável;
* raridades e tiers.

## Direção do MVP-010

O jogo deve passar a ter progressão de personagem baseada em classes.

Todos os mercenários contratados normalmente começam como Aprendiz.

O jogador evolui o mercenário até determinados níveis e usa uma missão especial para trocar de classe.

A Taverna passa a ser o local central de contratação.

## Árvore de classes

### Tier 0 - Classe inicial

Todos os mercenários normais começam como:

```text
Aprendiz
```

Código sugerido:

```text
apprentice
```

Level inicial:

```text
1
```

## Tier 1 - Primeira classe

Ao atingir level 20, o Aprendiz pode escolher uma das 5 classes:

```text
Warrior -> Guerreiro
Rogue -> Ladino
Mage -> Mago
Cleric -> Clérigo
Archer -> Arqueiro
```

Observação:

O Ranger do jogo será uma especialização futura do Archer, não a primeira classe.

## Tier 2 - Especialização

Ao atingir level 100, cada classe pode escolher uma especialização.

### Warrior

```text
Knight -> Cavaleiro
Blade -> Duelista
```

Cavaleiro:

* perfil de tank forte;
* usa lança e escudo;
* voltado para missões e dungeons difíceis;
* foco em sobrevivência.

Duelista:

* guerreiro ágil;
* usa duas espadas ou dois machados;
* não usa escudo;
* funciona como tank mais ofensivo;
* menos resistente que Cavaleiro;
* mais resistente que classes ágeis.

### Rogue

```text
Assassin -> Assassino
Ninja -> Ninja
```

Assassino:

* extremamente ágil;
* usa adagas;
* foco em eliminar alvos difíceis;
* deve ter bônus em conteúdo que exige agilidade/crítico/execução.

Ninja:

* misto de ataque físico de média distância, agilidade e magia;
* usa kunais ou shurikens;
* deve ter bônus híbrido físico/mágico.

### Mage

```text
Wizard -> Sábio
Mentalist -> Mentalista
```

Sábio:

* mago elemental;
* usa cajado;
* domina elementos;
* deve ter bônus em missões/dungeons com fraqueza elemental.

Mentalista:

* assassino mágico;
* usa varinha e escudo;
* usa magia dark;
* foco em dano mágico/verdadeiro;
* escudo compensa defesa baixa.

### Cleric

```text
Priest -> Padre
Paladin -> Paladino
```

Padre:

* healer do grupo;
* usa livro;
* coringa do time;
* deve ter bônus de cura, buffs e suporte ao grupo.

Paladino:

* mercenário da luz que se apaixonou pela batalha;
* usa espada e escudo;
* tem cura, buffs e sustain, mas aplicados principalmente nele mesmo;
* bônus parecidos com Padre, mas menores e mais individuais.

### Archer

```text
Ranger -> Ranger
Shooter -> Pistoleiro
```

Ranger:

* arqueiro especializado e focado em riqueza;
* usa arco;
* bônus em ganho de ouro;
* pode aumentar chance de itens raros.

Pistoleiro:

* cobrador de recompensas;
* usa duas pistolas;
* bônus geral de sorte;
* deve ser útil em missões de caçar recompensas.

## Tier 3 - Classe final

Ao atingir level 350, a especialização pode alcançar a classe final.

### Knight

```text
Templar -> Templário
```

* evolução do Cavaleiro;
* tanque extremamente forte;
* usa lança e escudo;
* aumenta os bônus defensivos da classe anterior.

### Blade

```text
Reaper -> Retalhador
```

* evolução do Duelista;
* especialista em combate corpo a corpo;
* ágil;
* usa duas espadas ou dois machados.

### Assassin

```text
Predator -> Predador
```

* evolução do Assassino;
* especialista em assassinato de alvos difíceis;
* usa adagas.

### Ninja

```text
Shinobi -> Shinobi
```

* evolução do Ninja;
* especialista na arte ninja;
* mistura distrações, ataques físicos de média distância e magia;
* usa kunais ou shurikens.

### Wizard

```text
Arcane -> Arcano
```

* evolução do Sábio;
* especialista em magias elementais fortes;
* usa cajado;
* representa magias como meteoros, gelo, tsunamis e efeitos elementais poderosos.

### Mentalist

```text
Warlock -> Bruxo
```

* evolução do Mentalista;
* especialista em magia dark e dano verdadeiro;
* passa a usar apenas varinha;
* não usa mais escudo.

### Priest

```text
HighPriest -> Sacerdote
```

* evolução do Padre;
* especialista em cura, buffs e debuffs;
* usa livro.

### Paladin

```text
Sentinel -> Sentinela
```

* evolução do Paladino;
* especialista em duelo corpo a corpo;
* menor potencial ofensivo que Retalhador;
* mantém buffs e cura própria;
* usa espada e escudo.

### Ranger

```text
Patroller -> Patrulheiro
```

* evolução do Ranger;
* especialista em escolta de pessoas importantes;
* foco em contratos muito lucrativos;
* usa arco.

### Shooter

```text
Renegade -> Renegado
```

* evolução do Pistoleiro;
* especialista em armas de fogo e execução à longa distância;
* pode usar pistolas;
* arma principal passa a ser rifle;
* rifle é arma de duas mãos;
* não pode usar dois rifles, rifle + escudo ou rifle + outra arma.

## Códigos internos recomendados

Usar códigos estáveis no backend e nomes de exibição em PT-BR.

```text
apprentice -> Aprendiz

warrior -> Guerreiro
rogue -> Ladino
mage -> Mago
cleric -> Clérigo
archer -> Arqueiro

knight -> Cavaleiro
blade -> Duelista
assassin -> Assassino
ninja -> Ninja
wizard -> Sábio
mentalist -> Mentalista
priest -> Padre
paladin -> Paladino
ranger -> Ranger
shooter -> Pistoleiro

templar -> Templário
reaper -> Retalhador
predator -> Predador
shinobi -> Shinobi
arcane -> Arcano
warlock -> Bruxo
high_priest -> Sacerdote
sentinel -> Sentinela
patroller -> Patrulheiro
renegade -> Renegado
```

## Reaproveitamento da tabela de classes

Se o projeto já possui `mercenary_classes`, preferir evoluir essa tabela em vez de criar outra tabela paralela.

Adicionar campos conforme necessário:

```text
code
display_name
tier
parent_class_id
required_level
allowed_weapon_profile
role_type
description
is_active
```

Se for tecnicamente melhor criar `class_templates`, documentar a decisão e manter compatibilidade com mercenários existentes.

## Transições de classe

Criar tabela global de transições.

Nome sugerido:

```text
class_transition_options
```

Campos sugeridos:

```text
id
from_class_id
to_class_id
transition_tier
required_mercenary_level
required_guild_level
required_training_field_level
gold_cost
duration_seconds
is_active
created_at
updated_at
```

Duração padrão:

```text
86400 segundos
```

Equivale a 24 horas.

## Requisitos de troca de classe

### Primeira classe

```text
Aprendiz -> Warrior/Rogue/Mage/Cleric/Archer
```

Requisitos:

```text
mercenary_level >= 20
guild_level >= 5
training_field_level >= 10
gold_cost = 1000
duration = 24h
```

### Segunda classe

```text
Warrior/Rogue/Mage/Cleric/Archer -> especializações
```

Requisitos:

```text
mercenary_level >= 100
guild_level >= 15
training_field_level >= 50
gold_cost = 5000
duration = 24h
```

### Terceira classe

```text
especialização -> classe final
```

Requisitos:

```text
mercenary_level >= 350
guild_level >= 50
training_field_level >= 100
gold_cost = 10000
duration = 24h
```

## Missão de troca de classe

A troca de classe deve funcionar como uma missão especial.

Não misturar diretamente com missões normais nem dungeons.

Tabela sugerida:

```text
class_change_runs
```

Campos sugeridos:

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

No MVP, não precisa permitir cancelamento se isso gerar complexidade.

## Regras da missão de troca de classe

* usuário precisa estar autenticado;
* guilda obrigatória;
* mercenário precisa pertencer à guilda;
* mercenário precisa estar `available`;
* mercenário precisa ter nível mínimo;
* guilda precisa ter nível mínimo;
* Campo de Treino precisa ter nível mínimo;
* guilda precisa ter gold suficiente;
* apenas 1 mercenário por missão de troca de classe;
* mercenário fica `busy`;
* missão dura 24h;
* ao finalizar, usuário clica para concluir;
* backend valida `now >= ends_at`;
* classe do mercenário é alterada;
* mercenário volta para `available`.

## Fluxo da troca de classe

Tela sugerida:

```text
/class-change
```

Fluxo:

```text
1. Usuário acessa tela de troca de classe.
2. Sistema lista mercenários elegíveis ou próximos de elegibilidade.
3. Usuário seleciona mercenário.
4. Sistema mostra apenas classes destino válidas para a classe atual.
5. Usuário escolhe classe destino.
6. Sistema valida requisitos.
7. Sistema cobra gold.
8. Sistema inicia class_change_run.
9. Mercenário fica ocupado por 24h.
10. Após o tempo, usuário clica em "Concluir troca".
11. Sistema altera a classe.
12. Mercenário volta a ficar disponível.
```

## Respeito ao caminho de classe

O mercenário precisa seguir a árvore.

Exemplo:

```text
Aprendiz -> Guerreiro -> Cavaleiro -> Templário
```

Não permitir:

```text
Aprendiz -> Cavaleiro
Guerreiro -> Templário
Ladino -> Arcano
```

Se um Aprendiz chegar ao level 350 sem trocar de classe, ainda assim ele deve começar pela primeira troca:

```text
Aprendiz -> primeira classe
```

Depois precisará fazer as trocas seguintes.

## Taverna

A Taverna será um edifício da guilda.

Ela será o local central para contratação de mercenários.

O recrutamento antigo em `/mercenaries` deve ser removido, desativado ou redirecionado para a Taverna.

Rota sugerida:

```text
/tavern
```

## Taverna como construção

Garantir que exista um building template:

```text
Taverna
```

Se o sistema de construções já existir, adicionar Taverna como construção ativa.

A Taverna pode ter nível e upgrades como as demais construções.

No MVP-010, os efeitos principais da Taverna são:

```text
liberar contratação de Aprendizes
exibir custo atual de contratação
exibir oferta especial temporária
melhorar levemente chances futuras, se implementado de forma simples
```

## Contratação de Aprendiz

Na Taverna, o jogador pode contratar mercenários Aprendizes por gold.

Todo mercenário normal contratado pela Taverna nasce como:

```text
Classe: Aprendiz
Level: 1
Status: available
Raridade: common ou uncommon
```

Raridades possíveis para Aprendiz normal:

```text
common
uncommon
```

Aprendiz normal não pode nascer rare, epic, legendary ou mythic.

## Raridades de mercenário

Usar as mesmas raridades gerais:

```text
common -> Comum
uncommon -> Incomum
rare -> Raro
epic -> Épico
legendary -> Lendário
mythic -> Mítico
```

## RNG de atributos do Aprendiz

Ao contratar um Aprendiz, gerar atributos por RNG no ato da compra.

Não recalcular depois.

Atributos:

```text
power
vitality
agility
intelligence
luck
```

Regras iniciais:

```text
common: cada atributo entre 1 e 10
uncommon: cada atributo entre 1 e 15
```

A intenção é fazer o jogador contratar aprendizes repetidas vezes para buscar bons atributos.

Exemplo:

```text
Aprendiz common:
power = 4
vitality = 8
agility = 2
intelligence = 10
luck = 5
```

Esse personagem pode ser bom candidato a Mago.

## Chance de raridade no Aprendiz

Regra inicial sugerida:

```text
common = 90%
uncommon = 10%
```

A Taverna pode futuramente melhorar essa chance.

Se for simples no MVP:

```text
uncommon_chance = 10 + bônus da Taverna
```

Aplicar cap para não quebrar balanceamento.

Exemplo de cap:

```text
uncommon_chance máximo = 30%
```

## Custo de contratação de Aprendiz

Custo inicial:

```text
50 gold
```

O custo aumenta a cada contratação.

Regra:

```text
se custo atual < 5000:
  próximo custo = ceil(custo atual * 1.05)

se custo atual >= 5000:
  próximo custo = ceil(custo atual * 1.03)
```

Guardar esse estado por guilda.

Campos possíveis em `guild_tavern_states`:

```text
id
guild_id
apprentice_hire_count
current_apprentice_hire_cost
next_special_check_at
active_special_offer_until
created_at
updated_at
```

Se preferir, esses campos podem ser adicionados em outra tabela de estado da guilda, desde que fiquem por `guild_id`.

## XP da guilda

A guilda passa a ter XP e level real.

Se `guilds.level` já existe, reaproveitar.

Adicionar:

```text
guilds.xp
```

Se necessário, adicionar:

```text
guilds.max_level
```

Regra:

```text
max guild level = 50
```

Fórmula de XP:

```text
xp_required = current_guild_level * 100
```

Ao ganhar XP suficiente, a guilda sobe de nível.

Permitir múltiplos níveis se houver XP suficiente.

## Ganho de XP da guilda

Ações fixas dão XP da guilda:

```text
contratar mercenário: +10 XP
evoluir construção: +10 XP
iniciar/concluir troca de classe: +10 XP, se fizer sentido na implementação
```

Missões e dungeons dão XP da guilda com base no XP gerado para mercenários:

```text
guild_xp = floor(total_mercenary_xp_generated * 0.01)
```

Se houver XP gerado e o cálculo der zero, aplicar mínimo:

```text
guild_xp = 1
```

A guilda deve ganhar XP tanto em sucesso quanto em falha, pois falha também gera XP reduzido.

Criar service centralizado:

```text
guild_progression_service.add_guild_xp(...)
```

Não espalhar regra de XP da guilda em vários pontos sem centralização.

## Construções até nível 100

A partir deste MVP, construções devem poder ir até level 100.

Garantir que templates e validações não estejam travados em níveis menores, salvo se o admin configurar diferente.

Campo de Treino é especialmente importante porque troca de classe depende dele.

Requisitos:

```text
1ª classe: Campo de Treino level 10
2ª classe: Campo de Treino level 50
3ª classe: Campo de Treino level 100
```

## Mercenário especial da Taverna

A Taverna terá uma mecânica separada de mercenário especial temporário.

Esse mercenário:

* pode aparecer em uma janela de tempo;
* fica disponível por tempo limitado;
* é caro;
* pode ser rare, epic, legendary ou mythic;
* já nasce no level 20;
* nasce em uma das primeiras classes;
* não nasce como Aprendiz;
* tem atributos RNG orientados pela classe e raridade.

Classes possíveis:

```text
Warrior
Rogue
Mage
Cleric
Archer
```

## Janela de mercenário especial

Regra inicial:

```text
a cada 8 horas existe uma tentativa de surgimento
se surgir, fica disponível por 2 horas
se não surgir, mostra mensagem informando que ninguém apareceu
```

Esses valores devem ser configuráveis pelo admin.

Campos configuráveis:

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

Para testes locais, o admin pode aumentar a chance e reduzir o cooldown.

## Persistência da oferta especial

Não criar registro em `mercenaries` até a guilda contratar o mercenário.

É aceitável manter uma tabela de oferta temporária por guilda, desde que ela represente apenas a oferta e expire.

Nome sugerido:

```text
tavern_special_offers
```

Campos sugeridos:

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

Ao expirar, a oferta não deve aparecer mais.

Ao contratar, criar o mercenário real e marcar a oferta como `hired`.

## RNG do mercenário especial

O RNG deve respeitar a classe.

Exemplo:

Guerreiro deve tender a ter mais:

```text
power
vitality
```

Mago deve tender a ter mais:

```text
intelligence
luck
```

Ladino deve tender a ter mais:

```text
agility
luck
```

Clérigo deve tender a ter mais:

```text
intelligence
vitality
```

Arqueiro deve tender a ter mais:

```text
agility
luck
```

## Caps por raridade

Caps máximos iniciais por atributo:

```text
rare = 40
epic = 50
legendary = 70
mythic = 100
```

Esses caps são máximos possíveis, não garantia.

O RNG ainda pode gerar valores abaixo do teto.

## Classe e atributos do especial

O mercenário especial nasce no level 20.

Ele deve nascer em uma primeira classe:

```text
Warrior
Rogue
Mage
Cleric
Archer
```

Ele não precisa passar pela missão de primeira classe, pois já aparece como mercenário especial.

Para chegar à segunda classe, deverá usar a missão de troca de classe normalmente quando atender os requisitos.

## Nome do mercenário especial

O sistema pode sugerir nomes simples.

No MVP, pode usar uma lista interna.

Exemplo:

```text
Arkon
Mira
Thalos
Nyra
Darian
Kael
Veyra
Rurik
```

Não precisa implementar gerador avançado.

## Tela da Taverna

A tela `/tavern` deve exibir:

```text
nome da guilda
gold atual
nível da Taverna
custo atual para contratar Aprendiz
botão contratar Aprendiz
explicação das chances common/uncommon
mercenário especial ativo, se houver
contador para próxima tentativa de mercenário especial
contador de expiração da oferta especial
botão contratar mercenário especial, se disponível
```

Se não houver oferta especial:

```text
Nenhum mercenário especial disponível no momento.
```

Se houver timer:

```text
Próxima chance de visitante especial em: HH:MM:SS
```

Se houver oferta ativa:

```text
Visitante especial disponível por: HH:MM:SS
```

## Admin da Taverna

Criar tela admin para parâmetros da Taverna.

Campos editáveis:

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

Não hardcodar esses valores se já forem parte da configuração.

## Admin de classes

Criar ou ajustar admin para classes.

Admin deve conseguir ver e editar, no mínimo:

```text
display_name
description
tier
required_level
allowed_weapon_profile
role_type
is_active
```

Se for complexo editar toda árvore via admin, ao menos listar as classes e permitir ativar/desativar e ajustar descrição/nome.

A árvore de transições pode ser seedada inicialmente.

## Bônus de classes

Neste MVP, não implementar sistema profundo de bônus individuais e bônus de grupo.

Criar base para isso com campos simples.

Sugestão em `mercenary_classes`:

```text
bonus_power
bonus_vitality
bonus_agility
bonus_intelligence
bonus_luck
bonus_gold_percent
bonus_xp_percent
bonus_drop_percent
bonus_success_chance
```

No MVP, aplicar apenas bônus simples se for seguro e produtivo.

Não criar sistema complexo de composição de grupo agora.

## Restrições de armas

Preparar campos para restrição de armas por classe.

Perfis sugeridos:

```text
spear_shield
dual_blade_or_axe
dagger
kunai_shuriken
staff
wand_shield
wand_only
book
sword_shield
bow
dual_pistol
rifle
```

No MVP, se a lógica de equipamentos já tiver tipo de arma, aplicar validação básica.

Se ainda não existir tipo de arma, preparar os campos e não bloquear a entrega por isso.

## Itens específicos por classe

Fora do MVP-010 implementar completamente roupas/itens específicos por classe.

Regra futura:

* classe final pode usar itens da classe anterior;
* itens específicos da classe final só devem nascer acima de rare;
* common/uncommon/rare podem ser usados da classe anterior.

No MVP-010, apenas documentar/preparar campos se necessário.

## Multi-tenancy

Tudo que pertence ao jogador deve usar `guild_id`.

Por guilda:

```text
guild_tavern_states
tavern_special_offers
class_change_runs
mercenaries
guild_buildings
guild_resources
```

Global:

```text
mercenary_classes
class_transition_options
tavern_config
building_templates
```

Nunca aceitar `guild_id` vindo do frontend.

## Seeds

Seeds devem ser idempotentes.

Não duplicar.

Não sobrescrever alteração feita pelo admin.

Criar seeds para:

```text
classes
transições de classe
Taverna como construção
configuração inicial da Taverna
```

## Fora do escopo do MVP-010

Não implementar agora:

```text
árvore de talentos
skills ativas
bônus complexos de composição
roupas específicas por classe
itens finais exclusivos por classe
crafting
refino
loja
trade
combate visual
UX final
```

UX final será MVP-011.
