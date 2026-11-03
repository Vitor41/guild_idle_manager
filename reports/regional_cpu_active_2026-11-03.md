# Simulação CPU regional ativa — 2026-11-03

Uma campanha determinística em SQLite temporário; 100 Vigílias de 6h; sem ações do jogador. Catch-up e isolamento da campanha foram verificados pelo teste reproduzível indicado abaixo.

Reproduzir: `APP_MODE=desktop .venv-desktop\Scripts\python.exe -m unittest tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_seeded_cpu_simulation_100_cycles_and_campaign_isolation`.

| Vigílias | Ações CPU resolvidas | Sucessos | Falhas | Taxa de sucesso | Contratações |
|---:|---:|---:|---:|---:|---:|
| 10 | 500 | 394 | 106 | 78.8% | 35 |
| 50 | 2529 | 1866 | 663 | 73.8% | 98 |
| 100 | 5069 | 3653 | 1416 | 72.1% | 145 |

## Perfil no horizonte de 100 Vigílias

| Perfil | Ações | Sucessos | Falhas | Contratações | Elenco médio |
|---|---:|---:|---:|---:|---:|
| medium | 1150 | 839 | 311 | 31 | 7.03 |
| new | 2937 | 2044 | 893 | 84 | 4.55 |
| strong | 982 | 770 | 212 | 30 | 9.15 |

## Regiões no horizonte de 100 Vigílias

| Região | Ações resolvidas | Sucessos | Falhas | Contratações |
|---|---:|---:|---:|---:|
| bosque-ambar | 1016 | 670 | 346 | 30 |
| costa-brumas | 1011 | 759 | 252 | 29 |
| picos-norte | 1013 | 690 | 323 | 28 |
| terras-cinza | 1014 | 786 | 228 | 27 |
| vale-fronteira | 1015 | 748 | 267 | 31 |

## Estado e integridade

- Ações CPU seguem ofertas elegíveis, disponibilidade e duração das equipes, sem teto fixo global, regional ou por perfil.
- Primeira contratação forte: Vigília 2 (índice iniciado em zero).
- Segurança final: 45.92–100.0; ameaça: 0.0–91.1329; influência: 80–100.
- Valores negativos de recursos CPU: 0.
- Os eventos reais desta campanha única não estimam incidência; a matriz de 20 campanhas está no relatório regional de incidência.

`regional_cpu_active_2026-11-03.json` guarda as métricas detalhadas por horizonte, perfil e região, além do estado e ranking finais.
