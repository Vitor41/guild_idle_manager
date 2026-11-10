# ML-029 E2 — simulação pareada de CPU

Simulação dos serviços reais de campanha com 1 seeds determinísticas pareadas, 100 Vigílias de seis horas por tratamento e nenhuma ação do jogador. Cada seed clona o mesmo save descartável; o baseline mantém o `recommended_power` do template e E2 usa a fórmula candidate para os mesmos tipos de contratos de combate. Não há acesso a saves do usuário.

A fórmula nova reduz a chance de qualquer guilda CPU que aceite esses contratos; isso é intencionalmente medido sob regras iguais, sem exceção de dificuldade. Os contadores elegíveis contam pares guilda/oferta/seed-ciclo em que a escala real de grupo/nível/requisitos permite a execução dentro da Vigília; iniciados são decisões efetivamente registradas como `contract`.

- Seeds: `2026110301–2026110301` (1 pares); 100 ciclos por cenário; fases: início 0–19, meio 20–59 e final 60–99.
- CSV com linhas por seed/cenário/escopo/fase: [lot_e2_ml029_cpu_paired_ml038-rank-table-2026-11-09.csv](lot_e2_ml029_cpu_paired_ml038-rank-table-2026-11-09.csv); detalhe pareado por seed: [lot_e2_ml029_cpu_paired_ml038-rank-table-2026-11-09.json](lot_e2_ml029_cpu_paired_ml038-rank-table-2026-11-09.json).

## CPU regional por fase

| Escopo | Fase | Elegíveis B→E2 | Iniciados B→E2 | Sucesso/falha B→E2 | Chance média B→E2 | Ouro líquido B→E2 | XP líquido B→E2 | Contratações B→E2 | Nível médio do elenco B→E2 | Pressão (ameaça ≥85 / segurança ≤25) B→E2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global | early | 1000 → 1000 | 1000 → 1000 | 837/163 → 594/406 | 83.9% → 61.2% | 18962 → 16251 | 360039 → 282881 | 61 → 56 | 4.25 → 4.02 | 13/14 → 13/15 |
| global | mid | 2000 → 2000 | 2000 → 2000 | 1754/246 → 1246/754 | 87.3% → 61.9% | 2575 → 5275 | 773038 → 609416 | 56 → 44 | 5.51 → 5.26 | 30/12 → 34/18 |
| global | late | 2000 → 2000 | 2000 → 2000 | 1789/211 → 1288/712 | 89.0% → 64.3% | 63 → 74 | 829474 → 657658 | 47 → 45 | 6.30 → 6.20 | 36/13 → 38/17 |
| home_region | early | 200 → 200 | 200 → 200 | 171/29 → 119/81 | 88.0% → 64.9% | 3540 → 3539 | 79895 → 64562 | 12 → 12 | 4.54 → 4.36 | 0/0 → 0/0 |
| home_region | mid | 400 → 400 | 400 → 400 | 371/29 → 271/129 | 90.2% → 65.4% | 60 → 61 | 156405 → 121695 | 11 → 7 | 5.70 → 5.32 | 0/0 → 0/0 |
| home_region | late | 400 → 400 | 400 → 400 | 367/33 → 279/121 | 92.3% → 69.4% | 0 → 0 | 164560 → 133035 | 9 → 10 | 6.22 → 6.20 | 0/0 → 0/0 |
| other_regions | early | 800 → 800 | 800 → 800 | 666/134 → 475/325 | 82.9% → 60.3% | 15422 → 12712 | 280144 → 218319 | 49 → 44 | 4.18 → 3.94 | 13/14 → 13/15 |
| other_regions | mid | 1600 → 1600 | 1600 → 1600 | 1383/217 → 975/625 | 86.6% → 61.1% | 2515 → 5214 | 616633 → 487721 | 45 → 37 | 5.47 → 5.25 | 30/12 → 34/18 |
| other_regions | late | 1600 → 1600 | 1600 → 1600 | 1422/178 → 1009/591 | 88.2% → 63.0% | 63 → 74 | 664914 → 524623 | 38 → 35 | 6.32 → 6.20 | 36/13 → 38/17 |

## Portais e rebeliões por fase e escopo

| Escopo | Fase | Portais abertos B→E2 | Rebeliões abertas B→E2 |
|---|---|---:|---:|
| global | early | 1 → 1 | 0 → 0 |
| global | mid | 3 → 3 | 0 → 0 |
| global | late | 1 → 2 | 0 → 0 |
| home_region | early | 0 → 0 | 0 → 0 |
| home_region | mid | 0 → 0 | 0 → 0 |
| home_region | late | 0 → 0 | 0 → 0 |
| other_regions | early | 1 → 1 | 0 → 0 |
| other_regions | mid | 3 → 3 | 0 → 0 |
| other_regions | late | 1 → 2 | 0 → 0 |

`home_region` é a região natal da guilda CPU; `other_regions` agrega as outras quatro regiões. `global` conta todas as cinco. Recursos líquidos vêm do before/after dos planos CPU e incluem custo de contratação e limites de capacidade; sucesso/fracasso e chance dizem respeito apenas a contratos efetivamente iniciados. A pressão regional conta estados pós-ciclo, não eventos independentes.

## Eventos e progressão CPU

| Indicador | Baseline | E2 | Δ E2 − baseline |
|---|---:|---:|---:|
| CPU success rate (média) | 87.4% | 62.7% | -24.6 p.p. |
| Ações CPU/ciclo (média por seed) | 50.79 | 50.80 | +0.01 |
| Rebeliões abertas (total em 1 seeds) | 0 | 0 | +0 |
| Rolagens de rebelião (total em 1 seeds) | 38 | 47 | +9 |
| Região-ciclos elegíveis para rebelião (total em 1 seeds) | 38 | 47 | +9 |
| Portais abertos (total em 1 seeds) | 5 | 6 | +1 |
| Entradas CPU em portal (total em 1 seeds) | 6 | 7 | +1 |
| Sucessos CPU em portal (total em 1 seeds) | 4 | 5 | +1 |
| Nível médio final de guildas CPU (global) | 20.50 | 17.88 | -2.62 |
| Roster médio final (global) | 9.08 | 8.29 | -0.79 |
| Nível médio final de guildas CPU (home_region) | 23.00 | 20.50 | -2.50 |
| Roster médio final (home_region) | 10.50 | 9.75 | -0.75 |
| Nível médio final de guildas CPU (other_regions) | 20.00 | 17.35 | -2.65 |
| Roster médio final (other_regions) | 8.80 | 8.00 | -0.80 |

## Leitura de risco

Os efeitos sobre sucesso, recursos, ameaça/segurança, portais e rebeliões são resultados pareados das mesmas seeds, mas as execuções divergem deterministicamente depois da primeira resolução cujo sucesso mudou. Portanto, os deltas mostram o efeito total de equilíbrio ao longo de 100 ciclos, não uma comparação controlada de uma única oferta. As regiões permanecem com a mesma fórmula de Rank e grupo para CPU e jogador; não há regra especial para preservar sucesso CPU.
