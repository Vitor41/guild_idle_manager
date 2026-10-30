# Validação runtime integrada Stage 5 — evidência parcial

**Data:** 2026-10-29
**Estado:** evidência adicional; Stage 5 segue aberto
**Classificação:** checks de serviços em fixture temporária e auditoria condicional; não é playthrough.

## O que foi executado

`tests.test_stage5_runtime_validation` passou **7/7 em 45,550 s**, usando SQLite em memória e serviços reais:

- missão: início e saque com XP individual real, level-up e descarte de drop quando o inventário está cheio;
- mercado e ferreiro: venda de material com timer e pagamento real; salvage de equipamento com custo, resultado e descarte por capacidade;
- dungeon: início e saque reais, sucesso forçado no fixture e verificação de overflow;
- gathering: profissão correspondente, produção real, inventário cheio, pausa automática e retomada após abrir espaço;
- regional: três ciclos processados pelo serviço e gatilho de portal exercitado com ameaça colocada no limiar.
- cadeia composta adicional: a rotação ativa fabricou equipamento por `craft_recipe`; a instância passou por `start_salvage`/`collect_salvage`; o material resultante passou por `start_material_sale`/`collect_market_sale`. O teste conferiu o saldo após custo de fabricação, taxa de desmontagem e crédito da venda.

Fixture começa com ouro abundante, edifícios necessários já elevados e elenco criado no nível 1. Os resultados de sucesso/tempo são determinísticos por controle de relógio e RNG no teste. A cadeia composta liga crafting→desmontagem→venda, mas não percorre uma rota fresh-save nem encadeia loot de missão/dungeon à venda ou ao salvage.

## Eventos regionais

[Auditoria condicional dos serviços](stage5_runtime_event_services_2026-10-29.md) executou 1.000 números de ciclo (0–999), com cinco regiões mantidas artificialmente em ameaça 85 e segurança 25. A chave `seed_start=2026102900` deriva um UUID estável de campanha; os serviços derivam as rolagens desse UUID, ciclo, região e versão das regras.

| Serviço | Resultado observado | Intervalo Wilson 95% | Alvo |
|---|---:|---:|---:|
| Portal | 746/5.000 = 14,92% | 13,96–15,93% | 15% por região-ciclo neste limiar |
| Candidata de rebelião | 86/4.190 = 2,05% | 1,67–2,53% | 2% por região-ciclo elegível |

Das 86 candidatas, 81 foram ativadas e 5 suprimidas pelo limite global. Uma versão anterior do relatório contava apenas eventos ainda ativos/suprimidos no fim do horizonte e informava erroneamente 6/4.190; a geração corrigida usa flags imutáveis do resumo do serviço, incluindo eventos ativados que expiraram antes da consulta final. JSON e Markdown foram regenerados com as mesmas contagens.

O cenário confirma frequência condicional do serviço. Não estima quando um save novo cruza os limiares, participação ou recompensas. O prazo do portal continua avançando offline, como definido no GDD e confirmado para esta validação; não foi medido o tempo até o primeiro portal em catch-up natural.

## Ligação com o modelo financiado

O relatório financiado [N=20 por perfil/caminho](integrated_funded_stage5_2026-10-29.md) continua responsável pelas projeções 1–50, estoques e escolhas de investimento. Conforme a hipótese de balanceamento aceita pelo usuário, ele projeta o nível do roster junto com o nível da guilda; não representa XP individual. Os testes runtime acima verificam que uma missão concede XP e pode subir um mercenário de nível, mas não convertem a projeção N=20 em uma campanha econômica de serviços integrada.

## Limites e decisões em aberto

- Sem roteiro contínuo fresh-save: não há progressão runtime financiada de nível 1 a 50 com várias políticas e caminhos de gasto.
- Market e salvage foram exercitados separadamente; equipamento criado na fixture foi salvaged, sem cadeia missão/dungeon→equipamento→salvage.
- Dungeon foi executada com gate previamente aberto e resolução controlada; não mede acesso pelo tempo de campanha ou taxa natural de vitória/loot.
- Overflow foi observado em missão, dungeon, salvage e gathering. O descarte está demonstrado para essas transações, mas seu efeito combinado sobre a recuperação de materiais ao longo da campanha continua sem medida.
- A auditoria de eventos mantém limiares fixos e não inclui economia, ações do jogador/CPU, escolhas, participação ou rewards.
- Hard softlock global, economia infinita/estabilidade, UX da build candidata e timing médio de primeiro evento continuam sem prova. Stage 5 não está aceito.

## Reprodução

Na raiz `App GIM`:

```powershell
..\.venv\Scripts\python.exe -m unittest tests.test_stage5_runtime_validation -v
..\.venv\Scripts\python.exe scripts\balance\audit_stage5_runtime_event_services.py --cycles 1000 --seed-start 2026102900
```
