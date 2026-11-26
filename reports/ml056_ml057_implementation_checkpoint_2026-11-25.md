# Checkpoint documental ML-052–057 — 2026-11-25

Branch única: `feature/anomalies-ui-audit`
Base do pacote: `986b6b7c885c3a2bc8564ebc61514c3e0099223e`
HEAD de referência após os gates e F34: `2bb187850bf66021c19e0a128c4103560db7a3fa`; o checkpoint anterior registrava `ed179b7cb75a736f7293eca616fd0787ee069f26`.

Este checkpoint registra os gates anteriores, os dois lotes finais autorizados e a evidência textual compartilhável. As especificações de aceite são `docs/art_direction/ML052_ML055_VISUAL_SPEC.md` e `docs/art_direction/ML056_ML057_COMPONENT_ACCEPTANCE.md`. O levantamento ML-053 é `reports/ml053_coverage_checkpoint_2026-11-24.md`. Relatórios DA de ML-052 e ML-055 foram sanitizados para remover caminhos de usuário e nomes de capturas; PNGs, JSONs de medição e harnesses permanecem locais e não fazem parte do Git.

## Gates concluídos e limites

| Item | Fonte fixada | Estado e limite |
| --- | --- | --- |
| ML-052 / F15 | CR/DA: `64d6d34f7f2482938fb304a5d6e60e5c93016210`; relatório textual sanitizado em `reports/ml052_da_64d6d34_2026-11-24.md` | Aprovado no escopo visual sintético. Cinco larguras, alvos de 40 px, teclado/toque/foco e modais/portal cobertos. A escala 200% foi reflow equivalente, não zoom nativo WebView2; sem aceite manual ou publicação. |
| ML-053 | `reports/ml053_coverage_checkpoint_2026-11-24.md` | Auditoria DA registrou 36 achados/oportunidades. Evidências privadas continuam locais; validação de estados que exigem mutação pertence a fixtures descartáveis. |
| ML-054 | CR: `4999670d79ec08d8573702a19e80eea5020a1e6e`; simulação textual `faefcd252f4cef87682328c5ddcfab6ec0e27818` | Núcleo aprovado pelo CR: migração/legado/retry e 45 testes, com oito cenários da simulação reproduzidos. +5 p.p. em cinco regiões foi sensibilidade, não campanha real com Exploradores só natais; ausência e CPU/combat/recompensas não foram simuladas por essa evidência. |
| ML-055 backend | CR: `043cb5eceac1bc160c76350cf3a4b628bac2f200` | Aprovado pelo CR, 36 testes independentes. Corrige efeitos antecipados/duplicados, prioridades de reserva e divergência entre diagnóstico e gerador. O aceite funcional não aprova sozinho a central visual. |
| ML-055 central | CR/DA: `5fe567968fb53803e3873b7bb5c68f94266b1fa6`; relatório DA `reports/ml055_da_5fe5679_2026-11-25.md` | CR repetiu 73 testes Python, 12 JavaScript e 1 smoke; DA fechou DA55-01–04 e R1/R2/R3F, incluindo indicador, participação, foco e expiração externa com contagens 0/0. ML-055 fechada no escopo dos relatórios; integração ML-056/057 e gate de publicação permanecem abertos. |
| ML-057 / F34 | CR/DA: `2bb187850bf66021c19e0a128c4103560db7a3fa`; relatório `reports/ml057_f34_2bb1878_2026-11-25.md` | F34 fechado por CR e DA: segurança do loader, inicialização após navegação parcial e busca encontrado/ausente/vazio via Enter/botão sem submit global. Os outros Fxx e ML-056 permanecem pendentes. |

Os relatórios DA originais de ML-052 (`reports/ml052_da_897fde9_2026-11-24.md`, baseline anterior) e ML-055 (`reports/ml055_da_4ff9aad_2026-11-24.md`, candidato não aprovado) ficam como histórico textual sanitizado. Nenhum deles deve ser lido como aceite do candidato atual.

## ML-055 central — matriz do DEV

| Critério | Implementação/cobertura no candidato | Limite do aceite atual |
| --- | --- | --- |
| CR indicador do menu | `app/services/navigation_work_status_service.py`; `tests/test_navigation_work_status.py`; `tests/js/navigation-work-status.test.mjs` | CR aprovou a elegibilidade real da equipe (composição/poder/equipamento), estado pronto com precedência, leitura sem mutação/RNG, token de revisão e atualização de eventos externos 0/0. |
| CR participação central | `app/templates/regional/events.html`, `app/templates/components/regional_offer_actions.html`, rotas regionais e smoke HTTP | CR confirmou decisão, preparo, início e reforço a partir de `/regional/events`, retorno allowlisted e regressões. Campanha descartável, sem perfil do jogador. |
| DA55-01–04 / F21 | `events.html`, `regional_event_history.html`, `regional_routes.py`, CSS e macros de histórico | DA fechou duas seções com históricos por contexto, alvos/foco, chance autoritativa e janela de entrada separada do prazo da equipe/estado de coleta. |
| DA55-R1/R2/R3F | CTA, links dos avisos, `main.js`, histórico de portais | DA fechou contraste do CTA, alvos secundários de 40 px, atualização card+indicador por polling e foco estável no summary, sem perda de seleção/contexto. |
| Convite sem aceite | `tests/test_desktop_http_smoke.py` | Fixture de convite realmente vencido: idade 14 h, prioridade/TTL encerrados e `expire_due_events` aplicado; aparece no histórico sem ações. Cenário é separado do evento aceito que continua em andamento. |

## Evidência automatizada de ML-055 central

- CR reproduziu no SHA `5fe567968fb53803e3873b7bb5c68f94266b1fa6`: 73 testes Python, 12 JavaScript e 1 smoke. O smoke cobre participação direta na central, portal natal em andamento/coleta, portal externo, convite expirado sem aceite e histórico legado.
- DA aprovou o reteste residual no mesmo SHA `5fe5679`: aguardo real de 22 s, atualização de card/indicador, expiração externa com contagens 0/0, retry após falha de GET, foco/seleção/contexto e critérios visuais anteriores. Artefatos de imagem e dados estruturados ficaram em armazenamento local privado e não foram versionados.
- `py_compile` dos módulos/arquivos de teste tocados e `git diff --check` — passaram.

Resultados sintéticos não equivalem à revisão DA em viewports/telas nem ao aceite manual do usuário. A matriz consolidada DA ainda deve aferir 390/980/1100/1101/1440 px, largura útil, estados e acessibilidade indicados nas especificações.

## Próximo lote ML-057 e cobertura integral

ML-057 segue autorizado com todos os Fxx de `docs/art_direction/ML056_ML057_COMPONENT_ACCEPTANCE.md`: F01–F07, F14, F16 modal/rolagem, F17, F19, F30–F31, F32 detalhe/navegação e F34–F36. ML-056 continua obrigatório, cobrindo F08–F13, F16 seleção/ações, F18, F20, F22–F29, F32 estados e F33. F15 é ML-052; F21 é ML-055 e não deve ser reimplementado como terceiro lote.

F34 foi reproduzido, corrigido e aprovado por CR e DA em etapas: ciclo de vida em `2c0612e3da7e11ae169c367f0bee915a36763af2`; loader seguro em `e59536237899a1aad9d4e82f47d263b6286ceda8`; submit global/local em `2bb187850bf66021c19e0a128c4103560db7a3fa`. A fixture integrada carrega os scripts reais após navegação parcial e testa encontrado/ausente/vazio por Enter e botão, sem segunda requisição, mantendo termo/primeiro match/foco. No SHA `2bb1878`, 22 testes Node focados passaram; `node --check` e `git diff --check` passaram. O CR repetiu 33 testes JS; a DA validou 12 combinações direto/parcial × Enter/botão × encontrado/ausente/vazio. Também passaram 39 testes Python no SHA-base `e595362`, antes do delta JS/template, sem atribuí-los a `2bb1878`. Limite: a integração automatizada é sintética/VM; não houve smoke desktop para esse delta. Continuar F01–F07, F14, F16 modal, F17, F19, F30–31, F32 navegação e F35–36, depois completar ML-056. Emitir matriz Fxx → componente/arquivo → teste/evidência/limite; preservar ML-055 aprovado e manter todo o pacote sem publicação.

## Preservação e publicação

Somente os relatórios textuais sanitizados e registros documentais aprovados serão adicionados ao checkpoint. Capturas privadas ou sintéticas, JSONs com caminhos locais, saves e dados de perfil não serão commitados. `scripts/balance/simulate_regional_cpu_campaigns.py` é alteração preexistente alheia e permanece fora do staging. Não foi executado build, instalação, push, PR, merge, tag ou release.
