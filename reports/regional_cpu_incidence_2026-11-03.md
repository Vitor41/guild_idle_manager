# Regional CPU event balance — 20 campaigns

Deterministic SQLite campaigns; 100 six-hour cycles each; player takes no actions. Events, timers, CPU plans, snapshots and region state use the live services.

- Campaigns with at least one portal: **20/20**; without portal: **0**; opened portals: **112**; first portal cycles: `[4, 9, 13, 5, 9, 5, 21, 7, 14, 11, 5, 15, 6, 10, 7, 9, 5, 7, 7, 7]`.
- Campaigns with at least one rebellion: **4/20**; opened rebellions: **4**; first rebellion cycles: `[19, 95, 38, 13]`; mean selected rolls: **10.85**; mean cycles with a vulnerable region: **42.85**.
- Maximum simultaneous active global rebellions: **1**.
- Mean CPU success rate: **72.9%**.
- Mean CPU actions per global Vigília: **50.62** with throughput set by eligible offers, available mercenaries, activity durations, and 1h player priority.
- Minimum regional Vigílias with at least one CPU action: **100/100**.
- Final security range across all regions/campaigns: **44.4–100.0**; threat range: **0.0–95.94**.
- Concurrent regional pressure per cycle (p50/p90/max regions): security_at_floor: 0/1/1; threat_at_least_85: 1/1/1; joint_rebellion_vulnerability: 0/1/1.

| Region | Mean CPU actions/cycle | 0.5.4 expected actions/cycle |
|---|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 10.12 | 5.11 |
| Bosque de Âmbar (`bosque-ambar`) | 10.12 | 5.21 |
| Costa das Brumas (`costa-brumas`) | 10.14 | 5.11 |
| Terras de Cinza (`terras-cinza`) | 10.12 | 5.01 |
| Picos do Norte (`picos-norte`) | 10.13 | 5.11 |

| Região | Campanhas sem portal | Portais/campanha mediana (p90) | Intervalo portal mediano (p90) | Janelas pressão | Ciclos piso 20 | Ameaça 100 | Ações CPU/ciclo (p50/p90/máx.) | Seq. piso (média/máx.) | Seq. ameaça ≥85 (média/máx.) | Seq. vulnerável (média/máx.) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 12 | 0 (3) | 34 (41) | 20.7 | 8.1 | 0.0 | 10/11/12 | 3.95/13 | 7.15/18 | 4.3/13 |
| Bosque de Âmbar (`bosque-ambar`) | 11 | 0 (3) | 35 (40) | 20.75 | 7.15 | 0.0 | 10/11/12 | 3.7/12 | 8.05/18 | 4.15/13 |
| Costa das Brumas (`costa-brumas`) | 14 | 0 (3) | 35 (41) | 14.3 | 5.1 | 0.0 | 10/11/12 | 2.55/12 | 5.35/18 | 2.85/13 |
| Terras de Cinza (`terras-cinza`) | 15 | 0 (2) | 39 (53) | 11.45 | 3.65 | 0.0 | 10/11/12 | 1.95/12 | 4.45/18 | 2.25/13 |
| Picos do Norte (`picos-norte`) | 8 | 3 (3) | 34 (40) | 32.8 | 13.95 | 0.0 | 10/11/12 | 6.75/13 | 10.75/18 | 7.25/13 |

| Seed | Portal(s) | Rebelião(ões) | 1º portal | 1ª rebelião | Ações CPU/ciclo | Sucesso CPU | Seg. final min–max | Ameaça final min–max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026110301 | 7 | 0 | 4 | — | 50.6 | 71.5% | 46.14–100.0 | 0.0–91.78 |
| 2026110302 | 5 | 0 | 9 | — | 50.63 | 73.4% | 45.84–100.0 | 0.0–90.15 |
| 2026110303 | 5 | 0 | 13 | — | 50.54 | 73.4% | 45.78–100.0 | 0.0–91.67 |
| 2026110304 | 6 | 1 | 5 | 19 | 50.69 | 72.6% | 46.74–100.0 | 0.0–90.75 |
| 2026110305 | 5 | 0 | 9 | — | 50.72 | 72.8% | 45.92–100.0 | 0.0–92.18 |
| 2026110306 | 5 | 0 | 5 | — | 50.64 | 74.0% | 45.72–100.0 | 0.0–90.71 |
| 2026110307 | 5 | 0 | 21 | — | 50.6 | 72.9% | 45.16–100.0 | 0.0–89.82 |
| 2026110308 | 6 | 0 | 7 | — | 50.38 | 72.7% | 45.6–100.0 | 0.0–90.72 |
| 2026110309 | 6 | 0 | 14 | — | 50.62 | 72.2% | 44.92–100.0 | 0.0–95.94 |
| 2026110310 | 7 | 1 | 11 | 95 | 50.56 | 72.4% | 46.06–100.0 | 0.0–89.36 |
| 2026110311 | 6 | 0 | 5 | — | 50.62 | 73.0% | 46.18–100.0 | 0.0–90.0 |
| 2026110312 | 6 | 0 | 15 | — | 50.6 | 72.3% | 46.3–100.0 | 0.0–89.62 |
| 2026110313 | 6 | 1 | 6 | 38 | 50.71 | 73.3% | 45.28–100.0 | 0.0–89.32 |
| 2026110314 | 5 | 0 | 10 | — | 50.77 | 72.4% | 44.4–100.0 | 0.0–89.53 |
| 2026110315 | 5 | 0 | 7 | — | 50.6 | 74.0% | 45.92–100.0 | 0.0–89.25 |
| 2026110316 | 6 | 1 | 9 | 13 | 50.71 | 73.3% | 46.68–100.0 | 0.0–90.85 |
| 2026110317 | 6 | 0 | 5 | — | 50.66 | 73.1% | 45.84–100.0 | 0.0–91.18 |
| 2026110318 | 5 | 0 | 7 | — | 50.63 | 72.7% | 46.0–100.0 | 0.0–91.68 |
| 2026110319 | 5 | 0 | 7 | — | 50.51 | 71.6% | 46.32–100.0 | 0.0–90.39 |
| 2026110320 | 5 | 0 | 7 | — | 50.68 | 73.6% | 45.16–100.0 | 0.0–89.08 |

Each 19-cycle pressure window targets one region; off-window threat and security recovery limits overlapping crises. The cooldown permits at most one hidden regional rebellion roll per eligible cycle. CPU action scheduling continues in all five regions.
