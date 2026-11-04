param(
    [ValidateSet('DEV', 'stable', 'beta')]
    [string]$Channel = 'DEV',
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'
# IExpress can inherit a working directory from the caller that points inside
# the installation being replaced. Move to the extracted package before any
# install operations so Windows does not keep the target directory in use.
Set-Location -LiteralPath $PSScriptRoot
$appVersionFile = Join-Path $PSScriptRoot 'gim-app-version.txt'
if (-not (Test-Path -LiteralPath $appVersionFile -PathType Leaf)) {
    throw "Versao esperada do pacote nao encontrada: $appVersionFile"
}
$appVersion = (Get-Content -LiteralPath $appVersionFile -Raw).Trim()
if ($appVersion -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$') {
    throw "Versao esperada do pacote invalida: $appVersion"
}
$setupResultFile = $env:GIM_SETUP_RESULT
$expectedLocalAppData = $env:GIM_SETUP_EXPECTED_LOCALAPPDATA
if ($setupResultFile) {
    if (-not $expectedLocalAppData) {
        throw 'O handoff verificado nao forneceu o perfil de destino esperado.'
    }
    $actualLocalAppData = [System.IO.Path]::GetFullPath($env:LOCALAPPDATA)
    if (-not [string]::Equals($actualLocalAppData, [System.IO.Path]::GetFullPath($expectedLocalAppData), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "O perfil de destino do Setup diverge do perfil aprovado: $actualLocalAppData"
    }
}
$source = Join-Path $PSScriptRoot 'GuildIdleManager'
$extractedBundle = $null
if (-not (Test-Path -LiteralPath (Join-Path $source 'GuildIdleManager.exe') -PathType Leaf)) {
    $archive = Join-Path $PSScriptRoot ("GuildIdleManager-$Channel.zip")
    if (Test-Path -LiteralPath $archive -PathType Leaf) {
        $extractedBundle = Join-Path $env:TEMP ("GuildIdleManager-$Channel-" + [Guid]::NewGuid().ToString('N'))
        Expand-Archive -LiteralPath $archive -DestinationPath $extractedBundle
        $source = Join-Path $extractedBundle 'GuildIdleManager'
    }
}
$exe = Join-Path $source 'GuildIdleManager.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Pacote Guild Idle Manager $Channel nao encontrado ao lado deste instalador: $source"
}

$programs = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs'))
$target = Join-Path $programs 'GuildIdleManager'
$markerName = '.gim-desktop-install.json'
$markerValue = (@{ product = 'org.guildidlemanager.desktop'; channel = $Channel; version = $appVersion } | ConvertTo-Json -Compress)

function Assert-NoReparsePoint([string]$Path) {
    $resolved = [System.IO.Path]::GetFullPath($Path)
    $current = $resolved
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Instalacao recusada: caminho com junction/reparse point: $current"
            }
        }
        $parent = [System.IO.Directory]::GetParent($current)
        if (-not $parent) { break }
        $current = $parent.FullName
    }
}

function Assert-ManagedInstall([string]$Path) {
    Assert-NoReparsePoint $Path
    $marker = Join-Path $Path $markerName
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        throw "Instalacao recusada: a pasta de destino existe sem marcador Guild Idle Manager: $Path"
    }
    Assert-NoReparsePoint $marker
    $identity = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ($identity.product -ne 'org.guildidlemanager.desktop' -or $identity.channel -ne $Channel) {
        throw "Instalacao recusada: o marcador de $Path nao identifica uma instalacao $Channel gerenciada."
    }
}

Assert-NoReparsePoint $programs
$targetExists = Test-Path -LiteralPath $target
if ($targetExists) { Assert-ManagedInstall $target }

$token = [Guid]::NewGuid().ToString('N')
$staging = Join-Path $programs "GuildIdleManager.stage-$token"
$backup = Join-Path $programs "GuildIdleManager.backup-$token"
$result = Join-Path $env:TEMP "GuildIdleManager-smoke-$token.txt"
$backupCreated = $false
function Copy-DirectoryContents([string]$SourceDirectory, [string]$DestinationDirectory) {
    Get-ChildItem -LiteralPath $SourceDirectory -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $DestinationDirectory -Recurse -Force
    }
}
function Clear-DirectoryContents([string]$Directory) {
    Get-ChildItem -LiteralPath $Directory -Force | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Path $programs -Force | Out-Null
try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    Assert-NoReparsePoint $staging
    Copy-Item -Path (Join-Path $source '*') -Destination $staging -Recurse -Force

    $versionProbe = Join-Path $env:TEMP ("GuildIdleManager-version-$token.txt")
    $env:GIM_VERSION_RESULT = $versionProbe
    try {
        $versionCheck = Start-Process -FilePath (Join-Path $staging 'GuildIdleManager.exe') -ArgumentList '--version' -PassThru -Wait -WindowStyle Hidden
    } finally {
        Remove-Item Env:GIM_VERSION_RESULT -ErrorAction SilentlyContinue
    }
    if ($versionCheck.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $versionProbe -PathType Leaf)) {
        throw 'O aplicativo empacotado nao respondeu a verificacao de versao.'
    }
    $actualVersion = (Get-Content -LiteralPath $versionProbe -Raw).Trim()
    Remove-Item -LiteralPath $versionProbe -Force
    if ($actualVersion -ne $appVersion) {
        throw "Versao embutida $actualVersion diverge da versao declarada no pacote $appVersion."
    }

    $env:GIM_SMOKE_RESULT = $result
    $smoke = Start-Process -FilePath (Join-Path $staging 'GuildIdleManager.exe') -ArgumentList '--smoke' -PassThru -Wait -WindowStyle Hidden
    if ($smoke.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $result -PathType Leaf)) {
        throw 'O teste offline da copia de instalacao falhou; a versao instalada foi preservada.'
    }
    if ((Get-Content -LiteralPath $result -Raw) -notmatch '^PASS:') {
        throw 'O teste offline nao confirmou os arquivos e dados incluidos no pacote.'
    }

    $markerPath = Join-Path $staging $markerName
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($markerPath, $markerValue, $utf8NoBom)
    if ($targetExists) {
        New-Item -ItemType Directory -Path $backup | Out-Null
        Copy-DirectoryContents $target $backup
        Assert-ManagedInstall $backup
        $backupCreated = $true
        # Keep the target directory in place. Windows may reject renaming it
        # while an updater or shell process still has the directory open.
        Clear-DirectoryContents $target
        Copy-DirectoryContents $staging $target
    } else {
        Move-Item -LiteralPath $staging -Destination $target
    }
    if (Test-Path -LiteralPath $backup) {
        Assert-ManagedInstall $backup
        $resolvedBackup = [System.IO.Path]::GetFullPath($backup)
        if (-not $resolvedBackup.StartsWith(($programs.TrimEnd('\') + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Instalacao recusada: o backup temporario saiu da pasta Programs.'
        }
        Remove-Item -LiteralPath $resolvedBackup -Recurse -Force
    }

    if (-not $NoShortcut -and $env:GIM_SETUP_NO_SHORTCUT -ne '1') {
        $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) "Guild Idle Manager $Channel.lnk"
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = Join-Path $target 'GuildIdleManager.exe'
        $shortcut.WorkingDirectory = $target
        $shortcut.IconLocation = "$($shortcut.TargetPath),0"
        $shortcut.Description = "Guild Idle Manager - canal $Channel"
        $shortcut.Save()
        Write-Output "Atalho criado em $shortcutPath"
    }

    if ($setupResultFile) {
        $setupResult = "SUCCESS|$appVersion|$target|$actualLocalAppData"
        [System.IO.File]::WriteAllText($setupResultFile, $setupResult, [System.Text.UTF8Encoding]::new($false))
    }

    Write-Output "Instalacao concluida em $target"
} catch {
    if ($backupCreated -and (Test-Path -LiteralPath $backup)) {
        try {
            if (Test-Path -LiteralPath $target) { Clear-DirectoryContents $target }
            else { New-Item -ItemType Directory -Path $target | Out-Null }
            Copy-DirectoryContents $backup $target
            Assert-ManagedInstall $target
            Remove-Item -LiteralPath $backup -Recurse -Force
        } catch {
            # Preserve the verified backup if rollback cannot restore in place.
        }
    }
    if ($setupResultFile) {
        $failure = "ERROR|$($_.Exception.Message)|$($_.InvocationInfo.ScriptName):$($_.InvocationInfo.ScriptLineNumber)|$($_.ScriptStackTrace)"
        [System.IO.File]::WriteAllText($setupResultFile, $failure, [System.Text.UTF8Encoding]::new($false))
    }
    throw
} finally {
    Remove-Item Env:GIM_SMOKE_RESULT -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $result) { Remove-Item -LiteralPath $result -Force }
    if (Test-Path -LiteralPath $staging) {
        $resolvedStaging = [System.IO.Path]::GetFullPath($staging)
        if ($resolvedStaging.StartsWith(($programs.TrimEnd('\') + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
            Assert-NoReparsePoint $resolvedStaging
            Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
        }
    }
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $target)) {
        Assert-ManagedInstall $backup
        Move-Item -LiteralPath $backup -Destination $target
    }
    if ($extractedBundle -and (Test-Path -LiteralPath $extractedBundle)) {
        $resolvedExtractedBundle = [System.IO.Path]::GetFullPath($extractedBundle)
        $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        if ($resolvedExtractedBundle.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedExtractedBundle -Recurse -Force
        }
    }
}
