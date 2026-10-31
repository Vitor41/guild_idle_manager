# Aceite técnico do hotfix 0.3.1

Branch local `hotfix/gameplay-actions-dev-diagnostics`, iniciada em `c6b18fb` da `melhorias-lote-2`. Nenhum save real, WebView GUI ou instalação foi aberto; o Setup gerado abaixo foi apenas inspecionado como arquivo, sem execução. As campanhas HTTP foram SQLite temporárias descartadas ao fim dos testes.

## Causa reproduzida

`main.js` substitui `.game-shell` quando a navegação assíncrona abre a Vigília. `regional-supply.js` só registrava seus listeners no `DOMContentLoaded` e consultava os formulários presentes naquele instante. Os formulários inseridos depois da navegação ficavam sem listener de equipe/cotação e contagem regressiva. Por isso o botão Preparar permanecia desabilitado; o botão sem suprimento também podia enviar `supply=1`, já que o handler que o desmarca não estava ligado.

O POST delegado de `main.js` já seguia redirects 303 e substituía a tela, mas seu fallback de erro chamava `form.submit()`. Esse caminho descartava `formaction` do botão Preparar e não deixava referência de diagnóstico. Os testes anteriores exercitavam as rotas HTTP diretamente e conferiam HTML/contrato estático; não executavam `DOMContentLoaded`, a navegação assíncrona seguida da reinserção dos formulários, nem o listener de `formaction`. A verificação do instalador 0.3.0 também não identifica a revisão Git exata do bundle. O spec inclui templates/static do checkout no build, mas não foi inspecionada a instalação do usuário.

## Fluxos e provas

| Fluxo / validação | Verificação realizada | Resultado esperado comprovado |
|---|---|---|
| Coleta | POST HTTP de `/gathering/assign`, consulta do save temporário, estado do mercenário e avanço controlado de 60 s | Redirect de sucesso, atividade salva, mercenário `gathering`, 1 ciclo processado e progresso reiniciado em 0 s. |
| Oferta sem suprimento | POST com `supply=1` primeiro comprova erro visível sem alteração; em seguida POST de início sem a flag | O primeiro erro volta à Vigília; o segundo redireciona para Missões, oferta `in_progress`, run sem snapshot de suprimento, worker `busy` e saldo intacto. |
| Oferta com suprimento | Cotação HTTP com equipe de poder 12 e recomendação 10, rank E/recompensa 100; POST `/prepare`; espera do timer de 1 s e novo GET; POST `/start` | Cotação disponível, +5 p.p., custo E de 1 ouro; oferta passa por `supply_preparing`, chega a 100%, inicia com mesmo grupo, snapshot persiste bônus/custo e o ouro é debitado uma única vez. |
| Sem construções | A fixture apaga todas as linhas `guild_buildings` antes dos fluxos e define no template do contrato `required_building_type=contract_office`, nível requerido 1 | Coleta, contrato, missão normal, masmorra e chefe iniciam sem qualquer prédio construído. Guilda continua no nível normal mínimo dos templates, isolando a regra de construção. |
| Exceção inesperada | Rota temporária de diagnóstico lança `RuntimeError` com strings que imitam senha e Bearer token | HTTP 500 vira redirect 303 com mensagem genérica e referência; stack trace fica no arquivo, os valores sensíveis não aparecem. |

## Validadores de construção inspecionados

- `assign_worker()` valida família, vínculo do mercenário, disponibilidade e exclusividade do posto; não consulta prédio.
- `validate_mission_requirements()` verifica somente nível da guilda. `start_mission()` usa esse validador; campos legados `required_building_*` não são lidos.
- `validate_dungeon_requirements()` verifica somente nível da guilda. `are_dungeons_available()` retorna `True`; `start_dungeon()` ainda valida tamanho/nível/equipe, poder, classe, papel e equipamento quando o desafio os exige, mas não prédio. Bônus de Exploradores continuam usando `get_building_level()` sem bloquear entrada.
- `/regional/offers/{id}/start` não tem gate de prédio: valida ciclo, região, oferta/preparo, equipe e depois chama missão ou masmorra. A cotação pode ler bônus de escritório/Exploradores, com nível zero como valor padrão.
- `_select_contract_templates()` prefere dois contratos iniciais sem requisitos de prédio quando disponíveis; isso é seleção de catálogo, não bloqueio do início. O teste ainda iniciou um contrato cujo template declara escritório nível 1 com a guilda sem construções.

### Evidência explícita por fluxo sem construções

O teste `tests.test_building_gate_contract.BuildingGateContractTests` contém quatro casos nomeados para contrato regional, missão normal, masmorra e chefe. Cada template declara um prédio legado de nível 100, e os validadores passam usando DB stub sem acesso à tabela de construções. O smoke HTTP também apaga todas as linhas `GuildBuilding`, reduz os requisitos legados dos templates a nível 1 e inicia cada execução de verdade:

- Contrato regional: `POST /regional/offers/{id}/start` chama `start_mission`; oferta vira `in_progress`, `MissionRun` persiste e mercenário fica `busy` com zero prédios.
- Missão normal: `start_mission` + `validate_mission_requirements`; `MissionRun` persiste com zero prédios.
- Masmorra: `start_dungeon` + `validate_dungeon_requirements` + `are_dungeons_available`; `DungeonRun` persiste com zero prédios.
- Chefe: `start_dungeon` + os mesmos validadores; `DungeonRun` persiste com zero prédios. A fixture satisfaz os requisitos de nível/grupo do conteúdo, sem criar construções.

`POST /gathering/assign` e `assign_worker()` também passam na campanha sem construções; o teste do serviço em memória confirma zero linhas antes e depois da atribuição. As rotas desktop legadas `/missions/start` e `/dungeons/start` encaminham à Vigília por design e não adicionam gates.

## Cliente, redirects e segurança

`window.initializeRegionalSupply(root)` é chamado no carregamento inicial e após `restoreGameFormState()` em cada troca de `.game-shell`; o formulário fica ligado só uma vez por nó. O teste de contrato confirma listener de checkbox, desmarcação de suprimento no botão sem suprimento, uso de `submitter.formAction`, seguimento de redirect, toast, registro de erro do cliente e mensagem inline quando a requisição falha. Desktop envia `Origin` same-origin; o smoke HTTP cobre os POSTs pelo middleware que valida host/origem. A API de diagnóstico aceita somente rotas de gameplay permitidas e nunca recebe conteúdo do formulário.

## Logs de diagnóstico

Arquivo estável do perfil local, fora do executável e dos saves:

`%LOCALAPPDATA%\GuildIdleManager\logs\gameplay-actions.log`

Texto simples com timestamp UTC, ação, rota sem query, referência, status HTTP e resultado. Exceções inesperadas incluem traceback sanitizado. Senhas, cookies, tokens, autorização e corpo de formulário não são registrados. Rotação: 1 MB + dois arquivos anteriores. Em falha, a tela mostra referência e caminho. Documentação: `docs/DEV_DESKTOP.md`.

## Atualizador GitHub Releases

Owner/repo padrão resolvido pelo código: `Vitor41/guild_idle_manager`; canal de bundle vem do marcador DEV/beta/stable. Sem `.env` para esses valores. O teste de release usa uma chave Ed25519 efêmera, executa o signer, valida assinatura do manifesto e SHA-256 no cliente que prepara o Setup. Teste também comprova que, sem chave pública, nenhuma requisição é feita e `query_enabled/install_enabled` seguem falsos.

Nos próximos builds, `-GitHubOwner` e `-GitHubRepo` permitem selecionar o destino no momento da distribuição; os valores e a chave pública são gravados em `app/data/gim-release-config.json`. Slugs inválidos são rejeitados pelo build e pelo runtime. O bundle 0.3.1 anterior ao config mantém defaults atuais e a leitura opcional do arquivo de chave legado. Depois que o repositório for escolhido, é necessário reconstruir o Setup com os valores escolhidos; nenhum build foi feito nesta atualização preparatória.

A revisão Git local tem `origin` configurado para esse remoto. A integração GitHub disponível respondeu 404 tanto ao consultar metadata como releases; não se pode concluir se o repo é privado ou se a conta conectada carece de acesso. O updater atual faz consulta anônima e não tem token; para ele funcionar o repo precisa estar público. Não foi observada release real com manifesto, assinatura, Setup e hash validados.

A instalação 0.3.0 não implementa bootstrap pelo GitHub e não pode aceitar atualização assinada retroativamente. O Setup 0.3.1 abaixo é uma primeira atualização de instalação manual; ele foi construído sem chave pública e mantém o updater fail-closed. Falta provisionar uma chave Ed25519 real, guardar a privada fora do Git e tornar o repositório acessível à consulta anônima para habilitar atualizações futuras. Não se configurou chave falsa nem se ativou a consulta sem confiança. O Setup foi criado apenas como artefato; não foi executado nem instalado.

### Setup DEV 0.3.1 validado

- Arquivo: `dist/staging/hotfix-0.3.1-DEV-20261031/GuildIdleManager-DEV-Setup.exe` (60,98 MiB; 63.946.752 bytes).
- SHA-256: `a41bfaf8538e8cfb8b1d8b4463e3e4a05cefdd481dfd3064f64da9a184aad184`.
- Build: `.venv-desktop` com Python 3.12.14 e PyInstaller 6.22.3.
- Validação sem execução: assinatura DOS `MZ` e cabeçalho PE válidos; ZIP de 61,41 MiB com 941 entradas passou `testzip`, contendo launcher de instalação, executável, templates e JS; arquivo versionado do PyInstaller contém `APP_VERSION=0.3.1`; nome, default e marcador do instalador são DEV.
- Nenhum `gim-release-public-key.txt` foi incluído. O updater não consulta nem instala releases. Este artefato não é bootstrap para o 0.3.0; a transição inicial é manual.

## Testes registrados

Execução final: 23 testes passaram em 49,746 s no runtime desktop, com `APP_MODE=desktop`, campanhas e diretórios temporários:

| Módulo | Testes |
|---|---:|
| `tests.test_release_signing_tool` | 4 |
| `tests.test_gameplay_diagnostics` | 2 |
| `tests.test_stage5_ui_contracts` | 16 |
| `tests.test_desktop_http_smoke` | 1 |

Verificação preparatória final: 20 testes passaram em 42,345 s nos módulos `tests.test_release_signing_tool` (9), `tests.test_building_gate_contract` (4), `tests.test_gathering_service` (6) e `tests.test_desktop_http_smoke` (1). O parser PowerShell aceitou o script, e o próprio build rejeitou inputs inválidos (`bad/name`, `../repo`, `repo.git` e `bad--owner`) antes de iniciar qualquer build.

`git diff --check` passou após as alterações documentais. Não houve inspeção visual, instalação, execução de Setup, push ou PR.
