param(
    [string]$OutputRoot,
    [ValidateSet('DEV', 'stable', 'beta')]
    [string]$Channel = 'DEV',
    [string]$GitHubOwner = 'Vitor41',
    [string]$GitHubRepo = 'guild_idle_manager',
    [string]$GitHubPublicKeyBase64
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repo

if ($GitHubOwner.Length -gt 39 -or $GitHubOwner -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$' -or $GitHubOwner.Contains('--')) {
    throw 'GitHubOwner precisa ser um slug GitHub de 1 a 39 caracteres alfanuméricos/hífens, sem hífen nas pontas.'
}
if ($GitHubRepo.Length -gt 100 -or $GitHubRepo -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$' -or
    $GitHubRepo.Contains('..') -or $GitHubRepo.EndsWith('.git', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'GitHubRepo precisa ser um slug GitHub válido de 1 a 100 caracteres.'
}

function Assert-ContainedNoReparsePoint([string]$Root, [string]$Target) {
    $resolvedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $resolvedTarget = [System.IO.Path]::GetFullPath($Target)
    if (-not $resolvedTarget.StartsWith(($resolvedRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside expected root: $resolvedTarget"
    }
    if (Test-Path -LiteralPath $resolvedRoot) {
        $rootItem = Get-Item -LiteralPath $resolvedRoot -Force
        if (($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing to use reparse point as operation root: $resolvedRoot"
        }
    }
    $cursor = $resolvedTarget
    while ($cursor.StartsWith(($resolvedRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing recursive or replacement operation through reparse point: $cursor"
            }
        }
        $parent = [System.IO.Directory]::GetParent($cursor)
        if (-not $parent) { break }
        $cursor = $parent.FullName
    }
    return $resolvedTarget
}

$distRoot = Assert-ContainedNoReparsePoint $repo (Join-Path $repo 'dist')
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
$stagingRoot = Join-Path $distRoot 'staging'
New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $stagingRoot ("gim-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
} else {
    if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
        $OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
    } else {
        $OutputRoot = [System.IO.Path]::GetFullPath((Join-Path $repo $OutputRoot))
    }
}
$buildRoot = Assert-ContainedNoReparsePoint $stagingRoot $OutputRoot
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

$python = Join-Path $repo '.venv-desktop\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Crie .venv-desktop e instale requirements-desktop-dev.txt antes do build.'
}
$publicKeyBytes = $null
if (-not [string]::IsNullOrWhiteSpace($GitHubPublicKeyBase64)) {
    try { $publicKeyBytes = [Convert]::FromBase64String($GitHubPublicKeyBase64) }
    catch { throw 'GitHubPublicKeyBase64 precisa ser Base64 válido.' }
    if ($publicKeyBytes.Length -ne 32) { throw 'A chave pública Ed25519 precisa conter 32 bytes.' }
}
$distributionConfigFile = Join-Path $buildRoot 'gim-release-config.json'
$distributionConfig = [ordered]@{
    schema_version = 1
    owner = $GitHubOwner
    repo = $GitHubRepo
    public_key_b64 = $GitHubPublicKeyBase64
}
$distributionConfigJson = ConvertTo-Json -InputObject $distributionConfig -Compress
[System.IO.File]::WriteAllText(
    $distributionConfigFile,
    $distributionConfigJson,
    [System.Text.UTF8Encoding]::new($false)
)
$previousDistributionConfigFile = $env:GIM_BUILD_RELEASE_CONFIG_FILE
$env:GIM_BUILD_RELEASE_CONFIG_FILE = $distributionConfigFile
try {
    & $python -m PyInstaller --noconfirm --clean --distpath $buildRoot --workpath (Join-Path $buildRoot 'pyinstaller-work') (Join-Path $repo 'packaging\desktop\GuildIdleManager.spec')
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminou com codigo $LASTEXITCODE" }
}
finally {
    if ($null -eq $previousDistributionConfigFile) { Remove-Item Env:GIM_BUILD_RELEASE_CONFIG_FILE -ErrorAction SilentlyContinue }
    else { $env:GIM_BUILD_RELEASE_CONFIG_FILE = $previousDistributionConfigFile }
    if (Test-Path -LiteralPath $distributionConfigFile) { Remove-Item -LiteralPath $distributionConfigFile -Force }
}

$packageRoot = Join-Path $buildRoot "GuildIdleManager-$Channel"
$packageRoot = Assert-ContainedNoReparsePoint $stagingRoot $packageRoot
if (Test-Path -LiteralPath $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
New-Item -ItemType Directory -Path $packageRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $buildRoot 'GuildIdleManager') -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $repo 'packaging\desktop\Install-Desktop-Dev.ps1') -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $repo 'docs\DEV_DESKTOP.md') -Destination $packageRoot
$zipName = "GuildIdleManager-$Channel.zip"
$zip = Join-Path $buildRoot $zipName
$zip = Assert-ContainedNoReparsePoint $stagingRoot $zip
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $zip -CompressionLevel Optimal
Write-Output "Pacote $Channel criado: $zip"

$installerName = "GuildIdleManager-$Channel-Setup.exe"
$installer = Join-Path $buildRoot $installerName
$installer = Assert-ContainedNoReparsePoint $stagingRoot $installer
$iexpressSource = Join-Path $env:TEMP ("gim_iexpress_" + [Guid]::NewGuid().ToString('N'))
$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP)
$iexpressSource = Assert-ContainedNoReparsePoint $tempRoot $iexpressSource
New-Item -ItemType Directory -Path $iexpressSource | Out-Null
Copy-Item -LiteralPath $zip -Destination (Join-Path $iexpressSource $zipName)
Copy-Item -LiteralPath (Join-Path $repo 'packaging\desktop\Install-Desktop-Dev.ps1') -Destination $iexpressSource
$sedPath = Join-Path $iexpressSource "GuildIdleManager-$Channel.sed"
$installerTemp = Join-Path $iexpressSource $installerName
$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$installerTemp
FriendlyName=Guild Idle Manager $Channel
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-Desktop-Dev.ps1 -Channel $Channel
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0="$zipName"
FILE1="Install-Desktop-Dev.ps1"
[SourceFiles]
SourceFiles0=$iexpressSource
[SourceFiles0]
%FILE0%=
%FILE1%=
"@
Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII
$iexpress = Join-Path $env:WINDIR 'System32\iexpress.exe'
& $iexpress /N /Q $sedPath
$iexpressExitCode = $LASTEXITCODE
if ($iexpressExitCode -ne 0) {
    throw "IExpress terminou com codigo $iexpressExitCode. ZIP e diagnosticos preservados em $iexpressSource."
}
$installerCreated = $false
$stableLengthSamples = 0
$previousLength = 0L
# IExpress can return before its background packaging process materializes the
# self-extracting Setup; keep waiting for the completed file and stable size.
for ($attempt = 0; $attempt -lt 300; $attempt++) {
    if (Test-Path -LiteralPath $installerTemp -PathType Leaf) {
        $fileInfo = Get-Item -LiteralPath $installerTemp
        if ($fileInfo.Length -gt 10MB -and $fileInfo.Length -eq $previousLength) {
            $stableLengthSamples++
        } else {
            $stableLengthSamples = 0
        }
        $previousLength = $fileInfo.Length
        if ($stableLengthSamples -ge 5) {
            $installerCreated = $true
            break
        }
    }
    Start-Sleep -Seconds 1
}
if (-not $installerCreated) {
    throw "IExpress terminou com codigo zero, mas nao materializou um Setup estavel em 300 segundos. ZIP e diagnosticos preservados em $iexpressSource."
}
$signature = [System.IO.File]::ReadAllBytes($installerTemp)
if ($signature.Length -lt 2 -or $signature[0] -ne 0x4D -or $signature[1] -ne 0x5A) {
    throw "IExpress produziu um arquivo que nao tem assinatura PE valida: $installerTemp"
}
if (Test-Path -LiteralPath $installer) {
    $installer = Assert-ContainedNoReparsePoint $distRoot $installer
    Remove-Item -LiteralPath $installer -Force
}
Move-Item -LiteralPath $installerTemp -Destination $installer
Assert-ContainedNoReparsePoint $distRoot $installer | Out-Null
Assert-ContainedNoReparsePoint $tempRoot $iexpressSource | Out-Null
Remove-Item -LiteralPath $iexpressSource -Recurse -Force
Write-Output "Instalador Windows $Channel criado: $installer"
Write-Output "Pasta de staging preservada: $buildRoot"
