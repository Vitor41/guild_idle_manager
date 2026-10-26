# Estudo de Balanceamento: Masmorras e Chefes

## Escopo e decisão pendente

Este documento é **somente um estudo**. Nenhuma recomendação de chance ou loot foi aplicada.
A única alteração efetiva deste pacote foi liberar o Chefe recomendado para nível 1 de requisitos rígidos de formação e equipamento.

## Diagnóstico executivo

- Masmorras e Chefes ativos possuem, em média, apenas **1 equipamento e 1 material possíveis** por card.
- O sistema atual soma bônus de drop em pontos percentuais: Ferreiro +25, habilidades +20 e Exploradores +10, totalizando até **+55 p.p.**.
- Um drop Mítico base de 3% pode chegar a 58% após uma vitória; isto torna bônus de endgame desproporcionais.
- A chance de conclusão também pode receber Poder +15, Classe +8, Raridade +20, Habilidades +20, Sinergia +6 e Exploradores +2. Chefes tardios podem atingir o teto global de 95%.
- Adicionar várias linhas de drop ao modelo atual faria rolagens independentes e permitiria múltiplos equipamentos na mesma coleta.

## Modelo recomendado para análise

1. Manter vários equipamentos visíveis como **pool de possibilidades**.
2. Após uma vitória, realizar uma única rolagem para decidir se haverá equipamento.
3. Se houver, escolher no máximo um equipamento do pool por pesos de raridade.
4. Manter materiais em rolagens separadas.
5. Aplicar bônus de drop como multiplicador percentual, não como pontos percentuais: `chance_base × (1 + bônus/100)`.
6. Aplicar teto de conclusão específico para Chefes, decrescente por faixa.

## Parâmetros simulados no cenário recomendado

| Faixa | Teto Masmorra | Teto Chefe | Pool Masmorra médio | Pool Chefe | Roll equip. Masmorra | Roll equip. Chefe | Raro+ no pool Chefe | Mítico no pool Chefe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-20 | 92% | 80% | 3.3 | 4 | 38% | 48% | 5% | 0% |
| 21-50 | 90% | 72% | 3.5 | 5 | 36% | 44% | 12% | 0% |
| 51-100 | 88% | 65% | 3.5 | 6 | 34% | 40% | 25% | 0% |
| 101-130 | 85% | 58% | 3.5 | 7 | 31% | 34% | 40% | 0% |
| 131-200 | 82% | 50% | 3.5 | 8 | 28% | 28% | 55% | 0.5% |
| 201-250 | 80% | 45% | 3.5 | 9 | 25% | 22% | 68% | 1% |
| 251-300 | 78% | 40% | 3.5 | 10 | 23% | 16% | 78% | 2% |
| 301-350 | 75% | 35% | 3.5 | 12 | 20% | 10% | 88% | 3% |

## Estado atual por faixa

| Faixa | Masmorras | Chefes | Equip. possíveis/Masmorra | Equip. possíveis/Chefe | Materiais/Masmorra | Materiais/Chefe |
|---|---:|---:|---:|---:|---:|---:|
| 1-20 | 12 | 2 | 1.3 | 1.0 | 1.0 | 1.0 |
| 21-50 | 15 | 3 | 1.0 | 1.0 | 1.0 | 1.0 |
| 51-100 | 22 | 5 | 1.0 | 1.0 | 1.0 | 1.0 |
| 101-130 | 15 | 3 | 1.0 | 1.0 | 1.0 | 1.0 |
| 131-200 | 30 | 8 | 1.0 | 1.0 | 1.0 | 1.0 |
| 201-250 | 22 | 6 | 1.0 | 1.0 | 1.0 | 1.0 |
| 251-300 | 22 | 6 | 1.0 | 1.0 | 1.0 | 1.0 |
| 301-350 | 26 | 10 | 1.0 | 1.0 | 1.0 | 1.0 |

## Comparação: grupo Fraco

| Faixa | Conclusão atual Masm. | Conclusão prop. Masm. | Equip./tentativa atual | Equip./tentativa prop. | Conclusão atual Chefe | Conclusão prop. Chefe | Equip./tentativa atual Chefe | Equip./tentativa prop. Chefe | Mítico prop. Chefe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-20 | 51.83% | 51.83% | 22.03% | 19.70% | 49.00% | 49.00% | 20.58% | 23.52% | 0.00% |
| 21-50 | 54.20% | 54.20% | 17.03% | 19.51% | 42.67% | 42.67% | 16.21% | 18.77% | 0.00% |
| 51-100 | 51.41% | 51.41% | 13.88% | 17.48% | 32.80% | 32.80% | 9.94% | 13.12% | 0.00% |
| 101-130 | 48.33% | 48.33% | 9.63% | 14.98% | 30.00% | 30.00% | 7.50% | 10.20% | 0.00% |
| 131-200 | 45.70% | 45.70% | 7.21% | 12.80% | 26.88% | 26.88% | 4.54% | 7.53% | 0.04% |
| 201-250 | 42.59% | 42.59% | 6.92% | 10.65% | 24.00% | 24.00% | 3.91% | 5.28% | 0.05% |
| 251-300 | 39.59% | 39.59% | 3.98% | 9.11% | 21.00% | 21.00% | 2.00% | 3.36% | 0.07% |
| 301-350 | 38.19% | 38.19% | 3.03% | 7.64% | 18.80% | 18.80% | 1.24% | 1.88% | 0.06% |

## Comparação: grupo No nível

| Faixa | Conclusão atual Masm. | Conclusão prop. Masm. | Equip./tentativa atual | Equip./tentativa prop. | Conclusão atual Chefe | Conclusão prop. Chefe | Equip./tentativa atual Chefe | Equip./tentativa prop. Chefe | Mítico prop. Chefe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-20 | 80.33% | 79.83% | 42.77% | 33.37% | 74.00% | 74.00% | 38.29% | 39.07% | 0.00% |
| 21-50 | 81.20% | 80.67% | 33.52% | 31.94% | 69.67% | 67.33% | 33.44% | 32.59% | 0.00% |
| 51-100 | 80.41% | 79.50% | 29.71% | 29.73% | 61.80% | 61.80% | 24.99% | 27.19% | 0.00% |
| 101-130 | 78.33% | 77.40% | 23.44% | 26.39% | 60.00% | 58.00% | 21.00% | 21.69% | 0.00% |
| 131-200 | 77.70% | 75.90% | 19.97% | 23.38% | 58.88% | 50.00% | 15.94% | 15.40% | 0.08% |
| 201-250 | 77.59% | 75.27% | 20.35% | 20.70% | 59.00% | 45.00% | 15.64% | 10.89% | 0.11% |
| 251-300 | 76.59% | 73.77% | 15.34% | 18.66% | 58.00% | 40.00% | 11.37% | 7.04% | 0.14% |
| 301-350 | 77.19% | 72.38% | 13.77% | 15.92% | 57.80% | 35.00% | 9.75% | 3.85% | 0.12% |

## Comparação: grupo Forte

| Faixa | Conclusão atual Masm. | Conclusão prop. Masm. | Equip./tentativa atual | Equip./tentativa prop. | Conclusão atual Chefe | Conclusão prop. Chefe | Equip./tentativa atual Chefe | Equip./tentativa prop. Chefe | Mítico prop. Chefe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-20 | 92.33% | 89.83% | 68.35% | 45.06% | 93.00% | 80.00% | 68.42% | 50.69% | 0.00% |
| 21-50 | 94.93% | 90.00% | 59.81% | 42.77% | 90.33% | 72.00% | 63.23% | 41.82% | 0.00% |
| 51-100 | 95.00% | 88.00% | 55.92% | 39.49% | 86.20% | 65.00% | 53.87% | 34.32% | 0.00% |
| 101-130 | 94.93% | 85.00% | 49.31% | 34.78% | 85.67% | 58.00% | 48.83% | 26.03% | 0.00% |
| 131-200 | 95.00% | 82.00% | 45.22% | 30.31% | 86.50% | 50.00% | 42.50% | 18.48% | 0.09% |
| 201-250 | 95.00% | 80.00% | 45.77% | 26.40% | 88.00% | 45.00% | 42.73% | 13.07% | 0.13% |
| 251-300 | 95.00% | 78.00% | 39.90% | 23.68% | 86.67% | 40.00% | 36.10% | 8.45% | 0.17% |
| 301-350 | 95.00% | 75.00% | 37.78% | 19.80% | 88.50% | 35.00% | 34.44% | 4.62% | 0.14% |

## Comparação: grupo Máximo

| Faixa | Conclusão atual Masm. | Conclusão prop. Masm. | Equip./tentativa atual | Equip./tentativa prop. | Conclusão atual Chefe | Conclusão prop. Chefe | Equip./tentativa atual Chefe | Equip./tentativa prop. Chefe | Mítico prop. Chefe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-20 | 95.00% | 92.00% | 88.98% | 54.19% | 95.00% | 80.00% | 91.67% | 59.52% | 0.00% |
| 21-50 | 95.00% | 90.00% | 81.70% | 50.22% | 95.00% | 72.00% | 88.35% | 49.10% | 0.00% |
| 51-100 | 95.00% | 88.00% | 77.77% | 46.38% | 95.00% | 65.00% | 81.32% | 40.30% | 0.00% |
| 101-130 | 95.00% | 85.00% | 71.19% | 40.84% | 95.00% | 58.00% | 76.00% | 30.57% | 0.00% |
| 131-200 | 95.00% | 82.00% | 67.07% | 35.59% | 95.00% | 50.00% | 68.64% | 21.70% | 0.11% |
| 201-250 | 95.00% | 80.00% | 67.62% | 31.00% | 95.00% | 45.00% | 68.08% | 15.35% | 0.15% |
| 251-300 | 95.00% | 78.00% | 61.75% | 27.81% | 95.00% | 40.00% | 61.43% | 9.92% | 0.20% |
| 301-350 | 95.00% | 75.00% | 59.63% | 23.25% | 95.00% | 35.00% | 58.90% | 5.43% | 0.16% |

## Simulação Monte Carlo

Foram executadas **100.000 tentativas por faixa, tipo de conteúdo, força de grupo e modelo**.
A tabela abaixo resume o cenário Máximo, onde o risco de banalização é maior.

| Faixa | Modelo | Sucessos Chefes | Equipamentos | Raro+ | Míticos | Tentativas por Mítico |
|---|---|---:|---:|---:|---:|---:|
| 1-20 | Atual | 95038 | 91648 | 44298 | 0 | — |
| 1-20 | Recomendado | 79980 | 59633 | 3027 | 0 | — |
| 21-50 | Atual | 94899 | 88362 | 88362 | 0 | — |
| 21-50 | Recomendado | 71989 | 48990 | 5855 | 0 | — |
| 51-100 | Atual | 95025 | 81205 | 81205 | 0 | — |
| 51-100 | Recomendado | 64958 | 40229 | 9986 | 0 | — |
| 101-130 | Atual | 94990 | 75937 | 75937 | 0 | — |
| 101-130 | Recomendado | 57970 | 30268 | 12138 | 0 | — |
| 131-200 | Atual | 94794 | 68710 | 68710 | 0 | — |
| 131-200 | Recomendado | 49814 | 21975 | 11941 | 103 | 971 |
| 201-250 | Atual | 94926 | 68302 | 68302 | 0 | — |
| 201-250 | Recomendado | 45012 | 15289 | 10328 | 143 | 700 |
| 251-300 | Atual | 94929 | 61447 | 61447 | 18136 | 6 |
| 251-300 | Recomendado | 39447 | 9991 | 7796 | 208 | 481 |
| 301-350 | Atual | 94936 | 58987 | 58987 | 33057 | 4 |
| 301-350 | Recomendado | 35001 | 5540 | 4852 | 177 | 565 |

## Leitura de produto

- **Missões:** fonte básica, normalmente 1 material + 1 equipamento possível.
- **Masmorras:** maior variedade e frequência de equipamento intermediário; dificuldade aumenta o tamanho do pool.
- **Chefes:** maior variedade e qualidade, mas conclusão e rolagem de equipamento diminuem fortemente no late game.
- Um Chefe pode ser mais vantajoso para buscar um item forte sem ser a melhor fonte de equipamentos por hora.
- O Chefe nível 1 funciona como apresentação da mecânica. O Chefe nível 16 mantém composição, poder e equipamento obrigatórios.

## Decisões sugeridas para aprovação

1. Aprovar ou ajustar os tetos de conclusão de Chefes por faixa.
2. Aprovar o pool com no máximo um equipamento por vitória.
3. Aprovar bônus de drop multiplicativos em vez de aditivos.
4. Definir se Chefes devem entregar materiais garantidos ou apenas com chance alta.
5. Definir os pesos exatos de Raro, Épico, Lendário e Mítico por faixa.

## Alteração efetivamente aplicada

- Chefe recomendado para nível 1: grupo 1–5, sem papéis obrigatórios, sem Tier obrigatório e sem bloqueio rígido por Poder.
- Poder 60 permanece como referência para o cálculo de chance.
- Chefe recomendado para nível 16 não foi alterado.
- Nenhuma chance, recompensa ou tabela de loot foi modificada.
