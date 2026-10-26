# Guild Idle Manager — Extended Icons v1

Pacote adicional de ícones para o Guild Idle Manager.

## Conteúdo

- 10 ícones de especializações.
- 10 ícones de classes finais.
- 7 ícones de construções da guilda.
- Versão master em PNG 512x512.
- Versão UI em PNG 128x128.
- Fundo transparente.
- `manifest_extended_icons.json`.
- Preview em `previews/contact_sheet.png`.

## Estrutura

```text
guild_idle_manager_extended_icons_v1/
├── classes/
│   ├── specializations/
│   │   ├── master_512/
│   │   └── ui_128/
│   └── final_classes/
│       ├── master_512/
│       └── ui_128/
├── buildings/
│   ├── master_512/
│   └── ui_128/
├── previews/
│   └── contact_sheet.png
├── manifest_extended_icons.json
└── README_EXTENDED_ICONS.md
```

## Padrão visual

Os ícones seguem a identidade dark medieval/fantasy já usada nos pacotes anteriores:

- medalhão circular escuro;
- borda dourada;
- símbolo central em leitura simples;
- variação sutil de cor por função/tema;
- sem texto dentro do ícone;
- boa leitura em slots pequenos;
- fundo transparente fora do medalhão.

## Sugestão de integração

Destino sugerido no projeto:

```text
app/static/img/extended/
```

Ou, se preferir separar por domínio:

```text
app/static/img/classes/specializations/
app/static/img/classes/final_classes/
app/static/img/buildings/
```

O `manifest_extended_icons.json` pode ser usado para resolver os caminhos por `key` técnica.

## Fallback recomendado

Caso uma classe, especialização, classe final ou construção não tenha ícone resolvido:

1. manter o placeholder atual com a inicial;
2. não quebrar o card;
3. registrar no log apenas em modo debug, se existir;
4. evitar erro em template Jinja.

## Keys principais

Especializações:
- cavaleiro
- duelista
- assassino
- ninja
- sabio
- mentalista
- padre
- paladino
- ranger
- pistoleiro

Classes finais:
- templario
- retalhador
- predador
- shinobi
- arcano
- bruxo
- sacerdote
- sentinela
- patrulheiro
- renegado

Construções:
- alojamento
- campo_de_treino
- ferreiro
- armazem
- escritorio_de_contratos
- exploradores
- taverna
