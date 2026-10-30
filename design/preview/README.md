# Prévia visual local

Abra `index.html` diretamente no navegador e navegue pelas telas locais: salão, mercenários, operações, taverna, inventário e evolução da campanha. Os arquivos usam CSS, um pequeno script de navegação e imagens locais; não precisam de servidor, internet ou build. Dados, nomes, preços e ações são ilustrativos.

## Evolução da gameplay

Abra [`evolution.html`](evolution.html) diretamente no navegador para ver região natal, Vigília, coleta designada, portal, rebelião, conquistas e quatro pop-ups demonstrativos. A prévia usa apenas HTML, CSS, JavaScript e os novos assets locais. Os botões de pop-up mostram os estados de interface, sem executar regras ou alterar saves. Os masters originais estão em `evolution_masters/`; `export_evolution_assets.py` reconstrói os WebP e sprites PNG otimizados. A especificação está em [`docs/art_direction/GAMEPLAY_EVOLUTION_VISUAL_SYSTEM.md`](../../docs/art_direction/GAMEPLAY_EVOLUTION_VISUAL_SYSTEM.md).

Os cinco mocks de telas completas têm navegação entre si, botão para simular janela estreita e diálogos demonstrativos:

1. [`evolution-campaigns.html`](evolution-campaigns.html) — campanhas, região natal, coleta e armazém.
2. [`evolution-vigilia.html`](evolution-vigilia.html) — ciclo regional, ofertas e ranking.
3. [`evolution-events.html`](evolution-events.html) — portal e rebelião, com resultados.
4. [`evolution-offline.html`](evolution-offline.html) — retorno offline e relatório obrigatório.
5. [`evolution-codex.html`](evolution-codex.html) — conquistas, item lendário e Códex.

As telas usam dados ilustrativos e não alteram o save. Confira estados e pendências em [`GAMEPLAY_EVOLUTION_MOCK_REVIEW.md`](../../docs/art_direction/GAMEPLAY_EVOLUTION_MOCK_REVIEW.md).

## Navegação em janela estreita

Até 760 px, `nav.js` cria um menu nativo expansível (`details`/`summary`) a partir da navegação lateral de cada página. Ele contém todos os destinos, inclusive Taverna, Construções, Inventário e Códex; cada ícone permanece acompanhado por texto. O controle opera com teclado e expõe o estado aberto/fechado pela semântica nativa. Se o script não carregar, os links originais continuam acessíveis por rolagem horizontal. Para o aplicativo, reproduzir esse padrão com o componente de navegação real, preservando rótulos, foco visível e destino atual. A janela mínima atual é 760 px; a prévia de 500 px é uma prova adicional de resistência do layout.

## Capturas de referência

| Tela | Desktop | Janela estreita (500 px) |
|---|---|---|
| Salão da guilda | `dashboard-overview.png` (1440 × 1850) | `dashboard-narrow-overview.png` (500 × 3000) |
| Mercenários | `roster-desktop.png` (1440 × 1850) | `roster-narrow-overview.png` (500 × 3000) |
| Missões e masmorras | `operations-desktop.png` (1440 × 1850) | `operations-narrow.png` (500 × 3000) |
| Taverna | `tavern-desktop.png` (1440 × 1850) | `tavern-narrow.png` (500 × 3000) |
| Inventário | `inventory-desktop.png` (1440 × 1850) | `inventory-narrow.png` (500 × 3000) |

O layout também inclui regras para 420 px e menores. As capturas de 500 px registram a navegação compacta e a revisão principal de tipografia. Os ajustes posteriores no rótulo **Equipamentos** e nos nomes de item em duas linhas estão no HTML/CSS e ainda precisam de uma nova captura para o gate visual. A versão final deve testar WebView2, zoom, teclado e conteúdo real durante a integração.

O catálogo `sprite-catalog.html` lista os 92 sprites e seis retratos. `catalog-additions.png` mostra os nove novos grupos de recurso/equipamento em 64 e 24 px. Para reconstruir os exports, instalar opcionalmente `design/requirements-art.txt` (Pillow 12.3.0 testado) e seguir os comandos em `docs/art_direction/FINAL_ASSET_HANDOFF.md`; essa dependência não pertence ao runtime desktop.
