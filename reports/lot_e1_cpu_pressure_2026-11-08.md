# Regional CPU event balance — 20 campaigns

Deterministic SQLite campaigns; 100 six-hour cycles each; player takes no actions. Events, timers, CPU plans, snapshots and region state use the live services.
The funnel aligns pressure and threshold state from snapshot N−1 to the rebellion check when Vigília N opens; global-lock cycles are inferred from the active event deadline and the preceding snapshot.

- Campaigns with at least one portal: **20/20**; without portal: **0**; opened portals: **85**; first portal cycles: `[4, 9, 13, 5, 9, 5, 21, 7, 14, 11, 5, 15, 6, 10, 7, 9, 5, 7, 7, 7]`.
- Campaigns with at least one rebellion: **5/20**; opened rebellions: **6**; first rebellion cycles: `[95, 19, 95, 13, 31]`; mean selected rolls: **12.0**; mean cycles with a vulnerable region: **67.0**.
- Maximum simultaneous active global rebellions: **1**.
- Mean CPU success rate: **73.0%**.
- Mean CPU actions per global Vigília: **50.62** with throughput set by eligible offers, available mercenaries, activity durations, and 1h player priority.
- CPU actions per Vigília: guilda da região natal **10.13**; nas outras quatro regiões, juntas, **40.49**.
- Minimum regional Vigílias with at least one CPU action: **100/100**.
- Final security range across all regions/campaigns: **20.0–100.0**; threat range: **0.0–96.55**.
- Concurrent regional pressure per cycle (p50/p90/max regions): security_at_floor: 1/1/1; threat_at_least_85: 1/1/1; joint_rebellion_vulnerability: 1/1/1.

- Rebellion funnel across 20×100 Vigílias: 1980 pressure-target region-cycles; 1352 eligible region-cycles in 1352 campaign-cycles; 240 selected rolls × 2% = 4.8 expected openings; 6 observed, 234 RNG failures.
- Eligible region-cycles withheld by regional cooldown: 1100; by one-roll-per-cycle cap: 0; by active global event limit: 12 across 12 campaign-cycles; unclassified: 0.

| Região | Ciclos-alvo | Região-ciclos elegíveis | Bloqueio cooldown | Bloqueio limite por ciclo | Rolagens | Rebeliões | Sem atribuição |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 425 | 293 | 237 | 0 | 52 | 2 | 0 |
| Bosque de Âmbar (`bosque-ambar`) | 338 | 224 | 182 | 0 | 40 | 1 | 0 |
| Costa das Brumas (`costa-brumas`) | 268 | 181 | 149 | 0 | 32 | 0 | 0 |
| Terras de Cinza (`terras-cinza`) | 239 | 153 | 123 | 0 | 28 | 1 | 0 |
| Picos do Norte (`picos-norte`) | 710 | 501 | 409 | 0 | 88 | 2 | 0 |

| Vigília | Campanhas sob pressão | Campanhas com região elegível | Região-ciclos elegíveis | Rolagens selecionadas | RNG falhou | Bloqueio cooldown | Bloqueio global | Rebeliões | Sem atribuição |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 3 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 6 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 7 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 8 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 9 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 10 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 11 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 12 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 13 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 14 | 20 | 20 | 20 | 0 | 0 | 19 | 1 | 0 | 0 |
| 15 | 20 | 20 | 20 | 0 | 0 | 19 | 1 | 0 | 0 |
| 16 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 17 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 18 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 19 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 20 | 20 | 20 | 20 | 0 | 0 | 19 | 1 | 0 | 0 |
| 21 | 20 | 20 | 20 | 0 | 0 | 19 | 1 | 0 | 0 |
| 22 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 23 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 24 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 25 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 26 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 27 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 28 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 29 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 30 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 31 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 32 | 20 | 20 | 20 | 0 | 0 | 19 | 1 | 0 | 0 |
| 33 | 20 | 20 | 20 | 0 | 0 | 19 | 1 | 0 | 0 |
| 34 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 35 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 36 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 37 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 38 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 39 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 40 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 41 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 42 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 43 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 44 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 45 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 46 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 47 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 48 | 20 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| 49 | 20 | 17 | 17 | 16 | 16 | 1 | 0 | 0 | 0 |
| 50 | 20 | 20 | 20 | 3 | 3 | 17 | 0 | 0 | 0 |
| 51 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 52 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 53 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 54 | 20 | 20 | 20 | 1 | 1 | 19 | 0 | 0 | 0 |
| 55 | 20 | 20 | 20 | 16 | 16 | 4 | 0 | 0 | 0 |
| 56 | 20 | 20 | 20 | 3 | 3 | 17 | 0 | 0 | 0 |
| 57 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 58 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 59 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 60 | 20 | 20 | 20 | 1 | 1 | 19 | 0 | 0 | 0 |
| 61 | 20 | 20 | 20 | 16 | 15 | 4 | 0 | 1 | 0 |
| 62 | 20 | 20 | 20 | 3 | 3 | 16 | 1 | 0 | 0 |
| 63 | 20 | 20 | 20 | 0 | 0 | 19 | 1 | 0 | 0 |
| 64 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 65 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 66 | 20 | 20 | 20 | 1 | 1 | 19 | 0 | 0 | 0 |
| 67 | 20 | 20 | 20 | 16 | 16 | 4 | 0 | 0 | 0 |
| 68 | 20 | 20 | 20 | 3 | 3 | 17 | 0 | 0 | 0 |
| 69 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 70 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 71 | 20 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| 72 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 73 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 74 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 75 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 76 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 77 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 78 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 79 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 80 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 81 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 82 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 83 | 20 | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| 84 | 20 | 20 | 20 | 7 | 7 | 13 | 0 | 0 | 0 |
| 85 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 86 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 87 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 88 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 89 | 20 | 20 | 20 | 13 | 13 | 7 | 0 | 0 | 0 |
| 90 | 20 | 20 | 20 | 7 | 7 | 13 | 0 | 0 | 0 |
| 91 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 92 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 93 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 94 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 95 | 20 | 20 | 20 | 13 | 11 | 7 | 0 | 2 | 0 |
| 96 | 20 | 20 | 20 | 7 | 7 | 11 | 2 | 0 | 0 |
| 97 | 20 | 20 | 20 | 0 | 0 | 18 | 2 | 0 | 0 |
| 98 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| 99 | 20 | 20 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |

| Region | Mean CPU actions/cycle | 0.5.4 expected actions/cycle |
|---|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 10.12 | 5.11 |
| Bosque de Âmbar (`bosque-ambar`) | 10.12 | 5.21 |
| Costa das Brumas (`costa-brumas`) | 10.14 | 5.11 |
| Terras de Cinza (`terras-cinza`) | 10.12 | 5.01 |
| Picos do Norte (`picos-norte`) | 10.13 | 5.11 |

| Região | Campanhas sem portal | Portais/campanha mediana (p90) | Intervalo portal mediano (p90) | Janelas pressão | Ciclos piso 20 | Ameaça 100 | Ações CPU/ciclo (p50/p90/máx.) | Seq. piso (média/máx.) | Seq. ameaça ≥85 (média/máx.) | Seq. vulnerável (média/máx.) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 12 | 0 (2) | 47 (69) | 21.5 | 14.25 | 0.0 | 10/11/12 | 10.15/29 | 11.45/29 | 10.55/29 |
| Bosque de Âmbar (`bosque-ambar`) | 12 | 0 (2) | 28 (35) | 17.0 | 10.75 | 0.0 | 10/11/12 | 9.05/28 | 11.3/29 | 9.5/29 |
| Costa das Brumas (`costa-brumas`) | 14 | 0 (2) | 28 (72) | 13.5 | 8.7 | 0.0 | 10/11/12 | 7.0/28 | 8.55/29 | 7.35/29 |
| Terras de Cinza (`terras-cinza`) | 14 | 0 (2) | 28 (38) | 12.0 | 7.35 | 0.0 | 10/11/12 | 6.55/28 | 8.45/29 | 6.85/29 |
| Picos do Norte (`picos-norte`) | 8 | 1 (3) | 34 (70) | 36.0 | 24.55 | 0.0 | 10/11/12 | 16.2/29 | 17.3/29 | 16.7/29 |

| Seed | Portal(s) | Rebelião(ões) | 1º portal | 1ª rebelião | Ações CPU/ciclo | Sucesso CPU | Seg. final min–max | Ameaça final min–max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026110301 | 5 | 0 | 4 | — | 50.6 | 71.8% | 20.0–100.0 | 0.0–96.36 |
| 2026110302 | 5 | 1 | 9 | 95 | 50.63 | 73.4% | 20.0–100.0 | 0.0–95.06 |
| 2026110303 | 3 | 0 | 13 | — | 50.54 | 73.3% | 20.0–100.0 | 0.0–95.28 |
| 2026110304 | 4 | 1 | 5 | 19 | 50.69 | 72.9% | 20.0–100.0 | 0.0–95.24 |
| 2026110305 | 3 | 0 | 9 | — | 50.72 | 73.1% | 20.0–100.0 | 0.0–96.45 |
| 2026110306 | 4 | 0 | 5 | — | 50.64 | 74.2% | 20.0–100.0 | 0.0–95.78 |
| 2026110307 | 4 | 0 | 21 | — | 50.6 | 73.1% | 20.0–100.0 | 0.0–96.49 |
| 2026110308 | 5 | 0 | 7 | — | 50.38 | 72.6% | 20.0–100.0 | 0.0–95.89 |
| 2026110309 | 4 | 0 | 14 | — | 50.62 | 72.6% | 20.0–100.0 | 0.0–95.52 |
| 2026110310 | 4 | 1 | 11 | 95 | 50.56 | 72.5% | 20.0–100.0 | 0.0–94.71 |
| 2026110311 | 4 | 0 | 5 | — | 50.62 | 73.2% | 20.0–100.0 | 0.0–95.91 |
| 2026110312 | 3 | 0 | 15 | — | 50.6 | 72.7% | 20.0–100.0 | 0.0–95.61 |
| 2026110313 | 6 | 0 | 6 | — | 50.71 | 73.2% | 20.0–100.0 | 0.0–96.33 |
| 2026110314 | 5 | 0 | 10 | — | 50.77 | 72.5% | 20.0–100.0 | 0.0–96.25 |
| 2026110315 | 3 | 0 | 7 | — | 50.6 | 74.5% | 20.0–100.0 | 0.0–95.15 |
| 2026110316 | 4 | 2 | 9 | 13 | 50.71 | 73.5% | 20.0–100.0 | 0.0–96.55 |
| 2026110317 | 6 | 0 | 5 | — | 50.66 | 73.6% | 20.0–100.0 | 0.0–96.21 |
| 2026110318 | 5 | 0 | 7 | — | 50.63 | 72.9% | 20.0–100.0 | 0.0–96.51 |
| 2026110319 | 4 | 1 | 7 | 31 | 50.51 | 71.7% | 20.0–100.0 | 0.0–96.22 |
| 2026110320 | 4 | 0 | 7 | — | 50.68 | 73.6% | 20.0–100.0 | 0.0–96.47 |

Each 19-cycle pressure window targets one region; off-window threat and security recovery limits overlapping crises. The cooldown permits at most one hidden regional rebellion roll per eligible cycle. CPU action scheduling continues in all five regions.
