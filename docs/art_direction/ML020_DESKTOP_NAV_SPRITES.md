# ML-020 — cobertura de sprites da navegação desktop

**Auditoria:** 02/11/2026. Inventário dos 22 links em `app/templates/base.html`; cabeçalhos “Domínio” e “Guias e registros” são rótulos de seção, sem destino e sem ícone. O mapa canônico de rota → chave foi adicionado a `app/static/assets/desktop/manifest.json` em `navigation`. Todas as 22 chaves têm sprite 64 px local resolvido. Nenhum nome ou código de menu foi criado.

| Menu | Rota | Sprite no manifesto | Origem |
|---|---|---|---|
| Visão geral | `/dashboard` | `guild-sigil` | existente |
| Taverna | `/tavern` | `building-tavern` | existente |
| Mercenários | `/mercenaries` | `class-warrior` | existente |
| Missões | `/missions` | `expedition-map` | existente |
| Coleta | `/gathering` | `nav-gathering` | `evolution/sprites/ui_64/gathering-kit.png`, arte existente específica |
| Oficinas | `/workshops` | `nav-workshops` | novo bitmap |
| Masmorras | `/dungeons` | `dungeon-gate` | existente |
| Vigília Regional | `/regional` | `nav-regional` | `evolution/sprites/ui_64/vigil-tower.png`, arte existente específica |
| Inventário | `/inventory` | `item-chest` | existente |
| Ferreiro | `/blacksmith` | `building-blacksmith` | existente |
| Mercado | `/market` | `building-market` | existente |
| Docas | `/docks` | `building-docks` | existente |
| Construções | `/buildings` | `building-warehouse` | existente |
| Troca de Classe | `/class-change` | `class-apprentice` | existente |
| Progresso da Guilda | `/guild/progress` | `resource-xp` | existente |
| Profissões | `/professions` | `building-training_ground` | existente |
| Guia de Classes | `/classes` | `nav-class-guide` | novo bitmap, diferencia de Mercenários |
| Guia de Raridades | `/tiers` | `status-ready` | existente |
| Conquistas e Códex | `/codex` | `item-book` | existente |
| Guia do Jogo | `/guide` | `item-quest-scroll` | existente |
| Atualizações | `/updates` | `nav-updates` | novo bitmap |
| Admin (condicional) | `/admin` | `status-warning` | existente |

## Novos arquivos

Três famílias em `app/static/assets/desktop/sprites/`: `64/nav-workshops.png`, `128/nav-workshops.png`, `master_512/nav-workshops.png`; equivalentes `nav-updates.png` e `nav-class-guide.png`. Masters de 512 px e exports foram produzidos com a skill **imagegen** em modo integrado, fundo transparente. Os sprites 64 px têm aproximadamente 8 KB cada e canto com alpha 0. A arte de Coleta e Vigília permanece em `app/static/assets/desktop/evolution/sprites/`, sem cópia duplicada.

**Prompts finais resumidos:** (1) Oficinas: bancada medieval com almofariz, tenaz e suprimentos, madeira/latão/teal; (2) Atualizações: setas mecânicas circulares em torno de pacote de pergaminho selado, latão/teal; (3) Guia de Classes: códice aberto com escudo, arco e estrela arcana. Todos pediram silhueta centrada, legibilidade a 64 px, textura pictórica da Sala de Comando, transparência real, sem texto nem moldura.

## Handoff para DEV

`app/static/js/desktop-art.js` ainda tem `navigationArt` embutido: faltam `/workshops`, `/regional` e `/updates`; `/gathering` aponta para madeira e `/classes` repete o Guerreiro. Alterar esse arquivo no escopo DEV para ler `manifest.navigation` e resolver as chaves pelo `manifest.sprites`, evitando dois mapas divergentes. Não usar glyph Unicode como fallback visual para menu sem asset: se o manifesto falhar, conservar o texto do link e uma superfície neutra, com falha verificável no QA. O mapa `routeArt` de títulos é independente e pode ser alinhado depois se a tarefa cobrir ícones dos títulos.

A sidebar elástica e a rolagem são CSS de runtime e ficaram com o DEV. Verificar em altura curta, 420 px, zoom 200%, foco de teclado e menu Admin visível/oculto; fundo contínuo até o último link e nenhum ícone espremido ou sobreposto. Esta entrega não faz inspeção do aplicativo instalado, build ou commit.
