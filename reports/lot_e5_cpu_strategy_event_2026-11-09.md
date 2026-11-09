# Regional CPU event balance — 20 campaigns

Deterministic SQLite campaigns; 100 six-hour cycles each; player takes no actions. Events, timers, CPU plans, snapshots and region state use the live services.
The funnel aligns pressure and threshold state from snapshot N−1 to the rebellion check when Vigília N opens; global-lock cycles are inferred from the active event deadline and the preceding snapshot.

- Campaigns with at least one portal: **20/20**; without portal: **0**; opened portals: **122**; first portal cycles: `[8, 5, 10, 6, 13, 5, 12, 7, 8, 7, 9, 12, 6, 6, 18, 8, 13, 14, 8, 5]`.
- Campaigns with at least one rebellion: **17/20**; opened rebellions: **23**; first rebellion cycles: `[31, 71, 15, 56, 11, 72, 37, 77, 71, 69, 32, 12, 69, 55, 72, 90, 31]`; mean selected rolls: **48.9**; mean cycles with a vulnerable region: **48.9**.
- Maximum simultaneous active global rebellions: **1**.
- Mean CPU success rate: **52.3%**.
- CPU portal entries: **142** (87 successes, 55 failures).
- Net CPU XP / gold over the horizon: **25,944,801 XP / 430,091 gold**.
- Mean CPU actions per global Vigília: **50.8** with throughput set by eligible offers, available mercenaries, activity durations, and 1h player priority.
- CPU actions per Vigília: guilda da região natal **10.17**; nas outras quatro regiões, juntas, **40.63**.
- Minimum regional Vigílias with at least one CPU action: **100/100**.
- Final security range across all regions/campaigns: **43.92–85.44**; threat range: **14.56–97.02**.
- Concurrent regional pressure per cycle (p50/p90/max regions): security_at_floor: 0/1/1; threat_at_least_85: 1/1/2; joint_rebellion_vulnerability: 1/1/1.

- Rebellion funnel across 20×100 Vigílias: 1980 pressure-target region-cycles; 1016 eligible region-cycles in 1016 campaign-cycles; 978 selected rolls × 2% = 19.56 expected openings; 23 observed, 955 RNG failures.
- Eligible region-cycles withheld by regional cooldown: 0; by one-region-per-cycle selection cap: 0; by active global event limit: 38 across 38 campaign-cycles; unclassified: 0.

| Região | Ciclos-alvo | Região-ciclos elegíveis | Bloqueio cooldown | Bloqueio limite por ciclo | Rolagens | Rebeliões | Sem atribuição |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 411 | 220 | 0 | 0 | 208 | 7 | 0 |
| Bosque de Âmbar (`bosque-ambar`) | 408 | 202 | 0 | 0 | 196 | 4 | 0 |
| Costa das Brumas (`costa-brumas`) | 240 | 118 | 0 | 0 | 115 | 2 | 0 |
| Terras de Cinza (`terras-cinza`) | 267 | 126 | 0 | 0 | 119 | 5 | 0 |
| Picos do Norte (`picos-norte`) | 654 | 350 | 0 | 0 | 340 | 5 | 0 |

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
| 8 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 9 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 10 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 11 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 12 | 20 | 20 | 20 | 19 | 18 | 0 | 1 | 1 | 0 |
| 13 | 20 | 20 | 20 | 18 | 18 | 0 | 2 | 0 | 0 |
| 14 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 15 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 16 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 17 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 18 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 19 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 20 | 20 | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| 21 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 22 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 23 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 24 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 25 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 26 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 27 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 28 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 29 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 30 | 20 | 18 | 18 | 18 | 18 | 0 | 0 | 0 | 0 |
| 31 | 20 | 20 | 20 | 20 | 18 | 0 | 0 | 2 | 0 |
| 32 | 20 | 20 | 20 | 18 | 17 | 0 | 2 | 1 | 0 |
| 33 | 20 | 20 | 20 | 17 | 17 | 0 | 3 | 0 | 0 |
| 34 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 35 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 36 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 37 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 38 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 39 | 20 | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| 40 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 41 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 42 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 43 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 44 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 45 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 46 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 47 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 48 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 49 | 20 | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| 50 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 51 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 52 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 53 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 54 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 55 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 56 | 20 | 20 | 20 | 19 | 18 | 0 | 1 | 1 | 0 |
| 57 | 20 | 20 | 20 | 18 | 18 | 0 | 2 | 0 | 0 |
| 58 | 20 | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| 59 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 60 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 61 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 62 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 63 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 64 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 65 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 66 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 67 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 68 | 20 | 12 | 12 | 12 | 12 | 0 | 0 | 0 | 0 |
| 69 | 20 | 20 | 20 | 20 | 18 | 0 | 0 | 2 | 0 |
| 70 | 20 | 20 | 20 | 18 | 17 | 0 | 2 | 1 | 0 |
| 71 | 20 | 20 | 20 | 17 | 15 | 0 | 3 | 2 | 0 |
| 72 | 20 | 20 | 20 | 17 | 15 | 0 | 3 | 2 | 0 |
| 73 | 20 | 20 | 20 | 16 | 16 | 0 | 4 | 0 | 0 |
| 74 | 20 | 20 | 20 | 18 | 18 | 0 | 2 | 0 | 0 |
| 75 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 76 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 77 | 20 | 14 | 14 | 14 | 12 | 0 | 0 | 2 | 0 |
| 78 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 79 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 80 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 81 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 82 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 83 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 84 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 85 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 86 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 87 | 20 | 14 | 14 | 14 | 14 | 0 | 0 | 0 | 0 |
| 88 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 89 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 90 | 20 | 20 | 20 | 20 | 17 | 0 | 0 | 3 | 0 |
| 91 | 20 | 20 | 20 | 17 | 17 | 0 | 3 | 0 | 0 |
| 92 | 20 | 20 | 20 | 17 | 17 | 0 | 3 | 0 | 0 |
| 93 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 94 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 95 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 96 | 20 | 10 | 10 | 10 | 9 | 0 | 0 | 1 | 0 |
| 97 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 98 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 99 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

| Region | Mean CPU actions/cycle | 0.5.4 expected actions/cycle |
|---|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 10.16 | 5.11 |
| Bosque de Âmbar (`bosque-ambar`) | 10.16 | 5.21 |
| Costa das Brumas (`costa-brumas`) | 10.16 | 5.11 |
| Terras de Cinza (`terras-cinza`) | 10.17 | 5.01 |
| Picos do Norte (`picos-norte`) | 10.16 | 5.11 |

| Região | Campanhas sem portal | Portais/campanha mediana (p90) | Intervalo portal mediano (p90) | Janelas pressão | Ciclos piso 20 | Ameaça 100 | Ações CPU/ciclo (p50/p90/máx.) | Seq. piso (média/máx.) | Seq. ameaça ≥85 (média/máx.) | Seq. vulnerável (média/máx.) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 12 | 0 (3) | 31 (38) | 20.7 | 9.5 | 0.25 | 10/11/13 | 4.45/13 | 7.85/20 | 4.9/14 |
| Bosque de Âmbar (`bosque-ambar`) | 11 | 0 (3) | 29 (43) | 20.75 | 8.35 | 0.0 | 10/11/13 | 4.1/13 | 8.85/20 | 4.85/14 |
| Costa das Brumas (`costa-brumas`) | 15 | 0 (3) | 30 (41) | 12.15 | 5.1 | 0.0 | 10/11/13 | 2.5/13 | 4.9/20 | 2.75/14 |
| Terras de Cinza (`terras-cinza`) | 14 | 0 (3) | 28 (38) | 13.6 | 5.4 | 0.0 | 10/11/13 | 2.65/13 | 5.9/20 | 3.15/14 |
| Picos do Norte (`picos-norte`) | 8 | 3 (3) | 31 (38) | 32.8 | 15.45 | 0.15 | 10/11/13 | 7.3/13 | 11.6/20 | 7.65/14 |

| Seed | Portal(s) | Rebelião(ões) | 1º portal | 1ª rebelião | Ações CPU/ciclo | Sucesso CPU | Seg. final min–max | Ameaça final min–max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026110301 | 6 | 0 | 8 | — | 50.77 | 51.3% | 45.1–82.48 | 22.52–92.12 |
| 2026110302 | 7 | 2 | 5 | 31 | 50.81 | 52.2% | 43.92–80.9 | 19.18–92.92 |
| 2026110303 | 6 | 1 | 10 | 71 | 50.89 | 52.2% | 44.24–80.24 | 19.76–96.52 |
| 2026110304 | 6 | 2 | 6 | 15 | 50.98 | 52.5% | 44.06–81.42 | 20.28–93.89 |
| 2026110305 | 7 | 1 | 13 | 56 | 50.84 | 52.3% | 44.34–85.44 | 14.56–95.67 |
| 2026110306 | 7 | 0 | 5 | — | 50.82 | 51.5% | 44.0–82.74 | 17.26–95.36 |
| 2026110307 | 6 | 3 | 12 | 11 | 50.83 | 52.1% | 45.14–82.9 | 17.1–91.19 |
| 2026110308 | 6 | 1 | 7 | 72 | 50.73 | 52.9% | 45.4–82.46 | 17.54–91.92 |
| 2026110309 | 7 | 1 | 8 | 37 | 50.83 | 52.8% | 45.2–80.22 | 19.78–95.2 |
| 2026110310 | 5 | 1 | 7 | 77 | 50.91 | 53.5% | 44.16–81.26 | 18.74–92.97 |
| 2026110311 | 6 | 1 | 9 | 71 | 50.66 | 52.0% | 44.3–81.1 | 18.9–97.02 |
| 2026110312 | 6 | 2 | 12 | 69 | 50.59 | 52.1% | 44.22–79.68 | 20.32–95.66 |
| 2026110313 | 6 | 1 | 6 | 32 | 50.72 | 51.7% | 43.96–84.4 | 15.6–92.47 |
| 2026110314 | 6 | 1 | 6 | 12 | 50.73 | 52.4% | 44.82–83.22 | 16.78–96.48 |
| 2026110315 | 5 | 2 | 18 | 69 | 50.85 | 52.8% | 44.5–83.8 | 16.2–93.16 |
| 2026110316 | 5 | 1 | 8 | 55 | 50.89 | 51.9% | 44.46–82.1 | 17.9–95.81 |
| 2026110317 | 6 | 0 | 13 | — | 50.8 | 52.8% | 43.94–82.04 | 17.96–92.1 |
| 2026110318 | 6 | 1 | 14 | 72 | 50.6 | 51.5% | 44.36–79.22 | 20.78–91.33 |
| 2026110319 | 7 | 1 | 8 | 90 | 50.89 | 52.5% | 44.84–85.0 | 15.0–93.3 |
| 2026110320 | 6 | 1 | 5 | 31 | 50.87 | 53.4% | 44.26–83.46 | 16.54–96.53 |

Each 19-cycle pressure window targets one region; off-window threat and security recovery limits overlapping crises. Rebellion rolls at 2% on every eligible cycle, selecting at most one region per cycle and allowing at most one active global event. CPU action scheduling continues in all five regions.

Per-seed outcomes, including portal entries and XP/gold totals: [CSV](lot_e5_cpu_strategy_event_2026-11-09.csv).
