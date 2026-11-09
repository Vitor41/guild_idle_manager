# Lote D — Guia pesquisável e exportação Markdown

**Escopo visual:** seção **Equipamentos e Materiais** do Guia, filtros, busca global por Enter ou botão, estados de resultado e exportação Markdown. Base: `DESKTOP_VISUAL_SYSTEM.md`, `LOT_A_EVENT_NOTICES_VISUAL_HANDOFF.md`, `LOT_B_MARKET_GATHERING_VISUAL_HANDOFF.md` e `LOT_C_SUPPLY_BATCH_VISUAL_HANDOFF.md`. A direção segue a Sala de Comando e os componentes atuais do Guia (`app/templates/guide/index.html`), sem propor mudança de mecânica ou conteúdo autoritativo. Dados, disponibilidade, fontes, chances e regras de exportação devem vir do conteúdo compartilhado aprovado pelo DEV.

## Hierarquia e composição

Preservar o hero “Guia do Jogo”, a numeração editorial das seções e o índice por âncoras. Adicionar **Equipamentos e Materiais** como seção numerada no índice e no corpo, sem transformar o Guia inteiro em tabela ou catálogo denso. Manter fundo sólido nas áreas de leitura; não colocar texto essencial sobre ilustração.

No início da seção, usar uma barra de ferramentas em painel discreto, nesta ordem visual:

1. Campo **Buscar no guia**, com instrução curta: “Busque equipamentos, materiais, fontes e chances.”
2. Botão primário **Buscar**, alinhado ao campo.
3. Filtros em controles textuais claramente associados à seção: **Tudo**, **Equipamentos**, **Materiais** e, quando disponível no escopo confirmado, filtros por origem (**Coleta**, **Missões**, **Masmorras**, **Mercado**, **Desmontagem**).
4. Botão secundário **Exportar Markdown**, separado visualmente da ação de busca, mas no mesmo bloco de ferramentas.

Os filtros devem ter estado selecionado visual e semântico (`aria-pressed` para botões, ou `aria-current` se forem navegação). Seleção não pode depender apenas de cor: usar borda/fundo mais fortes e texto. Mostrar resultados em cartões compactos sobre superfícies escuras existentes, com título, tipo, resumo e detalhes de origem/chance quando conhecidos. Para Equipamento, distinguir nome, slot, Tier e raridade por rótulo/badge textual. Para Material, mostrar nome/família e as fontes aplicáveis. Não inventar valor ausente nem converter ausência em chance zero.

## Busca global e filtros

A busca cobre o conteúdo pesquisável compartilhado aprovado para o Guia e Códex, incluindo a nova seção, sem confundir uma descoberta da campanha com existência no catálogo. Cada resultado informa seu tipo e sua seção de origem; se um registro estiver bloqueado ou ainda não descoberto, não revelar dados que o jogo mantém ocultos. O estado “descoberto” não deve ser comunicado só por cor.

A submissão deve funcionar pelo botão **Buscar** e pela tecla Enter quando o foco estiver no campo. Ambos executam a mesma consulta, preservam o texto e os filtros escolhidos e levam o foco/posição até o cabeçalho dos resultados sem fazer o usuário percorrer o hero novamente. Evitar submissões duplicadas por um único Enter.

| Estado verificável | Apresentação recomendada |
|---|---|
| Antes da primeira busca | Texto de apoio “Pesquise para encontrar equipamentos, materiais e suas fontes.”; sem painel de erro. Filtros podem ser usados como navegação do conjunto, conforme implementação. |
| Busca com resultados | Cabeçalho “Resultados da busca” com termo consultado e quantidade; cards em ordem estável e cada item com ligação à seção ou detalhe correspondente. |
| Busca sem resultados | Estado vazio no mesmo espaço dos resultados: “Nenhum resultado para ‘[termo]’.” e orientação curta para tentar outro nome, filtro ou origem. Manter campo editável e filtros acessíveis. |
| Busca sucessiva com resultados | Substituir o conjunto anterior pelo novo, atualizar termo e contagem, e mover a região de resultados de forma previsível. Não acumular resultados de consultas diferentes. |
| Busca sucessiva sem resultados | Remover resultados antigos da área ativa e mostrar o vazio da nova consulta. Nunca deixar cards anteriores parecendo resposta ao novo termo. |
| Erro de leitura/exportação | Mensagem PT-BR próxima à ferramenta afetada, com `role="alert"` para erro acionável; preservar consulta e filtros para nova tentativa. |

Busca vazia não precisa produzir estado “sem resultado”; manter o convite inicial ou informar “Digite um termo para buscar”, sem listar um catálogo inesperado. Texto submetido deve ser exibido como texto escapado, nunca interpretado como marcação.

## Exportação Markdown

Manter **Exportar Markdown** como ação secundária de utilidade; não competir visualmente com **Buscar**. Ao acionar, oferecer o arquivo Markdown resultante pelo fluxo suportado pela aplicação, com confirmação não intrusiva via `role="status"`, por exemplo: **“Arquivo Markdown preparado.”** Se a exportação falhar, explicar em linguagem direta e deixar a ação disponível para tentar de novo.

A interface precisa deixar claro o escopo exportado antes da ação ou no feedback: conteúdo completo do Guia ou conjunto filtrado/consultado, conforme decisão do produto. Não sugerir que dados dinâmicos ausentes ou ocultos foram incluídos. Preservar cabeçalhos, listas, caracteres PT-BR, acentos, tabelas simples e links internos no arquivo; nenhuma ilustração é necessária no Markdown. Nome/identidade do arquivo deve ser previsível e sem depender de imagem.

## Estados de conteúdo

- **Equipamentos e Materiais com conteúdo:** separar visualmente os dois grupos por subtítulo; cada registro usa título HTML e metadados textuais, com origem em lista legível. Descrições longas podem crescer sem truncamento essencial.
- **Somente equipamentos ou somente materiais após filtro:** o grupo sem correspondências sai da lista ativa; anunciar quantidade e filtro selecionado.
- **Seção sem registros no catálogo atual:** mostrar estado vazio dentro do painel com explicação curta e preservar busca e filtros.
- **Fonte ou chance não disponível:** usar “Fonte não informada” ou “Chance não disponível” somente se for necessário explicar a lacuna; não esconder o item nem inferir indisponibilidade do item em si.
- **Registros ainda desconhecidos:** respeitar o tratamento já usado pelo Códex: itens desconhecidos permanecem ocultos quando isso for uma regra de descoberta; não expor nome, raridade ou descrição por busca/exportação.

## Responsividade e acessibilidade

- Em largura desktop, busca e botão podem compartilhar uma linha; filtros e exportação ocupam a linha seguinte quando necessário. Resultados usam grade fluida, sem largura fixa que cause corte de nomes.
- Em 420 px, campo ocupa a largura disponível, botão **Buscar** permanece alcançável e com alvo mínimo de 40 px; exportação pode ficar em linha própria. Filtros rolam horizontalmente se necessário, com indicação visual de continuidade e sem esconder o filtro selecionado.
- A 200% de zoom, controles e cards empilham; nomes, chances e origem quebram linha sem sobrepor botões ou criar rolagem horizontal da página.
- Campo tem `<label>` visível (“Buscar no guia”), não apenas placeholder. O botão inclui nome acessível inequívoco. Ordem de Tab segue campo, buscar, filtros, exportar e resultados; foco visível usa o contorno dourado de 3 px já adotado.
- O estado atual do filtro e o total de resultados devem ser lidos como texto. Uma região `aria-live="polite"` anuncia apenas conclusão da busca/quantidade/estado vazio, nunca cada atualização visual. Após busca, foco vai ao título dos resultados (`tabindex="-1"`) ou permanece no campo com anúncio equivalente, de forma consistente.
- Badge de raridade e tipo sempre carregam texto além da cor. Ícones são decorativos (`alt=""`) quando o nome já aparece ao lado; imagens não substituem o nome do item.
- Respeitar `prefers-reduced-motion`; não animar a troca de resultados nem fazer scroll suave obrigatório. Não depender de hover ou tooltip para nome, raridade, chance ou origem.

## Aceite visual

Conferir: entrada inicial; filtro Tudo/Equipamentos/Materiais e filtros de origem confirmados; busca por Enter e por botão; primeiro resultado; consulta sem resultado; consulta sucessiva com e sem correspondência; conteúdo sem registros; fonte/chance ausente; exportação preparada e erro de exportação; conteúdo oculto por regra de descoberta; teclado e leitor de tela; 420 px; zoom 200%; nomes longos e acentos; movimento reduzido. Validar que o foco chega a uma posição útil, que a busca seguinte substitui integralmente a anterior e que o arquivo reflete o escopo anunciado na interface.
