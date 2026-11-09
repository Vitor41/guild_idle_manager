# ML-029 E2 — simulação pareada de CPU

Simulação dos serviços reais de campanha com 20 seeds determinísticas pareadas, 100 Vigílias de seis horas por tratamento e nenhuma ação do jogador. Cada seed clona o mesmo save descartável; o baseline mantém o `recommended_power` do template e E2 usa a fórmula candidate para os mesmos tipos de contratos de combate. Não há acesso a saves do usuário.

A fórmula nova reduz a chance de qualquer guilda CPU que aceite esses contratos; isso é intencionalmente medido sob regras iguais, sem exceção de dificuldade. Os contadores elegíveis contam pares guilda/oferta/seed-ciclo em que a escala real de grupo/nível/requisitos permite a execução dentro da Vigília; iniciados são decisões efetivamente registradas como `contract`.

- Seeds: `2026110301–2026110320` (20 pares); 100 ciclos por cenário; fases: início 0–19, meio 20–59 e final 60–99.
- CSV com linhas por seed/cenário/escopo/fase: [lot_e2_ml029_cpu_paired_2026-11-08.csv](lot_e2_ml029_cpu_paired_2026-11-08.csv); detalhe pareado por seed: [lot_e2_ml029_cpu_paired_2026-11-08.json](lot_e2_ml029_cpu_paired_2026-11-08.json).

## CPU regional por fase

| Escopo | Fase | Elegíveis B→E2 | Iniciados B→E2 | Sucesso/falha B→E2 | Chance média B→E2 | Ouro líquido B→E2 | XP líquido B→E2 | Contratações B→E2 | Nível médio do elenco B→E2 | Pressão (ameaça ≥85 / segurança ≤25) B→E2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global | early | 19957 → 19944 | 19957 → 19944 | 15158/4799 → 9973/9971 | 76.3% → 50.1% | 376130 → 287218 | 6066891 → 4728414 | 1125 → 1011 | 3.96 → 3.79 | 260/277 → 277/298 |
| global | mid | 40000 → 40000 | 40000 → 40000 | 28761/11239 → 18564/21436 | 71.9% → 46.7% | 53937 → 138846 | 12038774 → 9261173 | 1001 → 809 | 5.08 → 4.90 | 634/316 → 734/395 |
| global | late | 40000 → 40000 | 40000 → 40000 | 28789/11211 → 18489/21511 | 71.9% → 46.2% | -127 → 4283 | 12208209 → 9268883 | 751 → 658 | 5.75 → 5.59 | 756/317 → 837/390 |
| home_region | early | 3997 → 3995 | 3997 → 3995 | 3128/869 → 2064/1931 | 78.1% → 52.1% | 73701 → 58166 | 1223152 → 937713 | 204 → 184 | 4.22 → 4.01 | 26/27 → 28/30 |
| home_region | mid | 8000 → 8000 | 8000 → 8000 | 5935/2065 → 3853/4147 | 74.1% → 48.2% | 5778 → 21691 | 2476126 → 1880470 | 191 → 151 | 5.31 → 5.13 | 50/23 → 106/58 |
| home_region | late | 8000 → 8000 | 8000 → 8000 | 5921/2079 → 3848/4152 | 74.3% → 47.8% | 260 → 50 | 2594839 → 1977783 | 141 → 124 | 5.92 → 5.81 | 56/23 → 128/60 |
| other_regions | early | 15960 → 15949 | 15960 → 15949 | 12030/3930 → 7909/8040 | 75.9% → 49.6% | 302429 → 229052 | 4843739 → 3790701 | 921 → 827 | 3.91 → 3.74 | 234/250 → 249/268 |
| other_regions | mid | 32000 → 32000 | 32000 → 32000 | 22826/9174 → 14711/17289 | 71.4% → 46.3% | 48159 → 117155 | 9562648 → 7380703 | 810 → 658 | 5.03 → 4.85 | 584/293 → 628/337 |
| other_regions | late | 32000 → 32000 | 32000 → 32000 | 22868/9132 → 14641/17359 | 71.3% → 45.8% | -387 → 4233 | 9613370 → 7291100 | 610 → 534 | 5.71 → 5.54 | 700/294 → 709/330 |

`home_region` é a região natal da guilda CPU; `other_regions` agrega as outras quatro regiões. `global` conta todas as cinco. Recursos líquidos vêm do before/after dos planos CPU e incluem custo de contratação e limites de capacidade; sucesso/fracasso e chance dizem respeito apenas a contratos efetivamente iniciados. A pressão regional conta estados pós-ciclo, não eventos independentes.

## Eventos e progressão CPU

| Indicador | Baseline | E2 | Δ E2 − baseline |
|---|---:|---:|---:|
| CPU success rate (média) | 72.9% | 47.5% | -25.4 p.p. |
| Ações CPU/ciclo (média por seed) | 50.62 | 50.62 | -0.01 |
| Rebeliões abertas (total em 20 seeds) | 4 | 8 | +4 |
| Rolagens de rebelião (total em 20 seeds) | 217 | 220 | +3 |
| Região-ciclos elegíveis para rebelião (total em 20 seeds) | 859 | 1061 | +202 |
| Portais abertos (total em 20 seeds) | 112 | 125 | +13 |
| Entradas CPU em portal (total em 20 seeds) | 0 | 0 | +0 |
| Sucessos CPU em portal (total em 20 seeds) | 0 | 0 | +0 |
| Nível médio final de guildas CPU (global) | 17.82 | 15.26 | -2.56 |
| Roster médio final (global) | 8.24 | 7.41 | -0.83 |
| Nível médio final de guildas CPU (home_region) | 20.36 | 17.38 | -2.99 |
| Roster médio final (home_region) | 9.20 | 8.24 | -0.96 |
| Nível médio final de guildas CPU (other_regions) | 17.31 | 14.84 | -2.47 |
| Roster médio final (other_regions) | 8.05 | 7.25 | -0.81 |

## Leitura de risco

Os efeitos sobre sucesso, recursos, ameaça/segurança, portais e rebeliões são resultados pareados das mesmas seeds, mas as execuções divergem deterministicamente depois da primeira resolução cujo sucesso mudou. Portanto, os deltas mostram o efeito total de equilíbrio ao longo de 100 ciclos, não uma comparação controlada de uma única oferta. As regiões permanecem com a mesma fórmula de Rank e grupo para CPU e jogador; não há regra especial para preservar sucesso CPU.
