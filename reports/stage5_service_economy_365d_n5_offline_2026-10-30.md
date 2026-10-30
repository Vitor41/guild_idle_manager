# Economia Stage 5 — perfil offline, 365d, N=5

Cinco seeds completos com serviços reais em SQLite descartável e política `roster_first`. Este arquivo agrega as trajetórias válidas; a tabela abaixo valida cada seed separadamente.

| Seed | Dias | Encerramento | Segundos | Resíduo diário somado | Rejeições de serviço |
|---:|---:|---|---:|---:|---:|
| 2026310000 | 365 | full_horizon | 769.1 | 0 | 0 |
| 2026310001 | 365 | full_horizon | 989.4 | 0 | 0 |
| 2026310002 | 365 | full_horizon | 1173.1 | 0 | 0 |
| 2026310003 | 365 | full_horizon | 719.6 | 0 | 0 |
| 2026310004 | 365 | full_horizon | 779.8 | 0 | 0 |

**Ouro:** passivo 1460912; missões 10088259; masmorras 792402; Market 525659; compras 610640; salvage 73450; crafting 400; delta 12182742; resíduo agregado 0. O agregador também exige resíduo zero em cada dia de cada seed.

## Rejeições de serviços opcionais

| Serviço | Motivo | Contagem |
|---|---|---:|
| — | Nenhuma rejeição registrada | 0 |

## Seeds substituídos

- Seed 2026310003: antes 346 dias / `wall_budget` / resíduo 0; reexecutada até D365, resíduo 0 (evidência stage5_service_economy_replacement_offline_seeds_3_4_2026-10-30.json).
- Seed 2026310004: antes 337 dias / `wall_budget` / resíduo 0; reexecutada até D365, resíduo 0 (evidência stage5_service_economy_replacement_offline_seeds_3_4_2026-10-30.json).

As rejeições ficam associadas à semente, serviço e motivo literal em `service_rejections` no JSON. N=5 é uma amostra exploratória; não sustenta alegação de P95 ou estabilidade global.

Os JSONs por jornada e ledgers CSV permanecem localmente para reprodução e foram excluídos deste commit. O agregado dos cinco perfis é [stage5_service_economy_365d_n5_2026-10-30.md](stage5_service_economy_365d_n5_2026-10-30.md).
