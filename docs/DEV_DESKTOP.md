# Launcher desktop DEV

O launcher roda a cópia deste checkout em uma janela pywebview. Ele não usa PostgreSQL, não instala pacotes ao abrir e grava saves, backups, âncoras de tempo e logs em `%LOCALAPPDATA%\GuildIdleManager`.

## Gerar instalador DEV offline

Com PyInstaller instalado no `.venv-desktop`, gere o Setup e o ZIP portátil em uma pasta nova e isolada dentro de `dist\staging`. O build não substitui pacotes anteriores:

```powershell
Set-Location 'C:\Users\vitor\Guild Idle Manager\App GIM'
.\scripts\build_desktop_dev.ps1
```

O comando informa o caminho da pasta candidata e preserva nela `GuildIdleManager-DEV-Setup.exe`, `GuildIdleManager-DEV.zip` e o bundle. Para escolher um nome determinístico, use `-OutputRoot 'dist\staging\gim-candidate'`. Os comandos abaixo selecionam o candidato mais recente para smoke e teste isolado do instalador.

Consulte [WORK3_QA_DESKTOP.md](WORK3_QA_DESKTOP.md) para os hashes dos artefatos e as evidências. Em 2026-10-27, o smoke nativo confirmou `shown`, `loaded`, DOM e bridge em duas execuções; a instalação congelada também passou pelo fluxo de campanha e pelo smoke offline. Isso fecha a pendência de renderização inicial registrada anteriormente. A validação do instalador e o layout estreito também estão documentados ali.

O instalador inclui o executável e arquivos locais de templates, imagens, estilos, JavaScript, migrations Alembic e catálogo de nomes. Para instalar sem PostgreSQL ou conexão de rede, execute o Setup; ele valida a cópia temporária offline antes de trocar a instalação em `%LOCALAPPDATA%\Programs\GuildIdleManager` e cria um atalho na área de trabalho. Os saves continuam em `%LOCALAPPDATA%\GuildIdleManager\saves`, fora da pasta do aplicativo.

O bundle também tem um smoke offline sem janela para validar a cópia empacotada, as migrations SQLite, o conteúdo inicial e o manifesto de arte, sem usar a rede:

```powershell
$env:GIM_SMOKE_RESULT = Join-Path $env:TEMP ('gim-desktop-bundle-smoke-' + [Guid]::NewGuid().ToString('N') + '.txt')
$candidate = Get-ChildItem .\dist\staging -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'GuildIdleManager\GuildIdleManager.exe') } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$bundle = Join-Path $candidate.FullName 'GuildIdleManager\GuildIdleManager.exe'
& $bundle --smoke
Get-Content $env:GIM_SMOKE_RESULT
Remove-Item $env:GIM_SMOKE_RESULT
Remove-Item Env:GIM_SMOKE_RESULT

$env:GIM_TEST_BUILT_PACKAGE = Join-Path $candidate.FullName 'GuildIdleManager-DEV'
& .\.venv-desktop\Scripts\python.exe -m unittest tests.test_desktop_installer
Remove-Item Env:GIM_TEST_BUILT_PACKAGE
```

Para validar novamente em um computador limpo, extraia o ZIP, execute o instalador e abra `Guild Idle Manager DEV`. O aplicativo não consulta serviços externos durante a abertura. Atualizações DEV substituem os arquivos do aplicativo no diretório de instalação; os saves permanecem separados. O canal padrão aponta para `Vitor41/guild_idle_manager`, agora público; a instalação 0.3.1, sem chave pública, precisa primeiro do Setup bootstrap 0.3.2 instalado manualmente. A nova instalação só verificará releases depois da publicação da primeira release DEV assinada. Para assinatura e configuração do build, consulte [UPDATE_ARCHITECTURE.md](UPDATE_ARCHITECTURE.md).

## Preparação única neste checkout

No PowerShell, na pasta `App GIM`. Neste host, use o Python do checkout pai somente para criar o ambiente; instale e execute as dependências desktop dentro de `.venv-desktop`. O Python pai não é usado para rodar a aplicação ou os testes:

```powershell
& 'C:\Users\vitor\Guild Idle Manager\.venv\Scripts\python.exe' -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop-dev.txt
```

`requirements-desktop-dev.txt` fixa as versões testadas do runtime, pywebview e PyInstaller para reproduzir o bundle. Atualizações devem alterar esses pins deliberadamente e repetir os testes desktop, smoke offline e build antes de publicar um novo pacote. O ambiente e os pacotes ficam em `App GIM\.venv-desktop`; nenhum pacote é instalado no `.venv` do checkout pai. `Iniciando_jogo_dev.bat` nunca cria ambiente nem instala dependências.

Para rodar os testes do desktop, defina o modo antes de importar o aplicativo:

```powershell
$env:APP_MODE = 'desktop'
$env:DATABASE_URL = 'sqlite:///:memory:'
.\.venv-desktop\Scripts\python.exe -m unittest discover -s tests -v
```

O resultado integral mais recente registrou 72 testes executados, com 71 aprovados e um smoke nativo opt-in ignorado pela descoberta normal. O smoke nativo foi executado separadamente no contexto Windows normal e passou; veja a tabela de execução em [WORK3_QA_DESKTOP.md](WORK3_QA_DESKTOP.md).

O smoke nativo de janela é opt-in porque precisa abrir uma janela Windows real. Ele usa uma pasta temporária, espera `shown` e `loaded` do pywebview, confere o DOM do gerente e do dashboard, cria uma campanha pelo formulário nativo, retorna ao gerente, destrói a janela pelo próprio objeto pywebview e verifica evento `closed`, encerramento do servidor e metadados da campanha:

```powershell
$env:APP_MODE = 'desktop'
$env:GIM_RUN_DESKTOP_RUNTIME_SMOKE = '1'
.\.venv-desktop\Scripts\python.exe -m unittest tests.test_desktop_runtime -v
```

O smoke HTTP local e os testes de campanha cobrem persistência SQLite, abertura e fechamento de saves, migração Alembic, recuperação por backup, exportação e importação. O smoke nativo também confirmou o carregamento do WebView, DOM, bridge e retorno ao menu. As capturas em [WORK3_QA_DESKTOP.md](WORK3_QA_DESKTOP.md) pertencem a builds anteriores; a validação visual do Setup atual em tela será feita pelo usuário.

## Abrir

```powershell
.\.venv-desktop\Scripts\python.exe -m app.desktop
```

Ou execute `Iniciando_jogo_dev.bat`. O launcher escolhe uma porta local disponível, mantém o servidor ligado em `127.0.0.1`, aguarda `/desktop/health` e abre a janela. A saída técnica fica em `%LOCALAPPDATA%\GuildIdleManager\logs\desktop.log`.

### Diagnóstico de ações do jogo

Ao designar coleta ou iniciar/preparar uma oferta, o app registra rota, ação, horário UTC, status HTTP e uma referência em `%LOCALAPPDATA%\GuildIdleManager\logs\gameplay-actions.log`. Exceções inesperadas incluem stack trace sanitizado. O arquivo não registra corpo do formulário, senha, cookie, token ou cabeçalho de autorização. A rotação mantém até 1 MB no arquivo atual e dois arquivos anteriores (`gameplay-actions.log.1` e `.2`).

Quando uma ação falhar, a tela mostra a referência e o caminho do arquivo. Para anexar o diagnóstico, feche o jogo e envie `gameplay-actions.log`; se necessário, inclua `.1` e `.2` também. A pasta é independente do diretório instalado e dos saves, então funciona com o app congelado sem gravar em `Program Files`.

Fechar a janela pede confirmação e encerra o servidor. `Ctrl+R` atualiza a página atual; CSS, JavaScript e templates são enviados sem cache. Mudanças Python exigem reiniciar o launcher.

## Dados

- Saves: `%LOCALAPPDATA%\GuildIdleManager\saves`
- Backups: `%LOCALAPPDATA%\GuildIdleManager\backups`
- Âncoras DPAPI: `%LOCALAPPDATA%\GuildIdleManager\clock-guard`
- Logs: `%LOCALAPPDATA%\GuildIdleManager\logs`
- Exportações: escolha o destino no diálogo nativo de arquivos.

### Backup e recuperação

No gerenciador de campanhas, use **Criar backup** para salvar uma cópia consistente da campanha. Para restaurar, use **Restaurar backup** no cartão da campanha e escolha o arquivo desejado; o aplicativo cria um backup de segurança antes de substituir o progresso. Se um save não puder ser aberto, ele aparece em **Arquivos que precisam de recuperação** e pode ser restaurado a partir de um backup compatível. Mantenha o aplicativo fechado antes de copiar arquivos manualmente.

Os arquivos ficam em `%LOCALAPPDATA%\GuildIdleManager\saves` e `%LOCALAPPDATA%\GuildIdleManager\backups`. Estes comandos mostram os arquivos e abrem a pasta de backups no Explorer:

```powershell
$data = Join-Path $env:LOCALAPPDATA 'GuildIdleManager'
Get-ChildItem (Join-Path $data 'saves')
Get-ChildItem (Join-Path $data 'backups') -Recurse
Start-Process explorer.exe (Join-Path $data 'backups')
```

Para manter uma cópia externa, feche o jogo e copie a pasta de dados inteira para um destino seguro. Para recuperar, abra o aplicativo e use **Restaurar backup** no gerenciador; não substitua um `.db` aberto manualmente.

```powershell
$data = Join-Path $env:LOCALAPPDATA 'GuildIdleManager'
$destination = Join-Path $env:USERPROFILE 'Documents\GuildIdleManager-backup'
Copy-Item $data $destination -Recurse
```

O servidor só aceita o Host e a origem definidos pelo launcher, bloqueia requisições cross-site e não tem middleware de sessão no modo desktop. O launcher fixa o bind em IPv4 loopback.
