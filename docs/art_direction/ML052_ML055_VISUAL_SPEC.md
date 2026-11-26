# ML-052 e ML-055 — direção visual

Data: 2026-11-24. Branch coordenada: `feature/anomalies-ui-audit`; base informada: `986b6b7c885c3a2bc8564ebc61514c3e0099223e`.

Especificação anterior à implementação. Não constitui validação do jogo renderizado nem conclusão da auditoria ML-053. Reutilizar `DESKTOP_VISUAL_SYSTEM.md` e os assets ML-028. Nenhuma regra de gameplay é alterada por este documento.

## ML-052 — drops compactos

Um único componente para contratos/missões, masmorras, chefes e cards da central. O bloco ocupa a largura interna do card, sem margem negativa ou recuo próprio. Espaço de 12 px antes do bloco; título e lista alinhados ao mesmo início do conteúdo. Linhas com intervalo de 8 px e padding vertical de 6 px. Ícone 32 px, sem esticar; intervalo de 8 px até o nome. Separação visual sutil entre linhas, sem transformar cada material em um grande card independente.

Em largura ampla, a linha tem quatro campos: ícone, nome/raridade, chance, quantidade. Nome pode quebrar; chance e quantidade não se separam de seus valores. Exemplo de conteúdo sintético: `Minério de Ferro · Comum | 23% | ×1–3`. Raridade é um rótulo curto com cor já existente, não uma borda de alto contraste em toda a linha. Em 390 px, nome e raridade ficam na primeira linha e os dois valores na segunda, junto ao nome; o ícone permanece à esquerda. Nenhuma coluna exige rolagem horizontal.

Exibir três entradas inicialmente e o controle `Ver todos (N)` quando houver mais. Expandir mantém a ordem, o foco e o contexto do card. Recolher por controle com nome claro; não duplicar as três entradas iniciais. Para lista vazia confirmada, `Somente recompensa fixa`; para dados ausentes, `Drops não registrados`, preservando a distinção. Não preencher dados ausentes com zero.

Remover da ação o parágrafo de modificadores e a repetição de `Qtd. base`, `chance-base` em cada item. O título pode ser `Drops · chance base` quando o dado realmente representar chance base; não apresentar uma chance base como chance final. Quando todos os valores exibidos forem efetivos, usar apenas `Drops`. Essa distinção deve vir do contrato de dados; não recalcular probabilidades no frontend. Regras completas e exemplos ficam na fonte única Guia/Markdown; um link `Como funcionam os drops` é suficiente, sem tooltip obrigatório para decidir.

Custos, tamanho mínimo/máximo de equipe, prazo de entrada e motivo atual de bloqueio continuam junto à ação. Quantidades e chances fornecidas pelo servidor permanecem idênticas antes/depois. Não colapsar requisitos essenciais junto com os drops extras.

## Equipe preparada e reforços

Este componente pertence ao lote derivado da auditoria ML-053 a ser numerado pela coordenação. A posição neste handoff apenas integra sua direção ao seletor usado por ML-052/055; não amplia o escopo original de ML-052 nem substitui a auditoria completa.

Dentro do seletor existente, agrupar membros em `Equipe preparada` e `Disponíveis para reforço`. Cada mercenário conserva a seleção atual e mostra retrato/classe, nome, condição e checkbox real. Integrantes preparados recebem selo de escudo e rótulo `Preparado`; reforços efetivamente selecionados recebem selo `Reforço`. Nenhum selo substitui a marca de seleção. Membro preparado temporariamente indisponível continua no grupo, com motivo curto e seleção indisponível conforme o contrato existente. Não confundir a preparação histórica com disponibilidade atual.

Usar teal para o contexto de preparação e borda/fundo discreto para seleção; reforços não são erros e não recebem vermelho. Amarelo é reservado ao aviso de incompatibilidade da composição com o suprimento. Estados acessíveis têm nomes curtos completos, por exemplo `Selecionado, preparado` ou `Selecionado, reforço`; leitores de tela recebem também a indisponibilidade e o motivo.

Resumo imediatamente antes das ações: quantidade selecionada/limite, composição preparada e estado do suprimento. Combinar ícone com texto: `Preparo em andamento · 02:34`, `Suprimento pronto`, `Composição diferente` ou motivo real de indisponibilidade. Não exibir múltiplos parágrafos equivalentes.

| Estado autoritativo | Apresentação junto à ação |
| --- | --- |
| Equipe exata, disponível e preparo concluído | `Iniciar com suprimento` habilitado; bônus resumido conforme dado atual |
| Equipe exata e preparo em andamento | Ação com suprimento indisponível; relógio e tempo restante |
| Reforço selecionado ou preparado removido | Ação com suprimento indisponível; `Exige a equipe preparada completa, sem reforços` |
| Preparado indisponível ou prazo vencido | Motivo específico; nunca estado visual de pronto |
| Composição válida para início sem suprimento | `Iniciar sem suprimento` permanece disponível conforme regra vigente |

Alterar seleção atualiza resumo e ações no mesmo ciclo visual. Polling, navegação parcial e expiração não deixam selo/tempo/botão contraditórios. A preparação original não muda ao selecionar reforços. Em tela estreita, grupos empilham e ações ocupam linhas próprias. Ações nunca são iniciadas por seleção, expansão ou fechamento de ajuda.

## ML-055 — Eventos Regionais

Inserir `Eventos Regionais` no grupo Domínio, ao lado da Vigília, com rota própria `/regional/events` no router regional existente. O acesso é direto e não exige visita prévia à Vigília. A ativação do menu deve comparar a rota específica: abrir a central não marca também Vigília como página atual. Reutilizar os sprites de portal/escudo ML-028; o item de menu pode usar o portal existente com nome textual. Não criar sprites enquanto os existentes representarem o conceito. Página com título, região natal como contexto e duas abas: `Portais Regionais` e `Rebeliões`. Manter uma URL endereçável por seção e por evento sob a rota da central; links de pop-up apontam diretamente ao evento, expandem seu detalhe quando necessário e posicionam título abaixo do cabeçalho fixo. O foco retorna ao acionador ao fechar modal; fechar não decide convite.

Cada seção separa `Atuais` de `Encerrados`. Histórico não compete visualmente com uma ação pendente: fica depois dos atuais, inicialmente resumido, com filtros próprios apenas se necessários ao volume. Evento sem ação continua consultável. Vazio de atuais tem mensagem curta, sem promessa de novo surgimento.

### Portais

Card: arte discreta ou ícone ML-028 no cabeçalho; nome do desafio, região, estado e prazo. Segunda faixa: recomendação e requisitos essenciais. Depois drops no componente ML-052 e ação contextual. Não repetir a explicação de geração em cada card.

| Estado | Sinal e ação |
| --- | --- |
| Natal elegível e entrada não usada | Selo `Disponível`, prazo de entrada, `Enviar equipe` |
| Natal sem equipe/requisito | Selo `Indisponível`, motivo específico; nenhuma ação de envio habilitada |
| Entrada já usada | `Entrada utilizada`; participação própria, se houver, acessível |
| Participação própria em andamento | Relógio e `Em andamento`; prazo da equipe separado da janela de entrada |
| Resultado próprio pronto | `Resultado disponível` e ação real de resultado/coleta conforme servidor |
| Janela expirada | `Entrada encerrada`; equipe que entrou no prazo pode continuar em andamento |
| Externo | `Outra região` e texto essencial `Fora da região natal: sua guilda não pode participar deste portal` |

Um detalhe `Próxima tentativa` exibe `Chance efetiva`, decomposta em base, contribuição das falhas e bônus dos Exploradores, com unidades em pontos percentuais. Exemplo sintético: `14% = 8% base + 3 p.p. por falhas + 3 p.p. dos Exploradores`. Com configuração padrão no teto e bônus máximo: `25% = 8% base + 12 p.p. por falhas + 5 p.p. dos Exploradores`, acompanhado de `Teto de falhas atingido`; não escrever `garantido` nem confundir 12 falhas com 20 stacks. Sem Exploradores, essa decomposição resulta em 20%. Se o servidor não fornecer a decomposição, mostrar indisponibilidade; frontend não mantém contadores paralelos.

Em cooldown, mostrar `Nova tentativa após o cooldown, em uma Vigília elegível` e prazo autoritativo. Próximo fechamento elegível não é horário de surgimento. Sem conteúdo elegível, mostrar esse motivo separadamente. Fórmula completa e política de ausência ficam no Guia/Markdown. Nunca derivar a chance da ameaça ou segurança regional.

### Rebeliões

Convite pendente apresenta região, prazo de decisão e dois controles distintos: `Aceitar convite` (principal) e `Delegar à CPU` (secundário). Antes da ação, consequência objetiva curta conforme regras vigentes. Não inventar custo, recompensa ou garantia. A confirmação só existe se o fluxo vigente a exigir; não adicionar etapa arbitrária.

Após aceite, o mesmo card mostra `Convite aceito` e acesso às atividades realmente liberadas, com disponibilidade individual. Delegação mostra `Delegado à CPU`, nunca uma equipe fictícia do jogador em andamento. Expirado mostra `Convite expirado`; encerrado mantém resultado e contribuições. Estado de decisão e estado da atividade são campos separados: aceito não significa equipe enviada.

### CPU e histórico

Participantes aparecem em linhas compactas: guilda, região, estado, equipe/resumo de composição quando registrado e resultado/contribuição. Quantidades de CPU participante e equipes em andamento são separadas. Diferenciar `Nenhuma entrada registrada`, `Processamento pendente` e `Dados históricos não registrados`. Motivos de ausência só aparecem quando persistidos: não inferir falta de equipe de um total zero. Resultado final não antecede participações devidas ainda em processamento.

Na Vigília, manter resumo e atalho para ações próprias. Portais externos ficam em bloco `Eventos de outras regiões`, com restrição explícita e sem botão de participação. Aceitar rebelião externa não altera a restrição do portal externo. Arte de aviso ML-028 é preservada com CTA direcionado à central e ao evento correto.

### Indicador compartilhado

| Agregado autoritativo da própria guilda | Menu |
| --- | --- |
| Nenhuma ação, equipe ou resultado próprio pendente | Sem bolinha |
| Ação efetivamente disponível | Verde + nome acessível com tipo/quantidade |
| Equipe própria em andamento, nenhuma ação disponível | Amarelo + nome acessível com quantidade |
| Ação e equipe em andamento | Verde; tooltip/foco informa ambos e quantidades |
| Apenas evento externo, CPU ou delegação | Sem falsa ação ou equipe própria |

Reutilizar o helper de tarefas ML-040. O menu não decide elegibilidade independentemente da seção; todos consomem o mesmo estado do servidor. Durante uma ação, mostrar processamento no controle específico. Falha de sincronização não confirma resultado nem habilita ação com snapshot antigo. Após polling/expiração, recompor seção e indicador juntos; anúncio acessível discreto apenas em mudança relevante.

## Aceite visual para DEV/DA

- Conferir 390, 980, 1100, 1101 e 1440 px; zoom 200%; nomes longos, uma/muitas entradas e dados ausentes. Sem corte, rolagem horizontal, sobreposição ou ação escondida pelo cabeçalho.
- Conferir teclado completo, ordem de foco, Escape e retorno de foco em modal; alvo mínimo 40 px, foco dourado visível e contraste do sistema existente. Estado nunca depende apenas de cor, hover ou animação.
- Movimento reduzido preserva feedback sem pulsação obrigatória. Artes não contêm dados essenciais embutidos.
- Matriz sintética cobre todas as linhas das tabelas e suas transições após polling/navegação parcial. Comparar dados de chances, quantidades, custos e composição antes/depois.
- Validar escolha de equipe, confirmação, erro, sucesso e coleta exclusivamente em perfil sintético/cópia descartável. Save real permanece limitado à observação.
- Guia/Markdown compartilham explicações removidas da ação e valores da configuração ML-054. Evidência sintética não é observação do save real nem aceite do usuário.
