# Auditoria condicional dos serviços de eventos Stage 5

Executada em 2026-10-29T13:43:40.695408+00:00 · N=1000 Vigílias · chave seed da campanha=2026102900 · números de ciclo 0–999.

Esta amostra executa os serviços reais de eventos em SQLite temporário. Todas as cinco regiões são mantidas artificialmente elegíveis em ameaça 85 e segurança 25. Os números estimam rolagens condicionais, não o tempo para atingir os limiares em campanha nova. A chave seed determina um UUID estável da campanha; o serviço de eventos deriva cada rolagem desse UUID, do número de ciclo, da região e da versão de regras.

| Evento | Oportunidades efetivamente roladas | Resultado | IC95% Wilson | Regra-alvo |
|---|---:|---:|---:|---:|
| Portal | 5000 região-Vigílias | 746 (14.92%) | 13.96–15.93% | 15% por região-ciclo |
| Rebelião | 4190 região-Vigílias elegíveis sem rebelião global ativa | 86 candidatas (2.05%) | 1.67–2.53% | 2.00% por região-ciclo |

Rebeliões ativadas: 81. Candidatas suprimidas pelo limite global: 5. O denominador de rebelião exclui ciclos em que uma rebelião ativa impediu a rolagem, conforme o serviço.

### Estabilidade por blocos cumulativos

| Ciclos | Portais no bloco | Portais acumulados / oportunidades (IC95%) | Rebeliões elegíveis no bloco | Candidatas no bloco | Rebeliões acumuladas / oportunidades (IC95%) |
|---:|---:|---:|---:|---:|---:|
| 0–99 | 82 | 82/500 (16.40%; 13.41–19.90%) | 410 | 9 | 9/410 (2.20%; 1.16–4.12%) |
| 100–199 | 67 | 149/1000 (14.90%; 12.83–17.24%) | 415 | 9 | 18/825 (2.18%; 1.38–3.42%) |
| 200–299 | 67 | 216/1500 (14.40%; 12.71–16.27%) | 425 | 8 | 26/1250 (2.08%; 1.42–3.03%) |
| 300–399 | 81 | 297/2000 (14.85%; 13.36–16.48%) | 420 | 7 | 33/1670 (1.98%; 1.41–2.76%) |
| 400–499 | 72 | 369/2500 (14.76%; 13.42–16.20%) | 450 | 5 | 38/2120 (1.79%; 1.31–2.45%) |
| 500–599 | 73 | 442/3000 (14.73%; 13.51–16.05%) | 450 | 6 | 44/2570 (1.71%; 1.28–2.29%) |
| 600–699 | 73 | 515/3500 (14.71%; 13.58–15.93%) | 440 | 7 | 51/3010 (1.69%; 1.29–2.22%) |
| 700–799 | 71 | 586/4000 (14.65%; 13.59–15.78%) | 390 | 12 | 63/3400 (1.85%; 1.45–2.36%) |
| 800–899 | 83 | 669/4500 (14.87%; 13.86–15.94%) | 420 | 9 | 72/3820 (1.88%; 1.50–2.37%) |
| 900–999 | 77 | 746/5000 (14.92%; 13.96–15.93%) | 370 | 14 | 86/4190 (2.05%; 1.67–2.53%) |

## Limites

Serviços reais create_cycle_portals/evaluate_open_rebellion em campanha SQLite temporária. As cinco regiões ficam fixas em ameaça 85/segurança 25 para cada Vigília rolada. Tempo de elegibilidade, ações do jogador, mudança dos limiares, resultados de CPU e participação/recompensas de evento ficam fora desta auditoria condicional.
A amostra não inclui resolução de portal, participação/decisão de rebelião, recompensas, progressão de ameaça/segurança, nem campanha econômica. Reutilize como validação condicional de serviço, não como estimativa de incidência média e não como playthrough.

## Reprodução

```powershell
.venv\Scripts\python.exe scripts\balance\audit_stage5_runtime_event_services.py --cycles 1000 --seed-start 2026102900
```
