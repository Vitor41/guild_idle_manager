# Pacote visual desktop — entrega

O pacote em `app/static/assets/desktop/` contém 92 sprites originais com masters locais em `design/masters/`, exportações PNG de 512, 128 e 64 px, seis retratos, quatro ilustrações e `app-icon.ico` com tamanhos de 16 a 256 px. O catálogo visual fica em `design/preview/sprite-catalog.html`.

`manifest.json` associa as artes aos códigos conhecidos de classes, prédios, materiais, equipamentos, consumíveis, estados, ações, menus, missões, masmorras, biomas e recursos. A cobertura das 26 classes é individual: 26/26. O relatório gerado em `docs/art_direction/SPRITE_COVERAGE.md` registra 214 mapeamentos conhecidos e zero arquivos ausentes, incluindo os 13 grupos antes descobertos no catálogo de itens. As cinco prévias em `design/preview/` carregam imagens deste pacote.

## Uso pelo DEV

1. Ler `app/static/assets/desktop/manifest.json` como fonte dos caminhos e dos mapeamentos semânticos. Usar o tamanho 64 para a maioria dos ícones de interface, 128 para cards e detalhes e 512 apenas onde a área visual exigir. Usar os retratos de 448 × 560 px nos cards de herói.
2. Exibir texto visível ou dica de tela junto aos símbolos de classe quando renderizados a 24 px; nessa escala, os detalhes de alguns símbolos ficam sutis. Adicionar nomes acessíveis às imagens e estados.
3. Preservar os caminhos locais relativos à raiz do projeto. Não copiar dependências das imagens legadas do aplicativo para a interface desktop nova.
4. Regenerar as saídas a partir dos masters locais e validar o manifesto com os comandos abaixo. O verificador lê `app/static/assets/items/manifest_assets.json` e as declarações atuais de classes, prédios e conteúdo massivo; um grupo real sem mapeamento causa falha.

## Regeneração opcional da arte

Pillow **12.3.0** foi a versão testada. É dependência apenas das ferramentas de arte, registrada em `design/requirements-art.txt`; o aplicativo usa os PNGs/WebP já exportados e não precisa de Pillow em `requirements-desktop-dev.txt`.

```powershell
python -m pip install -r design/requirements-art.txt
python design/export_sprites.py
python design/export_portraits.py
python design/build_sprite_manifest.py
python design/build_sprite_catalog.py
```

O pacote desktop usa arte original gerada para esta entrega. O inventário de imagens legadas em `LEGACY_ASSET_PROVENANCE.md` permanece apenas para rastreio histórico; a procedência e licença dessas imagens não foram confirmadas e elas não são dependências do pacote desktop.

Os seis retratos são referências visuais dos arquétipos de classe. Eles não definem a identidade literal de cada mercenário nomeado na campanha; a integração deve manter nomes, atributos e disponibilidade vindos dos dados do jogo.

Em janelas de até 760 px, a prévia reúne a navegação em um menu expansível nativo com todos os destinos, ícones e rótulos. `design/preview/README.md` descreve o comportamento e o fallback. O aplicativo deve preservar esse alcance e o foco visível na sua navegação real. As prévias de 500 px testam uma largura menor que a janela mínima atual de 760 px.

## Verificação visual

- `design/preview/index.html`, `roster.html`, `operations.html`, `tavern.html` e `inventory.html`: telas navegáveis.
- `design/preview/sprite-catalog.html`: todos os sprites e retratos.
- `design/preview/class-readability-26.png`: leitura das 26 classes em 48 e 24 px.
- `design/preview/sprite-readability-groups.png`: leitura dos demais grupos em 48 e 24 px.
- `design/preview/catalog-additions.png`: os nove símbolos novos do catálogo em 64 e 24 px.
- `design/preview/portrait-archetypes.png`: seis arquétipos de retrato.
- Capturas desktop e estreitas de cada tela em `design/preview/`. Os ajustes finais do KPI **Equipamentos**, nomes de item em duas linhas e marcadores decorativos estão no código da prévia, mas ocorreram após essas capturas; recapturar antes da aprovação visual final.

Nenhum commit foi criado nesta entrega. A aplicação real da interface fica para a integração DEV.
