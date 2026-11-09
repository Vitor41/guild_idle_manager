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
| 1 | E | 2 | solo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 36 | 95% | 59% | 64% | 77% | 95% | 95% |
| 1 | E | 2 | grupo_maximo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 36 | 95% | 85% | 90% | 95% | 95% | 95% |
| 1 | C | 2 | solo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 40 | 95% | 57% | 62% | 75% | 95% | 95% |
| 1 | C | 2 | grupo_maximo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 40 | 95% | 77% | 82% | 95% | 95% | 95% |
| 1 | S | 2 | solo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 56 | 95% | 51% | 56% | 69% | 95% | 95% |
| 1 | S | 2 | grupo_maximo | Conter Mapa Fragmentado em Arredores da Guilda | 10 | 56 | 95% | 65% | 70% | 88% | 95% | 95% |
| 5 | E | 2 | solo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 70 | 93% | 55% | 60% | 73% | 95% | 95% |
| 5 | E | 2 | grupo_maximo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 70 | 93% | 81% | 86% | 95% | 95% | 95% |
| 5 | C | 2 | solo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 77 | 93% | 53% | 58% | 71% | 95% | 95% |
| 5 | C | 2 | grupo_maximo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 77 | 93% | 73% | 78% | 95% | 95% | 95% |
| 5 | S | 2 | solo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 109 | 93% | 47% | 52% | 65% | 89% | 94% |
| 5 | S | 2 | grupo_maximo | Explorar Batedores Hostis em Bosque dos Sinos | 19 | 109 | 93% | 61% | 66% | 84% | 95% | 95% |
| 18 | E | 2 | solo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 186 | 95% | 57% | 62% | 75% | 89% | 94% |
| 18 | E | 2 | grupo_maximo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 186 | 95% | 83% | 88% | 95% | 95% | 95% |
| 18 | C | 2 | solo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 205 | 95% | 55% | 60% | 73% | 86% | 91% |
| 18 | C | 2 | grupo_maximo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 205 | 95% | 75% | 80% | 95% | 95% | 95% |
| 18 | S | 2 | solo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 289 | 95% | 49% | 54% | 67% | 76% | 81% |
| 18 | S | 2 | grupo_maximo | Localizar Suprimentos Perdidos em Bosque dos Sinos | 49 | 289 | 95% | 63% | 68% | 86% | 95% | 95% |
| 50 | E | 2 | solo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 462 | 87% | 49% | 54% | 67% | 81% | 86% |
| 50 | E | 2 | grupo_maximo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 462 | 87% | 75% | 80% | 95% | 95% | 95% |
| 50 | C | 2 | solo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 509 | 87% | 47% | 52% | 65% | 77% | 82% |
| 50 | C | 2 | grupo_maximo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 509 | 87% | 67% | 72% | 90% | 95% | 95% |
| 50 | S | 2 | solo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 717 | 87% | 41% | 46% | 59% | 68% | 73% |
| 50 | S | 2 | grupo_maximo | Recuperar Acampamento Inimigo em Mata das Corujas | 131 | 717 | 87% | 55% | 60% | 78% | 95% | 95% |
| 75 | E | 3 | solo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1017 | 79% | 33% | 38% | 51% | 66% | 71% |
| 75 | E | 3 | grupo_maximo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1017 | 79% | 67% | 72% | 90% | 95% | 95% |
| 75 | C | 3 | solo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1119 | 79% | 32% | 37% | 50% | 64% | 69% |
| 75 | C | 3 | grupo_maximo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1119 | 79% | 59% | 64% | 82% | 95% | 95% |
| 75 | S | 3 | solo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1577 | 79% | 28% | 33% | 46% | 57% | 62% |
| 75 | S | 3 | grupo_maximo | Explorar Peregrinos Cercados em Floresta Rubra | 196 | 1577 | 79% | 48% | 53% | 71% | 95% | 95% |
| 200 | E | 4 | solo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 3524 | 66% | 17% | 22% | 35% | 50% | 55% |
| 200 | E | 4 | grupo_maximo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 3524 | 66% | 54% | 59% | 77% | 95% | 95% |
| 200 | C | 4 | solo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 3877 | 66% | 16% | 21% | 34% | 49% | 54% |
| 200 | C | 4 | grupo_maximo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 3877 | 66% | 46% | 51% | 69% | 93% | 95% |
| 200 | S | 4 | solo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 5463 | 66% | 13% | 18% | 31% | 44% | 49% |
| 200 | S | 4 | grupo_maximo | Recuperar Relíquia Desaparecida em Ermos Imperiais | 499 | 5463 | 66% | 35% | 40% | 58% | 81% | 86% |
| 350 | E | 5 | solo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 7655 | 52% | 5% | 6% | 19% | 43% | 48% |
| 350 | E | 5 | grupo_maximo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 7655 | 52% | 40% | 45% | 63% | 91% | 95% |
| 350 | C | 5 | solo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 8421 | 52% | 5% | 5% | 18% | 42% | 47% |
| 350 | C | 5 | grupo_maximo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 8421 | 52% | 32% | 37% | 55% | 89% | 94% |
| 350 | S | 5 | solo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 11866 | 52% | 5% | 5% | 15% | 38% | 43% |
| 350 | S | 5 | grupo_maximo | Recuperar Criaturas da Névoa em Aurora Extinta | 868 | 11866 | 52% | 21% | 26% | 44% | 77% | 82% |

A comparação integral Rank E–S, nos dois conjuntos de multiplicadores, está em [CSV de cenários](lot_e2_ml029_scenarios_2026-11-08.csv). `grupo_max` é o tamanho máximo real do template amostrado; `solo` usa um mercenário e `grupo_maximo` usa esse número de Comuns. O baseline de cada nível é igual entre Ranks porque o template atual não escala poder pelo Rank.

## Multiplicadores avaliados

| Rank | PO inicial | Conservador escolhido para teste |
|:---:|---:|---:|
| E | 1.00 | 1.00 |
| D | 1.15 | 1.05 |
| C | 1.30 | 1.10 |
| B | 1.50 | 1.20 |
| A | 1.75 | 1.35 |
| S | 2.00 | 1.55 |

## Decisão e riscos

A variante conservadora foi escolhida para aplicação a novas ofertas de contratos regionais de combate. Em Rank C nível 18, ela recomenda `ceil(93 × 1,10 × 2) = 205`: chance Comum sem bônus fica 55% solo e 75% com dois; suprimento eleva para 60%/80%. O baseline de 49 levava os dois cenários a 95%, então +5 p.p. não tinha efeito. O conjunto PO inicial elevaria C18 a 242 e reduziria a chance do grupo a 69% (74% com suprimento), risco maior no começo. Em nível 1, Rank E mantém 36 de poder recomendado, dá 59% solo e 85% com dois Comuns, com suprimento 64%/90%; isso preserva uma entrada solo com risco e recompensa a formação completa. O Rank S completo no nível 1 dá 65% sem bônus, contra 59% com o conjunto PO inicial; no nível 350, grupo completo Rank S dá 21% contra 14% no conjunto inicial, antes de bônus/equipamento.

A chance continua usando cap 95%, classe/skills e os bônus reais; Comuns não recebem bônus de raridade. `get_party_chance_details()` acrescenta até +3 p.p. de classe para solo, até +8 p.p. no grupo e skills até +15 p.p.; raridade pode acrescentar até +20 p.p. em conteúdo de nível alto para elencos não Comuns. Equipamento acrescenta atributos ao poder efetivo, não p.p. direto. O CSV mede o teto de equipamento combinando a melhor peça permitida de cada slot, seu RNG máximo seedado, e os limites de classe, skill e raridade. Esse extremo pode chegar a 95% até no início; no jogo ele depende de obter várias peças fortes, então representa uma fronteira e não uma expectativa. O suprimento demonstra +5 p.p. nos cenários Common sem bônus enquanto há espaço; em qualquer combinação já limitada a 95%, não aumenta a chance. Esse é risco residual explícito para validação de builds equipadas.

A aplicação calcula apenas o snapshot de novas ofertas do tipo `contract` para templates que não sejam `gathering` ou `long_idle`; o valor do template/admin, requisitos, seed, ofertas já materializadas, snapshots, runs, coleta, missão longa, masmorra e chefe não são recalculados. Níveis fora de 1–350 e Ranks desconhecidos mantêm o poder configurado do template.

## Reproduzir

Com o ambiente desktop do projeto ativo, execute `python scripts/balance/study_ml029_contract_power.py`. O comando cria uma campanha descartável em pasta temporária para ler os templates atuais e gera os CSVs e este Markdown em `reports/`.
