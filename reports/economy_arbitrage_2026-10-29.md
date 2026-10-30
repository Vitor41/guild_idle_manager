# Auditoria de arbitragem econômica — Stage 5

Gerada em 2026-10-29T18:37:25.596113+00:00 · resultado **PASS**.

Economia sem arbitragem significa que nenhum ciclo fechado de conversão de ouro e bens financiado por Docas/Market/desmontagem/crafting tem valor esperado positivo. Renda legítima de tarefas, contratos, eventos e recompensas pode acumular sem teto de saldo.

## Cobertura

- Compra direta Docas → Market: 1200 ofertas seedadas; 0 com margem positiva; melhor margem -1 ouro/unidade.
- Docas → desmontagem → Market: 1706 equipamentos; 0 com EV positivo; 0 têm algum resultado RNG positivo.
- Melhor EV da desmontagem: -58.00 ouro; melhor resultado único: -56 ouro.

- Docas→Crafting→Market: 61 receitas ativas; 35 abastecíveis por compra direta ou material recuperado por desmontagem; 8 tinham margem positiva antes da proteção; após incluir o menor custo entre compra direta e material recuperado por desmontagem, 0 ficam positivas. Melhor margem: -1.0 ouro/receita.
- Arestas saída→insumo entre receitas (possível crafting encadeado): 0. O grafo seedado não contém uma saída de receita usada como ingrediente.

- Crafting→desmontagem→Market: 35 ciclos fechados com equipamento produzido; 0 com EV positivo e 0 com algum resultado RNG positivo. Melhor EV: -144.00 ouro/ciclo.

A busca usa o catálogo seedado real, bônus máximo do Market 100 e preços unitários reais. Sorteio de mercante, pesos e estoque limitam disponibilidade; como toda oferta é percorrida, não escondem um preço melhor. A desmontagem exaure exatamente os resultados 1, 2 e 3, e a expectativa usa a média dos três. Para o custo mínimo de salvage usa-se Blacksmith 1 (50 ouro) e rendimento esperado 2 por equipamento, sem penalidade de capacidade. Esse valor médio cobre o custo de longo prazo do insumo RNG; o relatório também testa a revenda direta de cada resultado isolado. Para receitas, cada ingrediente usa o menor custo esperado entre preço Dock acessível e equipamento comprado nas Docas e desmontado para o material requerido. Receitas sem fonte nessas rotas são listadas como inalcançáveis neste subgrafo.

Variações de estoque, slots, timers e rotações aumentam ou reduzem throughput, mas não convertem uma margem negativa por unidade em EV positivo. Renda de sistemas que criam ouro ou itens fora desses ciclos é renda legítima e não implica arbitragem; o saldo de ouro não precisa de teto.

## Reproduzir

```powershell
.venv-desktop\Scripts\python.exe scripts\balance\audit_economy_arbitrage.py
```

Receitas sem insumos recebem piso de ouro igual à revenda máxima mais 1 mesmo sem Docas. O JSON adjacente contém cada preço configurado/efetivo, estoque, requisito, material compatível e os três resultados de desmontagem por equipamento.
