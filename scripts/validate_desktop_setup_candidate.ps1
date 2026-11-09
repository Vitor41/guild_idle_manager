param(
    [Parameter(Mandatory = $true)]
    [string]$SetupPath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion,
    [Parameter(Mandatory = $true)]
    [string]$ProfileRoot,
    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,
    [Parameter(Mandatory = $true)]
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$setup = [System.IO.Path]::GetFullPath($SetupPath)
$profile = [System.IO.Path]::GetFullPath($ProfileRoot)
$runnerTemp = [System.IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'
$evidence = [System.IO.Path]::GetFullPath($EvidenceDirectory)
$python = [System.IO.Path]::GetFullPath($PythonPath)
if (-not $profile.StartsWith($runnerTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'O perfil de smoke precisa ficar dentro de RUNNER_TEMP.'
}
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) { throw "Setup ausente: $setup" }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python ausente: $python" }

New-Item -ItemType Directory -Path $profile,$evidence -Force | Out-Null
$localAppData = Join-Path $profile 'LocalAppData'
$appData = Join-Path $profile 'Roaming'
$tempRoot = Join-Path $profile 'Temp'
New-Item -ItemType Directory -Path $localAppData,$appData,$tempRoot -Force | Out-Null

$environmentNames = @(
    'LOCALAPPDATA', 'APPDATA', 'TEMP', 'TMP', 'APP_MODE', 'GIM_SMOKE_TEMP_DIR',
    'GIM_SMOKE_RESULT', 'GIM_LAUNCHER_SMOKE_RESULT', 'GIM_SETUP_RESULT',
    'GIM_SETUP_EXPECTED_LOCALAPPDATA', 'GIM_SETUP_NO_SHORTCUT', 'GIM_VERSION_RESULT',
    'GIM_SETUP_FIXTURE_SAVE_ROOT'
)
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

function Invoke-CandidateSmoke([string]$Executable, [string]$Argument, [string]$ResultVariable, [string]$ResultPath, [string]$ExpectedPrefix, [int]$TimeoutMs) {
    [Environment]::SetEnvironmentVariable($ResultVariable, $ResultPath, 'Process')
    $process = Start-Process -FilePath $Executable -ArgumentList $Argument -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit($TimeoutMs)) {
        $running = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
        if ($running -and $running.Path -and [IO.Path]::GetFullPath($running.Path).Equals([IO.Path]::GetFullPath($Executable), [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $running.Id -Force
        }
        throw "Smoke $Argument excedeu o limite de $TimeoutMs ms."
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        $detail = if (Test-Path -LiteralPath $ResultPath) { Get-Content -LiteralPath $ResultPath -Raw } else { 'sem marcador de resultado' }
        throw "Smoke $Argument falhou (exit=$($process.ExitCode)): $detail"
    }
    $result = Get-Content -LiteralPath $ResultPath -Raw
    if ($result -notmatch $ExpectedPrefix) { throw "Smoke $Argument não confirmou o resultado esperado: $result" }
    return $result.Trim()
}

try {
    [Environment]::SetEnvironmentVariable('LOCALAPPDATA', $localAppData, 'Process')
    [Environment]::SetEnvironmentVariable('APPDATA', $appData, 'Process')
    [Environment]::SetEnvironmentVariable('TEMP', $tempRoot, 'Process')
    [Environment]::SetEnvironmentVariable('TMP', $tempRoot, 'Process')
    [Environment]::SetEnvironmentVariable('GIM_SMOKE_TEMP_DIR', $tempRoot, 'Process')
    [Environment]::SetEnvironmentVariable('APP_MODE', 'desktop', 'Process')

    $saveRoot = Join-Path $localAppData 'GuildIdleManager\saves'
    New-Item -ItemType Directory -Path $saveRoot -Force | Out-Null
    [Environment]::SetEnvironmentVariable('GIM_SETUP_FIXTURE_SAVE_ROOT', $saveRoot, 'Process')
    $fixtureCode = 'import os; from app.services.campaign_service import CampaignService; campaign = CampaignService(os.environ["GIM_SETUP_FIXTURE_SAVE_ROOT"]).create_campaign("Build only Setup fixture", "Temporary guild"); print(campaign.database_path)'
    $fixtureOutput = & $python -c $fixtureCode
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível criar o save temporário de regressão (exit=$LASTEXITCODE)." }
    $savePath = [System.IO.Path]::GetFullPath(($fixtureOutput | Select-Object -Last 1).Trim())
    $savePrefix = [System.IO.Path]::GetFullPath($saveRoot).TrimEnd('\') + '\'
    if (-not $savePath.StartsWith($savePrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $savePath -PathType Leaf)) {
        throw "O save-fixture ficou fora do perfil isolado: $savePath"
    }
    $saveHashBefore = (Get-FileHash -LiteralPath $savePath -Algorithm SHA256).Hash

    $setupResultPath = Join-Path $evidence 'setup-result.txt'
    [Environment]::SetEnvironmentVariable('GIM_SETUP_RESULT', $setupResultPath, 'Process')
    [Environment]::SetEnvironmentVariable('GIM_SETUP_EXPECTED_LOCALAPPDATA', $localAppData, 'Process')
    [Environment]::SetEnvironmentVariable('GIM_SETUP_NO_SHORTCUT', '1', 'Process')
    $installer = Start-Process -FilePath $setup -WorkingDirectory (Split-Path -Parent $setup) -PassThru -WindowStyle Hidden
    if (-not $installer.WaitForExit(300000)) {
        $runningInstaller = Get-Process -Id $installer.Id -ErrorAction SilentlyContinue
        if ($runningInstaller -and $runningInstaller.Path -and [IO.Path]::GetFullPath($runningInstaller.Path).Equals($setup, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $runningInstaller.Id -Force
        }
        throw 'Setup.exe excedeu o limite de 300 segundos.'
    }
    if ($installer.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $setupResultPath -PathType Leaf)) {
        $detail = if (Test-Path -LiteralPath $setupResultPath) { Get-Content -LiteralPath $setupResultPath -Raw } else { 'sem resultado do Setup' }
        throw "Setup.exe falhou (exit=$($installer.ExitCode)): $detail"
    }

    $expectedInstall = [System.IO.Path]::GetFullPath((Join-Path $localAppData 'Programs\GuildIdleManager'))
    $setupResult = (Get-Content -LiteralPath $setupResultPath -Raw).Trim() -split '\|'
    if ($setupResult.Count -ne 4 -or $setupResult[0] -ne 'SUCCESS' -or $setupResult[1] -ne $ExpectedVersion -or
        -not [System.IO.Path]::GetFullPath($setupResult[2]).Equals($expectedInstall, [StringComparison]::OrdinalIgnoreCase) -or
        -not [System.IO.Path]::GetFullPath($setupResult[3]).Equals([System.IO.Path]::GetFullPath($localAppData), [StringComparison]::OrdinalIgnoreCase)) {
        throw "O Setup não confirmou a instalação no perfil temporário esperado: $($setupResult -join '|')"
    }

    $markerPath = Join-Path $expectedInstall '.gim-desktop-install.json'
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) { throw 'Marcador de instalação não encontrado.' }
    $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
    if ($marker.product -ne 'org.guildidlemanager.desktop' -or $marker.channel -ne 'DEV' -or $marker.version -ne $ExpectedVersion) {
        throw "Marcador de instalação inesperado: $($marker | ConvertTo-Json -Compress)"
    }

    $saveHashAfter = (Get-FileHash -LiteralPath $savePath -Algorithm SHA256).Hash
    if ($saveHashAfter -ne $saveHashBefore) { throw 'O Setup alterou o save-fixture temporário.' }

    $installedExe = Join-Path $expectedInstall 'GuildIdleManager.exe'
    $versionResult = Join-Path $evidence 'installed-version.txt'
    [Environment]::SetEnvironmentVariable('GIM_VERSION_RESULT', $versionResult, 'Process')
    $versionProcess = Start-Process -FilePath $installedExe -ArgumentList '--version' -PassThru -Wait -WindowStyle Hidden
    if ($versionProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $versionResult -PathType Leaf) -or
        (Get-Content -LiteralPath $versionResult -Raw).Trim() -ne $ExpectedVersion) {
        throw 'A cópia instalada não confirmou a versão esperada.'
    }

    $campaignEvidence = Invoke-CandidateSmoke $installedExe '--smoke' 'GIM_SMOKE_RESULT' (Join-Path $evidence 'installed-campaign-smoke.txt') '^PASS: SQLite, campanhas temporárias, seleção de campanhas' 120000
    $launcherEvidence = Invoke-CandidateSmoke $installedExe '--launcher-smoke' 'GIM_LAUNCHER_SMOKE_RESULT' (Join-Path $evidence 'installed-launcher-smoke.txt') '^PASS: packaged launcher entry' 30000
    $setupHash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash
    $evidenceObject = [ordered]@{
        schema_version = 1
        setup_sha256 = $setupHash
        version = $ExpectedVersion
        installed_marker = $marker
        save_sha256_before = $saveHashBefore
        save_sha256_after = $saveHashAfter
        setup_result = Get-Content -LiteralPath $setupResultPath -Raw
        campaign_smoke = $campaignEvidence
        launcher_smoke = $launcherEvidence
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $evidence 'candidate-setup-validation.json'),
        ($evidenceObject | ConvertTo-Json -Depth 5),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "PASS: Setup.exe instalado em perfil isolado; versão $ExpectedVersion; save-fixture preservado ($saveHashAfter)."
    Write-Host $campaignEvidence
    Write-Host $launcherEvidence
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
