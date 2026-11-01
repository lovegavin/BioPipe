param(
    [Parameter(Mandatory=$true)][string]$IgvDirectory,
    [Parameter(Mandatory=$true)][string]$JavaExecutable,
    [Parameter(Mandatory=$true)][string]$HandoffDirectory,
    [Parameter(Mandatory=$true)][string]$SettingsDirectory
)
$ErrorActionPreference = 'Stop'
$igvRoot = (Resolve-Path -LiteralPath $IgvDirectory).Path
$javaPath = (Resolve-Path -LiteralPath $JavaExecutable).Path
$handoffRoot = (Resolve-Path -LiteralPath $HandoffDirectory).Path
New-Item -ItemType Directory -Force -Path $SettingsDirectory | Out-Null
$settingsRoot = (Resolve-Path -LiteralPath $SettingsDirectory).Path
foreach ($item in @('igv.args', 'lib')) {
    if (-not (Test-Path -LiteralPath (Join-Path $igvRoot $item))) { throw "Missing IGV component: $item" }
}
foreach ($item in @('session.xml', 'synthetic.fa', 'synthetic.fa.fai', 'load-and-snapshot.bat.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $handoffRoot $item))) { throw "Missing handoff file: $item" }
}
# IGV is the intentionally visible application under test. These settings are
# local to the supplied task folder; no registry, PATH or global preferences edit.
$arguments = @('-Xmx1g', '--module-path=lib', '@igv.args',
    ('"-Duser.home=' + $settingsRoot + '"'),
    '--module=org.igv/org.broad.igv.ui.Main',
    '--igvDirectory', ('"' + $settingsRoot + '"'),
    '-g', ('"' + (Join-Path $handoffRoot 'synthetic.fa') + '"'),
    '-b', ('"' + (Join-Path $handoffRoot 'load-and-snapshot.bat.txt') + '"'))
$process = Start-Process -FilePath $javaPath -ArgumentList $arguments -WorkingDirectory $igvRoot `
    -WindowStyle Normal -PassThru -RedirectStandardOutput (Join-Path $settingsRoot 'stdout.log') `
    -RedirectStandardError (Join-Path $settingsRoot 'stderr.log')
[pscustomobject]@{ pid=$process.Id; igv=$igvRoot; settings=$settingsRoot; session=(Join-Path $handoffRoot 'session.xml') } | ConvertTo-Json
