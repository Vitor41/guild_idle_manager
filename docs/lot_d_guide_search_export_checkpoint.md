# Lote D — evidência para revisão

Base de implementação: `074e019ee033110160e4f00a9ea5b2099ab2c03d` (Lote C aprovado). Branch: `feature/lot-d-guide-search-export`.

## Critérios e evidência

| Critério | Evidência nesta entrega |
|---|---|
| ML-025: Guia com seção e fontes identificáveis | `app/templates/guide/index.html` inclui Equipamentos e Materiais no índice e no Guia, com navegação de Missões, Masmorras, Chefes, Coleta, Docas, Desmontagem e outras fontes. Os dados são formados por `build_guide_catalog` usando os templates e associações ativos. |
| Fontes, chances, quantidades e requisitos | `material_source_manifest.py` lê drops ativos por conteúdo específico, ofertas das Docas somente até o nível de catálogo realmente alcançável pelo runtime e pelo limite ativo da construção, seleção determinística de coleta por faixa, desmontagem e produções especiais. A interface separa chance-base por entrada após sucesso, chance de unidade extra, compra sem chance de drop e processamento. Ingredientes consumidos não contam como origem. |
| Cobertura de materiais e receitas | Os dados seed cobrem as 13 famílias de materiais e não apresentam lacunas ativas; o teste confirma que ingredientes de receitas ativas possuem origem. Itens adicionados sem origem são exibidos como “Sem fonte disponível” e excluídos do conjunto elegível para novas receitas. |
| ML-026: Busca global e filtros | Busca cobre o texto do Guia e catálogo carregado, funciona por envio de formulário (Enter ou botão), ignora caixa e espaços repetidos e substitui destaque anterior. Os filtros combinam nome, tipo, família, faixa, Tier e origem; incluem estado vazio, limpeza e recarga após falha. |
| Markdown sincronizado e privado | `/guide/export.md` converte o mesmo template explicativo usado na tela e acrescenta o mesmo catálogo ativo. A exportação exclui navegação, controles, estados de carregamento, bônus/renda privados, estoque atual e identificadores de campanha; inclui versão, data, fontes, slots, requisitos, chance, quantidade e preço configurado quando aplicável. |
| Direção visual | Aplicados os handoffs `LOT_D_GUIDE_WIKI_VISUAL_HANDOFF.md` e `LOT_D_GUIDE_SEARCH_EXPORT_VISUAL_HANDOFF.md`: hierarquia do Guia, controles textuais, tabela semântica responsiva, estados, foco, navegação e movimento reduzido. O aceite visual manual segue pendente para o usuário, conforme os handoffs. |

## Verificações executadas

- `..\.venv\Scripts\python.exe -m unittest tests.test_guide_routes tests.test_material_source_manifest` — 5 testes passaram.
- `node --test tests/guide_frontend_utils.test.js` — 4 testes passaram para busca normalizada e filtros combinados/de origem.
- `node --check app/static/js/guide.js` e `node --check app/static/js/guide-utils.js` — passaram.
- `..\.venv\Scripts\python.exe -m compileall -q ...` nos módulos e testes desta entrega — passou.
- `git diff --check` — passou; Git emitiu apenas avisos de conversão de finais de linha para CRLF nos arquivos do checkout.
- Regressão adicional: requisitos 21 no template da oferta ou do mercante ficam como lacuna porque o catálogo das Docas chega a 20; limitar o template de construção ao nível 50 reduz o catálogo alcançável a 10, e requisito de guilda acima do máximo torna as Docas inacessíveis. Esses casos não aparecem no Guia nem qualificam ingrediente para nova receita.

## Limites desta evidência

Os testes de rota invocam handlers diretamente com SQLite temporário porque o ambiente não contém a dependência `httpx2` exigida pelo `TestClient` instalado. Não houve build, instalação, execução por CUA, teste visual em navegador nem alteração de perfil/saves. Os handoffs DA registram os cenários de validação visual a realizar na etapa de aceite.

Arquivos e dados preexistentes fora do escopo foram preservados. Não foram feitos push, merge, publicação ou instalação.
