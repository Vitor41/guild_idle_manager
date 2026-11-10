# QA da integração contra DEV-v0.8.0 — 10/11/2026

## Escopo e ambiente

- Candidato fixado: `cf65219f9c571370d41d9c25cbf74f3e7728524f` na branch `integration/approved-bug010-041-042-012-2026-11-10`.
- Base de comparação: tag `DEV-v0.8.0`, commit `9f3a6a05de86f7c4f342a4a175c6a799e8ef5ea3`.
- Checkout mantido em `C:\Users\vitor\Guild Idle Manager\App GIM`; nenhum worktree ou checkout paralelo foi criado.
- Nenhum perfil, save ou banco persistente do usuário foi aberto. As suítes usaram SQLite em memória; o smoke HTTP guardou saves e logs em diretórios temporários.
- Após confirmar que a falha também existia no comportamento legado da tag, foi aplicado um fix mínimo em `alembic/env.py` e um teste de regressão em `tests/test_gameplay_diagnostics.py`.
- Outros arquivos sem rastreamento existentes no checkout foram preservados e ficaram fora deste trabalho.

## Execuções

### Suíte ampla

Comando executado no checkout, de acordo com `docs/DEV_DESKTOP.md`:

```powershell
$env:APP_MODE = 'desktop'
$env:DATABASE_URL = 'sqlite:///:memory:'
python -m unittest discover -s tests -v
```

O Python fallback do ambiente não tinha `cryptography`; a primeira execução terminou com 330 testes, 3 falhas, 6 erros e 4 ignorados, incluindo falhas de importação e subprocessos que não carregavam o app. `cryptography==49.0.0` já estava no `.venv-desktop` do projeto. Sem instalar pacotes, um `sitecustomize.py` descartável em `%TEMP%` acrescentou esse diretório ao fim de `sys.path` do Python fallback, preservando a precedência das dependências já carregadas.

Reexecução com esse ajuste temporário:

- Resultado: `Ran 363 tests in 1501.263s; FAILED (failures=1, skipped=4)`.
- A única falha foi `test_desktop_http_smoke.DesktopHttpSmokeTests.test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions`.
- Os quatro skips são testes do instalador que exigem build, não executado nesta validação.
- A falha foi investigada e corrigida depois dessa execução; ver reteste abaixo.

### Smoke HTTP isolado

Executado separadamente com o mesmo Python fallback e o pacote já existente no venv desktop:

```powershell
python -m unittest tests.test_desktop_http_smoke.DesktopHttpSmokeTests.test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions -v
```

Resultado: `Ran 1 test in 74.846s; FAILED (failures=1)`. O filho isolado reproduziu `desktop_http_smoke_child.py:866`: `assert len(regional_production_lines) == 1`, valor `[]`.

## Causa e comparação com a tag

O teste executa `CampaignService.create_campaign()` após o primeiro registro de diagnóstico. A migração chama `fileConfig(config.config_file_name)` em `alembic/env.py:17`; com a configuração atual de logging, `fileConfig()` desativa loggers existentes não configurados, incluindo `gim.gameplay.*`. O rastreamento temporário de `Logger.disabled` capturou a pilha em `alembic/env.py:17` / `logging.config._handle_existing_loggers`; depois disso, o logger estava `disabled=True`, `isEnabledFor(INFO)=False` e com o stream fechado.

Um rastreamento de chamadas confirmou que o app invocou exatamente uma vez `log_gathering_advancement` com `action=gathering.production`, `route=/regional` e `cycles=1`. A linha não foi escrita porque o logger já estava desativado.

Evidências de não regressão contra `DEV-v0.8.0`:

- `alembic.ini`, `alembic/env.py`, `app/routes/gathering_routes.py`, `app/routes/inventory_routes.py` e o caminho de avanço de coleta permanecem iguais à tag.
- O gancho de registro em `app/routes/regional_routes.py` e a asserção de produção regional em `tests/test_desktop_http_smoke.py` já existem na tag; o bloco que falha não mudou.
- O módulo de diagnóstico também existe na tag. Repeti o smoke isolado com a lógica de nome de logger da tag (`gim.gameplay.{len(_LOGGERS)}`) substituída apenas em memória; a mesma asserção falhou.

Conclusão inicial: a falha é reproduzível no comportamento legado/configuração da tag, não foi introduzida pela integração `cf65219`. Era um defeito preexistente na continuidade dos logs após migrações SQLite.

## Correção e reteste

`fileConfig()` agora é chamado com `disable_existing_loggers=False`, preservando loggers de gameplay que não são declarados no arquivo de configuração do Alembic. O novo teste `test_gameplay_log_survives_campaign_migration_and_regional_production` grava um evento, cria campanha (executando a migração) e confirma que a produção regional continua registrada.

- `tests.test_gameplay_diagnostics`: 5/5 aprovados.
- Smoke HTTP isolado `test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions`: 1/1 aprovado em 112.113s.
- Suíte completa `python -m unittest discover -s tests -v`: `Ran 364 tests in 1694.798s; OK (skipped=4)`.
- Os quatro skips continuam sendo testes do instalador que exigem build, que não foi executado.
- Nenhum build, instalador, publicação ou instalação foi realizado. A execução usou SQLite em memória e dados temporários; saves e perfil normal ficaram intocados.

## Gate

A suíte ampla passou após a correção e cobertura de regressão. A revisão independente do CR do commit de correção ainda é o gate pendente. Esta validação não executou build, instalação nem publicação.

Logs desta execução e diretórios de campanha descartável foram mantidos em `%TEMP%` para auditoria; nenhum arquivo de teste foi gravado no perfil normal.
