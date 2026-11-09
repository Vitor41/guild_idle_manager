# ML-030 — handoff visual para a futura branch E3

**Preparado em:** 08/11/2026. O checkout `App GIM` não foi alterado. Esta entrega especifica somente apresentação dos bônus FORTE e fornece um sprite de estrela para integração posterior. Regras, faixas, garantias e compatibilidade de saves permanecem em `ML-BUGS.md` e serão implementadas pelo DEV.

## Uso no inventário e detalhe

Manter borda, ícone do equipamento e badge de raridade já existentes. Cada bônus especial é um chip próprio com a estrela pequena e texto completo: **FORTE FOR +N**, **FORTE VIT +N**, **FORTE AGI +N** ou **FORTE INT +N**. Usar superfície escura elevada, borda em latão claro e texto creme; o marcador FORTE mantém a mesma cor em Lendário e Mítico, enquanto a badge de raridade continua dourada ou rosa conforme o item. O rótulo, atributo e valor nunca dependem da estrela ou da cor.

No card compacto, dispor chips de bônus normais e FORTE em linhas que possam quebrar; não sobrepor nome, raridade, estado de venda/equipado ou ação. Se houver muitos bônus, mostrar os primeiros chips com texto “Ver todos os N bônus” que abre detalhe, preservando contagem correta de tipos distintos. No detalhe, listar todos os bônus em duas seções legíveis, **Normais** e **FORTE**, com valores persistidos por instância. Para um mesmo atributo, apresentar a soma de forma explícita, por exemplo `FOR +8 normal +15 FORTE = +23 total`, sem exibir +23 como um terceiro bônus independente. O poder efetivo exibido usa o total confirmado pelo serviço.

FORTE só aparece quando a instância realmente o possui; raridade Lendário ou Mítico não cria estrela por si só. Equipamentos antigos sem bônus FORTE mantêm a apresentação atual. Não duplicar chips ao equipar, refinar, vender ou reabrir a ficha. A ordem pode ser FOR, VIT, AGI, INT para leitura estável, seguida dos bônus normais restantes. O Guia do Jogo precisa explicar que FORTE soma ao atributo normal e só pode surgir a partir de Lendário, com as garantias e faixas finais aprovadas pelo DEV.

## Sprite e integração proposta

Sprite original criado com **imagegen integrado**: estrela de latão envelhecido com centro teal, contorno de ferro, fundo transparente. Arquivos deste handoff:

| Arquivo | Uso sugerido |
|---|---|
| `strong-bonus-star-16.png` | chip compacto (16×16) |
| `strong-bonus-star-32.png` | detalhe ou tela com maior densidade de pixels |
| `strong-bonus-star-64.png` | chave base no manifesto desktop |
| `strong-bonus-star-128.png` | detalhe ampliado, se necessário |
| `strong-bonus-star-512.png` e `strong-bonus-star-master.png` | master/exportação |

Quando E3 abrir, copiar os exports para `app/static/assets/desktop/sprites/64/bonus-strong-star.png`, `sprites/128/bonus-strong-star.png` e `sprites/master_512/bonus-strong-star.png`; guardar o master em uma origem DA apropriada. Adicionar chave `bonus-strong-star` ao `app/static/assets/desktop/manifest.json`, com paths 64/128/512. A UI pode usar o PNG 16 px diretamente exportado para o slot pequeno, ou renderizar o PNG 64 px a 16–20 px após verificar nitidez. `alt=""` quando o texto “FORTE” estiver ao lado. O sprite não deve entrar no mapa de raridade, pois representa tipo de bônus, não raridade.

**Prompt final resumido:** sprite bitmap transparente de estrela única de cinco pontas, latão envelhecido, centro esmaltado teal, borda de ferro escuro, silhueta grossa legível a 16 px, sem medalha, texto, UI ou sombra externa. Os exports 16/32/64/128/512 preservam alpha; o de 16 px foi inspecionado como marcador legível.

## Estados, responsividade e aceite

- Sem FORTE: card normal, sem espaço vazio nem estrela decorativa.
- Um a quatro tipos FORTE: um chip por tipo persistido, com valor e total corretos; garantias de distribuição são responsabilidade do serviço.
- Em 420 px e zoom 200%, chips quebram linha; o detalhe lista todos os bônus sem rolagem horizontal obrigatória. Foco visível no acesso ao detalhe; leitor de tela lê rótulo e valor completos.
- Nenhum brilho/pulso contínuo. `prefers-reduced-motion: reduce` remove eventual transição curta de abertura; a estrela permanece estática.
- Comparar o mesmo item antes/depois de equipar, vender e reabrir a campanha para garantir valores e chips estáveis. Validar caso `FOR +8` com `FORTE FOR +15` exibindo total +23 uma única vez.

## Complemento E3 — superfícies além do Inventário (09/11/2026)

| Superfície atual | Tratamento de FORTE |
|---|---|
| **Inventário** (`app/templates/inventory/index.html`) | Card compacto mantém raridade, refino e estado; estrela + chip textual em cada tipo FORTE persistido. Se a quantidade de bônus exceder o espaço, “Ver todos os N bônus” abre detalhe completo. O detalhe mostra normal, FORTE e soma efetiva sem contar a soma como outro bônus. |
| **Ficha do mercenário, equipamento equipado** (`app/templates/mercenaries/detail.html`) | A lista atual mostra somente nome e slot. Acrescentar no item equipado um marcador textual “N bônus FORTE” apenas se a instância os possuir, com acesso ao mesmo detalhe completo. Atributos totais da ficha continuam calculados pelo serviço e não somam o chip novamente. |
| **Seletor de equipar** (mesmo template) | O `<option>` de cada instância deve conter texto curto `FORTE FOR +N` etc. quando aplicável, além de raridade, poder e diferença já exibidos. Não depender do sprite dentro de `<option>`, pois controles nativos não renderizam imagens de forma consistente. A visualização detalhada fora do select pode usar a estrela. |
| **Loot e histórico de resultado** (`app/templates/components/result_card.html`) | Se a recompensa já criou uma instância com bônus persistidos, mostrar nome, raridade e “N bônus FORTE” no resumo e acesso aos valores completos. Se o resultado só conhece um template ou loot possível, não colocar estrela nem prometer FORTE. Histórico deve ler snapshot/instância já gravada e nunca sortear bônus ao abrir. |
| **Ferreiro/refino** (`app/templates/blacksmith/index.html`) | Ao escolher uma instância para refino, preservar marcador e valores FORTE no resumo antes/depois. O refino não deve parecer gerar outro tipo FORTE, salvo regra aprovada. Desmontagem confirma a instância e seus bônus que serão consumidos. |
| **Mercado/Docas** (`app/templates/market/index.html`, `app/templates/docks/index.html`) | Anúncio de instância já existente pode mostrar marcador FORTE no detalhe da venda. Oferta de catálogo sem instância sorteada mostra apenas raridade e características conhecidas; não antecipar estrela. Após compra/geração, o item real segue a apresentação do Inventário. |
| **Guia do Jogo** (`app/templates/guide/index.html`) | Explicar os quatro rótulos FORTE, que somam ao bônus normal e que a estrela indica bônus persistido, não garantia visual por raridade. Faixas e garantias publicadas devem refletir a regra final do serviço e o Markdown exportado da mesma fonte. |

**Integração visual mínima:** copiar os PNGs deste diretório para os caminhos propostos acima, adicionar a chave `bonus-strong-star` ao manifesto desktop e renderizar a estrela com `alt=""` ao lado de “FORTE”. O arquivo de 16 px é adequado ao chip; 32 px serve ao detalhe; 64/128/512 seguem o padrão do manifesto. Todos permanecem fora do checkout até o DEV abrir E3. Conferir Lendário com e sem FORTE legado, Mítico com vários tipos, item equipado, resultado de loot persistido, anúncio de instância e oferta de catálogo ainda não gerada, janela de 420 px, zoom 200%, teclado e movimento reduzido.
