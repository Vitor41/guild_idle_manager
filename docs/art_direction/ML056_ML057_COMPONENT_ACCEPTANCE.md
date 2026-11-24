# ML-056/057 — componentes e aceite visual

Data: 2026-11-24. Complemento implementável de `ML052_ML055_VISUAL_SPEC.md`, do relatório ML-053 e dos dois lotes aprovados em `ML-BUGS.md`. Não cria tela, regra, terceiro lote ou dependência de arte nova. Não é aprovação visual da implementação. A próxima validação usa SHA do DEV e perfis sintéticos; nenhuma nova navegação no save real foi feita para produzir este documento.

## Aplicação e limites

ML-056 responde por estados, requisitos e decisões; ML-057, pela composição, navegação e confiabilidade das consultas. Quando o mesmo componente aparece nos dois, implementar uma vez e conferir os dois critérios. F15 continua em ML-052, F21 em ML-055. Este complemento não reabre decisões já especificadas para drops ou central de eventos.

Preferir macros/partials, classes, helpers e assets existentes. Extrair um componente compartilhado quando houver repetição real; não é necessário criar framework de componentes ou reestruturar rotas. Manter formulários, campos, ações e identificadores usados pelos contratos atuais. Estado e valores vêm do servidor; o frontend apresenta, não reconstrói elegibilidade ou economia. Mudança visual não autoriza habilitar ação proibida, mudar regra de confirmação ou criar confirmação extra.

## Padrões compartilhados

Os códigos C01–C12 abaixo identificam padrões de apresentação, não novas telas nem classes CSS obrigatórias. Os valores são padrão de implementação; exceção local só é necessária quando conteúdo real não cabe, mantendo os critérios de leitura. Reutilizar os tokens do sistema Sala de Comando, Georgia nos títulos e Segoe UI na interface; nenhuma fonte remota.

### C01 — estrutura, grade e cabeçalho

| Elemento | Padrão concreto |
| --- | --- |
| Conteúdo | Padding lateral 24 px em ampla, 16 px em reduzida; 16–24 px entre seções. Usar o contêiner já existente; não criar uma segunda largura máxima dentro de cada rota |
| Painel | Padding 16 px, 24 px apenas para leitura longa; borda 1 px, raio do sistema. Dentro do card, 8 px entre campos relacionados e 12–16 px entre grupos |
| Grades de decisão | Largura **útil do contêiner** ≥960 px: até 3 colunas; 640–959: 2; abaixo de 640: 1. Intervalo 16 px. Não usar o viewport inteiro como largura disponível quando há sidebar |
| Grades de acervo | Cards de item com mínimo útil de 240 px; preencher apenas o número que cabe, até 5 colunas. Mercenários: mínimo 280 px, até 4. Um card isolado não ocupa toda a largura sem necessidade |
| Raridades | Seis entradas: 3×2 a partir de 900 px úteis, 2×3 entre 560–899 e 1 abaixo. Evitar 5+1 |
| Cabeçalho de ação | Ícone 40 px + título/contexto, com ações próximas em grupo próprio. Padding 16–24 px; altura pelo conteúdo, sem min-height ornamental. Arte existente pode permanecer contida, sem aumentar a altura para preencher o fundo |
| Topbar | Identidade em grupo; nível/XP/tesouro em grupo; estamina/ajuda em grupo. Gap 8–12 px; nomes podem quebrar, números/unidades não. Remover métricas duplicadas do hero quando não ajudam a ação atual. Preservar recursos e controles existentes |
| Altura de cards | Cards comparáveis podem alinhar ações pela base. Painéis independentes usam altura natural: oferta especial vazia e construção não esticam à altura do formulário da Taverna |

Aplicar `min-width: 0` aos filhos de grid/flex que contêm nomes ou valores longos; não usar largura fixa de tabela/card para resolver um título. Alterar grades com media queries locais ou container queries suportadas pelo runtime existente; nenhum polyfill novo é exigido. Preservar o comportamento do shell reduzido já estabelecido, inclusive posicionamento relativo/sticky do cabeçalho por breakpoint. O offset de âncora usa a altura real após quebra/zoom, nunca uma altura presumida.

### C02 — tipografia e hierarquia

Título de página 28–32 px, seção 22–24 px, card 18–20 px; corpo 14 px com entrelinha 1,45–1,55; metadado 12–13 px com entrelinha ≥1,35. Valores contextuais 16–20 px, sem competir com o título. Manter `letter-spacing: 0` em todos os textos, inclusive eyebrow; maiúsculas apenas no eyebrow curto, nunca no motivo de bloqueio ou num parágrafo. Valores e tempos com algarismos tabulares; números comparáveis alinhados à direita. Usar formatação PT-BR compartilhada, incluindo separadores e unidades.

Título de item pode quebrar em mais de duas linhas; não cortar informação necessária por ellipsis sem alternativa acessível. Evitar fazer o nome inteiro dourado e negritar todos os demais campos. Raridade usa borda/acento e rótulo existentes; a descrição permanece `--text`/`--muted`. Texto essencial não recebe opacidade do card. Não reduzir fonte para encaixar uma grade que deveria perder coluna.

### C03 — estado e capacidade

Uma indicação operacional por card/linha, com ícone + rótulo; raridade é outra dimensão. O azul de atividade abaixo vale para o estado local do card e não substitui a bolinha de menu ML-040/055: amarelo em andamento, verde para ação disponível/resultado pronto, com precedência do verde nos estados mistos. Não repetir `Resgatada` no cabeçalho e no rodapé como se fossem dois estados. Categorias como Material/Progressão usam texto pequeno, não precisam de pílula. Bordas de raridade não devem sobrescrever seleção/foco.

| Estado | Apresentação |
| --- | --- |
| Livre/sem tarefa | Ícone semântico + texto neutro; não declarar disponibilidade de equipe se só o posto está livre |
| Disponível | Verde com check/rótulo quando há ação realmente elegível; teal para informação/contexto de seleção |
| Em andamento | Azul + relógio + nome do estado e tempo autoritativo |
| Pausado | Ouro/âmbar do sistema + pausa + motivo. Timer ativo não conta para baixo; tempo preservado pode ser mostrado como tal |
| Pronto para ação/coleta | Verde + check + ação real; não confundir com histórico já coletado |
| Bloqueado | Cadeado + motivo curto; texto legível. Vermelho apenas para falta impeditiva/erro, não para toda progressão ainda bloqueada |
| Falha/erro | Vermelho + ícone e mensagem específica. Não substituir dado indisponível por zero ou lista vazia |

Capacidade usa `Ocupação N/limite` ou `Vagas livres N`; não `Vagas N/limite` quando N são ocupados. Barra acompanhada dos números e nome; cheia: `Armazém cheio` e ícone de atenção. No resumo regional, listar famílias com designação pertinente, inclusive pausadas, e disponibilizar acesso à gestão completa. Não inventar designação nas famílias omitidas anteriormente.

### C04 — custos, requisitos e ações

Ordem no bloco de decisão: seleção → quantidade → total/duração → requisitos ou motivo atual → ações. Gap 8 px entre motivo e controle; 12–16 px até o grupo anterior. Custos em pares ícone/valor com nome acessível, sem frases de zeros comprovados. Dado ausente permanece indisponível. Insumo insuficiente mostra `atual/necessário` e ícone de falta; não depende de vermelho. Valores unitário e total ficam identificados, sem recalcular preço fora do mecanismo existente.

Botão principal dourado para ação contextual; consultar detalhes e voltar são secundários; remoção/manutenção não dominam o item. Controles têm altura/alvo ≥40 px e gap ≥8 px. A ação indisponível mantém seu motivo ao lado, mesmo se o botão disabled não recebe foco. Campo vazio não comunica prontidão. A elegibilidade segue o contrato atual e é revalidada no servidor; para insuficiência conhecida, não desenhar aparência de ação pronta. Reroll não depende de vaga de contratação.

Quando dois caminhos válidos coexistirem, manter ambos claros; no preparo, a disponibilidade depende da composição e do estado real, sem trocar silenciosamente de modo. Confirmações existentes preservam custo/consequência antes do envio. Durante envio, o controle específico mostra processamento e evita repetição; erro de sincronização não confirma sucesso ou reabilita snapshot obsoleto.

### C05 — atributos e equipamento

Usar pares compactos ou tabela para atributos; reservar badges para raridade, condição e refino. Tabela base/bônus/total: primeira coluna flexível, três numéricas proporcionais, padding 8–12 px. Sem min-width maior que as quatro colunas exigem em ampla. Abaixo de 480 px úteis, uma linha por atributo com seus três valores rotulados; pode manter tabela com rolagem local quando os dados adicionais justificarem, nunca cortar colunas.

Slot: ícone 40–48 px, tipo, nome, raridade/refino e consulta; remover em estilo secundário. Vazio mostra tipo + `Vazio`, sem falsa raridade. Reutilizar o detalhe de equipamento para Docas, inventário e elenco; abrir detalhe é consulta. Não ligar remoção/equipar ao título do item. Raridade e descrição concordam com a fonte canônica daquele contexto; F33 exige diagnóstico antes da alteração. Não substituir palavras em lore ou dados salvos para ajustar texto.

### C06 — preparados e reforços

Aplicar integralmente a seção correspondente de `ML052_ML055_VISUAL_SPEC.md` como parte de ML-056. Linha selecionável com checkbox real, ícone de classe 32–40 px, nome, condição e selo curto. Dois grupos: `Equipe preparada` e `Disponíveis para reforço`; mostrar o segundo apenas quando há contexto de preparação. Sem preparo existente, manter o seletor normal e rótulos naturais de disponibilidade.

Preparado é identidade persistida; selecionado é decisão atual. Preparado indisponível continua identificado; reforço só recebe selo ao ser selecionado. Borda/fundo teal distingue seleção de raridade, sem depender só da cor. Resumo antes das ações mostra N/limite, preparo/suprimento e incompatibilidade atual. Ao remover preparado/adicionar reforço, manter a identidade original e atualizar o motivo do modo com suprimento. Sem parágrafo permanente de tutorial. Não alterar ML-043, consumir kit ao selecionar ou iniciar por expansão.

### C07 — produção e histórico

Produção: material/receita com ícone 32 px, condição, estoque, quantidade, total e duração juntos. Motivo de pausa ao lado da tarefa; sem próximo ciclo ativo contraditório. Bancada bloqueada ocupa apenas título, cadeado e requisito, sem form e sem opacidade no texto inteiro. Manter a ordem das bancadas.

Histórico: resultado + nome + data no resumo, recompensas principais em uma faixa curta, `Ver detalhes` expansível. Dentro: experiência/evolução/itens/contribuições com títulos apenas quando há conteúdo. Recompensa ainda pendente e sua ação nunca ficam escondidas como histórico coletado. Serviços do Ferreiro em linhas `item ×N → retorno`, com quantidades alinhadas, em vez de pílulas de frases.

### C08 — tabelas e relatórios

Cabeçalhos semânticos, números à direita, nome/região próximos, linha da própria guilda com rótulo além da cor. Em largura útil ≥900 px, tabela completa; abaixo, manter rolagem **local** identificável, com cabeçalho e primeiro campo legíveis. Não criar uma segunda representação com regras diferentes. Quando já houver cards responsivos, podem ser preservados desde que cada número mantenha rótulo e ordem. O documento inteiro não rola horizontalmente.

Relatório: deltas antes→depois com sinal textual e ícone; se melhora/piora depende do indicador, não atribuir verde a todo aumento. Resumo por região/guilda e tabela de planejadas/entradas/resultados; detalhes técnicos expansíveis. Nunca somar categorias distintas como participação resolvida nem inferir motivo do zero. `Não registrado` permanece diferente de `0`. Slugs e códigos de raridade recebem os mapeamentos PT-BR existentes.

### C09 — modais, popovers e retorno

Modal de atividade/relatório: largura existente até 760 px quando o conteúdo exigir; limite horizontal `calc(100% - 32px)`; altura máxima `calc(100dvh - 32px)` com fallback suportado. Cabeçalho com título/fechar fora da área de rolagem; corpo rolável com padding 16–24 px; rodapé sem cobrir requisitos. Se o footer tiver altura variável, pode continuar no fluxo do corpo desde que o título/fechar permaneçam acessíveis. Evitar dois scrolls verticais concorrentes dentro do modal.

Abrir move foco para título/controle seguro; Tab fica no diálogo, Escape fecha e retorna ao acionador ainda existente. Se o acionador deixou de existir após atualização, retornar ao título do grupo equivalente. Âncoras usam altura medida da topbar + 12 px de respiro; título e foco visíveis após navegação parcial, expansão e zoom. Fechar nunca aceita convite ou executa gameplay.

Popover de cabeçalho: um aberto por vez, largura até 360 px e no máximo viewport menos 32 px; reposicionar para permanecer dentro da janela. Escape/fora fecham e foco retorna; abrir o segundo fecha o primeiro. Conteúdo importante também acessível por clique/teclado/toque. Não alterar a ativação separada de Modo Offline.

### C10 — filtros, consulta e ciclo de vida

Filtros com labels persistentes, gap 12 px, campos em grid mínimo 180 px; busca ocupa espaço restante e ação compacta. Em <640 px úteis, empilhar; em 390 px, input/select com largura total e sem coluna residual estreita. `Limpar filtros` é secundário, não ocupa o destaque dourado principal. Mostrar total/estado da consulta abaixo dos filtros; resultado vazio não é erro.

Preservar termo, categoria, filtro e posição ao voltar do detalhe. A inicialização após troca de root deve ser idempotente; cada envio gera um resultado atual, sem resposta antiga sobrescrever consulta nova. Carregamento termina em conteúdo, vazio ou erro com Tentar novamente. Exportação usa a mesma fonte do Guia, com progresso/erro/cancelamento, sem captura de dados privados. Repro F34 precisa demonstrar o defeito e a correção com navegação direta e parcial, não apenas validar funções isoladas.

### C11 — leitura, entrada e informação auxiliar

Campanhas: Continuar principal; manutenção secundária agrupada; exclusão visualmente separada. Recuperação mantém nome seguro e motivo necessário, identificador técnico em detalhe quando não for o único identificador disponível. Resumo de ausência prioriza total/tempo reconhecido; decomposição e limite sem duplicação.

Guia permite texto extenso; organizar índice/retorno no componente existente e remover painéis aninhados sem função. Classes por etapa e raridades com comparação estável. Tutorial mantém 13 etapas informativas e seus links; ícone existente do assunto, alvos padronizados e nenhum novo botão de gameplay. Atualizações destaca versão/canal/verificar; provedor técnico subordinado, sem novo atualizador. Rótulos de link sempre descrevem seu destino real.

### C12 — acessibilidade e evidência

Foco do sistema: 3 px dourado claro, afastamento 3 px; nenhum contorno cortado por overflow. Texto comum com contraste ≥4,5:1, texto grande ≥3:1; borda/estado essencial de controle ≥3:1 contra adjacência. Medir cores compostas reais, incluindo fundo/hover/disabled, sem alegar medição pela captura. Redução de movimento elimina pulsação/transição ornamental; timers continuam legíveis. Erros relevantes usam anúncio acessível; polling sem mudança não repete anúncios.

## Matriz Fxx → componente → critério observável

Cada linha é um ponto de aceite, não uma rodada estética independente. Evidência pode reunir várias linhas na mesma captura/fluxo. Números, custos, requisitos, composição, ranking e recompensas devem permanecer iguais aos dados autoritativos.

| Fxx / lote | Componente | Critério visual observável |
| --- | --- | --- |
| F01 / 057 | C01, C10 | Entrar em Oficinas/Vigília/Guia/Atualizações e voltar preserva marca, sprites, Tesouro e formato PT-BR; repetir navegação/polling não duplica UI |
| F02 / 057 | C11 | Campanhas sem breadcrumb de Coleta; Continuar primeiro, manutenção agrupada, recuperação com motivo legível |
| F03 / 057 | C01–C02 | Nome longo não empurra métricas para fora; header cabe em reduzida/zoom e offset acompanha sua altura |
| F04 / 057 | C09 | Abrir oferta/detalhe por âncora deixa título/foco abaixo da topbar com respiro |
| F05 / 057 | C09 | Tesouro→ajuda fecha o primeiro; nenhum texto se sobrepõe; Escape retorna foco |
| F06 / 057 | C11 | Resumo de ausência tem um total, tempo reconhecido e um aviso de limite, com decomposição subordinada |
| F07 / 057 | C01, C11 | Estado/conteúdo útil antes de explicações; Ver ofertas leva à Vigília, sem CTA que promete lista inexistente |
| F08 / 056 | C01, C03–C04 | Candidato/custo/vagas/ação juntos; roster cheio tem motivo; reroll permanece independente; painéis vazios não esticam |
| F09 / 056 | C01, C03, C05 | Elenco prioritário, ocupação sem ambiguidade e uma identidade de classe por título |
| F10 / 056 | C05, C09 | Atributos cabem em ampla; slot/detalhe acessíveis por foco/toque; Remover secundário e sem execução ao consultar |
| F11 / 056 | C07 | Histórico recolhido mostra resultado/recompensa/data; pendência de coleta permanece evidente |
| F12 / 056 | C03, C07 | Pausa tem mesmo sinal em Coleta/Vigília, motivo e nenhuma contagem ativa contraditória |
| F13 / 056 | C04, C07 | Sem seleção/insumos, condição legível junto à ação; total e duração próximos da quantidade |
| F14 / 057 | C01, C11 | Ofertas usam 3/2/1 colunas por largura útil; recomendações e exigências distintas, sem tutorial repetido |
| F15 / 052 | Handoff ML-052 | Drops alinhados ao padding e compactos nos três tipos de atividade; não implementar outra variante neste lote |
| F16 / 056+057 | C06, C09 | Preparados/reforços distinguíveis; modo com suprimento acompanha composição; título/fechar e retorno de foco preservados |
| F17 / 057 | C08 | Ranking/região sem overflow global; números rotulados e própria guilda reconhecível em reduzida |
| F18 / 056 | C02, C08 | Nenhum common/uncommon ou slug técnico usado como nome visível quando há mapeamento PT-BR |
| F19 / 057 | C08 | Relatório permite comparar deltas/entrada/resultado sem ler frase repetida por CPU; dados ausentes explícitos |
| F20 / 056 | C03, C07 | Resumo regional representa famílias pertinentes além das três antigas e leva à gestão completa |
| F21 / 055 | Handoff ML-055 | Portal natal/externo, atual/histórico e própria equipe/CPU distintos; sem segunda central neste lote |
| F22 / 056 | C05, C10 | Atributos em pares, badges apenas para estado/raridade, filtros e posição preservados no retorno |
| F23 / 056 | C04, C07 | Receita com faltas/total; bancada bloqueada compacta e legível; serviços em linhas de item→retorno |
| F24 / 056 | C04, C07 | Mercado mostra quantidade/total/prazo juntos; cancelar e coletar continuam distintos |
| F25 / 056 | C04–C05 | Mercante/nome/prazo juntos; detalhe consultável antes da compra, sem executar compra |
| F26 / 056 | C02–C04 | Construção/progresso agrupam nível/benefício/marco; custos aplicáveis e faltantes identificados, sem zeros inventados |
| F27 / 056 | C04, C09 | Reset mantém custo, estimativa/exato, capacidade e bloqueios à vista; só proveniência longa recolhida |
| F28 / 056 | C03–C04 | Etapa mostra faltas principais e permite ver matriz completa sem perder exigências |
| F29 / 056 | C03, C07 | Profissões usam ícones de família e disponibilidade real; bônus/duração próximos, sem pílula de frase longa |
| F30 / 057 | C01, C11 | Guia de classes com índice/retorno acessíveis e menos painéis aninhados; cards comparáveis por etapa |
| F31 / 057 | C01–C02 | Seis raridades em grade equilibrada, rótulos legíveis e descrição sem cor de raridade no parágrafo inteiro |
| F32 / 056+057 | C03, C09–C11 | Um estado por conquista; detalhe com padding/identidade e retorno preservando contexto |
| F33 / 056 | C05 | Fixture confirma fonte canônica; descrição e campo de raridade deixam de se contradizer, sem alterar item salvo/lore |
| F34 / 057 | C10 | Busca mantém termo e mostra resultado; catálogo sai de loading para estado real após entrada direta/parcial; exportação funciona sem handlers duplicados |
| F35 / 057 | C11–C12 | 13 etapas com mesmo padrão de alvo/foco, ícone por assunto e nenhum efeito de gameplay ao navegar |
| F36 / 057 | C11 | Versão/canal e Verificar têm prioridade; provedor subordinado e nenhuma instalação automática |

## Validação em uma passagem consolidada

DEV entrega matriz Fxx → arquivos/componentes → cenário/evidência no SHA candidato. Registrar os Fxx sem alteração necessária com evidência de que o componente compartilhado já resolve o critério; não encerrar item só pela ausência de edição específica. Diagnósticos F33/F34 incluem reprodução antes/depois e causa confirmada. Não corrigir dados reais para produzir comparação favorável.

Capturas sintéticas em **390, 980, 1100, 1101 e 1440 px de viewport CSS**, altura mínima de referência 800 px. Conferir também zoom 200% numa janela desktop: reflow, foco e ações acessíveis, sem exigir mesma altura de cabeçalho. Respeitar o mínimo nativo do aplicativo ao validar a janela; 390 px pode ser verificado na superfície sintética suportada, explicitamente identificado. Sem rolagem horizontal global; exceção apenas para tabela local identificada em C08. A largura útil dos grids deve ser anotada na evidência para explicar 3/2/1 colunas.

| Grupo sintético | Estados e transições necessários |
| --- | --- |
| Identidade/entrada | Nome longo, campanha vazia/existente/recuperação, direto→parcial→retorno; apenas fixture para ações de manutenção |
| Decisão | Vazio, seleção válida/inválida, sem vaga, sem material, limite cheio e dado ausente. Custos/requisitos idênticos antes/depois |
| Preparo | Sem preparo, em andamento, pronto com equipe exata, preparado indisponível, reforço adicionado/removido, preparado removido, expiração e polling |
| Produção | Livre, produzindo, pausado por capacidade/alvo, retomada, resultado pronto e histórico; oficina/bancada bloqueada e liberada |
| Consulta | Busca encontrada/ausente/vazia, filtros, detalhe/retorno, catálogo carregado/vazio/erro, retry e exportação após navegação parcial |
| Sobreposições | Modal longo, rolagem do corpo, fechamento por Escape e controle, foco/Tab/retorno, dois popovers em sequência e clique externo |
| Acessibilidade | Teclado completo, foco visível, toque sem hover, nomes acessíveis, contraste medido e movimento reduzido |

Preferir uma captura ampla e uma reduzida por família de componente, mais sequência curta quando o aceite depende de transição; não exigir uma imagem por Fxx se a mesma evidência o demonstra. Dados sintéticos e falhas controladas devem ficar identificados. Nenhuma evidência privada da auditoria real entra no Git. Concluída essa matriz sem divergências observáveis, DA faz uma revisão consolidada; revisões adicionais ficam reservadas a falha concreta, regressão ou critério não coberto, sem ciclos de preferências estéticas fora deste escopo.
