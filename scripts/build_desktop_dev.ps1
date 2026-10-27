$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repo

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

$python = Join-Path $repo '.venv-desktop\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Crie .venv-desktop e instale requirements-desktop-dev.txt antes do build.'
}
& $python -m PyInstaller --noconfirm --clean --distpath (Join-Path $repo 'dist') --workpath (Join-Path $repo 'build\pyinstaller') (Join-Path $repo 'packaging\desktop\GuildIdleManager.spec')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminou com codigo $LASTEXITCODE" }

$packageRoot = Join-Path $repo 'dist\GuildIdleManager-DEV'
$distRoot = Join-Path $repo 'dist'
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
$packageRoot = Assert-ContainedNoReparsePoint $distRoot $packageRoot
if (Test-Path -LiteralPath $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
New-Item -ItemType Directory -Path $packageRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'dist\GuildIdleManager') -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $repo 'packaging\desktop\Install-Desktop-Dev.ps1') -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $repo 'docs\DEV_DESKTOP.md') -Destination $packageRoot
$zip = Join-Path $repo 'dist\GuildIdleManager-DEV.zip'
$zip = Assert-ContainedNoReparsePoint $distRoot $zip
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $zip -CompressionLevel Optimal
Write-Output "Pacote DEV criado: $zip"

$installerName = 'GuildIdleManager-DEV-Setup.exe'
$installer = Join-Path $repo "dist\$installerName"
$installer = Assert-ContainedNoReparsePoint $distRoot $installer
$iexpressSource = Join-Path $env:TEMP ("gim_iexpress_" + [Guid]::NewGuid().ToString('N'))
$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP)
$iexpressSource = Assert-ContainedNoReparsePoint $tempRoot $iexpressSource
New-Item -ItemType Directory -Path $iexpressSource | Out-Null
Copy-Item -LiteralPath $zip -Destination (Join-Path $iexpressSource 'GuildIdleManager-DEV.zip')
Copy-Item -LiteralPath (Join-Path $repo 'packaging\desktop\Install-Desktop-Dev.ps1') -Destination $iexpressSource
$sedPath = Join-Path $iexpressSource 'GuildIdleManager-DEV.sed'
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
FriendlyName=Guild Idle Manager DEV
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-Desktop-Dev.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0="GuildIdleManager-DEV.zip"
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
for ($attempt = 0; $attempt -lt 90; $attempt++) {
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
    throw "IExpress terminou com codigo zero, mas nao materializou um Setup estavel. ZIP e diagnosticos preservados em $iexpressSource."
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
Write-Output "Instalador Windows DEV criado: $installer"
