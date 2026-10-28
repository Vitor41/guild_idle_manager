# Work 1 — simulação reproduzível de coleta e ausência

## Reprodução

A execução usa SQLite em memória, conteúdo mínimo versionado no harness e relógio/âncoras determinísticos. Nenhum save real é lido ou alterado.

```powershell
$env:APP_MODE='desktop'
.\.venv-desktop\Scripts\python.exe scripts\balance\simulate_work1_gathering.py
```

## Regra de bônus adotada neste gate

- Profissão compatível: **15 p.p.** por ciclo, o valor existente em `ProfessionTemplate.bonus_percent` e nas linhas seedadas de profissões (`app/seeds/massive_content.py`). Sem profissão compatível: **0 p.p.**. A unidade-base continua 1 por minuto.
- Ferramentas: **0 p.p. em Work 1**. O GDD as descreve como proposta/saída futura do Ferreiro; o modelo de item atual não identifica ferramentas de coleta por família nem fornece bônus balanceado. Adiar até haver modelo, custos/sinks e comparação reproduzível, sem atribuir valor especulativo.
- Construções: **0 p.p. em Work 1**. Armazém altera capacidade e seu bônus de materiais é aplicado a drops de missões/masmorras; Vigias altera chance de sucesso/drop de combate. Nenhum é bônus de chance de unidade extra de coleta designada. Adiar até decisão de balanceamento específica, sem reutilizar esses efeitos como coleta.
- A composição futura permanece soma em pontos percentuais, limitada a 45 p.p.; os testes existentes cobrem o teto. A base de 1 unidade e o ciclo de 60 segundos não mudam.
- Compatibilidade de construções: novos templates iniciais e Docas usam teto 100. Uma migration one-shot amplia apenas os nove `effect_type` base quando ainda estão exatamente no teto legado 50; caps diferentes de 50 e tipos customizados permanecem. Os seeds criam templates ausentes e não alteram o `max_level` de linhas existentes. Como não existe histórico de edição por linha, `50` em um template base é tratado como o valor padrão legado. O Alojamento continua em 20 vagas nos níveis 50–100.

## Resultados

`Ativos` aplica a regra atual de até três atividades por guilda (uma por família). Perfis com elenco de 5 ou 20 mercenários são medidos com três coletores ativos e os demais sem designação; não representam capacidade de coleta acima do limite atual.

| Elenco | Ativos | Profissão | Armazém | Ausência pedida | Tempo reconhecido | Ciclos | Produzido | Guardado | Excedente | Uso/capacidade | Pausou | Bônus por família | Madeira/minério/cristal comum | Cristal especial concedido |
|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|:---:|---|---:|---:|
| 1 | 1 | sem profissão | 0 | 5 min | 300 s | 5 | 5 | 5 | 0 | 5/1500 | não | wood:0pp | 5/0/0 | 0 |
| 1 | 1 | sem profissão | 0 | 6 h | 21600 s | 360 | 360 | 360 | 0 | 360/1500 | não | wood:0pp | 360/0/0 | 0 |
| 1 | 1 | sem profissão | 0 | 8 h | 28800 s | 480 | 480 | 480 | 0 | 480/1500 | não | wood:0pp | 480/0/0 | 1 |
| 1 | 1 | sem profissão | 0 | 24 h | 28800 s | 480 | 480 | 480 | 0 | 480/1500 | não | wood:0pp | 480/0/0 | 1 |
| 1 | 1 | sem profissão | 5 | 5 min | 300 s | 5 | 5 | 5 | 0 | 5/1750 | não | wood:0pp | 5/0/0 | 0 |
| 1 | 1 | sem profissão | 5 | 6 h | 21600 s | 360 | 360 | 360 | 0 | 360/1750 | não | wood:0pp | 360/0/0 | 0 |
| 1 | 1 | sem profissão | 5 | 8 h | 28800 s | 480 | 480 | 480 | 0 | 480/1750 | não | wood:0pp | 480/0/0 | 1 |
| 1 | 1 | sem profissão | 5 | 24 h | 28800 s | 480 | 480 | 480 | 0 | 480/1750 | não | wood:0pp | 480/0/0 | 1 |
| 1 | 1 | compatível | 0 | 5 min | 300 s | 5 | 7 | 7 | 0 | 7/1500 | não | wood:15pp | 7/0/0 | 0 |
| 1 | 1 | compatível | 0 | 6 h | 21600 s | 360 | 412 | 412 | 0 | 412/1500 | não | wood:15pp | 412/0/0 | 0 |
| 1 | 1 | compatível | 0 | 8 h | 28800 s | 480 | 547 | 547 | 0 | 547/1500 | não | wood:15pp | 547/0/0 | 1 |
| 1 | 1 | compatível | 0 | 24 h | 28800 s | 480 | 547 | 547 | 0 | 547/1500 | não | wood:15pp | 547/0/0 | 1 |
| 1 | 1 | compatível | 5 | 5 min | 300 s | 5 | 7 | 7 | 0 | 7/1750 | não | wood:15pp | 7/0/0 | 0 |
| 1 | 1 | compatível | 5 | 6 h | 21600 s | 360 | 412 | 412 | 0 | 412/1750 | não | wood:15pp | 412/0/0 | 0 |
| 1 | 1 | compatível | 5 | 8 h | 28800 s | 480 | 547 | 547 | 0 | 547/1750 | não | wood:15pp | 547/0/0 | 1 |
| 1 | 1 | compatível | 5 | 24 h | 28800 s | 480 | 547 | 547 | 0 | 547/1750 | não | wood:15pp | 547/0/0 | 1 |
| 3 | 3 | sem profissão | 0 | 5 min | 300 s | 15 | 15 | 15 | 0 | 15/1500 | não | wood:0pp, ore:0pp, leather:0pp | 5/5/0 | 0 |
| 3 | 3 | sem profissão | 0 | 6 h | 21600 s | 1080 | 1080 | 1080 | 0 | 1080/1500 | não | wood:0pp, ore:0pp, leather:0pp | 360/360/0 | 0 |
| 3 | 3 | sem profissão | 0 | 8 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1500 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 3 | 3 | sem profissão | 0 | 24 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1500 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 3 | 3 | sem profissão | 5 | 5 min | 300 s | 15 | 15 | 15 | 0 | 15/1750 | não | wood:0pp, ore:0pp, leather:0pp | 5/5/0 | 0 |
| 3 | 3 | sem profissão | 5 | 6 h | 21600 s | 1080 | 1080 | 1080 | 0 | 1080/1750 | não | wood:0pp, ore:0pp, leather:0pp | 360/360/0 | 0 |
| 3 | 3 | sem profissão | 5 | 8 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1750 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 3 | 3 | sem profissão | 5 | 24 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1750 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 3 | 3 | compatível | 0 | 5 min | 300 s | 15 | 16 | 16 | 0 | 16/1500 | não | wood:15pp, ore:15pp, leather:15pp | 5/5/0 | 0 |
| 3 | 3 | compatível | 0 | 6 h | 21600 s | 1080 | 1251 | 1251 | 0 | 1251/1500 | não | wood:15pp, ore:15pp, leather:15pp | 411/417/0 | 0 |
| 3 | 3 | compatível | 0 | 8 h | 28800 s | 1295 | 1500 | 1500 | 0 | 1500/1500 | sim | wood:15pp, ore:15pp, leather:15pp | 382/557/0 | 1 |
| 3 | 3 | compatível | 0 | 24 h | 28800 s | 1295 | 1500 | 1500 | 0 | 1500/1500 | sim | wood:15pp, ore:15pp, leather:15pp | 382/557/0 | 1 |
| 3 | 3 | compatível | 5 | 5 min | 300 s | 15 | 16 | 16 | 0 | 16/1750 | não | wood:15pp, ore:15pp, leather:15pp | 5/5/0 | 0 |
| 3 | 3 | compatível | 5 | 6 h | 21600 s | 1080 | 1251 | 1251 | 0 | 1251/1750 | não | wood:15pp, ore:15pp, leather:15pp | 411/417/0 | 0 |
| 3 | 3 | compatível | 5 | 8 h | 28800 s | 1440 | 1666 | 1666 | 0 | 1666/1750 | não | wood:15pp, ore:15pp, leather:15pp | 548/557/0 | 1 |
| 3 | 3 | compatível | 5 | 24 h | 28800 s | 1440 | 1666 | 1666 | 0 | 1666/1750 | não | wood:15pp, ore:15pp, leather:15pp | 548/557/0 | 1 |
| 5 | 3 | sem profissão | 0 | 5 min | 300 s | 15 | 15 | 15 | 0 | 15/1500 | não | wood:0pp, ore:0pp, leather:0pp | 5/5/0 | 0 |
| 5 | 3 | sem profissão | 0 | 6 h | 21600 s | 1080 | 1080 | 1080 | 0 | 1080/1500 | não | wood:0pp, ore:0pp, leather:0pp | 360/360/0 | 0 |
| 5 | 3 | sem profissão | 0 | 8 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1500 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 5 | 3 | sem profissão | 0 | 24 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1500 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 5 | 3 | sem profissão | 5 | 5 min | 300 s | 15 | 15 | 15 | 0 | 15/1750 | não | wood:0pp, ore:0pp, leather:0pp | 5/5/0 | 0 |
| 5 | 3 | sem profissão | 5 | 6 h | 21600 s | 1080 | 1080 | 1080 | 0 | 1080/1750 | não | wood:0pp, ore:0pp, leather:0pp | 360/360/0 | 0 |
| 5 | 3 | sem profissão | 5 | 8 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1750 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 5 | 3 | sem profissão | 5 | 24 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1750 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 5 | 3 | compatível | 0 | 5 min | 300 s | 15 | 17 | 17 | 0 | 17/1500 | não | wood:15pp, ore:15pp, leather:15pp | 5/5/0 | 0 |
| 5 | 3 | compatível | 0 | 6 h | 21600 s | 1080 | 1253 | 1253 | 0 | 1253/1500 | não | wood:15pp, ore:15pp, leather:15pp | 413/429/0 | 0 |
| 5 | 3 | compatível | 0 | 8 h | 28800 s | 1301 | 1500 | 1500 | 0 | 1500/1500 | sim | wood:15pp, ore:15pp, leather:15pp | 389/564/0 | 1 |
| 5 | 3 | compatível | 0 | 24 h | 28800 s | 1301 | 1500 | 1500 | 0 | 1500/1500 | sim | wood:15pp, ore:15pp, leather:15pp | 389/564/0 | 1 |
| 5 | 3 | compatível | 5 | 5 min | 300 s | 15 | 17 | 17 | 0 | 17/1750 | não | wood:15pp, ore:15pp, leather:15pp | 5/5/0 | 0 |
| 5 | 3 | compatível | 5 | 6 h | 21600 s | 1080 | 1253 | 1253 | 0 | 1253/1750 | não | wood:15pp, ore:15pp, leather:15pp | 413/429/0 | 0 |
| 5 | 3 | compatível | 5 | 8 h | 28800 s | 1440 | 1667 | 1667 | 0 | 1667/1750 | não | wood:15pp, ore:15pp, leather:15pp | 556/564/0 | 1 |
| 5 | 3 | compatível | 5 | 24 h | 28800 s | 1440 | 1667 | 1667 | 0 | 1667/1750 | não | wood:15pp, ore:15pp, leather:15pp | 556/564/0 | 1 |
| 20 | 3 | sem profissão | 0 | 5 min | 300 s | 15 | 15 | 15 | 0 | 15/1500 | não | wood:0pp, ore:0pp, leather:0pp | 5/5/0 | 0 |
| 20 | 3 | sem profissão | 0 | 6 h | 21600 s | 1080 | 1080 | 1080 | 0 | 1080/1500 | não | wood:0pp, ore:0pp, leather:0pp | 360/360/0 | 0 |
| 20 | 3 | sem profissão | 0 | 8 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1500 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 20 | 3 | sem profissão | 0 | 24 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1500 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 20 | 3 | sem profissão | 5 | 5 min | 300 s | 15 | 15 | 15 | 0 | 15/1750 | não | wood:0pp, ore:0pp, leather:0pp | 5/5/0 | 0 |
| 20 | 3 | sem profissão | 5 | 6 h | 21600 s | 1080 | 1080 | 1080 | 0 | 1080/1750 | não | wood:0pp, ore:0pp, leather:0pp | 360/360/0 | 0 |
| 20 | 3 | sem profissão | 5 | 8 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1750 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 20 | 3 | sem profissão | 5 | 24 h | 28800 s | 1440 | 1440 | 1440 | 0 | 1440/1750 | não | wood:0pp, ore:0pp, leather:0pp | 480/480/0 | 1 |
| 20 | 3 | compatível | 0 | 5 min | 300 s | 15 | 16 | 16 | 0 | 16/1500 | não | wood:15pp, ore:15pp, leather:15pp | 5/5/0 | 0 |
| 20 | 3 | compatível | 0 | 6 h | 21600 s | 1080 | 1232 | 1232 | 0 | 1232/1500 | não | wood:15pp, ore:15pp, leather:15pp | 413/406/0 | 0 |
| 20 | 3 | compatível | 0 | 8 h | 28800 s | 1312 | 1500 | 1500 | 0 | 1500/1500 | sim | wood:15pp, ore:15pp, leather:15pp | 404/550/0 | 1 |
| 20 | 3 | compatível | 0 | 24 h | 28800 s | 1312 | 1500 | 1500 | 0 | 1500/1500 | sim | wood:15pp, ore:15pp, leather:15pp | 404/550/0 | 1 |
| 20 | 3 | compatível | 5 | 5 min | 300 s | 15 | 16 | 16 | 0 | 16/1750 | não | wood:15pp, ore:15pp, leather:15pp | 5/5/0 | 0 |
| 20 | 3 | compatível | 5 | 6 h | 21600 s | 1080 | 1232 | 1232 | 0 | 1232/1750 | não | wood:15pp, ore:15pp, leather:15pp | 413/406/0 | 0 |
| 20 | 3 | compatível | 5 | 8 h | 28800 s | 1440 | 1644 | 1644 | 0 | 1644/1750 | não | wood:15pp, ore:15pp, leather:15pp | 548/550/0 | 1 |
| 20 | 3 | compatível | 5 | 24 h | 28800 s | 1440 | 1644 | 1644 | 0 | 1644/1750 | não | wood:15pp, ore:15pp, leather:15pp | 548/550/0 | 1 |

## Interpretação e limites

- As quatro durações passam pelo `ClockGuard` real. Com estamina inicial de 8 h: 5 min reconhece 300 s; 6 h reconhece 21.600 s; 8 h reconhece 28.800 s; 24 h reconhece somente 28.800 s. Os casos de 8 h e 24 h usam a mesma seed de ciclo e devem produzir o mesmo resultado.
- Os perfis 5/20 verificam o limite estrutural, não extrapolam cinco/vinte postos: só madeira, minério e couro têm atividades compatíveis no GDD e cada uma admite um trabalhador.
- O ensaio é uma trajetória determinística por combinação, não Monte Carlo. Serve para reproduzir o gate atual, validar teto/pausa e comparar entradas pareadas; não fecha a distribuição p50/p90 nem o balanceamento final. O GDD mantém os números como hipótese sujeita a simulação mais ampla.
- Madeira, minério e cristal comum passivos ficam em zero. A última coluna registra cristal especial novo: zero abaixo de 8 h e exatamente um em 8 h e 24 h (24 h é limitado a 8 h). Cada cenário reabre a campanha uma segunda vez antes do reconhecimento do relatório e valida que o grant e o relatório não duplicam. Os contadores `GuildResources` da penúltima coluna acompanham o inventário e incluem somente as atividades de coleta nesta fixture; o cristal especial fica fora da capacidade.
