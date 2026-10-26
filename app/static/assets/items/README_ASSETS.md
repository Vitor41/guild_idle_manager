# Guild Idle Manager — Item Icons v1

Pacote inicial de ícones para inventário, equipamentos, materiais e recursos do Guild Idle Manager.

## Base visual analisada

O projeto atual usa uma identidade medieval/fantasia escura, com cards em tons de marrom/preto, bordas douradas e destaque principal em dourado/parchment.

Pontos usados como referência:

- CSS principal: `app/static/css/main.css`.
- Slot atual dos ícones: `.asset-placeholder`.
- Tamanho visual do slot atual: `58px x 58px`.
- Cards de inventário: `.inventory-card` dentro de `.inventory-grid`.
- Cores base: `#11100e`, `#211b16`, `#352a20`, `#d2a84a`, `#f0cb72`, `#e7d6aa`.
- Raridades já existentes no CSS: common, uncommon, rare, epic, legendary, mythic.

## Entrega

Total de ícones: **100**.

Estrutura pronta para copiar para o projeto:

```text
app/static/img/items/
├── 512/
│   ├── resources/
│   ├── materials/
│   ├── weapons/
│   ├── armors/
│   └── accessories/
└── 128/
    ├── resources/
    ├── materials/
    ├── weapons/
    ├── armors/
    └── accessories/
```

Também acompanha:

```text
manifest_assets.json
previews/contact_sheet.png
README_ASSETS.md
```

## Padrão dos arquivos

- Formato: PNG.
- Proporção: 1:1.
- Fundo: transparente.
- Master: 512x512.
- Uso em UI: 128x128.
- Naming: `snake_case`, sem acento, sem espaço.
- Sem texto dentro dos ícones.
- Ícones centralizados, com margem segura para leitura em cards pequenos.

## Recomendação de uso no jogo

Para o inventário atual, use a versão 128x128. O slot `.asset-placeholder` tem 58x58, então o browser vai reduzir bem sem perda perceptível.

Exemplo de uso no template:

```html
<img class="item-icon" src="/static/img/items/128/weapons/espada_enferrujada.png" alt="Espada Enferrujada">
```

CSS sugerido:

```css
.asset-placeholder img,
.item-icon {
  width: 42px;
  height: 42px;
  object-fit: contain;
  display: block;
}
```

## Observação técnica

O código atual usa `view_icon` como símbolo textual vindo de `icon_service.py`.

Para usar os PNGs, o ideal é evoluir o serviço para retornar `icon_path` quando houver imagem cadastrada ou mapeada.

Estratégias possíveis:

1. Adicionar uma coluna `icon_path` em `item_templates`.
2. Criar um mapeamento por `icon_group` e/ou `slug` no `icon_service.py`.
3. Carregar o `manifest_assets.json` como base de referência para popular o banco ou gerar seed.

A opção mais limpa para longo prazo é adicionar `icon_path` em `item_templates`.

## Decisão de raridade

Os ícones não têm moldura fixa de raridade. Isso foi intencional.

A raridade já é tratada no CSS do card e nos badges. Assim, o mesmo ícone pode ser usado em variações common, uncommon, rare, epic, legendary e mythic sem duplicar imagem.

## Itens já compatíveis com seeds atuais

O pacote inclui os ícones dos itens que já aparecem no projeto:

- Pele de Lobo
- Garra de Lobo
- Erva Medicinal
- Fragmento de Minério / Fragmento de Minerio
- Madeira Rústica / Madeira Rustica
- Espada Enferrujada
- Armadura de Couro
- Anel Simples
- Espada de Ferro
- Armadura Reforçada / Armadura Reforcada
- Amuleto do Caçador / Amuleto do Cacador

## Ordem sugerida de integração

1. Copiar `app/static/img/items/128` para o projeto.
2. Manter `512` como master para ajustes futuros.
3. Criar `icon_path` ou mapeamento no `icon_service.py`.
4. Atualizar `inventory/index.html` para renderizar `<img>` quando `icon_path` existir.
5. Manter fallback textual atual para itens sem imagem.

