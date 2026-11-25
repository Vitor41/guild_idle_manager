# Checkpoint documental ML-052–057 — 2026-11-25

Branch única: `feature/anomalies-ui-audit`
Base do pacote: `986b6b7c885c3a2bc8564ebc61514c3e0099223e`
HEAD no checkpoint: `ed179b7cb75a736f7293eca616fd0787ee069f26`

Este checkpoint registra os gates anteriores, os dois lotes finais autorizados e a evidência textual compartilhável. As especificações de aceite são `docs/art_direction/ML052_ML055_VISUAL_SPEC.md` e `docs/art_direction/ML056_ML057_COMPONENT_ACCEPTANCE.md`. O levantamento ML-053 é `reports/ml053_coverage_checkpoint_2026-11-24.md`. Relatórios DA de ML-052 e ML-055 foram sanitizados para remover caminhos de usuário e nomes de capturas; PNGs, JSONs de medição e harnesses permanecem locais e não fazem parte do Git.

## Gates concluídos e limites

| Item | Fonte fixada | Estado e limite |
| --- | --- | --- |
| ML-052 / F15 | CR/DA: `64d6d34f7f2482938fb304a5d6e60e5c93016210`; relatório textual sanitizado em `reports/ml052_da_64d6d34_2026-11-24.md` | Aprovado no escopo visual sintético. Cinco larguras, alvos de 40 px, teclado/toque/foco e modais/portal cobertos. A escala 200% foi reflow equivalente, não zoom nativo WebView2; sem aceite manual ou publicação. |
| ML-053 | `reports/ml053_coverage_checkpoint_2026-11-24.md` | Auditoria DA registrou 36 achados/oportunidades. Evidências privadas continuam locais; validação de estados que exigem mutação pertence a fixtures descartáveis. |
| ML-054 | CR: `4999670d79ec08d8573702a19e80eea5020a1e6e`; simulação textual `faefcd252f4cef87682328c5ddcfab6ec0e27818` | Núcleo aprovado pelo CR: migração/legado/retry e 45 testes, com oito cenários da simulação reproduzidos. +5 p.p. em cinco regiões foi sensibilidade, não campanha real com Exploradores só natais; ausência e CPU/combat/recompensas não foram simuladas por essa evidência. |
| ML-055 backend | CR: `043cb5eceac1bc160c76350cf3a4b628bac2f200` | Aprovado pelo CR, 36 testes independentes. Corrige efeitos antecipados/duplicados, prioridades de reserva e divergência entre diagnóstico e gerador. O aceite funcional não aprova sozinho a central visual. |
| ML-055 central | Código: `cebe8fbb38ef682ad16ff55cb5c312401ae94d11`; cobertura complementar: `ed179b7cb75a736f7293eca616fd0787ee069f26` | DA55-01–04 implementados; DA visual pendente. CR encontrou falso verde no helper: contar grupo mínimo não detecta falha real de poder/equipamento exigido pelo portal. Correção está pendente; não marcar ML-055 validada. |

Os relatórios DA originais de ML-052 (`reports/ml052_da_897fde9_2026-11-24.md`, baseline anterior) e ML-055 (`reports/ml055_da_4ff9aad_2026-11-24.md`, candidato não aprovado) ficam como histórico textual sanitizado. Nenhum deles deve ser lido como aceite do candidato atual.

## ML-055 central — matriz do DEV

| Critério | Implementação/cobertura no candidato | Limite do aceite atual |
| --- | --- | --- |
| CR indicador do menu | `app/services/navigation_work_status_service.py`; `tests/test_navigation_work_status.py`; `tests/js/navigation-work-status.test.mjs` | Resultado próprio pronto vence amarelo de andamento; falha/dado incompleto vira indisponível, não zero. **Bloqueio CR atual:** portal com grupo mínimo, porém sem poder/equipamento exigido ainda pode aparecer verde; helper deve consumir validação autoritativa compartilhada com o início. Sem novo gate de nível de mercenário. |
| CR participação central | `app/templates/regional/events.html`, `app/templates/components/regional_offer_actions.html`, rotas regionais e smoke HTTP | Decidir, preparar, iniciar e reforçar a partir de `/regional/events`; retorno validado mantém seção/evento. Testado em campanha descartável, sem perfil do jogador. |
| DA55-01 / F21 | `events.html`, `regional_event_history.html`, divisão de cards em `regional_routes.py` | Duas seções principais; eventos atuais e encerrados organizados por Portais/Rebeliões; externo atual visível sem ação de participação. Revisão DA pendente. |
| DA55-02 | `desktop-evolution.css`, `tests/test_desktop_art.py` | Navegação e summaries têm alvo mínimo 40 px e foco visível; confirmação visual DA pendente. |
| DA55-03 / ML-054 | `portal_spawn_status_for_region()` fornece valores; central apresenta chance efetiva, base, falhas, Exploradores, teto e cooldown; teste de contrato no `test_desktop_art.py` | Sem fórmula de chance paralela no frontend; indisponibilidade de dados/conteúdo é distinta de cooldown; texto não promete portal. Revalidação visual DA pendente. |
| DA55-04 | `regional_routes.py`, `events.html`, macro de histórico; `tests/test_desktop_http_smoke.py` | Prazo de entrada separado do prazo da equipe; portal em andamento permanece atual após expiração; pronto para coleta tem link; coletado fica distinto. DA retesta pendente. |
| Convite sem aceite | `tests/test_desktop_http_smoke.py` | Fixture de convite realmente vencido: idade 14 h, prioridade/TTL encerrados e `expire_due_events` aplicado; aparece no histórico sem ações. Cenário é separado do evento aceito que continua em andamento. |

## Evidência automatizada de ML-055 central

- `python -m unittest tests.test_desktop_http_smoke` — 1 teste passou em servidor loopback, campanha sintética e perfil descartável. Inclui participação direta na central; portal natal aberto, equipe em andamento após fim da janela, coleta e estado coletado; portal externo aberto/em andamento sem início local; convite vencido sem aceite no histórico; histórico legado sem dados versus lista vazia.
- `python -m unittest tests.test_navigation_work_status tests.test_regional_route_access tests.test_desktop_art` — 32 testes passaram. A cobertura do serviço do spawn de portal confirma valores autoritativos e separação de cooldown/conteúdo; o teste de arte afirma que a central consome a decomposição recebida do servidor.
- `node --test tests/js/navigation-work-status.test.mjs tests/js/regional-navigation.test.mjs tests/js/regional-notice-focus.test.mjs` — 7 testes passaram para erro/zero/polling, rota ativa distinta, deep-link, foco e avisos.
- `py_compile` dos módulos/arquivos de teste tocados e `git diff --check` — passaram.

Resultados sintéticos não equivalem à revisão DA em viewports/telas nem ao aceite manual do usuário. A matriz consolidada DA ainda deve aferir 390/980/1100/1101/1440 px, largura útil, estados e acessibilidade indicados nas especificações.

## Próximo lote ML-057 e cobertura integral

ML-057 segue autorizado com todos os Fxx de `docs/art_direction/ML056_ML057_COMPONENT_ACCEPTANCE.md`: F01–F07, F14, F16 modal/rolagem, F17, F19, F30–F31, F32 detalhe/navegação e F34–F36. ML-056 continua obrigatório, cobrindo F08–F13, F16 seleção/ações, F18, F20, F22–F29, F32 estados e F33. F15 é ML-052; F21 é ML-055 e não deve ser reimplementado como terceiro lote.

Primeiro de ML-057: reproduzir F34 em fixture isolada por navegação direta e navegação parcial de outra tela para Guia, incluindo termo buscado, loading do catálogo e exportação. Confirmar a causa no ciclo de vida de `guide.js`/`main.js` antes da correção. Depois seguir composição do shell, header/offset/popovers, grades, relatórios, Guia/raridades, tutorial e Atualizações conforme a especificação. Emitir SHA, arquivos, Fxx, regressões e limites por lote; manter ML-055 imutável para revisão DA.

## Preservação e publicação

Somente os relatórios textuais sanitizados e registros documentais aprovados serão adicionados ao checkpoint. Capturas privadas ou sintéticas, JSONs com caminhos locais, saves e dados de perfil não serão commitados. `scripts/balance/simulate_regional_cpu_campaigns.py` é alteração preexistente alheia e permanece fora do staging. Não foi executado build, instalação, push, PR, merge, tag ou release.
