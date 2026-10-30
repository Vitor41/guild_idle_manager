# Economia Stage 5 — perfil combate, 365d, N=5

Cinco seeds completos com serviços reais em SQLite descartável e política `roster_first`. Este arquivo agrega as trajetórias válidas; a tabela abaixo valida cada seed separadamente.

| Seed | Dias | Encerramento | Segundos | Resíduo diário somado | Rejeições de serviço |
|---:|---:|---|---:|---:|---:|
| 2026510000 | 365 | full_horizon | 765.3 | 0 | 0 |
| 2026510001 | 365 | full_horizon | 948.7 | 0 | 0 |
| 2026510002 | 365 | full_horizon | 1137.9 | 0 | 0 |
| 2026510003 | 365 | full_horizon | 601.5 | 0 | 0 |
| 2026510004 | 365 | full_horizon | 599.2 | 0 | 0 |

**Ouro:** passivo 1453480; missões 7190637; masmorras 1948070; Market 384635; compras 610640; salvage 72750; crafting 400; delta 10293032; resíduo agregado 0. O agregador também exige resíduo zero em cada dia de cada seed.

## Rejeições de serviços opcionais

| Serviço | Motivo | Contagem |
|---|---|---:|
| — | Nenhuma rejeição registrada | 0 |

## Seeds substituídos

- Seed 2026510003: antes 340 dias / `wall_budget` / resíduo 0; reexecutada até D365, resíduo 0 (evidência stage5_service_economy_replacement_combate_seeds_3_4_2026-10-30.json).
- Seed 2026510004: antes 343 dias / `wall_budget` / resíduo 0; reexecutada até D365, resíduo 0 (evidência stage5_service_economy_replacement_combate_seeds_3_4_2026-10-30.json).

As rejeições ficam associadas à semente, serviço e motivo literal em `service_rejections` no JSON. N=5 é uma amostra exploratória; não sustenta alegação de P95 ou estabilidade global.

Os JSONs por jornada e ledgers CSV permanecem localmente para reprodução e foram excluídos deste commit. O agregado dos cinco perfis é [stage5_service_economy_365d_n5_2026-10-30.md](stage5_service_economy_365d_n5_2026-10-30.md).
