# Validação limitada do ciclo de portal — 29/10/2026

- Estado: **stopped_no_eligible_home_portal_within_budget**
- Perfil/caminho/seed: `offline/roster_first/2026303000`
- Campanha: `f99255a5-1b90-55c4-baaa-ff20976e22bc`
- Tempo de campanha: 169.617s; dia do portal natal: não alcançado
- Coordenação das execuções: A execução local iniciada antes da chegada do resultado final também terminou em 157,989s enquanto a execução final de 169,617s era coordenada no fio de origem. Ambas usaram perfil/caminho/seed e limites idênticos; esta saída preserva a execução final e as duas não são amostras independentes. Nenhuma execução adicional foi iniciada depois disso.
- Checkpoint: `not taken: no active portal in the player's home region within the budget`
- Região/portal: `não houve portal natal elegível` / `—`
- Região natal: `vale-fronteira`; portais naturais no horizonte: 100

## Regras e escopo

Cada execução usa uma campanha fresh-save em SQLite temporário; o JSON publicado representa a execução final, limitada a 90 dias ou 180 segundos. O checkpoint ocorre somente após o serviço natural de ciclo apresentar um portal ativo da região natal. Nenhum threshold, seed de evento, rolagem de combate, preço ou regra foi forçado. Se o portal natal não surgir no teto, os ramos A e B não são criados; não existe snapshot de evento elegível para copiar.

## Evidência

- Síntese fiel do JSON: estado `stopped_no_eligible_home_portal_within_budget`, perfil `offline/roster_first`, seed `2026303000`, 100 portais naturais; região natal `vale-fronteira`.
- Portais observados por região: `{"bosque-ambar": 20, "costa-brumas": 22, "picos-norte": 22, "terras-cinza": 36}`.
- Portais observados por estado: `{"active": 1, "expired": 72, "resolved": 27}`.
- Ledger diário coletado (não usado como evidência econômica): `{"passive_offline": 24840, "missions": 62140, "dungeons": 3490, "market_sales": 2253, "salvage_fees": 2050, "building_and_hire_purchases": 23628, "observed_delta": 67045, "unattributed_residual": 0}`; resíduo não atribuído: `0`.
- Diagnóstico da região natal por ciclo: `{"cycles_observed": 303, "threat_eligible_cycles": 0, "rng_rolls": 0, "rng_accepted": 0, "rng_rejected": 0, "active_portal_blocked_cycles": 0, "reason_counts": {"threat_below_minimum": 303}, "max_threat": 26.1, "eligible_cycle_numbers": [], "all_observed_rolls_match_runtime": null}`.
- O JSON mantém cada ciclo com ameaça, segurança, influência, elegibilidade, chance (somente quando elegível), bloqueio, seed, rolagem determinística reproduzida e decisão; a reprodução usa o mesmo seed sem consumir nem alterar a rolagem do serviço.
- A/B e ledger de evento: `{"A_player_participation": "not run; eligibility precondition was not met", "B_offline_expiration": "not run; no eligible shared event snapshot existed", "event_reward_ledger": "not applicable; no player event activity was started"}`.
- Causa imediata confirmada: vale-fronteira começou com ameaça 25 e permaneceu abaixo do mínimo 70 em todos os 303 ciclos observados (mínima 19.42, máxima 26.1, final 25.66); por isso houve zero rolagens RNG e zero portais elegíveis. O requisito corresponde ao GDD §15. A causa exata da estabilidade baixa não pode ser atribuída a um rival sem o ledger de planos CPU por ciclo.

## Leitura estática das regras regionais

- Estado inicial por código: `{"threat": 25, "security": 50, "influence": 0}`. Rivais natais e cadência nominal: `[{"slot": 1, "profile": "strong", "archetype": "expansion", "configured_per_check_probability": 0.2832, "checks_per_vigil": 2, "initial_roster_size": 5}, {"slot": 2, "profile": "medium", "archetype": "security", "configured_per_check_probability": 0.252, "checks_per_vigil": 1, "initial_roster_size": 3}, {"slot": 3, "profile": "new", "archetype": "expansion", "configured_per_check_probability": 0.2196, "checks_per_vigil": 1, "initial_roster_size": 1}, {"slot": 4, "profile": "new", "archetype": "exploration", "configured_per_check_probability": 0.2138, "checks_per_vigil": 1, "initial_roster_size": 1}]`.
- Ameaça observada na trilha: `{"first_cycle": 24.82, "minimum": 19.42, "maximum": 26.1, "last_cycle": 25.66, "cycles": 303}`.
- As probabilidades configuradas produzem nominalmente `1.2518` verificações de atividade por Vigília e `0.7642` de chance de ao menos uma verificação; `Probabilidade nominal calculada das verificações independentes configuradas; não é a contagem observada de ações CPU. Ofertas, elegibilidade do grupo e resultados podem impedir que uma verificação vire ação.
- Regra observada no código: `ameaça +1/segurança -1 somente quando ações CPU e do jogador são zero naquela Vigília`; `cada sucesso/falha efetivo altera ameaça pelo impacto do rank (-/+0,04 a 0,14); qualquer ação CPU efetiva suprime o baseline`.
- Comparação com GDD §§13–15: O GDD §13 diz que o rival forte mantém a região calma por um período, mas não indefinidamente. As regras examinadas usam taxas fixas por perfil/arquétipo e não definem duração nem atenuação explícita do efeito estabilizador do rival forte.
- Limite de atribuição: O SQLite temporário foi removido e a trilha JSON não preserva cada plano/resultado CPU nem o marcador baseline_applied; as contribuições realizadas não podem ser atribuídas apenas ao rival forte.
- Proposta para revisão de design: decidir se “não indefinidamente” exige uma duração/atenuação explícita ou se o comportamento emergente atual é aceitável. Se for exigida uma subida garantida, aprovar a regra e uma validação temporal com ledger por Vigília (CPU solicitada/executada, rank, sucesso/falha e baseline) antes de qualquer alteração de produção. Nenhuma alteração de produção foi feita.

Os arquivos SQLite de execução ficaram em diretório temporário e foram removidos ao fim. Sem checkpoint elegível, não há hashes de snapshot nem operações/ledger dos ramos A/B; os resultados naturais e a trilha diagnóstica estão preservados no JSON. Esta validação não altera preços/regras, não é amostra estatística e não aprova Stage 5.
