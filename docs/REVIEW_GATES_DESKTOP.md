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

### 2026-10-27 — Setup atual e isolamento do bloqueio nativo

- Commits DEV revisados: `8f2ae2e` (espera pelo IExpress e relatório de instalação) e `9f1ace9` (sonda nativa com diagnóstico opt-in). O checkout permaneceu na branch `feature/desktop-offline`, sem worktree.
- Hashes dos artefatos atuais conferidos independentemente: ZIP `7A8B728912385BACF690341E7B7939DBBAD5245F83E75763A8B36E8E528E4770`; Setup `E8E31FD998A907331474E19CFA8C7793E5271E92B08BFE80C5BCDECC0A501AB0`. O relatório DEV registra instalação e atualização isoladas, save preservado e 856 arquivos instalados idênticos ao bundle; isto não substitui a validação em outro Windows limpo.
- A sonda nativa sem instrumentação ainda falhou antes de `loaded`. Uma janela mínima com HTTP local e outra com HTML inline também não chegaram a `loaded`; a consulta de DOM não concluiu. FastAPI, CSP e dados do jogo não explicam sozinhos a falha. A causa no caminho pywebview/WebView2 deste host permanece indeterminada.
- Decisão: aceitar o Setup DEV como artefato reproduzível para o teste posterior, **não** aprovar o aplicativo ou o Gate 2/3 sem DOM, bridge, fluxo de campanha e evidência visual em janela própria.

### 2026-10-27 — Ciclo nativo em contexto Windows normal

- O smoke opt-in `tests.test_desktop_runtime` foi executado com `APP_MODE=desktop`, `GIM_RUN_DESKTOP_RUNTIME_SMOKE=1`, diagnósticos desligados e permissão elevada para sair do ambiente restrito de execução. Após a correção do retorno ao menu em andamento, duas execuções independentes passaram em 22,086 s e 20,186 s: janela, DOM do gerente, ponte JS/Python, criação de campanha, dashboard, retorno ao gerente, fechamento da janela, persistência e encerramento do servidor. Somente saves temporários foram usados.
- A mesma prova em execução restrita ainda ficou sem `loaded` e sem processo WebView2 visível; essa diferença de contexto explica por que os testes anteriores não sustentavam uma conclusão sobre a janela real. O primeiro ensaio fora do ambiente restrito chegou ao dashboard, mas falhou no retorno; o ajuste de submissão da rota desktop permitiu as duas execuções completas seguintes.
- Decisão: evidência positiva para o ciclo nativo do código-fonte; **Gate 2/3 ainda abertos** até commit da correção, regressão final, execução da janela no bundle instalado e conferência visual nas dimensões exigidas.

### 2026-10-27 — Inspeção visual da instalação temporária

- O executável reconstruído passou pelo healthcheck local e abriu a janela. A captura `docs/qa/desktop-dashboard.jpg` mostra a campanha renomeada e o dashboard com sprites reais, navegação e textos legíveis em largura ampla.
- A captura `docs/qa/desktop-minimum.jpg` revela rolagem horizontal no topo e cabeçalho excessivamente alto a 760 x 600; a navegação não está claramente acessível nessa largura. Este achado foi devolvido ao DEV para correção e nova captura.
- A escolha inicial do tutorial expôs outro POST fora do fluxo AJAX. A correção e o smoke nativo ampliado estão em andamento. **Gate visual e pacote instalado permanecem abertos.**

### 2026-10-27 — Revisão independente do pacote e commit `d7d85c7`

- O commit corrigiu os dois POSTs locais, o healthcheck do launcher congelado e a navegação compacta. Árvore de trabalho limpa na revisão. O ZIP e o Setup atuais têm SHA-256 `9B5AACC55E0EC5556B5DEAFE314D704F4174251A79700318593A649F0D2ACF67` e `531A2E6D1A1367C94F0B1D8537865C4FF337C86BF241B30B5722FDDC23569D7A`, respectivamente; ambos conferidos novamente.
- Suíte independente após o commit: `APP_MODE=desktop`, SQLite em memória, 64 testes em 198,888 s, zero falhas, um skip opt-in. O smoke nativo opt-in passou separadamente em 21,041 s: janela, DOM, bridge, criação, tutorial, retorno, fechamento e servidor. Somente perfil temporário foi usado.
- Capturas da instalação final em `docs/qa/` foram revisadas: dashboard amplo, mínimo 747 x 593, menu compacto aberto, Missões e gerenciador de campanhas. Não há rolagem horizontal no mínimo; o botão Campanhas e a navegação estão visíveis e operáveis. Aceite visual para essas superfícies e dimensões.
- Inspeção das entradas do ZIP não encontrou `.env`, `venv`, saves, logs, testes, `.git` ou `.aws`. O instalador foi validado em perfil local temporário; a instalação em **outro Windows limpo** ainda não foi executada. A documentação técnica de DEV estava desatualizada e foi devolvida para ajuste. A branch permanece aberta até a auditoria completa do GDD e o teste externo quando disponível.

### 2026-10-27 — Decisão desta rodada

- `README.md` e `docs/DEV_DESKTOP.md` foram corrigidos nos commits `3d6c524` e `1ecae6f`; contêm comandos de checkout DEV, suíte SQLite, build, instalação e recuperação, sem apagar variáveis pré-existentes do shell. O estado da branch está limpo.
- A versão DEV pode seguir para teste do usuário na máquina atual: servidor apenas em loopback, janela própria, campanha SQLite, arte local, instalador e atualização isolada demonstrados. Isto **não fecha o GDD**.
- Pendências de aceite integral: smoke em outro Windows limpo/WebView2 e passagem manual no aplicativo instalado por um fluxo de cada sistema da seção 13, incluindo timers e loot de sucesso/falha. A matriz de serviços e páginas HTTP cobre a lógica, mas não substitui essas interações de ponta a ponta. Manter `feature/desktop-offline` aberta; não integrar nem arquivar o trabalho.

### 2026-10-27 — QA nativa ampliada e revisão dos commits `cdfb1c6` / `5eea195`

- O QA em uma instalação DEV com perfil e campanha temporários revelou comparação entre timestamps SQLite sem fuso e UTC nas telas com timer. A correção normaliza os timestamps antes da renderização e em `claim_class_change`; os testes HTTP cobrem timers ativos de Missões, Masmorras, Mercado, Profissões, Troca de Classe, Ferreiro, painel, Taverna e Docas. A tela distingue chance base da chance final limitada a 95%, sem alterar o RNG.
- O relatório `docs/WORK3_QA_DESKTOP.md` registra passagem manual no aplicativo instalado por contratação, equipamento, construção, missão com sucesso e falha, Masmorra, Chefe, Mercado, Docas, profissão, forja, desmontagem, refino, progresso, conquista e Codex. Conferi que todos os links de capturas `docs/qa/work3-*.jpg` citados no relatório existem. Inspecionei visualmente as capturas da chance base e do refino.
- Regressão independente após os commits: 67 testes passaram em 222,457 s; 1 teste opt-in foi ignorado pela suíte e passou separadamente em 29,662 s com janela, DOM e fluxo de campanha. `git diff f880781..HEAD --check` não apontou erros. A branch `feature/desktop-offline` está limpa.
- Hashes SHA-256 conferidos novamente: ZIP `88D69551535A8A16688D57A9DBB7FF2D4F8EE84B665095027997F8ECD84F883F`; Setup `865ADE6AB3F4B9AC98F4479EB826EAFB19E2F04B8B1858BD2B63B3FC8EE644BE`. Inspeção das entradas do ZIP não encontrou `.env`, saves, logs, testes, `.git` nem `.aws`.
- Decisão: a lacuna de passagem manual dos sistemas da seção 13 está sanada neste host. O GDD continua **não aceito integralmente** até instalação/smoke em outro Windows limpo e auditoria final item a item; manter a branch aberta, sem merge.

### 2026-10-27 — Auditoria do GDD e veto visual da DA

- A matriz item a item está em `docs/GDD_ACCEPTANCE_AUDIT.md`. A auditoria encontrou ausência de aviso de migração bem-sucedida; o commit `3943824` acrescentou o aviso acessível na chegada ao dashboard, confirmação de backup e teste de exibição única com campanha temporária. DEV informou 67 testes OK, 1 opt-in ignorado, smoke HTTP/pacote congelado e instalação em perfil temporário. Os hashes SHA-256 do novo ZIP e Setup conferidos independentemente são `7D7EAD1DF4AA64AC014449B851533E8199853188F795E8C987CD4F72E83560C8` e `DF24AE8B601472633F86345D47EFDFBFAAE0B1C32743A9442C753997C3ED2001`.
- A DA revisou `docs/art_direction/DESKTOP_VISUAL_SYSTEM.md` e capturas instaladas: reprovou o gate §7.1. Os sprites estão presentes, mas a paleta marrom, Trebuchet e a composição antiga dominam as telas; a nova linguagem azul-petróleo/turquesa das prévias não foi aplicada ao aplicativo real. O ajuste foi encaminhado ao DEV no mesmo checkout, sem tocar em mecânicas ou saves.
- A branch permanece aberta. Além da integração visual e nova revisão da DA, ainda falta smoke em outro Windows limpo, sem Python/PostgreSQL e sem rede. Este host não dispõe de Windows Sandbox.

### 2026-10-27 — Revisão da identidade visual integrada

- O commit `3371ab4` aplicou a linguagem Sala de Comando somente ao modo desktop. A revisão estática da DA encontrou hover dourado indevido em botões secundários e destrutivos; `1771540` corrigiu esses estados. Minha revisão encontrou o mesmo problema no botão Voltar; `e4a7fa3` separou Voltar/Campanhas e o botão textual do tutorial. Revisei o diff e executei `tests.test_desktop_art`: 9 testes passaram.
- A suíte completa independente no commit visual inicial passou: 70 testes executados, zero falhas e 1 smoke nativo opt-in ignorado. O DEV executou esse smoke à parte no contexto elevado e reportou passagem. `git diff HEAD~1..HEAD --check` não apontou erros no commit visual.
- Após os fixes, o ZIP e o Setup foram reconstruídos. Conferi independentemente SHA-256 do ZIP `A568641FC0D237E84EC7CB072193C401E08985C307535842F63A9FF6777F9948`, Setup `9C2514C4EE860FC46879EFCCB4FD30248D535460AF1044D8C93E33B5C58F4B52` e CSS no fonte, dist e ZIP `C0FCCCAFDA855DC87469D44C694B50DA3C271070A512F83D54B8B5E0CFD05666`. A inspeção das 882 entradas do ZIP não encontrou `.env`, saves, logs, testes, `.git` ou `.aws`.
- A DA não apontou outra regressão concreta no código ou no mapeamento de arte. O usuário decidiu realizar pessoalmente a validação visual em tela posteriormente. O controle de UI não conseguiu interagir com a janela elevada do Setup final, então não há captura final nem alegação de aceite visual instalado. A instalação/smoke em outro Windows limpo também segue pendente. Manter `feature/desktop-offline` aberta, sem merge.
