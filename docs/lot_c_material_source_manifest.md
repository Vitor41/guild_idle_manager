# Lote C — contrato de fontes de materiais para o Guia

Consumidor: Lote D, Wiki/Guia. O serviço `app.services.material_source_manifest.build_material_source_manifest(db, guild_level=None, guild_id=None)` monta a resposta diretamente da configuração ativa em cada chamada. O resultado não persiste dados e não contém ID de campanha.

## Estrutura

- `schema_version`: versão inteira do contrato.
- `scope`: nível de guilda opcional e indicação de inclusão do snapshot do cais.
- `materials[]`: `item` com identificador/slug/nome/família/tier/nível/ativo; `required_by[]` com receitas ativas e quantidades; `sources[]` com a fonte e sua proveniência.
- `gaps[]`: materiais ativos sem nenhuma fonte registrada.

## Semântica das fontes

- `mission` e `dungeon_or_boss`: chance base e faixa de quantidade da tabela de drop ativa; só após sucesso, sujeita aos modificadores do gameplay. Os templates registram nível mínimo, requisito de edifício e nível mínimo do mercenário para contextualizar disponibilidade. A chance configurada não é chance total incondicional.
- `docks_possible_offer`: oferta-template ativa e alcançável pelo maior nível de catálogo das Docas (`docks_values` aplicado ao limite real da construção e da guilda), preço-base, faixa de estoque, nível mínimo e peso de seleção. Ofertas acima desse teto — por exemplo, nível 21 quando o runtime limita o catálogo a 20 — não contam como fonte. Peso não é convertido em probabilidade.
- `docks_current_snapshot`: só aparece quando um `guild_id` foi pedido; representa estoque restante, preço e término da rotação atual daquela guilda. É estado de campanha, não configuração global.
- `gathering`: material realmente selecionado pelo algoritmo por família e faixa de nível da guilda (`guild_level_range`). É determinístico, sem chance; a varredura cobre 1–350.
- `salvage`: saída efetiva da regra de desmontagem para cada equipamento ativo elegível; a quantidade usa inteiro uniforme de 1 a 3 por equipamento.
- `workshop_output`: a Oficina é fonte do Kit de Suprimentos (3 Carnes + 2 Ervas → 1 Kit, 5 segundos por unidade).
- `dependencies[]` contém `workshop_input` para variantes ativas de Carne/Erva. É um consumo por receita, não uma forma de obter esses materiais, e nunca elimina uma lacuna de fonte.
- `gaps[]` é calculado sobre fontes reais (`sources[]`); uma dependência sem rota de obtenção continua sendo lacuna.
- A varredura determinística de coleta cobre níveis de guilda 1–350, inclusive variantes selecionadas apenas nas faixas finais.

As entidades ORM e seus flags ativos são a fonte viva. Nomes e IDs são dados, nunca regras duplicadas do Guia. Ao mudar as regras/fontes, atualize o contrato e seus testes antes de o Lote D consumir campos novos.
