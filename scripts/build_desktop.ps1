param([switch]$SkipFrontend, [string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$output = if ($OutputDirectory) { [System.IO.Path]::GetFullPath($OutputDirectory, $repo) } else { Join-Path $repo 'dist\BioPipe Studio' }
if (-not $env:DOTNET_CLI_HOME) { $env:DOTNET_CLI_HOME = Join-Path $repo '.local\dotnet' }
if (-not $env:NUGET_PACKAGES) { $env:NUGET_PACKAGES = Join-Path $repo '.local\nuget' }
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_NOLOGO = '1'
if (-not $SkipFrontend) {
    Push-Location (Join-Path $repo 'frontend')
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
}
& dotnet publish (Join-Path $repo 'desktop\BioPipeStudio.csproj') -c Release -o $output
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }
$frontendOutput = Join-Path $output 'frontend'
New-Item -ItemType Directory -Path $frontendOutput -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $repo 'frontend\dist') | Copy-Item -Destination $frontendOutput -Recurse -Force
# Preserve a locally configured Python/backend path on subsequent rebuilds.
$config = Join-Path $output 'biopipe-desktop.json'
if (-not (Test-Path -LiteralPath $config)) {
    Copy-Item -LiteralPath (Join-Path $repo 'desktop\biopipe-desktop.json') -Destination $config
}
Write-Output (Join-Path $output 'BioPipe Studio.exe')
