# 13 - MVP 011 - UX/UI Medieval Modernization

## Objetivo

Modernizar a UX/UI do Guild Idle Manager com uma identidade visual medieval/fantasia, mantendo o sistema funcional, organizado e preparado para uso futuro de imagens, ícones, avatares e assets visuais.

Este MVP deve melhorar a experiência visual e a navegação do jogo sem alterar regras centrais de negócio.

## Direção visual

O jogo deve ter uma interface moderna, mas temática medieval.

Referências conceituais:

* guilda medieval;
* taverna;
* pergaminhos;
* couro;
* pedra;
* metal;
* brasões;
* runas;
* fantasia RPG;
* painel de gestão de jogo.

Evitar aparência genérica de sistema administrativo corporativo.

A interface deve parecer um jogo web, não um CRUD.

## Princípios de UX

Priorizar:

* navegação clara;
* leitura rápida;
* hierarquia visual forte;
* cards informativos;
* botões de ação evidentes;
* feedbacks claros;
* status visuais;
* consistência entre telas;
* responsividade básica;
* base preparada para assets futuros.

## Não quebrar regra de negócio

Este MVP é visual/UX.

Não alterar regras de negócio sem necessidade.

Não mudar cálculos.

Não mudar multi-tenancy.

Não mudar regras de missão, dungeon, taverna, classe, equipamento ou admin, salvo ajustes mínimos para exibir melhor os dados existentes.

## Estrutura visual esperada

Criar ou refatorar o layout base para conter:

* sidebar/menu lateral;
* header/topbar;
* área principal de conteúdo;
* cards de resumo;
* componentes reutilizáveis;
* badges de status;
* botões temáticos;
* mensagens de feedback;
* padrões para tabelas;
* padrões para formulários;
* suporte a ícones;
* suporte a imagens/avatares.

## Sidebar

A sidebar deve ser o menu principal do jogo.

Itens esperados:

* Dashboard
* Mercenários
* Taverna
* Missões
* Dungeons
* Construções
* Inventário
* Troca de Classe
* Admin, apenas se usuário for admin
* Logout

Cada item deve estar preparado para exibir ícone.

Se não houver biblioteca de ícones, usar placeholders visuais ou emojis temporários com fácil substituição futura.

Preferência:

* criar estrutura CSS/classes para ícones;
* evitar acoplar visual a texto fixo;
* permitir trocar por SVG/PNG futuramente.

## Header / Topbar

O header deve exibir:

* nome da guilda;
* usuário logado;
* nível da guilda;
* XP da guilda;
* ouro atual;
* aviso de missão/dungeon/troca pronta, se existir;
* ação de logout, se não estiver na sidebar.

## Dashboard

O Dashboard deve virar a home principal do jogo.

Exibir cards de resumo:

* Guilda
* Ouro
* Recursos
* Mercenários
* Missões
* Dungeons
* Construções
* Inventário
* Taverna
* Troca de Classe

Cada card deve ter:

* título;
* valor principal;
* descrição curta;
* ação/link.

Exemplo:

```text
Mercenários
12 / 15
Ver equipe
```

## Mercenários

A tela de mercenários deve parecer uma tela de roster/equipe.

Cada mercenário deve ser exibido em card ou tabela visual aprimorada contendo:

* nome;
* avatar placeholder;
* classe;
* raridade;
* nível;
* status;
* poder total;
* atributos principais;
* equipamentos;
* ação de detalhes/equipar.

Preparar espaço visual para:

* avatar do mercenário;
* ícone da classe;
* borda/cor por raridade;
* badge de status.

## Avatares e imagens

O sistema deve nascer preparado para imagens, mesmo que inicialmente use placeholders.

Criar padrão para:

```text
/static/img/
  placeholders/
  classes/
  mercenaries/
  items/
  buildings/
  icons/
```

Sugestão:

* usar placeholder para avatar de mercenário;
* usar placeholder para ícone de classe;
* usar placeholder para item/equipamento;
* usar placeholder para construção.

Não precisa gerar imagens reais neste MVP.

O importante é a estrutura estar pronta.

## Ícones de classe

Cada classe deve poder ter ícone visual.

Se não houver campo no banco, avaliar adicionar ou preparar por código/template:

```text
class_icon
image_path
icon_path
```

Se for simples e seguro, adicionar campos configuráveis no admin de classes.

Se for complexo, usar mapping temporário no frontend/CSS e preparar estrutura para evolução futura.

## Raridade visual

Aplicar padrão visual por raridade.

Raridades:

```text
common
uncommon
rare
epic
legendary
mythic
```

Cada raridade deve ter:

* badge;
* borda ou detalhe visual;
* classe CSS própria.

Não precisa usar cores gritantes. Deve manter o tema medieval.

## Status visual

Status devem virar badges.

Exemplos:

```text
available -> Disponível
busy -> Ocupado
in_progress -> Em andamento
completed -> Concluído
failed -> Falhou
active -> Ativo
expired -> Expirado
hired -> Contratado
```

## Missões e Dungeons

Telas de missões e dungeons devem usar cards.

Cada card deve exibir:

* nome;
* descrição;
* duração;
* recompensa;
* chance base;
* requisitos;
* tamanho do grupo;
* seleção de mercenários;
* chance estimada;
* botão de iniciar;
* timer;
* botão de receber loot.

O timer deve ser visualmente claro.

Missões prontas para loot devem receber destaque.

## Taverna

A Taverna deve ser uma das telas mais temáticas do jogo.

Exibir:

* card de contratação de Aprendiz;
* custo atual;
* chance de raridade;
* botão de contratar;
* card de visitante especial;
* contador para próxima aparição;
* contador de expiração;
* gold da guilda;
* nível da Taverna.

Visual deve remeter a uma taverna medieval.

## Construções

A tela de construções deve exibir cards para cada construção.

Cada card:

* nome;
* nível atual;
* efeito;
* custo do próximo upgrade;
* botão de evoluir;
* imagem/ícone placeholder;
* status ativo/inativo.

## Inventário

Separar visualmente:

* materiais;
* equipamentos.

Materiais podem ser cards pequenos ou tabela visual.

Equipamentos devem ter cards com:

* nome;
* raridade;
* tier;
* slot;
* nível mínimo;
* bônus base;
* bônus RNG;
* status equipado/livre.

## Troca de Classe

A tela de troca de classe deve ter visual de ritual/treinamento.

Exibir:

* mercenário selecionado;
* classe atual;
* opções de evolução;
* requisitos;
* custo;
* duração;
* status da troca em andamento;
* timer;
* botão de concluir.

## Admin

O admin pode continuar mais simples, mas deve receber padrão visual coerente.

Não precisa ficar tão temático quanto o jogo, mas deve:

* usar o layout base;
* ter navegação clara;
* manter tabelas/formulários legíveis;
* ter cards ou seções;
* proteger rotas admin;
* manter feedbacks claros.

## CSS e organização

Criar ou reorganizar CSS em estrutura mais sustentável.

Sugestão:

```text
/static/css/
  main.css
  layout.css
  components.css
  theme.css
  game.css
  admin.css
```

Se preferir manter um arquivo único por simplicidade, garantir organização por seções comentadas.

## JavaScript

Manter JavaScript simples.

Usar apenas para:

* timers;
* interações leves;
* previews/seleções;
* melhoria visual.

Não transformar o projeto em SPA.

Não adicionar React/Vue/Angular.

## Responsividade

Garantir responsividade básica:

* sidebar adaptável;
* cards empilhando em telas menores;
* tabelas minimamente utilizáveis;
* botões acessíveis no mobile;
* sem quebra visual grave.

## Acessibilidade mínima

Garantir:

* contraste aceitável;
* botões identificáveis;
* labels em formulários;
* foco visual básico;
* textos legíveis.

## Liberdade criativa do Codex

O Codex pode propor e aplicar melhorias visuais além do descrito, desde que:

* não quebre regras de negócio;
* não adicione dependências pesadas sem necessidade;
* não transforme o frontend em SPA;
* mantenha o projeto simples de rodar;
* preserve multi-tenancy;
* preserve rotas e fluxos principais;
* mantenha templates Jinja2.

## Fora do escopo

Não implementar nesta task:

```text
novas mecânicas de gameplay
novas regras de classe
novos cálculos de combate
novas dungeons
novas missões
crafting
loja
trade
monetização
sistema completo de assets
upload de imagem
geração real de imagens
SPA frontend
```

## Critério de aceite visual

O MVP-011 estará concluído quando:

* o jogo tiver identidade visual medieval/moderna;
* dashboard parecer tela de jogo;
* sidebar/header estiverem padronizados;
* mercenários tiverem cards/visual melhorado;
* missões/dungeons tiverem cards e timers claros;
* taverna estiver temática;
* inventário diferenciar materiais e equipamentos;
* construções estiverem em cards;
* troca de classe estiver visualmente clara;
* admin estiver organizado;
* raridades/status tiverem badges;
* estrutura para imagens/ícones estiver pronta;
* aplicação continuar rodando localmente;
* nenhum fluxo principal for quebrado.
