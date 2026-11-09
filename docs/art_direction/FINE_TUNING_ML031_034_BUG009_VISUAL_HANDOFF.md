# Handoff DA — ML-031 a ML-034 e BUG-009

**Data:** 09/11/2026. **Escopo:** diretrizes de interface para o DEV; nenhuma tela de jogo foi inspecionada em execução nesta entrega. Base: `App GIM/ML-BUGS.md`, `docs/art_direction/DESKTOP_VISUAL_SYSTEM.md`, templates e CSS atuais lidos estaticamente. Este arquivo está dentro do checkout e deve acompanhar a branch do lote; os demais arquivos em andamento permanecem preservados.

## Linguagem e assets existentes

Manter a Sala de Comando: fundo `#101A1D`, superfícies `#172327`/`#203035`, texto `#F1EADB`, ação dourada `#E6B965`, informação teal `#68C3B5`, sucesso `#9BD498`, erro `#E38B75`. Títulos Georgia, interface Segoe UI. Estados sempre têm palavra e ícone, nunca só cor ou animação. Foco dourado de 3 px com afastamento de 3 px; controles de pelo menos 40 px.

O `app/static/assets/desktop/manifest.json` já resolve `guild-sigil`, `nav-updates`, `building-market`, `nav-class-guide`, `status-progress`, `status-ready`, `status-warning` e `status-failed` em PNG 64/128/512. Os itens já têm sprites por grupo/slot e `bonus-strong-star` para FORTE. Usar `guild-sigil` como marca do launcher, `nav-updates` junto ao título e os `status-*` em 20–24 px; usar 64 px de origem para escala pequena, 128 px para marca até 72 px. `building-market` é identificação da seção, não repetição em cada card. Imagens decorativas têm `alt=""` quando o rótulo adjacente comunica tudo. **Nenhum novo bitmap ou alteração de manifesto é necessário.** Não usar imagem para barra de progresso, texto, percentual ou botões.

## ML-034 — launcher independente

Janela inicial compacta, sugerida em torno de 440 × 380 px, com largura mínima adaptável e rolagem vertical se o texto crescer. Superfície sólida, selo da guilda acima ou ao lado de “Guild Idle Manager”, versão instalada e canal configurado em linha secundária. Uma área central contém título do estado, frase de consequência, indicador, detalhes de progresso ou erro e ação principal. Rodapé com “Abrir jogo” apenas quando permitido. Não mostrar dados de campanha antes da seleção. Não embutir a arte ambiental do dashboard numa janela pequena.

| Estado | Mensagem e indicador | Ações visíveis |
|---|---|---|
| Verificando | “Verificando atualizações…”; `status-progress`, indicador indeterminado. | Desabilitar início concorrente apenas enquanto a decisão de versão é resolvida; oferecer cancelamento se o processo permitir. |
| Atualização disponível | Versão instalada → disponível, tamanho se conhecido, fonte/canal; explicar que a atualização ocorre antes do jogo. | “Atualizar e jogar” primária; “Jogar versão instalada”/“Adiar” somente se a compatibilidade permitir. |
| Baixando | “Baixando atualização…”; barra determinada com bytes e percentual somente quando conhecidos; caso contrário indeterminada. | “Cancelar” se seguro; impedir duplo acionamento. |
| Validando | “Validando assinatura e integridade…”; indeterminado, sem percentual fabricado. | Aguardar/cancelar somente se o fluxo preservar o pacote instalado. |
| Instalando | “Instalando atualização…”; indeterminado ou progresso real do instalador, sem prometer conclusão prematura. | Evitar segundo instalador; instrução curta se o Windows pedir confirmação. |
| Pronto | `status-ready`; “Atualização concluída. Versão X pronta.” | “Abrir jogo” primária, uma vez; abrir seleção de campanhas. |
| Sem atualização | `status-ready`; “Você já está na versão X.” | “Abrir jogo” primária. |
| Erro recuperável | `status-failed`/`status-warning`; frase humana, etapa onde parou e código copiável discreto; caminho para ver log se confirmado pelo DEV. | “Tentar novamente”; “Jogar versão instalada” apenas se permitido. |
| Offline | `status-warning`; “Não foi possível verificar atualizações. Você pode jogar a versão instalada.” | “Jogar versão instalada” primária quando compatível; “Tentar novamente” secundária. |
| Incompatibilidade de save | `status-warning`; explicar por que a versão instalada não abre aquele formato, sem oferecer continuação inválida. | Atualizar/tentar novamente e sair. |

Em assinatura/hash inválidos, não usar texto genérico “falha na rede” nem ação de executar pacote; mostrar “Não foi possível validar a atualização” e permitir nova tentativa segura. Falta de permissão, Setup que não abriu, download interrompido e rollback precisam de mensagens próprias. A tela de Atualizações **dentro** do jogo apresenta versão e “Verificar”; se houver versão nova, informa “Feche a campanha e abra o launcher pelo atalho para atualizar”, sem CTA de instalação. O atalho e o processo são decisões do DEV; DA não especifica mecanismo de segurança.

## ML-031 e BUG-009 — Mercado

Retirar a tabela inteira de prazos do Mercado e o espaço que ela ocupava. Na seção “Docas e Mercado” do Guia, mostrar tabela textual simples e responsiva: Comum 10 s, Incomum 25 s, Raro 60 s, Épico 180 s, Lendário 600 s, Mítico 1.200 s **por unidade**, seguida da regra de redução vigente e da observação de que a estimativa individual do card já incorpora quantidade e redução. Tela e Markdown devem compartilhar fonte; DA não altera fórmula.

Card de material: ícone 44–48 px; bloco de nome com `min-width:0`, quebra de palavras longas e até duas linhas antes de expandir verticalmente; raridade/estoque/preço em metadados separados. Área de ação própria: quantidade e MAX adjacentes, estimativa abaixo, botão **Vender** no canto inferior direito. O botão não pode dividir a trilha estreita do campo num grid de três colunas rígidas. Desktop pode usar duas colunas (identidade e ação); em janela estreita empilhar identidade, campo+MAX, estimativa e CTA alinhado à direita. Quantidade e MAX permanecem associados visualmente; estado desabilitado explica falta de estoque ou slots sem esconder o motivo.

Card de equipamento livre: ícone, nome completo, badge de raridade, preço e FORTE quando persistido no item; botão **Vender** na extrema direita, centralizado verticalmente no desktop. Em largura estreita, CTA fica em linha própria, alinhado à direita, com alvo ≥40 px. Não comprimir nome para forçar alinhamento, nem colocar atributos longos na coluna do botão. Confirmar que item equipado/indisponível não parece vendável.

Verificar 1440×900, 1024×768, 760×900 e 420×900, zoom 200%, nomes longos PT-BR, raridades, 1 e máximo de quantidade, slots cheios, botão desabilitado, foco e ordem de Tab. Estimativa deve atualizar sem deslocar ou cobrir CTA; sem rolagem horizontal da página. Os templates atuais `app/templates/market/index.html` e regras `.market-item-row`/`.market-item-action` em `app/static/css/main.css` são os pontos de integração do DEV.

## ML-032 — download do Guia

No próprio bloco de busca/exportação (`app/templates/guide/index.html`), manter “Baixar Guia em Markdown” como ação secundária. Ao acionar: botão desabilitado e rotulado “Preparando Guia…”, indicador indeterminado discreto, `role="status"`/`aria-live="polite"` para uma atualização por mudança de estado. Sucesso: ícone `status-ready`, “Guia gerado: NOME.md. Confira a pasta de downloads definida no navegador.” Nome vem da resposta real; não inventar caminho absoluto. Falha: `status-failed`, “Não foi possível gerar o Guia. Tente novamente.” com ação de nova tentativa no mesmo componente e `role="alert"`. Sem modal. Em lentidão, não saltar para sucesso antes da resposta/download confirmado pelo fluxo disponível. Após fim, reabilitar botão e preservar busca/filtros. O arquivo deve refletir o conteúdo/versão atual e não conter dados privados.

## ML-033 — detalhe contextual de equipamento equipado

Em `app/templates/mercenaries/detail.html`, remover apenas a faixa extensa de atributos abaixo dos slots; manter a identidade do item e a ação de desequipar. Item preenchido abre painel de superfície elevada (`#203035`, borda `#375057`, sombra discreta) com nome completo, badge textual de raridade, nível mínimo, refino, bônus normais e chips FORTE com a estrela existente. Agrupar valores por atributo; se FOR +8 normal e FORTE FOR +15, mostrar +23 total uma vez, sem novo bônus. Item vazio exibe estado vazio e não abre painel de atributos.

Hover abre no desktop e permanece enquanto ponteiro está no item ou painel; foco por teclado abre e permite navegar pelo painel; clique/toque alterna abertura para dispositivos sem hover. Escape fecha e devolve foco ao gatilho quando abertura foi explícita; saída do foco fecha quando apropriado. Painel não pode ser cortado pelo grid/modal: posicionar dentro da viewport ou inverter lado/acima quando necessário, com largura máxima `min(360px, viewport - 32px)`. Em 420 px/zoom 200%, usar painel em fluxo ou fixo com rolagem própria, sem cobrir “Desequipar” ou navegação. Usar botão/semântica de expansão e `aria-expanded`/`aria-controls` para abertura explícita; associação e leitura dos bônus precisam funcionar sem mouse. Dados vêm da instância persistida, sem novo sorteio/cálculo visual independente.

## Gate visual para o DEV

Entregar capturas ou inspeção DOM das telas implementadas em largura ampla/estreita e zoom 200%; matriz dos estados do launcher, exportação e painel; navegação por teclado e toque; foco, leitura de status e ausência de sobreposição. Testes automatizados isolados podem validar estado/dados, mas a inspeção visual do jogo e do launcher executados permanece pendente até ser realizada. Não usar instalação ou saves reais.
