# E4 — gate integrado de equilíbrio regional

**Decisão:** gate reprovado. Manter ML-021 aberto e ML-029 sem conclusão de produto. Esta rodada não alterou multiplicadores, chance de rebelião ou cooldown.

## Método

Comparação pareada dos serviços reais de campanha sobre as seeds `2026110301–2026110320`, com 100 Vigílias de seis horas por campanha e por tratamento (2.000 Vigílias por tratamento). O baseline usa E1+E3 e conserva o `recommended_power` dos templates; o integrado usa E1+E2+E3 com o snapshot de poder por Rank e tamanho de grupo. Cada par parte de clones descartáveis equivalentes, sem ações de jogador e sem acesso a saves do usuário.

O runner falhava ao criar arquivos temporários do SQLite no ambiente. A execução foi repetida com `PRAGMA temp_store=MEMORY` aplicado em runtime aos motores SQLite dos cenários; o ajuste não mudou arquivos de produto ou regras da simulação. O save-base descartável foi criado e os 20 pares terminaram.

Evidência bruta por seed, tratamento, escopo e fase: [CSV](lot_e2_ml029_cpu_paired_2026-11-09-e4-integrated.csv) e [JSON pareado](lot_e2_ml029_cpu_paired_2026-11-09-e4-integrated.json).

## Resultados integrados

| Indicador (20 campanhas) | Baseline E1+E3 | Integrado E1+E2+E3 | Variação |
|---|---:|---:|---:|
| Campanhas com ao menos uma rebelião | 4/20 (20%) | 6/20 (30%) | +2 campanhas |
| Rebeliões abertas | 4 | 6 | +2 |
| Rolagens selecionadas | 217 | 220 | +3 |
| Região-ciclos elegíveis (ameaça ≥85 e segurança ≤25) | 859 | 1.035 | +176 (+20,5%) |
| Campanhas com mais de uma região elegível no mesmo ciclo | 0/20 | 0/20 | sem mudança |
| Máximo de rebeliões simultâneas | 1 | 1 | sem mudança |
| Portais abertos | 112 | 125 | +13 (+11,6%) |
| Portais iniciados pela CPU | 0 | 0 | sem mudança |

O requisito de ocorrência é **mais de 10 campanhas em 20**. O integrado alcançou 6/20; portanto, a frequência de rebelião não passou o critério. A pressão simultânea também não produziu ciclos com várias regiões vulneráveis: o cap/cooldown continuou limitando as rolagens a uma região por ciclo.

| Resultado CPU | Baseline E1+E3 | Integrado E1+E2+E3 | Variação |
|---|---:|---:|---:|
| Ações resolvidas (100 Vigílias) | 101.247 | 101.234 | −13 (−0,01%) |
| Sucessos / falhas (100 Vigílias) | 73.770 / 27.477 | 53.291 / 47.943 | −20.479 / +20.466 |
| Taxa média de sucesso por campanha | 72,9% | 52,6% | −20,2 p.p. |
| Ouro líquido de planos CPU | 429.940 | 430.178 | +238 |
| XP líquido de planos CPU | 30.313.874 | 24.555.686 | −5.758.188 (−19,0%) |
| Contratações CPU | 2.877 | 2.553 | −324 (−11,3%) |
| Nível médio final das guildas CPU | 17,82 | 15,72 | −2,10 |
| Tamanho médio final do elenco CPU | 8,24 | 7,57 | −0,68 |

As ações praticamente não mudaram; a diferença veio principalmente de menos sucesso e XP, menor contratação e elencos finais menores. Os portais ficaram mais frequentes, mas não houve entrada CPU em portal em nenhum tratamento. Esse dado aponta uma lacuna de participação CPU que já existe no baseline; esta comparação não demonstra que E2 a causou.

## Casos de referência do jogador

Os testes usam a curva de poder máxima válida para um Aprendiz Comum. O bônus abaixo é somente o componente de poder; a chance final também depende da chance-base do contrato e do bônus de classe, com limite de 5% a 95%.

| Caso | Poder de grupo | Poder recomendado | Ajuste por poder no fallback | Ajuste por poder integrado |
|---|---:|---:|---:|---:|
| Rank E, nível 1, Comum solo | 18 | 10 → 13 | +15 p.p. → +9 p.p. | −6 p.p. |
| Rank C, nível 18, grupo de 2 Comuns | 186 (93 cada) | 49 → 144 | +15 p.p. → +8 p.p. | −7 p.p. |

Esses exemplos confirmam a aplicação para jogadores e CPU pela mesma fórmula. O grupo C18 deixa de receber o bônus máximo de poder que o template de 49 proporcionava; esse impacto está refletido na queda de sucesso CPU observada.

## Leitura do gate e opções para decisão

O integrado elevou rebeliões de 4 para 6 campanhas e aumentou as região-ciclos elegíveis, mas não chegou ao alvo de mais de 10/20. Ao mesmo tempo, reduziu a taxa de sucesso CPU em 20,2 p.p. e XP em 19%, sem redução relevante no volume de ações. Assim, os dados sustentam que a fórmula E2 muda materialmente a progressão e ainda não resolve a frequência de rebeliões.

Manter ML-021 aberto. Próximas opções para uma decisão explícita de produto, sem alteração nesta rodada:

1. Reavaliar a chance de 2% por rolagem elegível; testar uma taxa maior em uma rodada própria, mantendo ameaça ≥85 e segurança ≤25.
2. Reavaliar o cooldown regional de cinco Vigílias; um intervalo menor permitiria mais tentativas, com risco de concentrar eventos.
3. Manter as regras e o alvo atuais e tratar o resultado de 6/20 como bloqueio para release até nova calibração aprovada.

Qualquer nova calibração precisa repetir o pareamento integrado e medir novamente progressão, risco de rebelião e participação em portais. Nenhuma alternativa foi implementada aqui.

## Regressões focadas

- `test_ml029_mission_power.py`: **5/5 passaram**.
- `test_campaign_content_versioning.py`: **4/4 passaram**.
- `test_ml030_equipment_bonus_rules.py`: **6/6 passaram**.
- `test_regional_cpu_simulation.py`: **2/2 passaram**.

Os testes de campanha usaram o mesmo ajuste SQLite somente em runtime e saves temporários isolados.
