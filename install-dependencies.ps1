# BioPipe Operator Library: install the dependencies declared by the library.
#
#   .\install-dependencies.ps1 -ProfileDir C:\BioPipe -DryRun
#   .\install-dependencies.ps1 -ProfileDir C:\BioPipe
#   .\install-dependencies.ps1 -ProfileDir C:\BioPipe -Tools
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
