# ML-029 E2 — simulação pareada de CPU

Simulação dos serviços reais de campanha com 5 seeds determinísticas pareadas, 100 Vigílias de seis horas por tratamento e nenhuma ação do jogador. Cada seed clona o mesmo save descartável; o baseline mantém o `recommended_power` do template e E2 usa a fórmula candidate para os mesmos tipos de contratos de combate. Não há acesso a saves do usuário.

A fórmula nova reduz a chance de qualquer guilda CPU que aceite esses contratos; isso é intencionalmente medido sob regras iguais, sem exceção de dificuldade. Os contadores elegíveis contam pares guilda/oferta/seed-ciclo em que a escala real de grupo/nível/requisitos permite a execução dentro da Vigília; iniciados são decisões efetivamente registradas como `contract`.

- Seeds: `2026110301–2026110305` (5 pares); 100 ciclos por cenário; fases: início 0–19, meio 20–59 e final 60–99.
- CSV com linhas por seed/cenário/escopo/fase: [lot_e2_ml029_cpu_paired_2026-11-09-adjusted-retest.csv](lot_e2_ml029_cpu_paired_2026-11-09-adjusted-retest.csv); detalhe pareado por seed: [lot_e2_ml029_cpu_paired_2026-11-09-adjusted-retest.json](lot_e2_ml029_cpu_paired_2026-11-09-adjusted-retest.json).

## CPU regional por fase

| Escopo | Fase | Elegíveis B→E2 | Iniciados B→E2 | Sucesso/falha B→E2 | Chance média B→E2 | Ouro líquido B→E2 | XP líquido B→E2 | Contratações B→E2 | Nível médio do elenco B→E2 | Pressão (ameaça ≥85 / segurança ≤25) B→E2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global | early | 4999 → 4995 | 4999 → 4995 | 3804/1195 → 2632/2363 | 76.2% → 53.0% | 91834 → 71648 | 1492418 → 1184084 | 282 → 252 | 3.91 → 3.75 | 65/70 → 70/75 |
| global | mid | 10000 → 10000 | 10000 → 10000 | 7150/2850 → 4944/5056 | 71.8% → 49.7% | 15609 → 34399 | 3054787 → 2440860 | 255 → 211 | 5.08 → 4.91 | 159/82 → 184/100 |
| global | late | 10000 → 10000 | 10000 → 10000 | 7201/2799 → 4862/5138 | 72.0% → 49.4% | 43 → 1589 | 3035369 → 2369001 | 184 → 163 | 5.79 → 5.63 | 190/78 → 207/98 |
| home_region | early | 1000 → 999 | 1000 → 999 | 801/199 → 550/449 | 79.0% → 55.7% | 17204 → 14052 | 303673 → 232924 | 50 → 46 | 3.97 → 3.75 | 0/0 → 0/0 |
| home_region | mid | 2000 → 2000 | 2000 → 2000 | 1462/538 → 1033/967 | 73.9% → 52.0% | 1930 → 5208 | 611263 → 487083 | 51 → 39 | 5.11 → 5.03 | 14/8 → 17/10 |
| home_region | late | 2000 → 2000 | 2000 → 2000 | 1480/520 → 1028/972 | 74.0% → 51.8% | 14 → -41 | 642417 → 511799 | 35 → 33 | 5.73 → 5.69 | 20/7 → 22/10 |
| other_regions | early | 3999 → 3996 | 3999 → 3996 | 3003/996 → 2082/1914 | 75.5% → 52.3% | 74630 → 57596 | 1188745 → 951160 | 232 → 206 | 3.89 → 3.75 | 65/70 → 70/75 |
| other_regions | mid | 8000 → 8000 | 8000 → 8000 | 5688/2312 → 3911/4089 | 71.3% → 49.1% | 13679 → 29191 | 2443524 → 1953777 | 204 → 172 | 5.07 → 4.88 | 145/74 → 167/90 |
| other_regions | late | 8000 → 8000 | 8000 → 8000 | 5721/2279 → 3834/4166 | 71.5% → 48.8% | 29 → 1630 | 2392952 → 1857202 | 149 → 130 | 5.80 → 5.62 | 170/71 → 185/88 |

## Portais e rebeliões por fase e escopo

| Escopo | Fase | Portais abertos B→E2 | Rebeliões abertas B→E2 |
|---|---|---:|---:|
| global | early | 5 → 5 | 1 → 1 |
| global | mid | 10 → 12 | 0 → 0 |
| global | late | 13 → 14 | 0 → 2 |
| home_region | early | 0 → 0 | 0 → 0 |
| home_region | mid | 1 → 1 | 0 → 0 |
| home_region | late | 2 → 2 | 0 → 0 |
| other_regions | early | 5 → 5 | 1 → 1 |
| other_regions | mid | 9 → 11 | 0 → 0 |
| other_regions | late | 11 → 12 | 0 → 2 |

`home_region` é a região natal da guilda CPU; `other_regions` agrega as outras quatro regiões. `global` conta todas as cinco. Recursos líquidos vêm do before/after dos planos CPU e incluem custo de contratação e limites de capacidade; sucesso/fracasso e chance dizem respeito apenas a contratos efetivamente iniciados. A pressão regional conta estados pós-ciclo, não eventos independentes.

## Eventos e progressão CPU

| Indicador | Baseline | E2 | Δ E2 − baseline |
|---|---:|---:|---:|
| CPU success rate (média) | 72.7% | 50.2% | -22.6 p.p. |
| Ações CPU/ciclo (média por seed) | 50.64 | 50.63 | -0.01 |
| Rebeliões abertas (total em 5 seeds) | 1 | 3 | +2 |
| Rolagens de rebelião (total em 5 seeds) | 55 | 55 | +0 |
| Região-ciclos elegíveis para rebelião (total em 5 seeds) | 216 | 268 | +52 |
| Portais abertos (total em 5 seeds) | 28 | 31 | +3 |
| Entradas CPU em portal (total em 5 seeds) | 0 | 0 | +0 |
| Sucessos CPU em portal (total em 5 seeds) | 0 | 0 | +0 |
| Nível médio final de guildas CPU (global) | 17.83 | 15.54 | -2.29 |
| Roster médio final (global) | 8.26 | 7.47 | -0.79 |
| Nível médio final de guildas CPU (home_region) | 20.20 | 17.65 | -2.55 |
| Roster médio final (home_region) | 9.30 | 8.40 | -0.90 |
| Nível médio final de guildas CPU (other_regions) | 17.36 | 15.12 | -2.24 |
| Roster médio final (other_regions) | 8.05 | 7.28 | -0.77 |

## Leitura de risco

Os efeitos sobre sucesso, recursos, ameaça/segurança, portais e rebeliões são resultados pareados das mesmas seeds, mas as execuções divergem deterministicamente depois da primeira resolução cujo sucesso mudou. Portanto, os deltas mostram o efeito total de equilíbrio ao longo de 100 ciclos, não uma comparação controlada de uma única oferta. As regiões permanecem com a mesma fórmula de Rank e grupo para CPU e jogador; não há regra especial para preservar sucesso CPU.
