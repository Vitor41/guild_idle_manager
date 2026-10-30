# Jornadas fresh-save com serviços reais — Stage 5

Pilot=True · N=1/célula · 5 perfis × 2 políticas · horizonte=365 dias · teto=600s/jornada · reserva fixa=30 unidades/família · tempo total=1302.5s (21.7 min) · setup SQLite=2.63s · seed de conteúdo=7.205s.

| Perfil/política | Nível 50 | Alvos planejados | Falhas missão/contrato | Dungeon tentadas/vencidas | Ouro final | Equip. D | Dungeon D | Portal D | Rebelião D | Alvo bloqueado final |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ativo/roster_first | 50/50 · D68 | sim | 61 | 21/15 | 62,806.0 | D1 | D37 | D47 | D65 | 0 |
| ativo/commerce_early | 50/50 · D66 | sim | 63 | 15/10 | 184,815.0 | D1 | D41 | D37 | D52 | 0 |
| casual/roster_first | 50/50 · D127 | sim | 63 | 10/5 | 70,986.0 | D1 | D27 | D52 | D72 | 0 |
| casual/commerce_early | 50/50 · D132 | sim | 46 | 14/11 | 78,148.0 | D1 | D46 | D54 | D77 | 0 |
| offline/roster_first | 50/50 · D76 | sim | 68 | 15/12 | 67,075.0 | D1 | D48 | D33 | D49 | 0 |
| offline/commerce_early | 50/50 · D75 | sim | 55 | 14/11 | 178,036.0 | D1 | D45 | D60 | D70 | 0 |
| produtor/roster_first | 50/50 · D73 | sim | 70 | 18/15 | 656,883.0 | D1 | D19 | D39 | D52 | 0 |
| produtor/commerce_early | 50/50 · D201 | sim | 59 | 12/10 | 1,237,691.0 | D1 | D144 | D61 | D84 | 0 |
| combate/roster_first | 50/50 · D73 | sim | 60 | 21/17 | 70,146.0 | D1 | D34 | D35 | D43 | 0 |
| combate/commerce_early | 50/50 · D69 | sim | 59 | 17/14 | 178,493.0 | D1 | D43 | D50 | D65 | 0 |

## Progressão, caixa e eventos por célula

Marcos são dias simulados de guild level 10/25/50. Fontes e drenos são totais reais registrados pelos serviços; residual zero reconcilia o delta de ouro diário. Pico de inventário compara unidades usadas com capacidade final.

| Perfil/política | D10/25/50 | Ouro fontes O/M/D/Market | Drenos compras/salvage | Delta/resíduo | Inventário pico/cap. | Overflow M/D/G/S | Recuperações/bloqueios finais | Portal: D/criados/encerrados* | Rebelião: D/ativações/oportunidades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ativo/roster_first | 10/36/68 | 23504/57035/3127/4488 | 23628/1750 | 62776/0 | 1613/1990 | 18/0/0/0 | 15/0 | D47/32/32 | D65/1/111 |
| ativo/commerce_early | 11/41/66 | 20920/62095/3003/125195 | 23628/2800 | 184785/0 | 870/1990 | 0/0/0/0 | 23/0 | D37/28/27 | D52/4/90 |
| casual/roster_first | 28/73/127 | 17232/58309/953/2170 | 2308/5400 | 70956/0 | 516/1990 | 0/0/0/0 | 3/0 | D52/232/232 | D72/18/776 |
| casual/commerce_early | 30/78/132 | 17576/59406/2173/6871 | 2308/5600 | 78118/0 | 517/1990 | 0/0/0/0 | 6/0 | D54/299/299 | D77/15/973 |
| offline/roster_first | 13/49/76 | 24840/62140/3490/2253 | 23628/2050 | 67045/0 | 1640/1990 | 4/0/0/0 | 14/0 | D33/108/107 | D49/7/332 |
| offline/commerce_early | 14/46/75 | 24040/62543/1998/116453 | 23628/3400 | 178006/0 | 855/1990 | 0/0/0/0 | 24/0 | D60/38/38 | D70/1/55 |
| produtor/roster_first | 19/44/73 | 20432/59268/3948/578825 | 2370/3250 | 656853/0 | 1738/1990 | 0/0/0/0 | 2/0 | D39/60/59 | D52/4/168 |
| produtor/commerce_early | 13/170/201 | 48504/61747/2589/1134591 | 2370/7400 | 1237661/0 | 1776/1990 | 0/0/0/0 | 6/0 | D61/561/559 | D84/31/1989 |
| combate/roster_first | 10/42/73 | 25232/63169/4673/2770 | 23628/2100 | 70116/0 | 1512/1990 | 0/0/0/0 | 14/0 | D35/73/73 | D43/5/226 |
| combate/commerce_early | 12/41/69 | 22760/61582/4398/116251 | 23628/2900 | 178463/0 | 671/1990 | 0/0/0/0 | 24/0 | D50/18/18 | D65/1/65 |

*Portal encerrado inclui estados resolved ou expired; o runner não executa ações de participação/resolução de evento pelo jogador. Eventos regionais são gerados e seus timers avançam pelos serviços de ciclo; contagem de fechamento não equivale a vitória do jogador.

## Comparação com o modelo N=20

Para `roster_first`, o modelo integrado anterior estimou medianas de nível 50 de D107 (ativo), D188,5 (casual), D84 (offline), D97,5 (produtor) e D108 (combate), com 20/20 por célula e IC95% Wilson 84–100%. As execuções reais correspondentes terminaram em D68, D127, D76, D73 e D73. Essa diferença é descritiva, não pareada: há N=1 no runtime, seeds distintas, mecanismo de sucesso/loot diferente e políticas operacionais não idênticas. O modelo usa `_cycle_outcome` e sincroniza roster abstrato diariamente; o runtime usa `mission_service`/`dungeon_service`, XP individual real, nível de cada mercenário sem sincronização sintética e transações/loot reais. O modelo não executa a masmorra nem participação/resolução de eventos.

## Limites e definições

- SQLite temporário por lote; saves reais não foram abertos. Todos os 10 jobs concluíram com 0 erros, 960 dias-cell agregados, e dentro de 365 dias/600 s por jornada. Checkpoints JSON são gravados atomicamente a cada dia, mas preservam evidência, não snapshot retomável do banco temporário.
- N=1 por perfil/política é um piloto de integração, não estima probabilidade de sucesso, taxa rara, inflação nem ausência global de softlock. Limites de Wilson por 1/1 e 0/1 são muito largos; não substituir nem agrupar com os modelos N=20/N=100.
- Sem sincronização diária de nível dos mercenários à guilda e sem crédito sintético de recursos. XP, drops, contratos, masmorras, gathering, Market, salvage e compras passam por serviços reais. O relógio, prioridades de compra, reserva de 30 materiais, limiar de 75 ouro para salvage e escolha/reatribuição do trabalhador são política controlada do harness, não comportamento aprovado do jogador.
- Os boards são finitos e cada oferta é executada uma vez; templates ativos entram via `mission_service` apenas no bootstrap sem oferta regional elegível. Eventos são gerados/atualizados por ciclos reais, mas nenhuma resolução de portal ou rebelião pelo jogador é simulada. Portal aberto/encerrado não demonstra participação ou recompensa.
- Sem crafting no caminho fresh-save, sem compra de opção fora do plano, sem garantia de rotação natural; os serviços usam RNG runtime, mas estratégias e horários são fixos. Overflow observado inclui 22 unidades de missão em 960 dias-célula; gathering, dungeon e salvage não descartaram unidades.
- Plano finito e recuperação de compra observada não provam hard softlock global ou estabilidade econômica. O perfil produtor mostrou vendas de material muito altas sob esta política e horizonte, o que é sinal para análise econômica separada, não aprovação de balance.

## Reprodução

```powershell
.venv-desktop\Scripts\python.exe scripts\balance\simulate_stage5_service_journeys.py --runs-per-cell 1 --seed-start 2026103000 --max-days 365 --max-wall-seconds 600 --market-reserve-base 30 --output-stem stage5_live_service_journeys_2026-10-29
```

## Escala de vendas do Market e sensibilidade da reserva

No caso-base, `commerce_early` constrói Market 1 após formar o party mínimo. Todas as quatro células de `commerce_early` ficaram no Market 1: um slot, bônus de valor 0% e redução de tempo 0%. O preço efetivo médio abaixo é ouro coletado dividido por unidades vendidas; muda conforme os templates de material selecionados.

| Perfil/política | Lotes | Unidades vendidas | Ouro Market | Ouro/unidade ponderado |
|---|---:|---:|---:|---:|
| ativo/commerce_early | 55 | 19.730 | 125.195 | 6,35 |
| offline/commerce_early | 68 | 17.064 | 116.453 | 6,82 |
| combate/commerce_early | 57 | 17.048 | 116.251 | 6,82 |
| produtor/commerce_early | 186 | 112.509 | 1.134.591 | 10,08 |

Em `produtor/commerce_early`, as vendas somaram madeira 69.769/662.216 ouro, minério 22.339/263.036 e couro 20.401/209.339. O material produzido por gathering foi 113.196 unidades; o Market escoou 112.509. Sob a política do harness, vende-se o maior excedente disponível (uma pilha por checkpoint diário), preservando 30 unidades/família e acrescentando o custo do próximo upgrade para madeira/minério; o serviço `start_material_sale` inicia e `collect_market_sale` coleta na fronteira do dia seguinte. O caminho usa serviços e preços atuais, mas venda diária disciplinada, prioridades fixas, checkpoints perfeitos e alocação predefinida de trabalhadores tornam o volume uma trajetória otimizada do harness, não um comportamento medido de jogador. O Market 1 não concede bônus de valor nem aceleração; a faixa efetiva observada nos lotes foi 5–45 ouro/unidade, dependendo do template.

Uma sensibilidade N=1 pareada reutilizou o produtor, caminho e seed 2026413000 e alterou apenas a reserva fixa para 300 unidades/família. O nível 50 chegou no D198 (base D201); o saldo final foi 622.254 contra 1.237.691, vendas caíram de 112.509 unidades/1.134.591 ouro para 45.751/520.224, e gathering acumulado caiu de 113.196 para 46.687 unidades. O pico de inventário foi 1.886/1.990 contra 1.776/1.990, sem descarte em nenhum caso. É sensibilidade descritiva: demonstra a influência da reserva e espaço de estoque na renda deste harness, não arbitragem, estabilidade econômica ou causalidade generalizável. A auditoria de ciclos fechados permanece separada.
