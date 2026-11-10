# Auditoria de arbitragem econômica — Stage 5

Gerada em 2026-11-10T17:47:37.741204+00:00 · resultado **PASS**.

Economia sem arbitragem significa que nenhum ciclo fechado de conversão de ouro e bens financiado por Docas/Market/desmontagem/crafting tem valor esperado positivo. Renda legítima de tarefas, contratos, eventos e recompensas pode acumular sem teto de saldo.

## Cobertura

- Compra direta Docas → Market: 1200 ofertas seedadas; 0 com margem positiva; melhor margem -1 ouro/unidade.
- Docas → desmontagem → Market: 933 equipamentos; 0 com EV positivo; 0 têm algum resultado RNG positivo.
- Melhor EV da desmontagem: -36.00 ouro; melhor resultado único: -1 ouro.

## Comparação antes e depois

| Ciclo | Antes: rotas lucrativas | Depois: rotas lucrativas | Métrica |
|---|---:|---:|---|
| Docas → Market | 0 | 0 | Ofertas |
| Docas → desmontagem → Market | 707 | 0 | EV positivo |
| Docas → desmontagem → Market | 766 | 0 | Algum resultado RNG lucrativo |
| Docas → crafting → Market | 0 | 0 | Receitas com EV positivo |
| Crafting → desmontagem → Market | 4 | 0 | EV positivo |
| Crafting → desmontagem → Market | 11 | 0 | Algum resultado RNG lucrativo |

Preços de equipamentos nas Docas, antes/depois:

| Estágio | Equipamento | Nv. item | Raridade | Antes | Depois | Aumento |
|---|---|---:|---|---:|---:|---:|
| early | Adaga Polido da Precisão 1-681 | 1 | common | 75 | 75 | 0 |
| mid | Lança Antigo da Força 4-420 | 130 | rare | 79 | 854 | 775 |
| late | Amuleto Primordial do Arcano 8-200 | 350 | legendary | 135 | 4919 | 4784 |
| extreme | Amuleto Primordial do Arcano 8-200 | 350 | legendary | 135 | 4919 | 4784 |

Custos de crafting, antes/depois:

| Estágio | Receita | Saída | Nv. item | Raridade | Antes | Depois | Aumento |
|---|---|---|---:|---|---:|---:|---:|
| early | Forjar Espada Enferrujada | Espada Enferrujada | 1 | common | 80 | 80 | 0 |
| mid | Forjar Arco Antigo da Precisão | Arco Antigo da Precisão 6-622 | 222 | epic | 1320 | 1320 | 0 |
| late | Forjar Túnica Rúnico do Arcano | Túnica Rúnico do Arcano 8-292 | 342 | legendary | 2200 | 2200 | 0 |
| extreme | Forjar Cinto Polido da Fortaleza | Cinto Polido da Fortaleza 8-064 | 314 | rare | 1320 | 3590 | 2270 |

Resumo da desmontagem por raridade e faixa de progressão (cada linha contabiliza ofertas únicas de equipamento):

| Raridade | Ofertas | EV positivo | RNG positivo | Melhor resultado RNG |
|---|---:|---:|---:|---:|
| common | 339 | 0 | 0 | -1 ouro |
| epic | 105 | 0 | 0 | -1 ouro |
| legendary | 41 | 0 | 0 | -1 ouro |
| mythic | 4 | 0 | 0 | -1 ouro |
| rare | 203 | 0 | 0 | -1 ouro |
| uncommon | 241 | 0 | 0 | -1 ouro |

| Faixa de nível | Ofertas | EV positivo | RNG positivo | Melhor resultado RNG |
|---|---:|---:|---:|---:|
| 1-20 | 117 | 0 | 0 | -57 ouro |
| 101-130 | 117 | 0 | 0 | -1 ouro |
| 131-200 | 117 | 0 | 0 | -1 ouro |
| 201-250 | 116 | 0 | 0 | -1 ouro |
| 21-50 | 117 | 0 | 0 | -1 ouro |
| 251-300 | 115 | 0 | 0 | -1 ouro |
| 301-350 | 116 | 0 | 0 | -1 ouro |
| 51-100 | 118 | 0 | 0 | -1 ouro |

Taxas de desmontagem por slot preservadas: slot 1: 50 ouro, slot 2: 150 ouro, slot 3: 300 ouro.

Exemplos de preço Docas antes/depois por oferta (estágio, raridade e extremo): ver `price_comparison_examples` no JSON adjacente.

- Docas→Crafting→Market: 66 receitas ativas; 42 abastecíveis por compra direta ou material recuperado por desmontagem; 0 tinham margem positiva antes da proteção; após incluir o menor custo entre compra direta e material recuperado por desmontagem, 0 ficam positivas. Melhor margem: -169.5 ouro/receita.
- Arestas saída→insumo entre receitas (possível crafting encadeado): 0. O grafo seedado não contém uma saída de receita usada como ingrediente.

- Crafting→desmontagem→Market: 42 ciclos fechados com equipamento produzido; 0 com EV positivo e 0 com algum resultado RNG positivo. Melhor EV: -230.50 ouro/ciclo.

A busca usa o catálogo seedado real, bônus máximo do Market 100 e preços unitários reais. Sorteio de mercante, pesos e estoque limitam disponibilidade; como toda oferta é percorrida, não escondem um preço melhor. A desmontagem exaure exatamente os resultados 1, 2 e 3, e a expectativa usa a média dos três. Para o custo mínimo de salvage usa-se Blacksmith 1 (50 ouro) e rendimento esperado 2 por equipamento, sem penalidade de capacidade. Esse valor médio cobre o custo de longo prazo do insumo RNG; o relatório também testa a revenda direta de cada resultado isolado. Para receitas, cada ingrediente usa o menor custo esperado entre preço Dock acessível e equipamento comprado nas Docas e desmontado para o material requerido. Receitas sem fonte nessas rotas são listadas como inalcançáveis neste subgrafo.

Variações de estoque, slots, timers e rotações aumentam ou reduzem throughput, mas não convertem uma margem negativa por unidade em EV positivo. Renda de sistemas que criam ouro ou itens fora desses ciclos é renda legítima e não implica arbitragem; o saldo de ouro não precisa de teto.

## Reproduzir

```powershell
.venv-desktop\Scripts\python.exe scripts\balance\audit_economy_arbitrage.py
```

Receitas sem insumos recebem piso de ouro igual à revenda máxima mais 1 mesmo sem Docas. O JSON adjacente contém cada preço configurado/efetivo, estoque, requisito, material compatível e os três resultados de desmontagem por equipamento.
