# Launcher desktop DEV

O launcher roda a cópia deste checkout em uma janela pywebview. Ele não usa PostgreSQL, não instala pacotes ao abrir e grava saves, backups, âncoras de tempo e logs em `%LOCALAPPDATA%\GuildIdleManager`.

## Preparação única neste checkout

No PowerShell, em `C:\Users\vitor\Guild Idle Manager\App GIM` (este host não tem o comando `py`; usa-se o Python 3.12 já disponível no checkout pai apenas para criar o ambiente novo):

```powershell
& 'C:\Users\vitor\Guild Idle Manager\.venv\Scripts\python.exe' -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop-dev.txt
```

O ambiente e seus pacotes ficam inteiramente em `App GIM\.venv-desktop`; nenhum pacote é instalado no `.venv` do checkout pai. `Iniciando_jogo_dev.bat` nunca cria ambiente nem instala dependências.

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
