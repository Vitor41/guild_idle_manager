# Economia Stage 5 — perfil casual, 365d, N=5

Cinco seeds completos com serviços reais em SQLite descartável e política `roster_first`. Este arquivo agrega as trajetórias válidas; a tabela abaixo valida cada seed separadamente.

| Seed | Dias | Encerramento | Segundos | Resíduo diário somado | Rejeições de serviço |
|---:|---:|---|---:|---:|---:|
| 2026210000 | 365 | full_horizon | 666.0 | 0 | 0 |
| 2026210001 | 365 | full_horizon | 849.7 | 0 | 0 |
| 2026210002 | 365 | full_horizon | 1051.1 | 0 | 0 |
| 2026210003 | 365 | full_horizon | 484.1 | 0 | 0 |
| 2026210004 | 365 | full_horizon | 513.0 | 0 | 0 |

**Ouro:** passivo 573140; missões 2441685; masmorras 50670; Market 233978; compras 31540; salvage 75150; crafting 400; delta 3192383; resíduo agregado 0. O agregador também exige resíduo zero em cada dia de cada seed.

## Rejeições de serviços opcionais

| Serviço | Motivo | Contagem |
|---|---|---:|
| — | Nenhuma rejeição registrada | 0 |

## Seeds substituídos

- Seed 2026210003: antes 359 dias / `wall_budget` / resíduo 0; reexecutada até D365, resíduo 0 (evidência stage5_service_economy_replacement_casual_seeds_3_4_2026-10-30.json).
- Seed 2026210004: antes 344 dias / `wall_budget` / resíduo 0; reexecutada até D365, resíduo 0 (evidência stage5_service_economy_replacement_casual_seeds_3_4_2026-10-30.json).

As rejeições ficam associadas à semente, serviço e motivo literal em `service_rejections` no JSON. N=5 é uma amostra exploratória; não sustenta alegação de P95 ou estabilidade global.

Os JSONs por jornada e ledgers CSV permanecem localmente para reprodução e foram excluídos deste commit. O agregado dos cinco perfis é [stage5_service_economy_365d_n5_2026-10-30.md](stage5_service_economy_365d_n5_2026-10-30.md).
