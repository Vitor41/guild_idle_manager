# ML-049 | Estudo de ranking competitivo

Esta etapa exploratória compara opções para o ranking da campanha solo contra guildas CPU. Foi complementada pelo [replay de três campanhas descartáveis](../reports/ml049_estudo_independente_2026-11-17.md), com várias sementes/perfis, saturação por guilda e economia/progressão observadas. O ML-049 permanece em revisão: os limites do estudo e os critérios completos precisam ser conferidos pelo CR antes de encerrar a entrega. Não altera a pontuação, a economia, o histórico nem o Guia do Jogo. Os parâmetros abaixo são hipóteses de teste, não regras aprovadas.

O [complemento controlado para o CR](../reports/ml049_complemento_cr_2026-11-17.md) acrescenta a correção da deduplicação entre ciclos, rebeliões e teto de vitórias, entrada tardia, pausa/retorno, repetição de ciclos e políticas que reagem à pontuação. Inclui uma hipótese concreta de transição e apresentação, alinhada à direção da DA. Os cenários controlados identificaram risco de farming em várias famílias e sacrifício de XP/ouro ao otimizar pontos; por isso **nenhuma fórmula experimental é recomendada para produção neste pacote**. O resultado do estudo orienta um próximo protótipo descartável, não uma mudança silenciosa no jogo.

## Diagnóstico e referências

- Hoje: `0,50 × influência + 0,25 × reputação + 0,25 × min(100, 10 × vitórias em eventos)`. Os dois primeiros eixos param em 100; sem vitórias, o teto combinado é 75. No empate, a ordem alfabética não indica desempenho diferente. Isso explica o platô observado na Vigília 51, sem provar que toda campanha satura no mesmo momento.
- [Guild Wars 2: PvP Leagues](https://www.guildwars2.com/en/news/introducing-pvp-leagues/) separa a posição da temporada de reconhecimento permanente. Para o GIM, isso inspira uma disputa periódica sem apagar o histórico da guilda, não a adoção de Elo ou de divisões.
- [Brawlhalla: Guild Missions and Battles](https://www.brawlhalla.com/news/the-attack-on-brawlhalla-crossover-event-begins-patch-10-01) apresenta objetivos de guilda e placares semanais. A hipótese para o GIM é usar objetivos compartilhados e rotativos, não exigir partidas entre jogadores.

## Comparação controlada

Mesmas 64 Vigílias sintéticas, 11 guildas iniciais, uma estreante na Vigília 45, 3.870 registros e 3.550 ações únicas. A entrada não usa aleatoriedade. Os modelos não escrevem em saves e não executam a economia do jogo.

- **Controle:** fórmula atual, duas casas decimais e desempate por nome. No replay, um sucesso fora de evento soma o valor do rank a influência e reputação, limitadas a 100; falha soma 1 a influência e reduz a reputação em `max(1, rank // 2)`; vitória em evento soma 1 ao contador. Essa é uma aproximação sintética dos eixos, não a simulação integral da campanha.
- **Pontuação experimental:** para cada guilda, Vigília e família (contrato, masmorra, chefe, evento), considerar até dois sucessos distintos; melhor vale 100%, segundo vale 50%. Ranks E a S valem 1 a 6; vitória em evento vale 3. Remover registros duplicados por guilda, Vigília e identidade da ação. Uma Vigília sem sucesso vale zero. Em eventual teste com dados de campanha, contar apenas uma vitória por guilda e evento, mesmo se houver várias atividades registradas para ele.
- **Temporada 16:** somar os pontos em blocos fixos 1–16, 17–32, 33–48 e 49–64. Zerar só a pontuação competitiva na virada; o histórico de conquistas fica separado.
- **Média com decaimento:** `M[t] = d × M[t-1] + (1-d) × pontos[t]`, com `d = 2^(-1/8)` e `M[0] = 0`. Arredondar só para classificar e usar o mesmo desempate do controle. Oito Vigílias sem pontuar reduzem a pontuação pela metade.

Para reproduzir a sequência: `C/D/B/V` identificam contrato, masmorra, chefe e vitória em evento; o número é o valor do rank ou do evento. Salvo indicação, as ações são sucessos e têm identidades distintas.

| Guilda | Ações na Vigília `t` |
| --- | --- |
| Alfa, Bravo | Cada uma: `C4 + D3`, sempre (empate intencional). |
| Cume | `C6 + D5 + B4` até `t=20`, mais `V3` em múltiplos de 4 dentro desse período; depois, nenhuma. |
| Delta | 40 ações `C1` diferentes, mais cinco cópias do primeiro registro por Vigília. |
| Eco, Forte, Giro | Eco: `C6 + D4` nas pares; Forte: `C3 + B2` e uma falha `C6` em múltiplos de 4; Giro: `C2 + D2 + D1`. |
| Halo, Iris | Halo: `C1` sempre; Iris: `C2` em múltiplos de 3. |
| Jade, Kilo | Jade: `C4` e `V3` em múltiplos de 4; Kilo: `D3` nas ímpares, `B3` nas pares. |
| Nova | Ausente até `t=44`; `C5 + D4` a partir de `t=45`. |

| Recorte | Controle | Temporada 16 | Decaimento 8 |
| --- | ---: | ---: | ---: |
| Delta (repetição fácil), Vigília 51 | 75,00 · 5ª | 4,50 · 9ª | 1,48 · 9ª |
| Cume (inativa), Vigílias 28 → 33 | 2ª → 2ª | 3ª → 10ª | 1ª → 7ª |
| Nova, virada da Vigília 48 → 49 | 11ª → 11ª | 8ª → 1ª | 8ª → 7ª |
| Nova, Vigília 64 | 9ª | 1ª | 1ª |
| Trocas de líder / entradas no Top 10, Vigílias 21–64 | 1 / 1 | 2 / 5 | 2 / 2 |
| Pares empatados acumulados, Vigílias 21–64 | 833 | 82 | 47 |

No controle, sete guildas empataram em 75 na Vigília 51. O limite por família reduziu 40 atividades fáceis e cinco duplicatas a 1,5 ponto por Vigília. Ainda existe risco de repetição distribuída: duas vitórias E em cada uma das três famílias comuns dão 4,5 pontos, quase o equivalente a um sucesso A. A estreante também era mais forte por Vigília (9 contra 7 de Alfa e Bravo); a virada não garante recuperar terreno para qualquer guilda nova.

### Definições das métricas

O intervalo 21–64 inclui a transição 20→21. Cada classificação inclui guildas inativas; Nova só existe a partir da Vigília 45. Ordenar por pontuação decrescente, depois nome sem distinguir maiúsculas/minúsculas. Controle e decaimento usam duas casas decimais na classificação, sem arredondar o estado interno do decaimento.

- **Entradas no Top 10:** somar o tamanho de `Top10[t] − Top10[t−1]` em cada transição. Inclui reentradas e estreia. Os totais 1/5/2 correspondem a 1/4/2 guildas distintas, não a cinco guildas distintas no modelo sazonal.
- **Pares empatados acumulados:** agrupar pela pontuação classificatória a cada Vigília, somar `n × (n−1) / 2` por grupo e acumular nos 44 ciclos. Inclui zero e guildas inativas; não inclui Nova antes de existir. A unidade é par de guildas por ciclo, não par distinto.
- **Troca de líder:** mudança de identidade da primeira colocada em relação ao ciclo anterior, mesmo se causada por desempate. A temporada permite que Cume, inativa, reentre no Top 10 com zero na virada por ordem alfabética. Mobilidade, isoladamente, não prova melhora competitiva.

As definições e a sequência acima foram incorporadas no script reproduzível `scripts/balance/ml049_replay_study.py`, com asserts e modo de reanálise do ledger sem importar gameplay. Relatórios agregados ML-045 não substituem essa evidência: não contêm a série de eixos por guilda nem um ledger identificado de resoluções para reaplicar as fórmulas sem novo sorteio. Os arquivos detalhados e as limitações do novo ledger estão no relatório complementar.

## Recomendação e critérios ainda pendentes

A hipótese inicial deste ensaio sintético era priorizar temporada de **16 Vigílias**. A [evidência posterior de campanhas descartáveis](../reports/ml049_estudo_independente_2026-11-17.md) contradiz essa preferência: em três sementes de 55 Vigílias, a temporada aumentou os pares empatados de 2.455 para 5.245, enquanto o decaimento reduziu para 1.385. Priorizar agora o decaimento como candidato a um próximo protótipo, sem aprovar fórmula ou parâmetros de produção. O relatório preserva ledger, hashes, reprodução e limitações; a análise independente do CR ainda é necessária. Mais mobilidade não prova justiça nem equilíbrio.

Isolar os números competitivos das métricas vitalícias. Não usar poder, ouro, nível da guilda ou volume bruto de ações como pontuação direta. Testar nível da guilda como indicador ou filtro de comparação, não como vantagem acumulativa. Não confundir economia observada no simulador com efeito causal de mudar os incentivos: o replay usa as mesmas ações e recompensas nos três modelos.

1. **Replay de campanha descartável, necessário para concluir ML-049:** repetir os mesmos logs de eventos entre modelos, com várias sementes, perfis CPU, várias fases de entrada, guildas de força igual e desigual, pausas, retornos, jogo offline e repetição fácil em uma ou várias famílias. Medir saturação de cada eixo por guilda, empates, mobilidade fora das viradas, contribuição por fonte e efeito da frequência de portais/rebeliões. Conferir que deduplicação e catch-up não duplicam pontos. Oportunidades das guildas CPU e da guilda jogável devem ser comparáveis ou a diferença precisa ser explícita. Avaliar impacto econômico e de progressão antes de recomendar regras finais.
2. **Pontuação e conteúdo (só após aprovação):** definir retorno decrescente, acesso equivalente a objetivos rotativos de contratos/masmorras/chefes e contribuições regionais; medir dificuldade, tempo e risco antes de atribuir pontos. Testar participação e sucesso em eventos sem premiar múltiplos registros do mesmo evento. Usar nível recomendado/rank como contexto, não como penalidade arbitrária. Separar prêmios cosméticos ou históricos de poder, materiais, ouro e XP para evitar vantagem crescente. Considerar faixas de desafio/divisões só se o replay mostrar que oponentes de estágios diferentes distorcem o resultado.
3. **Exibição e transição (só após aprovação):** definir desempates, visibilidade dos pontos e requisitos, fim de temporada, registro histórico e política de início para campanhas em andamento. Não apagar a classificação anterior, não reconstruir vitórias sem evidência e não atualizar Guia/Markdown para regras ainda não entregues.

**Limite da evidência:** este replay identifica diferenças entre fórmulas com entradas controladas. Não estima o equilíbrio do jogo real nem aprova mudança em produção. A próxima decisão é autorizar um protótipo em campanhas descartáveis, não trocar o ranking diretamente.

## Complementos controlados e veredito posterior

Os relatórios `reports/ml049_complemento_cr_2026-11-17.md` e `reports/ml049_top2_veredito_2026-11-17.md` complementam, sem substituir, o ledger original. Os ensaios cobrem vitórias globais de rebelião, contribuição, teto do eixo existente, entrada tardia, pausa/retorno e catch-up regional. Não equivalem à validação do aplicativo desktop offline. A deduplicação usa identidade global por campanha/semente, guilda e evento, inclusive entre ciclos.

O cap por família apresentou farming multifamília: 18 pontos contra 20 de atividades A no ensaio de quatro ciclos. A hipótese adicional de considerar os dois maiores sucessos globalmente, com pesos 1 e 0,5, reduziu o primeiro resultado a 6 pontos. O teto de atividades E é 1,5 por Vigília, independentemente de volume ou famílias. Esse resultado não redefine os números do replay original: os 1.385 pares empatados pertencem ao modelo anterior por família, não ao TOP2 global.

A recomendação para estudo futuro é prototipar decaimento com TOP2 global, rejeitando por ora o cap por família. Não adotar a fórmula neste pacote. Permanecem riscos explícitos de menor incentivo à variedade e a eventos, vantagem de tentativas extras para alcançar o teto e empate com precisão finita; o envelope constante arredonda ao teto oficial Q6 no ciclo 193. Não há promessa de ranking sem saturação ou equilíbrio de late game.

A DA aprovou direção de apresentação para esse futuro protótipo, não fórmula nem economia: empate compartilhado, Q6 oficial, detalhe M12, coluna “Variação da pontuação”, estados de dados distintos e histórico legado preservado. A transição proposta inicia na próxima Vigília completa sem retrocrédito. O estudo e seus complementos ainda dependem de revisão formal em SHA dedicado; nenhuma dessas regras foi aplicada ao ranking do jogo.
