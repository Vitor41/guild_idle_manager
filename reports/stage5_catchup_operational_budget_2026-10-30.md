# Orçamento provisório de catch-up regional — Stage 5

## Critério técnico provisório

Para comparação de regressões na máquina deste replay, fixo **12 s como teto de medição para processar 100 Vigílias consecutivas** (25 dias simulados), incluindo CPU regional e materialização de ofertas. O orçamento é aprovado apenas como critério provisório desta branch: foi escolhido acima do máximo visto no lote medido, com a regra explícita `elapsed_seconds <= 12.0` por chamada de 100 ciclos. Não é SLA, não é compromisso por hardware e não inclui escrita/compactação/backup do save.

## Medição

30 campanhas fresh-save isoladas em SQLite temporário; cada campanha avançou cumulativamente 1, 10, 50 e 100 Vigílias em quatro chamadas. Foram 4.830 ciclos processados no total. Inicialização do banco e seed de catálogo ficam fora do tempo cronometrado; cada chamada cronometrada executa `advance_regional_world` e commit.

| Vigílias por chamada | P50 da chamada | P95 observado (N=30) | Máximo da amostra | Teto provisório | Resultado |
|---:|---:|---:|---:|---:|---|
| 1 | 0,2086 s | 0,3075 s | 0,3098 s | 0,35 s | passou |
| 10 | 0,9360 s | 1,0520 s | 1,2597 s | 1,20 s | P95 passou; máximo excedeu |
| 50 | 4,6796 s | 4,9664 s | 5,1657 s | 6,00 s | passou |
| 100 | 10,2042 s | 10,7418 s | 10,8184 s | 12,00 s | passou |

O critério de 12 s é o único gate de lote definido nesta rodada; os demais tetos ajudam a localizar regressões em tamanhos menores. O lote 10 excedeu 1,20 s uma vez (1,2597 s), embora seu P95 observado tenha ficado abaixo do teto. Não escondo esse máximo em uma média agregada.

## Limites

N=30 descreve esta máquina e esta amostra. Os P95 são percentis observados, não estimativas de cauda de produção. O benchmark mede somente ciclos regionais e ofertas com SQLite temporário; não contém atividades do jogador, navegação de UI, dispositivo mínimo, backup/restore ou save instalado. Os replays econômicos multi-perfil de 365 dias são um ensaio separado e não transformam esse benchmark regional numa medição multiperfil completa do catch-up offline.

Os resultados detalhados dos benchmarks N=30 e N=5 permanecem em JSON local e foram excluídos deste commit; os valores resumidos acima são a evidência versionada.
