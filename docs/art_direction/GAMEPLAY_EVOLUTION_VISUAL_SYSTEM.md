# Evolução da campanha — pacote visual DA

**Versão:** 0.1 · 28/10/2026  
**Status:** assets e prévia para integração; dados e fluxos ainda dependem do DEV  
**Fonte de verdade de gameplay:** [`GDD_EVOLUCAO_GAMEPLAY.md`](../GDD_EVOLUCAO_GAMEPLAY.md)  
**Base visual:** [`DESKTOP_VISUAL_SYSTEM.md`](DESKTOP_VISUAL_SYSTEM.md), linguagem **Sala de Comando**

## Intenção

A nova região faz a guilda parecer parte de um mundo habitado. O mapa, a torre da Vigília, a área de trabalho, o portal, a rebelião e a recompensa têm cenas próprias. Números, timers, causas, escolhas e consequências continuam em HTML legível sobre superfícies sólidas. O azul-esverdeado da Sala de Comando estrutura a interface; dourado indica a ação principal, verde a recompensa pronta, azul a atividade em curso, vermelho o convite urgente ou a ameaça. Cada cor acompanha um rótulo textual.

O GDD determina o ciclo de seis horas, a restrição regional, os prazos de portal/rebelião, a coleta designada, a prestação de contas modal e o resgate único. Os textos da prévia são **exemplos de composição**: não são parâmetros de balanceamento, promessa de recurso, nem implementação de regra. O backend fornece os números e a validade de cada ação.

## Abrir a prévia

Abra [`design/preview/evolution.html`](../../design/preview/evolution.html) diretamente no navegador. Funciona localmente, sem rede, servidor ou build. Os botões “Ver relatório”, “Responder”, “Preparar entrada”, “Ver recompensa” e “Ver retorno offline” abrem diálogos nativos demonstrativos. A prévia cobre desktop e janela estreita; não substitui QA na aplicação instalada.

## Pacote de arte

Todos os arquivos de produção ficam em `app/static/assets/desktop/evolution/`. O [`manifest.json`](../../app/static/assets/desktop/evolution/manifest.json) declara chaves semânticas, caminhos, papéis, tamanhos e fallbacks. Os masters originais estão em [`design/preview/evolution_masters/`](../../design/preview/evolution_masters/) e o exportador reproduzível é [`export_evolution_assets.py`](../../design/preview/export_evolution_assets.py). Execute-o com Python e Pillow apenas durante a produção de arte, nunca no runtime do jogo.

| Chave sugerida | Cena WebP 1600×900 | Sprite PNG 64/128/512 | Uso |
|---|---|---|---|
| `region_home` | `region-home.webp` | reutilizar bioma da região real | Save, região natal e hero regional. |
| `regional_vigil` | `regional-vigil.webp` | `vigil-tower.png` | Ciclo ativo e relatório encerrado. |
| `dimensional_portal` | `dimensional-portal.webp` | `portal-gate.png` | Evento ativo, prazo e entrada. |
| `regional_rebellion` | `regional-rebellion.webp` | `rebellion-shield.png` | Convite, prioridade de 1h e evento em curso. |
| `gathering_worksite` | `gathering-worksite.webp` | `gathering-kit.png` | Designação e tarefas de coleta. |
| `achievement_reliquary` | `achievement-reliquary.webp` | `achievement-medal.png` | Conquistas raras e resgate. |

As seis cenas usam WebP local de 148–262 KB. Os sprites de 64 px têm 5–9 KB cada. Escolher 64 px em linha/card, 128 px em hero ou diálogo e 512 px somente quando a apresentação justificar; não carregar masters em listas. Os 512 px são masters de exportação, não dependência de cada card. Use `width`/`height`, `loading="lazy"` abaixo da dobra e cena hero prioritária. `alt=""` para arte decorativa junto a nome e estado em texto. Nunca rasterizar texto, número ou timer.

## Estados e mensagens

| Estado | Expressão visual | Conteúdo obrigatório |
|---|---|---|
| Vigília ativa | Torre + faixa azul, progresso discreto | Ciclo, hora prevista, ofertas estáveis e ação para consultar o estado. |
| Vigília encerrada | Painel de relatório sem imagem atrás dos números | Antes/depois de segurança, ameaça e influência, ações causais e confirmação única. |
| Coleta produzindo | Kit + barra funcional | Família, nó, trabalhador, próximo ciclo, previsão e capacidade. |
| Coleta pausada | Faixa de atenção sem brilho animado | Motivo “Armazém cheio”, trabalhador ainda designado e caminho para liberar espaço. |
| Portal ativo | Cena e emblema próprios | Região, rank, prazo para iniciar, entrada por guilda, duração, risco e equipe ocupada. |
| Rebelião pendente | Notificação persistente e diálogo temático | Prazo de resposta, participar/recusar, consequência da recusa e janela de prioridade. |
| Rebelião em curso | Card no estado regional, sem repetir convite | Participantes, tempo restante, atividades disponíveis e contribuição. |
| Conquista em progresso | Medalha contida + barra | Requisito verificável e progresso persistido. |
| Conquista pronta | Medalha destacada + botão dourado | Recompensa e resgate manual; uma vez por campanha. |
| Conquista resgatada | Medalha sem pulso + rótulo “Resgatada” | Recompensa entregue e registro histórico; sem botão de resgate. |
| Conteúdo bloqueado | Superfície neutra e requisito em texto | Requisito real e benefício futuro, com link contextual para Guia/Construções. |

As quatro medidas não são intercambiáveis: **reputação** é da guilda; **segurança**, **ameaça** e **influência** são regionais. Mostrar deltas com causa no relatório, sem atribuir um mesmo prêmio a dois resumos. No retorno offline, o diálogo de prestação de contas vem antes do salão e informa tempo ausente/reconhecido, estamina, ouro passivo, produção por tarefa, limites e alertas. A cena não fica atrás desses números.

## Movimento, acessibilidade e desempenho

A prévia anima somente o emblema de evento com deslocamento leve de 4 px em 5 s, a abertura curta de diálogo e o hover de botões. Nenhum movimento transmite sozinho prazo, progresso ou claim. A animação para completamente com `prefers-reduced-motion: reduce`; não há loop de vídeo, filtro pesado ou dependência externa. No produto, evitar reanimar uma notificação já confirmada após reload e não usar pulso contínuo em listas extensas. Atualizações de timer devem ser textuais e não causar rearranjo do card.

Foco visível de 3 px em ouro claro, controles de no mínimo 40 px, nomes e estados em texto, `dialog` nativo e botões com rótulos distintos. A cor de ameaça nunca substitui “Ameaça”; `aria-live` deve anunciar somente mudança importante, sem narrar cada segundo de timer. Em 420 px, hero usa proteção vertical e os cards empilham. Os bitmaps são locais, sem CDN, fonte remota ou telemetria.

## Checklist de integração para DEV

1. Resolver as chaves do manifesto a partir dos códigos reais do modelo quando existirem. Este pacote não inventa IDs persistidos nem altera o manifesto v1 existente. Definir fallback por categoria antes de permitir novos códigos.
2. Adicionar região natal à seleção de saves usando o nome real da guilda como título; a cena regional é decorativa, não um substituto para o nome sorteado.
3. Associar Vigília a ciclo e relatório reais; separar oferta ativa, timer encerrado, recompensa pendente e relatório confirmado. Não inferir um estado de outro pela cor.
4. Ligar coleta a trabalhador, família, capacidade e estado transacional reais. “Pausada” não libera o mercenário. Ícones de madeira, minério e couro já existentes continuam mostrando a família específica; o kit novo identifica a atividade.
5. Usar portal e rebelião como eventos distintos. Mostrar prazo de entrada, resposta e prioridade conforme a regra atual; a notificação de rebelião deve persistir enquanto aguarda decisão e desaparecer após a resolução, mantendo histórico.
6. Resgatar conquistas pelo backend idempotente. O diálogo de recompensa só deve confirmar o resultado da transação; equipamento Lendário é uma instância única criada pelo jogo, jamais pela animação ou pelo front-end.
7. Integrar o retorno offline em modal obrigatório e acessível antes do jogo, com foco inicial e retorno de foco. Usar dados persistidos e confirmar entrega única. Conferir teclado, zoom 200%, janela de 420 px, WebView2 offline, alto contraste e falha de asset.
8. Manter a cena em hero/card narrativo e números em painel sólido. Validar contraste de texto, foco, hover, disabled e cada estado no componente real antes do gate visual.

## Limites desta entrega

Este pacote cobre **uma linguagem visual por sistema**, não cinco cenas exclusivas para as cinco regiões nem um emblema distinto para cada conquista do catálogo. As regiões podem compartilhar a cena genérica de fronteira na primeira integração, mas devem sempre exibir o nome natal real em HTML e, quando houver biomas definidos, usar o sprite de bioma existente adequado. Não há spritesheet de personagem ou animação de gameplay; a microanimação local em CSS foi escolhida para manter leveza e controle de movimento reduzido. Não há assets para cada rank E–S; o rank deve permanecer texto e poderá ganhar tratamento depois da taxonomia final. Nenhum arquivo de regra, banco ou template do app foi alterado.

## Prompts finais do imagegen

Modo: **ferramenta imagegen integrada**. Todas as imagens são originais, sem referência visual de terceiros. O conjunto de prompts usou a categoria `stylized-concept`, arte de jogo realista pictórica, materiais de pedra/madeira/latão e paleta teal/âmbar da Sala de Comando, sem texto ou UI. Temas específicos por imagem:

1. `region-home`: vale de fronteira com rio, bosque, pedreira e cidade muralhada visto da varanda da guilda; mapa e bússola no primeiro plano, lado esquerdo escuro.
2. `regional-vigil`: torre de vigia e braseiro de sinalização sobre o vale ao amanhecer; sentinelas pequenas, lado esquerdo livre.
3. `dimensional-portal`: arco de pedra fraturado abrindo um véu ciano-violeta num passo montanhoso; pequeno grupo se aproxima, lado esquerdo escuro.
4. `regional-rebellion`: cidade ameaçada à noite, barricadas, sinais de fogo e coalizão chegando pela ponte; vermelho contido.
5. `gathering-worksite`: posto de trabalho com bosque, pedreira e couro visíveis; um trabalhador, materiais reconhecíveis.
6. `achievement-reliquary`: medalha da guilda e espada Lendária em relicário aberto sobre mesa de pedra; metade esquerda livre.
7. Sprites transparentes separados: torre com braseiro; portal de pedra; escudo e duas bandeiras; bolsa de ferramentas de coleta; medalha de louros e esmalte teal. Cada prompt exigiu objeto único centralizado, contorno legível a 64 px, fundo realmente transparente e ausência de texto.
