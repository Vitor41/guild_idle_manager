param([switch]$NoShortcut)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'GuildIdleManager'
$extractedBundle = $null
if (-not (Test-Path -LiteralPath (Join-Path $source 'GuildIdleManager.exe') -PathType Leaf)) {
    $archive = Join-Path $PSScriptRoot 'GuildIdleManager-DEV.zip'
    if (Test-Path -LiteralPath $archive -PathType Leaf) {
        $extractedBundle = Join-Path $env:TEMP ("GuildIdleManager-DEV-" + [Guid]::NewGuid().ToString('N'))
        Expand-Archive -LiteralPath $archive -DestinationPath $extractedBundle
        $source = Join-Path $extractedBundle 'GuildIdleManager'
    }
}
$exe = Join-Path $source 'GuildIdleManager.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Pacote Guild Idle Manager DEV nao encontrado ao lado deste instalador: $source"
}

$programs = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs'))
$target = Join-Path $programs 'GuildIdleManager'
$markerName = '.gim-desktop-install.json'
$markerValue = '{"product":"org.guildidlemanager.desktop","channel":"DEV"}'

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
    if ($identity.product -ne 'org.guildidlemanager.desktop' -or $identity.channel -ne 'DEV') {
        throw "Instalacao recusada: o marcador de $Path nao identifica uma instalacao DEV gerenciada."
    }
}

Assert-NoReparsePoint $programs
$targetExists = Test-Path -LiteralPath $target
if ($targetExists) { Assert-ManagedInstall $target }

$token = [Guid]::NewGuid().ToString('N')
$staging = Join-Path $programs "GuildIdleManager.stage-$token"
$backup = Join-Path $programs "GuildIdleManager.backup-$token"
$result = Join-Path $env:TEMP "GuildIdleManager-smoke-$token.txt"
New-Item -ItemType Directory -Path $programs -Force | Out-Null
try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    Assert-NoReparsePoint $staging
    Copy-Item -Path (Join-Path $source '*') -Destination $staging -Recurse -Force

    $env:GIM_SMOKE_RESULT = $result
    $smoke = Start-Process -FilePath (Join-Path $staging 'GuildIdleManager.exe') -ArgumentList '--smoke' -PassThru -Wait -WindowStyle Hidden
    if ($smoke.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $result -PathType Leaf)) {
        throw 'O teste offline da copia de instalacao falhou; a versao instalada foi preservada.'
    }
    if ((Get-Content -LiteralPath $result -Raw) -notmatch '^PASS:') {
        throw 'O teste offline nao confirmou os arquivos e dados incluidos no pacote.'
    }

    if ($targetExists) {
        Move-Item -LiteralPath $target -Destination $backup
        Assert-ManagedInstall $backup
    }
    $markerPath = Join-Path $staging $markerName
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($markerPath, $markerValue, $utf8NoBom)
    try {
        Move-Item -LiteralPath $staging -Destination $target
    } catch {
        if ($targetExists -and (Test-Path -LiteralPath $backup)) {
            Move-Item -LiteralPath $backup -Destination $target
        }
        throw
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
        $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Guild Idle Manager DEV.lnk'
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = Join-Path $target 'GuildIdleManager.exe'
        $shortcut.WorkingDirectory = $target
        $shortcut.IconLocation = "$($shortcut.TargetPath),0"
        $shortcut.Description = 'Guild Idle Manager - build DEV local e offline'
        $shortcut.Save()
        Write-Output "Atalho criado em $shortcutPath"
    }

    Write-Output "Instalacao concluida em $target"
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
