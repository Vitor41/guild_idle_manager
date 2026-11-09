# ML-029 E2 — simulação pareada de CPU

Simulação dos serviços reais de campanha com 5 seeds determinísticas pareadas, 100 Vigílias de seis horas por tratamento e nenhuma ação do jogador. Cada seed clona o mesmo save descartável; o baseline mantém o `recommended_power` do template e E2 usa a fórmula candidate para os mesmos tipos de contratos de combate. Não há acesso a saves do usuário.

A fórmula nova reduz a chance de qualquer guilda CPU que aceite esses contratos; isso é intencionalmente medido sob regras iguais, sem exceção de dificuldade. Os contadores elegíveis contam pares guilda/oferta/seed-ciclo em que a escala real de grupo/nível/requisitos permite a execução dentro da Vigília; iniciados são decisões efetivamente registradas como `contract`.

- Seeds: `2026110301–2026110305` (5 pares); 100 ciclos por cenário; fases: início 0–19, meio 20–59 e final 60–99.
- CSV com linhas por seed/cenário/escopo/fase: [lot_e2_ml029_cpu_paired_2026-11-09-minus30-final.csv](lot_e2_ml029_cpu_paired_2026-11-09-minus30-final.csv); detalhe pareado por seed: [lot_e2_ml029_cpu_paired_2026-11-09-minus30-final.json](lot_e2_ml029_cpu_paired_2026-11-09-minus30-final.json).

## CPU regional por fase

| Escopo | Fase | Elegíveis B→E2 | Iniciados B→E2 | Sucesso/falha B→E2 | Chance média B→E2 | Ouro líquido B→E2 | XP líquido B→E2 | Contratações B→E2 | Nível médio do elenco B→E2 | Pressão (ameaça ≥85 / segurança ≤25) B→E2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global | early | 4999 → 4995 | 4999 → 4995 | 3804/1195 → 2731/2264 | 76.2% → 55.0% | 91834 → 73942 | 1492418 → 1204220 | 282 → 253 | 3.91 → 3.75 | 65/70 → 70/74 |
| global | mid | 10000 → 10000 | 10000 → 10000 | 7150/2850 → 5184/4816 | 71.8% → 51.7% | 15609 → 32161 | 3054787 → 2497123 | 255 → 215 | 5.08 → 4.92 | 159/82 → 177/99 |
| global | late | 10000 → 10000 | 10000 → 10000 | 7201/2799 → 5071/4929 | 72.0% → 51.3% | 43 → 1258 | 3035369 → 2420367 | 184 → 170 | 5.79 → 5.64 | 190/78 → 209/95 |
| home_region | early | 1000 → 999 | 1000 → 999 | 801/199 → 571/428 | 79.0% → 57.8% | 17204 → 14469 | 303673 → 237899 | 50 → 46 | 3.97 → 3.75 | 0/0 → 0/0 |
| home_region | mid | 2000 → 2000 | 2000 → 2000 | 1462/538 → 1077/923 | 73.9% → 54.0% | 1930 → 4791 | 611263 → 498532 | 51 → 40 | 5.11 → 5.00 | 14/8 → 16/10 |
| home_region | late | 2000 → 2000 | 2000 → 2000 | 1480/520 → 1084/916 | 74.0% → 53.7% | 14 → -155 | 642417 → 524569 | 35 → 36 | 5.73 → 5.66 | 20/7 → 22/10 |
| other_regions | early | 3999 → 3996 | 3999 → 3996 | 3003/996 → 2160/1836 | 75.5% → 54.4% | 74630 → 59473 | 1188745 → 966321 | 232 → 207 | 3.89 → 3.75 | 65/70 → 70/74 |
| other_regions | mid | 8000 → 8000 | 8000 → 8000 | 5688/2312 → 4107/3893 | 71.3% → 51.1% | 13679 → 27370 | 2443524 → 1998591 | 204 → 175 | 5.07 → 4.90 | 145/74 → 161/89 |
| other_regions | late | 8000 → 8000 | 8000 → 8000 | 5721/2279 → 3987/4013 | 71.5% → 50.7% | 29 → 1413 | 2392952 → 1895798 | 149 → 134 | 5.80 → 5.64 | 170/71 → 187/85 |

## Portais e rebeliões por fase e escopo

| Escopo | Fase | Portais abertos B→E2 | Rebeliões abertas B→E2 |
|---|---|---:|---:|
| global | early | 5 → 5 | 1 → 1 |
| global | mid | 10 → 14 | 0 → 0 |
| global | late | 13 → 12 | 0 → 3 |
| home_region | early | 0 → 0 | 0 → 0 |
| home_region | mid | 1 → 2 | 0 → 0 |
| home_region | late | 2 → 1 | 0 → 0 |
| other_regions | early | 5 → 5 | 1 → 1 |
| other_regions | mid | 9 → 12 | 0 → 0 |
| other_regions | late | 11 → 11 | 0 → 3 |

`home_region` é a região natal da guilda CPU; `other_regions` agrega as outras quatro regiões. `global` conta todas as cinco. Recursos líquidos vêm do before/after dos planos CPU e incluem custo de contratação e limites de capacidade; sucesso/fracasso e chance dizem respeito apenas a contratos efetivamente iniciados. A pressão regional conta estados pós-ciclo, não eventos independentes.

## Eventos e progressão CPU

| Indicador | Baseline | E2 | Δ E2 − baseline |
|---|---:|---:|---:|
| CPU success rate (média) | 72.7% | 52.4% | -20.4 p.p. |
| Ações CPU/ciclo (média por seed) | 50.64 | 50.63 | -0.01 |
| Rebeliões abertas (total em 5 seeds) | 1 | 4 | +3 |
| Rolagens de rebelião (total em 5 seeds) | 55 | 55 | +0 |
| Região-ciclos elegíveis para rebelião (total em 5 seeds) | 216 | 263 | +47 |
| Portais abertos (total em 5 seeds) | 28 | 31 | +3 |
| Entradas CPU em portal (total em 5 seeds) | 0 | 0 | +0 |
| Sucessos CPU em portal (total em 5 seeds) | 0 | 0 | +0 |
| Nível médio final de guildas CPU (global) | 17.83 | 15.74 | -2.09 |
| Roster médio final (global) | 8.26 | 7.57 | -0.69 |
| Nível médio final de guildas CPU (home_region) | 20.20 | 17.80 | -2.40 |
| Roster médio final (home_region) | 9.30 | 8.60 | -0.70 |
| Nível médio final de guildas CPU (other_regions) | 17.36 | 15.33 | -2.03 |
| Roster médio final (other_regions) | 8.05 | 7.36 | -0.69 |

## Leitura de risco

Os efeitos sobre sucesso, recursos, ameaça/segurança, portais e rebeliões são resultados pareados das mesmas seeds, mas as execuções divergem deterministicamente depois da primeira resolução cujo sucesso mudou. Portanto, os deltas mostram o efeito total de equilíbrio ao longo de 100 ciclos, não uma comparação controlada de uma única oferta. As regiões permanecem com a mesma fórmula de Rank e grupo para CPU e jogador; não há regra especial para preservar sucesso CPU.
