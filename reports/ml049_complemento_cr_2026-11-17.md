# ML049 - Complemento controlado para CR

## Escopo e cobertura

Complementa `ml049_estudo_independente_2026-11-17.md`, sem refazer as campanhas aleatorias 3x55. Estas continuam validas e **temporada16 continua pior que o controle em empates**: 5245 contra 2455 pares-ciclo; EWMA8=1385, na precisao de duas casas usada naquele estudo. Nenhum resultado foi substituido por uma narrativa mais favoravel.

| Pedido | Evidencia entregue | Limite |
| --- | --- | --- |
| P2 dedup entre ciclos/temporadas/retomada | Regressao pura, estado serializado, replay sem snapshot antigo, `--reanalyze` | Nao implementa storage competitivo em producao |
| Rebeliao: participacao, vitoria global e teto10 | 13 eventos reais nos modelos SQLite, resolvedor publico de expiracao, 12 vitorias controladas | Nao mede frequencia natural nem comportamento |
| Estreante inserida tarde, atividade/pausa/retorno e oportunidades pareadas | Linha RegionalGuildState inserida no ciclo5, gemea pareada, planos/processamento reais, pausa7..9 e retorno10 | Fixture minima, nao campanha completa migrada/semeada |
| Catch-up repetido sem novo ponto | Reprocessamento de cada ciclo apos reload; lote7..10 repetido duas vezes; plano/estado/projecao iguais | Nucleo regional com ciclos materializados; nao fluxo UI/offline de sessao desktop |
| Farming multifamilia e reacao aos pontos | Quatro politicas, ofertas/equipe/tempo/recompensas iguais, planejador e progressao reais | Sucessos fixados, acesso congelado por quatro ciclos |
| Hipotese concreta e direcao DA | Especificacao abaixo com memoria, fontes, precisao, empate, zeros, reconhecimento, transicao e UX | Hipotese para proximo ML, sem runtime/UI/Guia alterados |

O conjunto solicitado de cenarios CONTROLADOS foi executado, sem impedimento de permissao ou harness. Isso completa esta rodada de evidencia para revisao; nao e autoaprovacao do CR nem aceite de uma nova regra em producao.

## P2 corrigido sem mudar o ledger

O problema era real: `seen` local por guilda/ciclo permitia que a mesma vitoria pontuasse novamente em outro ciclo. `replay()` agora filtra as vitorias no **ledger inteiro**, em ordem cronologica, pela identidade `(seed, guilda, evento)`, antes de projetar snapshots. A primeira vitoria confirmada consome essa identidade; participacao/falha anterior nao a consome. Virada de temporada nao limpa a identidade. Duas guildas ou duas seeds podem legitimamente usar o mesmo ID de evento em seus respectivos dominios.

`points()` tambem aceita um conjunto persistente de eventos vistos, para projecao incremental; a regressao serializa e restaura esse conjunto antes de simular retomada. O caminho normal `--reanalyze` le o ledger inteiro, portanto nao depende de cache de uma execucao anterior.

Asserts: vitoria no16; duplicatas no17,33,40; nenhum novo ponto na virada; somente decaimento posterior; falha no15 nao bloqueia sucesso no16; isolamento entre seeds/guildas; ordem invertida do arquivo; retomada com conjunto serializado; view do17 sem snapshot16 ainda nao pontua a duplicata porque a origem continua no ledger completo. Vitoria sem ID e rejeitada, nao agrupada em um evento nulo.

O ledger 3x55 permanece byte a byte com SHA256:

```text
dd2b05d0f2010cbaca4cb9a8539036b137ce87f9ee9b8e39bca4abf1d043d4c9
```

Hashes para fixar a revisao dos artefatos sem criar commit (SHA256):

| Artefato | Hash |
| --- | --- |
| `scripts/balance/ml049_replay_study.py` | `1424f802a8cd5627d0b40229a888fc579036b831ea77189115386e479cc75bc0` |
| `scripts/balance/ml049_controlled_study.py` | `e03549c737850ae1e1a133efeb65983aa704e92e8ab976dbc650d7ef2b09d343` |
| `reports/ml049_controlled_2026-11-17_results.json` | `1904d2dcc86c7cf67a2bb000b09f10ee3bb6598e3a4b9e7dc5891a0ed5e33216` |

`--reanalyze` voltou a produzir todas as metricas e classificacoes anteriores, com igualdade conferida: essa amostra nao tinha vitorias de rebeliao, logo a correcao nao muda seus numeros. O manifesto da coleta original permanece intacto; `analysis_revision` registra a revisao atual do script, sem fingir que ela foi a revisao usada na coleta.

## Fixtures SQLite e reproducao

Script novo: `scripts/balance/ml049_controlled_study.py`. Resultados auditaveis: `ml049_controlled_2026-11-17_results.json`, incluindo IDs de campanhas, guildas, eventos, atividades, ciclos, planos e ofertas, estados antes/depois, escolhas e rankings. Fontes: `_sources_start.json` e `_sources_end.json` do mesmo prefixo.

Um arquivo SQLite temporario real dentro de `reports/ml049_controlled_*`, com chaves estrangeiras ligadas, foi criado pelo metadata dos modelos existentes e descartado ao fim. Verificacoes: `foreign_key_check` sem linhas; `integrity_check=ok`. Linhas persistidas: **6 campanhas, 11 guildas, 28 ciclos, 53 planos, 288 ofertas, 13 eventos, 26 atividades de evento**. Esses seis registros de campanha sao fixtures pequenas, nao seis campanhas aleatorias longas.

Os servicos reais usados foram `_process_cycle`, `_cpu_plan_for_guild`, `_cpu_offer_party`, `_apply_cpu_xp` e `expire_due_events`/resolvedor de rebelioes. Intervencoes exclusivamente em memoria: RNG com resolucoes bem-sucedidas, contratacao desativada e geracao aleatoria de portais desativada. Nos bracos de politica, restringe-se o conjunto de acoes escolhido; elegibilidade, disponibilidade da equipe, prazo, recompensas e niveis continuam aplicados pelo planejador real. Nenhum arquivo do DEV foi editado.

Comandos no checkout existente, todos aprovados:

```powershell
..\.venv\Scripts\python.exe -B scripts/balance/ml049_replay_study.py --synthetic-only
..\.venv\Scripts\python.exe -B scripts/balance/ml049_replay_study.py --reanalyze
..\.venv\Scripts\python.exe -B scripts/balance/ml049_controlled_study.py
..\.venv\Scripts\python.exe -B scripts/balance/ml049_controlled_study.py
```

A segunda execucao do MESMO script compara e asserta igualdade de todo o payload dos cenarios com a anterior; o resultado registra `reproduction.scenario_payload_identical=true`. Uma verificacao intermediaria falhou por comparar chaves inteiras de scores com as strings lidas de JSON; a comparacao foi corrigida para normalizar a serializacao, sem mudar valores/cenarios. TEMP/TMP exclusivos, configuracao de banco inicial em memoria e dotenv desativado antes de importar gameplay; isolamento WMI em memoria. Sem UI, perfil pessoal, save real, instalacao, branch, worktree ou commit. A parte pura continua sem importar gameplay. Hashes de fonte no inicio/fim das execucoes controladas nao apresentaram diferencas detectadas; isso nao promete imutabilidade de um checkout compartilhado entre leituras.

## 1. Rebelioes e dez vitorias

Na primeira rebeliao, LocalSuccess completa uma atividade com sucesso, mas LocalFailure tem duas falhas: agregado1:2, derrota global. Ambos ficam com zero vitoria. Nas doze seguintes, LocalSuccess contribui3 sucessos e LocalFailure1 falha: agregado3:1, vitoria global. Pelo resolvedor atual, **ambos os contribuintes** recebem uma vitoria; NoContribution, participante sem atividade/contribuicao, nao recebe. O campo de sucesso do participante reflete o resultado global com contribuicao, nao a chance ou sucesso individual da atividade.

As duas guildas contribuintes terminam com12 vitorias cada, mas ha apenas **24 identidades competitivas** (12eventos x2guildas), nao26 por volume de atividades. Repetir a expiracao publica apos commit/reload nao aumenta esse total nem o contador.

Com I=R=100 fixados para isolar V, o controle passa de75 a77,5 com uma vitoria; a97,5 com nove; a100 com dez. A11a e12a mantem100. Portanto, a saturacao do terceiro eixo foi exercitada com estados reais em SQLite, sem alegar que ocorreria nessa cadencia em campanha natural. Nenhuma recompensa economica de evento foi inventada na fixture.

Risco observado: premiar contribuicao em vitoria global admite um participante que falhou localmente. Isso e diferente de AFK sem contribuicao e pode incentivar carona; a hipotese abaixo o assume explicitamente, e exige teste de abuso no proximo ML.

## 2. Estreante, pausa, retorno e catch-up

Active e Paused existem desde o ciclo1. Late e LateTwin **nao existem na tabela de guildas antes do5**, quando sao inseridas com XP0, nivel1 e sem pontuacao anterior. Nao sao apenas linhas sinteticas de ranking. A partir do5, as gemeas recebem os mesmos valores de oferta e membros iniciais iguais; IDs sao distintos e ficam no resultado. Cada ator tem uma arena isolada equivalente para nao disputar uma unica oferta com o outro. Isso demonstra oportunidades pareadas por construcao, nao paridade natural CPU/jogador num mundo compartilhado.

Uma oferta C por ciclo,7200s,400XP,20ouro; uma equipe de um membro; janela CPU normal apos1h. Paused fica inativa7..9 e retorna10. O processamento e o planejador sao reais; a agenda de atividade e injetada deliberadamente, nao comportamento espontaneo.

| Ator | Acoes | XP concedido | Ouro | Nivel final | XP residual da guilda | EWMA no12 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Active | 12 | 4800 | 240 | 4 | 30 | 1,94 |
| Paused | 9 | 3600 | 180 | 3 | 90 | 1,41 |
| Late | 8 | 3200 | 160 | 3 | 50 | 1,50 |
| LateTwin | 8 | 3200 | 160 | 3 | 50 | 1,50 |

Os valores EWMA desta evidencia usam as duas casas do replay original. Paused cai de1,22 no6 a0,94 no9 e volta a1,11 no10. Late estreia com0,25 no5, nao recebe os quatro ciclos anteriores, e nao alcanca Active ate12. As gemeas mantem estados/resultados iguais em todos os ciclos desde a entrada. Nenhuma promessa de recuperar lideranca.

Cada ciclo completo e chamado outra vez depois de reload; a quantidade de planos e todos os saldos/niveis permanecem iguais. Na volta10, o lote de ciclos7..10 e reprocessado duas vezes, tambem sem novo plano ou estado. Uma projecao com as mesmas resolucoes novamente entregues mantem exatamente os mesmos rankings. Trata-se do nucleo regional de catch-up de ciclos materializados; nao foi exercitado o servico de retorno de sessao desktop, notificacoes ou UI.

## 3. Politicas, farming e economia causal restrita

Mesmo conjunto de15 ofertas em cada braco e ciclo: dez contratos E de30min,100XP,20ouro; duas masmorras E e dois chefes E de30min,10XP,2ouro; um contrato A de5h,100XP,5ouro. Todos com chance snapshot95%, mesmos requisitos e uma equipe inicial identica, sem novas contratacoes. O RNG forca sucesso para isolar escolha, nao para estimar risco. Cada ciclo oferece5h uteis apos a prioridade do jogador; quatro ciclos, sem recalibrar acesso ou ofertas ao subir nivel.

`current_xp_rate` usa a preferencia real atual de XP esperado/tempo. Os demais enumeram subconjuntos que cabem na MESMA janela/equipe: `rank_optimal` maximiza pontos; `farm_multi` faz isso restrito aos ranks E nas tres familias; `farm_one` restrito a contratos E. Desempate do otimizador: menor tempo, maior XP, IDs. Parar quando o cap nao adiciona pontos e escolha de politica; tempo ocioso nao e removido do orcamento comparavel. Com estado anterior igual e d constante, maximizar pontos da Vigilia tambem maximiza seu incremento EWMA.

| Politica | Escolha por ciclo | Pontos4ciclos | XP | Ouro | Nivel final / ganho | Horas usadas em20 disponiveis |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Atual XP/tempo | 10 contratos E | 6 | 4000 | 800 | 3 / +2 | 20 |
| Reativa ao ranking | 1 contrato A | 20 | 400 | 20 | 1 / +0 | 20 |
| Farming multifamilia | 2E por familia | 18 | 960 | 192 | 1 / +0 | 12 |
| Farming monofamilia | 2 contratos E | 6 | 800 | 160 | 1 / +0 | 4 |

Saldos de XP/ouro conciliam com cada resolucao; niveis sao do `_apply_cpu_xp` real, nao uma formula de progressao inventada. Inicialmente todos os saldos e XP sao zero e nivel1; equipes, atributos e equipamento sao assertados iguais, ignorando somente IDs.

Aqui existe uma comparacao causal restrita: dado o controle das demais entradas, a politica que troca40 contratos por4 atividades A aumenta pontos6->20, mas reduz XP em90%, ouro em97,5% e ganho de nivel2->0. Farming em tres familias faz18 pontos contra6 na mesma familia, usando12 de20h. Os4,5 pontos de E por ciclo chegam a90% dos5 de A usando60% do tempo. E evidencia de risco de incentivo/farming, **nao aprovacao dos pesos** nem economia melhor.

Essa conclusao nao se transfere para sucesso natural, risco relativo, custos/loot reais de outros templates, disponibilidade regional compartilhada, contratacoes, eventos ou campanhas longas. Nao e um novo ensaio de equilibrio geral. O replay3x55 continua sendo somente comparacao de formulas sobre escolhas fixas; nao se atribui a ele este efeito economico.

## 4. Hipotese fechada para o proximo ML

**Nome proposto: Ranking Recente com meia-vida8.** Escolha de produto para prototipo descartavel, nao producao, sprite, Guia ou migracao entregue. A duracao do placar e continua: nao reseta a cada16. A temporada16 fica como comparador rejeitado nesta amostra por maior empate, nao escondida.

1. **Memoria:** M[t]=2^(-1/8)M[t-1]+(1-2^(-1/8))P[t], M inicial0. Uma Vigilia concluida sem sucesso elegivel usa P=0; oito sem pontuar deixam metade do estado anterior,16 deixam1/4,32 deixam1/16. Nao chamar de "ultimas8Vigilias": a cauda antiga persiste. Catch-up aplica cada ciclo faltante uma vez em ordem, nao uma bonificacao por login. Sem garantia de ultrapassar quem continua ativo.
2. **Fontes iniciais do prototipo:** contratos/masmorras/chefes com ranks E..S=1..6, melhores dois sucessos distintos de cada familia por ciclo valendo100% e50%; falha0. Rebeliao global vencida com contribuicao positiva de pelo menos uma atividade elegivel concluida concede3 **uma vez por evento/guilda**, mesmo se a atividade local falhou; participante sem contribuicao0. Portal nao e vitoria global e, nesta primeira hipotese, nao concede ponto competitivo; preserva suas recompensas e historico normais. Coleta, ouro, XP e nivel nao sao fontes de pontos. Esta escolha explicita evita rebatizar entrada de portal como vitoria, mas cria risco de incentivo assimetrico de conteudo. Nao aprovar esses pesos sem o teste de farming abaixo.
3. **Identidade:** persistir projecao separada com identidades de resolucao e de vitoria `(campanha,guilda,evento)` sem apagar na virada/reinicio; pontos so de registros confirmados. Nao inferir vitorias de numero de atividades. Reprocessar a mesma entrada nao altera pontos nem recompensas. O estudo nao implementa esse storage no runtime.
4. **Precisao:** para o proximo prototipo, Decimal com contexto28 e d calculado nesse contexto; acumular sem arredondar por ciclo. Pontuacao OFICIAL Q=quantizacao de M em6 casas, ROUND_HALF_EVEN; comparacao e exibicao usam a MESMA Q, seis casas fixas. Diferencas internas abaixo desse quantum sao empate oficial intencional, explicado no detalhe com M em12 casas e a regra de quantizacao. Esta proposta nao foi usada para recalcular os numeros de empate anteriores, que continuam em duas casas. Testar limites de arredondamento e comparar desempates em seis casas antes de aprovar.
5. **Empate:** Q igual implica posicao compartilhada, estilo1,1,3. Nome casefold e ID imutavel ordenam apenas a apresentacao, nao a colocacao nem premio. Top10 inclui todos empatados na nota de corte, podendo exceder dez linhas. Lider e conjunto de empatadas em1o, nao primeira alfabetica. O proximo teste mede mudanca do conjunto de lideres e entradas com esse corte; as metricas antigas continuam com as definicoes originais para nao fabricar melhora.
6. **Zeros e dados:** zero real exige M=0 e cobertura completa desde a inscricao; mostrar0,000000. Se M>0 mas Q=0, mostrar a indicacao "abaixo da precisao", com detalhe e empate oficial Q=0 explicado, sem chamar de ausencia de atividade. Falta de ledger/snapshot e "dados pendentes", com ultima Vigilia confirmada e sem colocacao corrente; nao preencher a lacuna com zero nem presumir derrota. Depois da reconciliacao, reprocessar cronologicamente. Primeiras oito Vigilias concluidas desde inscricao levam badge "historico em formacao" sem bonus, penalidade adicional ou retrocredito. Estreante nao e dado ausente.
7. **Reconhecimento:** a cada16Vigilias, guardar um quadro de honra cosmetico da classificacao oficial, incluindo empates, sem zerar M. Apenas registro/titulo visual local: **nenhum poder, ouro, XP, material, chance, desconto, vaga ou vantagem mecanica**. Historico de feitos e eixos vitalicios continua separado. O marco16 organiza reconhecimento; nao transforma EWMA em temporada16 nem elimina a cauda.
8. **Campanhas antigas:** adesao a partir da proxima Vigilia completa apos ativacao, todos com M0, mantendo campanha acessivel. Somente acoes iniciadas depois desse marco e eventos criados a partir dele sao elegiveis; atividades/eventos ja em andamento continuam recompensas/historico atuais, sem ponto retroativo. Nao reconstruir a EWMA a partir de I/R/V ou totais antigos. Preservar ranking legado e historico existentes, identificados pelo modelo anterior, sem apagar ou converter conquistas. Novas guildas inscritas depois comecam em0 no seu primeiro ciclo completo.
9. **UX conforme DA:** preservar a composicao tabular atual, com posicao, guilda/composicao, pontuacao recente e variacao desde a ultima Vigilia; historico em area separada. Variacao numerica=Q[t]-Q[t-1], para reconciliar com as seis casas exibidas; primeira linha temporal usa "estreia", lacuna usa "dados pendentes", nao delta0. Empate, zero real, abaixo da precisao, estreante e falta de dados tem estados textuais distintos. Detalhe explica meia-vida, cauda, contribuicoes e empate oficial. Sem promessa visual de recuperar lideranca, sem confundir ordem alfabetica com superioridade. DA detalhara direcao visual depois da validacao dessa especificacao; nenhum runtime/sprite foi criado.

## Riscos e gate proposto

- **Farming multifamilia nao resolvido:** a fixture demonstra4,5 pontos de E contra5 de A por menor tempo. No proximo ML, comparar esses pesos com retorno decrescente compartilhado entre familias e pontos por desafio/tempo/risco, mantendo o mesmo quadro de ofertas. Hipotese atual e candidata a reprovar esse gate, nao justificativa para publicar.
- **Carona em rebeliao:** contribuicao com falha local pode ganhar3. Testar participacao minima de uma atividade distinta e tentativas repetidas; rejeitar se incentivar falha trivial sustentada por terceiros. Nao alterar o criterio global silenciosamente.
- **Troca por economia:** politica reativa perdeu90%XP/97,5%ouro nesta fixture. O proximo ML deve medir a curva de sacrificio e escolhas sob probabilidades naturais, custos e acesso compartilhado. Nao compensar automaticamente com premio economico competitivo.
- **Vies de oportunidade:** arenas pareadas isolam a escolha, mas nao reproduzem disputa regional CPU/jogador. Exigir bracos com mesma disponibilidade real, ordem de acesso e eventos antes de calibracao final.
- **Memoria, precisao e exibicao:** EWMA pode conservar lideres fortes e caudas pequenas; seis casas reduzem aparentes empates mas nao garantem justica. Testar12casas internas vs6oficiais, zeros, dados incompletos e todos os empatados no corte Top10 com a DA.
- **Compatibilidade e produto:** o inicio sem retrocredito e comparavel entre inscritas no mesmo marco, mas pode frustrar veteranas. Explicar a separacao de historico; nao apagar o reconhecimento previo nem exigir save novo. Reconhecimento cosmetico por16 nao e autorizacao de migracao.

Proximo ML proposto: **prototipo descartavel do Ranking Recente**, com essa especificacao como hipotese, regressao persistente de identidades, testes de fronteira de precisao/empate, politica reativa/farming/participacao e validacao DA dos estados. Criterio minimo: sem dupla pontuacao em qualquer retomada, sem confundir zero/ausencia/estreia, historico preservado, paridade de oportunidades explicitada e risco de farming/economia resolvido ou motivo documentado para rejeitar a candidata. Ate esse gate, manter a formula atual em producao.
