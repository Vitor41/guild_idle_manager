# ML-038 — simulação pareada de CPU

Simulação dos serviços reais de campanha com 5 seeds determinísticas pareadas, 100 Vigílias de seis horas por tratamento e nenhuma ação do jogador. Cada seed clona o mesmo save descartável; baseline: ML-038 previous multipliers E .700, D .735, C .770, B .840, A .945, S 1.085; candidato usa os mesmos tipos de contratos de combate. Não há acesso a saves do usuário.

A fórmula nova reduz a chance de qualquer guilda CPU que aceite esses contratos; isso é intencionalmente medido sob regras iguais, sem exceção de dificuldade. Os contadores elegíveis contam pares guilda/oferta/seed-ciclo em que a escala real de grupo/nível/requisitos permite a execução dentro da Vigília; iniciados são decisões efetivamente registradas como `contract`.

- Seeds: `2026110301–2026110305` (5 pares); 100 ciclos por cenário; fases: início 0–19, meio 20–59 e final 60–99.
- CSV com linhas por seed/cenário/escopo/fase: [lot_e2_ml029_cpu_paired_ml038-old-table-clean-2026-11-10.csv](lot_e2_ml029_cpu_paired_ml038-old-table-clean-2026-11-10.csv); detalhe pareado por seed: [lot_e2_ml029_cpu_paired_ml038-old-table-clean-2026-11-10.json](lot_e2_ml029_cpu_paired_ml038-old-table-clean-2026-11-10.json).

## CPU regional por fase

| Escopo | Fase | Elegíveis B→E2 | Iniciados B→E2 | Sucesso/falha B→E2 | Chance média B→E2 | Ouro líquido B→E2 | XP líquido B→E2 | Contratações B→E2 | Nível médio do elenco B→E2 | Pressão (ameaça ≥85 / segurança ≤25) B→E2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global | early | 5000 → 5000 | 5000 → 5000 | 3023/1977 → 2919/2081 | 62.1% → 59.7% | 84431 → 82128 | 1495450 → 1464988 | 270 → 267 | 4.05 → 4.05 | 66/74 → 68/74 |
| global | mid | 10000 → 10000 | 10000 → 10000 | 6385/3615 → 6112/3888 | 64.3% → 61.5% | 22959 → 25451 | 3146852 → 3059419 | 257 → 254 | 5.43 → 5.43 | 166/87 → 168/90 |
| global | late | 10000 → 10000 | 10000 → 10000 | 6787/3213 → 6512/3488 | 67.3% → 64.2% | 139 → -44 | 3318447 → 3230326 | 210 → 205 | 6.23 → 6.25 | 190/82 → 194/87 |
| home_region | early | 1000 → 1000 | 1000 → 1000 | 641/359 → 613/387 | 65.6% → 63.1% | 17183 → 16600 | 305768 → 298314 | 49 → 49 | 4.11 → 4.05 | 0/0 → 0/0 |
| home_region | mid | 2000 → 2000 | 2000 → 2000 | 1374/626 → 1326/674 | 69.2% → 66.3% | 1949 → 2595 | 666523 → 651113 | 51 → 49 | 5.47 → 5.49 | 0/0 → 0/0 |
| home_region | late | 2000 → 2000 | 2000 → 2000 | 1476/524 → 1418/582 | 72.7% → 69.6% | 57 → 65 | 682738 → 665618 | 42 → 42 | 6.29 → 6.27 | 0/0 → 0/0 |
| other_regions | early | 4000 → 4000 | 4000 → 4000 | 2382/1618 → 2306/1694 | 61.3% → 58.9% | 67248 → 65528 | 1189682 → 1166674 | 221 → 218 | 4.04 → 4.04 | 66/74 → 68/74 |
| other_regions | mid | 8000 → 8000 | 8000 → 8000 | 5011/2989 → 4786/3214 | 63.1% → 60.3% | 21010 → 22856 | 2480329 → 2408306 | 206 → 205 | 5.42 → 5.42 | 166/87 → 168/90 |
| other_regions | late | 8000 → 8000 | 8000 → 8000 | 5311/2689 → 5094/2906 | 65.9% → 62.8% | 82 → -109 | 2635709 → 2564708 | 168 → 163 | 6.21 → 6.24 | 190/82 → 194/87 |

## Portais e rebeliões por fase e escopo

| Escopo | Fase | Portais abertos B→E2 | Rebeliões abertas B→E2 |
|---|---|---:|---:|
| global | early | 5 → 5 | 1 → 1 |
| global | mid | 12 → 14 | 3 → 3 |
| global | late | 11 → 12 | 2 → 4 |
| home_region | early | 0 → 0 | 0 → 0 |
| home_region | mid | 0 → 0 | 0 → 0 |
| home_region | late | 0 → 0 | 0 → 0 |
| other_regions | early | 5 → 5 | 1 → 1 |
| other_regions | mid | 12 → 14 | 3 → 3 |
| other_regions | late | 11 → 12 | 2 → 4 |

`home_region` é a região natal da guilda CPU; `other_regions` agrega as outras quatro regiões. `global` conta todas as cinco. Recursos líquidos vêm do before/after dos planos CPU e incluem custo de contratação e limites de capacidade; sucesso/fracasso e chance dizem respeito apenas a contratos efetivamente iniciados. A pressão regional conta estados pós-ciclo, não eventos independentes.

## Eventos e progressão CPU

| Indicador | Baseline | E2 | Δ E2 − baseline |
|---|---:|---:|---:|
| CPU success rate (média) | 65.0% | 62.5% | -2.6 p.p. |
| Ações CPU/ciclo (média por seed) | 50.82 | 50.84 | +0.02 |
| Rebeliões abertas (total em 5 seeds) | 6 | 8 | +2 |
| Rolagens de rebelião (total em 5 seeds) | 218 | 229 | +11 |
| Região-ciclos elegíveis para rebelião (total em 5 seeds) | 227 | 238 | +11 |
| Portais abertos (total em 5 seeds) | 28 | 31 | +3 |
| Entradas CPU em portal (total em 5 seeds) | 33 | 39 | +6 |
| Sucessos CPU em portal (total em 5 seeds) | 24 | 29 | +5 |
| Nível médio final de guildas CPU (global) | 18.19 | 17.94 | -0.25 |
| Roster médio final (global) | 8.39 | 8.30 | -0.09 |
| Nível médio final de guildas CPU (home_region) | 20.70 | 20.35 | -0.35 |
| Roster médio final (home_region) | 9.60 | 9.50 | -0.10 |
| Nível médio final de guildas CPU (other_regions) | 17.69 | 17.46 | -0.23 |
| Roster médio final (other_regions) | 8.15 | 8.06 | -0.09 |

## Leitura de risco

Os efeitos sobre sucesso, recursos, ameaça/segurança, portais e rebeliões são resultados pareados das mesmas seeds, mas as execuções divergem deterministicamente depois da primeira resolução cujo sucesso mudou. Portanto, os deltas mostram o efeito total de equilíbrio ao longo de 100 ciclos, não uma comparação controlada de uma única oferta. As regiões permanecem com a mesma fórmula de Rank e grupo para CPU e jogador; não há regra especial para preservar sucesso CPU.
