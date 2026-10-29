# Work 2 — evidências da Vigília regional

## Escopo e método

Simulações determinísticas do serviço real, em bancos temporários, para três IDs de campanha distintos (101, 202 e 303) e horizontes de 100, 250 e 500 ciclos de seis horas (25, 62,5 e 125 dias). A análise de cadência também comparou 15%, 25% e 30% de probabilidade-base para cada oportunidade de ação. A distribuição sintética de ranks usa 10.000 ciclos por estágio (inicial, médio e avançado). Snapshots por rank são médias das ofertas reais materializadas no cenário de 100 ciclos.

Os valores de chance, nível recomendado, poder, duração e recompensa vêm dos templates ativos sem multiplicadores de rank. O rank rotula ofertas ordenadas por desafio dentro de contratos, masmorras e chefes. Os pesos e as chances internas não são mostrados na interface.

## Cadência e atividade CPU

Cada oportunidade de ação da CPU recebe uma decisão determinística, derivada da campanha, ciclo, rival, arquétipo e versão das regras. A probabilidade-base por oportunidade é 28% para fortes, 25% para médios e 22% para novos; a seed do rival varia a taxa em até 1 ponto percentual e o arquétipo em até 0,5 ponto. Um forte pode tentar duas ações por Vigília; médio e novo, uma. O elenco disponível continua limitando cada grupo e impedindo reutilizar o mesmo mercenário dentro do ciclo.

O sweep de uma campanha de calibração comparou as seguintes taxas. A chance menor produziu um portal elegível já no ciclo 99; a maior manteve todas as regiões mais seguras após 100 ciclos. A taxa intermediária foi escolhida porque conserva as regiões sem gatilhos durante os primeiros 25 dias e, no serviço completo, permite elegibilidade regional em horizontes posteriores.

| Base média | Taxas forte/média/nova | Ações em 100 ciclos | Portal elegível aos 100 | Rebelião elegível aos 100 | Ameaça final |
|---:|---:|---:|---:|---:|---:|
| 15% | 18% / 15% / 12% | 408 | 1 região, índice 99 | 0 regiões | 56,16–70,18 |
| 25% — selecionada | 28% / 25% / 22% | 676 | 0 regiões | 0 regiões | 30,56–49,48 |
| 30% | 33% / 30% / 27% | 806 | 0 regiões | 0 regiões | 23,70–39,70 |

Com a taxa selecionada, as três seeds acumularam as ações abaixo. “Ações/guilda/ciclo” inclui as até duas oportunidades dos fortes; a taxa efetiva menor dos novos também reflete o elenco de um mercenário e a elegibilidade de grupo das ofertas. Os recursos CPU nunca ficaram negativos. O GDD não define custo de manutenção para esses trabalhos, então nenhum custo econômico novo foi introduzido.

| Ciclos | Ações totais | Fortes: ações (taxa efetiva) | Médios: ações (taxa efetiva) | Novos: ações (taxa efetiva) | Baseline aplicado, ciclos-região |
|---:|---:|---:|---:|---:|---:|
| 100 | 1.889 | 833 (27,8%) | 372 (24,8%) | 684 (16,3%) | 359/1.500 |
| 250 | 4.703 | 2.106 (28,1%) | 928 (24,7%) | 1.669 (15,9%) | 918/3.750 |
| 500 | 9.334 | 4.183 (27,9%) | 1.882 (25,1%) | 3.269 (15,6%) | 1.850/7.500 |

Os elencos permaneceram nos tamanhos GDD de 5/3/1. Ao longo das três seeds, nível médio por perfil subiu de 20,07/13,87/1,69 em 100 ciclos para 32,13/33,13/3,93 em 500 ciclos (forte/médio/novo); não houve valores negativos de recurso.

## Pressão regional e eventos futuros

A deterioração sem ações permanece na referência confirmada do GDD: ameaça +1 e segurança −1 por Vigília de seis horas, somente quando não houve ação regional de CPU nem do jogador naquela Vigília. Sucessos e falhas contam igualmente como ações e suprimem o baseline. Na simulação sem CPU e sem jogador, todas as cinco regiões atingiram ameaça ≥70 no índice de ciclo 44 e ameaça ≥85/segurança ≤25 no índice 59. A execução repetida no mesmo instante não criou novos snapshots.

O conjunto de impacto regional permanece positivo, fracionário e monotônico por rank em sucesso e falha; o sinal é que muda: vitória aumenta segurança e reduz ameaça, derrota faz o inverso. A sequência E–S é 0,04; 0,06; 0,08; 0,10; 0,12; 0,14. O baseline confirmado não mudou. O bônus extra de segurança por sucesso foi removido; o arquétipo de segurança continua priorizando atividades defensivas.

Com a taxa selecionada, nenhuma das quinze regiões atingiu os limiares nos primeiros 100 ciclos. No ciclo 250, três regiões em duas campanhas já tinham elegibilidade de portal, e uma região em uma campanha tinha elegibilidade de rebelião. No ciclo 500, 14/15 regiões em 3/3 campanhas tinham atingido portal; 12/15 em 3/3 campanhas tinham atingido rebelião. O total acumulado de ciclos-regionais elegíveis foi 0/167/2.712 para portal e 0/93/1.705 para rebelião nos horizontes 100/250/500.

| Seed | Primeira elegibilidade de portal | Primeira elegibilidade de rebelião | Regiões portal/rebelião em 100 / 250 / 500 ciclos |
|---:|---|---|---|
| 101 | índice 116, Terras de Cinza | índice 157, Terras de Cinza | 0/0 · 2/1 · 4/4 |
| 202 | índice 245, Vale da Fronteira | índice 296, Terras de Cinza | 0/0 · 1/0 · 5/4 |
| 303 | índice 254, Picos do Norte | índice 296, Picos do Norte | 0/0 · 0/0 · 5/4 |

O primeiro índice conta a partir de zero; por exemplo, índice 116 é a 117ª Vigília processada. Esses números mostram que a cadência permite o período inicial de estabilização e depois deixa os gatilhos alcançáveis. São condições de limiar, não eventos iniciados: o Work 2 não executa a rolagem ou resolução dos portais nem rebeliões. O GDD não fixa chance numérica de rebelião.

Na verificação de catch-up, a seed 101 foi avançada em etapas (100, 250 e 500) e comparada com a mesma campanha criada do zero e avançada diretamente a 500. As 49.765 linhas canônicas de snapshots regionais, planos/resultados CPU, ofertas, estados e recursos foram idênticas. O calendário é determinístico nos dois caminhos.

O cenário sem guildas ativas é uma checagem de limite do calendário. O baseline +1/−1 só se aplica se nenhuma guilda CPU ou do jogador atuar na região naquela Vigília. Um teste separado aplica uma vitória de rank S do jogador (+0,14 segurança/−0,14 ameaça) e uma falha de rank C (−0,08 segurança/+0,08 ameaça), usando a mesma função de impacto que a CPU. Ambos contam como ações e impedem o baseline daquela Vigília.

## Distribuição e conteúdo por rank

O limite de três ofertas de contrato por rank foi respeitado em todos os ciclos simulados. A média de ofertas B–S por ciclo cresceu com a progressão: 2,47 no estágio inicial, 3,78 no médio e 5,18 no avançado. Foram 100.000 ciclos sintéticos por estágio contando os dez slots de contrato.

Uma verificação independente de 10.000 ciclos por tipo (100.000 contratos, 30.000 masmorras e 10.000 chefes) ordenou os templates por rank sem alterar seus campos. As médias de nível/poder recomendado não diminuíram ao subir de rank em nenhum tipo. Extremos E→S: contratos nível 1,00→2,00 e poder 10,01→14,07; masmorras nível 110,77→264,12 e poder 2.499,80→6.541,27; chefes nível 1,00→350,00 e poder 60→24.325. Para chefes, o rank sorteado seleciona o template no mesmo percentil de dificuldade do catálogo ordenado.

No estágio avançado, B–S representou 51,81% dos slots de contrato; no inicial, 24,68%. Para ofertas de chefe, a fração S foi 1,90%, 7,02% e 9,00% nos estágios inicial, médio e avançado. As ofertas mantêm suas estatísticas de template; por isso os relatórios de snapshots separam contratos, masmorras e chefes, cujas escalas de nível e recompensa são diferentes.

## Verificações executadas

- `tests.test_regional_cycle_service`: 3 testes passaram após a nova cadência; inclui distribuição de ranks, isolamento entre campanhas, retry/idempotência, catch-up, baseline sem ações, impacto fracionário CPU/jogador e snapshots congelados mesmo após alteração do template.
- Migração e ciclo de vida de save: 3 testes passaram; upgrade para a revisão regional, restauração de schema após migração falha, export/import/restore/backup/delete.
- A página regional foi renderizada no teste de template. Não houve abertura de executável ou teste visual interativo nesta validação.
