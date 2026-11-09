# Regional CPU event balance — 20 campaigns

Deterministic SQLite campaigns; 100 six-hour cycles each; player takes no actions. Events, timers, CPU plans, snapshots and region state use the live services.
The funnel aligns pressure and threshold state from snapshot N−1 to the rebellion check when Vigília N opens; global-lock cycles are inferred from the active event deadline and the preceding snapshot.

## CPU strategy gate vs E1+E3 baseline

Paired seeds and a 100-Vigília horizon; XP is campaign resource net, and success excludes portal entries.

| Measure | E1+E3 baseline | Rejected E5 `6d98bc5` | Corrected E5 | Difference vs baseline | Acceptance gate |
|---|---:|---:|---:|---:|---|
| CPU XP net | 30,313,874 | 25,944,801 | 31,652,945 | +4.42% | ±10%: pass |
| Mission success | 72.86% | 52.31% | 65.13% | −7.73 pp | ±10 pp: pass |

The rejected planner started nearly every contract but selected each party by earliest availability before evaluating value. The corrected planner evaluates feasible teams by expected XP per duration, including the existing chance and quarter-XP failure reward, and may wait for a stronger team only when it can still finish before the offer deadline. Offer selection uses expected XP per duration, then success chance and archetype preference; it does not add rank or success bonuses. ML-029's power formula is unchanged; Rank C level 18 still recommends power 144.

Across 10,000 region-cycles, boards generated 100,000 contracts, 30,000 dungeons and 10,000 bosses. CPU guilds started 99,961 contracts, 482 dungeons and 1,045 introductory Rank E bosses. The other 36,012 plan scans had offers remaining but no eligible offer-party match; none were stopped only by cycle duration. Offer supply is sufficient for contract throughput, while high-level dungeon/boss snapshots remain outside current CPU team requirements.

- Campaigns with at least one portal: **20/20**; without portal: **0**; opened portals: **114**; first portal cycles: `[8, 5, 10, 6, 13, 5, 12, 7, 8, 7, 9, 12, 6, 6, 18, 8, 13, 14, 8, 5]`.
- Campaigns with at least one rebellion: **15/20**; opened rebellions: **19**; first rebellion cycles: `[31, 71, 15, 38, 11, 70, 73, 90, 32, 12, 93, 55, 72, 90, 31]`; mean selected rolls: **44.2**; mean cycles with a vulnerable region: **45.95**.
- Maximum simultaneous active global rebellions: **1**.
- Mean CPU success rate: **65.1%**.
- Mission-only CPU success rate (excluding portal entries): **65.1%** over 101,488 started contracts, dungeons, and bosses.
- CPU portal entries: **130** (93 successes, 37 failures).
- Net CPU XP / gold over the horizon: **31,652,945 XP / 429,623 gold**.
- Mean CPU actions per global Vigília: **50.81** with throughput set by eligible offers, available mercenaries, activity durations, and 1h player priority.
- Board coverage: **101,488/140,000** region-board offers started by CPU (72.5%); 38,512 remained unstarted.
- Planner stop reasons: **36,012** plans had board offers but no party-offer pair eligible; **0** reached an already-used board; **0** terminal passes found a party but no selected action could finish inside the cycle.
- CPU actions per Vigília: guilda da região natal **10.17**; nas outras quatro regiões, juntas, **40.64**.
- Minimum regional Vigílias with at least one CPU action: **100/100**.
- Final security range across all regions/campaigns: **44.14–100.0**; threat range: **0.0–95.76**.
- Concurrent regional pressure per cycle (p50/p90/max regions): security_at_floor: 0/1/1; threat_at_least_85: 1/1/1; joint_rebellion_vulnerability: 0/1/1.

## CPU outcomes by Rank and level band

Unstarted offers are counted against the generated regional board. Success chance and XP are measured only for started offers; XP includes all mercenaries in the party.

| Tipo | Rank | Faixa de nível | Ofertas | Iniciadas | Não iniciadas | Sucesso | Chance média | XP/início | Duração s | Grupo |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| boss | A | 301-350 | 1688 | 0 | 1688 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| boss | B | 201-250 | 2140 | 0 | 2140 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| boss | C | 131-200 | 2844 | 0 | 2844 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| boss | D | 51-100 | 2079 | 0 | 2079 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| boss | E | 1-20 | 1048 | 1045 | 3 | 86.3% | 85.6% | 3573.8 | 2340 | 4.92 |
| boss | S | 301-350 | 201 | 0 | 201 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| contract | A | 1-20 | 8802 | 8794 | 8 | 47.0% | 46.9% | 348.0 | 647 | 2.28 |
| contract | B | 1-20 | 14799 | 14783 | 16 | 51.6% | 51.3% | 327.0 | 591 | 2.24 |
| contract | C | 1-20 | 23127 | 23115 | 12 | 58.2% | 58.3% | 291.1 | 509 | 2.16 |
| contract | D | 1-20 | 25398 | 25396 | 2 | 68.2% | 68.8% | 252.4 | 419 | 2.08 |
| contract | E | 1-20 | 26647 | 26647 | 0 | 81.7% | 81.5% | 226.0 | 338 | 2.05 |
| contract | S | 1-20 | 1227 | 1226 | 1 | 44.8% | 44.5% | 350.6 | 674 | 2.29 |
| dungeon | A | 1-20 | 6 | 0 | 6 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | A | 101-130 | 108 | 0 | 108 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | A | 131-200 | 321 | 0 | 321 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | A | 201-250 | 421 | 0 | 421 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | A | 21-50 | 16 | 0 | 16 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | A | 251-300 | 538 | 0 | 538 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | A | 301-350 | 907 | 0 | 907 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | A | 51-100 | 100 | 0 | 100 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | B | 1-20 | 41 | 8 | 33 | 37.5% | 65.4% | 715.0 | 1306 | 2.38 |
| dungeon | B | 101-130 | 242 | 0 | 242 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | B | 131-200 | 688 | 0 | 688 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | B | 201-250 | 717 | 0 | 717 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | B | 21-50 | 87 | 0 | 87 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | B | 251-300 | 845 | 0 | 845 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | B | 301-350 | 1351 | 0 | 1351 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | B | 51-100 | 261 | 0 | 261 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | C | 1-20 | 184 | 42 | 142 | 73.8% | 71.8% | 860.7 | 1424 | 2.24 |
| dungeon | C | 101-130 | 563 | 0 | 563 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | C | 131-200 | 1380 | 0 | 1380 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | C | 201-250 | 1108 | 0 | 1108 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | C | 21-50 | 347 | 0 | 347 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | C | 251-300 | 1163 | 0 | 1163 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | C | 301-350 | 1401 | 0 | 1401 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | C | 51-100 | 735 | 0 | 735 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | D | 1-20 | 506 | 131 | 375 | 67.9% | 68.0% | 905.5 | 1436 | 2.37 |
| dungeon | D | 101-130 | 838 | 0 | 838 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | D | 131-200 | 1560 | 0 | 1560 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | D | 201-250 | 1098 | 0 | 1098 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | D | 21-50 | 817 | 0 | 817 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | D | 251-300 | 891 | 0 | 891 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | D | 301-350 | 839 | 0 | 839 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | D | 51-100 | 1280 | 0 | 1280 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | E | 1-20 | 1135 | 301 | 834 | 70.1% | 72.9% | 905.8 | 1398 | 2.37 |
| dungeon | E | 101-130 | 983 | 0 | 983 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | E | 131-200 | 1540 | 0 | 1540 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | E | 201-250 | 711 | 0 | 711 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | E | 21-50 | 1498 | 0 | 1498 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | E | 251-300 | 467 | 0 | 467 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | E | 301-350 | 248 | 0 | 248 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | E | 51-100 | 1785 | 0 | 1785 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | S | 101-130 | 6 | 0 | 6 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | S | 131-200 | 38 | 0 | 38 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | S | 201-250 | 39 | 0 | 39 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | S | 251-300 | 73 | 0 | 73 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | S | 301-350 | 113 | 0 | 113 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |
| dungeon | S | 51-100 | 5 | 0 | 5 | 0.0% | 0.0% | 0.0 | 0 | 0.00 |

- Rebellion funnel across 20×100 Vigílias: 1980 pressure-target region-cycles; 919 eligible region-cycles in 919 campaign-cycles; 884 selected rolls × 2% = 17.68 expected openings; 19 observed, 865 RNG failures.
- Eligible region-cycles withheld by regional cooldown: 0; by one-region-per-cycle selection cap: 0; by active global event limit: 35 across 35 campaign-cycles; unclassified: 0.

| Região | Ciclos-alvo | Região-ciclos elegíveis | Bloqueio cooldown | Bloqueio limite por ciclo | Rolagens | Rebeliões | Sem atribuição |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 411 | 204 | 0 | 0 | 192 | 6 | 0 |
| Bosque de Âmbar (`bosque-ambar`) | 282 | 126 | 0 | 0 | 124 | 1 | 0 |
| Costa das Brumas (`costa-brumas`) | 282 | 122 | 0 | 0 | 119 | 2 | 0 |
| Terras de Cinza (`terras-cinza`) | 309 | 129 | 0 | 0 | 121 | 5 | 0 |
| Picos do Norte (`picos-norte`) | 696 | 338 | 0 | 0 | 328 | 5 | 0 |

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
| 20 | 20 | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 |
| 21 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 22 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 23 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 24 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 25 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 26 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 27 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 28 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 29 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 30 | 20 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| 31 | 20 | 19 | 19 | 19 | 17 | 0 | 0 | 2 | 0 |
| 32 | 20 | 20 | 20 | 18 | 17 | 0 | 2 | 1 | 0 |
| 33 | 20 | 20 | 20 | 17 | 17 | 0 | 3 | 0 | 0 |
| 34 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 35 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 36 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 37 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 38 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 39 | 20 | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 |
| 40 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 41 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 42 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 43 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 44 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 45 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 46 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 47 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 48 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 49 | 20 | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 |
| 50 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 51 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 52 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 53 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 54 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 55 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 56 | 20 | 20 | 20 | 19 | 18 | 0 | 1 | 1 | 0 |
| 57 | 20 | 20 | 20 | 18 | 18 | 0 | 2 | 0 | 0 |
| 58 | 20 | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| 59 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 60 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 61 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 62 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 63 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 64 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 65 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 66 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 67 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 68 | 20 | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 0 |
| 69 | 20 | 19 | 19 | 19 | 19 | 0 | 0 | 0 | 0 |
| 70 | 20 | 20 | 20 | 20 | 18 | 0 | 0 | 2 | 0 |
| 71 | 20 | 20 | 20 | 18 | 17 | 0 | 2 | 1 | 0 |
| 72 | 20 | 20 | 20 | 17 | 16 | 0 | 3 | 1 | 0 |
| 73 | 20 | 20 | 20 | 18 | 16 | 0 | 2 | 2 | 0 |
| 74 | 20 | 20 | 20 | 17 | 17 | 0 | 3 | 0 | 0 |
| 75 | 20 | 20 | 20 | 18 | 18 | 0 | 2 | 0 | 0 |
| 76 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 77 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 78 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 79 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 80 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 81 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 82 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 83 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 84 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 85 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 86 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 87 | 20 | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 0 |
| 88 | 20 | 18 | 18 | 18 | 18 | 0 | 0 | 0 | 0 |
| 89 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 | 0 |
| 90 | 20 | 20 | 20 | 20 | 17 | 0 | 0 | 3 | 0 |
| 91 | 20 | 20 | 20 | 17 | 17 | 0 | 3 | 0 | 0 |
| 92 | 20 | 20 | 20 | 17 | 17 | 0 | 3 | 0 | 0 |
| 93 | 20 | 20 | 20 | 20 | 19 | 0 | 0 | 1 | 0 |
| 94 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 95 | 20 | 20 | 20 | 19 | 19 | 0 | 1 | 0 | 0 |
| 96 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 97 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 98 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 99 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

| Region | Mean CPU actions/cycle | 0.5.4 expected actions/cycle |
|---|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 10.16 | 5.11 |
| Bosque de Âmbar (`bosque-ambar`) | 10.15 | 5.21 |
| Costa das Brumas (`costa-brumas`) | 10.16 | 5.11 |
| Terras de Cinza (`terras-cinza`) | 10.17 | 5.01 |
| Picos do Norte (`picos-norte`) | 10.16 | 5.11 |

| Região | Campanhas sem portal | Portais/campanha mediana (p90) | Intervalo portal mediano (p90) | Janelas pressão | Ciclos piso 20 | Ameaça 100 | Ações CPU/ciclo (p50/p90/máx.) | Seq. piso (média/máx.) | Seq. ameaça ≥85 (média/máx.) | Seq. vulnerável (média/máx.) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vale da Fronteira (`vale-fronteira`) | 12 | 0 (3) | 32 (42) | 20.7 | 9.1 | 0.0 | 10/11/13 | 4.3/13 | 7.45/19 | 4.65/14 |
| Bosque de Âmbar (`bosque-ambar`) | 14 | 0 (3) | 37 (42) | 14.3 | 5.7 | 0.0 | 10/11/13 | 2.8/13 | 5.4/18 | 3.0/13 |
| Costa das Brumas (`costa-brumas`) | 14 | 0 (3) | 33 (42) | 14.3 | 5.5 | 0.0 | 10/11/13 | 2.75/13 | 5.4/18 | 2.95/13 |
| Terras de Cinza (`terras-cinza`) | 13 | 0 (3) | 30 (40) | 15.75 | 5.65 | 0.0 | 10/11/13 | 2.85/13 | 6.3/18 | 3.25/14 |
| Picos do Norte (`picos-norte`) | 7 | 3 (3) | 33 (44) | 34.95 | 15.6 | 0.0 | 10/11/13 | 7.6/13 | 11.7/18 | 7.8/14 |

| Seed | Portal(s) | Rebelião(ões) | 1º portal | 1ª rebelião | Ações CPU/ciclo | Sucesso CPU | Seg. final min–max | Ameaça final min–max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026110301 | 5 | 0 | 8 | — | 50.69 | 64.0% | 45.34–96.46 | 3.54–90.14 |
| 2026110302 | 6 | 1 | 5 | 31 | 50.75 | 65.6% | 44.76–99.3 | 0.7–94.78 |
| 2026110303 | 5 | 1 | 10 | 71 | 50.86 | 64.2% | 44.76–95.86 | 4.14–90.93 |
| 2026110304 | 6 | 2 | 6 | 15 | 50.97 | 66.1% | 45.58–99.94 | 0.06–94.87 |
| 2026110305 | 6 | 2 | 13 | 38 | 50.85 | 65.3% | 45.14–100.0 | 0.0–91.98 |
| 2026110306 | 6 | 0 | 5 | — | 50.84 | 65.0% | 45.12–100.0 | 0.0–93.84 |
| 2026110307 | 5 | 2 | 12 | 11 | 50.86 | 65.2% | 45.66–100.0 | 0.0–92.35 |
| 2026110308 | 6 | 2 | 7 | 70 | 50.75 | 66.0% | 46.28–96.72 | 3.28–91.84 |
| 2026110309 | 5 | 1 | 8 | 73 | 50.81 | 65.7% | 46.36–100.0 | 0.0–91.13 |
| 2026110310 | 5 | 0 | 7 | — | 50.93 | 65.5% | 45.44–98.52 | 1.48–95.76 |
| 2026110311 | 6 | 0 | 9 | — | 50.63 | 64.0% | 45.58–99.66 | 0.34–94.54 |
| 2026110312 | 6 | 1 | 12 | 90 | 50.6 | 64.1% | 45.14–98.42 | 1.58–91.2 |
| 2026110313 | 6 | 1 | 6 | 32 | 50.8 | 64.1% | 45.48–98.68 | 1.32–94.51 |
| 2026110314 | 6 | 1 | 6 | 12 | 50.7 | 67.1% | 45.82–100.0 | 0.0–92.44 |
| 2026110315 | 5 | 1 | 18 | 93 | 50.9 | 65.4% | 45.7–99.46 | 0.54–93.54 |
| 2026110316 | 5 | 1 | 8 | 55 | 50.87 | 64.8% | 45.94–100.0 | 0.0–93.02 |
| 2026110317 | 6 | 0 | 13 | — | 50.81 | 65.5% | 44.14–100.0 | 0.0–93.84 |
| 2026110318 | 6 | 1 | 14 | 72 | 50.71 | 63.9% | 46.2–99.48 | 0.52–92.56 |
| 2026110319 | 7 | 1 | 8 | 90 | 50.91 | 65.1% | 46.12–99.72 | 0.28–94.0 |
| 2026110320 | 6 | 1 | 5 | 31 | 50.94 | 66.2% | 45.94–99.96 | 0.04–91.97 |

Each 19-cycle pressure window targets one region; off-window threat and security recovery limits overlapping crises. Rebellion rolls at 2% on every eligible cycle, selecting at most one region per cycle and allowing at most one active global event. CPU action scheduling continues in all five regions.


Per-seed outcomes: [lot_e5_cpu_strategy_event_2026-11-09.csv](lot_e5_cpu_strategy_event_2026-11-09.csv).
