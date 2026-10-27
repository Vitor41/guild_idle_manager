# Gates de revisão — Guild Idle Manager Desktop Offline

Este documento é o checklist independente da conversa principal. A fonte do escopo é `docs/GDD_DESKTOP_OFFLINE.md`. Nenhuma etapa é aceita apenas porque o código compila ou porque os testes antigos passam. Cada gate exige evidência no estado atual da branch `feature/desktop-offline`.

## Regra de operação

- Pasta única: `C:\Users\vitor\Guild Idle Manager\App GIM`.
- Sem worktrees, novas branches de execução ou mudanças na pasta web original.
- Commits por assunto, com arquivos limitados ao dono da tarefa.
- DA: `docs/art_direction/`, `design/`, `app/static/assets/desktop/`.
- DEV: código, testes, scripts de build e documentação técnica; não alterar assets da DA sem revisão.
- A conversa principal revisa diff, execução, dados e resultado visual. Pendência retorna ao autor da etapa; não é aceita por promessa de correção futura.

## Gate DA — Identidade visual

- [ ] Guia de identidade define paleta variada, tipografia local/licenciada, grid, espaçamento, estados, raridade e acessibilidade.
- [x] Uso real da skill `imagegen` comprovado por assets bitmap entregues, não apenas por briefing ou mockup.
- [x] Assets cobrem as superfícies prioritárias do jogo e possuem nomes, dimensões, manifesto e fallback.
- [ ] Preview desktop e janela estreita podem ser abertos localmente e mostram interface legível, sem sobreposição.
- [ ] Assets funcionam offline, sem CDN, têm pesos razoáveis e licença/proveniência registrada.
- [ ] A substituição visual não causa regressão na identificação de classe, item ou construção.
- [x] A iconografia nova cobre menu, ações, classes/evoluções, mercenários, equipamentos por grupo/slot, materiais/recursos, construções e demais sistemas; manifesto/fallback não deixam grupos com placeholder genérico.
- [x] Ícones legados sem procedência confirmada não são dependência do pacote distribuído; sprites novos têm autoria e permissões de uso registradas.
- [x] A conversa principal visualizou os previews e informou ao usuário os caminhos exatos para vê-los.

## Gate 1 — Core offline e campanhas

- [x] App novo cria e abre campanha SQLite sem PostgreSQL, `.env` ou login.
- [x] Duas campanhas têm guildas, recursos, mercenários, itens e progresso isolados.
- [x] `campaign_metadata`, preferências de tutorial/confirmação e identificação da campanha persistem entre aberturas.
- [ ] Chaves estrangeiras, transações, cascatas e locks possuem comportamento compatível com SQLite.
- [ ] Missão, masmorra, loot, inventário, contratação e construções continuam respeitando pré-condições e atomicidade.
- [x] Alembic/estratégia de schema local é versionada e não executa SQL exclusivo do PostgreSQL.
- [ ] Seeds de conteúdo são aplicadas por versão; segundo carregamento não duplica nem sobrescreve estado.
- [ ] Modo web anterior ainda inicia ou há justificativa explícita/testada para mudança inevitável.
- [x] Testes novos usam diretórios temporários e não escrevem em guildas reais; suite anterior continua verde.
- [x] Relatório DEV lista commits, arquivos, comandos, resultados e riscos conhecidos.

## Gate 2 — Janela, save e relógio

- [ ] Aplicativo inicia e encerra FastAPI local junto de uma janela própria; servidor escuta apenas em loopback.
- [ ] Nova campanha/continuar/renomear/exportar/importar/excluir funcionam com confirmação e tratamento de erro.
- [ ] Save, backups, logs e âncora de tempo ficam fora da pasta de instalação e fora do Git.
- [ ] Migração de save faz backup prévio; falha não destrói o save original e oferece recuperação.
- [ ] Aplicativo aberto não concede idle; retorno de período fechado concede uma vez, respeitando mínimo e teto atuais.
- [ ] Relógio monotônico é usado durante execução; retrocesso, salto, corrupção da âncora e crash têm testes determinísticos com relógio injetado.
- [ ] Timers e coleta manual de missão, masmorra, mercado, taverna e ferreiro seguem as regras existentes.
- [ ] Launcher DEV usa o checkout em `App GIM`, sem reinstalação e sem instalar dependências/migrar PostgreSQL a cada inicialização.
- [ ] Relatório DEV lista commits, arquivos, comandos, resultados e riscos conhecidos.

## Gate 3 — Build DEV e regressão final

- [ ] Executável/instalador Windows inclui Python, templates, CSS/JS, assets, JSON de dados e migrations necessários.
- [ ] Smoke test em ambiente limpo sem Python, PostgreSQL, `.env` e rede.
- [ ] Atualização por instalador preserva saves e permite migrar/restaurar versão anterior.
- [ ] QA manual registra ao menos um fluxo de cada sistema listado na seção 13 do GDD; falha/sucesso de loot são verificados.
- [ ] Interface integrada à nova DA é responsiva, tem imagens reais e mantém navegação fluida em janelas desktop e estreitas.
- [ ] Testes automatizados atuais e novos passam; gaps são explicitados, não escondidos por skips silenciosos.
- [ ] Pacote não contém senhas, `.env`, arquivos de conta de teste, saves do usuário nem logs pessoais.
- [ ] README contém comandos reais para DEV, build, instalação, backup e recuperação.
- [ ] Branch só é integrada/fechada depois de todos os gates aceitos e GDD auditado item por item.

## Registro de revisão

Para cada retorno de DA ou DEV, registrar na conversa principal:

1. Revisão/commit examinado.
2. Arquivos e superfícies inspecionados.
3. Comandos de teste, resultado e ambiente.
4. Evidência visual/runtime quando aplicável.
5. Achados com gravidade e responsável.
6. Decisão: aprovado, devolver para correção, ou bloqueado com motivo verificável.

Este checklist não substitui o GDD nem os testes de regressão; serve para tornar explícito o padrão de aprovação.

### 2026-10-26 — Gate 1 autorizado para avançar

- Commits revisados: `aa6398f`, `2dc7596`, `e28c973`, `9fb9db4`, `e80b501` e `235903e`.
- Verificação independente: `C:\Users\vitor\Guild Idle Manager\.venv\Scripts\python.exe -m unittest discover -s tests -q` em `App GIM`: 35 testes passaram.
- Evidência: criação de duas campanhas SQLite, cadeia Alembic completa, dados de guilda e gameplay isolados, reabertura persistente, migração de revisão anterior com backup, rejeição sem modificação de arquivos vazios, parciais, com revisão desconhecida ou UUID interno divergente.
- Decisão: Trabalho 2 liberado. Este aceite não declara o aplicativo jogável nem a recuperação de falha de migration pronta.
- Pendências obrigatórias: restauração automática/testada após falha de migration (Gate 2); janela/launcher, ClockGuard, idle e menus de campanha (Gate 2); regressão de todos os sistemas, modo web e build limpa (Gate 3).

### 2026-10-26 — Revisão parcial do Gate 2 (não aprovado)

- Verificação independente no checkout compartilhado: `python -m unittest tests.test_desktop_bridge tests.test_desktop_security -q` passou (3/3) com o interpretador local disponível; `python -m unittest tests.test_clock_guard -q` passou (4/4) no Windows após correção da limpeza do SQLite.
- A prancha `design/preview/class-readability-26.png` foi inspecionada: os 26 códigos de `CLASS_TREE` têm um sprite correspondente, sem faltas ou sobras. Em 24 px, os emblemas requerem nome adjacente e fundo sólido para identificação.
- Achados devolvidos ao DEV durante a implementação: encerrar corretamente campanhas suspensas quando o aplicativo fecha, impedir caminho arbitrário no bridge de exportação e provar navegação/formulários com a proteção de origem ativa. Os testes isolados acima não aprovam o Gate 2.
- Ainda faltam avaliação da janela real, suite completa, cenários de falha/recuperação e pacote final de sprites integrado antes de qualquer aceite.

### 2026-10-26 — Revisão independente dos commits do Trabalho 2

- Commits examinados: `04c8d11` e `47c4208`.
- No ambiente isolado `.venv-desktop`, com `APP_MODE=desktop`, a bateria `tests.test_campaign_service`, `tests.test_clock_guard`, `tests.test_desktop_bridge`, `tests.test_desktop_http_smoke` e `tests.test_desktop_security` passou: 27 testes em 218,239 s.
- Um lançamento adicional com `LOCALAPPDATA` temporário respondeu ao healthcheck em loopback. O processo Python criou uma janela intitulada `Guild Idle Manager` (handle nativo observado), mas ela não apareceu no inventário da automação visual desta sessão. O processo de diagnóstico foi encerrado; nenhum save do usuário foi aberto.
- Decisão: ainda não aprovar Gate 2. Falta evidência visual/interativa da janela, fechamento limpo com a campanha ativa e revisão do fluxo completo do menu no runtime nativo. Prosseguir com a integração de arte e o QA de empacotamento sem tratar essa lacuna como resolvida.

### 2026-10-26 — Pacote DA registrado, gate visual parcial

- Commit examinado: `f4cbf86`, limitado a `app/static/assets/desktop/`, `design/` e `docs/art_direction/`; alterações em andamento do DEV ficaram fora dele.
- Verificação independente: `design/build_sprite_manifest.py` gerou 92 sprites e 214 mapeamentos com zero códigos conhecidos ausentes. O manifesto referencia 282 arquivos únicos, todos presentes e não vazios; os 92 masters também existem. `design/preview/nav.js` passou em checagem de sintaxe, `git diff --check` passou e não restaram perfis temporários de captura.
- Prévias desktop/estreitas e pranchas de legibilidade foram inspecionadas. O usuário recebeu os caminhos da prévia e do catálogo. O pacote usa bitmaps originais e fontes locais; a procedência dos assets web legados permanece separada.
- Decisão: aceitar o pacote fonte de sprites para integração, **não** o Gate DA completo. Os últimos ajustes de nomes/KPI/menu compacto ainda carecem de conferência visual atualizada; aplicação real em templates, navegação, WebView2 e build offline permanece no Gate 3.

### 2026-10-26 — Runtime nativo ainda sem aceite

- Commit DEV revisado: `300eeff`. A CSP desktop permite `unsafe-eval`, necessário ao `new Function` da bridge pywebview; o smoke exige a API de exportação. Não há hooks de diagnóstico no commit nem mudança de backend de produção.
- Verificação independente: `APP_MODE=desktop` com `tests.test_desktop_bridge tests.test_desktop_security -q` passou (4/4). `GIM_RUN_DESKTOP_RUNTIME_SMOKE=1` com `tests.test_desktop_runtime -v` falhou: janela `shown=True`, mas `loaded=False`, bridge indisponível e nenhuma resposta capturada; a janela fechou. O smoke durou 39,634 s e não tocou saves reais.
- Diagnóstico DEV separado observou `ExecuteScriptAsync` com `CoreWebView2 is uninitialized` antes de fechar a janela. Teste alternativo Qt também não concluiu carregamento/bridge, portanto nenhum dos dois backends foi aceito como solução.
- Decisão: Gate 2 **aberto**. Prosseguir apenas com integração visual, QA transacional e empacotamento como trabalho em andamento; o instalador não será declarado testável até comprovar `loaded`, DOM, criação/retorno de campanha e encerramento limpo em janela nativa.

### 2026-10-27 — Revisão parcial do instalador DEV

- No checkout compartilhado, `.venv-desktop\Scripts\python.exe -m unittest tests.test_desktop_art tests.test_desktop_installer -v` passou (7/7). Os testes de segurança recusaram uma pasta alheia e um junction sem alterar arquivos sentinela.
- O executável congelado em `dist/GuildIdleManager/GuildIdleManager.exe --smoke` retornou código 0 e confirmou SQLite, Alembic, conteúdo inicial, catálogo de nomes e manifesto local de arte. Foi usado um arquivo de resultado temporário, fora dos saves reais.
- Em `%LOCALAPPDATA%` e `%TEMP%` isolados, o script distribuído em `dist/GuildIdleManager-DEV/Install-Desktop-Dev.ps1` instalou o pacote, repetiu a atualização gerenciada e preservou um save sentinela em `%LOCALAPPDATA%/GuildIdleManager/saves/`.
- Decisão: aceitar essas evidências do caminho de instalação por pasta; não aceitar ainda o arquivo único IExpress, o smoke sem Python/rede em máquina limpa, nem a janela nativa. Gate 2 e Gate 3 permanecem abertos.

### 2026-10-27 — Suíte desktop e lacuna de gameplay

- Revisão independente no checkout compartilhado: `APP_MODE=desktop .venv-desktop\Scripts\python.exe -m unittest discover -s tests -q` terminou com 63 testes em 179,501 s, sem falhas e com um teste ignorado. O runtime nativo permanece opt-in; o resultado da suíte não prova que a janela carregou.
- `tests/test_desktop_http_smoke.py` verifica GET de telas, referências de sprites e somente duas mutações auxiliares (tutorial e preferência de confirmação). Ainda não cobre os fluxos end-to-end de gameplay enumerados na seção 13 do GDD.
- Decisão: regressão automatizada atual verde, mas Gate 3 aberto até haver evidência isolada de cada sistema, loot manual e timers, além do runtime nativo e do instalador final.

### 2026-10-27 — Revisão dos commits do Trabalho 3

- Commits DEV examinados: `a5a601a` (manifesto de ícones), `d90737a` (transações de gameplay) e `e80f694` (pacote DEV). A matriz em `docs/WORK3_QA_DESKTOP.md` distingue o ZIP atual do Setup IExpress antigo.
- Verificação independente dos commits: `APP_MODE=desktop .venv-desktop\Scripts\python.exe -m unittest tests.test_desktop_art tests.test_desktop_http_smoke tests.test_desktop_installer -q` passou (9/9, 48,312 s). O teste ampliado de duas campanhas e transações de gameplay também passou isoladamente (22,825 s).
- O executável congelado `dist/GuildIdleManager/GuildIdleManager.exe --smoke` passou com diretório de trabalho e `%LOCALAPPDATA%` temporários e `PATH` limitado ao Windows/System32: código 0; confirmou SQLite, Alembic, conteúdo, nomes e manifesto. Isso não equivale a uma máquina limpa nem valida a janela.
- O ZIP atual não possui Setup IExpress correspondente: a geração atual saiu com código 1. O smoke nativo chega a `shown` e inicializa WebView2 em STA, mas a página fica em `about:blank`, sem `loaded`, DOM ou bridge. Decisão: aceitar evidências parciais dos commits; Gate 2 e Gate 3 continuam abertos.

### 2026-10-27 — Regressão integral após Work 3

- Verificação independente: `APP_MODE=desktop .venv-desktop\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -q` passou: 64 testes em 204,466 s, sem falhas, com 1 teste ignorado (smoke da janela nativa opt-in).
- A instrumentação provisória do smoke nativo chama `EnsureCoreWebView2Async` após o construtor do `EdgeChrome`, que já chama essa função. DEV foi orientado a repetir o diagnóstico sem essa segunda chamada e com uma execução sem monkey patch antes de concluir causa raiz.
- Esta evidência sustenta a regressão automatizada, não o carregamento da janela, a interação visual, o Setup atual ou a instalação em máquina limpa. Gate 2 e Gate 3 permanecem abertos.
