# Inventário de procedência dos ícones existentes

**Estado de distribuição:** **não verificado**. Esta revisão constatou a presença e a utilidade visual dos arquivos, mas não encontrou prova de autoria, cessão ou licença nos manifestos/READMEs consultados. Não atribuir licença por inferência. A revisão de direitos deve ser resolvida pelo responsável pelo produto antes de incluir os ícones legados no instalador.

| Conjunto observado | Arquivos UI PNG presentes | Manifesto/documentação no projeto | Situação de procedência |
|---|---:|---|---|
| Classes-base em `app/static/img/classes/128/` | 6 | `app/static/assets/classes/manifest_class_icons.json`, `README_CLASS_ICONS.md` | Não verificada para distribuição |
| Itens em `app/static/img/items/128/` | 100 | `app/static/assets/items/manifest_assets.json`, `README_ASSETS.md` | Não verificada para distribuição |
| Especializações em `app/static/assets/extended/classes/specializations/ui_128/` | 10 | `app/static/assets/extended/manifest_extended_icons.json`, `README_EXTENDED_ICONS.md` | Não verificada para distribuição |
| Classes finais em `app/static/assets/extended/classes/final_classes/ui_128/` | 10 | mesmos arquivos do conjunto extended | Não verificada para distribuição |
| Construções em `app/static/assets/extended/buildings/ui_128/` | 7 | mesmos arquivos do conjunto extended | Não verificada para distribuição |

As prévias usam apenas algumas amostras desses conjuntos. O manifesto do pacote novo lista os padrões de caminho como **reuso proposto**, não como atestado de licença. Até a verificação, manter fallback textual/geométrico para cada ícone legado e evitar que o layout dependa dele para nome, raridade, estado ou ação.

## Registro necessário antes do build de distribuição

- Fonte/autoria de cada pacote e comprovante aplicável.
- Permissão de uso, modificação e redistribuição dentro do instalador Windows.
- Atribuição ou arquivo de licença exigido, se houver.
- Decisão de substituir o conjunto caso os direitos não sejam confirmados.
