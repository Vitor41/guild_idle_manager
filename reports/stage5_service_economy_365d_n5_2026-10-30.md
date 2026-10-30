# Economia Stage 5 por serviços reais — horizonte 365d, N=5 por perfil

Cinco seeds independentes por perfil; uma política `roster_first`; execução até 365 dias com serviços reais em campanhas SQLite temporárias. Saldo final, loot, compras, salvamento, vendas, conquistas, eventos e sinks entram quando ocorrem.

| Perfil | N | Guilda 50 | Alvos planejados completos | Guilda final | Craft(s) | Masmorras tentadas/vencidas | Entradas portal | Portal criado/fechado | Rebeliões ativadas/oportunidades | Bloqueado→comprado | Bloqueios finais | Maior housing | Regional cycles s (p50; faixa) | Ouro final p50 (IC95% descritivo) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ativo | 5 | 5/5 | 5/5 | 100–100 | 4 | 2162/1736 | 0 | 6441/6439 | 411/21533 | 152 | 0 | 40 | 468.4; 433.9–573.6 | 3404882 (2654849–4018516) |
| casual | 5 | 5/5 | 5/5 | 100–100 | 5 | 193/165 | 0 | 7052/7048 | 471/23262 | 25 | 0 | 10 | 535.5; 375.4–854.3 | 621348 (610911–679664) |
| offline | 5 | 5/5 | 5/5 | 100–100 | 5 | 1638/1346 | 0 | 6413/6405 | 416/22047 | 140 | 0 | 40 | 570.7; 523.5–864.6 | 2499076 (2133341–2805501) |
| produtor | 5 | 5/5 | 5/5 | 100–100 | 0 | 1366/1034 | 0 | 6579/6573 | 441/22159 | 25 | 0 | 15 | 459.5; 433.2–484.8 | 3351229 (3316859–3433781) |
| combate | 5 | 5/5 | 5/5 | 100–100 | 5 | 3002/2194 | 0 | 6470/6464 | 421/22207 | 154 | 0 | 40 | 552.7; 377.2–834.8 | 2043394 (1905136–2288823) |

## Ouro: fontes e drenos registrados

Totais somados nas cinco campanhas do perfil; residual zero reconcilia as alterações de ouro contabilizadas com o delta diário. Valores agregados não significam renda média por dia nem aprovação de faixa econômica.

| Perfil | Passivo offline | Missões/contratos | Masmorras/portais | Market | Compras edifício/contratação | Taxas salvage | Craft | Delta observado | Resíduo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ativo | 1461336 | 14272774 | 1266262 | 558956 | 610640 | 73650 | 320 | 16874718 | 0 |
| casual | 573140 | 2441685 | 50670 | 233978 | 31540 | 75150 | 400 | 3192383 | 0 |
| offline | 1460912 | 10088259 | 792402 | 525659 | 610640 | 73450 | 400 | 12182742 | 0 |
| produtor | 1421800 | 13241507 | 917848 | 1419074 | 68100 | 83100 | 0 | 16849029 | 0 |
| combate | 1453480 | 7190637 | 1948070 | 384635 | 610640 | 72750 | 400 | 10293032 | 0 |

## Reconciliação por seed

Validação seed a seed e dia a dia; a agregação é bloqueada se qualquer valor de resíduo for diferente de zero.

| Perfil | Seed | Dias | Dias com resíduo | Resíduo total |
|---|---:|---:|---:|---:|
| ativo | 2026110000 | 365 | 0 | 0 |
| ativo | 2026110001 | 365 | 0 | 0 |
| ativo | 2026110002 | 365 | 0 | 0 |
| ativo | 2026110003 | 365 | 0 | 0 |
| ativo | 2026110004 | 365 | 0 | 0 |
| casual | 2026210000 | 365 | 0 | 0 |
| casual | 2026210001 | 365 | 0 | 0 |
| casual | 2026210002 | 365 | 0 | 0 |
| casual | 2026210003 | 365 | 0 | 0 |
| casual | 2026210004 | 365 | 0 | 0 |
| offline | 2026310000 | 365 | 0 | 0 |
| offline | 2026310001 | 365 | 0 | 0 |
| offline | 2026310002 | 365 | 0 | 0 |
| offline | 2026310003 | 365 | 0 | 0 |
| offline | 2026310004 | 365 | 0 | 0 |
| produtor | 2026410000 | 365 | 0 | 0 |
| produtor | 2026410001 | 365 | 0 | 0 |
| produtor | 2026410002 | 365 | 0 | 0 |
| produtor | 2026410003 | 365 | 0 | 0 |
| produtor | 2026410004 | 365 | 0 | 0 |
| combate | 2026510000 | 365 | 0 | 0 |
| combate | 2026510001 | 365 | 0 | 0 |
| combate | 2026510002 | 365 | 0 | 0 |
| combate | 2026510003 | 365 | 0 | 0 |
| combate | 2026510004 | 365 | 0 | 0 |

## Recusas e rejeições opcionais

A contagem inclui o motivo literal e a seed. Falhas do serviço são isoladas em savepoint; pré-checks atualizados podem bloquear uma ação antes da chamada. O agregador exige resíduo diário zero em cada uma das 25 trajetórias.

| Perfil | Registros | Motivos (etapa: mensagem × contagem) |
|---|---:|---|
| ativo | 2 | building_upgrade_precheck: Orçamento atualizado insuficiente após redirecionamento da contratação. × 2 |
| casual | 0 | — |
| offline | 0 | — |
| produtor | 0 | — |
| combate | 0 | — |

## Entrada natural em portais

O runner registra gates do snapshot por portal ativo que foi avaliado; isso explica ausência de entrada. A bateria financiada separada testa sucesso/falha e claim idempotente sem inferir acessibilidade fresh-save.

| Perfil | Eventos diagnosticados | Elegíveis | Bloqueados e motivo mais frequente | Entradas reais |
|---|---:|---:|---|---:|
| ativo | 205 | 0 | 205; insufficient_mercenary_levels | 0 |
| casual | 304 | 0 | 304; insufficient_mercenary_levels | 0 |
| offline | 195 | 0 | 195; insufficient_mercenary_levels | 0 |
| produtor | 290 | 0 | 290; insufficient_mercenary_levels | 0 |
| combate | 262 | 0 | 262; insufficient_mercenary_levels | 0 |

## Exemplo bloqueado e recuperado

Na primeira ocorrência observada, **housing_2** no perfil ativo, seed 2026110004, bloqueou no dia 1 por falta de 114 ouro, guilda 1 níveis abaixo do requisito e materiais `{'wood': 40, 'ore': 0, 'crystals': 0}`. A mesma melhoria foi comprada no dia 8. Esta é recuperação observada dentro da política, não prova de que todos os bloqueios do jogo sejam temporários.

## Alojamento nível 100 e as 20 vagas

Housing max alcançado nas cinco jornadas de cada perfil: ativo: nível 40; casual: nível 10; offline: nível 40; produtor: nível 15; combate: nível 40. Se nenhum chegar a 100, as 20 vagas permanecem conteúdo tardio; a rota financiada via 50 chamadas do serviço está demonstrada separadamente.

N=5 não sustenta uma estimativa de P95; por isso este relatório não apresenta P95. O IC da mediana de ouro e os intervalos Wilson são descrições exploratórias da amostra. Os cinco arquivos individuais preservam checkpoints e evidência por perfil; o CSV adjacente reúne todos os ledgers diários.

Nenhum save real foi aberto. Veja também [participação real em eventos](stage5_event_participation_runtime_2026-10-30.md), [loot regional de chefes](stage5_regional_boss_loot_runtime_2026-10-30.md), [arbitragem por serviços reais](stage5_arbitrage_service_loops_2026-10-30.md), [rota financiada do Alojamento](stage5_buildings_51_100_2026-10-30.md) e [orçamento regional de catch-up](stage5_catchup_operational_budget_2026-10-30.md).
