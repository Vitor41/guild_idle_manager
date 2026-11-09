# Lote E1 — calibração de cadência CPU e crises regionais

**Base:** `a818bfc867102df52205ac71b22ee2030c5bd376`
**Escopo:** somente campanhas descartáveis; 20 seeds fixos (`2026110301`–`2026110320`), 100 Vigílias cada, serviços reais de campanha, CPU, eventos e snapshots. Nenhum save do usuário foi aberto.

## Decisão

Manter os parâmetros de jogo atuais da `vigilia-v6`. Nenhuma das três calibrações justificou alterar a janela ou acelerar a pressão: o ganho de rebeliões ficou muito abaixo da meta de 11 campanhas, enquanto as candidatas aumentaram bastante o tempo em crise ou reduziram portais. A escolha de região permanece baseada no maior risco, com desempate determinístico; não foi fixada uma região específica.

## Evidência das calibrações

| Variante | Seeds | Campanhas com rebelião | Rolagens selecionadas/campanha | Ciclos com região vulnerável | Portais | CPU ações/Vigília | Sucesso CPU | Regiões simultaneamente vulneráveis |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline: janela 19, pressão 9,5–9,9 / segurança 4,5–4,9 | 20 | 4/20 | 10,85 | 42,85 | 112 | 50,62 | 72,85% | máximo 1; zero ciclos com 2+ |
| Pressão acelerada: janela 19, pressão 12,5–12,9 / segurança 6,0–6,4 | 5 | 1/5 (baseline pareado: 1/5) | 11 | 56,8 | — | — | — | máximo 1; zero ciclos com 2+ |
| Janela 35, pressão baseline | 20 | 5/20 | 12 | 67,0 | 85 | 50,62 | 73,04% | máximo 1; zero ciclos com 2+ |
| Diagnóstico descartado: janela 10, pressão baseline | 2 | 0/2 | 1 | 4 | — | — | — | sem sobreposição |

A janela 35 elevou rebeliões de 4 para 6 eventos e campanhas afetadas de 4 para 5, mas aumentou ciclos vulneráveis em 56% e reduziu portais em 24%. A pressão acelerada aumentou a exposição sem aumentar as rolagens ou rebeliões nos cinco seeds pareados. A janela 10 foi abandonada após os dois primeiros seeds, que caíram de 11 para 1 rolagem cada.

## Funil causal na candidata de janela 35

O funil alinha o estado materializado no snapshot de uma Vigília à avaliação de rebelião que ocorre quando a próxima Vigília abre. Em 2.000 verificações possíveis, houve 1.980 ciclos-região com pressão direcionada; 1.352 ciclos-região alcançaram simultaneamente ameaça ≥85 e segurança ≤25. A vulnerabilidade ficou em no máximo uma região por ciclo.

Das 1.352 elegibilidades: 240 foram selecionadas para rolagem; 1.100 foram vetadas pelo cooldown regional de 5 ciclos; 12 foram bloqueadas enquanto uma rebelião global ainda estava ativa; zero foram barradas pelo limite de uma rolagem por ciclo; zero ficaram sem atribuição. A partição fecha exatamente: `240 + 1.100 + 12 = 1.352`.

As 240 rolagens a 2% previam 4,8 aberturas. Houve 6 aberturas e 234 falhas de RNG (2,5% de sucesso observado nas rolagens), resultado compatível com a taxa configurada. A baixa incidência vem principalmente do cooldown regional, não de falta de estados vulneráveis, do teto global ou de uma sequência adversa de RNG. A janela 35 produz 12 rolagens por campanha, contra 10,85 no baseline, ainda muito abaixo da meta sem elevar a pressão de forma dispendiosa.

O [relatório detalhado](lot_e1_cpu_pressure_2026-11-08.md) inclui o funil por Vigília e região; os dados completos estão no [JSON](lot_e1_cpu_pressure_2026-11-08.json).

## Risco residual

A taxa escolhida pelo usuário continua em 2% por rolagem elegível, com cooldown regional de 5 ciclos e limite de uma região por rolagem. A melhor candidata completa produziu 12 rolagens por campanha e 5 campanhas com rebelião em 20 seeds — abaixo da meta de mais de 10. Pelo modelo binomial aproximado, 12 rolagens independentes a 2% dão 21,5% de chance por campanha, 4,3 campanhas esperadas em 20, e cerca de 0,11% de chance de alcançar 11 ou mais. Essa probabilidade é uma inferência; o resultado observado vem da matriz determinística.

Para obter a frequência pedida seria necessário elevar muito a quantidade de rolagens elegíveis ou a chance aprovada. A janela 35 já adiciona 24 ciclos vulneráveis por campanha sem entregar a frequência pretendida e reduz portais; por isso não é um equilíbrio seguro para promover. O cooldown explica a maior parte da diferença entre elegibilidade e rolagem, mas foi mantido conforme a regra aprovada. Manter 2% e cooldown de 5 preserva as regras aprovadas. A meta de 11/20 permanece não alcançada e deve ser decidida em revisão de balanceamento.

## Relatórios e validação

- [Matriz de 20 campanhas e cortes por perfil/região](lot_e1_cpu_pressure_2026-11-08.md)
- [Dados JSON da matriz](lot_e1_cpu_pressure_2026-11-08.json)
- A simulação mantém os dados por guilda, ofertas elegíveis, roster disponível, duração e prioridade humana de 1h; agrupa CPU por perfil e por início/meio/fim, comparando a região natal com as quatro regiões externas.
- Foi adicionado teste automatizado para garantir que os clones descartáveis reidentificam somente linhas do save-modelo e preservam linhas globais. As regras de cooldown, chance, snapshots e catch-up permanecem no serviço testado existente.
