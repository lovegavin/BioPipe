# Operon Operator Library: install the dependencies declared by the library.
#
#   .\install-dependencies.ps1 -ProfileDir <profile-dir> -DryRun
#   .\install-dependencies.ps1 -ProfileDir <profile-dir>
#   .\install-dependencies.ps1 -ProfileDir <profile-dir> -Tools
#
# The script re-launches itself with the interpreter recorded in server.json.
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Rest
)
$ErrorActionPreference = "Stop"
$python = $env:PYTHON
if (-not $python) { $python = "python" }
& $python (Join-Path $PSScriptRoot "install_dependencies.py") @Rest
exit $LASTEXITCODE
