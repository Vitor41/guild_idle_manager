# Guild Idle Manager — Ícones de Classes v1

Pacote inicial de ícones/emblemas para as classes-base do Guild Idle Manager.

## Conteúdo

- 6 classes: Aprendiz, Guerreiro, Ladino, Mago, Clérigo e Arqueiro.
- PNG com fundo transparente.
- Master: 512x512.
- UI: 128x128.
- Preview: `previews/contact_sheet.png`.
- Manifest: `manifest_class_icons.json`.

## Estrutura

```text
app/static/img/classes/
├── 512/
│   ├── class_apprentice.png
│   ├── class_warrior.png
│   ├── class_rogue.png
│   ├── class_mage.png
│   ├── class_cleric.png
│   └── class_archer.png
└── 128/
    ├── class_apprentice.png
    ├── class_warrior.png
    ├── class_rogue.png
    ├── class_mage.png
    ├── class_cleric.png
    └── class_archer.png
```

## Identidade visual

A direção visual segue a UI medieval/fantasia já usada no projeto:

- fundo transparente;
- dourado, pergaminho, bronze e tons escuros;
- símbolos legíveis em tamanhos pequenos;
- sem texto dentro do ícone;
- composição 1:1;
- compatível com os slots atuais `.avatar-placeholder` e `.class-emblem`.

## Sugestão de integração

O projeto atual usa placeholders textuais nas classes e mercenários:

- `.avatar-placeholder`: 68x68 no card de mercenário;
- `.class-emblem`: 48x48 no Guia de Classes.

A sugestão é manter o container atual e substituir o texto por imagem:

```html
<div class="avatar-placeholder class-avatar">
  <img class="class-icon" src="/static/img/classes/128/class_{{ mercenary.mercenary_class.code }}.png" alt="{{ mercenary.class_label }}">
</div>
```

No Guia de Classes:

```html
<div class="class-emblem">
  <img class="class-icon" src="/static/img/classes/128/class_{{ card.class.code }}.png" alt="{{ card.class.view_label }}">
</div>
```

CSS sugerido:

```css
.avatar-placeholder.class-avatar,
.class-emblem {
  overflow: hidden;
}

.class-icon {
  width: 78%;
  height: 78%;
  object-fit: contain;
  display: block;
  filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.45));
}
```

## Mapeamento técnico

Use `MercenaryClass.code` como chave principal:

```text
apprentice -> class_apprentice.png
warrior    -> class_warrior.png
rogue      -> class_rogue.png
mage       -> class_mage.png
cleric     -> class_cleric.png
archer     -> class_archer.png
```

## Observação

Este pacote não inclui especializações de nível 100, classes finais de nível 350 ou avatares de mercenários. Ele cobre apenas a primeira versão visual das classes-base.
