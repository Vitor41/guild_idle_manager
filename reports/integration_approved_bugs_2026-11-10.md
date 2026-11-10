# Integração local — candidato DEV 0.9.0

## Escopo e base

Integração montada no checkout principal, sem worktree, em `integration/approved-bug010-041-042-012-2026-11-10`. A base é `integration/ml-028-035-040-bug011-2026-11-10` em `70ed958ba061c6021d4a10a7604dc233da7d13b7`.

O histórico foi integrado por merge local, preservando os commits revisados:

| Item | Commits-fonte integrados | Merge local |
|---|---|---|
| BUG-010 | `768ecaea0baa37f78e30ec45295b3d3c6084a3ec`, `f3fb83269bf26ce60ef851cf30ebbef8ca1e101e` | `6597134` |
| ML-041 | `a3390e9b89c8fad965ceb915eb717cf1eb6636d5`, `c687019fe418c7bd8809e5de9f770da73a361a53` | `ebabc40` |
| ML-042 | `e46d679405e03892162affb2c58b735ebd642fc5`, `79dc7aad5f8e5860ea3e421a47f1e4382c58372e` | `1f4e2be` |
| BUG-012 | `83448f6b06f8ea549b869da8d848747912b5616e` | `8ad2efd` |

`git merge-base --is-ancestor` confirmou `yes` no candidato para a base `70ed958`, os commits-fonte listados acima, os quatro hashes aprovados de ponta (`f3fb832`, `c687019`, `79dc7aa`, `83448f6`) e a tag `DEV-v0.8.0` (`9f3a6a05de86f7c4f342a4a175c6a799e8ef5ea3`). Os commits-pai de implementação também foram verificados como ancestrais, não apenas os nomes dos branches.

## Versão candidata

Antes da alteração, `git tag --list --sort=-version:refname` mostrou `DEV-v0.8.0` como tag local mais recente. A consulta somente de leitura `git ls-remote --tags origin` confirmou que `DEV-v0.8.0` também é a tag remota mais recente e aponta para `9f3a6a05de86f7c4f342a4a175c6a799e8ef5ea3`; não há tag `0.9.0` ou posterior. O commit-base da integração descende de `DEV-v0.8.0`.

O candidato atualiza `app/core/version.py` para `0.9.0`, acrescenta as notas em `docs/CHANGELOG.md`, atualiza a versão candidata em `docs/UPDATE_ARCHITECTURE.md` e ajusta a regressão do Guia que verifica a versão renderizada. Nenhuma tag foi criada. A assinatura, build, instalação e publicação continuam para uma única etapa coordenada depois da aprovação do CR da integração.

## Matriz dos itens registrados

Estados resumidos de `ML-BUGS.md`; aprovação técnica e aceite visual pelo usuário são gates distintos.

| Itens | Estado técnico no candidato | Gate ou observação restante |
|---|---|---|
| ML-001–019 | Validados conforme evidências individuais do backlog | Nenhum item novo nesta integração |
| ML-020 | Implementado e validado estruturalmente | A cobertura registrada é estrutural/DOM |
| ML-021–023 | Validados; ML-023 já está na história base e não foi duplicada | Sem mudança nesta integração |
| ML-024, ML-027 | Corrigidos e aprovados tecnicamente pelo CR | Aceite/publicação de release permanecem separados |
| ML-025–026 | Validados e encerrados pelo usuário | Sem mudança nesta integração |
| ML-028 | Integrado na base e aprovado tecnicamente pelo CR | Aceite visual final do usuário pendente |
| ML-029–034 | Validados/encerrados conforme o backlog | ML-034 não declara atualização completa; teste do usuário da atualização permanece como registrado |
| ML-035 | Integrado na base e aprovado tecnicamente pelo CR | Aceite visual manual pendente |
| ML-036–037 | Integrados na base e aprovados tecnicamente pelo CR | Aceite visual manual pendente |
| ML-038 | Integrado na base e aprovado tecnicamente/economicamente pelo CR | Balanceamento fino durante o jogo permanece risco residual registrado |
| ML-039 | Integrado na base e aprovado tecnicamente pelo CR | Aceite visual do usuário pendente |
| ML-040 | Integrado na base e aprovado tecnicamente pelo CR | Aceite visual manual pendente |
| ML-041 | Integrado; `c687019` aprovado tecnicamente pelo CR | Aceite visual final e publicação pendentes |
| ML-042 | Integrado; `79dc7aa` aprovado tecnicamente pelo CR | Smoke HTTP amplo anterior não foi aprovado por falha do harness; aceite visual final pendente |
| BUG-001 | Validado e revisado pelo CR | Sem mudança nesta integração |
| BUG-002 | Corrigido e validado com regressão HTTP | Sem mudança nesta integração |
| BUG-003 | Validado pelo usuário e encerrado | Sem mudança nesta integração |
| BUG-004 | Corrigido e aprovado pelo CR | A causa específica no save do usuário não foi confirmada; nenhum save real consultado |
| BUG-005 | Implementado e coberto por smoke HTTP local | Sem mudança nesta integração |
| BUG-006–007 | Integrados e aprovados tecnicamente pelo CR | Inspeção visual manual final não foi reivindicada |
| BUG-008 | Corrigido e aprovado pelo CR | Sem mudança nesta integração |
| BUG-009 | Validado pelo usuário e encerrado | Sem mudança nesta integração |
| BUG-010 | Correção aprovada tecnicamente pelo CR e incluída | Validação de usuário em candidato assinado/perfil temporário pendente; não usar perfil real |
| BUG-011 | Integrado na base e aprovado pelo CR | E2E visual no aplicativo instalado/perfil temporário pendente |
| BUG-012 | Integrado; `83448f6` aprovado tecnicamente pelo CR | Avaliar em jogo o impacto dos aumentos avançados antes do aceite final |

## Validação da integração

Comando executado, em SQLite e dados temporários:

```powershell
$env:TEMP=(Resolve-Path .qa-temp-bug010).Path
$env:TMP=$env:TEMP; $env:TMPDIR=$env:TEMP
$env:PYTHONPATH=(Resolve-Path .validation-site-packages-080).Path
& .venv-e2e-080\Scripts\python.exe -m unittest `
  tests.test_workshop_service `
  tests.test_workshop_route_diagnostics `
  tests.test_guide_routes `
  tests.test_economy_arbitrage `
  tests.test_dock_pricing `
  tests.test_salvage_balance `
  tests.test_material_source_manifest `
  tests.test_regional_cycle_service.RegionalCycleSimulationTests.test_requirement_overrides_remain_defensive_in_services `
  tests.test_stage5_runtime_validation.Stage5RuntimeValidationTests.test_equipping_over_single_slot_returns_previous_item_and_recalculates_power `
  tests.test_stage5_runtime_validation.Stage5RuntimeValidationTests.test_two_ring_and_earring_slots_require_explicit_replacement_target_when_full `
  tests.test_stage5_runtime_validation.Stage5RuntimeValidationTests.test_ineligible_or_foreign_item_cannot_change_current_equipment `
  tests.test_stage5_runtime_validation.Stage5RuntimeValidationTests.test_failed_equipment_commit_rolls_back_both_items `
  tests.test_stage5_runtime_validation.Stage5RuntimeValidationTests.test_mercenary_level_is_recommendation_while_guild_level_still_gates_missions `
  tests.test_stage5_runtime_validation.Stage5RuntimeValidationTests.test_under_recommended_mercenary_starts_dungeon_and_boss_but_guild_gate_remains `
  tests.test_stage5_runtime_validation.Stage5RuntimeValidationTests.test_crafted_equipment_can_flow_through_salvage_and_market_services
```

Resultado: 39 testes executados; 37 passaram e 2 testes de `test_workshop_route_diagnostics` deram `FileNotFoundError` ao ler o log temporário. O Python de validação não conseguiu gravar nos diretórios temporários externos permitidos pelo runner e recuou para uma pasta sob o checkout; a aplicação bloqueia corretamente `LOCALAPPDATA` dentro da pasta do app. A repetição com `%TEMP%` externo encontrou a mesma limitação de gravação. Os outros 37 testes passaram, incluindo o teste do Guia com `APP_VERSION=0.9.0`, swaps de equipamento, nível recomendado, economia, preços, taxas e o fluxo de crafting/desmontagem/Market. Essa restrição do harness também já foi registrada na investigação anterior de BUG-010; não foi contornada alterando o código do produto ou o teste.

`git diff --check` foi executado depois das mudanças da integração. A suíte completa não foi executada. A revisão CR da integração e a aceitação visual permanecem pendentes.

## Riscos e limites

- BUG-012 fecha os ciclos modelados, mas aumenta preços de equipamentos avançados: o relatório `reports/economy_arbitrage_bug012_2026-11-10.md` registra aumento de até 4.784 ouro em oferta late e 2.270 ouro no custo de uma receita extrema. A viabilidade de progressão deve ser avaliada em jogo antes de aceite final.
- Alguns itens têm aprovação técnica sem aceite visual do usuário. Não declarar aceite visual final nesta integração.
- Duas regressões de log de BUG-010 não puderam completar sob a restrição de diretório temporário do runner; o smoke HTTP amplo também não foi declarado aprovado.
- `0.9.0` é só a versão do candidato local. Não há tag, assinatura, build, instalação, push, PR, merge remoto ou release.
