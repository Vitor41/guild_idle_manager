# Launcher desktop DEV

O launcher roda a cópia deste checkout em uma janela pywebview. Ele não usa PostgreSQL, não instala pacotes ao abrir e grava saves, backups, âncoras de tempo e logs em `%LOCALAPPDATA%\GuildIdleManager`.

## Gerar instalador DEV offline

Com PyInstaller instalado no `.venv-desktop`, gere `dist\GuildIdleManager-DEV-Setup.exe` e o ZIP portátil ao lado dele:

```powershell
Set-Location 'C:\Users\vitor\Guild Idle Manager\App GIM'
.\scripts\build_desktop_dev.ps1
```

Consulte [WORK3_QA_DESKTOP.md](WORK3_QA_DESKTOP.md) para o estado dos gates. A geração atual do Setup IExpress não está aprovada; distribua apenas um executável Setup que tenha sido criado a partir do ZIP atual e passe os testes de primeira instalação e atualização.

O instalador inclui o executável e arquivos locais de templates, imagens, estilos, JavaScript, migrations Alembic e catálogo de nomes. Para instalar sem PostgreSQL ou conexão de rede, execute o Setup; ele valida a cópia temporária offline antes de trocar a instalação em `%LOCALAPPDATA%\Programs\GuildIdleManager` e cria um atalho na área de trabalho. Os saves continuam em `%LOCALAPPDATA%\GuildIdleManager\saves`, fora da pasta do aplicativo.

O bundle também tem um smoke offline sem janela para validar a cópia empacotada, as migrations SQLite, o conteúdo inicial e o manifesto de arte, sem usar a rede:

```powershell
$env:GIM_SMOKE_RESULT = Join-Path $env:TEMP ('gim-desktop-bundle-smoke-' + [Guid]::NewGuid().ToString('N') + '.txt')
.\dist\GuildIdleManager\GuildIdleManager.exe --smoke
Get-Content $env:GIM_SMOKE_RESULT
Remove-Item $env:GIM_SMOKE_RESULT
Remove-Item Env:GIM_SMOKE_RESULT
```

Para validar novamente em um computador limpo, extraia o ZIP, execute o instalador e abra `Guild Idle Manager DEV`. O aplicativo não consulta serviços externos durante a abertura. Atualizações DEV substituem os arquivos do aplicativo no diretório de instalação; os saves permanecem separados.

## Preparação única neste checkout

No PowerShell, em `C:\Users\vitor\Guild Idle Manager\App GIM` (este host não tem o comando `py`; usa-se o Python 3.12 já disponível no checkout pai apenas para criar o ambiente novo):

```powershell
& 'C:\Users\vitor\Guild Idle Manager\.venv\Scripts\python.exe' -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop-dev.txt
```

`requirements-desktop-dev.txt` fixa as versões testadas do runtime, pywebview e PyInstaller para reproduzir o bundle. Atualizações devem alterar esses pins deliberadamente e repetir os testes desktop, smoke offline e build antes de publicar um novo pacote. O ambiente e os pacotes ficam em `App GIM\.venv-desktop`; nenhum pacote é instalado no `.venv` do checkout pai. `Iniciando_jogo_dev.bat` nunca cria ambiente nem instala dependências.

Para rodar os testes do desktop, defina o modo antes de importar o aplicativo:

```powershell
$env:APP_MODE = 'desktop'
.\.venv-desktop\Scripts\python.exe -m unittest tests.test_clock_guard tests.test_desktop_bridge tests.test_desktop_security tests.test_desktop_http_smoke tests.test_campaign_service -q
```

O smoke nativo de janela é opt-in porque precisa abrir uma janela Windows real. Ele usa uma pasta temporária, espera `shown` e `loaded` do pywebview, confere o DOM do gerente e do dashboard, cria uma campanha pelo formulário nativo, retorna ao gerente, destrói a janela pelo próprio objeto pywebview e verifica evento `closed`, encerramento do servidor e metadados da campanha:

```powershell
$env:APP_MODE = 'desktop'
$env:GIM_RUN_DESKTOP_RUNTIME_SMOKE = '1'
.\.venv-desktop\Scripts\python.exe -m unittest tests.test_desktop_runtime -v
```

O smoke HTTP local e os testes de campanha cobrem persistência SQLite, abertura e fechamento de saves, migração Alembic, recuperação por backup, exportação e importação. O smoke HTTP não substitui a validação visual nativa do WebView; mantenha o gate visual aberto enquanto `shown`, `loaded` e o DOM nativo não forem confirmados na máquina-alvo.

## Abrir

```powershell
.\.venv-desktop\Scripts\python.exe -m app.desktop
```

Ou execute `Iniciando_jogo_dev.bat`. O launcher escolhe uma porta local disponível, mantém o servidor ligado em `127.0.0.1`, aguarda `/desktop/health` e abre a janela. A saída técnica fica em `%LOCALAPPDATA%\GuildIdleManager\logs\desktop.log`.

Fechar a janela pede confirmação e encerra o servidor. `Ctrl+R` atualiza a página atual; CSS, JavaScript e templates são enviados sem cache. Mudanças Python exigem reiniciar o launcher.

## Dados

- Saves: `%LOCALAPPDATA%\GuildIdleManager\saves`
- Backups: `%LOCALAPPDATA%\GuildIdleManager\backups`
- Âncoras DPAPI: `%LOCALAPPDATA%\GuildIdleManager\clock-guard`
- Logs: `%LOCALAPPDATA%\GuildIdleManager\logs`
- Exportações: escolha o destino no diálogo nativo de arquivos.

O servidor só aceita o Host e a origem definidos pelo launcher, bloqueia requisições cross-site e não tem middleware de sessão no modo desktop. O launcher fixa o bind em IPv4 loopback.
When running the desktop-focused test modules from PowerShell, set `$env:APP_MODE = 'desktop'` first so the intentionally PostgreSQL-free environment does not load the web database default.
