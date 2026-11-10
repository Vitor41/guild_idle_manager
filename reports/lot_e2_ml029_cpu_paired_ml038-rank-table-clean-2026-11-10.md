# ML-029 E2 — simulação pareada de CPU

Simulação dos serviços reais de campanha com 5 seeds determinísticas pareadas, 100 Vigílias de seis horas por tratamento e nenhuma ação do jogador. Cada seed clona o mesmo save descartável; o baseline mantém o `recommended_power` do template e E2 usa a fórmula candidate para os mesmos tipos de contratos de combate. Não há acesso a saves do usuário.

A fórmula nova reduz a chance de qualquer guilda CPU que aceite esses contratos; isso é intencionalmente medido sob regras iguais, sem exceção de dificuldade. Os contadores elegíveis contam pares guilda/oferta/seed-ciclo em que a escala real de grupo/nível/requisitos permite a execução dentro da Vigília; iniciados são decisões efetivamente registradas como `contract`.

- Seeds: `2026110301–2026110305` (5 pares); 100 ciclos por cenário; fases: início 0–19, meio 20–59 e final 60–99.
- CSV com linhas por seed/cenário/escopo/fase: [lot_e2_ml029_cpu_paired_ml038-rank-table-clean-2026-11-10.csv](lot_e2_ml029_cpu_paired_ml038-rank-table-clean-2026-11-10.csv); detalhe pareado por seed: [lot_e2_ml029_cpu_paired_ml038-rank-table-clean-2026-11-10.json](lot_e2_ml029_cpu_paired_ml038-rank-table-clean-2026-11-10.json).

## CPU regional por fase

| Escopo | Fase | Elegíveis B→E2 | Iniciados B→E2 | Sucesso/falha B→E2 | Chance média B→E2 | Ouro líquido B→E2 | XP líquido B→E2 | Contratações B→E2 | Nível médio do elenco B→E2 | Pressão (ameaça ≥85 / segurança ≤25) B→E2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global | early | 5000 → 5000 | 5000 → 5000 | 4221/779 → 2919/2081 | 84.3% → 59.7% | 98383 → 82128 | 1862334 → 1464988 | 298 → 267 | 4.26 → 4.05 | 65/67 → 68/74 |
| global | mid | 10000 → 10000 | 10000 → 10000 | 8655/1345 → 6112/3888 | 87.5% → 61.5% | 9101 → 25451 | 3915144 → 3059419 | 302 → 254 | 5.61 → 5.43 | 150/61 → 168/90 |
| global | late | 10000 → 10000 | 10000 → 10000 | 8935/1065 → 6512/3488 | 89.2% → 64.2% | -80 → -44 | 4082839 → 3230326 | 233 → 205 | 6.33 → 6.25 | 180/61 → 194/87 |
| home_region | early | 1000 → 1000 | 1000 → 1000 | 872/128 → 613/387 | 87.7% → 63.1% | 18435 → 16600 | 377119 → 298314 | 53 → 49 | 4.35 → 4.05 | 0/0 → 0/0 |
| home_region | mid | 2000 → 2000 | 2000 → 2000 | 1767/233 → 1326/674 | 88.8% → 66.3% | 762 → 2595 | 801710 → 651113 | 61 → 49 | 5.77 → 5.49 | 26/11 → 0/0 |
| home_region | late | 2000 → 2000 | 2000 → 2000 | 1807/193 → 1418/582 | 90.0% → 69.6% | -52 → 65 | 799314 → 665618 | 42 → 42 | 6.47 → 6.27 | 38/12 → 0/0 |
| other_regions | early | 4000 → 4000 | 4000 → 4000 | 3349/651 → 2306/1694 | 83.5% → 58.9% | 79948 → 65528 | 1485215 → 1166674 | 245 → 218 | 4.24 → 4.04 | 65/67 → 68/74 |
| other_regions | mid | 8000 → 8000 | 8000 → 8000 | 6888/1112 → 4786/3214 | 87.2% → 60.3% | 8339 → 22856 | 3113434 → 2408306 | 241 → 205 | 5.57 → 5.42 | 124/50 → 168/90 |
| other_regions | late | 8000 → 8000 | 8000 → 8000 | 7128/872 → 5094/2906 | 89.0% → 62.8% | -28 → -109 | 3283525 → 2564708 | 191 → 163 | 6.30 → 6.24 | 142/49 → 194/87 |

## Portais e rebeliões por fase e escopo

| Escopo | Fase | Portais abertos B→E2 | Rebeliões abertas B→E2 |
|---|---|---:|---:|
| global | early | 5 → 5 | 1 → 1 |
| global | mid | 12 → 14 | 1 → 3 |
| global | late | 10 → 12 | 2 → 4 |
| home_region | early | 0 → 0 | 0 → 0 |
| home_region | mid | 3 → 0 | 0 → 0 |
| home_region | late | 2 → 0 | 0 → 0 |
| other_regions | early | 5 → 5 | 1 → 1 |
| other_regions | mid | 9 → 14 | 1 → 3 |
| other_regions | late | 8 → 12 | 2 → 4 |

`home_region` é a região natal da guilda CPU; `other_regions` agrega as outras quatro regiões. `global` conta todas as cinco. Recursos líquidos vêm do before/after dos planos CPU e incluem custo de contratação e limites de capacidade; sucesso/fracasso e chance dizem respeito apenas a contratos efetivamente iniciados. A pressão regional conta estados pós-ciclo, não eventos independentes.

## Eventos e progressão CPU

| Indicador | Baseline | E2 | Δ E2 − baseline |
|---|---:|---:|---:|
| CPU success rate (média) | 87.1% | 62.5% | -24.6 p.p. |
| Ações CPU/ciclo (média por seed) | 50.85 | 50.84 | -0.01 |
| Rebeliões abertas (total em 5 seeds) | 4 | 8 | +4 |
| Rolagens de rebelião (total em 5 seeds) | 178 | 229 | +51 |
| Região-ciclos elegíveis para rebelião (total em 5 seeds) | 185 | 238 | +53 |
| Portais abertos (total em 5 seeds) | 27 | 31 | +4 |
| Entradas CPU em portal (total em 5 seeds) | 25 | 39 | +14 |
| Sucessos CPU em portal (total em 5 seeds) | 17 | 29 | +12 |
| Nível médio final de guildas CPU (global) | 20.60 | 17.94 | -2.66 |
| Roster médio final (global) | 9.19 | 8.30 | -0.89 |
| Nível médio final de guildas CPU (home_region) | 23.00 | 20.35 | -2.65 |
| Roster médio final (home_region) | 10.30 | 9.50 | -0.80 |
| Nível médio final de guildas CPU (other_regions) | 20.12 | 17.46 | -2.66 |
| Roster médio final (other_regions) | 8.97 | 8.06 | -0.91 |

## Leitura de risco

Os efeitos sobre sucesso, recursos, ameaça/segurança, portais e rebeliões são resultados pareados das mesmas seeds, mas as execuções divergem deterministicamente depois da primeira resolução cujo sucesso mudou. Portanto, os deltas mostram o efeito total de equilíbrio ao longo de 100 ciclos, não uma comparação controlada de uma única oferta. As regiões permanecem com a mesma fórmula de Rank e grupo para CPU e jogador; não há regra especial para preservar sucesso CPU.
