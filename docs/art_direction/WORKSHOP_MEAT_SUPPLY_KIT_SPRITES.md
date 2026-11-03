# Carne e Kit de Suprimentos — handoff de sprites desktop

**Escopo DA:** dois bitmaps novos e mapeamento no manifesto desktop; nenhuma regra, template ou serviço alterado. Criados com a skill `imagegen` integrada, em fundo transparente, seguindo a paleta de couro escuro, latão e teal da Sala de Comando.

| Item do catálogo | Identificador real | Sprite | Mapeamento usado pelo jogo |
|---|---|---|---|
| Carne da família de caça (inclui o material inicial `material_meat_1_001`) | `material_family="meat"`, `icon_group="meat"` | `material-meat` | `icon_maps.material_families.meat` e `icon_maps.item_icon_groups.meat` |
| Kit de Suprimentos | `slug="supply_kit"`, `icon_group="resource-provisions"` | `item-supply-kit` | `icon_maps.item_icon_groups.resource_provisions`; a chave usa sublinhado porque `desktop-art.js` normaliza o hífen do grupo |

Os arquivos ficam em `app/static/assets/desktop/sprites/{64,128,master_512}/material-meat.png` e nos três tamanhos equivalentes de `item-supply-kit.png`. `app/static/assets/desktop/manifest.json` declara os caminhos e as chaves semânticas. O sprite `resource-provisions` anterior permanece intacto para outros usos de provisões; o kit tem uma bolsa própria. Carne mostra um corte cru de caça, distinto de couro e partes de criatura.

**Evidência de integração estática:** o catálogo de materiais define `icon_group=family` e a família `meat`; `ensure_supply_kit()` define o grupo `resource-provisions`. O inventário fornece `data-desktop-item-group` e `data-desktop-item-family`, e `desktop-art.js` consulta `icon_maps.item_icon_groups` antes de `material_families` para resolver os sprites 64 px. O teste de manifesto confirmou os seis caminhos, PNGs 64/128/512 válidos e cantos transparentes. A Oficina atual exibe os nomes e saldos em texto, sem slot de ícone; o DEV pode aplicar esses mesmos data attributes no card da receita se quiser ilustrá-la. Não foi feita inspeção do aplicativo instalado.

**Prompts finais resumidos:** Carne: corte cru de caça com pequeno osso, silhueta isolada legível a 64 px, sem couro/troféu/refeição cozida. Kit: bolsa fechada de campanha com pano e pacote de ervas presos à tira, distinta de caixa genérica. Ambos com material pictórico, transparência real e nenhum texto ou moldura.
