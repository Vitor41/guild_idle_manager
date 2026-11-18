# ML049 - Alternativa antifarm TOP2 global

## Veredito para o proximo prototipo

**Rejeitar o cap por familia testado como candidato antifarm e levar TOP2 GLOBAL ao proximo prototipo descartavel**, ainda como hipotese, nao producao. A mudanca minima demonstrada e considerar os dois maiores sucessos elegiveis da guilda na Vigilia inteira, independentemente da familia, com pesos1 e0,5. Ranks E..S continuam1..6; vitoria global em evento continua3, com identidade global por seed/guilda/evento. Recompensas, ouro, XP e progressao nao foram alterados.

O teste demonstra eliminacao do farming concreto por multiplicar sucessos E entre familias: teto1,5 por Vigilia, contra5 de um sucesso A. **Nao demonstra eliminacao de todo farming, equilibrio probabilistico nem late game sustentavel.** O cap global cria desvantagens de variedade/eventos e preserva incentivos a tentativas extras para garantir os dois sucessos. Sao motivos para avaliar/rejeitar a candidata no prototipo, nao para publicar.

Esta alternativa substitui somente a regra de cap por familia da hipotese de pontuacao da secao4 do complemento anterior. Memoria EWMA8, identidade global, separacao de historico, reconhecimento sem poder e marco sem retrocredito permanecem hipoteses de prototipo. A aprovacao DA da DIRECAO UX, detalhada abaixo, nao aprova esta formula ou a economia.

## Preservacao e execucao

- Script novo: `scripts/balance/ml049_top2_study.py`. Resultados e manifests novos: `reports/ml049_top2_2026-11-17_results.json`, `_sources_start.json`, `_sources_end.json`.
- Os quatro bracos antigos foram reexecutados como controle e conferidos numericamente contra o resultado ja aprovado; os quatro correspondentes foram reotimizados sob TOP2 global. Nao houve nova coleta3x55, edicao de runtime/arquivos DEV, save real, instalacao, UI, sprite, commit, branch ou worktree.
- SQLite de fixture real descartavel:8 registros de campanha,8guildas,32ciclos,32planos,480ofertas. Integridade `ok`; chaves estrangeiras sem violacoes. Mesmos modelos/planejador/elegibilidade/recompensas/progressao reais do estudo controlado anterior.
- Antes/depois, todos os arquivos anteriores `reports/ml049_*` fora do prefixo novo foram hashados e assertados intactos. O JSON novo conserva esse manifesto em `protected_prior_artifacts_sha256`. Scripts anteriores tambem nao foram editados; hashes constam nos manifests de fonte.
- Ledger original3x55 preservado: `dd2b05d0f2010cbaca4cb9a8539036b137ce87f9ee9b8e39bca4abf1d043d4c9`.
- Fontes relevantes foram hashadas no inicio/fim; o resultado lista diferencas detectadas. Nao se afirma snapshot imutavel do checkout compartilhado entre as leituras.
- TEMP/TMP exclusivos no workspace, dotenv desativado e identidade WMI isolada em memoria antes de importar gameplay. Bancos temporarios removidos ao concluir; nenhum perfil pessoal acessado.

Comandos no checkout existente:

```powershell
..\.venv\Scripts\python.exe -B scripts/balance/ml049_top2_study.py --pure-only
..\.venv\Scripts\python.exe -B scripts/balance/ml049_top2_study.py
..\.venv\Scripts\python.exe -B scripts/balance/ml049_top2_study.py
```

`--pure-only` verifica invariantes, identidades, precisao e limites sem importar gameplay. A segunda execucao completa do mesmo script asserta igualdade de todo o payload dos cenarios com a anterior, normalizado em JSON. Os dois experimentos de pontuacao mantem identicas as ofertas/recompensas e a equipe inicial; so a escolha de acoes muda. A regra TOP2 vive apenas neste script de estudo.

Resultado final: asserts aprovados; repeticao identica;11artefatos anteriores com hashes intactos; nenhuma diferenca detectada nas fontes inicio/fim. Hashes SHA256 para fixar a revisao sem commit:

| Artefato novo | SHA256 |
| --- | --- |
| `scripts/balance/ml049_top2_study.py` | `abacbc99920a47abffc15d14c5797264bb32c566886764d525c258de818bab2d` |
| `reports/ml049_top2_2026-11-17_results.json` | `e48d28fe729bd44266ce9d3128c14ce6289174d17336991a4e5e0a05425fa039` |

## Comparacao controlada reotimizada

Mesmas15ofertas por braco/ciclo:10contratos E de30min/100XP/20ouro;2masmorras E e2chefes E de30min/10XP/2ouro;1contrato A de5h/100XP/5ouro. Uma equipe inicial igual, atributos/equipamento iguais,5h uteis apos1h de prioridade;4ciclos; sem contratacoes. O acesso as ofertas fica fixo apesar da progressao, como no ensaio anterior.

Para cada cap, `rank_optimal` enumera os subconjuntos viaveis de todas as ofertas; `farm_multi` faz o mesmo restrito a E de varias familias; `farm_one` restrito a contratos E. Objetivo: mais pontos, depois menos tempo, depois mais XP e IDs. A politica atual de XP/tempo continua usando a preferencia real do planejador e nao e rebatizada como otimizadora do ranking. O tempo que uma politica deixa ocioso continua disponivel, nao e removido da comparacao.

| Cap | Politica | Escolha por ciclo | Pontos em4ciclos | XP | Ouro | Ganho nivel | Acoes | Horas usadas /20 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Por familia | Atual XP/tempo | 10contratos E | 6 | 4000 | 800 | +2 | 40 | 20 |
| Por familia | Otima para pontos | 1contrato A | 20 | 400 | 20 | 0 | 4 | 20 |
| Por familia | Farming multifamilia | 2E de cada familia | 18 | 960 | 192 | 0 | 24 | 12 |
| Por familia | Farming monofamilia | 2contratos E | 6 | 800 | 160 | 0 | 8 | 4 |
| TOP2 global | Atual XP/tempo | 10contratos E | 6 | 4000 | 800 | +2 | 40 | 20 |
| TOP2 global | Otima para pontos | 1contrato A | 20 | 400 | 20 | 0 | 4 | 20 |
| TOP2 global | Farming multifamilia | 2contratos E | 6 | 800 | 160 | 0 | 8 | 4 |
| TOP2 global | Farming monofamilia | 2contratos E | 6 | 800 | 160 | 0 | 8 | 4 |

O multiplicador3x entre farming multifamilia e monofamilia desaparece:18->6, enquanto A permanece20. No braco multifamilia, a reotimizacao escolhe contratos porque, empatados os1,5pontos e o tempo, eles dao mais XP que masmorras/chefes E. A queda de960->800XP e192->160ouro decorre de executar menos acoes, **nao de nerf de recompensa**; cada resolucao continua pagando os valores identicos da oferta. Os saldos e niveis sao conciliados com o runtime real.

O problema economico anterior nao desapareceu: a politica A continua trocando4000XP/800ouro por400XP/20ouro para ganhar20 contra6pontos, com0 contra2niveis de ganho nesta fixture. E uma comparacao causal LOCAL de escolhas com demais entradas controladas, nao inferencia sobre a economia natural.

## Invariantes e identidade

Os asserts puros cobrem:

- Nenhum sucesso=0; um E=1;2,3,6,10,100,1000sucessos E=1,5, inclusive misturando contrato/masmorra/chefe.
- Duplicar cinco vezes o mesmo conjunto ou inverter sua ordem nao altera1,5. Adicionar duas familias **sinteticas de teste**, todas com rank E, tambem mantem1,5; nao adiciona conteudo ou fontes novas em producao.
- Um sucesso A=5; A mais sucessos E pode chegar a5,5, como determina o segundo peso0,5. O teto1,5 vale para conjuntos somente E, nao para misturas com ranks maiores ou eventos.
- Duas entradas da mesma vitoria sao3, nao4,5; a identidade persiste entre16->17->33, atraves de serializacao/retomada do conjunto visto, sem reset sazonal. Seed/guilda diferentes mantem dominios separados. Falha anterior nao consome a futura vitoria.
- Uma vitoria de evento excluida do TOP2 por dois S ainda e marcada como vista: nao pode ser reciclada na Vigilia seguinte. Evento sem ID e rejeitado.

Prova simples do teto E: cada valor elegivel e no maximo1, e so existem dois termos,1x e0,5x; logo P<=1+0,5=1,5 independentemente de quantidade, familia ou ordem. Um A isolado tem valor5. Esse e o farming concreto eliminado, nao uma prova de superioridade de A em qualquer risco, prazo ou disponibilidade.

## Novos problemas e risco probabilistico

**Variedade:** o cap deixa de premiar variar familias por si so. No teste, o farmer volta a contratos porque pagam mais XP. Duas atividades de rank alto podem dominar a disputa sem incentivar conteudo diverso. Acoes alem do TOP2 continuam com suas recompensas normais, mas nao aumentam a pontuacao daquela Vigilia.

**Eventos:** o valor3 compete pelas mesmas duas vagas. A5+evento3=6,5; S6+A5+evento3=8,5, igual a S+A sem evento. Dois S=9 e a vitoria de evento tem incremento0. Isso pode reduzir participacao em objetivos regionais depois de dois sucessos superiores e desalinhar beneficio coletivo e interesse de ranking. O limite nao e silenciosamente ampliado nem se adiciona bonus arbitrario para contornar o resultado. A semantica de contribuicao/vitoria global e a deduplicacao continuam as ja testadas; nao se presume que uma entrada bem-sucedida em portal seja vitoria global.

**Tempo:** dois E usam1h para1,5ponto; A usa5h para5. O A ganha na nota total dessa janela, mas E ainda tem mais pontos por hora e deixa4h para recompensas nao competitivas. Trocar as duracoes ou oportunidades pode trocar a escolha otima; nao se generaliza a partir destes templates artificiais.

**Forcado nao significa95% observado:** os snapshots tem chance95%, mas o RNG do ensaio devolve sempre sucesso, portanto a realizacao controlada e100% de sucessos. Nao houve amostragem de uma populacao natural95% nem estimativa de taxa de sucesso de guildas. Falhas naturais, adaptacao apos falha, acesso compartilhado e correlacao entre tentativas estao fora do ensaio causal.

Sensibilidade probabilistica SEPARADA, por algebra exata, supondo tentativas E Bernoulli independentes com p=0,95:

| Tentativas E | Pontos esperados do TOP2 global |
| ---: | ---: |
| 1 | 0,950000 |
| 2 | 1,448750 |
| 6 | 1,4999990859375 |
| 10 | 1,499999999990576171875 |

E[P]=Pr(N>=1)+0,5Pr(N>=2), sempre<=1,5. Mais tentativas continuam melhorando a **confiabilidade** de chegar ao teto, embora nao elevem o teto. Um A com p=0,95 tem4,75pontos esperados; com p=0,25 tem1,25, abaixo dos1,44875 de duas tentativas E a0,95. Esses p sao hipoteses de sensibilidade, nao medicoes do jogo nem novos pesos. Nenhuma conclusao economica ou de tempo e atribuida a essa conta abstrata.

## EWMA, precisao e alcance da evidencia

Manter como HIPOTESE M[t]=dM[t-1]+(1-d)P[t], d=2^(-1/8), sem reset; meia-vida8, nao "ultimas8Vigilias". Como ranks comuns sao no maximo6 e eventos3, o TOP2 global tem limite formal P<=9 (dois S), nao crescimento ilimitado. Com M0=0, M[t]<=9(1-d^t), e o limite assintotico e9. Isso e envelope matematico; a janela/equipe pode nem permitir dois S.

Teste puro com P=9 constante e Decimal28:

| Ciclo | M antes da quantizacao, mostrado em12casas | Q oficial6casas |
| ---: | ---: | ---: |
| 8 | 4,500000000000 | 4,500000 |
| 16 | 6,750000000000 | 6,750000 |
| 32 | 8,437500000000 | 8,437500 |
| 55 | 8,923323675047 | 8,923324 |

Asserts de ROUND_HALF_EVEN:1,0000005->1,000000;1,0000015->1,000002;0,0000004->Q0. Com P9 constante, **Q6 ja arredonda para9,000000 no ciclo193**, embora M ainda seja inferior ao limite matematico. Portanto, precisao finita e estrategias iguais podem gerar empates/um novo plato oficial; nao se promete que EWMA nunca sature visualmente. O193 vem de busca algebrica, nao de uma campanha simulada de193ciclos.

As campanhas reais continuam sendo APENAS3x55Vigilias, com os modelos e precisao originais. Seus2455pares-ciclo atuais,5245da temporada16 e1385do EWMA8 com cap POR FAMILIA permanecem intactos; **1385 nao e resultado do TOP2 global**. Temporada16 piorou. Esta rodada nova e somente4ciclos controlados por braco, invariantes e envelopes puros. Nao prova que o TOP2 global reduza empates ou sustente competicao no late game real.

## Parecer DA recebido e incorporado

**Atribuicao:** a coordenacao informou nesta conversa que a DA aprovou a direcao UX da secao4 para futuro prototipo, **nao a formula**, a economia ou a implementacao. Nao ha tela/sprite nesta entrega. Criterios finais dessa direcao registrados para o proximo ML:

1. Preservar a composicao tabular atual com guilda/composicao, pontuacao recente e a coluna **"Variação da pontuação"**, definida como Q[t]-Q[t-1]; nao usar seta de posicao para representar esse delta.
2. Q6 e a pontuacao oficial usada para ordem/empate; M mostrado em12casas no detalhe e **pre-quantizacao**, nao um segundo placar oficial. Explicar diferencas internas que pertencem ao mesmo quantum; nao aparentar igualdade sem explicacao.
3. Empate textual com posicoes1/1/3. Nome/ID so ordenam apresentacao. Top10 inclui todas as empatadas na nota de corte, mesmo que a lista tenha mais de dez linhas.
4. Distinguir **0,000000**, **"Abaixo da precisão"**, **"Dados pendentes"**, **"Histórico em formação"** e **"Estreia"** no delta. Lacuna de dados nao recebe zero; historico em formacao nao recebe retrocredito.
5. Historico separa vitalicio, ranking legado e honra a cada16Vigilias, **sem resetar M**. Reconhecimento apenas visual, sem poder/ouro/XP/materiais/chance/descontos/vagas. Marco inicial na proxima Vigilia completa, sem reconstruir pontuacao de atividades/eventos anteriores; historico existente preservado.
6. Gate responsivo em390px: numeros tabulares, sinal e seis casas juntos; nomes/badges longos e muitos empates nao podem sobrepor ou truncar o significado. M12 fica no detalhe, nao espremido como mais uma coluna da tabela.
7. Casos UX obrigatorios: nota sobe sem mudar posicao (ex.: Q2,000000->2,100000 mantendo colocacao); posicao sobe sem nota subir (ex.: Q2,000000->1,900000, mas a concorrente cai3,000000->1,800000). O delta de pontuacao permanece respectivamente+0,100000 e-0,100000; nao deve ser mostrado como variacao de posicao.

A coordenacao conduzira a revisao DA/apresentacao ao usuario; esta atribuicao nao substitui validacao economica. Para o proximo prototipo, preferir a candidata TOP2 global a candidata por familia, exigir testes de risco/variedade/eventos, precisao e oportunidades reais, e permitir rejeita-la se esses trade-offs forem ruins. **Nenhuma adocao em producao esta autorizada por este estudo.**
