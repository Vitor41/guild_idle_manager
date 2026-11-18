# ML049 - Evidencia independente de replay

Atualizacao de revisao: `ml049_complemento_cr_2026-11-17.md` corrige o P2 de deduplicacao entre ciclos/temporadas e acrescenta cenarios controlados em SQLite e uma hipotese de produto com direcao DA. O ledger e os resultados3x55 abaixo permanecem preservados; as limitacoes de ausencia de rebelioes nessa amostra nao foram apagadas.

## Resultado e decisao

Executadas **3 seeds x 55 Vigilias reais**, em SQLite descartavel, pelo `run_campaign` do harness existente `scripts/balance/simulate_regional_cpu_campaigns.py`. Nenhuma mudanca de ranking, runtime, teste existente, harness DEV, branch ou commit. Este complemento entrega dados para CR; nao declara aprovacao do CR nem encerra todos os criterios do ML049 guarda-chuva.

Conclusao cautelosa: **nao adotar temporada 16 diretamente**. Neste conjunto real, ela aumentou os pares empatados em todas as seeds. EWMA meia-vida 8 reduziu empates em todas, mas nao garante alternancia de lideranca: na seed 303 houve apenas uma troca entre Vigilias 21 e 55. Recomendo comparar os dois em um prototipo descartavel mais amplo, mantendo EWMA como candidato prioritario para reduzir platos, nao como regra aprovada. Mobilidade nao equivale a justica ou equilibrio.

## Isolamento e rastreabilidade

- Checkout existente: `C:\Users\vitor\Guild Idle Manager\App GIM`.
- Branch observada: `feature/vigilia-backlog-batch`; SHA inicio/fim: `96b780b6c4871e7ca48243afe01954986bb2fd60`.
- Checkout ja continha alteracoes do DEV e outros arquivos. Nenhuma foi revertida, escrita ou incluida em commit.
- 188 fontes Python/documento/harness hashadas no inicio e fim da coleta: **nenhuma diferenca detectada**. Isso nao transforma o checkout sujo em um snapshot Git imutavel nem exclui mudancas transitorias revertidas entre as duas leituras.
- Manifesta completos: `ml049_replay_2026-11-17_sources_start.json` e `_sources_end.json`.
- `regional_cycle_service.py`: `929277ba768ffcd9deeb4683fba6a888277af56c2ea391ab1589994c099eccb1`.
- Harness: `8704c732548a3d875cc5c4c8e867c3d3de5bb836d3d110ed6b2095c805675881`.
- `regional_event_service.py`: `473759727f709992080d3188f9538435e9fa05ccfe38fb749eca593510edaada`.
- Script na coleta: `f77c205c178666cf8a0d23541abaeb7ec114efbaeb4ca602fd2065a5d4ca390c`.
- Script apos correcao **somente da agregacao de XP do estudo**, inclusao de asserts puros e modo `--reanalyze`: `b12c389eaeb5c6f51c7396c1d0ffc42524fb12804c978f365cfa0942dd2309ea`. A revisao posterior esta registrada em `analysis_revision` no resultado. Nao se afirma identidade entre essa revisao e o script executado durante a coleta.
- TEMP/TMP exclusivos em diretorio temporario de estudo dentro de `reports`; os bancos foram removidos pelo contexto temporario ao terminar. Nenhum save real, perfil pessoal, UI ou dado privado lido. Nenhuma instalacao.
- `APP_MODE=desktop`, banco inicial em memoria e `PYTHON_DOTENV_DISABLED=1` antes de importar gameplay. Identidade de `platform.uname` isolada em memoria para evitar WMI. Nao houve fallback de campanha para engine em memoria; as tres campanhas foram em arquivos SQLite reais descartaveis.
- Fluxo local de AGENTS aplicado; adapter externo de pipeline nao usado, pois nao existe neste projeto.

## Comandos e verificacoes

Executados no checkout indicado, todos com retorno zero:

```powershell
..\.venv\Scripts\python.exe -B scripts/balance/ml049_replay_study.py --synthetic-only
..\.venv\Scripts\python.exe -B scripts/balance/ml049_replay_study.py
..\.venv\Scripts\python.exe -B scripts/balance/ml049_replay_study.py --reanalyze
..\.venv\Scripts\python.exe -B scripts/balance/ml049_replay_study.py --synthetic-only
```

O modo `--reanalyze` confere o hash existente, refaz os tres rankings, verifica igualdade das metricas e de todas as classificacoes, normalizando chaves JSON, e reconcilia a agregacao de XP. Nao importa gameplay nem executa sorteios. Um assert ad hoc inicial de igualdade dos rankings falhou porque chaves inteiras de scores tornam-se strings no JSON; a comparacao normalizada passou, sem mudar ledger ou valores.

Asserts adicionais executados em processo puro: nenhum modulo `app` importado, duplicar/reordenar registros nao muda pontos, ausencia/falha valem zero. Esses casos tambem estao persistidos no script. Assert por plano conciliou I/R/V/XP/nivel reconstruidos/capturados com o estado real final. Conferencia externa confirmou unicidade de `(seed, guild, activity)` e reproducao do ranking inteiro.

## Ledger congelado e metodo

`ml049_replay_2026-11-17_ledger.json`: **8.401 resolucoes, 3.960 planos e 165 snapshots de ciclo**, com 24 CPUs e uma guilda jogavel ociosa por campanha. Sao 72 CPUs observadas e tres controles jogaveis ociosos.

SHA256 do mesmo ledger usado pelos tres modelos:

```text
dd2b05d0f2010cbaca4cb9a8539036b137ce87f9ee9b8e39bca4abf1d043d4c9
```

Ordenacao: seed, ciclo, guilda, perfil, identidade de atividade, evento, familia, rank, sucesso. A identidade e `plan:<id>:action:<numero>`; os IDs pertencem somente aos bancos descartaveis. O campo `plan` permite recuperar ordem de execucao pelo numero da acao, independentemente da ordenacao lexical do arquivo.

- Rotulos 1..55 representam os ciclos processados 0..54 do servico mais um; o ciclo 55 aberto na borda nao e mais uma Vigilia completa.
- Hooks em memoria em `_cpu_plan_for_guild`, `_apply_cpu_xp`, `_process_cycle` e `_resolve_rebellion_summary`; nenhum arquivo desses servicos foi editado.
- Decisoes/resultados reais do plano fornecem familia/rank/sucesso/horario/ID. I/R por atividade sao reconstruidos com as mesmas regras do runtime e assertados contra o estado real ao terminar cada plano. V e observado. XP/nivel por atividade sao obtidos do hook real de aplicacao de XP.
- Ouro e XP concedidos constam por resolucao; saldos de recursos, contratacao e gasto de contratacao constam antes/depois de cada plano, **nao como saldos reais por atividade**. XP da guilda e residual apos subidas de nivel, nao XP vitalicio; por isso nivel acompanha antes/depois.
- Snapshots sao no fim de `_process_cycle`, antes da materializacao/consulta seguinte do quadro. Sao estados coerentes de fechamento, nao capturas da UI.
- Controle: eixos reais, pesos 50/25/25, arredondamento e desempate por nome do runtime. Experimentos: no maximo dois sucessos distintos por familia/ciclo, pesos 1 e 0,5, ranks E..S=1..6, vitoria confirmada em evento=3; temporada em blocos fixos de 16; EWMA d=2^(-1/8), sem arredondar estado interno.
- Sucesso isolado em portal **nao e convertido silenciosamente em `event_wins`**: o codigo atual incrementa esse contador em vitoria confirmada de rebeliao. Familia `portal` fica registrada mas nao pontua como vitoria confirmada no experimento conservador. Alterar essa semantica exige decisao de produto e outra analise. A deduplicacao de vitoria por evento e guilda tem assert sintetico; o hook real nao foi exercitado, pois nao houve rebeliao.
- O hash foi conferido antes/depois do replay e novamente na reanalise. O ledger nao foi alterado. Horarios absolutos de criacao/resolucao variam numa nova coleta; nao se promete hash identico em outra execucao com as mesmas seeds.

## Saturacao

Resultados por guilda, incluindo primeiro ciclo no teto, quantidade de ciclos no teto e valor final para cada eixo, estao em `guilds[].saturation` de `_results.json`.

| Eixo CPU | Atingiram teto ao menos uma vez | No teto ao final | Primeiro teto observado |
| --- | ---: | ---: | --- |
| Influencia 100 | 72/72 | 72/72 | ciclos 11..54 |
| Reputacao 100 | 37/72 | 26/72 | ciclos 16..55 |
| Vitorias 10 | 0/72 | 0/72 | nao observado |

Reputacao pode cair depois de saturar: primeiro teto nao significa permanencia. No fim, reputacao 100 ocorreu em 10/15 fortes, 10/15 medias e 6/42 novas; influencia 100 em todas. Na Vigilia 51, as seeds 301/302/303 tinham respectivamente **5/9/5 guildas empatadas em 75 com I=R=100 e V=0**. O caso da captura e reproduzido sem usar o save pessoal; nao se prova que a campanha pessoal tenha exatamente a mesma trajetoria.

## Empates e mobilidade

Classificacao global inclui todas as 25 guildas, inclusive a jogavel ociosa e CPUs sem acao. Pares empatados incluem zero. Entradas no Top10 sao entradas por transicao, incluindo reentradas, nao guildas distintas. Troca de lider pode ocorrer por desempate alfabetico. A primeira classificacao nao conta como transicao; os totais abaixo cobrem ciclos 1..55 e transicoes 1->2 ate 54->55.

| Seed final | Modelo | Pares-ciclo | Trocas lider | Entradas Top10 | Lider fora de virada | Top10 fora de virada |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 301 | Atual | 757 | 15 | 15 | 15 | 14 |
| 301 | Temporada16 | 1977 | 23 | 140 | 21 | 121 |
| 301 | EWMA8 | 488 | 25 | 145 | 23 | 136 |
| 302 | Atual | 956 | 10 | 29 | 10 | 27 |
| 302 | Temporada16 | 1673 | 21 | 128 | 18 | 108 |
| 302 | EWMA8 | 458 | 23 | 111 | 21 | 104 |
| 303 | Atual | 742 | 19 | 51 | 19 | 48 |
| 303 | Temporada16 | 1595 | 22 | 124 | 19 | 108 |
| 303 | EWMA8 | 439 | 4 | 104 | 4 | 98 |

Seed completa = 2026110301/302/303. Para todos os modelos, a coluna fora de virada exclui as mesmas transicoes para 17, 33 e 49, mesmo quando o modelo nao reseta.

Somando seeds: pares-ciclo **2455 / 5245 / 1385**, lider **44 / 66 / 52**, entradas **95 / 392 / 360** (atual/temporada/EWMA). No recorte tardio 21..55, incluindo 20->21: pares **1436 / 2962 / 241**, lider **20 / 44 / 26**, entradas **47 / 282 / 258**. Nao sao intervalos de confianca nem amostra suficiente para generalizacao.

O cap por familia reduz volume bruto, mas as ofertas compartilhadas e atividade concentrada deixam muitos zeros/valores iguais na temporada. Mais rotatividade pode ser oscilacao, reset ou desempate, nao necessariamente escolhas mais interessantes. As trajetorias completas estao em `_rankings.json`.

## Atividade, economia e progressao observadas

| Perfil | CPUs | Resolucoes | Ciclos com acao | Maior pausa sem acao | XP real concedido | Ouro bruto | Ouro contratacoes | Saldo ouro liquido | Nivel medio inicial -> final |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Forte | 15 | 1845 | 33,58% | 4 | 731704 | 52966 | 4042 | 30926 | 3,80 -> 15,93 |
| Media | 15 | 1761 | 24,00% | 4 | 499887 | 38812 | 3396 | 14673 | 2,80 -> 12,73 |
| Nova | 42 | 4795 | 23,42% | 8 | 985793 | 77579 | 8230 | 18084 | 1,83 -> 10,05 |

Percentual de atividade usa guilda-ciclo, com 55 ciclos por guilda. Pausa significa ausencia de acao registrada, nao ausencia voluntaria nem offline. A guilda jogavel esteve ociosa por desenho e nao entra nesta tabela. Todas as CPUs existem desde o inicio; perfil `new` nao e uma estreia tardia.

Niveis finais CPU: 8..20; ganhos de nivel por perfil: fortes 8..16, medias 7..13, novas 5..13. Totais: 5466 sucessos em 8401 resolucoes, **2217384 XP**, **169357 ouro bruto**, **15668 ouro gasto em contratacoes**, **63683 ouro liquido**. O saldo nao e simplesmente bruto menos contratacoes; ha outras movimentacoes/limites do servico. Nao atribuir o residual a um unico custo sem contabilidade mais fina.

XP real por resolucao e saldo liquido de XP do harness coincidiram: 2217384. Telemetria `plan.xp_earned` soma somente 1958363: ela nao acumula os 259021 XP de falhas que o runtime realmente aplica. `_results.json` conserva essa telemetria como `plan_xp_earned_telemetry` e usa as resolucoes para `gross_xp_party`. Isso e diagnostico de telemetria, nao alteracao de economia ou acusacao de perda de XP.

Familias: 8250 contratos, 55 masmorras, 89 chefes, 7 portais. Pontos experimentais antes de temporada/decaimento: contrato **5061**, masmorra **55,5**, chefe **75**, evento confirmado **0**. A oferta/estrategia continua dominada por contratos; o replay nao corrige oportunidades ou incentivos.

Cada seed abriu tres portais e nenhuma rebeliao. Entradas/sucessos em portais: 301=2/1, 302=1/0, 303=4/2. Assim, frequencia e contribuicao de rebelioes e saturacao do eixo de vitorias nao podem ser estimadas aqui. A abertura de nove portais nao implica nove oportunidades equivalentes para cada guilda.

**Nao ha impacto economico causal entre formulas medido.** Todos os rankings usam exatamente as mesmas acoes e recompensas. Dizer que a economia ficou igual entre modelos seria tautologico, nao prova de que guildas responderiam igualmente aos novos incentivos. A simulacao real mede a economia original sob a estrategia CPU existente.

## Replay sintetico e limites

Sequencia do documento reconstruida: 64 ciclos, 11 guildas iniciais, Nova no 45, 3870 registros/3550 identidades unicas. Asserts reproduzem, para 21..64, pares/lider/Top10: atual **833/1/1**, temporada **82/2/5**, EWMA **47/2/2**. Delta: 40 sucessos E e cinco duplicatas viram 1,5 ponto/ciclo. Cume inativa cai de 1a para 7a no EWMA entre 28 e 33; no controle permanece 2a. Nova, mais forte por ciclo, e 1a na temporada a partir de 49 e termina 1a no EWMA, mas somente 9a no controle. Alfa/Bravo sao de forca igual e empatam intencionalmente. Oito ciclos sem sucesso reduzem estado EWMA pela metade.

Isso verifica estreante, ausencia, igualdade/desigualdade de forca, spam e duplicatas **no modelo puro**. Nao exercita retomada offline/catch-up real, estrategia de retorno ou oportunidades reais de uma estreia. As identidades reais nao duplicaram; isso nao prova idempotencia do gameplay ao repetir uma chamada de catch-up. Tampouco testa campanha longa o bastante para dez vitorias, tiers altos ou varias fases de entrada real.

## Proximos MLs propostos, sem implementacao

1. **ML049-A - Contrato de pontuacao e objetivos**: decidir portal versus vitoria global, medir rank/tempo/risco e equivalencia CPU/jogador; repetir estudo com eventos suficientes, entradas tardias, pausas e catch-up real. Exigir uma contribuicao por evento/guilda e testes de replay de mesma resolucao. Nao premiar nivel, ouro ou volume bruto diretamente; nivel como contexto/filtro e hipotese, nao pontuacao.
2. **ML049-B - Prototipo competitivo descartavel**: comparar temporada16/EWMA8 com estrategias que reajam aos incentivos; medir economia/progressao pareadas, disponibilidade de familias e farming multifamilia. Aprovar limites apenas apos esse teste. Reconhecimento competitivo sem ouro/XP/poder como premio inicial para evitar realimentacao.
3. **ML049-C - Transicao, historico e UX**: especificar desempates, zeros, fim de temporada, visibilidade e inicio em campanhas existentes. Separar historico vitalicio de estado competitivo; nao apagar classificacao antiga nem reconstruir vitorias sem evidencias. DA/CR independentes antes de UI, Guia ou migracao. Sem bloqueio de abertura de campanhas antigas.
4. **ML de telemetria, se autorizada**: alinhar nome/semantica de `plan.xp_earned` com XP total ou explicitar sucesso/falha, adicionando reconciliacao. O estudo nao editou essa coleta do DEV.

O escopo concreto 3x55, ledger congelado, comparacao de formulas, saturacao por guilda e economia observada esta entregue. Os limites acima impedem promover esta evidencia a aprovacao de ranking definitivo ou fechamento automatico do guarda-chuva ML049. Fontes primarias externas ja verificadas permanecem no documento original; nenhum artigo foi copiado.
