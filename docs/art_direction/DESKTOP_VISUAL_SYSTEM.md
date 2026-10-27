# Direção de arte — Guild Idle Manager Desktop Offline

**Versão:** 1.0 · 26/10/2026  
**Status:** proposta visual pronta para revisão e integração pelo DEV  
**Nome da linguagem:** Sala de Comando

## Ideia central

A guilda é um lugar habitado: pedra fria, madeira usada, luz de lanterna e mapas de campanha. A interface é a mesa de comando sobre esse mundo. A arte ambiental fornece memória e atmosfera; números, timers, decisões e feedback ficam em painéis nítidos de HTML. Evitar molduras ornamentais em todos os cards e texturas atrás de textos longos. A fantasia aparece no enquadramento, na tipografia de títulos, nos medalhões já existentes e nas cores de estado.

As prévias são arquivos locais: [`design/preview/index.html`](../../design/preview/index.html), [`roster.html`](../../design/preview/roster.html), [`operations.html`](../../design/preview/operations.html), [`tavern.html`](../../design/preview/tavern.html) e [`inventory.html`](../../design/preview/inventory.html). Os números e nomes nas prévias são ilustrativos; não alteram mecânicas nem conteúdo do jogo.

## Princípios de leitura

1. **Uma ação principal por área.** O salão prioriza operações prontas para coleta. Timer em andamento é informativo. Ações irreversíveis recebem confirmação consistente com a aplicação.
2. **O estado é explícito.** Cor acompanha palavra, nunca a substitui: “Pronta para coleta”, “Em exploração”, “Disponível”. Timer usa algarismos tabulares e rótulo legível.
3. **Economia sempre visível.** Ouro fica no topo; madeira, minério e cristais aparecem juntos abaixo do hero e nos custos contextuais. A campanha local exibe estado de salvamento sem tratar o usuário como uma conta web.
4. **Arte em área controlada.** Imagem é fundo de hero e cards de narrativa. Listas, slots, tabelas e formulários usam superfícies sólidas. Nenhum texto essencial deve ser embutido em imagem.
5. **Janela estreita é jogo completo.** Navegação horizontal rolável acima do conteúdo, cartões em coluna, recursos em 2×2, alvo mínimo de 40 px. Não depender de hover.

## Tokens visuais

| Papel | Token | Valor | Uso |
|---|---|---:|---|
| Fundo | `--bg` | `#101A1D` | janela |
| Navegação | `--rail` | `#0B1316` | barra lateral |
| Superfície | `--surface` | `#172327` | cartões de operação |
| Superfície elevada | `--surface-hi` | `#203035` | seleção, painéis |
| Borda | `--border` | `#375057` | estrutura discreta |
| Texto | `--text` | `#F1EADB` | títulos e valores |
| Secundário | `--muted` | `#AEBFC0` | descrições |
| Fraco | `--dim` | `#869B9E` | metadados maiores; evitar corpo pequeno |
| Ouro | `--gold` | `#E6B965` | ação principal, progressão, tesouro |
| Ouro claro | `--gold-soft` | `#F5D798` | link sobre fundo escuro |
| Turquesa | `--teal` | `#68C3B5` | foco de sistema, informação |
| Sucesso | `--green` | `#9BD498` | pronto, disponível, salvo |
| Atenção | `--red` | `#E38B75` | erro, ação destrutiva |
| Azul | `--blue` | `#82BED9` | exploração, raro |
| Violeta | `--purple` | `#C6A5EB` | épico, cristais |

Preferir texto claro sobre superfícies escuras. Botão dourado usa texto escuro `#152025`. Contraste final deve ser aferido no componente real, inclusive foco, disabled e hover. Não usar opacidade em texto essencial. Contorno de foco de 3 px em `#F5D798`, com afastamento de 3 px.

**Escala:** 4, 8, 12, 16, 24, 32, 40 px. Área de conteúdo com respiro de 22–44 px; cards separados por 14–16 px; borda de 1 px e raio de 8–12 px. Hero pode ter borda interna ornamental única; cards de dados não precisam dela.

**Tipografia offline:** títulos `Georgia` (serifada do Windows) e interface `Segoe UI` (Windows), com fallbacks `Times New Roman` e `Tahoma`/sans-serif. Essas fontes vêm licenciadas com o Windows 10/11; **não redistribuir os arquivos de fonte** no instalador. Não há `@import`, CDN ou fonte remota. Se uma distribuição futura não incluir essas fontes, escolher e empacotar uma família OFL com licença incluída. Títulos 28–42 px; seção 25–27 px; corpo 13–15 px; metadados 10–12 px em peso alto e contraste suficiente. Valores usam `font-variant-numeric: tabular-nums`.

## Raridade e status

| Raridade existente | Cor de borda/texto | Apresentação |
|---|---|---|
| Comum | `#B9C4C0` | “Comum” em badge discreto |
| Incomum | `#9BD498` | verde; texto completo |
| Raro | `#82BED9` | azul; texto completo |
| Épico | `#C6A5EB` | violeta; texto completo |
| Lendário | `#E6B965` | ouro; texto completo |
| Mítico | `#EEA7C2` | rosa; texto completo |

Status de missão: “Disponível”, “Em andamento”, “Pronta para coleta”, “Concluída”, “Bloqueada”. Status de mercenário: “Disponível”, “Em missão”, “Em masmorra”, ou estado real equivalente. Reutilizar os valores do backend e traduzir apenas no componente. Uma borda superior pode indicar raridade em cards; nunca aplicar apenas brilho ou cor sem o badge textual.

## Componentes e navegação

- **Trilho principal:** comando (salão, mercenários, missões, masmorras), domínio (taverna, construções, inventário, ferreiro, mercado, docas) e registros (classes, profissões, códex, guia). Preservar todos os destinos atuais; o agrupamento reduz varredura visual. Em desktop offline, substituir login/logout/admin por campanha e salvar/gerenciar conforme o GDD.
- **Barra superior:** campanha e localização, ouro, estado de save. Evitar data de usuário e sessão web. Estado “salvando” e falha de gravação precisam de texto e ação contextual.
- **Hero do salão:** progressão da guilda e próxima decisão; não usar como painel de dez métricas. Imagem decorativa com gradiente protetor. Em 420 px, usar gradiente vertical e conteúdo abaixo da imagem.
- **Operação:** categoria, título, grupo/recomendação, estado e ação. Coletar manualmente continua explícito. Timer é texto de apoio e não promete auto-coleta.
- **Quadro de operações denso:** missão selecionada ao lado de lista curta; estados pronta, em andamento e bloqueada aparecem juntos para comparação. Detalhe mostra companhia, espólios e ação de coleta. Masmorra usa a mesma gramática, com recomendação, progresso e requisito bloqueante. Preparação do próximo grupo é um bloco separado para não confundir coleta com partida.
- **Card do mercenário:** retrato ou medalhão, nome, classe, nível, raridade, poder, disponibilidade, equipamento e link de ficha. Dados de atributos e slots continuam na ficha; layout não altera regras de grupo.
- **Taverna:** oferta especial concentra retrato, expiração, vagas, custo e ação. Recrutamento comum e em lote têm blocos menores; custo total e confirmação devem vir das regras atuais. Sem oferta ou taverna não construída exigem substituição textual completa do bloco, não um retrato vazio.
- **Construção:** sprite desktop 128 px, nível atual, benefício/custo contextual e ação. Estado bloqueado mostra requisito real em texto.
- **Inventário:** usar os PNGs do pacote desktop em slot de 58 px; quantidades, raridade e equipamento único distinguíveis. Não fazer cada item parecer uma carta lendária.
- **Inventário denso:** resumo e filtros acima de uma grade compacta; detalhe de item em painel separado. O KPI do resumo chama-se **Equipamentos**. Cada nome de item ocupa até duas linhas estáveis e oferece o título completo no tooltip; não depender da abertura do detalhe para identificá-lo. Equipamentos únicos mostram instância, atributos, proprietário e slots; materiais mostram quantidade acumulada. Refinar/desmontar requerem custo, requisitos e confirmação reais.
- **Formulários e diálogos:** superfícies sólidas, labels visíveis, validação junto ao campo, mensagens de falha sem texto técnico. Confirmar descarte/exclusão; salvar campanha e migrar dados requerem feedback claro.
- **Aviso offline:** bloco de retorno com período creditado, recursos e limite aplicado, sem imagem atrás de números. Estado de anomalia do relógio usa explicação simples e caminho de recuperação, conforme GDD.

## Assets e prioridades

O pacote final em `app/static/assets/desktop/` reúne quatro ilustrações WebP, seis retratos de arquétipo, 92 sprites originais com saídas PNG de 64/128/512 px e um ícone Windows `.ico`. Os 92 masters locais, em `design/masters/`, são a origem portátil dos sprites. A arte foi gerada com a skill `imagegen`, revisada em tamanhos pequenos e exportada para a interface. Nenhum texto foi incorporado às imagens. `manifest.json` documenta caminhos, papéis e mapeamento semântico.

As novas imagens não usam referência visual de terceiros. O inventário em [`LEGACY_ASSET_PROVENANCE.md`](LEGACY_ASSET_PROVENANCE.md) registra os ícones legados como **procedência não verificada para distribuição**; eles não são dependências deste pacote desktop. Os retratos representam arquétipos, não a identidade literal de cada mercenário.

**Cobertura:** 26/26 códigos de classe têm emblemas individuais. Os grupos de ícones presentes no catálogo de itens, os prédios, materiais, missões, profissões e biomas conhecidos têm resolução explícita no manifesto desktop. Grupos semânticos podem compartilhar o mesmo sprite quando a representação visual é equivalente, como `xp` e `guild_xp`; nenhum grupo conhecido depende de fallback genérico. O relatório [`SPRITE_COVERAGE.md`](SPRITE_COVERAGE.md) é reconstruído a partir das fontes reais do jogo.

**Próxima prioridade, se conteúdo pedir:** cenas menores para Mercado e Docas e ilustrações de capítulos. Qualquer novo conteúdo deve entrar primeiro nos catálogos do jogo e depois passar pelo verificador, que falha quando um código real não tem mapeamento.

**Fallbacks:** se imagem ambiental falhar, manter cor sólida e título/estado em HTML; se retrato falhar, usar o emblema da classe com nome visível. Para códigos futuros ainda não mapeados, usar o fallback semântico do manifesto e manter nome, tipo e raridade em texto. `alt=""` para decoração; `alt` útil para retrato/ícone que transmita identidade. O nome e a raridade nunca dependem do `alt` ou do bitmap.

## Integração para DEV

1. Incluir um CSS desktop separado após o CSS atual ou migrar tokens progressivamente. Não colar a prévia como template de produção; ela contém dados fictícios e links demonstrativos.
2. Resolver as quatro ilustrações, seis retratos e 92 sprites por `manifest.json` no helper de static/Jinja. Expor `width`/`height`, `loading="lazy"` para cards abaixo da dobra; hero prioritário. Usar `background-image` apenas onde a imagem for decorativa. Escolher 64 ou 128 px conforme o slot; 512 px é master de exportação.
3. Manter as rotas e ações existentes e trocar os blocos de interface por partes: shell, dashboard, operações, roster, taverna. As condições de bloqueio, timers, coleta e custo continuam vindas do backend.
4. Na versão desktop, resolver o menu de campanhas, estado de save e ausência de login/admin com o DEV. Os previews mostram a intenção visual sem afirmar esses controles como implementados.
5. Verificar em 1440×900, 1024×768, 760×900 e 420×900, além de teclado, zoom 200%, WebView2 offline, alto contraste e ausência de asset. Conferir textos longos PT-BR e dados extremos.

## Prompts finais usados no imagegen

1. **Salão:** guild hall ao entardecer, mesa de planejamento, mapa, lanternas, bandeiras e vista de fortaleza; 16:9, esquerda escura para HTML; teal, brass, parchment; sem texto/UI.
2. **Taverna:** interior aconchegante e funcional, aviso de recrutamento, aventureiros ao fundo e chuva na janela; esquerda escura; teal e âmbar; sem texto/UI.
3. **Masmorra:** escadaria em ruínas abobadadas, runas ciano, tochas distantes, profundidade arquitetônica; 16:9, contraste controlado; sem texto/UI.
4. **Retrato:** mercenária arqueira de capa verde e couro prático, expressão atenta, 3/4, crepúsculo; retrato 4:5, leitura em card; sem texto/UI.
5. **Selo:** escudo de ferro frontal com estrela bússola de latão e centro esmaltado teal; silhueta legível em 64/128 px; fundo transparente, sem texto/UI.
6. **Expedição:** mapa enrolado com agulha de bússola e selo teal; ícone frontal e compacto em 64/128 px; fundo transparente, sem texto/UI.
7. **Masmorra:** porta de pedra com runa de fechadura ciano e tocha âmbar; ícone frontal e compacto em 64/128 px; fundo transparente, sem texto/UI.

As descrições acima resumem os primeiros prompts de geração. As classes, construções, itens, materiais, estados, biomas e nove símbolos adicionais de catálogo seguiram a mesma direção: objeto único, silhueta legível em 64 px, metal envelhecido, teal contido, fundo transparente e ausência de texto. Os masters finais estão no projeto; os arquivos temporários da ferramenta não são necessários para regenerar as saídas. Para cobertura e comandos de exportação, consultar [FINAL_ASSET_HANDOFF.md](FINAL_ASSET_HANDOFF.md) e [SPRITE_COVERAGE.md](SPRITE_COVERAGE.md).
