# Jornadas fresh-save com serviços reais — Stage 5

Pilot=True · N=5/célula · 1 perfis × 1 políticas · horizonte=365 dias · teto=1200.0s/jornada · reserva fixa de material=30 unidades/família · cota L1=25, +5 nos níveis 5, 10, 15... · política de crafting=first_surplus_equipment_once · tempo=3789.13s · setup SQLite=2.12s · seed de conteúdo=7.88s.

| Perfil/caminho | Nível 50 | Alvos planejados completos | Falhas de missão | Dungeon tentadas/vencidas | Ouro final p50 (IC95% bootstrap; não estimável em N<2) | Primeiro equipamento | Dungeon | Portal criado | Rebelião ativada | Upgrade-alvo ainda bloqueado no horizonte |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| produtor/roster_first | 5/5 (100.0%; 56.55–100%) | 5/5 (100.0%; 56.55–100%) | 3660 | 1366/1034 | 3351229.0 (3316859.0–3433781.0; n=5) | 1.0 (1.0–2.0; n=5) | 43.0 (30.0–47.0; n=5) | 43.0 (40.0–46.0; n=5) | 65.0 (52.0–68.0; n=5) | 0/5 (0.0%; 0–43.45%) |

## Ledger, capacidade, marcos e eventos por célula

O ledger diário completo está no CSV; residual zero indica que as fontes/drenos contabilizados reconciliam o delta observado de ouro.

| Perfil/caminho | D10/D25/D50 da guilda | Fontes de ouro: offline/missões/masmorra/Market | Drenos: compras/salvage/crafting | Delta/resíduo | Pico/capacidade | Overflow M/D/G/S | Recuperações/bloqueios finais | Portal: dia/criados/encerrados* | Rebelião: dia/ativações/oportunidades | Craft: feitos/política |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| produtor/roster_first | 13/37/69 | 1421800/13241507/917848/1419074 | 68100/83100/0 | 16849029/0 | 2490/2490 | 2638/501/0/239 | 5/0 | D43/1286/1284 | D66/91/4394 | 0/first_surplus_equipment_once |

*Portal encerrado inclui estados resolvidos ou expirados. Portais ativos da região natal são iniciados e resgatados pelo jogador via serviços reais se estiverem disponíveis durante uma janela online e a equipe cumprir o snapshot; portais não observados continuam ausentes. Rebeliões têm oportunidades naturais e resultados de CPU, mas esta política não aceita convites nem vincula atividade do jogador. A chance aprovada de rebelião é 2% por Vigília elegível e o prazo do portal avança durante catch-up offline. Venda de materiais segue cota L1=25, +5 em cada marco de cinco níveis; sensibilidade está em relatório separado.

## Limites e definições

- Fresh campaign rows and all outputs live in a disposable SQLite file; real user saves are never opened.
- Guild and mercenary levels advance only through runtime service rewards; the journey never synchronizes mercenary level to guild level or fabricates resources.
- Home regional boards are finite and each offer is reserved/completed at most once. During fresh-save bootstrap without an accessible regional offer, active catalog templates use mission_service directly; they are not regional-board offers.
- Regional world advances through four real six-hour boundaries per day. Starts occur only in defined online windows; offline profile uses 4h before an 8h absence and 4h after return, while event timers continue during unattended cycles. First-event timing is measured to the day.
- Naturally active home-region portals are entered and claimed through start_dungeon, attach_event_activity and claim_dungeon_loot during an online window when the available party meets the snapshot requirements; portal equipment loot and failure are recorded. Other regional opportunities/closures are observed. Rebellion participation remains outside this player policy. Portal counts combine resolved and expired states; they are not player victories. The accepted rules remain 2% rebellion chance per eligible Vigil and a portal deadline that continues during offline catch-up.
- Each team has a separate per-window budget and uses a disjoint roster slice when enough mercenaries exist. Claims return mercenaries before their next assignment; no team shares a busy mercenary.
- No new sink or price is added. Salvage is attempted only with spare gold above 75; the fixed material reserve and optional one-time crafting policy are explicit simulator choices, not game rules.
- Market sales reserve 30 units per material family plus the full material cost of the current planned upgrade for wood/ore.
- Gathering uses the configured online windows and the persistent-stamina offline credit for each day, advancing real gathering_service checkpoints with max_seconds. It does not accrue 24 hours of gathering merely because the campaign clock advanced by one day.
- When a milestone changes the required material, the synthetic worker is released and reassigned via gathering_service.release_worker/assign_worker. Market sales protect 30 units per material family plus the full material cost of the current planned upgrade for wood/ore. This is an explicit recovery policy, not a game rule.
- Crafting policy is first_surplus_equipment_once. When enabled, the runner selects at most one affordable rotating equipment recipe using only material stock above the protected reserve, keeps the crafted item out of automatic salvage, and records actual gold/material costs. This is an explicit journey choice, not a new game rule.
- Material sales use the live service's rolling 24h throughput allowance: base=25 at Market 1, increasing by 5 units at each five-level milestone; it applies to all material sources and does not cap equipment sales.
- Daily JSON checkpoints preserve ledger, milestone, roster-level and event/action counts during a run, but are evidence checkpoints rather than a resumable SQLite snapshot. Each journey has max_days and max_wall_seconds budgets. N=1 per profile/path cannot support rare-event or stable-rate claims.
- A horizon blocker is the next planned target still pending at the end whose current gold, level, or material requirements are unmet. Historical blocked snapshots without a same-target retry are reported separately; neither metric proves a permanent softlock. Finite policy journeys do not establish whole-game hard-softlock absence or economic stability.

## Reprodução

```powershell
.venv-desktop\Scripts\python.exe scripts\balance\simulate_stage5_service_journeys.py --runs-per-cell 5 --seed-start 2026110000 --max-days 365 --max-wall-seconds 1200.0 --market-reserve-base 30 --craft-policy first_surplus_equipment_once --output-stem stage5_service_economy_365d_n5_produtor_2026-10-30 --profile produtor --path roster_first
```
