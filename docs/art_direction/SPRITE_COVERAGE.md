# Cobertura de sprites desktop

Todos os caminhos abaixo resolvem em `app/static/assets/desktop/`; o manifesto é a fonte de mapeamento.
O pacote é independente dos PNGs legados do projeto web. Raridade usa borda e rótulo CSS, sem duplicar imagens.

**Sprites canônicos:** 92 · **Classes:** 26/26 · **Mapeamentos conhecidos:** 214 · **Faltantes:** 0.
**Verificação contra fontes reais:** `app/static/assets/items/manifest_assets.json`, `app/seeds/massive_content.py`, `app/services/class_service.py`, `building_service.py`, `item_service.py` e `mission_service.py`. Os códigos são lidos desses arquivos a cada execução; grupo conhecido sem mapa causa falha.

## Classes: 26/26

| Código | Sprite 64 px | Retrato de arquétipo |
|---|---|---|
| `apprentice` | `sprites/64/class-apprentice.png` | `portraits/portrait-apprentice.webp` |
| `warrior` | `sprites/64/class-warrior.png` | `portraits/portrait-warrior.webp` |
| `rogue` | `sprites/64/class-rogue.png` | `portraits/portrait-rogue.webp` |
| `mage` | `sprites/64/class-mage.png` | `portraits/portrait-mage.webp` |
| `cleric` | `sprites/64/class-cleric.png` | `portraits/portrait-cleric.webp` |
| `archer` | `sprites/64/class-archer.png` | `portraits/portrait-archer.webp` |
| `knight` | `sprites/64/class-knight.png` | `portraits/portrait-warrior.webp` |
| `blade` | `sprites/64/class-blade.png` | `portraits/portrait-warrior.webp` |
| `templar` | `sprites/64/class-templar.png` | `portraits/portrait-warrior.webp` |
| `reaper` | `sprites/64/class-reaper.png` | `portraits/portrait-warrior.webp` |
| `assassin` | `sprites/64/class-assassin.png` | `portraits/portrait-rogue.webp` |
| `ninja` | `sprites/64/class-ninja.png` | `portraits/portrait-rogue.webp` |
| `predator` | `sprites/64/class-predator.png` | `portraits/portrait-rogue.webp` |
| `shinobi` | `sprites/64/class-shinobi.png` | `portraits/portrait-rogue.webp` |
| `wizard` | `sprites/64/class-wizard.png` | `portraits/portrait-mage.webp` |
| `mentalist` | `sprites/64/class-mentalist.png` | `portraits/portrait-mage.webp` |
| `arcane` | `sprites/64/class-arcane.png` | `portraits/portrait-mage.webp` |
| `warlock` | `sprites/64/class-warlock.png` | `portraits/portrait-mage.webp` |
| `priest` | `sprites/64/class-priest.png` | `portraits/portrait-cleric.webp` |
| `paladin` | `sprites/64/class-paladin.png` | `portraits/portrait-cleric.webp` |
| `high_priest` | `sprites/64/class-high_priest.png` | `portraits/portrait-cleric.webp` |
| `sentinel` | `sprites/64/class-sentinel.png` | `portraits/portrait-cleric.webp` |
| `ranger` | `sprites/64/class-ranger.png` | `portraits/portrait-archer.webp` |
| `shooter` | `sprites/64/class-shooter.png` | `portraits/portrait-archer.webp` |
| `patroller` | `sprites/64/class-patroller.png` | `portraits/portrait-archer.webp` |
| `renegade` | `sprites/64/class-renegade.png` | `portraits/portrait-archer.webp` |

## Cobertura por domínio

| Domínio | Códigos reais mapeados | Estratégia |
|---|---:|---|
| `classes` | 26 (26 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `buildings` | 9 (9 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `material_families` | 12 (12 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `item_icon_groups` | 55 (51 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `equipment_slots` | 14 (11 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `menu` | 21 | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `resources` | 6 | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `mission_types` | 14 (13 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `gathering_professions` | 8 (8 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `dungeon_biomes` | 12 (12 no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `dungeon_content_types` | 2 | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `statuses` | 14 | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |
| `actions` | 21 | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |

## Prova de leitura e fallbacks

- `design/preview/class-readability-26.png` compara todos os emblemas em 48 e 24 px sobre superfície sólida. A 24 px, usar sempre nome ou tooltip; 48 px é o tamanho preferido.
- `design/preview/sprite-catalog.html` reúne todas as categorias em slots reais.
- A expansão de conteúdo usa o fallback semântico registrado em `manifest.json` e mantém nome, estado e raridade como texto acessível.
- A resolução deve priorizar: código exato → icon_group/material_family/biome → slot/tipo → fallback do domínio. A raridade não altera o PNG.

## Risco de integração

A UI atual resolve ícones pelos manifestos legados em `app/services/icon_service.py`. O DEV precisa trocar a resolução para este manifesto e testar caminhos empacotados no WebView2/pywebview. Esta entrega não modifica serviços ou templates de produção.
