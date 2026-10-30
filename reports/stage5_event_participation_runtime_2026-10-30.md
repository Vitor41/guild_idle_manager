# Participação em portais e rebelião por serviços reais — Stage 5

Data UTC: 2026-10-30T08:35:00.843955+00:00. Campanha e inventários em SQLite temporário; nenhum save real foi aberto.

A configuração financiada monta guilda nível 50, equipe cinco de nível 350 com papéis válidos, Tier 7 equipado, Exploradores 1 e poder acima do maior portal seedado. Ameaça/segurança são definidas para alcançar a elegibilidade. Os serviços de evento ainda usam suas probabilidades e template RNG sem patch. Os rolls de combate portal são fixos apenas para cobrir resultados success/failure; não são estimativa de taxa.

| Fluxo | Resultado | Evidência |
|---|---|---|
| Portal success | resolved | template Arven, o Mestre das Cinzas; equipe 5; sucesso True; claim repetido recusado True |
| Portal failure | resolved | template Arven, o Mestre das Cinzas; equipe 5; sucesso False; claim repetido recusado True |
| Portal expiry | expired | template natural expiry; equipe 0; sucesso —; claim repetido recusado — |
| Rebelião | decisão accept, evento resolved | aceitação registrada; contribuição 1; atividade resolved; claim repetido recusado True |

No cenário de expiração, o portal ficou sem entrada durante 6 h de catch-up offline; o prazo de 3 h venceu 3 h antes do retorno e a entrada após expirar foi recusada: expired, `entry_after_expiry_rejected=True`.

## Limites

A validação é de integração: prova que equipe elegível percorre start/claim e que recompensas não duplicam; não estima incidência, participação natural, balanceamento de loot nem acessibilidade fresh-save. Portal expira sem participante na terceira ramificação. A amostra de combate intencionalmente força success/failure para percorrer ambos os braços. O relatório econômico e de agregado de loot continuam separados.

Arquivo bruto: `stage5_event_participation_runtime_2026-10-30.json`.
