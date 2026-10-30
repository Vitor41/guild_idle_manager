# Stage 5 — curvas regionais e custo de catch-up

Data: 30/10/2026
Escopo: evidência de serviço com campanha SQLite descartável. Não executa pacote, GUI, instalador nem saves do usuário.

## Reexecução

1. Ative o ambiente `.venv-desktop`.
2. Rode `python -m unittest tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_seeded_cpu_simulation_100_cycles_and_campaign_isolation -v` para reproduzir curvas, CPU, pressão regional e snapshots por rank.
3. Rode `python scripts/balance/benchmark_stage5_regional_catchup.py` para medir `advance_regional_world` em uma campanha SQLite nova, até 1, 10, 50 e 100 Vigílias.

Os diagnósticos brutos de rank/template, replay regional e benchmark permanecem locais e não fazem parte deste commit. A campanha do benchmark foi criada dentro de `TemporaryDirectory` e o engine SQLite é descartado antes da limpeza.

## Curva de ofertas E–S

O estágio usado para as ofertas é `clamp(0.65 * (nível_da_guilda - 1) / 49 + 0.35 * poder_total / 30000, 0, 1)`. Os pesos de contrato interpolam entre E–S `[31, 27, 22, 12, 7, 1]` no início e `[8, 14, 23, 32, 18, 5]` no fim, arredondando e ajustando C para manter soma 100. Dungeon aplica acréscimo progressivo de 8% por índice de rank e normaliza; chefe multiplica o peso por `(índice + 1)^1.25` e normaliza. Contratos mantêm máximo de três espaços por rank.

O replay anterior rotulava um pool estreito de contratos de início (nível e requisito de mercenário até 2) e produzia ranks altos sobre missões triviais. O motivo era a combinação de limite de candidatos pela guilda e refinamento que igualava requisito mínimo ao nível recomendado. A regra agora aceita missões ativas padrão com nível recomendado e requisito mínimo até `max(20, nível da guilda, maior nível de mercenário não dispensado)`. O refinamento v3 preserva o requisito mínimo da faixa; o piso 20 mantém conteúdo aspiracional cedo, e o elenco real abre faixas de 51–350 sem deixar que a guilda, sozinha, as desbloqueie.

Em cada Vigília, o serviço escolhe dez templates do pool, rola os ranks separadamente e associa E–S em ordem crescente de desafio (nível, poder, requisito, chance, duração e recompensa). No nível 1, dois templates são reservados do subconjunto iniciável por um mercenário nível 1 sem edifícios; os ranks mais baixos continuam recebendo os desafios mais baixos. Poder recomendado afeta a chance, não bloqueia o início. A versão de regras passou a `vigilia-v4`; ofertas antigas continuam snapshots. Limites customizados de guilda/edifício e validação de início continuam valendo.

A correlação foi medida em cinco seeds (1.842, 5.271, 9.013, 17.021 e 42.893), com 2.000 painéis por seed em cada cenário: 10.000 painéis e 100.000 contratos por estágio. O early usa guilda/elenco 1/1, o mid 25/25 e o late 50/350. Tamanho e teto de cada pool:

| Estágio | Guilda | Elenco | Teto de desafio | Templates ativos elegíveis | Maior nível/pedido de mercenário |
|---|---:|---:|---:|---:|---:|
| Inicial | 1 | 1 | 20 | 140 | 20 / 1 |
| Médio | 25 | 25 | 25 | 170 | 25 / 21 |
| Guilda tardia, elenco em 50 | 50 | 50 | 50 | 310 | 50 / 21 |
| Tardio | 50 | 350 | 350 | 1.660 | 350 / 301 |

Média do nível recomendado, poder recomendado, nível mínimo de mercenário e nível mínimo de guilda por rank:

| Estágio | Rank | Nível | Poder | Mercenário mín. | Guilda mín. |
|---|:---:|---:|---:|---:|---:|
| Inicial | E | 3,34 | 15,42 | 1,00 | 1,01 |
| Inicial | D | 7,21 | 24,88 | 1,00 | 1,26 |
| Inicial | C | 11,80 | 36,48 | 1,00 | 1,89 |
| Inicial | B | 15,40 | 45,88 | 1,00 | 2,40 |
| Inicial | A | 17,37 | 51,13 | 1,00 | 2,69 |
| Inicial | S | 18,19 | 53,62 | 1,00 | 2,83 |
| Médio | E | 4,28 | 17,93 | 1,00 | 1,10 |
| Médio | D | 8,52 | 28,32 | 1,03 | 1,51 |
| Médio | C | 12,97 | 39,83 | 1,86 | 2,06 |
| Médio | B | 17,71 | 53,45 | 6,56 | 2,64 |
| Médio | A | 21,12 | 64,45 | 13,56 | 3,05 |
| Médio | S | 22,65 | 69,69 | 17,23 | 3,25 |
| Tardio | E | 34,16 | 97,47 | 22,26 | 4,73 |
| Tardio | D | 65,26 | 179,24 | 48,93 | 8,60 |
| Tardio | C | 122,52 | 329,48 | 100,40 | 15,75 |
| Tardio | B | 205,29 | 543,47 | 179,77 | 26,09 |
| Tardio | A | 277,30 | 729,04 | 251,60 | 35,10 |
| Tardio | S | 309,80 | 812,52 | 281,58 | 39,17 |

No cenário late, 51.909/51.909 ofertas B–S passaram o envelope de nível de elenco 350, guilda 50, nível de edifício ≤100 e grupo de até cinco; a regra individual de guilda/edifício ainda pode bloquear uma oferta se o save não cumprir seu requisito. No early, rank S teve nível médio 18,19 contra 3,34 para E; o requisito mínimo médio de mercenário segue em 1, enquanto guilda e edifício podem bloquear os ranks altos. Eles continuam aspiracionais e impossíveis no estado atual.

## Opções iniciáveis no início

Critério: guilda nível 1, primeiro mercenário nível 1 com poder base conservador 14, escritório de contratos 0, nenhum edifício, grupo de uma pessoa. Conta como iniciável se passa nível da guilda, nível mínimo do mercenário, edifício exigido e mínimo/máximo de grupo. Poder recomendado é relatado separadamente porque a regra só ajusta a chance de sucesso.

Nos mesmos cinco seeds e 10.000 painéis early, a reserva de duas ofertas iniciáveis funcionou em todos os painéis: média 3,985 iniciáveis em dez; 100% tiveram pelo menos duas. Médias por seed: 1.842 = 3,975; 5.271 = 3,962; 9.013 = 4,027; 17.021 = 3,970; 42.893 = 3,989. Com o poder inicial conservador, média de 1,328 oferta por painel também atingiu ou superou o poder recomendado. Isso é recomendação de sucesso, não requisito de início. O teste fixa como regressão piso de duas ofertas iniciáveis em cada painel.

Para saves existentes, a ativação continua fazendo upgrade aditivo de catálogo e não chama `run_progression_refinement`; templates existentes, requisitos de guilda/mercenário customizados e snapshots não são recalibrados. A fixture v2→v3 agora verifica ambos os requisitos admin e confirma que uma linha de conteúdo ausente é reinserida com o gate original da faixa. Não há backfill dos mínimos inflados por refinamentos antigos, pois o catálogo não permite distinguir com segurança um valor administrado de outro gerado. A correção vale para campanhas novas e para templates efetivamente inseridos pela atualização.

Em 10.000 ciclos determinísticos por estágio (100.000 contratos por curva), as ofertas B–S ficaram em:

| Estágio | B–S por painel de 10 | Percentual |
|---|---:|---:|
| Inicial | 2,47 | 24,68% |
| Médio | 3,78 | 37,83% |
| Tardio | 5,18 | 51,81% |

A meta GDD de 5–6 ofertas B–S no late game foi atingida por essa curva sintética. A correlação agora liga rank e desafio e inclui conteúdo da faixa 301–350 quando o elenco chega lá. A amostra mede pool e associação, não a distribuição natural de níveis numa campanha real nem disponibilidade após requisitos personalizados do save.

## Impacto regional e eventos

O impacto atualmente aplicado por sucesso ou falha de atividade regional sobe por rank de E a S em `[0,04; 0,06; 0,08; 0,10; 0,12; 0,14]` pontos de segurança/ameaça. Uma execução determinística de 100 Vigílias com 25 guildas CPU/jogador materializou 601 ações, 363 sucessos (60,40%), 83.672 ouro e 932.761 XP. Nesse seed, os cinco estados terminaram entre 16,34–32,96 de segurança e 42,04–58,66 de ameaça; nenhuma região alcançou limiar de portal/rebelião. Os rivais fortes terminaram com nível/poder médios 30,0/215,0; médios 12,6/88,6; novos 2,79/16,5. Nenhum saldo de recurso CPU ficou negativo.

As alterações de reputação, influência e contribuição implementadas são: sucesso E–S concede `+1…+6` de reputação e influência e contribuição de `1…6`; falha concede `+1` influência, reduz reputação em `−1/−1/−1/−2/−2/−3` e grava contribuição `1`. Isso descreve regra de serviço e preservação no ledger, mas não define um alvo de progressão/ranking nem prova distribuição desejada entre campanhas.

O controle sem ações alcança elegibilidade de portal no ciclo 45 e de rebelião no ciclo 60, usando baseline +1 ameaça/−1 segurança e a calmaria inicial já definida. No replay com CPU ativa, a faixa testada de escala de impacto 0,01–0,03 não tornou eventos elegíveis dentro de 100 ciclos. São controles de um seed e não demonstram prevalência, balanceamento da chance de 2% de rebelião, nem participação do jogador. O prazo de portal permanece correndo offline conforme decisão confirmada; sua resolução/recompensa pela campanha continua fora deste replay.

## Orçamento observado de catch-up regional

Um seed fixo, banco SQLite temporário, cinco regiões e criação de 24 planos CPU por Vigília foram cronometrados dentro de `advance_regional_world`; migração e seed do conteúdo ficaram fora da medição.

| Vigílias novas na chamada | Tempo | Segundos por Vigília | Ofertas acumuladas | Ações CPU acumuladas |
|---:|---:|---:|---:|---:|
| 1 | 0,193 s | 0,193 s | 140 | 4 |
| 9 (até 10) | 0,796 s | 0,088 s | 770 | 65 |
| 40 (até 50) | 3,472 s | 0,087 s | 3.570 | 320 |
| 50 (até 100) | 4,593 s | 0,092 s | 7.070 | 663 |

No ensaio único, processar 100 Vigílias (25 dias) levou 9,05 s nas chamadas somadas, após a inicialização do banco. O ensaio não mede P95/P99, hardware mínimo, escrita/compactação/backup do save nem limite de experiência aceitável. Sem orçamento máximo aprovado, os números não fecham o requisito de CPU catch-up; dão um baseline repetível para comparar regressões.

### Repetição multiperfil de lote

Cinco campanhas fresh-save independentes mediram chamadas de 1, 10, 50 e 100 Vigílias (805 Vigílias no total). P50/P95 por chamada: **0,195/0,275 s**, **0,914/1,003 s**, **4,520/4,734 s** e **9,675/10,528 s**. Segundos por Vigília: P50/P95 **0,195/0,275**, **0,091/0,100**, **0,090/0,095** e **0,097/0,105**. Com N=5, P95/P99 repetem o máximo observado; não são estimativas de cauda de produção nem SLA. O ensaio continua somente regional/CPU com SQLite temporário, sem atividades do jogador, backup, restore, save completo ou hardware mínimo aprovado. O JSON bruto está preservado localmente e foi excluído deste commit.

## Decisões em aberto após a medição

- **Curva E–S:** fórmula e meta sintética estão medidas; aprovar/recalibrar o perfil natural e os requisitos de rank contra guildas realistas.
- **Magnitude regional:** a escada está implementada e monotônica; escolher magnitudes exige campanha pareada com participação humana/CPU e uma meta para tempo até portal/rebelião.
- **Loot de chefe:** o replay mede ranks e snapshots de ofertas, não tentativas/claims de chefes nem distribuição agregada de drops. Manter aberto.
- **CPU offline:** baseline regional multiperfil medido em cinco seeds e lotes de 1/10/50/100; definir orçamento por dispositivo e medir concorrência, save/backup e perfis com atividades do jogador.
- **Teto de construção:** o serviço usa teto 100 e há migration para templates built-in legados. Custos/marcos de oito edifícios no intervalo 51–100 estão cotados em [relatório dedicado](stage5_buildings_51_100_2026-10-30.md). O Alojamento libera a vaga 20 somente no nível 100; a curva é monotônica e a fixture confirma que mercenários existentes permanecem quando a capacidade recalculada fica abaixo do elenco. Acessibilidade financiada e fixture explícita de upgrade de save legado continuam pendentes.
- **Versão de catálogo:** fechada no nível de serviço/fixture. Saves novos gravam `PACK_VERSION=3`; ativação antiga faz backup, depois semeia apenas linhas ausentes e atualiza `CampaignMetadata.content_version`. Campos existentes de templates, profissões, mercantes e drops não são normalizados nem sobrescritos; pares de loot novos são criados somente para templates inseridos nesse seed, tanto para missão quanto masmorra, pois os serviços resolvem loot pela tabela atual. Desativação de missões legadas é default somente na inicialização de campanha nova; upgrades e ciclos futuros preservam `is_active`. Ofertas/ciclos materializados mantêm snapshots; ofertas/runs em andamento continuam utilizáveis. Fixture v2→v3 compara tabelas de loot de missão em andamento e dungeon existente, verifica drops para templates reinseridos e cobre customizações e flag manual sem oferta. Não valida atualização no pacote candidato nem em save real.

**Estado Stage 5: aberto.** As medições fecham lacunas de quantificação da curva sintética e acrescentam um custo-base de catch-up. Não aprovam equilíbrio econômico, elegibilidade natural/participação em eventos, loot agregado de chefe, compatibilidade da candidata nem UX instalada. Veja a [auditoria curta dos gates ainda abertos](stage5_open_gates_audit_2026-10-30.md) para evidência, fechamento possível na branch e o menor próximo replay.

## Replay de atualização de catálogo e regressão focada

O teste `tests.test_campaign_content_versioning` passou **2/2** em save SQLite temporário ([log](stage5_catalog_versioning_customization_tests_2026-10-30.txt)). Cobriu save novo com missões legadas default ocultas e upgrade v2→v3 com backup prévio, marcador/pack semeado, snapshots de oferta/ciclo preservados, customizações intactas, tabela de loot da missão em andamento e da dungeon existente sem alteração, novos drops nos templates reinseridos e flag manual preservada sem oferta ativa. Nenhum save do usuário foi aberto.

Após as correções de requisito mínimo e seleção de ofertas iniciais, passaram **59/59 testes focados em 246,483 s**: `tests.test_campaign_service`, `tests.test_campaign_content_versioning`, `tests.test_regional_cycle_service`, `tests.test_regional_event_service`, `tests.test_building_template_caps` e `tests.test_stage5_runtime_validation` ([log](stage5_catalog_full_focused_tests_2026-10-30.txt), [metadados](stage5_catalog_full_focused_tests_2026-10-30.meta.txt)). A simulação dentro do teste regional mede cinco seeds e afirma pelo menos duas ofertas iniciáveis em cada painel early.

## Regressão focada anterior ao upgrade

Após o benchmark, o comando abaixo passou **41/41 testes em 142,015 s**, incluindo curva/CPU regional, ciclo/catch-up, lifecycle e reward de eventos, teto de construção e integração de economia/dungeon.

```powershell
$env:APP_MODE='desktop'
$env:DATABASE_URL='sqlite://'
.\.venv-desktop\Scripts\python.exe -m unittest tests.test_regional_cycle_service tests.test_regional_event_service tests.test_building_template_caps tests.test_stage5_runtime_validation -v
```

Log anterior: [testes focados Stage 5](stage5_regional_open_criteria_focused_tests_2026-10-30.txt). A suíte geral desta rodada passou **191 testes em 806,064 s**, com 1 cenário opt-in ignorado e zero falhas/erros. Os três testes que executam o instalador foram excluídos antes da execução; nenhum Setup foi aberto. [Log da suíte](stage5_full_suite_no_installer_2026-10-30.txt).

## Atualização de jornadas e reconciliação — 30/10/2026

Amostra de serviços reais ampliada para cinco seeds por perfil (ativo, casual, offline, produtor e combate), em campanhas SQLite descartáveis de 365 dias. O [relatório consolidado](stage5_service_economy_365d_n5_2026-10-30.md) resume as 25 jornadas finais; os JSONs e ledger CSVs detalhados permanecem locais e não fazem parte deste commit. A primeira tentativa teve seis jornadas truncadas pelo teto antigo de 1.200 s; os checkpoints foram preservados e os seeds completos reexecutados com teto de 2.400 s. A seed ativa `2026110002` também foi reexecutada depois de corrigir a cotação obsoleta ao redirecionar contratação para `housing_21`. Cada seed entra uma única vez; o merger substitui a jornada e o ledger inteiros e não concatena as ações parciais.

A validação por seed confirma D365 e `full_horizon` em todas as jornadas, 365 linhas diárias por seed, sem erros, IDs de ação repetidos, dias faltantes ou resíduos não zero. A contagem final é 25 seeds e 9.125 linhas do ledger. O agregador bloqueia o relatório se qualquer dia divergir. Na seed ativa `2026110002`, um rollback global em tentativa opcional de compra apagava crédito passivo pendente nos dias 32/33; savepoints e transações sem commit foram adicionados às rotas opcionais de upgrade, Market e salvage. A recotação corrigida registra dois pré-checks insuficientes para `housing_21` em D32/D33 (2.650 ouro exigidos; 1.206/2.283 disponíveis; materiais suficientes); nenhum serviço foi chamado nesses bloqueios, e a compra foi recuperada em D34. O crédito passivo permanece e o resíduo diário é zero. Os testes do runner e runtime passaram 23/23.

Esta bateria é evidência de uma política explícita e de uma amostra N=5; não estima P95, estabilidade global, adoção humana ou ausência de softlock. Os gates de UX instalada/save-sentinela e de referência externa permanecem abertos. Stage 5 continua aberto.
