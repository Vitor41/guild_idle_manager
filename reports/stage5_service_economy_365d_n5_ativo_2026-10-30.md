# Economia Stage 5 — perfil ativo, 365d, N=5

Cinco seeds completos com serviços reais em SQLite descartável e política `roster_first`. Este arquivo agrega as trajetórias válidas; a tabela abaixo valida cada seed separadamente.

| Seed | Dias | Encerramento | Segundos | Resíduo diário somado | Rejeições de serviço |
|---:|---:|---|---:|---:|---:|
| 2026110000 | 365 | full_horizon | 661.0 | 0 | 0 |
| 2026110001 | 365 | full_horizon | 707.5 | 0 | 0 |
| 2026110002 | 365 | full_horizon | 855.5 | 0 | 2 |
| 2026110003 | 365 | full_horizon | 849.1 | 0 | 0 |
| 2026110004 | 365 | full_horizon | 890.3 | 0 | 0 |

**Ouro:** passivo 1461336; missões 14272774; masmorras 1266262; Market 558956; compras 610640; salvage 73650; crafting 320; delta 16874718; resíduo agregado 0. O agregador também exige resíduo zero em cada dia de cada seed.

## Recusas e rejeições opcionais

| Etapa | Motivo | Contagem |
|---|---|---:|
| building_upgrade_precheck | Orçamento atualizado insuficiente após redirecionamento da contratação. | 2 |

### Estado das tentativas recusadas

Valores de ouro: disponível / exigido. Materiais são apresentados nessa mesma ordem para a cotação do simulador e para a validação real do serviço. `pré-check; sem chamada` significa que o orçamento atualizado bloqueou a ação antes de invocar o serviço; `serviço chamado` identifica uma recusa retornada pelo próprio serviço.

| Seed | Dia | Tentativa | Camada | Alvo | Ouro pré-checagem | Materiais pré-checagem | Ouro em `can_pay` | Materiais em `can_pay` | Motivo |
|---:|---:|---|---|---|---:|---|---:|---|---|
| 2026110002 | D32 | redirected_target_precheck | pré-check; sem chamada | housing_21 | 1206 / 2650 | wood: 943 disponível / 530 exigido, ore: 172 disponível / 0 exigido, crystals: 29 disponível / 0 exigido | — / — | wood: — disponível / 0 exigido, ore: — disponível / 0 exigido, crystals: — disponível / 0 exigido | Orçamento atualizado insuficiente após redirecionamento da contratação. |
| 2026110002 | D33 | redirected_target_precheck | pré-check; sem chamada | housing_21 | 2283 / 2650 | wood: 948 disponível / 530 exigido, ore: 172 disponível / 0 exigido, crystals: 33 disponível / 0 exigido | — / — | wood: — disponível / 0 exigido, ore: — disponível / 0 exigido, crystals: — disponível / 0 exigido | Orçamento atualizado insuficiente após redirecionamento da contratação. |

## Seeds substituídos

- Seed 2026110002: antes 365 dias / `full_horizon` / resíduo 0; reexecutada até D365, resíduo 0 (evidência stage5_service_economy_ativo_seed_2026110002_reconciled_2026-10-30.json).

O JSON mantém todos os campos de contexto e as entradas literais em `service_rejections`. N=5 é uma amostra exploratória; não sustenta alegação de P95 ou estabilidade global.

Os JSONs por jornada e ledgers CSV permanecem localmente para reprodução e foram excluídos deste commit. O agregado dos cinco perfis é [stage5_service_economy_365d_n5_2026-10-30.md](stage5_service_economy_365d_n5_2026-10-30.md).
