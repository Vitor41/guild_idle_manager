# BUG-010 — investigação de abertura de Oficinas

**Data:** 2026-11-10  
**Branch:** `feature/bug-010-workshop-error`  
**Base:** `1f31a9436cfd06640e50325277117e70e5870a3a`

## Resultado

A falha mostrada na captura não foi reproduzida. A rota `GET /workshops` e o template atual funcionaram em uma campanha nova e em cópias descartáveis de campanhas de teste já existentes. Não há evidência suficiente para atribuir causa ou fazer uma correção de produto.

## Referência e logs

A referência `90e79039f32444b5b2d307f8ac25ae42` não apareceu nos arquivos consultados em `%LOCALAPPDATA%\GuildIdleManager\logs`:

- `desktop.log`
- `gameplay-actions.log`
- `update-handoff.log`
- `update-launcher.log`

O `desktop.log` termina em 2026-11-01. O `gameplay-actions.log` mais recente é de 2026-11-09, mas não contém essa referência. Nenhum outro diretório de perfil ou arquivo de campanha foi examinado.

## Reprodução isolada

- `tests.test_workshop_service`: **7/7 passaram**, usando SQLite em memória.
- `tests.test_desktop_http_smoke`: **1/1 passou**; o caso cria uma campanha temporária, solicita `/workshops`, exige status 200 e verifica ausência de resposta de erro interno.
- Smoke adicional em cópias temporárias de duas campanhas de teste: ambas migraram da revisão `f3b4c5d6e7f8` à revisão atual `0a1b2c3d4e5f`; `/workshops` respondeu 200 e incluiu o título esperado. Uma cópia não tinha mundo regional prévio e a outra já continha estado regional.

Os arquivos fonte dos dois fixtures em `.lot-e2-test-tmp` foram somente lidos. A migração, o avanço do mundo e as requisições ocorreram em clones em diretórios temporários, apagados ao final dos testes. Nenhum perfil instalado ou save real foi aberto ou alterado.

## Limite e próximo passo

O erro depende possivelmente de um estado específico da campanha ou de uma versão instalada anterior, mas não foi possível testar essa hipótese sem uma referência correlacionada ou um fixture reproduzível. O serviço e a tela passaram nas campanhas descartáveis disponíveis. A BUG-010 continua aberta até que o log correspondente ou um caso de reprodução isolado permita identificar a exceção original.
