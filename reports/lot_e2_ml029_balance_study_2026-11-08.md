# ML-029 — estudo de poder recomendado para contratos regionais

Este arquivo é gerado pelo script `scripts/balance/study_ml029_contract_power.py` a partir da curva real de progressão e de templates seedados em uma campanha descartável. Nenhum save do usuário é consultado.

## Referência Comum

O maior vetor válido recém-contratado é FOR/VIT/AGI/INT/SOR `7/7/7/7/7`: cada atributo respeita o cap Comum 7 e a fórmula de poder produz 18, dentro do intervalo Comum 1–18. O gerador de Taverna não aplica o bônus de função ao Aprendiz. A tabela por nível chama `apply_levelup_attributes()` real para raridade Comum e `calculate_power_score()` real, sem equipamento, profissão, skills ou evolução.

Com classe Aprendiz, cada level-up acrescenta FOR +2, VIT +2, AGI +1, INT +1 e SOR +1. Para Comum, o bônus por raridade é 0%. Essa curva de referência mantém a classe inicial; não representa uma trilha universal de evolução. `apply_class_evolution_attributes()` soma apenas deltas positivos dos atributos-base da classe de origem para a classe-alvo, e `class_success_bonus()`/skills/equipamento entram separadamente no cálculo de chance.

| Nível | Atributos FOR/VIT/AGI/INT/SOR | Poder |
|---:|---|---:|
| 1 | 7/7/7/7/7 | 18 |
| 5 | 15/15/11/11/11 | 35 |
| 10 | 25/25/16/16/16 | 58 |
| 12 | 29/29/18/18/18 | 67 |
| 18 | 41/41/24/24/24 | 93 |
| 20 | 45/45/26/26/26 | 101 |
| 50 | 105/105/56/56/56 | 231 |
| 75 | 155/155/81/81/81 | 339 |
| 100 | 205/205/106/106/106 | 448 |
| 200 | 405/405/206/206/206 | 881 |
| 350 | 705/705/356/356/356 | 1531 |

A tabela completa de 350 níveis está em [CSV](lot_e2_ml029_common_apprentice_1_350.csv).

## Exemplos do catálogo atual e comparação

O baseline é o `recommended_power` do template normal mais próximo do nível, com party iniciável de tamanho mínimo 1 e máximo correspondente à faixa. Hoje esse valor é copiado ao snapshot sem usar Rank; o Rank atual ordena ofertas, mas não multiplica o poder recomendado. Os candidatos usam `ceil(poder_Comum(nível) × multiplicador_Rank × grupo_máximo)`. Chance base, ajuste de poder, limites e suprimento usam os serviços atuais. A tabela base isola mercenários Comuns sem bônus de classe/raridade/skill e sem equipamento. As colunas de sensibilidade somam a melhor combinação por slot de equipamentos seedados até o nível do cenário, usando o maior valor RNG legal de cada peça, e/ou os limites atuais de classe, skill e raridade; isso representa um teto de catálogo, não uma expectativa de posse.

Caso do usuário: Rank C nível 18, grupo 1–2: template `Localizar Suprimentos Perdidos em Bosque dos Sinos` mantém recomendação atual 49, base 80%; a referência Comum nível 18 tem poder 93. O baseline dá chance 95% para solo e 95% para grupo máximo antes de classe/skill/suprimento.

| Nível | Rank | Grupo máx. | Tipo | Template base atual | Poder atual | Poder candidato | Chance atual | Chance candidata | Com suprimento | Classe+skill máx. | Equip.+classe+skill+raridade máx. | Mesmo teto + suprimento |
|---:|:---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | E | 2 | solo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 26 | 95% | 68% | 73% | 86% | 95% | 95% |
| 1 | E | 2 | grupo_maximo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 26 | 95% | 91% | 95% | 95% | 95% | 95% |
| 1 | C | 2 | solo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 28 | 95% | 65% | 70% | 83% | 95% | 95% |
| 1 | C | 2 | grupo_maximo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 28 | 95% | 90% | 95% | 95% | 95% | 95% |
| 1 | S | 2 | solo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 40 | 95% | 57% | 62% | 75% | 95% | 95% |
| 1 | S | 2 | grupo_maximo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 40 | 95% | 77% | 82% | 95% | 95% | 95% |
| 5 | E | 2 | solo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 49 | 93% | 65% | 70% | 83% | 95% | 95% |
| 5 | E | 2 | grupo_maximo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 49 | 93% | 88% | 93% | 95% | 95% | 95% |
| 5 | C | 2 | solo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 54 | 93% | 62% | 67% | 80% | 95% | 95% |
| 5 | C | 2 | grupo_maximo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 54 | 93% | 86% | 91% | 95% | 95% | 95% |
| 5 | S | 2 | solo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 76 | 93% | 53% | 58% | 71% | 95% | 95% |
| 5 | S | 2 | grupo_maximo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 76 | 93% | 74% | 79% | 95% | 95% | 95% |
| 18 | E | 2 | solo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 131 | 95% | 66% | 71% | 84% | 95% | 95% |
| 18 | E | 2 | grupo_maximo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 131 | 95% | 90% | 95% | 95% | 95% | 95% |
| 18 | C | 2 | solo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 144 | 95% | 64% | 69% | 82% | 95% | 95% |
| 18 | C | 2 | grupo_maximo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 144 | 95% | 88% | 93% | 95% | 95% | 95% |
| 18 | S | 2 | solo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 202 | 95% | 55% | 60% | 73% | 86% | 91% |
| 18 | S | 2 | grupo_maximo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 202 | 95% | 76% | 81% | 95% | 95% | 95% |
| 50 | E | 2 | solo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 324 | 87% | 59% | 64% | 77% | 95% | 95% |
| 50 | E | 2 | grupo_maximo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 324 | 87% | 82% | 87% | 95% | 95% | 95% |
| 50 | C | 2 | solo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 356 | 87% | 56% | 61% | 74% | 93% | 95% |
| 50 | C | 2 | grupo_maximo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 356 | 87% | 80% | 85% | 95% | 95% | 95% |
| 50 | S | 2 | solo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 502 | 87% | 47% | 52% | 65% | 78% | 83% |
| 50 | S | 2 | grupo_maximo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 502 | 87% | 68% | 73% | 89% | 95% | 95% |
| 75 | E | 3 | solo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 712 | 79% | 40% | 45% | 58% | 77% | 82% |
| 75 | E | 3 | grupo_maximo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 712 | 79% | 74% | 79% | 95% | 95% | 95% |
| 75 | C | 3 | solo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 784 | 79% | 38% | 43% | 56% | 73% | 78% |
| 75 | C | 3 | grupo_maximo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 784 | 79% | 72% | 77% | 95% | 95% | 95% |
| 75 | S | 3 | solo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1104 | 79% | 32% | 37% | 50% | 64% | 69% |
| 75 | S | 3 | grupo_maximo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1104 | 79% | 60% | 65% | 83% | 95% | 95% |
| 200 | E | 4 | solo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 2467 | 66% | 22% | 27% | 40% | 57% | 62% |
| 200 | E | 4 | grupo_maximo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 2467 | 66% | 61% | 66% | 84% | 95% | 95% |
| 200 | C | 4 | solo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 2714 | 66% | 20% | 25% | 38% | 55% | 60% |
| 200 | C | 4 | grupo_maximo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 2714 | 66% | 59% | 64% | 82% | 95% | 95% |
| 200 | S | 4 | solo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 3824 | 66% | 16% | 21% | 34% | 49% | 54% |
| 200 | S | 4 | grupo_maximo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 3824 | 66% | 47% | 52% | 70% | 93% | 95% |
| 350 | E | 5 | solo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 5359 | 52% | 5% | 9% | 22% | 48% | 53% |
| 350 | E | 5 | grupo_maximo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 5359 | 52% | 47% | 52% | 70% | 95% | 95% |
| 350 | C | 5 | solo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 5895 | 52% | 5% | 8% | 21% | 47% | 52% |
| 350 | C | 5 | grupo_maximo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 5895 | 52% | 45% | 50% | 68% | 95% | 95% |
| 350 | S | 5 | solo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 8306 | 52% | 5% | 5% | 18% | 42% | 47% |
| 350 | S | 5 | grupo_maximo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 8306 | 52% | 33% | 38% | 56% | 89% | 94% |

A comparação integral Rank E–S, nos três conjuntos de multiplicadores, está em [CSV de cenários](lot_e2_ml029_scenarios_2026-11-08.csv). `grupo_max` é o tamanho máximo real do template amostrado; `solo` usa um mercenário e `grupo_maximo` usa esse número de Comuns. O baseline de cada nível é igual entre Ranks porque o template atual não escala poder pelo Rank.

## Multiplicadores avaliados

| Rank | PO inicial | Primeiro candidato E2 | E2 ajustado para reteste |
|:---:|---:|---:|---:|
| E | 1.00 | 1.00 | 0.700 |
| D | 1.15 | 1.05 | 0.735 |
| C | 1.30 | 1.10 | 0.770 |
| B | 1.50 | 1.20 | 0.840 |
| A | 1.75 | 1.35 | 0.945 |
| S | 2.00 | 1.55 | 1.085 |

## Decisão e riscos

A primeira variante E2 foi revisada após a simulação pareada de CPU: manteve o volume de ações, mas reduziu em cerca de 25 p.p. a taxa média de sucesso dos rivais e em 22–24% o XP líquido por fase. O reteste com redução de 20% melhorou pouco; esta calibração reduz todos os multiplicadores em 30% igualmente para jogador e CPU, sem exceção por origem. Rank C nível 18 recomenda `144` (`ceil(93 × 0.770 × 2)`), com chance Comum 64% solo e 88% em grupo; suprimento leva a 69%/93%. O primeiro candidato E2 avaliava o mesmo grupo em 205 de poder e 75%. No nível 1, Rank E recomenda 26 e dá 68% solo / 91% em grupo (suprimento: 73%/95%); C18 fica abaixo do teto de 95%, e o grupo continua mais viável que o solo. Rank S completo no nível 350 fica em 33% antes de bônus/equipamento.
A calibração final de −30% foi pareada em cinco seeds (100 Vigílias por tratamento): sucesso total CPU 72,7%→52,4% (−20,4 p.p.), com ações 50,64→50,63 por Vigília praticamente iguais. O XP líquido caiu 19,3% no início, 18,3% no meio e 20,3% no final; o nível médio final das guildas CPU foi 17,83→15,74. Rebeliões foram 1→4 em cinco campanhas, com 55 rolagens em ambos os lados (chance configurada 2% por rolagem); estados elegíveis foram 216→263 e portais 28→31. Contratos continuaram elegíveis/iniciados em volumes equivalentes. Esses deltas são um risco residual material para progressão e atividade regional. O relatório pareado completo está em [CSV](lot_e2_ml029_cpu_paired_2026-11-09-minus30-final.csv), [Markdown](lot_e2_ml029_cpu_paired_2026-11-09-minus30-final.md) e [JSON por seed](lot_e2_ml029_cpu_paired_2026-11-09-minus30-final.json). O resultado segue pendente de CR e decisão da coordenação; esta evidência não aprova o balanceamento por si só.

A chance continua usando cap 95%, classe/skills e os bônus reais; Comuns não recebem bônus de raridade. O teto de classe respeita o grupo: até +3 p.p. solo, +6 p.p. em dupla e +8 p.p. a partir de três integrantes; skills chegam a +15 p.p. Raridade pode acrescentar até +20 p.p. em conteúdo alto para elencos não Comuns. Equipamento acrescenta atributos ao poder efetivo, não p.p. direto. O CSV mede o teto de equipamento combinando a melhor peça permitida de cada slot, seu RNG máximo seedado, e os limites de classe, skill e raridade. Esse extremo pode chegar a 95% até no início; no jogo ele depende de obter várias peças fortes, então representa uma fronteira e não uma expectativa. O suprimento demonstra +5 p.p. nos cenários Common sem bônus enquanto há espaço; em qualquer combinação já limitada a 95%, não aumenta a chance. Esse é risco residual explícito para validação de builds equipadas.

A aplicação calcula apenas o snapshot de novas ofertas do tipo `contract` para templates que não sejam `gathering` ou `long_idle`; o valor do template/admin, requisitos, seed, ofertas já materializadas, snapshots, runs, coleta, missão longa, masmorra e chefe não são recalculados. Níveis fora de 1–350 e Ranks desconhecidos mantêm o poder configurado do template.

## Reproduzir

Com o ambiente desktop do projeto ativo, execute `python scripts/balance/study_ml029_contract_power.py`. O comando cria uma campanha descartável em pasta temporária para ler os templates atuais e gera os CSVs e este Markdown em `reports/`.
