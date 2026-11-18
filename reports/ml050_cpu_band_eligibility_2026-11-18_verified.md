# ML-050 — elegibilidade CPU nos cortes de faixa após a contingência

32 casos determinísticos em um único save sintético reutilizado. Cada cenário cria e processa uma Vigília com serviços reais e reverte a transação ao final. Só um rival CPU fica ativo em cada caso para não haver competição entre guildas pelo mesmo quadro. Nenhuma rotina de elegibilidade ou ação foi substituída.

Os quatro estados CPU são exemplos semeados naturalmente: nova nível 1 na região de estágio 1; média nível 2 no estágio 1; média nível 3 no estágio 3; forte nível 5 no estágio 5. ‘Elegível’ chama o mesmo helper de seleção de equipe do planner e aplica duração, poderes, funções, equipamento e requisito de guilda. Ações elegíveis são contadas na primeira passagem do planner, antes de resultados/hiring mudarem o estado; ações são todos os inícios reais gravados no plano após resolver uma Vigília. As colunas de elegibilidade e início separam as ofertas públicas da contingência interna. O wrapper retorna o valor real do helper sem alterá-lo.

| Guilda jogador | Faixa contrato | Perfil CPU | Região CPU | Nível guilda CPU antes → depois | Elenco ativo antes → depois | Contratos públicos elegíveis | Masmorras públicas elegíveis | Chefes públicos elegíveis | Contingências elegíveis | Ações internas iniciadas | Contratos públicos iniciados | Masmorras públicas iniciadas | Chefes públicos iniciados | Ações totais | Motivo quando 0 |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 14 | 5–20 | new | vale-fronteira | 1 → 1 | 1 → 1 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | — |
| 14 | 5–20 | medium | vale-fronteira | 2 → 2 | 3 → 3 | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 5 | — |
| 14 | 5–20 | medium | costa-brumas | 3 → 3 | 3 → 3 | 10 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | — |
| 14 | 5–20 | strong | picos-norte | 5 → 6 | 5 → 5 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 10 | — |
| 15 | 10–25 | new | vale-fronteira | 1 → 1 | 1 → 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 15 | 10–25 | medium | vale-fronteira | 2 → 2 | 3 → 3 | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 3 | — |
| 15 | 10–25 | medium | costa-brumas | 3 → 4 | 3 → 3 | 10 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 5 | — |
| 15 | 10–25 | strong | picos-norte | 5 → 7 | 5 → 5 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 10 | — |
| 24 | 15–30 | new | vale-fronteira | 1 → 1 | 1 → 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 24 | 15–30 | medium | vale-fronteira | 2 → 2 | 3 → 3 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | — |
| 24 | 15–30 | medium | costa-brumas | 3 → 4 | 3 → 3 | 7 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 3 | — |
| 24 | 15–30 | strong | picos-norte | 5 → 7 | 5 → 5 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 10 | — |
| 25 | 20–35 | new | vale-fronteira | 1 → 1 | 1 → 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 25 | 20–35 | medium | vale-fronteira | 2 → 2 | 3 → 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 25 | 20–35 | medium | costa-brumas | 3 → 3 | 3 → 3 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | — |
| 25 | 20–35 | strong | picos-norte | 5 → 8 | 5 → 5 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 10 | — |
| 29 | 20–35 | new | vale-fronteira | 1 → 1 | 1 → 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 29 | 20–35 | medium | vale-fronteira | 2 → 2 | 3 → 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 29 | 20–35 | medium | costa-brumas | 3 → 3 | 3 → 3 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | — |
| 29 | 20–35 | strong | picos-norte | 5 → 8 | 5 → 5 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 10 | — |
| 30 | 25–40 | new | vale-fronteira | 1 → 1 | 1 → 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 30 | 25–40 | medium | vale-fronteira | 2 → 2 | 3 → 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 30 | 25–40 | medium | costa-brumas | 3 → 3 | 3 → 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 30 | 25–40 | strong | picos-norte | 5 → 9 | 5 → 5 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 10 | — |
| 49 | 40–55 | new | vale-fronteira | 1 → 1 | 1 → 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 49 | 40–55 | medium | vale-fronteira | 2 → 2 | 3 → 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 49 | 40–55 | medium | costa-brumas | 3 → 3 | 3 → 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 49 | 40–55 | strong | picos-norte | 5 → 5 | 5 → 5 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | — |
| 50 | 45–60 | new | vale-fronteira | 1 → 1 | 1 → 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 50 | 45–60 | medium | vale-fronteira | 2 → 3 | 3 → 3 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | — |
| 50 | 45–60 | medium | costa-brumas | 3 → 3 | 3 → 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |
| 50 | 45–60 | strong | picos-norte | 5 → 5 | 5 → 5 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | — |

Este ensaio mede permissões e atividade do planner em um ciclo por caso, não taxa de sucesso/recompensa nem progressão econômica de longo prazo. É evidência complementar à comparação pareada de 5 × 100 ciclos, que usa jogador nível 1 e por isso exercita apenas a faixa 1–10.
