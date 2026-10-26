# MVP-011 - UX/UI Medieval Redesign

## Contexto

O Guild Idle Manager já possui várias mecânicas implementadas:

* autenticação;
* guilda;
* recursos;
* mercenários;
* classes;
* taverna;
* missões;
* dungeons;
* construções;
* inventário;
* equipamentos;
* RNG;
* troca de classe;
* admin parametrizável.

A funcionalidade evoluiu bem, mas a interface ainda está com aparência simples e pouco imersiva.

Agora o foco é melhorar a UX/UI.

## Objetivo

Redesenhar a interface do jogo com tema medieval/fantasia, mantendo uma experiência moderna, organizada e preparada para imagens, ícones, avatares e assets futuros.

O sistema deve parecer um jogo web de guilda, não um sistema administrativo genérico.

## Documentos relevantes

Antes de executar esta task, ler:

* `docs/00-CODEX-INDEX.md`
* `docs/01-PRODUCT-CONTEXT.md`
* `docs/03-MULTI-TENANCY.md`
* `docs/04-GAME-LOOP.md`
* `docs/09-ADMIN-CONFIGURATION.md`
* `docs/10-EQUIPMENT-RNG.md`
* `docs/11-MVP-006-TO-009-SYSTEMS.md`
* `docs/12-MVP-010-CLASSES-TAVERN.md`
* `docs/13-MVP-011-UX-UI-MEDIEVAL.md`
* `tasks/MVP-011-UX-UI-MEDIEVAL-REDESIGN.md`

Consultar também todos os templates atuais para preservar rotas, forms e fluxos existentes.

## Escopo

Implementar:

* novo layout base;
* sidebar temática;
* topbar/header;
* dashboard visual;
* cards de resumo;
* cards de mercenários;
* cards de missões;
* cards de dungeons;
* visual da Taverna;
* visual de Construções;
* visual de Inventário;
* visual de Troca de Classe;
* badges de raridade;
* badges de status;
* suporte estrutural a imagens;
* placeholders para avatares, classes, itens, construções e ícones;
* organização de CSS;
* responsividade básica;
* melhorias nos feedbacks;
* padronização de botões, formulários e tabelas.

## Regra principal

Não alterar regra de negócio.

Esta task é de UX/UI.

Não modificar cálculos, regras de classe, loot, missão, dungeon, equipamento, taverna, guild XP ou admin, salvo se for necessário para exibir melhor dados já existentes.

## Estrutura visual

Criar uma estrutura visual moderna:

```text
sidebar + topbar + conteúdo principal
```

A sidebar deve concentrar a navegação.

A topbar deve mostrar dados relevantes da guilda.

O conteúdo deve usar cards, seções e componentes visuais.

## Identidade medieval

A interface deve usar uma identidade visual com:

* tons escuros;
* dourado/bronze;
* textura visual leve;
* bordas inspiradas em pergaminho/metal;
* cards com profundidade;
* fontes legíveis;
* detalhes de fantasia medieval.

Evitar exagero visual que atrapalhe leitura.

## Assets e placeholders

Criar estrutura:

```text
app/static/img/
  placeholders/
  classes/
  mercenaries/
  items/
  buildings/
  icons/
```

Criar placeholders simples se possível.

Não precisa gerar imagens reais.

Pode usar CSS, SVG simples ou blocos visuais como placeholder.

O objetivo é deixar a estrutura pronta para receber imagens depois.

## Layout base

Atualizar `base.html` ou equivalente.

Deve conter:

* HTML base;
* sidebar;
* header;
* área de mensagens/flash;
* bloco de conteúdo;
* links CSS;
* scripts globais.

Preservar funcionamento dos templates existentes.

## Sidebar

Itens mínimos:

```text
Dashboard
Mercenários
Taverna
Missões
Dungeons
Construções
Inventário
Troca de Classe
Admin
Logout
```

Admin só aparece para admin.

Cada item deve estar preparado para ícone.

Se não houver ícones reais, usar placeholder visual.

## Topbar

Exibir:

* nome da guilda;
* usuário logado;
* nível da guilda;
* XP da guilda;
* ouro;
* notificações simples de ações pendentes.

Não quebrar páginas públicas como login/cadastro.

## Dashboard

Transformar dashboard em painel de jogo.

Exibir cards para:

* Guilda;
* Ouro;
* Recursos;
* Mercenários;
* Missões;
* Dungeons;
* Construções;
* Inventário;
* Taverna;
* Troca de Classe.

Cards devem ter ação/link.

## Mercenários

Melhorar a tela de mercenários.

Preferência por cards.

Cada mercenário deve exibir:

* avatar placeholder;
* nome;
* classe;
* raridade;
* nível;
* status;
* poder total;
* principais atributos;
* equipamentos principais;
* ação de detalhes/equipar, se existir.

Aplicar badge visual por raridade e status.

## Missões

Melhorar tela de missões.

Cada missão deve ser um card com:

* nome;
* descrição;
* duração;
* recompensa;
* chance;
* requisitos;
* seleção de grupo;
* ação iniciar;
* timer;
* receber loot.

Missões prontas para loot devem ficar destacadas.

## Dungeons

Seguir padrão de missões, mas com visual mais perigoso/importante.

Dungeons devem parecer conteúdo mais valioso.

Exibir requisitos e recompensas com clareza.

## Taverna

A Taverna deve ter tela temática forte.

Exibir:

* painel de contratação de Aprendiz;
* custo atual;
* chances;
* botão de contratar;
* painel de visitante especial;
* contador;
* expiração;
* gold disponível.

Preparar espaço para imagem/ícone da Taverna.

## Construções

Construções devem virar cards.

Cada card:

* nome;
* imagem/ícone placeholder;
* nível;
* efeito;
* custo;
* botão de upgrade.

## Inventário

Separar:

* materiais;
* equipamentos.

Materiais: cards compactos ou tabela visual.

Equipamentos: cards com raridade, tier, slot, nível mínimo, bônus base e RNG.

## Troca de Classe

Melhorar tela para comunicar:

* mercenário;
* classe atual;
* possíveis evoluções;
* requisitos;
* duração;
* custo;
* status/timer.

## Admin

Aplicar layout base.

Melhorar tabelas e formulários.

Não precisa ficar tão temático quanto o jogo, mas precisa ser organizado.

## Componentes CSS

Criar padrões:

```text
.game-card
.resource-card
.action-card
.status-badge
.rarity-badge
.primary-button
.secondary-button
.danger-button
.timer
.empty-state
.form-panel
.data-table
.avatar-placeholder
.icon-placeholder
```

## Classes de raridade

Criar classes CSS para:

```text
rarity-common
rarity-uncommon
rarity-rare
rarity-epic
rarity-legendary
rarity-mythic
```

## Classes de status

Criar classes CSS para:

```text
status-available
status-busy
status-in-progress
status-completed
status-failed
status-active
status-expired
status-hired
```

## Responsividade

Implementar responsividade básica.

Em telas menores:

* sidebar pode virar topo ou menu compacto;
* cards empilham;
* tabelas não quebram layout;
* botões continuam acessíveis.

## JavaScript

Manter JS simples.

Preservar timers existentes.

Se alterar timers, garantir que:

* botão de loot continua funcionando;
* backend continua validando;
* tela não quebra quando houver múltiplos timers.

## Arquivos esperados

Podem ser criados/alterados:

```text
app/templates/base.html
app/templates/dashboard.html
app/templates/mercenaries/*.html
app/templates/missions/*.html
app/templates/dungeons/*.html
app/templates/tavern/*.html
app/templates/buildings/*.html
app/templates/inventory/*.html
app/templates/class_change/*.html
app/templates/admin/*.html

app/static/css/main.css
app/static/css/theme.css
app/static/css/layout.css
app/static/css/components.css
app/static/css/game.css
app/static/css/admin.css

app/static/js/main.js
app/static/js/timers.js

app/static/img/placeholders/
app/static/img/classes/
app/static/img/mercenaries/
app/static/img/items/
app/static/img/buildings/
app/static/img/icons/
```

A estrutura pode ser ajustada conforme o projeto atual.

## Fora do escopo

Não implementar:

* nova mecânica;
* nova tabela de gameplay sem necessidade visual;
* upload de imagem;
* geração real de imagem;
* SPA;
* React;
* Vue;
* Angular;
* Tailwind obrigatório;
* dependência pesada;
* monetização;
* crafting;
* loja;
* trade.

## Validação manual esperada

Após implementar:

1. Rodar aplicação.
2. Login.
3. Ver dashboard novo.
4. Navegar pela sidebar.
5. Ver topbar com guilda/usuário/ouro.
6. Acessar Mercenários.
7. Validar cards/status/raridade.
8. Acessar Taverna.
9. Validar visual temático e timers.
10. Acessar Missões.
11. Validar cards, seleção e timers.
12. Acessar Dungeons.
13. Validar visual e timers.
14. Acessar Construções.
15. Validar cards e upgrade.
16. Acessar Inventário.
17. Validar materiais/equipamentos.
18. Acessar Troca de Classe.
19. Validar fluxo visual.
20. Acessar Admin com usuário admin.
21. Validar telas admin.
22. Testar responsividade básica reduzindo a largura da janela.
23. Confirmar que login/cadastro continuam funcionando.
24. Confirmar que nenhum fluxo principal quebrou.

## Critérios de conclusão

Considerar concluído quando:

* o jogo tiver aparência medieval/moderna;
* sidebar e topbar estiverem funcionando;
* dashboard estiver visualmente melhorado;
* mercenários estiverem em visual de equipe/roster;
* missões e dungeons estiverem em cards;
* taverna estiver temática;
* construções estiverem em cards;
* inventário separar materiais/equipamentos visualmente;
* troca de classe estiver clara;
* admin estiver organizado;
* raridades tiverem badges;
* status tiverem badges;
* estrutura para imagens existir;
* placeholders existirem ou estiverem preparados;
* timers continuarem funcionando;
* formulários continuarem funcionando;
* aplicação continuar rodando localmente.
