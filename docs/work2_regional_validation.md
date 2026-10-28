# Work 2 — evidências da Vigília regional

## Escopo e método

Simulação determinística, isolada em banco temporário, com 100 ciclos de seis horas e seed fixa. Os pontos de 10 e 50 ciclos vêm da mesma execução, para mostrar a progressão acumulada. A distribuição sintética de ranks usa 10.000 ciclos por estágio (inicial, médio e avançado). Snapshots por rank são médias das ofertas reais materializadas no cenário de 100 ciclos.

Os valores de chance, nível recomendado, poder, duração e recompensa vêm dos templates ativos sem multiplicadores de rank. O rank rotula ofertas ordenadas por desafio dentro de contratos, masmorras e chefes. Os pesos e as chances internas não são mostrados na interface.

## Atividade CPU

| Ciclos | Ações | Sucessos | Taxa observada | Ouro | XP |
|---:|---:|---:|---:|---:|---:|
| 10 | 246 | 197 | 80,08% | 18.429 | 209.707 |
| 50 | 1.231 | 985 | 80,02% | 116.213 | 1.252.308 |
| 100 | 2.460 | 1.992 | 80,98% | 241.399 | 2.578.466 |

Em 100 ciclos, as decisões somaram chance esperada de 80,72% e tiveram 80,98% de sucesso observado. Por rank, a diferença entre taxa observada e esperada ficou entre −1,05 e +2,85 pontos percentuais; S teve 54 ações e E, 94, portanto esses extremos têm amostra pequena.

| Perfil | Guildas | Roster médio | Ações | Sucesso | Ouro/ação | Ouro/guilda | XP/guilda |
|---|---:|---:|---:|---:|---:|---:|---:|
| strong | 5 | 5 | 965 | 70,16% | 200,66 | 38.727 | 447.146 |
| medium | 5 | 3 | 500 | 81,40% | 59,89 | 5.989 | 52.476 |
| new | 14 | 1 | 995 | 91,26% | 17,91 | 1.273 | 5.740 |

As taxas brutas de sucesso não comparam força ou qualidade dos perfis: as guildas strong selecionam recompensas e conteúdo de maior desafio e usam equipes de cinco; as new têm um mercenário e concentram-se nas ofertas compatíveis. O critério relevante do sorteio é sucesso observado contra a chance calculada, não uma ordem de taxa por perfil. A simulação não implementa morte, baixa ou retirada de mercenários; os tamanhos de roster permaneceram 5/3/1.

Ao fim dos 100 ciclos, níveis médios foram 46,6 (strong), 17,4 (medium) e 3,86 (new). Influência média atingiu 100 nos perfis strong e medium e 71,43 no new. Reputação média foi 65,2, 79,6 e 71,21, respectivamente. Nenhuma das cinco regiões atingiu limiar de portal ou de rebelião enquanto a CPU atuou. Segurança terminou entre 62,84 e 92,04; ameaça, entre 0 e 12,16. Nenhum recurso CPU ficou negativo. O teste não considera uma região protegida por rivais como falha: o GDD prevê que um rival forte a acalme por um período.

## Pressão regional e eventos futuros

A deterioração sem ações permanece na referência confirmada do GDD: ameaça +1 e segurança −1 por Vigília de seis horas, somente quando não houve ação regional de CPU nem do jogador naquela Vigília. Atividades de ambos contam como ação e suprimem esse baseline, mesmo se falharem. Na simulação sem CPU e sem jogador, todas as cinco regiões atingiram ameaça ≥70 no ciclo 44 e ameaça ≥85/segurança ≤25 no ciclo 59. A execução repetida no mesmo instante não criou novos snapshots.

Para o cenário com CPU atuando e sem ações do jogador, a varredura usou os mesmos resultados determinísticos de 100 ciclos e testou cinco escalas de impacto (base e acréscimo por rank de 0,01 a 0,03). O conjunto selecionado usa impacto regional positivo e monotônico por rank em sucesso e falha; o sinal é que muda: vitória aumenta segurança e reduz ameaça, derrota faz o inverso. A sequência E–S é 0,04; 0,06; 0,08; 0,10; 0,12; 0,14. O bônus extra de segurança por sucesso foi removido; o arquétipo de segurança continua priorizando atividades defensivas.

Com impactos regionais, todas as escalas testadas mantiveram as cinco regiões abaixo dos limiares durante os 100 ciclos ativos da CPU: não houve ciclo elegível para portal ou rebelião. Essa estabilização resulta das ações observadas (2.460 ações, 1.992 sucessos e 468 falhas) e do efeito acumulado proporcional ao rank. Neste ritmo de jogo, os eventos são raros enquanto rivais continuam ativos; após cessarem todas as ações, o baseline confirmado pelo GDD volta a degradar as regiões. Sem ações, cada região soma 10,9 oportunidades teóricas de rolagem de portal do ciclo 44 ao 99; a probabilidade acumulada desse cálculo chega a 100% se toda oportunidade pudesse rolar. Isso não prevê portais iniciados: ocupação/supressão e resolução pertencem ao Work 3. A regra disponível não fixa uma chance numérica para a rolagem de rebelião; aqui a evidência é apenas elegibilidade pelo limiar.

Uma extensão executou o serviço real de Vigília por 250 e 500 ciclos (62,5 e 125 dias) em três campanhas determinísticas distintas, cada uma com cinco regiões e sem ações do jogador. Em todas as seis combinações de seed/horizonte, nenhuma região ficou elegível para portal (ameaça ≥70) ou rebelião (ameaça ≥85 e segurança ≤25): 0 ciclos-regionais elegíveis e 0/3 cenários atingidos em cada horizonte. Não há primeiro ciclo nem região elegível a reportar. Aos 250 ciclos, o pior caso entre as 15 regiões observadas terminou em segurança 70,34/ameaça 4,66; aos 500, o pior caso terminou em segurança 89,98/ameaça 0,20. Portanto, sob esse conjunto de rivais e sem pausas prolongadas nas ações regionais, os gatilhos são praticamente inalcançáveis no horizonte medido, e não apenas adiados por algumas semanas. Isso é uma conclusão limitada às três seeds e 125 dias, não uma prova sobre toda campanha possível. A medição observa elegibilidade pelos limiares; os sistemas de eventos do Work 3 seguem fora do escopo.

O cenário sem guildas ativas é uma checagem de limite do calendário. No cenário de jogo, CPU continua agindo quando o jogador não age. Um teste separado aplica uma vitória de rank S do jogador (+0,14 segurança/−0,14 ameaça) e uma falha de rank C (−0,08 segurança/+0,08 ameaça), usando a mesma função de impacto que a CPU. Ambos contam como ações e impedem o baseline daquela Vigília.

## Distribuição e conteúdo por rank

O limite de três ofertas de contrato por rank foi respeitado em todos os ciclos simulados. A média de ofertas B–S por ciclo cresceu com a progressão: 2,47 no estágio inicial, 3,78 no médio e 5,18 no avançado. Foram 100.000 ciclos sintéticos por estágio contando os dez slots de contrato.

Uma verificação independente de 10.000 ciclos por tipo (100.000 contratos, 30.000 masmorras e 10.000 chefes) ordenou os templates por rank sem alterar seus campos. As médias de nível/poder recomendado não diminuíram ao subir de rank em nenhum tipo. Extremos E→S: contratos nível 1,00→2,00 e poder 10,01→14,07; masmorras nível 110,77→264,12 e poder 2.499,80→6.541,27; chefes nível 1,00→350,00 e poder 60→24.325. Para chefes, o rank sorteado seleciona o template no mesmo percentil de dificuldade do catálogo ordenado.

No estágio avançado, B–S representou 51,81% dos slots de contrato; no inicial, 24,68%. Para ofertas de chefe, a fração S foi 1,90%, 7,02% e 9,00% nos estágios inicial, médio e avançado. As ofertas mantêm suas estatísticas de template; por isso os relatórios de snapshots separam contratos, masmorras e chefes, cujas escalas de nível e recompensa são diferentes.

## Verificações executadas

- `tests.test_regional_cycle_service`: 3 testes passaram; inclui 100 ciclos, distribuição de ranks, isolamento entre campanhas, retry/idempotência, catch-up, baseline sem ações, impacto fracionário CPU/jogador e snapshots congelados mesmo após alteração do template.
- Migração e ciclo de vida de save: 3 testes passaram; upgrade para a revisão regional, restauração de schema após migração falha, export/import/restore/backup/delete.
- A página regional foi renderizada no teste de template. Não houve abertura de executável ou teste visual interativo nesta validação.
